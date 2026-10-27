#!/usr/bin/env python3
"""Download custom resources (models/sounds/sprites) that a demo server used but
were not found locally. Two sources:
  1) local game installation (cstrike/, cstrike/custom/) - preferred
  2) fastdl HTTP root (like http://server/cstrike/) - fallback per file

Input: demo JSON (demo_extract output, section resources) or --file list.
Severity: files are matched by lowercase relative path; existing files are skipped
(the server version may differ - use --force to overwrite).

Usage:
  python fetch_resources.py demo.json --game "D:\\Counter-Strike Build 4554" --out out_dir
  python fetch_resources.py demo.json --fastdl https://gameserver/cstrike --out out_dir
"""
import json
import os
import sys
import urllib.request

def main():
    args = sys.argv[1:]
    src = game = fastdl = out_dir = None
    force = False
    for a in args:
        if a.startswith('--game='): game = a.split('=', 1)[1]
        elif a.startswith('--fastdl='): fastdl = a.split('=', 1)[1]
        elif a.startswith('--out='): out_dir = a.split('=', 1)[1]
        elif a == '--force': force = True
        else: src = a
    if not src or not out_dir:
        print(__doc__); return 2
    os.makedirs(out_dir, exist_ok=True)

    resources = []
    if src.lower().endswith('.json'):
        with open(src, encoding='utf-8') as f:
            data = json.load(f)
        r = data.get('resources', {})
        for k in ('models', 'sounds', 'sprites', 'skins'):
            resources += r.get(k, [])
    else:
        with open(src) as f:
            resources = [ln.strip() for ln in f if ln.strip()]

    game_root = None
    if game:
        for cand in (os.path.join(game, 'cstrike'), game, os.path.join(game, 'cstrike', 'custom')):
            if os.path.isdir(cand):
                game_root = cand
                break

    fetched, local_hits, missing = 0, 0, 0
    for name in resources:
        name = name.replace('\\', '/')
        rel = name[7:] if name.startswith('models/') else name  # keep as-is for now
        target = os.path.join(out_dir, name.replace('/', os.sep))
        if os.path.exists(target) and not force:
            continue
        # 1) local copy
        if game_root:
            cand = os.path.join(game_root, name.replace('/', os.sep))
            if os.path.exists(cand):
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(cand, 'rb') as g, open(target, 'wb') as o:
                    o.write(g.read())
                local_hits += 1
                print(f'[local] {name}')
                continue
        # 2) fastdl
        if fastdl:
            url = fastdl.rstrip('/') + '/' + name
            try:
                with urllib.request.urlopen(url, timeout=15) as resp:
                    body = resp.read()
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, 'wb') as o:
                    o.write(body)
                fetched += 1
                print(f'[http ] {name} ({len(body)} bytes)')
                continue
            except Exception as e:
                missing += 1
                print(f'[miss ] {name}: {e}')
    print(f'done: {fetched} via http, {local_hits} from local, {missing} missing')
    return 0

if __name__ == '__main__':
    sys.exit(main())
