import struct

def crc64_table(poly):
    tab = []
    for i in range(256):
        crc = i
        for _ in range(8):
            crc = (crc >> 1) ^ poly if crc & 1 else crc >> 1
        tab.append(crc)
    return tab

# reflected polys
POLY_ECMA_REFL = 0xC96C5795D7870F42
POLY_ISO_REFL  = 0xD800000000000000
POLY_JONES_REFL= 0x95AC9329AC4BC9B5

def crc64_file(path, poly, init=0xFFFFFFFFFFFFFFFF, xorout=0xFFFFFFFFFFFFFFFF):
    tab = crc64_table(poly)
    crc = init
    with open(path, 'rb') as f:
        while True:
            b = f.read(1 << 20)
            if not b: break
            for c in b:
                crc = tab[(crc ^ c) & 0xFF] ^ (crc >> 8)
    return crc ^ xorout

files = {
 '4554 hw.dll': r'D:\Counter-Strike Build 4554\hw.dll',
 '4554 FileSystem_Stdio.dll': r'D:\Counter-Strike Build 4554\FileSystem_Stdio.dll',
 'Gold hw.dll': r'D:\CS 1.6 GoldClient\hw.dll',
 'Gold FileSystem_Stdio.dll': r'D:\CS 1.6 GoldClient\FileSystem_Stdio.dll',
}
targets = {'4554': 'af713d75d839d5c7', '8684': 'f9b2f43f1509eb5c'}
for name, p in files.items():
    print(name)
    for label, poly in (('ecma', POLY_ECMA_REFL), ('iso', POLY_ISO_REFL), ('jones', POLY_JONES_REFL)):
        v = crc64_file(p, poly)
        mark = ''
        if '%016x' % v in targets.values(): mark = '  <== MATCH'
        print('   %-5s %016x%s' % (label, v, mark))
