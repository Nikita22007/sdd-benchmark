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
            self.assertEqual(json.loads((tmp / "captured.json").read_text()),["--output-format","stream-json","test prompt"])

    def test_qwen_adapter_builds_approval_arguments(self):
        import importlib.util

        path = ROOT / "harnesses/qwen-code/agent.py"
        spec = importlib.util.spec_from_file_location("qwen_agent", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(
            module.build_args({"approval_mode": "auto"}),
            ["--output-format", "stream-json", "--approval-mode", "auto"],
        )
        self.assertEqual(module.build_args({"approval_mode": "none"}), ["--output-format", "stream-json"])
        self.assertEqual(module.build_args({"args": ["--custom"]}), ["--custom"])

    def test_qwen_telemetry_adapter_reads_result_stats(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / "stdout"
            raw.write_text(
                "\n".join(
                    [
                        '{"type":"init","sessionId":"s"}',
                        '{"type":"message","role":"assistant","content":"готово"}',
                        '{"type":"result","stats":{"inputTokens":120,"outputTokens":8,"cachedTokens":30,"totalTokens":158}}',
                        "{bad}",
                    ]
                ),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["BENCH_AGENT_STDOUT"] = str(raw)
            process = subprocess.run(
                [sys.executable, str(ROOT / "harnesses/qwen-code/telemetry_adapter.py")],
                env=env,
                capture_output=True,
                check=True,
            )
            data = json.loads(process.stdout)
            self.assertEqual(data["source"], "qwen_stream_json")
            self.assertEqual(data["scope"], "run")
            self.assertEqual(data["request_usage"], "reported")
            self.assertEqual(data["invalid_lines"], [4])
            usage = data["requests"][0]["usage"]
            self.assertEqual(usage["input_tokens"]["value"], 120)
            self.assertEqual(usage["cached_input_tokens"]["value"], 30)
            self.assertEqual(usage["output_tokens"]["value"], 8)
            self.assertEqual(usage["reasoning_output_tokens"]["provenance"], "missing")

    def test_codex_adapter_passes_runner_context_without_model(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            fake = tmp / "fake.py"
            fake.write_text("import json, pathlib, sys\npathlib.Path('captured.json').write_text(json.dumps(sys.argv[1:]))\n", encoding="utf-8")
            config = tmp / "config.json"
            config.write_text(json.dumps({"executable":sys.executable,"args":[str(fake),"--json"],"prompt":"test prompt"}),encoding="utf-8")
            env = os.environ.copy()
            env.update(BENCH_HARNESS_CONFIG=str(config), BENCH_WORKSPACE=str(tmp), BENCH_TASK=str(tmp / "TASK.md"), BENCH_APPROACH=str(tmp / "APPROACH.md"), BENCH_CONTEXT=str(tmp / "sdd-context"))
            p = subprocess.run([sys.executable,str(ROOT / "harnesses/codex/agent.py")],cwd=tmp,env=env,capture_output=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual(json.loads((tmp / "captured.json").read_text()),["--json","-C",str(tmp),"test prompt"])

    def test_codex_adapter_default_prompt_names_task_context_and_approach(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            fake = tmp / "fake.py"
            fake.write_text("import json, pathlib, sys\npathlib.Path('captured.json').write_text(json.dumps(sys.argv[1:]))\n", encoding="utf-8")
            config = tmp / "config.json"
            config.write_text(json.dumps({"executable":sys.executable,"args":[str(fake)]}),encoding="utf-8")
            env = os.environ.copy()
            env.update(BENCH_HARNESS_CONFIG=str(config), BENCH_WORKSPACE=str(tmp), BENCH_TASK=str(tmp / "TASK.md"), BENCH_APPROACH=str(tmp / "APPROACH.md"), BENCH_CONTEXT=str(tmp / "sdd-context"))
            p = subprocess.run([sys.executable,str(ROOT / "harnesses/codex/agent.py")],cwd=tmp,env=env,capture_output=True)
            self.assertEqual(p.returncode,0,p.stderr)
            prompt = json.loads((tmp / "captured.json").read_text())[-1]
            for expected in (str(tmp / "TASK.md"), str(tmp / "APPROACH.md"), str(tmp / "sdd-context")):
                self.assertIn(expected, prompt)

    def test_deepseek_telemetry_adapter_normalizes_dsh_events(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / "stdout"
            raw.write_text(
                "\n".join(
                    [
                        '{"type":"session","sessionId":"s1"}',
                        '{"type":"status","phase":"turn_start","turn":1}',
                        '{"type":"status","phase":"step_end","turn":1,"step":1,"usage":{"inputTokens":100,"outputTokens":5,"cacheReadTokens":40,"cacheWriteTokens":0,"totalTokens":145}}',
                        '{"type":"status","phase":"step_end","turn":1,"step":2,"usage":{"inputTokens":50,"outputTokens":7,"cacheReadTokens":20}}',
                        '{"type":"status","phase":"turn_end","turn":1,"reason":{"kind":"ok"}}',
                        "{bad}",
                    ]
                ),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["BENCH_AGENT_STDOUT"] = str(raw)
            process = subprocess.run(
                [sys.executable, str(ROOT / "harnesses/deepseek/telemetry_adapter.py")],
                env=env,
                capture_output=True,
                check=True,
            )
            data = json.loads(process.stdout)
            self.assertEqual(data["source"], "dsh_jsonl")
            self.assertEqual(data["usage_granularity"], "step")
            self.assertEqual(data["request_usage"], "reported")
            self.assertEqual(data["invalid_lines"], [6])
            self.assertEqual(data["turns"][0]["state"], "completed")
            self.assertEqual(len(data["requests"]), 2)
            first = data["requests"][0]["usage"]
            self.assertEqual(first["input_tokens"]["value"], 140)
            self.assertEqual(first["cached_input_tokens"]["value"], 40)
            self.assertEqual(first["output_tokens"]["value"], 5)
            self.assertEqual(first["reasoning_output_tokens"]["provenance"], "missing")
            second = data["requests"][1]["usage"]
            self.assertEqual(second["input_tokens"]["value"], 70)

    def test_deepseek_adapter_forwards_patch_and_prompt_without_model(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            fake = tmp / "fake.py"
            fake.write_text(
                "import json, pathlib, sys\npathlib.Path('captured.json').write_text(json.dumps(sys.argv[1:]))\n",
                encoding="utf-8",
            )
            config = tmp / "config.json"
            config.write_text(
                json.dumps({"executable": sys.executable, "args": [str(fake), "headless", "--json"], "patch": str(tmp / "p.yml"), "prompt": "test prompt"}),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env.update(BENCH_HARNESS_CONFIG=str(config), BENCH_WORKSPACE=str(tmp))
            process = subprocess.run(
                [sys.executable, str(ROOT / "harnesses/deepseek/agent.py")],
                cwd=tmp,
                env=env,
                capture_output=True,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            captured = json.loads((tmp / "captured.json").read_text(encoding="utf-8"))
            self.assertEqual(captured[-3:], ["--patch", str(tmp / "p.yml"), "test prompt"])

    def test_deepseek_adapter_supplies_api_key_from_file(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            fake = tmp / "fake.py"
            fake.write_text(
                "import os, pathlib\npathlib.Path('key.txt').write_text(os.environ.get('DEEPSEEK_API_KEY', ''))\n",
                encoding="utf-8",
            )
            secret = tmp / "secret.txt"
            secret.write_text("sk-test\n", encoding="utf-8")
            config = tmp / "config.json"
            config.write_text(
                json.dumps({"executable": sys.executable, "args": [str(fake)], "api_key_file": str(secret), "prompt": "p"}),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env.update(BENCH_HARNESS_CONFIG=str(config), BENCH_WORKSPACE=str(tmp))
            process = subprocess.run(
                [sys.executable, str(ROOT / "harnesses/deepseek/agent.py")], cwd=tmp, env=env, capture_output=True
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual((tmp / "key.txt").read_text(encoding="utf-8"), "sk-test")

    def test_gold_harness_applies_reference_solution(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            task = tmp / "task"
            (task / "project").mkdir(parents=True)
            (task / "evaluation").mkdir()
            (task / "project" / "mod.py").write_text("def f():\n    return 0\n", encoding="utf-8")
            (task / "evaluation" / "reference.md").write_text(
                "# Эталон\n\n```python\ndef f():\n    return 1\n```\n", encoding="utf-8"
            )
            workspace = tmp / "work"
            workspace.mkdir()
            env = os.environ.copy()
            env["BENCH_WORKSPACE"] = str(workspace)
            process = subprocess.run(
                [sys.executable, str(ROOT / "harnesses/gold/apply.py"), str(task)],
                env=env,
                capture_output=True,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn("return 1", (workspace / "mod.py").read_text(encoding="utf-8"))

    def test_codex_telemetry_adapter_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory)/"stdout"
            raw.write_text('{"type":"turn.completed","usage":{"input_tokens":12}}\n',encoding="utf-8")
            env = os.environ.copy()
            env["BENCH_AGENT_STDOUT"] = str(raw)
            p=subprocess.run([sys.executable,str(ROOT/"harnesses/codex/telemetry_adapter.py")],env=env,capture_output=True,check=True)
            self.assertEqual(json.loads(p.stdout)["requests"][0]["usage"]["input_tokens"]["value"],12)

if __name__ == "__main__": unittest.main()
