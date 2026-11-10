"""Summarise a results directory: runs, success rate and output size per agent."""
import json
import statistics
from pathlib import Path


def load(results_dir):
    root = Path(results_dir)
    if not root.is_dir():
        return []
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(root.glob("*.json"))
    ]


def summarise(records):
    groups = {}
    for record in records:
        groups.setdefault(record["agent"], []).append(record)
    summary = {}
    for agent, items in groups.items():
        passed = sum(1 for item in items if item["passed"])
        summary[agent] = {
            "runs": len(items),
            "passed": passed,
            "pass_rate": round(passed / len(items), 3),
            "median_chars": round(statistics.median(item["output_chars"] for item in items), 1),
            "median_seconds": round(statistics.median(item["duration_seconds"] for item in items), 4),
        }
    return summary


def render(summary):
    lines = [
        "| агент | прогонов | пройдено | доля | медиана символов | медиана с |",
        "|---|---|---|---|---|---|",
    ]
    for agent, values in sorted(summary.items()):
        lines.append(
            f"| {agent} | {values['runs']} | {values['passed']} | {values['pass_rate']} | "
            f"{values['median_chars']} | {values['median_seconds']} |"
        )
    return "\n".join(lines)
