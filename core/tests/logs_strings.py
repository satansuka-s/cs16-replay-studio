import re
data = open(r'D:\CS 1.6 GoldClient\MetaHook.exe','rb').read()
for m in re.finditer(rb'[ -~]{4,}\.log', data):
    i = m.start()
    chunk = data[max(0,i-60):m.end()+20]
    s = ''.join(chr(c) if 32 <= c < 127 else '.' for c in chunk)
    print(s)
