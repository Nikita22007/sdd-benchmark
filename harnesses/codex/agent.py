import json, os, shutil, subprocess, sys
from pathlib import Path
config = json.loads(Path(os.environ["BENCH_HARNESS_CONFIG"]).read_text(encoding="utf-8"))
executable = config.get("executable", "codex")
codex = shutil.which(executable + ".cmd") or shutil.which(executable) or (executable if Path(executable).is_file() else None)
if not codex:
    print("Codex CLI is required", file=sys.stderr)
    sys.exit(2)
prompt = config.get("prompt", "Прочитайте TASK.md, APPROACH.md и все документы в sdd-context/. Выполните задание, следуя APPROACH.md. Работайте в текущем каталоге.")
args = config.get("args", ["exec", "--skip-git-repo-check", "--sandbox", "workspace-write", "--json"])
if not isinstance(args, list) or not all(isinstance(x, str) for x in args):
    sys.exit("args must be a list of strings")
sys.exit(subprocess.run([codex, *args, "-C", os.environ["BENCH_WORKSPACE"], prompt]).returncode)
