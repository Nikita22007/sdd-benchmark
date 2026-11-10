import unittest
from telemetry import codex_events, unavailable

class TelemetryTests(unittest.TestCase):
    def test_usage_is_turn_level_and_missing_is_not_zero(self):
        data = b'{"type":"turn.started"}\n{"type":"turn.completed","usage":{"input_tokens":100,"cached_input_tokens":60,"output_tokens":7}}\n'
        result = codex_events(data)
        self.assertEqual(result["scope"], "turn")
        self.assertEqual(result["request_usage"], "missing")
        usage = result["turns"][0]["usage"]
        self.assertEqual(usage["input_tokens"], {"value":100,"provenance":"reported"})
        self.assertEqual(usage["cached_input_tokens"]["value"],60)
        self.assertEqual(usage["reasoning_output_tokens"], {"value":None,"provenance":"missing"})

    def test_malformed_and_missing(self):
        result = codex_events(b'{bad}\n{"type":"turn.completed"}\n')
        self.assertEqual(result["invalid_lines"], [1])
        self.assertIsNone(result["turns"][0]["usage"]["output_tokens"]["value"])
        self.assertEqual(unavailable()["request_usage"], "missing")

if __name__ == "__main__":
    unittest.main()
