import pefile
from capstone import *
p = r"D:\CS 1.6 GoldClient\MetaHook_blob.exe"
data = open(p,"rb").read()
pe = pefile.PE(p, fast_load=True)
ib = pe.OPTIONAL_HEADER.ImageBase
def va2off(va): return pe.get_offset_from_rva(va - ib)
md = Cs(CS_ARCH_X86, CS_MODE_32)
s, e = 0x1416600, 0x1416750
for ins in md.disasm(data[va2off(s):va2off(e)], s):
    print("%08x: %-24s %s %s" % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str))
