import pefile, struct
from capstone import *

p = r"D:\CS 1.6 GoldClient\MetaHook_blob.exe"
data = open(p,"rb").read()
pe = pefile.PE(p, fast_load=True)
ib = pe.OPTIONAL_HEADER.ImageBase

def off2va(off):
    return ib + pe.get_rva_from_offset(off)

def va2off(va):
    return pe.get_offset_from_rva(va - ib)

target = 0x45a8d74  # "Could not get EngineAPI"
pat = struct.pack("<I", target)
hits = []
start = 0
while True:
    i = data.find(pat, start)
    if i < 0: break
    hits.append(i)
    start = i + 1
print("xref hits:", [hex(h) for h in hits][:10])

md = Cs(CS_ARCH_X86, CS_MODE_32)
md.detail = False

for h in hits[:3]:
    va = off2va(h)
    print("=== xref at file", hex(h), "va", hex(va), "bytes", data[h-1:h+4].hex())
    # disassemble from 200 bytes before
    s = h - 200
    code = data[s:h+120]
    for ins in md.disasm(code, off2va(s)):
        mark = "  <== xref" if ins.address == va - 1 else ""
        print("  %08x: %-24s %s %s%s" % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str, mark))
