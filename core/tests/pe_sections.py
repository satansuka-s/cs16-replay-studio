import pefile
for path in [r"D:\CS 1.6 GoldClient\MetaHook_blob.exe", r"D:\CS 1.6 GoldClient\MetaHook.exe", r"D:\Counter-Strike Build 4554\hw.dll"]:
    pe = pefile.PE(path, fast_load=True)
    print("===", path)
    print("  ImageBase=%08x SizeOfImage=%08x" % (pe.OPTIONAL_HEADER.ImageBase, pe.OPTIONAL_HEADER.SizeOfImage))
    for s in pe.sections:
        print("    %-10s va=%08x vs=%08x raw=%08x" % (s.Name.decode(errors="replace").strip("\x00"), s.VirtualAddress, s.Misc_VirtualSize, s.SizeOfRawData))
