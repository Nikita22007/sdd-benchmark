import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import uuid

from telemetry import TOKEN_FIELDS, unavailable
from vendor.harness2 import runmark

ROOT = Path(__file__).resolve().parent

USAGE_NOTE = "usage is reported per turn only; per-phase spend is unavailable"
ISOLATION_NOTE = "closed checks stay outside the working copy; the executor's filesystem boundary is the harness sandbox"

# Names the executor never needs, borrowed from the reference method's scrub list.
SECRET_ENV = frozenset(
    {
        "DEEPSEEK_API_KEY",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "HARNESS2_JUDGE_API_KEY",
    }
)

# Text a grader writes; none of it belongs in the executor's working copy.
GRADER_MARKERS = (
    "judge.json",
    "n_passed",
    "n_criteria",
    "pass_rate",
    "deterministic_eval",
    "reference_answer",
)
TEXT_SUFFIXES = frozenset({".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".py", ".log", ".csv", ""})


def executor_env(base, harness_spec):
    """Copy the environment without secrets, keeping only what the harness declares it needs."""
    keep = set(harness_spec.get("env_keep") or ())
    env, dropped = {}, []
    for key, value in base.items():
        if key in SECRET_ENV and key not in keep:
            dropped.append(key)
            continue
        env[key] = value
    return env, sorted(dropped)


def install(home_root, harness_spec):
    """Materialise the harness's own configuration instead of inheriting the host's.

    `inherit` keeps the ambient home: that is honest for harnesses whose credentials live there,
    and the manifest records it. `home` builds `runs/<id>/home` from the package's declared files
    and points HOME, USERPROFILE and the declared variables at it.
    """
    spec = harness_spec.get("install") or {"mode": "inherit"}
    mode = spec.get("mode", "inherit")
    if mode == "inherit":
        return None, {}, {"mode": "inherit", "fingerprint": None, "files": [], "env": []}
    if mode != "home":
        raise ValueError(f"unknown install mode {mode!r}; expected inherit or home")
    files = spec.get("files") or {}
    home = Path(home_root)
    home.mkdir(parents=True, exist_ok=True)
    for relative, content in files.items():
        target = home / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    variables = {name: str(home) for name in spec.get("env") or ()}
    variables.setdefault("HOME", str(home))
    variables.setdefault("USERPROFILE", str(home))
    return home, variables, {
        "mode": "home",
        "fingerprint": runmark.fingerprint(home),
        "files": sorted(files),
        "env": sorted(variables),
    }


def grader_markers(work):
    """Find grader output that reached the working copy, by marker text."""
    hits = []
    for path in work.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            if path.stat().st_size > 2_000_000:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for marker in GRADER_MARKERS:
            if marker in text:
                hits.append(f"{path.relative_to(work)}:{marker}")
                break
    return sorted(hits)



def inside(child, parent):
    try:
        return child.resolve().is_relative_to(parent.resolve())
    except (OSError, ValueError):
        return False


def inspect_isolation(work, task_dir, agent_env, sandbox):
    """Prove what the executor could see, instead of assuming it."""
    evaluation = task_dir / "evaluation"
    digests = {}
    for path in evaluation.rglob("*"):
        if path.is_file():
            digests.setdefault(hashlib.sha256(path.read_bytes()).hexdigest(), path.name)
    copied = []
    for path in work.rglob("*"):
        if not path.is_file():
            continue
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            continue
        if digest in digests:
            copied.append(str(path.relative_to(work)))
    leaks = sorted(key for key, value in agent_env.items() if isinstance(value, str) and str(task_dir) in value)
    return {
        "workspace_outside_task_package": not inside(work, task_dir),
        "evaluation_outside_workspace": not inside(evaluation, work),
        "references_in_workspace": sorted(copied),
        "grader_markers": grader_markers(work),
        "env_exposes_task_package": leaks,
        "harness_sandbox": sandbox,
        "note": ISOLATION_NOTE,
    }


class IntentWatch:
    """Record when the executor first produced the approach's intent artifact."""

    def __init__(self, workspace, marker, interval=0.05):
        self.workspace = workspace
        self.marker = marker
        self.interval = interval
        self.started = time.monotonic()
        self.ready_at = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._poll, daemon=True)

    def _check(self):
        try:
            found = next(iter(self.workspace.glob(self.marker)), None)
        except (OSError, ValueError):
            return False
        if found is None:
            return False
        if self.ready_at is None:
            self.ready_at = round(time.monotonic() - self.started, 3)
        return True

    def _poll(self):
        while not self._stop.is_set():
            if self._check():
                return
            self._stop.wait(self.interval)

    def start(self):
        self._check()
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=5)
        if not self._thread.is_alive():
            self._check()
        return {
            "marker": self.marker,
            "ready": self.ready_at is not None,
            "elapsed_seconds": self.ready_at,
            "source": "filesystem watch",
        }

def phase(name, record):
    return {
        "name": name,
        "status": record["status"] if record else "skipped",
        "duration_seconds": record["duration_seconds"] if record else None,
        "usage": "turn" if name == "agent" and record else ("missing" if record else None),
    }

def approach_steps(approach):
    """The approach's declared steps, or an empty list for a single-session run."""
    steps = approach.get("steps") or []
    if not isinstance(steps, list):
        raise ValueError("approach steps must be a list")
    names = []
    for step in steps:
        if not isinstance(step, dict) or not isinstance(step.get("name"), str) or not step["name"].strip():
            raise ValueError("every step needs a non-empty name")
        names.append(step["name"])
    if len(set(names)) != len(names):
        raise ValueError("step names must be unique")
    return steps


def step_prompt(step, harness_name, task_text):
    invoke = (step.get("invoke") or {}).get(harness_name) or (step.get("invoke") or {}).get("default")
    parts = []
    if invoke:
        parts.append(f"Выполните шаг процесса: {invoke}.")
    parts.append("Запрос задачи:\n" + task_text.strip())
    parts.append(
        "Прочитайте TASK.md, APPROACH.md и все файлы в sdd-context/. "
        "Работайте только в текущем каталоге."
    )
    return "\n\n".join(parts)


def usage_from(telemetry):
    totals = {}
    for request in (telemetry or {}).get("requests") or []:
        for field, entry in (request.get("usage") or {}).items():
            if entry.get("value") is not None:
                totals[field] = totals.get(field, 0) + entry["value"]
    return totals


def required_artifacts(work, step):
    """Check the artifact the step is supposed to leave behind; None when the step declares none."""
    pattern = step.get("require_glob")
    if not pattern:
        return None, []
    matches = sorted(path.relative_to(work).as_posix() for path in work.glob(pattern))
    return bool(matches), matches


def steps_telemetry(steps_record):
    """One telemetry document for a phased run: one request row per step that reported usage."""
    rows = []
    for step in steps_record:
        usage = step.get("usage") or {}
        if not usage:
            continue
        fields = {
            field: {
                "value": usage.get(field),
                "provenance": "reported" if usage.get(field) is not None else "missing",
            }
            for field in TOKEN_FIELDS
        }
        rows.append({"index": len(rows) + 1, "state": "completed", "step": step["name"], "usage": fields})
    if not rows:
        return unavailable("no step reported usage")
    reported = any(any(field["value"] is not None for field in row["usage"].values()) for row in rows)
    return {
        "source": "steps",
        "scope": "step",
        "usage_granularity": "step",
        "request_usage": "reported" if reported else "missing",
        "sources": {"events": "per-step harness stdout", "usage": "per-step telemetry adapter"},
        "events": None,
        "invalid_lines": [],
        "requests": rows,
        "steps": [step["name"] for step in steps_record],
    }


def outcome_of(setup, agent, evaluation, intent, passed, protocol=None):
    """One terminal outcome per run: what the series can be counted by.

    Order matters: infrastructure and time limits are reported before a product verdict, and a
    broken SDD protocol before a passing product, so a run is never counted as a pass by accident.
    """
    for record in (setup, agent, evaluation):
        if record is None:
            continue
        if record["status"] == "timeout":
            return "TIMEOUT"
        if record["status"] == "error":
            return "INFRA_ERROR"
    if agent is None:
        return "INFRA_ERROR"
    if protocol and protocol.get("failed_step"):
        return "FAIL_PROCESS"
    if evaluation is None:
        return "FAIL_PRODUCT"
    if evaluation["status"] != "completed":
        return "EVAL_ERROR"
    if intent.get("marker") and intent.get("ready") is False:
        return "FAIL_PROCESS"
    return "PASS" if passed else "FAIL_PRODUCT"

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

def execute(command, cwd, env, timeout, log):
    started = time.monotonic()
    try:
        process = subprocess.run(command, cwd=cwd, env=env, capture_output=True, timeout=timeout)
        code, status = process.returncode, "completed"
        stdout, stderr = process.stdout, process.stderr
    except subprocess.TimeoutExpired as error:
        code, status = None, "timeout"
        stdout, stderr = error.stdout or b"", error.stderr or b""
    except OSError as error:
        code, status = None, "error"
        stdout, stderr = b"", str(error).encode("utf-8")
    (log / ("stdout.bin")).write_bytes(stdout)
    (log / ("stderr.bin")).write_bytes(stderr)
    return {"status": status, "exit_code": code, "duration_seconds": round(time.monotonic() - started, 3)}

def judge_result(raw):
    """Validate the model judge contract: a score, a verdict and optional criteria."""
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("judge output must be a JSON object")
    score = data.get("score")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 1:
        raise ValueError("judge score must be a number between 0 and 1")
    if not isinstance(data.get("verdict"), str) or not data["verdict"].strip():
        raise ValueError("judge verdict must be a non-empty string")
    criteria = data.get("criteria", [])
    if not isinstance(criteria, list):
        raise ValueError("judge criteria must be a list")
    return data

def run(task_name, approach_name, harness_name, timeout, allow_model, harness_config, judge_name=None):
    task_dir = ROOT / "tasks" / task_name
    approach_dir = ROOT / "approaches" / approach_name
    harness_dir = ROOT / "harnesses" / harness_name
    harness = load(harness_dir / "harness.json")
    overrides = load(Path(harness_config)) if harness_config else {}
    if not isinstance(overrides, dict):
        raise ValueError("harness config must be a JSON object")
    if any(key in overrides for key in ("requires_model", "command", "telemetry_command")):
        raise ValueError("harness config may only override parameters, not adapter commands or requires_model")
    if harness.get("requires_model", True) and not allow_model:
        raise ValueError("model harness requires explicit --allow-model")
    judge_dir = ROOT / "judges" / judge_name if judge_name else None
    judge_spec = load(judge_dir / "judge.json") if judge_dir else None
    if judge_spec and judge_spec.get("requires_model", True) and not allow_model:
        raise ValueError("model judge requires explicit --allow-model")
    task = load(task_dir / "task.json")
    approach = load(approach_dir / "approach.json")
    steps = approach_steps(approach)
    started_at = dt.datetime.now(dt.timezone.utc).isoformat()
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    out = ROOT / "runs" / run_id
    work = out / "workspace"
    out.mkdir(parents=True)
    shutil.copytree(task_dir / "project", work)
    shutil.copytree(task_dir / "context", work / "sdd-context")
    shutil.copyfile(task_dir / "request.md", work / "TASK.md")
    shutil.copyfile(approach_dir / "instructions.md", work / "APPROACH.md")
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "task": task_name,
        "approach": approach_name,
        "harness": harness_name,
        "judge": judge_name,
        "started_at": started_at,
        "inputs": runmark.inputs_fingerprint((work / "TASK.md").read_text(encoding="utf-8"), work),
        "approach_fingerprint": runmark.fingerprint(approach_dir),
        "harness_fingerprint": runmark.fingerprint(harness_dir),
        "judge_fingerprint": runmark.fingerprint(judge_dir) if judge_dir else None,
        "harness_parameters": overrides,
        "python": sys.version.split()[0],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    env, scrubbed = executor_env(os.environ, harness)
    home, home_vars, install_record = install(out / "home", harness)
    env.update(home_vars)
    env.update({"BENCH_WORKSPACE": str(work), "BENCH_TASK": str(work / "TASK.md"), "BENCH_CONTEXT": str(work / "sdd-context"), "BENCH_APPROACH": str(work / "APPROACH.md"), "BENCH_HARNESS": harness_name, "BENCH_PYTHON": sys.executable, "PYTHONIOENCODING": "utf-8"})
    manifest["install"] = install_record
    manifest["env_scrubbed"] = scrubbed
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    def expand(command):
        replacements = {"{python}": sys.executable, "{approach}": str(approach_dir), "{task}": str(task_dir), "{harness}": str(harness_dir), "{judge}": str(judge_dir) if judge_dir else ""}
        for key, value in replacements.items():
            command = [part.replace(key, value) for part in command]
        return command
    (out / "harness-parameters.json").write_text(json.dumps(overrides, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "judge-parameters.json").write_text("{}", encoding="utf-8")
    env["BENCH_JUDGE_CONFIG"] = str(out / "judge-parameters.json")
    env["BENCH_HARNESS_CONFIG"] = str(out / "harness-parameters.json")
    env["BENCH_HARNESS_DIR"] = str(harness_dir)
    env["BENCH_AGENT_STDOUT"] = str(out / "agent" / "stdout.bin")
    for name in ("setup", "agent", "evaluation", "telemetry", "judge"):
        (out / name).mkdir()
    setup = None
    if approach.get("setup_command"):
        setup = execute(expand(approach["setup_command"]), work, env, timeout, out / "setup")
    agent = None
    agent_env = dict(env)
    steps_record = []
    protocol = {"mode": "phased" if steps else "single", "total": len(steps), "completed": 0}
    intent = {"marker": approach.get("intent_marker"), "ready": None, "elapsed_seconds": None, "source": "not configured"}
    if setup is None or (setup["status"] == "completed" and setup["exit_code"] == 0):
        watch = IntentWatch(work, approach["intent_marker"]).start() if approach.get("intent_marker") else None
        agent_env = dict(env)
        task_text = (work / "TASK.md").read_text(encoding="utf-8")
        if steps:
            for step in steps:
                step_dir = out / "steps" / step["name"]
                step_dir.mkdir(parents=True)
                config_path = step_dir / "harness-parameters.json"
                config_path.write_text(
                    json.dumps({**overrides, "prompt": step_prompt(step, harness_name, task_text)}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                step_env = dict(env)
                step_env["BENCH_HARNESS_CONFIG"] = str(config_path)
                step_env["BENCH_AGENT_STDOUT"] = str(step_dir / "stdout.bin")
                record = execute(expand(harness["command"]), work, step_env, timeout, step_dir)
                entry = {"name": step["name"], "invoke": (step.get("invoke") or {}).get(harness_name), **record}
                step_telemetry = None
                if harness.get("telemetry_command") and record["status"] == "completed":
                    adapter = execute(expand(harness["telemetry_command"]), work, step_env, timeout, step_dir / "telemetry")
                    entry["telemetry"] = adapter
                    if adapter["status"] == "completed" and adapter["exit_code"] == 0:
                        try:
                            candidate = load(step_dir / "telemetry" / "stdout.bin")
                            step_telemetry = candidate if isinstance(candidate, dict) else None
                        except (ValueError, UnicodeDecodeError, OSError):
                            step_telemetry = None
                entry["usage"] = usage_from(step_telemetry) or None
                ok_artifacts, matches = required_artifacts(work, step)
                entry["artifacts_ok"] = ok_artifacts
                entry["artifacts"] = matches
                steps_record.append(entry)
                if record["status"] != "completed" or record["exit_code"] != 0:
                    protocol["failed_step"] = step["name"]
                    protocol["reason"] = "step did not complete"
                    break
                if ok_artifacts is False:
                    protocol["failed_step"] = step["name"]
                    protocol["reason"] = "required artifacts missing"
                    break
                protocol["completed"] += 1
            finished = protocol["completed"] == len(steps) and "failed_step" not in protocol
            last = steps_record[-1] if steps_record else None
            agent = {
                "status": "completed" if finished else (last["status"] if last else "error"),
                "exit_code": 0 if finished else ((last or {}).get("exit_code") if (last or {}).get("exit_code") is not None else 1),
                "duration_seconds": round(sum((item["duration_seconds"] or 0) for item in steps_record), 3),
            }
        else:
            agent = execute(expand(harness["command"]), work, env, timeout, out / "agent")
        if watch is not None:
            intent = watch.stop()
    isolation = inspect_isolation(work, task_dir, agent_env, harness.get("sandbox"))
    evaluation = None
    if agent is not None and agent["status"] == "completed" and agent["exit_code"] == 0:
        evaluation = execute(expand(task["evaluation_command"]), task_dir / "evaluation", env, timeout, out / "evaluation")
    passed = evaluation is not None and evaluation["status"] == "completed" and evaluation["exit_code"] == 0
    telemetry = unavailable("harness has no telemetry adapter")
    if steps and steps_record:
        telemetry = steps_telemetry(steps_record)
    elif agent is not None and harness.get("telemetry_command"):
        adapter = execute(expand(harness["telemetry_command"]), work, env, timeout, out / "telemetry")
        if adapter["status"] == "completed" and adapter["exit_code"] == 0:
            try:
                telemetry = load(out / "telemetry" / "stdout.bin")
                if not isinstance(telemetry, dict):
                    raise ValueError("telemetry adapter output must be an object")
            except (ValueError, UnicodeDecodeError) as error:
                adapter["status"] = "invalid_output"
                adapter["error"] = str(error)
        if adapter["status"] == "invalid_output":
            telemetry = unavailable("telemetry adapter output is invalid")
        elif adapter["status"] != "completed" or adapter["exit_code"] != 0:
            telemetry = unavailable("telemetry adapter did not complete")
        telemetry["adapter"] = adapter
    (out / "telemetry.json").write_text(json.dumps(telemetry, ensure_ascii=False, indent=2), encoding="utf-8")
    judge = {"name": judge_name, "status": "skipped", "score": None, "result": None, "note": None}
    judge_record = None
    if judge_spec is not None and agent is not None:
        env["BENCH_EVALUATION_DIR"] = str(task_dir / "evaluation")
        env["BENCH_JUDGE_INSTRUCTIONS"] = str(task_dir / "evaluation" / "instructions.md")
        env["BENCH_JUDGE_REFERENCE"] = str(task_dir / "evaluation" / "reference.md")
        judge_record = execute(expand(judge_spec["command"]), out / "judge", env, timeout, out / "judge")
        judge["adapter"] = judge_record
        if judge_record["status"] == "completed" and judge_record["exit_code"] == 0:
            try:
                parsed = judge_result((out / "judge" / "stdout.bin").read_text(encoding="utf-8"))
                judge.update({"status": "completed", "score": parsed["score"], "result": parsed})
            except (ValueError, UnicodeDecodeError) as error:
                judge.update({"status": "invalid_output", "note": str(error)})
        else:
            judge.update({"status": "failed", "note": "judge did not complete"})
    (out / "judge.json").write_text(json.dumps(judge, ensure_ascii=False, indent=2), encoding="utf-8")
    if steps and steps_record:
        phases = (
            [phase("setup", setup)]
            + [
                {
                    "name": f"step:{step['name']}",
                    "status": step["status"],
                    "duration_seconds": step["duration_seconds"],
                    "usage": "reported" if step.get("usage") else "missing",
                }
                for step in steps_record
            ]
            + [phase("evaluation", evaluation), phase("telemetry", telemetry.get("adapter")), phase("judge", judge_record)]
        )
    else:
        phases = [phase("setup", setup), phase("agent", agent), phase("evaluation", evaluation), phase("telemetry", telemetry.get("adapter")), phase("judge", judge_record)]
    result = {"schema_version": 1, "run_id": run_id, "task": task_name, "approach": approach_name, "harness": harness_name, "setup": setup, "started_at": started_at, "agent": agent, "evaluation": evaluation, "judge": {key: judge[key] for key in ("name", "status", "score", "note")}, "phases": phases, "steps": steps_record, "protocol": protocol, "intent": intent, "isolation": isolation, "manifest": manifest, "outcome": outcome_of(setup, agent, evaluation, intent, passed, protocol), "usage_note": USAGE_NOTE, "status": "passed" if passed else "failed"}
    (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("Artifacts:", out)
    return 0 if passed else 1

def main():
    parser = argparse.ArgumentParser(description="SDD benchmark prototype")
    parser.add_argument("--task", required=True)
    parser.add_argument("--approach", required=True)
    parser.add_argument("--harness", required=True)
    parser.add_argument("--judge", help="directory name of the judge package used for a separate model evaluation")
    parser.add_argument("--harness-config", help="path to JSON parameters for harness adapter")
    parser.add_argument("--allow-model", action="store_true", help="explicitly allow model-backed harnesses")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    for value in (args.task, args.approach, args.harness, args.judge):
        if value is None:
            continue
        if not value or value in (".", "..") or Path(value).name != value or "/" in value or "\\" in value:
            parser.error("task, approach, harness and judge must be directory names")
    if args.timeout <= 0:
        parser.error("timeout must be positive")
    try:
        return run(args.task, args.approach, args.harness, args.timeout, args.allow_model, args.harness_config, args.judge)
    except (OSError, ValueError, KeyError) as error:
        print("Benchmark error:", error, file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
