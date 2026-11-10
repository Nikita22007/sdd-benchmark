"""Adapter that runs one benchmark attempt through the DeepSeek Harness CLI in headless mode."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_ARGS = ["headless", "--json", "--permission-mode", "workspace-write", "--approval-policy", "never"]


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
    dsh = resolve(config.get("executable", "dsh"))
    if not dsh:
        print("DeepSeek Harness CLI is required (dsh)", file=sys.stderr)
        return 2
    args = config.get("args", DEFAULT_ARGS)
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        print("args must be a list of strings", file=sys.stderr)
        return 2
    patch = config.get("patch")
    if patch:
        args = [*args, "--patch", str(Path(patch).resolve())]
    prompt = config.get("prompt") or default_prompt()
    env = os.environ.copy()
    key_file = config.get("api_key_file")
    if key_file:
        path = Path(key_file)
        if not path.is_file():
            print("api_key_file not found: " + str(path), file=sys.stderr)
            return 2
        env["DEEPSEEK_API_KEY"] = path.read_text(encoding="utf-8").strip()
    return subprocess.run([dsh, *args, prompt], cwd=os.environ["BENCH_WORKSPACE"], env=env).returncode


if __name__ == "__main__":
    sys.exit(main())
