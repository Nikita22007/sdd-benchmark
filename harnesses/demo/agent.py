import os
from pathlib import Path
workspace = Path(os.environ["BENCH_WORKSPACE"])
(workspace / "catalog.py").write_text("def search(items, query):\n    return [item for item in items if query.casefold() in item.casefold()]\n", encoding="utf-8")
