import pefile
from capstone import *
p = r"D:\CS 1.6 GoldClient\MetaHook_blob.exe"
data = open(p,"rb").read()
pe = pefile.PE(p, fast_load=True)
ib = pe.OPTIONAL_HEADER.ImageBase
def va2off(v): return pe.get_offset_from_rva(v - ib)
def va2str(v):
    o = va2off(v)
    if o < 0 or o >= len(data): return None
    e = data.find(b"\x00", o, o+200)
    if e < 0: return None
    s = data[o:e]
    if len(s) < 4: return None
    try: t = s.decode("ascii")
    except: return None
    if not all(32 <= ord(c) < 127 or c in "\r\n\t" for c in t): return None
    return t

md = Cs(CS_ARCH_X86, CS_MODE_32)
def scan(start, end, label):
    print("=== %s %08x-%08x ===" % (label, start, end))
    for ins in md.disasm(data[va2off(start):va2off(end)], start):
        if ins.mnemonic == "push" and ins.op_str.startswith("0x"):
            try: v = int(ins.op_str, 16)
            except: continue
            s = va2str(v)
            if s: print("  %08x: push %-12s ; %r" % (ins.address, ins.op_str, s[:80]))
        elif ins.mnemonic == "ret":
            print("  %08x: ret" % ins.address)

scan(0x141b710, 0x141b9e0, "func A")
scan(0x141b9e0, 0x141bc00, "func B")
