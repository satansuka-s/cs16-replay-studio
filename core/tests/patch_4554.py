import json, hashlib, os

gd = r'D:\Counter-Strike Build 4554\cstrike\metahook\gamedata'
idx_path = os.path.join(gd, 'index.json')
idx = json.load(open(idx_path, encoding='utf-8'))
src_path = os.path.join(gd, 'hl-4554.json')
src = json.load(open(src_path, encoding='utf-8'))
src['binaries']['engine']['windows']['crc64'] = '47dc98f6c909835a'
data = json.dumps(src, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
open(src_path, 'wb').write(data)
for v in idx['versions']:
    if v.get('gameVersion') == 'hl-4554':
        v['sha256'] = hashlib.sha256(data).hexdigest()
        v['size'] = len(data)
open(idx_path, 'w', encoding='utf-8').write(json.dumps(idx, separators=(',', ':'), ensure_ascii=False))
print('patched hl-4554 crc, size', len(data))
