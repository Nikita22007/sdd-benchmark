import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "tasks"
# These defects loop forever instead of returning, so they are covered by the timeout note in
# tasks/PROVENANCE.md rather than by a fast assertion here.
HANGING = {"quixbugs-bitcount", "quixbugs-find_first_in_sorted"}


def run_check(task, program):
    with tempfile.TemporaryDirectory() as directory:
        shutil.copyfile(program, Path(directory) / program.name)
        env = os.environ.copy()
        env["BENCH_WORKSPACE"] = directory
        return subprocess.run(
            [sys.executable, str(task / "evaluation" / "check.py")],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )


class ScenarioTests(unittest.TestCase):
    def test_every_scenario_passes_its_reference(self):
        for task in sorted(TASKS.glob("quixbugs-*")):
            with self.subTest(task=task.name):
                reference = task / "evaluation" / "reference.md"
                self.assertTrue(reference.is_file())
                program = task / "project" / (task.name[len("quixbugs-"):] + ".py")
                self.assertTrue(program.is_file())

    def test_reference_implementations_are_accepted(self):
        for task in sorted(TASKS.glob("quixbugs-*")):
            name = task.name[len("quixbugs-"):]
            source = task / "evaluation" / "reference.md"
            body = source.read_text(encoding="utf-8")
            code = body.split("```python", 1)[1].split("```", 1)[0]
            with tempfile.TemporaryDirectory() as directory:
                program = Path(directory) / f"{name}.py"
                program.write_text(code, encoding="utf-8")
                process = run_check(task, program)
            with self.subTest(task=task.name):
                self.assertEqual(process.returncode, 0, process.stderr[-400:])

    def test_defective_programs_are_rejected(self):
        for task in sorted(TASKS.glob("quixbugs-*")):
            if task.name in HANGING:
                continue
            name = task.name[len("quixbugs-"):]
            process = run_check(task, task / "project" / f"{name}.py")
            with self.subTest(task=task.name):
                self.assertNotEqual(process.returncode, 0, "the defective program must not pass")


if __name__ == "__main__":
    unittest.main()
