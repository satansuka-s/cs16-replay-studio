#!/usr/bin/env python3
"""One-command pipeline: CS:GO demo -> JSON -> Blender scene (+ camera JSON for AE).

Usage:
  python source1/run_pipeline.py demo.dem [--out scene.blend] [--follow USERID]
       [--tick-step 2] [--start-tick 0] [--end-tick 30000] [--interp linear]
       [--normalize] [--ae cam.json] [--cam-only]

The script verifies demoparser2 is installed, converts the demo to our common
JSON, then invokes Blender (from --blender or BLENDER env or PATH).
"""
import json
import os
import subprocess
import sys


def find_blender():
    cands = [
        os.environ.get('BLENDER', ''),
        r'D:\Blender\blender.exe',
        r'D:\Blender\5.0\blender.exe',
        'blender',
    ]
    for c in cands:
        if c and os.path.exists(c):
            return c
    return 'blender'


def main():
    args = sys.argv[1:]
    demo = None
    out = 'csgo_scene.blend'
    extra = []
    for a in args:
        if a.startswith('--out='):
            out = a.split('=', 1)[1]
        else:
            if demo is None and not a.startswith('--'):
                demo = a
            else:
                extra.append(a)
    if not demo:
        print(__doc__)
        return 2

    script_dir = os.path.dirname(os.path.abspath(__file__))
    conv = os.path.join(script_dir, 'csgo_demo2json.py')
    json_path = os.path.splitext(out)[0] + '.json'

    print(f'[1/3] converting {demo} ...')
    r = subprocess.run([sys.executable, conv, demo, f'--out={json_path}'] + extra)
    if r.returncode != 0:
        print('[error] conversion failed (is demoparser2 installed? pip install demoparser2)')
        return r.returncode

    blender = find_blender()
    import_path = os.path.join(os.path.dirname(script_dir), 'blender', 'blender_import.py')
    cam_args = [a for a in extra if a.startswith('--follow')]
    cmd = [blender, '--background', '--python', import_path, '--',
           f'--json={json_path}', f'--out={out}']
    if '--cam-only' in extra:
        cmd.append('--cam-only')
    print(f'[2/3] blender import -> {out} ...')
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print('[warn] blender step returned nonzero')
        return r.returncode

    print(f'[3/3] done. Files: {json_path}, {out}')
    print('      After Effects: ae/import_camera.jsx +', json_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
