import pefile, struct
from capstone import *

p = r"D:\CS 1.6 GoldClient\MetaHook_blob.exe"
pe = pefile.PE(p, fast_load=True)
ib = pe.OPTIONAL_HEADER.ImageBase
print("imagebase", hex(ib))

def find_str(s):
    data = open(p,"rb").read()
    idx = data.find(s)
    if idx < 0: return None
    # map file offset to RVA
    rva = pe.get_rva_from_offset(idx)
    return ib + rva, idx

for s in [b"Could not get EngineAPI from engine", b"MH_LoadEngine: Failed to resolve", b"metahook\\configs\\plugins.lst"]:
    r = find_str(s)
    print(s, "->", (hex(r[0]), hex(r[1])) if r else None)
