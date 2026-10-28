"""One-button replay builder: demo JSON + goldsrc install -> Blender scene.

Builds from a demo_extract JSON: BSP map (+textures, lightmap vertex colours,
skybox from gfx/env), player models (SMD reference + per-sequence NLA strips
driven by the demo entity timeline), camera track (keyframed on demo time with
svc FOV), sound/kill event markers and beacons.

Usage (inside Blender):
  blender --background --factory-startup --python replay_import.py -- \
      --demo-json out.json --game "D:\\Counter-Strike Build 4554" \
      --models-dir work\\models --out replay.blend [--scale 0.0254] [--fps 30] \
      [--cam-spline] [--no-sky]
"""
import argparse
import json
import math
import os
import re
import struct
import sys

from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bsp_import
import smd_import


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument('--demo-json', required=True)
    p.add_argument('--game', default='D:\\Counter-Strike Build 4554')
    p.add_argument('--models-dir', default='')
    p.add_argument('--out', default='replay.blend')
    p.add_argument('--scale', type=float, default=1.0)
    p.add_argument('--fps', type=float, default=30.0)
    p.add_argument('--tex-dir', default='')
    p.add_argument('--cam-spline', action='store_true',
                   help='add polyline camera path (manual smooth later)')
    p.add_argument('--no-sky', action='store_true',
                   help='skip the gfx/env skybox, use a plain background colour')
    return p.parse_args(argv)


# ------------------------------------------------------------------ math ----

def gs_look_quat(pitch_deg, yaw_deg):
    """GoldSrc viewangles -> Blender quaternion looking along the view dir."""
    p = math.radians(pitch_deg)
    y = math.radians(yaw_deg)
    d = Vector((math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), -math.sin(p)))
    return d.to_track_quat('-Z', 'Y')


def gs_body_quat(pitch_deg, yaw_deg):
    """Entity body orientation: model forward is local +X (MDL convention)."""
    p = math.radians(pitch_deg)
    y = math.radians(yaw_deg)
    d = Vector((math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), -math.sin(p)))
    return d.to_track_quat('X', 'Z')


def lens_from_fov(fov_deg, sensor=36.0):
    f = min(max(fov_deg, 1.0), 170.0)
    return sensor * 0.5 / math.tan(math.radians(f) * 0.5)


def _action_fcurves(action):
    """Iterate fcurves across Blender <=4.4 (legacy) and 5.0 (slot channelbags)."""
    try:
        if getattr(action, 'fcurves', None) is not None:
            yield from action.fcurves
            return
    except AttributeError:
        pass
    try:
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    yield from bag.fcurves
    except Exception:
        pass


def set_fcurves_linear(obj, data_paths):
    ad = obj.animation_data
    if not ad or not ad.action:
        return
    for fcu in _action_fcurves(ad.action):
        if fcu.data_path in data_paths:
            for kp in fcu.keyframe_points:
                kp.interpolation = 'LINEAR'


# ------------------------------------------------------------- camera -------

def choose_camera_track(camera):
    """Pick the best available camera source.

    Sources: 0 = demo ClientDataFrame (player feet position), 1 = svc_clientdata,
    2 = RefParams inside the demo frame prefix (what the renderer actually saw),
    4 = HLTV proxy view entity. Priority: 2, 1, 4, 0.
    Returns (samples, lift_z): lift is added to origin (source 0 stores feet;
    the other sources are already at eye level).
    """
    by_src = {}
    for c in camera:
        by_src.setdefault(c.get('source', 0), []).append(c)
    for src in (2, 1, 4, 0):
        if src in by_src:
            samples = sorted(by_src[src], key=lambda c: (c.get('time', 0), c.get('tick', 0)))
            return samples, (28.0 if src == 0 else 0.0)
    return [], 0.0


def build_camera(demo, cam, fps):
    camera = demo.get('camera') or []
    samples, lift = choose_camera_track(camera)
    if not samples:
        print('[cam] no camera track in JSON')
        return []
    for c in samples:
        t = c.get('time', c.get('tick', 0) / 100.0)
        fr = t * fps
        o = c.get('origin', [0, 0, 0])
        a = c.get('viewangles', [0, 0, 0])
        cam.location = Vector((o[0], o[1], o[2] + lift))
        cam.rotation_quaternion = gs_look_quat(a[0], a[1])
        cam.keyframe_insert('location', frame=fr)
        cam.keyframe_insert('rotation_quaternion', frame=fr)
        fov = c.get('fov') or 90.0
        cam.data.lens = lens_from_fov(fov)
        cam.data.keyframe_insert('lens', frame=fr)
    set_fcurves_linear(cam, {'location', 'rotation_quaternion'})
    print(f'[cam] {len(samples)} samples (source {samples[0].get("source")}), '
          f'time-based keys, FOV baked to lens')
    return samples


# ------------------------------------------------------------------- map ----

def bsp_worldspawn(path):
    try:
        with open(path, 'rb') as fh:
            d = fh.read()
        eo, el = struct.unpack_from('<ii', d, 4)  # lump 0 = entities
        txt = d[eo:eo + el].decode('latin1', 'replace')
        m = re.search(r'"skyname"\s+"([^"]*)"', txt, re.I)
        return m.group(1) if m else ''
    except OSError:
        return ''


def find_sky_images(game_dir, skyname):
    """Six gfx/env tgas for a skybox name (falls back to 'desert')."""
    sub = [os.path.join(game_dir, 'cstrike', 'gfx', 'env'),
           os.path.join(game_dir, 'valve', 'gfx', 'env'),
           os.path.join(game_dir, 'gfx', 'env')]
    for nm in [skyname, 'desert']:
        if not nm:
            continue
        found = {}
        for side in ('bk', 'ft', 'lf', 'rt', 'up', 'dn'):
            for gd in sub:
                cand = os.path.join(gd, nm + side + '.tga')
                if os.path.exists(cand):
                    found[side] = cand
                    break
        if len(found) >= 5:
            return found
    return {}


def add_skybox(game_dir, skyname, center, dist):
    """Six emissive planes around the map, camera-only visibility."""
    imgs = find_sky_images(game_dir, skyname)
    if not imgs:
        if skyname:
            print(f'[sky] no gfx/env images for "{skyname}"')
        return False
    import bpy
    size = dist * 2.2
    faces = {
        'ft': (Vector((0, 1, 0)), None, None),
        'bk': (Vector((0, -1, 0)), None, None),
        'rt': (Vector((1, 0, 0)), None, None),
        'lf': (Vector((-1, 0, 0)), None, None),
        'up': (Vector((0, 0, 1)), Vector((0, -1, 0)), Vector((-1, 0, 0))),
        'dn': (Vector((0, 0, -1)), Vector((0, -1, 0)), Vector((1, 0, 0))),
    }
    Z = Vector((0, 0, 1))
    uv_corner = [(0, 0), (1, 0), (1, 1), (0, 1)]
    for side, (dd, r_ov, u_ov) in faces.items():
        if side not in imgs:
            continue
        if r_ov is not None:
            r, u = r_ov, u_ov
        else:
            r = dd.cross(Z)
            if r.length < 1e-6:
                r = Vector((0, -1, 0))
            u = Z
        n = -dd
        mesh = bpy.data.meshes.new('sky_' + side)
        half = size * 0.5
        c = [(-half, -half, 0), (half, -half, 0), (half, half, 0), (-half, half, 0)]
        mesh.from_pydata(c, [], [[0, 1, 2, 3]])
        uvl = mesh.uv_layers.new(name='UVMap')
        for k in range(4):
            uvl.data[k].uv = uv_corner[k]
        mat = bpy.data.materials.new('sky_' + side)
        mat.use_nodes = True
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        outn = next((x for x in nodes if x.type == 'OUTPUT_MATERIAL'), None)
        em = nodes.new('ShaderNodeEmission')
        em.inputs['Strength'].default_value = 1.0
        links.new(em.outputs[0], outn.inputs['Surface'])
        tex = nodes.new('ShaderNodeTexImage')
        tex.image = bpy.data.images.load(imgs[side], check_existing=True)
        links.new(tex.outputs['Color'], em.inputs['Color'])
        mesh.materials.append(mat)
        ob = bpy.data.objects.new('sky_' + side, mesh)
        bpy.context.collection.objects.link(ob)
        ob.matrix_world = Matrix(((r.x, u.x, n.x, center.x + dd.x * dist),
                                  (r.y, u.y, n.y, center.y + dd.y * dist),
                                  (r.z, u.z, n.z, center.z + dd.z * dist),
                                  (0, 0, 0, 1)))
        # background only: no shadows/diffuse/glossy participation
        for attr in ('visible_shadow', 'visible_diffuse', 'visible_glossy',
                     'visible_transmission', 'visible_volume_scatter'):
            if hasattr(ob, attr):
                setattr(ob, attr, False)
    print(f'[sky] box from gfx/env/{skyname}* sides: {", ".join(imgs.keys())}')
    return True


# --------------------------------------------------------------- players ----

def load_actions(model_dir, manifest):
    """Actions from seq SMDs: (label -> frames, label -> manifest meta)."""
    actions = {}
    meta = {}
    for s in manifest.get('sequences', []):
        fn = s.get('file')
        if not fn:
            continue
        path = os.path.join(model_dir, 'seq', fn)
        if os.path.exists(path):
            nodes, skeleton, _ = smd_import._parse(path)
            if skeleton and s.get('frames', 0) > 1:
                actions[s['label']] = skeleton
                meta[s['label']] = s
    return actions, meta


def main():
    args = parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    import bpy

    with open(args.demo_json, encoding='utf-8') as f:
        demo = json.load(f)
    mapname = demo.get('map', '').replace('\\', '/').split('/')[-1]
    fps = args.fps
    scale = args.scale
    scene = bpy.context.scene
    scene.render.fps = max(1, int(round(fps)))
    scene.frame_start = 0

    # ---------- map ----------
    bsp_path = ''
    for mod in ('cstrike', 'csgo'):
        cand = os.path.join(args.game, mod, 'maps', mapname + '.bsp')
        if os.path.exists(cand):
            bsp_path = cand
            break
    tex_out = os.path.abspath(args.tex_dir) if args.tex_dir else \
        os.path.join(os.path.dirname(os.path.abspath(args.out)), 'map_tex')
    if bsp_path:
        bsp_import.import_bsp(bsp_path, 'map_' + mapname, tex_dir=tex_out)
        for mat in list(bpy.data.materials):
            bsp_import.load_texture_into_material(mat.name, tex_out)
    else:
        print('[map] BSP not found for', mapname,
              '- CS:GO maps need SourceIO in Blender 4.x; players/camera still work')

    # ---------- world + skybox ----------
    world = bpy.data.worlds.new('World')
    world.use_nodes = True
    bg = next((n for n in world.node_tree.nodes if n.type == 'BACKGROUND'), None)
    if bg:
        bg.inputs['Color'].default_value = (0.45, 0.5, 0.55, 1.0)
        bg.inputs['Strength'].default_value = 1.0
    scene.world = world
    map_center = Vector((0, 0, 0))
    map_obj = bpy.data.objects.get('map_' + mapname)
    if map_obj:
        bb = [Vector((v[0], v[1], v[2])) for v in map_obj.bound_box]
        if bb:
            mn = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
            mx = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
            map_center = (mn + mx) * 0.5
    if bsp_path and not args.no_sky:
        add_skybox(args.game, bsp_worldspawn(bsp_path), map_center * scale, 9000 * scale)

    # ---------- camera ----------
    camdata = bpy.data.cameras.new('DemoCamera')
    camdata.sensor_fit = 'HORIZONTAL'
    camdata.clip_start = 1.0
    camdata.clip_end = 65536.0 * max(scale, 1e-6)
    cam = bpy.data.objects.new('DemoCamera', camdata)
    bpy.context.collection.objects.link(cam)
    cam.rotation_mode = 'QUATERNION'
    cam_samples = build_camera(demo, cam, fps)
    scene.camera = cam

    # ---------- model palette ----------
    model_dirs = []
    if args.models_dir and os.path.isdir(args.models_dir):
        model_dirs = [os.path.join(args.models_dir, d) for d in sorted(os.listdir(args.models_dir))
                      if os.path.isdir(os.path.join(args.models_dir, d))]
    print(f'[models] {len(model_dirs)} available')

    # ---------- player inventory ----------
    frames = demo.get('frames', []) or []
    player_seen = {}
    for f in frames:
        t = f.get('time', 0)
        for e in f.get('entities', []):
            if not e.get('player'):
                continue
            info = player_seen.setdefault(e['index'], {'has_origin': False, 'rows': []})
            info['rows'].append(dict(e, _t=t, _seq=e.get('sequence', 0),
                                     _cycle=e.get('cycle', 0.0)))
            if e.get('origin'):
                info['has_origin'] = True
    if player_seen:
        print(f'[players] {len(player_seen)} ids in entity timeline')
    else:
        print('[players] no player entities in JSON')

    ghosts = sorted(i for i, v in player_seen.items() if not v['has_origin'])
    ghost_id = ghosts[0] if ghosts else None

    def pick_model(idx):
        if not model_dirs:
            return None
        return model_dirs[idx % len(model_dirs)]

    players = {}
    for idx in sorted(player_seen):
        arm = None
        actions, act_meta, manifest = {}, {}, None
        md = pick_model(idx) or ''
        if md:
            ref = None
            for x in os.listdir(md):
                if x.endswith('_reference.smd'):
                    ref = os.path.join(md, x)
                    break
            mp = os.path.join(md, 'manifest.json')
            if os.path.exists(mp):
                with open(mp, encoding='utf-8') as mf:
                    manifest = json.load(mf)
            if manifest:
                actions, act_meta = load_actions(md, manifest)
            if ref:
                arm = smd_import.import_smd(ref, obj_name='player_%d' % idx,
                                            fps=fps, seq_actions=actions)
                if arm:
                    if scale != 1.0:
                        arm.scale = (scale, scale, scale)
                    tga = [x for x in os.listdir(md) if x.endswith('.tga')]
                    if tga:
                        smd_import.attach_texture(arm, 'model', os.path.join(md, tga[0]))
                    print(f'[player] {idx} -> {os.path.basename(md)} ({len(actions)} actions)')
        if arm is None:
            arm = bpy.data.objects.new('player_%d' % idx, None)
            arm.empty_display_type = 'CUBE'
            arm.empty_display_size = 72.0 * scale
            bpy.context.collection.objects.link(arm)
            md = ''
        arm.rotation_mode = 'XYZ'
        players[idx] = {'object': arm, 'dir': md, 'actions': actions,
                        'meta': act_meta, 'manifest': manifest, 'ghost': idx == ghost_id}

    # ---------- motion keyframes ----------
    for f in frames:
        fr = f.get('time', 0) * fps
        for e in f.get('entities', []):
            if not e.get('player'):
                continue
            pl = players.get(e['index'])
            if not pl:
                continue
            obj = pl['object']
            o = e.get('origin')
            if o:
                obj.location = Vector((o[0] * scale, o[1] * scale, o[2] * scale))
                obj.keyframe_insert('location', frame=fr)
                a = e.get('angles') or [0, 0, 0]
                obj.rotation_euler = gs_body_quat(a[0], a[1]).to_euler()
                obj.keyframe_insert('rotation_euler', frame=fr)
    for pl in players.values():
        set_fcurves_linear(pl['object'], {'location', 'rotation_euler'})

    # ghost player (local client in listen demos) -> source-0 feet track
    if ghost_id is not None:
        feet = [c for c in (demo.get('camera') or []) if c.get('source') == 0]
        if feet:
            obj = players[ghost_id]['object']
            for c in feet:
                o = c['origin']
                obj.location = Vector((o[0] * scale, o[1] * scale, o[2] * scale))
                obj.keyframe_insert('location', frame=c.get('time', 0) * fps)
                yaw = (c.get('viewangles') or [0, 0, 0])[1]
                obj.rotation_euler = gs_body_quat(0, yaw).to_euler()
                obj.keyframe_insert('rotation_euler', frame=c.get('time', 0) * fps)
            set_fcurves_linear(obj, {'location', 'rotation_euler'})
            print(f'[players] local player {ghost_id} bound to source-0 feet track')

    # ---------- NLA strips per sequence run ----------
    for idx in sorted(players):
        pl = players[idx]
        if not pl['actions'] or pl['ghost']:
            continue
        arm = pl['object']
        ad = arm.animation_data
        if ad is None:
            continue
        ad.action = None
        rows = pl and player_seen[idx]['rows']
        if not rows:
            continue
        runs = []
        cur = None
        for e in rows:
            t, seq = e['_t'], e['_seq']
            if cur is None or seq != cur[2]:
                if cur is not None:
                    runs.append((cur[0], t, cur[2], cur[3]))
                cur = (t, None, seq, e['_cycle'])
        if cur is not None:
            runs.append((cur[0], rows[-1]['_t'] + 1.0 / fps, cur[2], cur[3]))
        track = ad.nla_tracks.new()
        track.name = 'DemoSequences'
        n_ok = 0
        for t0, t1, seq, cyc in runs:
            label, meta = None, {}
            for sm in (pl['manifest'] or {}).get('sequences', []):
                if sm.get('index') == seq:
                    label, meta = sm.get('label'), sm
                    break
            frames_smd = pl['actions'].get(label)
            if not frames_smd:
                continue
            pref = 'player_%d' % idx
            action = next((a for a in bpy.data.actions
                           if a.name.startswith(pref) and a.name.endswith('_' + label)), None)
            if action is None:
                continue
            seq_frames = max(len(frames_smd), int(meta.get('frames') or len(frames_smd)))
            seq_fps = float(meta.get('fps') or 15.0)
            start = max(1, int(round(t0 * fps)))
            end = max(start + 1, int(round(t1 * fps)))
            try:
                strip = track.strips.new('seq_%s@%.2f' % (label, t0), start, action)
                strip.frame_end = end
                off = max(0.0, min(float(cyc), 0.999)) * seq_frames
                span = (end - start) * (seq_fps / fps)
                strip.action_frame_start = off
                strip.action_frame_end = off + span
                if span > seq_frames:
                    strip.repeat = max(span / seq_frames, 0.001)
                n_ok += 1
            except Exception as ex:
                print(f'[nla] player {idx} strip "{label}" failed: {ex}')
        if n_ok:
            print(f'[nla] player {idx}: {n_ok} strips')

    # ---------- edit markers + beacons ----------
    ev_colors = {'sound': (1.0, 0.7, 0.2), 'kill': (1.0, 0.2, 0.15), 'round': (0.35, 0.8, 1.0)}
    for ev in demo.get('events', []):
        t = ev.get('time', ev.get('tick', 0) / 100.0)
        etype = ev.get('type', 'sound')
        if etype == 'round':
            name = 'round_%s' % ev.get('round_id', ev.get('tick', 0))
        elif etype == 'kill':
            name = 'kill_%s_%s' % (ev.get('subject', 0), ev.get('target', 0))
        else:
            name = 'snd_%s' % ev.get('index', ev.get('tick', 0))
        mk = scene.timeline_markers.new(name, frame=int(round(t * fps)))
        try:
            mk.color = ev_colors.get(etype, (0.8, 0.8, 0.8))
        except AttributeError:
            pass
        o = ev.get('origin')
        if o:
            beacon = bpy.data.objects.new('evt_%d_%s' % (ev['tick'], etype), None)
            bpy.context.collection.objects.link(beacon)
            beacon.location = Vector((o[0] * scale, o[1] * scale, o[2] * scale))
            beacon.empty_display_size = 1.0
            beacon.empty_display_type = 'SPHERE'
    if demo.get('events'):
        print(f'[markers] {len(demo["events"])} events -> timeline + beacons')

    # ---------- camera spline ----------
    if args.cam_spline and len(cam_samples) >= 4:
        curve = bpy.data.curves.new('CamPath', 'CURVE')
        curve.dimensions = '3D'
        spline = curve.splines.new('POLY')
        spline.points.add(len(cam_samples) - 1)
        for i, c in enumerate(cam_samples):
            o = c.get('origin', [0, 0, 0])
            lift = 28.0 if c.get('source') == 0 else 0.0
            spline.points[i].co = (o[0] * scale, o[1] * scale, (o[2] + lift) * scale, 1)
        path = bpy.data.objects.new('CamPath', curve)
        bpy.context.collection.objects.link(path)
        print('[cam] spline path CamPath created')

    # ---------- light ----------
    # NOTE: background/headless EEVEE on this machine ignores SUN lights;
    # the point light at the camera gives predictable fill light.
    sun = bpy.data.lights.new('Sun', 'SUN')
    sun.energy = 2.0
    sunobj = bpy.data.objects.new('Sun', sun)
    sunobj.rotation_euler = (math.radians(55), 0, math.radians(-30))
    bpy.context.collection.objects.link(sunobj)

    pl = bpy.data.lights.new('Fill', 'POINT')
    pl.energy = 500000.0
    pl.shadow_soft_size = 50.0
    plobj = bpy.data.objects.new('Fill', pl)
    bpy.context.collection.objects.link(plobj)
    cam_track = bpy.data.objects.get('DemoCamera')
    if cam_track is not None:
        con = plobj.constraints.new(type='COPY_LOCATION')
        con.target = cam_track
        off = plobj.constraints.new(type='TRACK_TO')
        off.target = cam_track
        off.track_axis = 'TRACK_NEGATIVE_Z'
        off.up_axis = 'UP_Y'

    # ---------- frame range ----------
    times = [c.get('time', 0) for c in cam_samples] + [f.get('time', 0) for f in frames]
    scene.frame_end = max(1, int(round(max(times) * fps)) + 1) if times else 1

    if args.out:
        out = args.out if args.out.endswith('.blend') else args.out + '.blend'
        bpy.ops.wm.save_as_mainfile(filepath=out)
        print('[save]', out)


if __name__ == '__main__':
    main()
