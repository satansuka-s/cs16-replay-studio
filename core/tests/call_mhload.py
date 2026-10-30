import pefile, struct
from capstone import *
p = r"D:\CS 1.6 GoldClient\MetaHook_blob.exe"
data = open(p,"rb").read()
pe = pefile.PE(p, fast_load=True)
ib = pe.OPTIONAL_HEADER.ImageBase
def off2va(o): return ib + pe.get_rva_from_offset(o)
def va2off(v): return pe.get_offset_from_rva(v - ib)

target = 0x141c070
hits = []
for i in range(len(data)-5):
    if data[i] == 0xE8:
        rel = struct.unpack_from("<i", data, i+1)[0]
        src = off2va(i)
        if src + 5 + rel == target:
            hits.append(src)
print("call sites to MH_LoadEngine:", [hex(h) for h in hits])

md = Cs(CS_ARCH_X86, CS_MODE_32)
for h in hits:
    s = h - 120
    print("=== around %08x ===" % h)
    for ins in md.disasm(data[va2off(s):va2off(h)+5], s):
        mark = "   <== CALL" if ins.address == h else ""
        print("  %08x: %-22s %s %s%s" % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str, mark))
