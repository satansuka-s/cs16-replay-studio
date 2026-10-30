import re
p = r'D:\CS 1.6 GoldClient\MetaHook.exe'
data = open(p,'rb').read()
for kw in [b'plugins.lst', b'metahook.log', b'Metahook', b'plugin', b'Trinity']:
    idxs = [m.start() for m in re.finditer(re.escape(kw), data)][:5]
    print(kw, len(idxs), idxs)
    for i in idxs[:3]:
        chunk = data[max(0,i-40):i+80]
        s = ''.join(chr(c) if 32 <= c < 127 else '.' for c in chunk)
        print('   ', s)
