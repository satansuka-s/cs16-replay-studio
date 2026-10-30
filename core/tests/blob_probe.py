import pefile
from capstone import *
p = r"D:\CS 1.6 GoldClient\MetaHook_blob.exe"
data = open(p,"rb").read()
pe = pefile.PE(p, fast_load=True)
ib = pe.OPTIONAL_HEADER.ImageBase
def va2off(v): return pe.get_offset_from_rva(v - ib)
def va2str(v):
    o = va2off(v)
    e = data.find(b"\x00", o, o+200)
    return data[o:e].decode("ascii", "replace") if e>0 else None
for v in [0x45a8f18]:
    print(hex(v), repr(va2str(v)))

md = Cs(CS_ARCH_X86, CS_MODE_32)
print("=== 0x141f5b0 prologue ===")
for ins in md.disasm(data[va2off(0x141f5b0):va2off(0x141f5b0)+0x80], 0x141f5b0):
    print("  %08x: %-22s %s %s" % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str))
print("=== strings pushed in 0x141f5b0..0x141f700 ===")
for ins in md.disasm(data[va2off(0x141f5b0):va2off(0x141f700)], 0x141f5b0):
    if ins.mnemonic == "push" and ins.op_str.startswith("0x"):
        try: v = int(ins.op_str,16)
        except: continue
        s = va2str(v)
        if s and len(s)>=4 and all(32<=ord(c)<127 for c in s): print("  %08x: %r" % (ins.address, s))
