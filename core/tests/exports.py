import pefile
for p in [r"D:\CS 1.6 GoldClient\hw.dll", r"D:\CS 1.6 GoldClient\filesystem_stdio.dll"]:
    pe = pefile.PE(p, fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_EXPORT']])
    names = []
    if hasattr(pe, 'DIRECTORY_ENTRY_EXPORT'):
        names = [e.name.decode(errors='replace') for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name]
    print(p.split('\\')[-1], 'exports:', names[:20], '... total', len(names))
