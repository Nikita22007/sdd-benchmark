import tempfile
import unittest
from pathlib import Path

from vendor.harness2 import runmark


class FingerprintTests(unittest.TestCase):
    def test_fingerprint_is_stable_and_detects_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "instructions.md").write_text("# Подход\n", encoding="utf-8")
            first = runmark.fingerprint(root)
            self.assertEqual(first, runmark.fingerprint(root))
            (root / "instructions.md").write_text("# Подход\nизменено\n", encoding="utf-8")
            self.assertNotEqual(first, runmark.fingerprint(root))

    def test_fingerprint_ignores_byproducts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "agent.py").write_text("print('ok')\n", encoding="utf-8")
            stable = runmark.fingerprint(root)
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "agent.cpython-314.pyc").write_bytes(b"\x00")
            self.assertEqual(stable, runmark.fingerprint(root))

    def test_missing_directory_is_not_a_crash(self):
        self.assertEqual(runmark.fingerprint(None), "base")
        self.assertEqual(runmark.fingerprint(Path("no-such-dir")), "absent")


class InputsFingerprintTests(unittest.TestCase):
    def test_inputs_change_with_prompt_and_source_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "catalog.py").write_text("", encoding="utf-8")
            prompt = "Добавьте search"
            first = runmark.inputs_fingerprint(prompt, root)
            self.assertEqual(first, runmark.inputs_fingerprint(prompt, root))
            self.assertNotEqual(first, runmark.inputs_fingerprint(prompt + " и тесты", root))
            (root / "catalog.py").write_text("def search():\n    return []\n", encoding="utf-8")
            self.assertNotEqual(first, runmark.inputs_fingerprint(prompt, root))

    def test_inputs_without_files_are_still_stable(self):
        value = runmark.inputs_fingerprint("prompt", None)
        self.assertEqual(value, runmark.inputs_fingerprint("prompt", None))


if __name__ == "__main__":
    unittest.main()
