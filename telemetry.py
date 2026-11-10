"""Normalize available harness events without inventing per-request usage."""
import json

TOKEN_FIELDS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens", "reasoning_output_tokens")

def codex_events(raw):
    events = []
    errors = []
    for number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            errors.append(number)
            continue
        if isinstance(event, dict):
            events.append(event)
        else:
            errors.append(number)
    turns = []
    for event in events:
        if event.get("type") == "turn.completed":
            usage = event.get("usage")
            usage = usage if isinstance(usage, dict) else {}
            turns.append({"type": "turn.completed", "usage": {field: {"value": usage.get(field), "provenance": "reported" if field in usage and usage[field] is not None else "missing"} for field in TOKEN_FIELDS}})
    return {"source": "codex_jsonl", "scope": "turn", "request_usage": "missing", "events": len(events), "invalid_lines": errors, "turns": turns}

def unavailable():
    return {"source": None, "scope": None, "request_usage": "missing", "events": None, "invalid_lines": [], "turns": []}
