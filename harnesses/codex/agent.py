import os, shutil, subprocess, sys
codex = shutil.which("codex.cmd") or shutil.which("codex")
if not codex:
    print("Codex CLI is required", file=sys.stderr)
    sys.exit(2)
prompt = "Прочитайте TASK.md, APPROACH.md и все документы в sdd-context/. Выполните задание, следуя APPROACH.md. Работайте в текущем каталоге."
sys.exit(subprocess.run([codex, "exec", "--skip-git-repo-check", "--sandbox", "workspace-write", "--json", "-C", os.environ["BENCH_WORKSPACE"], prompt]).returncode)
