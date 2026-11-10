import tempfile
import unittest
from pathlib import Path

from benchmark import inspect_isolation


def make_task(root):
    task = root / "tasks" / "demo-task"
    evaluation = task / "evaluation"
    evaluation.mkdir(parents=True)
    (evaluation / "reference.md").write_text("# Эталон\n", encoding="utf-8")
    (evaluation / "check.py").write_text("print('ok')\n", encoding="utf-8")
    return task


class IsolationTests(unittest.TestCase):
    def test_clean_workspace_exposes_no_references(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = make_task(root)
            work = root / "runs" / "r1" / "workspace"
            work.mkdir(parents=True)
            (work / "catalog.py").write_text("def search():\n    return []\n", encoding="utf-8")
            result = inspect_isolation(work, task, {"BENCH_WORKSPACE": str(work)}, "workspace-write")
            self.assertTrue(result["workspace_outside_task_package"])
            self.assertTrue(result["evaluation_outside_workspace"])
            self.assertEqual(result["references_in_workspace"], [])
            self.assertEqual(result["env_exposes_task_package"], [])
            self.assertEqual(result["harness_sandbox"], "workspace-write")

    def test_copied_reference_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = make_task(root)
            work = root / "runs" / "r1" / "workspace"
            work.mkdir(parents=True)
            (work / "answer.md").write_bytes((task / "evaluation" / "reference.md").read_bytes())
            result = inspect_isolation(work, task, {}, None)
            self.assertEqual(result["references_in_workspace"], ["answer.md"])

    def test_env_path_to_task_package_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = make_task(root)
            work = root / "runs" / "r1" / "workspace"
            work.mkdir(parents=True)
            result = inspect_isolation(work, task, {"BENCH_TASK_DIR": str(task), "BENCH_WORKSPACE": str(work)}, None)
            self.assertEqual(result["env_exposes_task_package"], ["BENCH_TASK_DIR"])

    def test_workspace_inside_task_package_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = make_task(root)
            work = task / "project"
            work.mkdir()
            result = inspect_isolation(work, task, {}, None)
            self.assertFalse(result["workspace_outside_task_package"])


if __name__ == "__main__":
    unittest.main()
