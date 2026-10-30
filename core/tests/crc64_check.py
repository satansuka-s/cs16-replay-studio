# CRC64/XZ (ECMA-182) as used by MetaHook
POLY = 0xC96C5795D7870F42
def crc64(data):
    crc = 0xFFFFFFFFFFFFFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ (POLY if crc & 1 else 0)
    return crc ^ 0xFFFFFFFFFFFFFFFF

for p in [r"D:\CS 1.6 GoldClient\hw.dll", r"D:\CS 1.6 GoldClient\filesystem_stdio.dll"]:
    d = open(p,"rb").read()
    print(p.split("\\")[-1], "%016x" % crc64(d), len(d))
