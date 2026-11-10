"""Deterministic judge used to verify the judging pipeline without a model."""
import json
import os
import sys


def main():
    workspace = os.environ.get("BENCH_WORKSPACE", "")
    data = {
        "score": 1.0,
        "verdict": "stub judge: solution not inspected",
        "criteria": [],
        "notes": "deterministic stub, no model call; input paths were passed correctly"
        if workspace and os.path.isdir(workspace)
        else "workspace is missing",
    }
    sys.stdout.buffer.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
