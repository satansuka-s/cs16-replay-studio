import json, re, struct, sys

GD = r"D:\CS 1.6 GoldClient\cstrike\metahook\gamedata\hl-9999.json"
BIN = r"D:\CS 1.6 GoldClient\hw.dll"

doc = json.load(open(GD, encoding="utf-8"))
data = open(BIN, "rb").read()

def sig_to_regex(sig):
    parts = sig.split()
    out = bytearray()
    for p in parts:
        if p == "??":
            out += b"."
        else:
            out += re.escape(bytes([int(p, 16)]))
    return re.compile(bytes(out), re.DOTALL)

print("module size: 0x%x" % len(data))
for rec in doc["records"]:
    p = rec["payload"]
    sig = p.get("func_sig") or p.get("gv_sig")
    rx = sig_to_regex(sig)
    hits = [m.start() for m in rx.finditer(data)]
    name = rec["symbolName"]
    kind = rec["kind"]
    if kind == "function":
        print("%-18s func  sig_len=%2d hits=%d  ref_rva=%s" % (name, len(sig.split()), len(hits), p.get("func_rva")))
    else:
        print("%-18s glob  sig_len=%2d hits=%d  ref_rva=%s inst_off=%s disp=%s len=%s" % (
            name, len(sig.split()), len(hits), p.get("gv_rva"), p.get("gv_inst_offset"), p.get("gv_inst_disp"), p.get("gv_inst_length")))
