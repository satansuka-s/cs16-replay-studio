import pefile, struct
from capstone import *
p = r"D:\CS 1.6 GoldClient\MetaHook_blob.exe"
data = open(p,"rb").read()
pe = pefile.PE(p, fast_load=True)
ib = pe.OPTIONAL_HEADER.ImageBase
def off2va(o): return ib + pe.get_rva_from_offset(o)
def va2off(v): return pe.get_offset_from_rva(v - ib)

for s in [b"metahook\\gamedata", b"\\metahook\\gamedata", b"metahook\\configs\\plugins.lst"]:
    i = data.find(s)
    print(s, hex(i) if i>=0 else None, hex(off2va(i)) if i>=0 else None)

# xrefs to the gamedata literal (push imm32)
i = data.find(b"metahook\\gamedata")
if i >= 0:
    va = off2va(i)
    pat = struct.pack("<I", va)
    hits = []
    st = 0
    while True:
        j = data.find(pat, st)
        if j < 0: break
        hits.append(j); st = j+1
    print("xrefs:", [(hex(h), hex(off2va(h))) for h in hits])
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    for h in hits:
        # find function start: scan back for 55 8b ec or 55 89 e5
        start = h
        while start > 0 and not (data[start] == 0x55 and data[start+1] in (0x8b, 0x89) and data[start+2] in (0xec, 0xe5)):
            start -= 1
        print("  func start candidate:", hex(off2va(start)))
