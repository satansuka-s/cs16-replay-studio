import pefile, struct
p = r"D:\CS 1.6 GoldClient\MetaHook_blob.exe"
data = open(p,"rb").read()
pe = pefile.PE(p, fast_load=True)
ib = pe.OPTIONAL_HEADER.ImageBase
def off2va(o): return ib + pe.get_rva_from_offset(o)
def va2off(v): return pe.get_offset_from_rva(v - ib)

# literal for plugins.lst with leading backslash
for s in [b"\\metahook\\configs\\plugins.lst", b"\\metahook\\plugins\\", b"\\metahook\\dlls"]:
    i = data.find(s)
    print(s, hex(off2va(i)) if i>=0 else None)
    if i>=0:
        va = off2va(i); pat = struct.pack("<I", va); hits=[]; st=0
        while True:
            j=data.find(pat,st)
            if j<0: break
            hits.append(j); st=j+1
        print("   xrefs:", [hex(off2va(h)) for h in hits][:10])

def func_start(va):
    o = va2off(va)
    for k in range(o, max(0,o-20000), -1):
        if data[k] == 0x55 and data[k+1] in (0x8b,0x89) and data[k+2] in (0xec,0xe5):
            return off2va(k)
    return None

for va in [0x141c66d]:
    print("func start for", hex(va), "->", hex(func_start(va)) if func_start(va) else None)
