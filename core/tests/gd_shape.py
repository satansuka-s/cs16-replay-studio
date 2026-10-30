import json
from pathlib import Path
p = Path(r"D:\Counter-Strike Build 4554\cstrike\metahook\gamedata\hl-4554.json")
doc = json.loads(p.read_text(encoding="utf-8"))
print("top keys:", list(doc.keys()))
print(json.dumps({k: v for k, v in doc.items() if k != "records"}, indent=2)[:2500])
print("record sample:", json.dumps(doc["records"][0], indent=2)[:900])
