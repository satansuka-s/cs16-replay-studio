import pefile
for p in [r"D:\CS 1.6 GoldClient\hw.dll", r"D:\CS 1.6 GoldClient\filesystem_stdio.dll"]:
    pe = pefile.PE(p, fast_load=False)
    print("===", p.split("\\")[-1], "size", pe.OPTIONAL_HEADER.SizeOfImage)
    for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
        print("  imports from", entry.dll.decode(errors="replace"), "count", len(entry.imports))
    # exports details
    if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
        for e in pe.DIRECTORY_ENTRY_EXPORT.symbols:
            print("  export", e.name, "at RVA", hex(e.address) if e.address else None, "forwarder", e.forwarder)
    print("  entrypoint RVA", hex(pe.OPTIONAL_HEADER.AddressOfEntryPoint))
