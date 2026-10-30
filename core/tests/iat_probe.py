import pefile
p = r"D:\CS 1.6 GoldClient\MetaHook_blob.exe"
data = open(p,"rb").read()
pe = pefile.PE(p, fast_load=False)
ib = pe.OPTIONAL_HEADER.ImageBase
def va2off(v): return pe.get_offset_from_rva(v - ib)
def va2str(v):
    try: o = va2off(v)
    except: return None
    e = data.find(b"\x00", o, o+200)
    if e < 0: return None
    return data[o:e].decode("ascii","replace")

# map IAT slots
iat = {}
for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
    dll = entry.dll.decode()
    for imp in entry.imports:
        if imp.address:
            iat[imp.address] = "%s!%s" % (dll, imp.name.decode() if imp.name else "#%d" % imp.ordinal)

for va in [0x44660c8, 0x44660ac, 0x44660b0, 0x44660cc, 0x44662a4, 0x4466140, 0x4466294]:
    print(hex(va), "->", iat.get(va, "?"))

for s in [0x45a8ea0, 0x45a982c, 0x45a8dc8, 0x45dad14, 0x45a8f18]:
    print(hex(s), repr(va2str(s)))
