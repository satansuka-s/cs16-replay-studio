import pefile
p = r'D:\CS 1.6 GoldClient\cstrike\metahook\plugins\TrinityRender.dll'
pe = pefile.PE(p, fast_load=False)
print('machine', hex(pe.FILE_HEADER.Machine), 'dll', pe.is_dll())
print('=== exports ===')
if hasattr(pe, 'DIRECTORY_ENTRY_EXPORT'):
    for e in pe.DIRECTORY_ENTRY_EXPORT.symbols:
        print('  ', e.ordinal, e.name, hex(e.address) if e.address else None)
print('=== imports ===')
for entry in getattr(pe, 'DIRECTORY_ENTRY_IMPORT', []):
    print(' ', entry.dll.decode(errors='replace'))
    for imp in entry.imports[:8]:
        print('     ', imp.name)
