"""Adapter that runs one benchmark attempt through the Codex CLI."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_ARGS = ["exec", "--skip-git-repo-check", "--sandbox", "workspace-write", "--json"]


def default_prompt():
    """Hand over the task, the approach instructions and the project context."""
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


def main():
    config = json.loads(Path(os.environ["BENCH_HARNESS_CONFIG"]).read_text(encoding="utf-8"))
    codex = resolve(config.get("executable", "codex"))
    if not codex:
        print("Codex CLI is required", file=sys.stderr)
        return 2
    args = config.get("args", DEFAULT_ARGS)
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        print("args must be a list of strings", file=sys.stderr)
        return 2
    prompt = config.get("prompt") or default_prompt()
    workspace = os.environ["BENCH_WORKSPACE"]
    # An inherited stdin lets the CLI wait forever for an answer; EOF fails fast instead.
    return subprocess.run(
        [codex, *args, "-C", workspace, prompt], stdin=subprocess.DEVNULL
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
