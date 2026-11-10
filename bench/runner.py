"""One run: load a scenario, ask an agent for output, record the outcome."""
import datetime as dt
import json
import time
import tomllib
import uuid
from pathlib import Path

from .agents import build


def load_scenario(path):
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    for field in ("name", "goal", "check"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise ValueError(f"{path}: field {field!r} must be a non-empty string")
    return data


def run(scenario_path, agent_name, results_dir="results"):
    scenario = load_scenario(scenario_path)
    agent = build(agent_name)
    started = time.monotonic()
    output = agent.solve(scenario)
    duration = round(time.monotonic() - started, 4)
    record = {
        "scenario": scenario["name"],
        "agent": agent.name,
        "passed": scenario["check"] in output,
        "output_chars": len(output),
        "duration_seconds": duration,
        "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    results = Path(results_dir)
    results.mkdir(parents=True, exist_ok=True)
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
    (results / f"{scenario['name']}-{agent.name}-{run_id}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return record
