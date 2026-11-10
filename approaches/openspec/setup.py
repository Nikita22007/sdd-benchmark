"""Prepare an OpenSpec workspace before the executor starts."""
import os
import shutil
import subprocess
import sys

# OpenSpec tool ids differ from benchmark harness names.
TOOLS = {"deepseek": "dsh", "qwen-code": "qwen", "codex": "codex"}


def resolve():
    return shutil.which("openspec.cmd") or shutil.which("openspec")


def main():
    cli = resolve()
    if not cli:
        print(
            "OpenSpec CLI is required: npm install -g @fission-ai/openspec",
            file=sys.stderr,
        )
        return 2
    version = subprocess.run([cli, "--version"], capture_output=True, text=True)
    if version.returncode != 0:
        print("OpenSpec CLI is not runnable: " + version.stderr.strip(), file=sys.stderr)
        return 2
    print("OpenSpec CLI: " + version.stdout.strip())
    tool = TOOLS.get(os.environ.get("BENCH_HARNESS", ""), "codex")
    init = subprocess.run(
        [cli, "init", "--tools", tool, "--language", "Russian", "--no-animation", "--force"],
        capture_output=True,
        text=True,
    )
    sys.stdout.write(init.stdout)
    sys.stderr.write(init.stderr)
    return init.returncode


if __name__ == "__main__":
    sys.exit(main())
