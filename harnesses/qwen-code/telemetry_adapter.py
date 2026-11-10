"""Normalize Qwen Code `stream-json` output without inventing usage.

The CLI emits newline-delimited JSON: init, message and tool events, and a final `result`.
Usage may appear as `stats` on that result or as `usage` objects on individual events. When a
result event carries usage, it wins: it is already the run total, and summing it together with
per-event usage would double count.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from telemetry import missing_usage, reported_usage

TOKEN_FIELDS = {
    "input_tokens": ("inputTokens", "input_tokens", "prompt_tokens"),
    "output_tokens": ("outputTokens", "output_tokens", "completion_tokens"),
    "cached_input_tokens": ("cachedTokens", "cached_input_tokens", "cache_read_input_tokens"),
    "cache_write_input_tokens": ("cacheWriteTokens", "cache_creation_input_tokens"),
    "reasoning_output_tokens": ("thoughtsTokens", "reasoning_output_tokens", "reasoning_tokens"),
}


def normalize(usage):
    mapped = {}
    for field, names in TOKEN_FIELDS.items():
        for name in names:
            if usage.get(name) is not None:
                mapped[field] = usage[name]
                break
    return mapped


def usage_in(node):
    """Any dict under `stats` or `usage` that carries at least one token field."""
    found = []
    if isinstance(node, dict):
        for key in ("stats", "usage"):
            candidate = node.get(key)
            if isinstance(candidate, dict) and normalize(candidate):
                found.append(candidate)
        if normalize(node):
            found.append(node)
    return found


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


def qwen_events(raw):
    events, invalid = parse(raw)
    from_result, from_events = [], []
    tool_events = 0
    for event in events:
        if event.get("type") == "tool_call" or event.get("type") == "tool_use":
            tool_events += 1
        found = usage_in(event)
        if not found:
            continue
        target = from_result if event.get("type") == "result" else from_events
        target.extend(found)

    chosen, scope = (from_result, "run") if from_result else (from_events, "event")
    requests = []
    for usage in chosen:
        requests.append(
            {"index": len(requests) + 1, "state": "completed", "usage": reported_usage(normalize(usage))}
        )
    reported = sum(1 for item in requests if any(field["value"] is not None for field in item["usage"].values()))
    if requests and reported == len(requests):
        request_usage = "reported"
    elif reported:
        request_usage = "partial"
    else:
        request_usage = "missing"

    return {
        "source": "qwen_stream_json",
        "scope": scope,
        "usage_granularity": scope,
        "request_usage": request_usage,
        "sources": {"events": "qwen --output-format stream-json stdout", "usage": "result.stats or event.usage"},
        "events": len(events),
        "invalid_lines": invalid,
        "tool_events": tool_events,
        "requests": requests,
    }


def main():
    raw = Path(os.environ["BENCH_AGENT_STDOUT"]).read_text(encoding="utf-8", errors="replace")
    sys.stdout.buffer.write(json.dumps(qwen_events(raw), ensure_ascii=False).encode("utf-8"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
