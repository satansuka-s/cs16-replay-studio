import pefile
from capstone import *
p = r"D:\CS 1.6 GoldClient\MetaHook_blob.exe"
data = open(p,"rb").read()
pe = pefile.PE(p, fast_load=True)
ib = pe.OPTIONAL_HEADER.ImageBase
def va2off(v): return pe.get_offset_from_rva(v - ib)
md = Cs(CS_ARCH_X86, CS_MODE_32)
print("=== WinMain tail 0x1416523..0x14165c0 ===")
for ins in md.disasm(data[va2off(0x1416523):va2off(0x14165c0)], 0x1416523):
    print("  %08x: %-24s %s %s" % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str))
