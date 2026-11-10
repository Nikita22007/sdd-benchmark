"""Normalize DeepSeek Harness run events, without inventing per-request usage.

The headless CLI reports usage per assistant step in `status` / `step_end`: `inputTokens` is the
uncached input, `cacheReadTokens` the cached part, and the two plus output make `totalTokens`.
Step usage is mapped onto the shared schema, where `input_tokens` is the whole input (cached
included, as the Codex adapter reports it) and `cached_input_tokens` is its cached share.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from telemetry import missing_usage, reported_usage


def normalize(usage):
    """Map the harness names onto the shared field names."""
    uncached = usage.get("inputTokens")
    cached = usage.get("cacheReadTokens")
    mapped = {}
    if uncached is not None or cached is not None:
        mapped["input_tokens"] = (uncached or 0) + (cached or 0)
    if cached is not None:
        mapped["cached_input_tokens"] = cached
    if usage.get("outputTokens") is not None:
        mapped["output_tokens"] = usage["outputTokens"]
    if usage.get("cacheWriteTokens") is not None:
        mapped["cache_write_input_tokens"] = usage["cacheWriteTokens"]
    if usage.get("reasoningTokens") is not None:
        mapped["reasoning_output_tokens"] = usage["reasoningTokens"]
    return mapped


def dsh_events(raw):
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

    steps, turns = [], []
    for event in events:
        kind, phase = event.get("type"), event.get("phase")
        if kind != "status":
            continue
        if phase == "turn_start":
            turns.append({"index": len(turns) + 1, "state": "started"})
        elif phase == "turn_end":
            reason = event.get("reason") or {}
            if turns:
                turns[-1]["state"] = "errored" if reason.get("kind") == "error" else "completed"
        elif phase == "step_end":
            usage = event.get("usage")
            if isinstance(usage, dict) and usage:
                steps.append(
                    {
                        "index": len(steps) + 1,
                        "turn": event.get("turn"),
                        "step": event.get("step"),
                        "state": "completed",
                        "usage": reported_usage(normalize(usage)),
                    }
                )

    reported = sum(1 for step in steps if any(field["value"] is not None for field in step["usage"].values()))
    if steps and reported == len(steps):
        request_usage = "reported"
    elif reported:
        request_usage = "partial"
    else:
        request_usage = "missing"

    return {
        "source": "dsh_jsonl",
        "scope": "step",
        "usage_granularity": "step",
        "request_usage": request_usage,
        "sources": {"events": "dsh headless --json stdout", "usage": "status.step_end.usage"},
        "events": len(events),
        "invalid_lines": invalid,
        "requests": steps,
        "turns": turns,
    }


def main():
    raw = Path(os.environ["BENCH_AGENT_STDOUT"]).read_text(encoding="utf-8", errors="replace")
    sys.stdout.buffer.write(json.dumps(dsh_events(raw), ensure_ascii=False).encode("utf-8"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
