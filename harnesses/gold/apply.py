"""Control harness: apply the task's reference solution to the working copy.

This is not an executor and never takes part in comparisons. It exists so the stand itself can be
checked without a model: if a scenario rejects the reference, the scenario or its check is wrong.
Access to the task package is deliberate and limited to `evaluation/reference.md`.
"""
import os
import re
import sys
from pathlib import Path

BLOCK = re.compile(r"```python\n(.*?)```", re.DOTALL)


def main():
    task_dir = Path(sys.argv[1])
    workspace = Path(os.environ["BENCH_WORKSPACE"])
    reference = (task_dir / "evaluation" / "reference.md").read_text(encoding="utf-8")
    match = BLOCK.search(reference)
    if match is None:
        print("reference.md has no python block", file=sys.stderr)
        return 2
    targets = sorted((task_dir / "project").glob("*.py"))
    if len(targets) != 1:
        print("project must contain exactly one python module", file=sys.stderr)
        return 2
    (workspace / targets[0].name).write_text(match.group(1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
