import tempfile
import unittest
from pathlib import Path

from benchmark import executor_env, grader_markers, install


class EnvScrubTests(unittest.TestCase):
    def test_secrets_are_dropped_unless_the_harness_keeps_them(self):
        base = {"PATH": "x", "OPENAI_API_KEY": "sk-1", "DEEPSEEK_API_KEY": "sk-2", "HOME": "h"}
        env, dropped = executor_env(base, {})
        self.assertEqual(env, {"PATH": "x", "HOME": "h"})
        self.assertEqual(dropped, ["DEEPSEEK_API_KEY", "OPENAI_API_KEY"])

    def test_declared_key_is_kept(self):
        env, dropped = executor_env({"DEEPSEEK_API_KEY": "sk-2"}, {"env_keep": ["DEEPSEEK_API_KEY"]})
        self.assertEqual(env["DEEPSEEK_API_KEY"], "sk-2")
        self.assertEqual(dropped, [])


class InstallTests(unittest.TestCase):
    def test_inherit_keeps_the_ambient_home(self):
        with tempfile.TemporaryDirectory() as directory:
            home, variables, record = install(Path(directory) / "home", {})
            self.assertIsNone(home)
            self.assertEqual(variables, {})
            self.assertEqual(record["mode"], "inherit")
            self.assertIsNone(record["fingerprint"])

    def test_home_mode_materialises_declared_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = {
                "install": {
                    "mode": "home",
                    "files": {"config/settings.json": '{"a": 1}', "README.md": "x"},
                    "env": ["DSH_HOME"],
                }
            }
            home, variables, record = install(root / "home", spec)
            self.assertTrue((home / "config" / "settings.json").is_file())
            self.assertEqual(variables["DSH_HOME"], str(home))
            self.assertEqual(variables["HOME"], str(home))
            self.assertEqual(record["mode"], "home")
            self.assertEqual(record["files"], ["README.md", "config/settings.json"])
            self.assertTrue(record["fingerprint"])

    def test_unknown_mode_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                install(Path(directory), {"install": {"mode": "nonsense"}})


class GraderMarkerTests(unittest.TestCase):
    def test_markers_in_the_working_copy_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "notes.md").write_text("просто заметки", encoding="utf-8")
            (root / "leak.json").write_text('{"pass_rate": 1.0}', encoding="utf-8")
            self.assertEqual(grader_markers(root), ["leak.json:pass_rate"])

    def test_clean_working_copy_has_no_markers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "catalog.py").write_text("def search():\n    return []\n", encoding="utf-8")
            self.assertEqual(grader_markers(root), [])


if __name__ == "__main__":
    unittest.main()
