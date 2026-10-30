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
print("=== writes to [ebp-0x28] / [ebp-0x24] in 0x1415d00-0x1416540 ===")
for ins in md.disasm(data[va2off(0x1415d00):va2off(0x1416540)], 0x1415d00):
    if "ebp - 0x28" in ins.op_str or "ebp - 0x24" in ins.op_str or "ebp - 0x2c" in ins.op_str:
        extra = ""
        if ins.mnemonic == "push" and ins.op_str.startswith("0x"):
            s = va2str(int(ins.op_str,16))
            if s: extra = "  ; %r" % s[:70]
        print("  %08x: %-24s %s %s%s" % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str, extra))
