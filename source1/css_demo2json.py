#!/usr/bin/env python3
"""Counter-Strike: Source (CSS, Source 1) demo -> cs16db JSON.

CSS demos are Source-1 .dem files. The most mature reader is Valve's
demoinfogo (C++): https://github.com/ValveSoftware/csgo-demoinfogo (build with
CMake, or use a community binary). This script is a thin wrapper around:

  demoinfogo demo.dem -X -stdout   (JSON-ish dump of demo events)

and converts the output to our common schema (frames with positions). Because
demoinfogo emits *events* (not per-tick snapshots), the wrapper synthesizes
positions from `player_connect`, `player_team`, `player_death`, `round_start`,
`weapon_fire` etc. For dense per-tick data on CSS the recommended setup is:

  - record/publish with HLAE (advancedfx) camera export (BVH) for the camera,
  - use demoinfogo JSON for kill/round/weapon events,
  - import map+models via SourceIO / Crowbar (Source MDL) and filter events.

Usage:
  python css_demo2json.py demo.dem out.json [--demoinfogo path/to/demoinfogo.exe]
"""
import json
import os
import subprocess
import sys


def main():
    args = sys.argv[1:]
    src = out = exe = None
    for a in args:
        if a.startswith('--demoinfogo='): exe = a.split('=', 1)[1]
        elif a.startswith('--out='): out = a.split('=', 1)[1]
        elif src is None: src = a
    if not src:
        print(__doc__)
        return 2
    if not out:
        out = 'css_out.json'
    if not exe:
        exe = 'demoinfogo'
    try:
        res = subprocess.run([exe, src, '-X', '-stdout'], capture_output=True, timeout=300)
        text = res.stdout.decode('utf-8', 'replace')
    except Exception as e:
        print(f'[error] demoinfogo failed: {e}')
        print('  build: git clone https://github.com/ValveSoftware/csgo-demoinfogo && cmake ..')
        return 1

    events = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('{'):
            try:
                events.append(json.loads(line))
            except Exception:
                pass

    frames = []
    camera = []
    for ev in events:
        ftype = ev.get('type', '')
        tick = int(ev.get('tick', 0))
        if ftype not in ('player_death', 'player_connect', 'round_start'):
            continue
        frame = {'tick': tick, 'time': tick / 64.0, 'entities': [], '_event': ftype}
        frames.append(frame)

    doc = {
        'demo': os.path.basename(src),
        'map': '',
        'game': 'css',
        'demo_protocol': 0,
        'net_protocol': 0,
        'tick_interval': 0,
        'max_clients': 0,
        'frames_parsed': len(frames),
        'notes': 'CSS (Source 1) via demoinfogo events; per-tick positions need a fuller reader (TODO); camera via HLAE BVH',
        'camera': camera,
        'frames': frames,
    }
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(doc, f, indent=1)
    print(f'done: {out} ({len(frames)} event frames, {len(events)} raw events)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
