import re
for p in [r'D:\CS 1.6 GoldClient\MetaHook.exe', r'D:\CS 1.6 GoldClient\cstrike\metahook\plugins\CaptionMod.dll']:
    data = open(p,'rb').read()
    print('===', p)
    for m in re.finditer(rb'METAHOOK_PLUGIN_API_VERSION[0-9]*', data):
        i = m.start()
        chunk = data[max(0,i-50):i+60]
        s = ''.join(chr(c) if 32 <= c < 127 else '.' for c in chunk)
        print('   ', s)
