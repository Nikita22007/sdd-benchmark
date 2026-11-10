import unittest
from telemetry import codex_events, unavailable


class TelemetryTests(unittest.TestCase):
    def test_usage_is_turn_level_and_missing_is_not_zero(self):
        data = b'{"type":"turn.started"}\n{"type":"turn.completed","usage":{"input_tokens":100,"cached_input_tokens":60,"output_tokens":7}}\n'
        result = codex_events(data)
        self.assertEqual(result["scope"], "turn")
        self.assertEqual(result["usage_granularity"], "turn")
        self.assertEqual(result["request_usage"], "missing")
        self.assertEqual(result["sources"]["usage"], "turn.completed.usage")
        request = result["requests"][0]
        self.assertEqual(request["state"], "completed")
        self.assertEqual(request["usage"]["input_tokens"], {"value":100,"provenance":"reported"})
        self.assertEqual(request["usage"]["cached_input_tokens"]["value"],60)
        self.assertEqual(request["usage"]["reasoning_output_tokens"], {"value":None,"provenance":"missing"})

    def test_unfinished_request_keeps_usage_missing(self):
        result = codex_events(b'{"type":"turn.started"}\n')
        self.assertEqual(len(result["requests"]), 1)
        self.assertEqual(result["requests"][0]["state"], "started")
        self.assertEqual(result["requests"][0]["usage"]["input_tokens"], {"value":None,"provenance":"missing"})

    def test_malformed_and_missing(self):
        result = codex_events(b'{bad}\n{"type":"turn.completed"}\n')
        self.assertEqual(result["invalid_lines"], [1])
        self.assertIsNone(result["requests"][0]["usage"]["output_tokens"]["value"])
        self.assertEqual(result["requests"][0]["usage"]["output_tokens"]["provenance"], "missing")
        missing = unavailable("harness has no telemetry adapter")
        self.assertEqual(missing["request_usage"], "missing")
        self.assertEqual(missing["requests"], [])
        self.assertEqual(missing["note"], "harness has no telemetry adapter")


if __name__ == "__main__":
    unittest.main()
