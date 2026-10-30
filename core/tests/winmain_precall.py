import pefile
from capstone import *
p = r"D:\CS 1.6 GoldClient\MetaHook_blob.exe"
data = open(p,"rb").read()
pe = pefile.PE(p, fast_load=True)
ib = pe.OPTIONAL_HEADER.ImageBase
def va2off(v): return pe.get_offset_from_rva(v - ib)
md = Cs(CS_ARCH_X86, CS_MODE_32)
start, end = 0x1416360, 0x1416530
for ins in md.disasm(data[va2off(start):va2off(end)], start):
    print("  %08x: %-22s %s %s" % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str))
