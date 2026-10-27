#!/usr/bin/env python3
"""CS:GO (Source 1) demo -> cs16db JSON (same schema as demo_extract output).

Uses demoparser2 (pip install demoparser2), the de-facto standard CS:GO/CS2
demo parser (https://pypi.org/project/demoparser2/).

Notes:
- CS:GO demos contain per-tick player positions/angles/velocity (like GoldSrc),
  but NOT player animation sequence/frame and NOT an observer camera track
  (same HLTV-style limitation). For an FPS-centric replay the camera can be
  derived from a player's viewangles (--follow USERID).
- Coordinates: Source units (1 unit = 1 inch, Z-up) - same convention as GoldSrc,
  so blender_import.py/max_import.py work unchanged.

Usage:
  python csgo_demo2json.py demo.dem out.json [--follow USERID] [--tick-step N]
"""
import json
import math
import os
import sys

def main():
    args = sys.argv[1:]
    src = None
    out = 'csgo_out.json'
    follow = None
    step = 1
    for a in args:
        if a.startswith('--follow='): follow = int(a.split('=', 1)[1])
        elif a.startswith('--tick-step='): step = int(a.split('=', 1)[1])
        elif a.startswith('--out='): out = a.split('=', 1)[1]
        elif src is None: src = a
    if not src:
        print(__doc__)
        return 2
    try:
        from demoparser2 import DemoParser
    except ImportError:
        print('[error] pip install demoparser2')
        return 1

    try:
        parser = DemoParser(src)
        header = parser.parse_header()
        players = parser.parse_player_info()
        props = [
            "userid", "player_name", "team", "is_alive", "health",
            "x", "y", "z",
            "pitch", "yaw", "roll",
            "velocity_x", "velocity_y", "velocity_z",
            "last_place_name",
        ]
        ticks = parser.parse_ticks(props)
    except Exception as e:
        print(f'[error] failed to parse {src}: {e}')
        print('       (is this a CS:GO/CSS or CS2 demo file?)')
        return 1
    if ticks is None or len(ticks) == 0:
        print(f'[error] no parsed ticks in {src} (unsupported game?)')
        return 1

    # tick -> time: demos tick at their recorded tickrate; approximate from header
    tickrate = float(header.get('tick_rate') or 128.0)
    players_valid = {p['steamid']: p for p in players} if isinstance(players, list) else {}

    def frame_time(tick):
        return tick / tickrate

    frames = []
    camera = []
    last_tick = None
    for row in ticks.to_dict('records'):
        t = int(row.get('tick', 0))
        if last_tick is None:
            last_tick = t
        if step > 1 and (t - last_tick) % step != 0 and t != last_tick:
            continue
        frame = {
            'tick': t,
            'time': frame_time(t),
            'entities': [],
        }
        e = {
            'index': int(row.get('userid') or 0),
            'player': bool(row.get('is_alive') is not None and row.get('userid')),
            'team': row.get('team'),
            'health': row.get('health'),
            'place': row.get('last_place_name') or '',
        }
        if row.get('x') is not None:
            e['origin'] = [round(float(row['x']), 2), round(float(row['y']), 2), round(float(row['z']), 2)]
        if row.get('pitch') is not None:
            # CS:GO pitch: up positive; yaw: counter-clockwise-positive from
            # -X axis; convert to our GoldSrc-style pitch/yaw/roll for pipelines
            pitch = float(row['pitch'])
            yaw = float(row['yaw'])
            e['angles'] = [
                round(-pitch, 2),          # CS:GO pitch down-positive -> our pitch
                round((-yaw + 90) % 360, 2),  # CS:GO yaw to GoldSrc-style yaw
                round(float(row.get('roll') or 0), 2),
            ]
        if row.get('velocity_x') is not None:
            e['velocity'] = [
                round(float(row['velocity_x']), 2),
                round(float(row['velocity_y']), 2),
                round(float(row['velocity_z']), 2),
            ]
        frame['entities'].append(e)
        frames.append(frame)

        if follow is not None and int(row.get('userid') or 0) == follow:
            if e.get('origin') and e.get('angles'):
                camera.append({
                    'tick': t,
                    'time': frame_time(t),
                    'origin': e['origin'],
                    'viewangles': e['angles'],
                    'fov': 90,
                    'source': 5,  # CS:GO follow camera
                })

    doc = {
        'demo': os.path.basename(src),
        'map': header.get('map_name') or '',
        'game': 'csgo',
        'demo_protocol': header.get('protocol') or 0,
        'net_protocol': header.get('network_protocol') or 0,
        'tick_interval': step,
        'max_clients': len(players) if isinstance(players, list) else 0,
        'frames_parsed': len(frames),
        'notes': 'CS:GO (Source 1) via demoparser2; units = inches Z-up; no sequence/frame (not recorded in CS:GO demos)',
        'camera': camera,
        'frames': frames,
    }
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(doc, f, indent=1)
    print(f'done: {out} ({len(frames)} frames, {len(camera)} camera samples)')

if __name__ == '__main__':
    sys.exit(main())
