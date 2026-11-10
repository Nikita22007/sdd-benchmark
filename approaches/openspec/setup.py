import shutil, subprocess, sys
npx = shutil.which("npx.cmd") or shutil.which("npx")
if not npx:
    print("npx is required", file=sys.stderr)
    sys.exit(2)
sys.exit(subprocess.run([npx, "--yes", "@fission-ai/openspec@1.16.0", "init", "--tools", "none", "--language", "Russian", "--no-animation"]).returncode)

