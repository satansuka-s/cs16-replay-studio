import pefile
p = r"D:\CS 1.6 GoldClient\MetaHook_blob.exe"
data = open(p,"rb").read()
pe = pefile.PE(p, fast_load=True)
ib = pe.OPTIONAL_HEADER.ImageBase
def off2va(o): return ib + pe.get_rva_from_offset(o)
def va2off(v): return pe.get_offset_from_rva(v - ib)

def func_start(va):
    o = va2off(va)
    # scan backwards for CC padding run
    i = o
    while i > 0:
        if data[i] == 0xCC and data[i-1] == 0xCC and data[i-2] == 0xCC:
            # function starts after the padding
            j = i
            while data[j] == 0xCC:
                j += 1
            return off2va(j)
        i -= 1
    return None

for va in [0x14196f9, 0x14190b3, 0x14190fd, 0x14199cc, 0x141b9e0, 0x141ad40, 0x1418130]:
    print(hex(va), "-> func start", hex(func_start(va)) if func_start(va) else None)
