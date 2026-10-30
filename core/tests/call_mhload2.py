import pefile
from capstone import *
p = r"D:\CS 1.6 GoldClient\MetaHook_blob.exe"
data = open(p,"rb").read()
pe = pefile.PE(p, fast_load=True)
ib = pe.OPTIONAL_HEADER.ImageBase
def va2off(v): return pe.get_offset_from_rva(v - ib)
md = Cs(CS_ARCH_X86, CS_MODE_32)
for start in [0x1416400, 0x1416430, 0x1416450, 0x1416480, 0x14164a0]:
    print("=== start %08x ===" % start)
    ok = True
    for ins in md.disasm(data[va2off(start):va2off(0x1416530)], start):
        print("  %08x: %-22s %s %s" % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str))
    print()
