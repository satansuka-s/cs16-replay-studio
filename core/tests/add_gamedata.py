import json, hashlib, os, datetime

gd = r'D:\CS 1.6 GoldClient\cstrike\metahook\gamedata'
idx_path = os.path.join(gd, 'index.json')
idx = json.load(open(idx_path, encoding='utf-8'))

# remove previous custom entry
idx['versions'] = [v for v in idx['versions'] if v.get('gameVersion') not in ('hl-gold-1127', 'hl-9999')]
old = os.path.join(gd, 'hl-gold-1127.json')
if os.path.exists(old):
    src = json.load(open(old, encoding='utf-8'))
    os.remove(old)
else:
    src = json.load(open(os.path.join(gd, 'hl-8684.json'), encoding='utf-8'))

src['source']['gameVersion'] = 'hl-9999'
src['binaries']['engine']['windows']['crc64'] = 'e528ce35231f1021'
out_name = 'hl-9999.json'
data = json.dumps(src, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
open(os.path.join(gd, out_name), 'wb').write(data)
entry = {
    'gameVersion': 'hl-9999', 'url': out_name,
    'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data),
    'snapshotSchemaVersion': 8, 'fileCount': 19,
    'lastPublishTime': datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
}
idx['versions'].append(entry)
open(idx_path, 'w', encoding='utf-8').write(json.dumps(idx, separators=(',', ':'), ensure_ascii=False))
print('ok', out_name, len(data))
