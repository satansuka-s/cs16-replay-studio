import json, re, sys
from pathlib import Path

def sig_to_regex(sig):
    out = bytearray()
    for p in sig.split():
        out += b"." if p == "??" else re.escape(bytes([int(p, 16)]))
    return re.compile(bytes(out), re.DOTALL)

def scan(bin_path, gd_path):
    data = Path(bin_path).read_bytes()
    doc = json.loads(Path(gd_path).read_text(encoding="utf-8"))
    hits = 0
    total = 0
    misses = []
    for rec in doc["records"]:
        p = rec["payload"]
        sig = p.get("func_sig") or p.get("gv_sig")
        if not sig:
            continue
        total += 1
        n = len(sig_to_regex(sig).findall(data))
        if n:
            hits += 1
        else:
            misses.append(rec["symbolName"])
    return hits, total, misses

for game, gd in [
    (r"D:\Counter-Strike Build 4554", r"D:\Counter-Strike Build 4554\cstrike\metahook\gamedata\hl-4554.json"),
    (r"D:\CS 1.6 GoldClient", r"D:\CS 1.6 GoldClient\cstrike\metahook\gamedata\hl-10210.json"),
]:
    h, t, m = scan(Path(game) / "hw.dll", gd)
    print(f"{game}: {h}/{t} signatures found; misses={m[:6]}")
