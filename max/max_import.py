"""
3ds Max import branch for CS 1.6 demo data (JSON from demo_extract).

Run inside 3ds Max:
    (1) MAXScript utility panel or listener:
        python.ExecuteFile @"C:\dev\cs16db\max\max_import.py"
        -- or pass an environment variable before launching:
        set MAX_IMPORT_JSON=C:\demos\demo.json
        set MAX_IMPORT_OPTIONS=--scale=1 --fps=30
    (2) The script reads MAX_IMPORT_JSON (or --json=... in sys.argv) and builds:
        - FreeCamera "DemoCamera" with linear position/rotation keyframes from JSON camera samples
        - Point helper per player entity with position keyframes (root object)
        - User properties (sequence timeline) attached to player helpers for later
          MotionMixer/MaxScript folding

Coordinate conventions: GoldSrc = Z-up inches; 3ds Max = Z-up system units.
Use --scale to convert (e.g. --scale=2.54 -> centimeters, --scale=1 -> keep inches).
Angles: GoldSrc (pitch, yaw, roll) degrees; apply --mirror-yaw/--flip-pitch like the Blender branch.
"""
import json
import math
import os
import sys

try:
    from pymxs import runtime as rt
except ImportError:
    rt = None


def parse_args(argv):
    args = {
        'json': None,
        'scale': 1.0,
        'fps': 30.0,
        'mirror_yaw': False,
        'flip_pitch': False,
        'tick_rate': 100.0,
        'cam_only': False,
    }
    argv = list(argv)
    while argv:
        a = argv.pop(0)
        if a.startswith('--'):
            k = a[2:].replace('-', '_')
            if '=' in k:
                k, v = k.split('=', 1)
            elif argv:
                v = argv.pop(0)
            else:
                v = 'True'
            if k in ('mirror_yaw', 'flip_pitch', 'cam_only'):
                args[k] = v.lower() in ('1', 'true', 'yes')
            else:
                try:
                    args[k] = float(v) if k in ('scale', 'fps', 'tick_rate') else v
                except ValueError:
                    args[k] = v
    if not args['json']:
        args['json'] = os.environ.get('MAX_IMPORT_JSON')
    return args


def gs_to_max(pos, scale):
    return rt.Point3(pos[0] * scale, pos[1] * scale, pos[2] * scale)


def angles_to_max(viewangles, args):
    pitch, yaw, roll = viewangles
    if args['flip_pitch']:
        pitch = -pitch
    if args['mirror_yaw']:
        yaw = -yaw
    roll = -roll
    return rt.Point3(math.radians(pitch), math.radians(yaw), math.radians(roll))


def build(args):
    if rt is None:
        print('[error] pymxs not available: run this script inside 3ds Max')
        return 2
    with open(args['json'], 'r', encoding='utf-8') as f:
        data = json.load(f)
    fps = args['fps']
    scale = args['scale']

    # ---------------- camera ----------------
    cam = rt.FreeCamera()
    cam.name = 'DemoCamera'
    rt.select(cam)

    samples = data.get('camera', [])
    for i, c in enumerate(samples):
        t = c['tick'] / args['tick_rate']
        fr = float(i)  # placeholder frame number; use t*fps below
        fr = t * fps
        org = gs_to_max(c.get('origin', [0, 0, 0]), scale)
        ang = angles_to_max(c.get('viewangles', [0, 0, 0]), args)
        rt.animate(cam, True)
        rt.animationRange = rt.Interval(0, int(max(1, (samples[-1]['tick'] / args['tick_rate']) * fps)))
        cam.pos.controller.value = org
        cam.rotation.controller.value = ang
        rt.setAnimateButton(True)
        rt.sliderTime = fr
        cam.pos.controller.addNewKey(rt.TimeValue(fr))
        cam.rotation.controller.addNewKey(rt.TimeValue(fr))
        if c.get('fov'):
            cam.fov = c['fov']
            cam.fov.controller.addNewKey(rt.TimeValue(fr))
        rt.setAnimateButton(False)
        rt.animate(cam, False)
    print(f'[cam] {len(samples)} keyframes on {cam.name}')
    rt.animationRange = rt.Interval(0, int(max(1, (samples[-1]['tick'] / args['tick_rate']) * fps)) if samples else 100)

    if args['cam_only']:
        return 0

    # ---------------- player roots ----------------
    frames = data.get('frames', [])
    seq_timeline = {}
    for idx in sorted({e['index'] for f in frames for e in f.get('entities', [])}):
        p = rt.Point()
        p.name = 'player_%d' % idx
        p.size = 10
        rt.select(p)
        for f in frames:
            ent = next((e for e in f.get('entities', []) if e['index'] == idx), None)
            if ent is None:
                continue
            t = f['tick'] / args['tick_rate']
            fr = t * fps
            rt.setAnimateButton(True)
            rt.sliderTime = fr
            if 'origin' in ent:
                p.pos.controller.value = gs_to_max(ent['origin'], scale)
            p.pos.controller.addNewKey(rt.TimeValue(fr))
            seq_timeline.setdefault(fr, {}).setdefault(idx, ent.get('sequence', 0))
        rt.setAnimateButton(False)
        # demo metadata: sequence at each key for later MotionMixer folding
        p.setUserPropBuffer('sequence_events=' + json.dumps(
            {int(k): v[idx] for k, v in sorted(seq_timeline.items()) if idx in v}))
        print(f'[player] {p.name} keyframed; {len(p.pos.controller.keys)} keys')

    print('[done] camera + player roots imported')
    return 0


if __name__ == '__main__':
    sys.exit(build(parse_args(sys.argv[1:])))
