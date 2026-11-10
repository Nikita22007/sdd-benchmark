import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from telemetry import codex_events
print(json.dumps(codex_events(Path(os.environ["BENCH_AGENT_STDOUT"]).read_bytes())))
