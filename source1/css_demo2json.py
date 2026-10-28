#!/usr/bin/env python3
"""Counter-Strike: Source (CSS, Source 1) demo -> cs16db JSON.

Primary path: our own css_extract.exe (built on css-demo-parser, sockfish/
bamtna) - decodes HL2DEMO demos (demo protocol 3, net protocol 24, 14-23
handled) with full per-tick PlayerTracker output: origin/eye angles/velocity/
team/health per player per tick, camera (source 5) and kill/round events.

  pip-install-free; build once with source1\\build_css_extract.bat

Fallback: demoinfogo event dump (kills/rounds only, no per-tick positions).

Usage:
  python css_demo2json.py demo.dem out.json [--follow N] [--exe path\\css_extract.exe]
"""
import json
import os
import subprocess
import sys


def main():
    args = sys.argv[1:]
    src = out = exe = None
    follow = 0
    for a in args:
        if a.startswith('--exe='):
            exe = a.split('=', 1)[1]
        elif a.startswith('--out='):
            out = a.split('=', 1)[1]
        elif a.startswith('--follow='):
            follow = int(a.split('=', 1)[1])
        elif src is None:
            src = a
    if not src:
        print(__doc__)
        return 2
    if not out:
        out = 'css_out.json'
    root = os.path.dirname(os.path.abspath(__file__))
    if not exe:
        cand = os.path.join(root, 'css_extract', 'build', 'css_extract.exe')
        if os.path.exists(cand):
            exe = cand
    if exe and os.path.exists(exe):
        cmd = [exe, src, out]
        if follow > 0:
            cmd += ['--follow', str(follow)]
        r = subprocess.call(cmd)
        return r

    # ---- fallback: demoinfogo events ----
    exe = exe or 'demoinfogo'
    print('[info] css_extract.exe not found - falling back to demoinfogo events')
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
        'notes': 'CSS via css-demo-parser (css_extract): per-tick positions; '
                 'fallback path = demoinfogo events only',
        'camera': camera,
        'frames': frames,
    }
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(doc, f, indent=1)
    print(f'done: {out} ({len(frames)} event frames, {len(events)} raw events)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
