"""Ask Codex to grade one attempt against the task package instructions and reference."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_ARGS = ["exec", "--skip-git-repo-check", "--sandbox", "read-only", "--json"]


def read(name):
    return Path(os.environ[name]).read_text(encoding="utf-8")


def build_prompt():
    return "\n\n".join(
        [
            "Вы независимый оценщик результатов SDD-бенчмарка. Оцените рабочую копию исполнителя.",
            "## Инструкции оценки\n" + read("BENCH_JUDGE_INSTRUCTIONS"),
            "## Эталон\n" + read("BENCH_JUDGE_REFERENCE"),
            "## Запрос задачи\n" + read("BENCH_TASK"),
            "Верните только один JSON-объект с полями score, verdict, criteria и notes.",
        ]
    )


def extract(text):
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("judge reply contains no JSON object")


def resolve(executable):
    return (
        shutil.which(executable + ".cmd")
        or shutil.which(executable)
        or (executable if Path(executable).is_file() else None)
    )


def load_config():
    path = os.environ.get("BENCH_JUDGE_CONFIG")
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else {}


def main():
    config = load_config()
    codex = resolve(config.get("executable", "codex"))
    if not codex:
        print("Codex CLI is required", file=sys.stderr)
        return 2
    args = config.get("args", DEFAULT_ARGS)
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        print("args must be a list of strings", file=sys.stderr)
        return 2
    prompt = config.get("prompt") or build_prompt()
    workspace = os.environ["BENCH_WORKSPACE"]
    process = subprocess.run(
        [codex, *args, "-C", workspace, prompt],
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        sys.stderr.write(process.stderr)
        return process.returncode
    message = ""
    for line in process.stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item") or {}
        if event.get("type") == "item.completed" and item.get("type") == "agent_message":
            message = item.get("text", "")
    if not message:
        print("Codex returned no grading message", file=sys.stderr)
        return 2
    try:
        sys.stdout.buffer.write(json.dumps(extract(message), ensure_ascii=False).encode("utf-8"))
        sys.stdout.buffer.flush()
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
