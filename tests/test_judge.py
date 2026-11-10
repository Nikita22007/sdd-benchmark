import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from benchmark import judge_result

ROOT = Path(__file__).resolve().parents[1]


class JudgeContractTests(unittest.TestCase):
    def test_valid_score_and_verdict_are_accepted(self):
        data = judge_result('{"score":0.75,"verdict":"почти","criteria":[{"name":"x","met":true}]}')
        self.assertEqual(data["score"], 0.75)

    def test_out_of_range_score_is_rejected(self):
        with self.assertRaises(ValueError):
            judge_result('{"score":1.5,"verdict":"ok"}')
        with self.assertRaises(ValueError):
            judge_result('{"score":true,"verdict":"ok"}')

    def test_missing_verdict_is_rejected(self):
        with self.assertRaises(ValueError):
            judge_result('{"score":0.5}')
        with self.assertRaises(ValueError):
            judge_result('not json')


class StubJudgeTests(unittest.TestCase):
    def test_stub_judge_prints_valid_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            env = os.environ.copy()
            env.update(
                BENCH_WORKSPACE=str(workspace),
                BENCH_TASK=str(workspace / "TASK.md"),
                BENCH_JUDGE_INSTRUCTIONS=str(workspace / "instructions.md"),
                BENCH_JUDGE_REFERENCE=str(workspace / "reference.md"),
            )
            process = subprocess.run(
                [sys.executable, str(ROOT / "judges/stub/judge.py")],
                env=env,
                capture_output=True,
                check=True,
            )
            data = judge_result(process.stdout.decode("utf-8"))
            self.assertEqual(data["score"], 1.0)
            self.assertIn("stub", data["verdict"])


    def test_codex_judge_adapter_parses_model_json_without_model(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            fake = tmp / "fake.py"
            reply = json.dumps({"score": 0.5, "verdict": "наполовину"}, ensure_ascii=False)
            event = json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": reply}}, ensure_ascii=False)
            fake.write_text(
                "import pathlib, sys\n"
                "pathlib.Path('captured.json').write_text(__import__('json').dumps(sys.argv[1:], ensure_ascii=False), encoding='utf-8')\n"
                "print(" + repr(event) + ")\n",
                encoding="utf-8",
            )
            config = tmp / "judge-config.json"
            config.write_text(json.dumps({"executable": sys.executable, "args": [str(fake)], "prompt": "test prompt"}), encoding="utf-8")
            env = os.environ.copy()
            env.update(BENCH_WORKSPACE=str(tmp), BENCH_JUDGE_CONFIG=str(config))
            process = subprocess.run(
                [sys.executable, str(ROOT / "judges/codex/judge.py")],
                cwd=tmp,
                env=env,
                capture_output=True,
            )
            self.assertEqual(process.returncode, 0, process.stderr.decode("utf-8", "replace"))
            self.assertEqual(judge_result(process.stdout.decode("utf-8"))["score"], 0.5)
            self.assertEqual(json.loads((tmp / "captured.json").read_text(encoding="utf-8")), ["-C", str(tmp), "test prompt"])


if __name__ == "__main__":
    unittest.main()
