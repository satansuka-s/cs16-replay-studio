import pefile, math, collections
for path in [r"D:\CS 1.6 GoldClient\hw.dll", r"D:\CS 1.6 GoldClient\FileSystem_Stdio.dll"]:
    pe = pefile.PE(path, fast_load=True)
    print("===", path)
    print("machine=%x imagebase=%x sizeOfImage=%x entry=%x" % (pe.FILE_HEADER.Machine, pe.OPTIONAL_HEADER.ImageBase, pe.OPTIONAL_HEADER.SizeOfImage, pe.OPTIONAL_HEADER.AddressOfEntryPoint))
    for s in pe.sections:
        d = s.get_data()
        if d:
            c = collections.Counter(d)
            ent = -sum((v/len(d))*math.log2(v/len(d)) for v in c.values())
        else:
            ent = 0
        print("  %-10s va=%08x vs=%08x raw=%08x ent=%.2f %s" % (s.Name.decode(errors="replace").strip("\x00"), s.VirtualAddress, s.Misc_VirtualSize, s.SizeOfRawData, ent, hex(s.Characteristics)))
    print("  timestamp:", pe.FILE_HEADER.TimeDateStamp)
