import pefile, struct
p = r"D:\CS 1.6 GoldClient\MetaHook_blob.exe"
data = open(p,"rb").read()
pe = pefile.PE(p, fast_load=True)
ib = pe.OPTIONAL_HEADER.ImageBase
def off2va(o): return ib + pe.get_rva_from_offset(o)

def xrefs(va):
    pat = struct.pack("<I", va)
    out=[]; st=0
    while True:
        j=data.find(pat,st)
        if j<0: break
        out.append(j); st=j+1
    return out

for name, va in [("gamedata", 0x45a963c), ("plugins.lst", 0x45a917d), ("MH_LoadEngine err", 0x45a9250)]:
    hits = xrefs(va)
    print(name, hex(va), "->", [hex(off2va(h)) for h in hits][:20], "count", len(hits))
