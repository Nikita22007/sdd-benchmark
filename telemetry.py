"""Normalize available harness events without inventing per-request usage."""
import json

TOKEN_FIELDS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens", "reasoning_output_tokens")


def missing_usage():
    return {field: {"value": None, "provenance": "missing"} for field in TOKEN_FIELDS}


def reported_usage(usage):
    """Keep every field, marking which values the harness actually reported."""
    return {
        field: {"value": usage.get(field), "provenance": "reported" if usage.get(field) is not None else "missing"}
        for field in TOKEN_FIELDS
    }


def parse(raw):
    events, invalid = [], []
    for number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            invalid.append(number)
            continue
        if isinstance(event, dict):
            events.append(event)
        else:
            invalid.append(number)
    return events, invalid


def codex_events(raw):
    """One request entry per turn; usage stays at the granularity Codex reports."""
    events, invalid = parse(raw)
    requests = []
    for event in events:
        kind = event.get("type")
        if kind == "turn.started":
            requests.append({"index": len(requests) + 1, "state": "started", "usage": missing_usage()})
        elif kind == "turn.completed":
            usage = event.get("usage")
            usage = usage if isinstance(usage, dict) else {}
            if requests and requests[-1]["state"] == "started":
                requests[-1]["state"] = "completed"
                requests[-1]["usage"] = reported_usage(usage)
            else:
                requests.append({"index": len(requests) + 1, "state": "completed", "usage": reported_usage(usage)})
    return {
        "source": "codex_jsonl",
        "scope": "turn",
        "usage_granularity": "turn",
        "request_usage": "missing",
        "sources": {"events": "codex exec --json stdout", "usage": "turn.completed.usage", "request_usage": None},
        "events": len(events),
        "invalid_lines": invalid,
        "requests": requests,
    }


def unavailable(note):
    return {
        "source": None,
        "scope": None,
        "usage_granularity": None,
        "request_usage": "missing",
        "sources": {},
        "events": None,
        "invalid_lines": [],
        "requests": [],
        "note": note,
    }
