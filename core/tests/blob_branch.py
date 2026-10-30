import pefile
from capstone import *
p = r"D:\CS 1.6 GoldClient\MetaHook_blob.exe"
data = open(p,"rb").read()
pe = pefile.PE(p, fast_load=True)
ib = pe.OPTIONAL_HEADER.ImageBase
def va2off(v): return pe.get_offset_from_rva(v - ib)
def va2str(v):
    try: o = va2off(v)
    except: return None
    e = data.find(b"\x00", o, o+200)
    if e < 0: return None
    s = data[o:e]
    try: t = s.decode("ascii")
    except: return None
    return t if len(t)>=3 and all(32<=ord(c)<127 or c in "\r\n\t" for c in t) else None

md = Cs(CS_ARCH_X86, CS_MODE_32)
# dump the start of the blob branch 0x141640b..0x1416500
print("=== blob branch 0x141640b..0x141650c ===")
for ins in md.disasm(data[va2off(0x141640b):va2off(0x141650c)], 0x141640b):
    extra = ""
    if ins.mnemonic == "push" and ins.op_str.startswith("0x"):
        s = va2str(int(ins.op_str,16))
        if s: extra = "  ; %r" % s[:70]
    print("  %08x: %-22s %s %s%s" % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str, extra))
