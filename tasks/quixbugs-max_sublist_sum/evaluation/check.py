"""Run the task's JSON cases against the executor's module."""
import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = "max_sublist_sum"


def load(workspace):
    path = Path(workspace) / (NAME + ".py")
    spec = importlib.util.spec_from_file_location("bench_" + NAME, path)
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load " + str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    workspace = os.environ["BENCH_WORKSPACE"]
    cases = [
        json.loads(line)
        for line in (HERE / "testcases.json").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    module = load(workspace)
    function = getattr(module, NAME, None)
    if function is None:
        print("function " + NAME + " is missing", file=sys.stderr)
        return 1
    failures = 0
    for index, (arguments, expected) in enumerate(cases, 1):
        try:
            got = function(*arguments)
        except Exception as error:
            failures += 1
            print("case %d: raised %s: %s" % (index, type(error).__name__, error), file=sys.stderr)
            continue
        if not isinstance(got, type(expected)) and hasattr(got, "__iter__") and not isinstance(got, (str, bytes)):
            got = list(got)
        if got != expected:
            failures += 1
            print("case %d: expected %r, got %r" % (index, expected, got), file=sys.stderr)
    print("%d cases, %d failed" % (len(cases), failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
