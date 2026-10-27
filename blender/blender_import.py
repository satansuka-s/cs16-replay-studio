#!/usr/bin/env python3
"""
Blender import branch for CS 1.6 demo data (JSON from demo_extract).

Usage (GUI or headless):
    blender --background --python blender_import.py -- \
        --json <demo.json> \
        [--out scene.blend] \
        [--fps 30] \
        [--scale 0.0254]          # GoldSrc inches -> meters
        [--mirror-yaw]            # GoldSrc yaw is clockwise; negate for Blender (default off, try both)
        [--flip-pitch]            # negate pitch for Blender camera convention (default off)
        [--cam-only]              # camera only, skip characters
        [--seq-map '0:idle,1:run,2:walk']   # sequence index -> Blender Action name
        [--bvh camera.bvh]        # import HLAE camera BVH instead of keyframing from JSON
        [--map-bsp de_dust2.bsp]  # hint to load the map via GoldImporter/io_mesh_bsp addon

Produces:
  - Camera (or BVH-imported rig) animated from JSON camera samples / interpolation
  - One empty per player entity with location keyframes (root)
  - NLA strips: action per interval, mapped by player sequence field
"""
import argparse
import json
import math
import os
import sys

def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--json', required=True)
    p.add_argument('--out', default='')
    p.add_argument('--fps', type=float, default=30.0)
    p.add_argument('--scale', type=float, default=0.0254)
    p.add_argument('--mirror-yaw', action='store_true')
    p.add_argument('--flip-pitch', action='store_true')
    p.add_argument('--cam-only', action='store_true')
    p.add_argument('--seq-map', default='')
    p.add_argument('--bvh', default='')
    p.add_argument('--map-bsp', default='')
    p.add_argument('--skip-nla', action='store_true')
    p.add_argument('--cam-step', type=int, default=1)
    p.add_argument('--tick-rate', type=float, default=100.0)
    p.add_argument('--interp', choices=['linear', 'bezier'], default='bezier',
                   help='keyframe interpolation: linear = try to keep exact demo motion')
    p.add_argument('--normalize', action='store_true',
                   help='center scene around mean camera/player origin (origin = world center)')
    p.add_argument('--export-camera-json', default='',
                   help='write camera track JSON (for After Effects import_camera.jsx) to this path')
    return p.parse_args(argv)

# ---------------------------------------------------------------- coordinate utils
def gs_to_blender(pos, scale):
    """GoldSrc: Z-up inches -> Blender: Z-up meters."""
    return (pos[0] * scale, pos[1] * scale, pos[2] * scale)

def angles_gs_to_blender(viewangles, args):
    """GoldSrc viewangles: (pitch, yaw, roll), degrees.
    Camera 'looking' direction: pitch up positive. Blender camera looks -Z.
    Euler order XYZ on camera: rotation_euler = (pitch', yaw', roll'):
      pitch' = -(pitch) if flip_pitch else pitch
      yaw'   = -(yaw)   if mirror_yaw else yaw
      roll'  = roll (positive roll tilts clockwise on screen for GoldSrc: negate)
    """
    pitch, yaw, roll = viewangles
    if args.flip_pitch:
        pitch = -pitch
    if args.mirror_yaw:
        yaw = -yaw
    # GoldSrc roll positive = clockwise viewed from behind; Blender Z-rotation
    # positive = counter-clockwise: negate for screen-stable roll.
    roll = -roll
    return (math.radians(pitch), math.radians(yaw), math.radians(roll))

# ---------------------------------------------------------------- blender scene
def ensure_blender():
    import bpy  # noqa: F401  (imported lazily so the module can be linted outside Blender)

def frame_for_time(t, fps):
    return t * fps

def evaluate_entities(data, tick, args):
    """Return (cam_origin, cam_angles, cam_fov or None) interpolated from frames."""
    import bpy  # noqa

def build_scene(args):
    import bpy
    from mathutils import Euler, Vector

    with open(args.json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    fps = args.fps
    scale = args.scale

    bpy.context.scene.render.fps = int(round(fps))
    bpy.context.scene.frame_start = 1

    # ---------------- camera ----------------
    camera = None
    if args.bvh:
        old_path = bpy.context.preferences.filepaths.script_directory
        bpy.ops.import_anim.bvh(filepath=args.bvh, target='ARMATURE')
        cam_rig = bpy.context.active_object or bpy.context.object
        camera = cam_rig
        print(f'[bvh] imported camera rig: {cam_rig.name}')
    else:
        cam_data = bpy.data.cameras.new('DemoCamera')
        camera = bpy.data.objects.new('DemoCamera', cam_data)
        bpy.context.collection.objects.link(camera)
        camera.rotation_mode = 'XYZ'

        cam = data.get('camera') or []
        if len(cam) == 1:
            # single sample: static camera
            c = cam[0]
            camera.location = Vector(gs_to_blender(c.get('origin', [0, 0, 0]), scale))
            camera.rotation_euler = Euler(angles_gs_to_blender(c.get('viewangles', [0, 0, 0]), args))
            camera.data.angle = math.radians(c.get('fov', 90))
        elif len(cam) > 1:
            bpy.context.scene.frame_end = int(frame_for_time(cam[-1]['tick'] / args.tick_rate, fps)) + 1
            for i, c in enumerate(cam):
                if i % args.cam_step:
                    continue
                t = c['tick'] / args.tick_rate
                fr = frame_for_time(t, fps)
                o = c.get('origin', [0, 0, 0])
                a = c.get('viewangles', [0, 0, 0])
                camera.location = Vector(gs_to_blender(o, scale))
                camera.rotation_euler = Euler(angles_gs_to_blender(a, args))
                camera.keyframe_insert(data_path='location', frame=fr)
                camera.keyframe_insert(data_path='rotation_euler', frame=fr)
                if c.get('fov'):
                    camera.data.angle = math.radians(c.get('fov', 90))
                    try:
                        camera.data.keyframe_insert(data_path='angle', frame=fr)
                    except TypeError:
                        try:
                            camera.data.keyframe_insert(data_path='fov', frame=fr)
                        except TypeError:
                            pass
                if i == 0:
                    bpy.context.scene.frame_start = int(fr)
            bpy.context.scene.frame_end = int(frame_for_time(cam[-1]['tick'] / args.tick_rate, fps)) + 1
            print(f'[cam] {len(cam)} keyframes on {camera.name}')
        else:
            print('[cam] no camera samples in JSON; camera created at origin')

    if args.map_bsp:
        # The BSP addon is out-of-tree; guide the user. If an operator is available,
        # call it (gold importer naming varies), otherwise print instructions.
        op_names = ['import_scene.bsp', 'import_goldsrc.bsp', 'import_mesh.bsp']
        imported = False
        for opname in op_names:
            if hasattr(bpy.ops, opname):
                getattr(bpy.ops, opname)(filepath=args.map_bsp)
                imported = True
                print(f'[map] imported {args.map_bsp} via {opname}')
                break
        if not imported:
            print('[map] no BSP importer addon is enabled. Install GoldImporter or '
                  'blender_io_mesh_bsp, then import manually: File > Import > BSP.')

    if args.cam_only:
        apply_export_and_finalize(args, data, camera, [])
        save_scene(args)
        return

    # ---------------- player roots + NLA ----------------
    seq_map = {}
    if args.seq_map:
        for item in args.seq_map.split(','):
            if ':' in item:
                k, v = item.split(':', 1)
                seq_map[int(k.strip())] = v.strip()

    frames = data.get('frames', [])
    if not frames:
        print('[nla] no entity frames in JSON')
        apply_export_and_finalize(args, data, camera, [])
        save_scene(args)
        return

    # collect playable actions available in the scene (imported via SMD addon)
    actions = {a.name for a in bpy.data.actions}
    print(f'[nla] actions in file: {sorted(actions)[:20]}')

    entities = {e['index'] for f in frames for e in f.get('entities', [])}
    players = []
    for idx in sorted(entities):
        player = bpy.data.objects.new(f'player_{idx}', None)
        bpy.context.collection.objects.link(player)
        player.empty_display_size = 0.5
        player.empty_display_type = 'ARROWS'
        players.append(player)

        first = None
        last_t = 0.0
        seg_start = None
        seg_seq = None
        for f in frames:
            ents = {e['index']: e for e in f.get('entities', [])}
            e = ents.get(idx)
            t = f['tick'] / args.tick_rate
            if e is None:
                continue
            fr = frame_for_time(t, fps)
            o = e.get('origin')
            if o:
                player.location = Vector(gs_to_blender(o, scale))
                player.keyframe_insert(data_path='location', frame=fr)
                if first is None:
                    first = fr
            last_t = max(last_t, t)
            seq = e.get('sequence', 0)
            if args.skip_nla:
                continue
            action_name = seq_map.get(seq)
            if action_name is None or action_name not in actions:
                continue
            if seg_start is None:
                seg_start = fr
                seg_seq = action_name
            elif action_name != seg_seq:
                push_nla(player, seg_seq, seg_start, fr)
                seg_start = fr
                seg_seq = action_name
        if seg_start is not None and not args.skip_nla:
            push_nla(player, seg_seq, seg_start, last_t * fps)

        if first is not None:
            bpy.context.scene.frame_start = min(bpy.context.scene.frame_start, int(first))
        bpy.context.scene.frame_end = max(bpy.context.scene.frame_end, int(last_t * fps))
        print(f'[player] {player.name}: location keyframes {"OK" if player.animation_data and player.animation_data.action else "partial"}')

    apply_export_and_finalize(args, data, camera, players)
    save_scene(args)


def push_nla(obj, action_name, start, end):
    import bpy
    action = bpy.data.actions.get(action_name)
    if action is None:
        print(f'[nla] {obj.name}: action not found, skipping strip {action_name}')
        return
    if obj.animation_data is None:
        obj.animation_data_create()
    track = obj.animation_data.nla_tracks.new()
    track.name = f'{action_name}'
    strip = track.strips.new(action_name, int(start), int(end - start))
    print(f'[nla] {obj.name}: strip {action_name} [{int(start)}..{int(end)}]')


def apply_export_and_finalize(args, data, camera, players):
    """--interp / --normalize / --export-camera-json postprocessing."""
    import bpy

    if args.export_camera_json and data.get('camera'):
        export = {'camera': data['camera'], 'tick_rate': args.tick_rate,
                  'map': data.get('map', ''), 'game': data.get('game', '')}
        path = args.export_camera_json
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(export, f, indent=1)
        print(f'[ae] camera JSON for After Effects: {path}')

    if args.normalize:
        # mean of all camera positions (and player roots) -> subtract
        pts = [c.get('origin', [0, 0, 0]) for c in data.get('camera', [])]
        for f in data.get('frames', []):
            for e in f.get('entities', []):
                if 'origin' in e:
                    pts.append(e['origin'])
        if pts:
            center = [sum(p[i] for p in pts) / len(pts) for i in range(3)]
            for obj in bpy.context.scene.objects:
                if obj.type == 'EMPTY' or obj.type == 'CAMERA':
                    obj.location.x -= center[0] * args.scale
                    obj.location.y -= center[1] * args.scale
                    obj.location.z -= center[2] * args.scale
            print(f'[norm] scene centered, removed {[round(c, 1) for c in center]}')

    if args.interp == 'linear':
        if not camera:
            camera = bpy.data.objects.get('DemoCamera')
        objs = [camera] + players if camera else players
        n = 0
        for obj in objs:
            if not (obj and obj.animation_data and obj.animation_data.action):
                continue
            try:
                for fc in obj.animation_data.action.fcurves:
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'LINEAR'
                        n += 1
            except Exception as e:
                # Blender 5 slotted-action API differences: fall back to safe path
                print(f'[interp] fallback needed: {e}')
                break
        print(f'[interp] keyframes set to LINEAR ({n} points)')


def save_scene(args):
    import bpy
    if args.out:
        out = args.out
        if not out.endswith('.blend'):
            out += '.blend'
        bpy.ops.wm.save_as_mainfile(filepath=out)
        print(f'[save] {out}')
    else:
        print('[save] no --out given; scene in memory (open Blender GUI to inspect)')


def main():
    args = parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    try:
        build_scene(args)
    except Exception as e:  # surface errors for headless runs
        print(f'[error] {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
