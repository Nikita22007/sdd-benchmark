import tempfile
import unittest
from pathlib import Path

from benchmark import (
    approach_steps,
    outcome_of,
    required_artifacts,
    step_prompt,
    steps_telemetry,
)


class StepsTests(unittest.TestCase):
    def test_steps_are_read_and_validated(self):
        approach = {"steps": [{"name": "propose"}, {"name": "apply"}]}
        self.assertEqual([step["name"] for step in approach_steps(approach)], ["propose", "apply"])
        self.assertEqual(approach_steps({}), [])

    def test_duplicate_or_missing_names_are_rejected(self):
        with self.assertRaises(ValueError):
            approach_steps({"steps": [{"name": "a"}, {"name": "a"}]})
        with self.assertRaises(ValueError):
            approach_steps({"steps": [{"name": ""}]})
        with self.assertRaises(ValueError):
            approach_steps({"steps": "propose"})

    def test_prompt_uses_the_harness_specific_invocation(self):
        step = {"name": "propose", "invoke": {"codex": "$openspec-propose", "qwen-code": "/opsx-propose"}}
        self.assertIn("$openspec-propose", step_prompt(step, "codex", "сделай поиск"))
        self.assertIn("/opsx-propose", step_prompt(step, "qwen-code", "сделай поиск"))
        self.assertIn("сделай поиск", step_prompt(step, "unknown", "сделай поиск"))

    def test_required_artifacts_are_checked_by_glob(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work / "openspec" / "changes" / "add-x").mkdir(parents=True)
            ok, matches = required_artifacts(work, {"require_glob": "openspec/changes/*/tasks.md"})
            self.assertFalse(ok)
            self.assertEqual(matches, [])
            (work / "openspec" / "changes" / "add-x" / "tasks.md").write_text("- [ ] 1\n", encoding="utf-8")
            ok, matches = required_artifacts(work, {"require_glob": "openspec/changes/*/tasks.md"})
            self.assertTrue(ok)
            self.assertEqual(matches, ["openspec/changes/add-x/tasks.md"])
            self.assertEqual(required_artifacts(work, {}), (None, []))


class StepsTelemetryTests(unittest.TestCase):
    def test_per_step_usage_becomes_one_request_row_per_step(self):
        record = [
            {"name": "propose", "usage": {"input_tokens": 100, "output_tokens": 10}},
            {"name": "apply", "usage": {"input_tokens": 50}},
            {"name": "sync", "usage": None},
        ]
        telemetry = steps_telemetry(record)
        self.assertEqual(telemetry["source"], "steps")
        self.assertEqual(telemetry["request_usage"], "reported")
        self.assertEqual([row["step"] for row in telemetry["requests"]], ["propose", "apply"])
        self.assertEqual(telemetry["requests"][0]["usage"]["input_tokens"]["value"], 100)
        self.assertEqual(telemetry["requests"][1]["usage"]["output_tokens"]["provenance"], "missing")

    def test_empty_step_usage_is_reported_as_missing(self):
        telemetry = steps_telemetry([{"name": "propose", "usage": None}])
        self.assertEqual(telemetry["request_usage"], "missing")
        self.assertEqual(telemetry["requests"], [])
        self.assertTrue(telemetry["note"])


class ProtocolOutcomeTests(unittest.TestCase):
    def test_failed_step_outranks_a_passing_product(self):
        ok = {"status": "completed", "exit_code": 0, "duration_seconds": 1}
        protocol = {"mode": "phased", "failed_step": "propose", "reason": "required artifacts missing"}
        self.assertEqual(outcome_of(None, ok, ok, {}, True, protocol), "FAIL_PROCESS")

    def test_single_run_protocol_keeps_pass(self):
        ok = {"status": "completed", "exit_code": 0, "duration_seconds": 1}
        self.assertEqual(outcome_of(None, ok, ok, {}, True, {"mode": "single"}), "PASS")


if __name__ == "__main__":
    unittest.main()
