import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class HarnessTests(unittest.TestCase):
    def test_qwen_adapter_forwards_configuration_without_model(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            fake = tmp / "fake.py"
            fake.write_text("import json, pathlib, sys\npathlib.Path('captured.json').write_text(json.dumps(sys.argv[1:]))\n", encoding="utf-8")
            config = tmp / "config.json"
            config.write_text(json.dumps({"executable":sys.executable,"args":[str(fake),"--output-format","stream-json"],"prompt":"test prompt"}),encoding="utf-8")
            env = os.environ.copy()
            env.update(BENCH_HARNESS_CONFIG=str(config), BENCH_WORKSPACE=str(tmp))
            p = subprocess.run([sys.executable,str(ROOT / "harnesses/qwen-code/agent.py")],cwd=tmp,env=env,capture_output=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual(json.loads((tmp / "captured.json").read_text()),["--output-format","stream-json","-p","test prompt"])

    def test_codex_telemetry_adapter_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory)/"stdout"
            raw.write_text('{"type":"turn.completed","usage":{"input_tokens":12}}\n',encoding="utf-8")
            env = os.environ.copy()
            env["BENCH_AGENT_STDOUT"] = str(raw)
            p=subprocess.run([sys.executable,str(ROOT/"harnesses/codex/telemetry_adapter.py")],env=env,capture_output=True,check=True)
            self.assertEqual(json.loads(p.stdout)["turns"][0]["usage"]["input_tokens"]["value"],12)

if __name__ == "__main__": unittest.main()
