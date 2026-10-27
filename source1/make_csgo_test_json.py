#!/usr/bin/env python3
"""Generate a synthetic CS:GO-style JSON (as produced by csgo_demo2json.py) for
pipeline smoke tests without a real demo: 3 players, 5 seconds @128 tick,
camera follow, DE-style units (inches), z-up."""
import json
import math
import os

def main():
    ticks = 5 * 128  # 5 seconds
    frames = []
    camera = []
    cam_user = 1  # follow camera targets player 2 (entity index 2)
    for t in range(0, ticks, 8):  # 64 samples/sec
        time = t / 128.0
        ents = []
        for i in (1, 2, 3):
            o = [
                200.0 + i * 100.0 + t * 1.5 * i * (1 if i % 2 else -1),
                300.0,
                64.0 + math.sin(time * 2 + i) * 10,
            ]
            yaw = (90 + t * 0.5 * i) % 360
            pitch = math.sin(time * 3 + i) * 20
            ents.append({
                'index': i, 'player': True, 'team': ((i - 1) % 2) + 2,
                'health': 100 - i, 'place': 'mid',
                'origin': [round(v, 2) for v in o],
                'angles': [round(-pitch, 2), round((-yaw + 90) % 360, 2), 0.0],
                'velocity': [round(100 * i, 2), 0.0, 0.0],
            })
        frame = {'tick': t, 'time': round(time, 4), 'entities': ents}
        frames.append(frame)
        # follow camera for player 2 from tick 64
        if t >= 64 and len(ents) > 1:
            e = ents[1]
            camera.append({
                'tick': t, 'time': round(time, 4),
                'origin': [e['origin'][0] - 40, e['origin'][1] + 30, e['origin'][2] + 20],
                'viewangles': e['angles'], 'fov': 90, 'source': 5,
            })

    doc = {
        'demo': 'synthetic_csgo.dem', 'map': 'de_mirage', 'game': 'csgo',
        'demo_protocol': 0, 'net_protocol': 0, 'tick_interval': 8,
        'max_clients': 3, 'frames_parsed': len(frames),
        'notes': 'synthetic CS:GO-style JSON for pipeline smoke test',
        'camera': camera, 'frames': frames,
    }
    out = os.path.join(os.path.dirname(__file__), '..', 'core', 'tests', 'csgo_synthetic.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(doc, f, indent=1)
    print('wrote', out, '| frames:', len(frames), '| camera:', len(camera))

if __name__ == '__main__':
    main()
