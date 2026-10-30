import pefile, struct
from capstone import *

def analyze(path):
    data = open(path,"rb").read()
    pe = pefile.PE(path, fast_load=True)
    ib = pe.OPTIONAL_HEADER.ImageBase
    def off2va(o): return ib + pe.get_rva_from_offset(o)
    def va2off(v): return pe.get_offset_from_rva(v - ib)

    prologue = bytes.fromhex("538BDC83EC0883E4F883C404558B6B04896C24048BEC")
    hits = []
    st = 0
    while True:
        i = data.find(prologue, st)
        if i < 0: break
        hits.append(off2va(i)); st = i+1
    print("===", path, "MH_LoadEngine candidates:", [hex(h) for h in hits])
    if not hits: return
    target = hits[0]
    calls = []
    for i in range(len(data)-5):
        if data[i] == 0xE8:
            rel = struct.unpack_from("<i", data, i+1)[0]
            src = off2va(i)
            if src + 5 + rel == target:
                calls.append(src)
    print("  call sites:", [hex(c) for c in calls])
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    for c in calls:
        s = c - 0x50
        print("  --- around %08x ---" % c)
        for ins in md.disasm(data[va2off(s):va2off(c)+5], s):
            mark = "  <== CALL" if ins.address == c else ""
            print("    %08x: %-20s %s %s%s" % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str, mark))

analyze(r"D:\CS 1.6 GoldClient\MetaHook.exe")
analyze(r"D:\CS 1.6 GoldClient\MetaHook_blob.exe")
