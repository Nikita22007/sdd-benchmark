import json
import tempfile
import unittest
from pathlib import Path

import summary
from benchmark import outcome_of


def write_run(root, name, outcome, tokens=None, judge=None, seconds=1.0):
    run_dir = root / name
    run_dir.mkdir(parents=True)
    result = {
        "run_id": name,
        "task": "catalog-search",
        "approach": "openspec",
        "harness": "codex",
        "outcome": outcome,
        "status": "passed" if outcome == "PASS" else "failed",
        "agent": {"status": "completed", "exit_code": 0, "duration_seconds": seconds},
        "judge": {"name": "stub", "status": judge or "skipped", "score": 1.0 if judge else None},
    }
    (run_dir / "result.json").write_text(json.dumps(result), encoding="utf-8")
    if tokens is not None:
        telemetry = {
            "requests": [
                {"usage": {"input_tokens": {"value": tokens[0], "provenance": "reported"}, "output_tokens": {"value": tokens[1], "provenance": "reported"}}}
            ]
        }
        (run_dir / "telemetry.json").write_text(json.dumps(telemetry), encoding="utf-8")
    return run_dir


class OutcomeTests(unittest.TestCase):
    def test_timeout_is_reported_before_product_verdict(self):
        timeout = {"status": "timeout", "exit_code": None, "duration_seconds": 1}
        self.assertEqual(outcome_of(None, timeout, None, {}, False), "TIMEOUT")

    def test_broken_protocol_is_not_counted_as_pass(self):
        ok = {"status": "completed", "exit_code": 0, "duration_seconds": 1}
        self.assertEqual(outcome_of(None, ok, ok, {"marker": "x/*.md", "ready": False}, True), "FAIL_PROCESS")

    def test_failed_check_is_a_product_failure(self):
        ok = {"status": "completed", "exit_code": 0, "duration_seconds": 1}
        failed = {"status": "completed", "exit_code": 1, "duration_seconds": 1}
        self.assertEqual(outcome_of(None, ok, failed, {}, False), "FAIL_PRODUCT")

    def test_missing_agent_is_an_infrastructure_error(self):
        self.assertEqual(outcome_of(None, None, None, {}, False), "INFRA_ERROR")


class SummaryTests(unittest.TestCase):
    def test_series_counts_and_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_run(root, "a", "PASS", tokens=(100, 10), judge="completed", seconds=2.0)
            write_run(root, "b", "FAIL_PRODUCT", tokens=(300, 30), seconds=4.0)
            write_run(root, "c", "TIMEOUT", seconds=6.0)
            rows = summary.collect(root)
            result = summary.summarise(rows)
            self.assertEqual(result["runs"]["started"], 3)
            self.assertEqual(result["runs"]["passed"], 1)
            self.assertEqual(result["runs"]["graded"], 1)
            self.assertAlmostEqual(result["runs"]["pass_rate"], 1 / 3, places=4)
            self.assertAlmostEqual(result["runs"]["grade_coverage"], 1 / 3, places=4)
            self.assertEqual(result["outcomes"]["TIMEOUT"], 1)
            self.assertEqual(result["usage"]["runs_with_complete_usage"], 2)
            self.assertEqual(result["usage"]["median_input_tokens"], 200)
            self.assertEqual(result["usage"]["median_agent_seconds"], 4.0)
            self.assertEqual(result["by_approach"]["openspec"]["passed"], 1)

    def test_missing_usage_is_not_counted_as_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_run(root, "a", "PASS", seconds=1.0)
            result = summary.summarise(summary.collect(root))
            self.assertEqual(result["usage"]["runs_with_complete_usage"], 0)
            self.assertIsNone(result["usage"]["median_input_tokens"])

    def test_render_lists_outcomes_and_groups(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_run(root, "a", "PASS", tokens=(10, 1), judge="completed")
            text = summary.render(summary.summarise(summary.collect(root)))
            self.assertIn("| PASS | 1 |", text)
            self.assertIn("approach openspec", text)


if __name__ == "__main__":
    unittest.main()
