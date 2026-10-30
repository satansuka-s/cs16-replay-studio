import pefile
from capstone import *
p = r"D:\CS 1.6 GoldClient\MetaHook_blob.exe"
data = open(p,"rb").read()
pe = pefile.PE(p, fast_load=True)
ib = pe.OPTIONAL_HEADER.ImageBase
def va2off(v): return pe.get_offset_from_rva(v - ib)
md = Cs(CS_ARCH_X86, CS_MODE_32)
for start in [0x141b710, 0x141b9e0, 0x1418f50, 0x1419670, 0x1418130]:
    print("=== %08x ===" % start)
    code = data[va2off(start):va2off(start)+24]
    for ins in md.disasm(code, start):
        print("  %08x: %-18s %s %s" % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str))
