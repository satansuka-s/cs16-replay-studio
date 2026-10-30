import pefile, struct
from capstone import *

p = r"D:\CS 1.6 GoldClient\MetaHook_blob.exe"
data = open(p,"rb").read()
pe = pefile.PE(p, fast_load=True)
ib = pe.OPTIONAL_HEADER.ImageBase
def va2off(va): return pe.get_offset_from_rva(va - ib)

md = Cs(CS_ARCH_X86, CS_MODE_32)
start_va = 0x1415e00
end_va   = 0x1416b00
code = data[va2off(start_va):va2off(end_va)]
prev = []
for ins in md.disasm(code, start_va):
    if ins.mnemonic == "call":
        print("%08x: call %s" % (ins.address, ins.op_str))
    prev.append(ins)
