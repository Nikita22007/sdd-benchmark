import tempfile
import time
import unittest
from pathlib import Path

from benchmark import IntentWatch, phase


class IntentWatchTests(unittest.TestCase):
    def test_ready_boundary_is_recorded_when_marker_appears(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            watch = IntentWatch(workspace, "specs/*/tasks.md").start()
            time.sleep(0.1)
            marker = workspace / "specs" / "catalog" / "tasks.md"
            marker.parent.mkdir(parents=True)
            marker.write_text("- [ ] 1.1 Задача\n", encoding="utf-8")
            result = watch.stop()
            self.assertTrue(result["ready"])
            self.assertGreaterEqual(result["elapsed_seconds"], 0)
            self.assertEqual(result["marker"], "specs/*/tasks.md")
            self.assertEqual(result["source"], "filesystem watch")

    def test_missing_marker_is_not_reported_as_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            watch = IntentWatch(Path(directory), "specs/*/tasks.md").start()
            result = watch.stop()
            self.assertFalse(result["ready"])
            self.assertIsNone(result["elapsed_seconds"])


class PhaseTests(unittest.TestCase):
    def test_usage_granularity_is_recorded_per_phase(self):
        record = {"status": "completed", "exit_code": 0, "duration_seconds": 1.5}
        self.assertEqual(phase("agent", record)["usage"], "turn")
        self.assertEqual(phase("evaluation", record)["usage"], "missing")
        skipped = phase("setup", None)
        self.assertEqual(skipped["status"], "skipped")
        self.assertIsNone(skipped["duration_seconds"])
        self.assertIsNone(skipped["usage"])


if __name__ == "__main__":
    unittest.main()
