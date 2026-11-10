"""Adapter that runs one benchmark attempt through the Qwen Code CLI."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# `-p` is deprecated in favour of the positional prompt; `--approval-mode` is chosen because
# `--yolo` is not available in every build.
DEFAULT_APPROVAL = "auto"
DEFAULT_ARGS = ["--output-format", "stream-json"]


def default_prompt():
    return (
        "Вы исполнитель бенчмарка. Задача: {task}. Инструкции подхода: {approach}. "
        "Контекст проекта: все файлы в {context}. Прочитайте эти файлы, выполните задачу, "
        "строго следуя инструкциям подхода. Работайте только в текущем каталоге."
    ).format(
        task=os.environ.get("BENCH_TASK", "TASK.md"),
        approach=os.environ.get("BENCH_APPROACH", "APPROACH.md"),
        context=os.environ.get("BENCH_CONTEXT", "sdd-context"),
    )


def resolve(executable):
    return (
        shutil.which(executable + ".cmd")
        or shutil.which(executable)
        or (executable if Path(executable).is_file() else None)
    )


def build_args(config):
    if "args" in config:
        args = config["args"]
        if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
            raise ValueError("args must be a list of strings")
        return list(args)
    args = list(DEFAULT_ARGS)
    approval = config.get("approval_mode", DEFAULT_APPROVAL)
    if approval != "none":
        args += ["--approval-mode", str(approval)]
    return args


def main():
    config = json.loads(Path(os.environ["BENCH_HARNESS_CONFIG"]).read_text(encoding="utf-8"))
    qwen = resolve(config.get("executable", "qwen"))
    if not qwen:
        print("Qwen Code CLI is required", file=sys.stderr)
        return 2
    try:
        args = build_args(config)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    prompt = config.get("prompt") or default_prompt()
    # An inherited stdin lets the CLI wait forever for an answer; EOF fails fast instead.
    return subprocess.run(
        [qwen, *args, prompt], cwd=os.environ["BENCH_WORKSPACE"], stdin=subprocess.DEVNULL
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
