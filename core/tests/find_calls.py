import pefile, struct
p = r"D:\CS 1.6 GoldClient\MetaHook_blob.exe"
data = open(p,"rb").read()
pe = pefile.PE(p, fast_load=True)
ib = pe.OPTIONAL_HEADER.ImageBase
def off2va(o): return ib + pe.get_rva_from_offset(o)
def va2off(v): return pe.get_offset_from_rva(v - ib)

def find_calls(target):
    out = []
    for i in range(len(data)-5):
        if data[i] == 0xE8:
            rel = struct.unpack_from("<i", data, i+1)[0]
            src = off2va(i)
            if src + 5 + rel == target:
                out.append(src)
    return out

for name, target in [("MH_LoadDllPaths", 0x1418f50), ("MH_LoadPlugins", 0x1419670), ("MH_SysError", 0x1418130)]:
    hits = find_calls(target)
    print(name, hex(target), "call sites:", [hex(h) for h in hits][:20], "count", len(hits))
