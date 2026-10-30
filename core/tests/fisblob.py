import pefile, struct
from capstone import *
p = r"D:\CS 1.6 GoldClient\MetaHook_blob.exe"
data = open(p,"rb").read()
pe = pefile.PE(p, fast_load=True)
ib = pe.OPTIONAL_HEADER.ImageBase
def off2va(o): return ib + pe.get_rva_from_offset(o)
def va2off(v): return pe.get_offset_from_rva(v - ib)
def va2str(v):
    try: o = va2off(v)
    except: return None
    e = data.find(b"\x00", o, o+200)
    if e < 0: return None
    s = data[o:e]
    try: t = s.decode("ascii")
    except: return None
    return t if len(t)>=3 and all(32<=ord(c)<127 for c in t) else None

pat = struct.pack("<I", 0x12345678)
hits = []
st = 0
while True:
    i = data.find(pat, st)
    if i < 0: break
    hits.append(i); st = i+1
print("0x12345678 hits:", [hex(off2va(h)) for h in hits])

md = Cs(CS_ARCH_X86, CS_MODE_32)
for h in hits:
    va = off2va(h)
    s = va - 120
    print("=== around %08x ===" % va)
    for ins in md.disasm(data[va2off(s):va2off(va)+60], s):
        mark = "  <== imm" if ins.address <= va < ins.address + ins.size else ""
        print("  %08x: %-22s %s %s%s" % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str, mark))
