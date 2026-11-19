from pathlib import Path
import json
values = json.loads(Path("data/values.json").read_text())
Path("results").mkdir(exist_ok=True)
Path("results/total.json").write_text(json.dumps({"total": sum(values)}, sort_keys=True) + "\n")
