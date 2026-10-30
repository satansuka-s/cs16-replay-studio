import re
p = r'D:\CS 1.6 GoldClient\cstrike\metahook\plugins\TrinityRender.dll'
data = open(p,'rb').read()
pats = [b'MetaHook', b'METAHOOK', b'Plugin', b'PLUGIN', b'Interface', b'VERSION', b'Trinity']
for kw in pats:
    idxs = [m.start() for m in re.finditer(re.escape(kw), data)]
    print(kw, len(idxs))
    for i in idxs[:6]:
        chunk = data[max(0,i-60):i+90]
        s = ''.join(chr(c) if 32 <= c < 127 else '.' for c in chunk)
        print('    ', s)
