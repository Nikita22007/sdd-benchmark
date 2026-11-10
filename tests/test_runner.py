import tempfile
import unittest
from pathlib import Path

from bench import report
from bench.agents import build
from bench.runner import load_scenario, run

ROOT = Path(__file__).resolve().parents[1]


class ScenarioTests(unittest.TestCase):
    def test_scenarios_have_required_fields(self):
        for path in sorted((ROOT / "scenarios").glob("*.toml")):
            scenario = load_scenario(path)
            with self.subTest(scenario=scenario["name"]):
                self.assertIn("goal", scenario)
                self.assertIn("check", scenario)

    def test_unknown_scenario_field_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.toml"
            path.write_text('name = "x"\ngoal = "y"\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_scenario(path)


class AgentTests(unittest.TestCase):
    def test_frugal_passes_and_sloppy_fails(self):
        scenario = {"name": "demo", "goal": "def f():\n    return 1\n", "check": "return 1"}
        with tempfile.TemporaryDirectory() as directory:
            frugal = run(self._write(Path(directory), scenario), "frugal", Path(directory) / "results")
            sloppy = run(self._write(Path(directory), scenario), "sloppy", Path(directory) / "results")
        self.assertTrue(frugal["passed"])
        self.assertFalse(sloppy["passed"])

    def test_unknown_agent_is_reported(self):
        with self.assertRaises(KeyError):
            build("nonexistent")

    def _write(self, directory, scenario):
        path = directory / "scenario.toml"
        path.write_text(
            f'name = "{scenario["name"]}"\ngoal = """{scenario["goal"]}"""\ncheck = "{scenario["check"]}"\n',
            encoding="utf-8",
        )
        return path


class ReportTests(unittest.TestCase):
    def test_summary_counts_and_render(self):
        records = [
            {"agent": "frugal", "passed": True, "output_chars": 10, "duration_seconds": 0.1},
            {"agent": "frugal", "passed": True, "output_chars": 20, "duration_seconds": 0.3},
            {"agent": "sloppy", "passed": False, "output_chars": 5, "duration_seconds": 0.1},
        ]
        summary = report.summarise(records)
        self.assertEqual(summary["frugal"]["runs"], 2)
        self.assertEqual(summary["frugal"]["pass_rate"], 1.0)
        self.assertEqual(summary["sloppy"]["pass_rate"], 0.0)
        self.assertIn("| frugal |", report.render(summary))

    def test_missing_results_directory_is_empty(self):
        self.assertEqual(report.load(ROOT / "results" / "does-not-exist"), [])


if __name__ == "__main__":
    unittest.main()
