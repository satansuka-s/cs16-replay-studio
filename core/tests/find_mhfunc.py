import pefile, struct
from capstone import *

p = r"D:\CS 1.6 GoldClient\MetaHook_blob.exe"
data = open(p,"rb").read()
pe = pefile.PE(p, fast_load=True)
ib = pe.OPTIONAL_HEADER.ImageBase

def off2va(off): return ib + pe.get_rva_from_offset(off)

target = 0x45a9250
pat = struct.pack("<I", target)
hits = []
start = 0
while True:
    i = data.find(pat, start)
    if i < 0: break
    hits.append(i); start = i+1
print("xrefs to MH_LoadEngine error string:", [(hex(h), hex(off2va(h))) for h in hits])

md = Cs(CS_ARCH_X86, CS_MODE_32)
for h in hits:
    s = max(0, h-400)
    print("=== around", hex(off2va(h)))
    for ins in md.disasm(data[s:h+80], off2va(s)):
        if ins.address >= off2va(h)-64:
            print("  %08x: %-20s %s %s" % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str))
