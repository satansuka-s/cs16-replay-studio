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
    if o < 0 or o >= len(data): return None
    e = data.find(b"\x00", o, o+200)
    if e < 0: return None
    s = data[o:e]
    if len(s) < 4: return None
    try: t = s.decode("ascii")
    except: return None
    if not all(32 <= ord(c) < 127 or c in "\r\n\t" for c in t): return None
    return t

# find prologues in range
start, end = 0x141bb00, 0x141d900
print("=== prologues ===")
for va in range(start, end):
    o = va2off(va)
    if data[o] == 0x55 and data[o+1] == 0x8b and data[o+2] == 0xec:
        # check preceding byte is ret/padding
        prev = data[o-1]
        print("  %08x prologue (prev=%02x)" % (va, prev))
    elif data[o] == 0x53 and data[o+1] == 0x8b and data[o+2] == 0xdc:
        prev = data[o-1]
        print("  %08x prologue2 (prev=%02x)" % (va, prev))

md = Cs(CS_ARCH_X86, CS_MODE_32)
print("=== strings pushed 0x141bb00-0x141d900 ===")
for ins in md.disasm(data[va2off(start):va2off(end)], start):
    if ins.mnemonic == "push" and ins.op_str.startswith("0x"):
        try: v = int(ins.op_str, 16)
        except: continue
        s = va2str(v)
        if s: print("  %08x: %r" % (ins.address, s[:90]))
