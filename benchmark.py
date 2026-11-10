import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

from telemetry import unavailable

ROOT = Path(__file__).resolve().parent

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

def run(task_name, approach_name, harness_name, timeout, allow_model, harness_config):
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
    task = load(task_dir / "task.json")
    approach = load(approach_dir / "approach.json")
    started_at = dt.datetime.now(dt.timezone.utc).isoformat()
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    out = ROOT / "runs" / run_id
    work = out / "workspace"
    out.mkdir(parents=True)
    shutil.copytree(task_dir / "project", work)
    shutil.copytree(task_dir / "context", work / "sdd-context")
    shutil.copyfile(task_dir / "request.md", work / "TASK.md")
    shutil.copyfile(approach_dir / "instructions.md", work / "APPROACH.md")
    env = os.environ.copy()
    env.update({"BENCH_WORKSPACE": str(work), "BENCH_TASK": str(work / "TASK.md"), "BENCH_CONTEXT": str(work / "sdd-context"), "BENCH_APPROACH": str(work / "APPROACH.md"), "BENCH_PYTHON": sys.executable})
    def expand(command):
        return [part.replace("{python}", sys.executable).replace("{approach}", str(approach_dir)).replace("{task}", str(task_dir)).replace("{harness}", str(harness_dir)) for part in command]
    (out / "harness-parameters.json").write_text(json.dumps(overrides, ensure_ascii=False, indent=2), encoding="utf-8")
    env["BENCH_HARNESS_CONFIG"] = str(out / "harness-parameters.json")
    env["BENCH_HARNESS_DIR"] = str(harness_dir)
    env["BENCH_AGENT_STDOUT"] = str(out / "agent" / "stdout.bin")
    for name in ("setup", "agent", "evaluation", "telemetry"):
        (out / name).mkdir()
    setup = None
    if approach.get("setup_command"):
        setup = execute(expand(approach["setup_command"]), work, env, timeout, out / "setup")
    agent = None
    if setup is None or (setup["status"] == "completed" and setup["exit_code"] == 0):
        agent = execute(expand(harness["command"]), work, env, timeout, out / "agent")
    evaluation = None
    if agent is not None and agent["status"] == "completed" and agent["exit_code"] == 0:
        evaluation = execute(expand(task["evaluation_command"]), task_dir / "evaluation", env, timeout, out / "evaluation")
    passed = evaluation is not None and evaluation["status"] == "completed" and evaluation["exit_code"] == 0
    telemetry = unavailable()
    if agent is not None and harness.get("telemetry_command"):
        adapter = execute(expand(harness["telemetry_command"]), work, env, timeout, out / "telemetry")
        if adapter["status"] == "completed" and adapter["exit_code"] == 0:
            try:
                telemetry = load(out / "telemetry" / "stdout.bin")
                if not isinstance(telemetry, dict):
                    raise ValueError("telemetry adapter output must be an object")
            except (ValueError, UnicodeDecodeError) as error:
                adapter["status"] = "invalid_output"
                adapter["error"] = str(error)
        telemetry["adapter"] = adapter
    (out / "telemetry.json").write_text(json.dumps(telemetry, ensure_ascii=False, indent=2), encoding="utf-8")
    result = {"schema_version": 1, "run_id": run_id, "task": task_name, "approach": approach_name, "harness": harness_name, "setup": setup, "started_at": started_at, "agent": agent, "evaluation": evaluation, "status": "passed" if passed else "failed"}
    (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("Artifacts:", out)
    return 0 if passed else 1

def main():
    parser = argparse.ArgumentParser(description="SDD benchmark prototype")
    parser.add_argument("--task", required=True)
    parser.add_argument("--approach", required=True)
    parser.add_argument("--harness", required=True)
    parser.add_argument("--harness-config", help="path to JSON parameters for harness adapter")
    parser.add_argument("--allow-model", action="store_true", help="explicitly allow model-backed harnesses")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    for value in (args.task, args.approach, args.harness):
        if not value or value in (".", "..") or Path(value).name != value or "/" in value or "\\" in value:
            parser.error("task and approach must be directory names")
    if args.timeout <= 0:
        parser.error("timeout must be positive")
    try:
        return run(args.task, args.approach, args.harness, args.timeout, args.allow_model, args.harness_config)
    except (OSError, ValueError, KeyError) as error:
        print("Benchmark error:", error, file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
