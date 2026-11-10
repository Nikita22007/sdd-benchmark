"""Aggregate a series of runs into counts, coverage and spend.

A benchmark answers with a series, not with one run: how many runs were started, how many ended
with a verdict, how many were graded independently, and what they cost. Missing data is counted
as missing, never as zero.
"""
import argparse
import json
from pathlib import Path
import statistics
import sys

OUTCOMES = ("PASS", "FAIL_PRODUCT", "FAIL_PROCESS", "TIMEOUT", "EVAL_ERROR", "INFRA_ERROR")
TOKEN_FIELDS = ("input_tokens", "output_tokens")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def usage_totals(telemetry):
    """Sum what the harness reported, and say whether every request contributed."""
    totals = {field: 0 for field in TOKEN_FIELDS}
    complete = True
    telemetry = telemetry or {}
    requests = telemetry.get("requests") or telemetry.get("turns") or []
    for request in requests:
        for field in TOKEN_FIELDS:
            entry = (request.get("usage") or {}).get(field) or {}
            value = entry.get("value")
            if value is None:
                complete = False
                continue
            totals[field] += value
    return {**totals, "usage_complete": bool(requests) and complete}


def row(run_dir):
    result = load(run_dir / "result.json")
    telemetry_path = run_dir / "telemetry.json"
    telemetry = load(telemetry_path) if telemetry_path.is_file() else None
    agent = result.get("agent") or {}
    judgement = result.get("judge") or {}
    return {
        "run_id": result.get("run_id") or run_dir.name,
        "task": result.get("task"),
        "approach": result.get("approach"),
        "harness": result.get("harness"),
        "outcome": result.get("outcome") or ("PASS" if result.get("status") == "passed" else "FAIL_PRODUCT"),
        "agent_seconds": agent.get("duration_seconds"),
        **usage_totals(telemetry),
        "graded": judgement.get("status") == "completed",
        "judge_score": judgement.get("score"),
    }


def collect(runs_root):
    root = Path(runs_root)
    rows = []
    for run_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        if (run_dir / "result.json").is_file():
            rows.append(row(run_dir))
    return rows


def median(values):
    present = [value for value in values if value is not None]
    return round(statistics.median(present), 3) if present else None


def group(rows, key):
    groups = {}
    for item in rows:
        groups.setdefault(item[key], []).append(item)
    return groups


def summarise(rows):
    started = len(rows)
    graded = sum(1 for item in rows if item["graded"])
    counts = {name: sum(1 for item in rows if item["outcome"] == name) for name in OUTCOMES}
    return {
        "runs": {
            "started": started,
            "completed": sum(1 for item in rows if item["outcome"] != "INFRA_ERROR"),
            "graded": graded,
            "passed": counts["PASS"],
            "pass_rate": round(counts["PASS"] / started, 4) if started else None,
            "grade_coverage": round(graded / started, 4) if started else None,
        },
        "outcomes": counts,
        "usage": {
            "runs_with_complete_usage": sum(1 for item in rows if item["usage_complete"]),
            "median_input_tokens": median([item["input_tokens"] for item in rows if item["usage_complete"]]),
            "median_output_tokens": median([item["output_tokens"] for item in rows if item["usage_complete"]]),
            "median_agent_seconds": median([item["agent_seconds"] for item in rows]),
        },
        "by_approach": group_summary(rows, "approach"),
        "by_harness": group_summary(rows, "harness"),
        "by_task": group_summary(rows, "task"),
    }


def group_summary(rows, key):
    result = {}
    for name, items in group(rows, key).items():
        passed = sum(1 for item in items if item["outcome"] == "PASS")
        result[str(name or "unknown")] = {
            "runs": len(items),
            "passed": passed,
            "pass_rate": round(passed / len(items), 4),
            "median_agent_seconds": median([item["agent_seconds"] for item in items]),
            "median_input_tokens": median([item["input_tokens"] for item in items if item["usage_complete"]]),
        }
    return result


def render(summary):
    lines = [
        "runs: {started} started, {completed} completed, {graded} graded, {passed} passed".format(**summary["runs"]),
        "pass rate: {pass_rate} | grade coverage: {grade_coverage}".format(**summary["runs"]),
        "",
        "| outcome | runs |",
        "|---|---|",
    ]
    lines += [f"| {name} | {count} |" for name, count in summary["outcomes"].items() if count]
    lines += [
        "",
        "| group | runs | passed | pass rate | median s | median input tokens |",
        "|---|---|---|---|---|---|",
    ]
    for key in ("by_approach", "by_harness", "by_task"):
        for name, values in summary[key].items():
            lines.append(
                f"| {key[3:]} {name} | {values['runs']} | {values['passed']} | "
                f"{values['pass_rate']} | {values['median_agent_seconds']} | {values['median_input_tokens']} |"
            )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Summarise a series of benchmark runs")
    parser.add_argument("runs", nargs="*", help="run directories; defaults to runs/ next to this file")
    parser.add_argument("--json", help="write the summary to this path")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent / "runs"
    directories = [Path(item) for item in args.runs] or sorted(
        path for path in root.iterdir() if path.is_dir() and (path / "result.json").is_file()
    )
    rows = [row(path) for path in directories if (path / "result.json").is_file()]
    if not rows:
        print("No runs found", file=sys.stderr)
        return 2
    summary = summarise(rows)
    if args.json:
        Path(args.json).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(render(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
