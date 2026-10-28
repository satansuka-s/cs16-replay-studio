"""Source 1 BSP (v17-v21: CS:GO, CS:S, HL2...) importer for Blender.

Self-contained geometry importer: world faces from VERTEXES/EDGES/SURFEDGES/
FACES/TEXINFO/TEXDATA lumps.  Textures are pre-extracted by
core/tools/source1_tex.py into tex_dir (PNG per material).

Structure layouts follow SourceIO (MIT, REDxEYE).  Skips: displacements
(no dispinfo support yet), SURF_SKY/SURF_NODRAW faces.
"""
import bpy
import os
import struct

from mathutils import Vector


def _i32(d, o): return struct.unpack_from('<i', d, o)[0]
def _u16(d, o): return struct.unpack_from('<H', d, o)[0]
def _f32(d, o): return struct.unpack_from('<f', d, o)[0]

SURF_SKY = 0x0004
SURF_NODRAW = 0x0080


def safe_name(name):
    return ''.join(c if c.isalnum() or c in '_-' else '_' for c in name).strip() or 'tex'


def load_lumps(d):
    lumps = []
    for i in range(64):
        o, s, v, dsz = struct.unpack_from('<iiII', d, 8 + i * 16)
        lumps.append((o, s))
    return lumps


def import_source_bsp(path, object_name='map', tex_dir=None):
    d = open(path, 'rb').read()
    version = _i32(d, 4)
    if version < 17 or version > 21:
        print('[sbsp] unsupported version', version)
        return None
    lumps = load_lumps(d)
    tex_dir = os.path.abspath(tex_dir) if tex_dir else ''

    # ---- vertices / edges / surfedges / faces / texinfo / texdata ----
    v_off, v_len = lumps[3]
    verts = [(_f32(d, v_off + i * 12), _f32(d, v_off + i * 12 + 4), _f32(d, v_off + i * 12 + 8))
             for i in range(v_len // 12)]

    e_off, e_len = lumps[12]
    edges = [(_u16(d, e_off + i * 4), _u16(d, e_off + i * 4 + 2)) for i in range(e_len // 4)]

    se_off, se_len = lumps[13]
    surfedges = [_i32(d, se_off + i * 4) for i in range(se_len // 4)]

    f_off, f_len = lumps[7]
    nfaces = f_len // 56

    ti_off, ti_len = lumps[6]
    texinfos = []
    for i in range(ti_len // 40):
        o = ti_off + i * 40
        sv = [(_f32(d, o + k * 4), _f32(d, o + k * 4 + 4), _f32(d, o + k * 4 + 8), _f32(d, o + k * 4 + 12))
              for k in range(2)]
        flags = _i32(d, o + 32)
        texdata = _i32(d, o + 36)
        texinfos.append((sv, flags, texdata))

    td_off, td_len = lumps[2]
    texdatas = []
    for i in range(td_len // 32):
        o = td_off + i * 32
        name_id = _i32(d, o + 12)
        texdatas.append(name_id)

    # strings
    sdo, sds = lumps[43]
    sto, sts = lumps[44]
    sdata = d[sdo:sdo + sds]
    stable = d[sto:sto + sts]
    count = sts // 2 if sts else 0
    offs = struct.unpack_from('<%dH' % count, stable, 0) if count else ()
    names = []
    for o in offs:
        names.append(sdata[o:].split(b'\0')[0].decode('latin1', 'replace') if o < len(sdata) else '')

    def matname(ti):
        sv, flags, td = ti
        if td < 0 or td >= len(texdatas):
            return None
        nid = texdatas[td]
        if nid < 0 or nid >= len(names):
            return None
        return names[nid]

    # ---- build per-material faces ----
    meshes = {}
    n_skip = {'disp': 0, 'sky': 0, 'nodraw': 0, 'tools': 0}
    for fi in range(nfaces):
        o = f_off + fi * 56
        planenum, side, on_node = struct.unpack_from('<HBB', d, o)
        first_edge = _i32(d, o + 4)
        numedges, texinfo_id, dispinfo_id, fogvol = struct.unpack_from('<4h', d, o + 8)
        # styles at o+16 (4 bytes), light_offset at o+20, area o+24 ...
        if dispinfo_id != -1:
            n_skip['disp'] += 1
            continue
        if texinfo_id < 0 or texinfo_id >= len(texinfos):
            continue
        sv, flags, td = texinfos[texinfo_id]
        nm = matname(texinfos[texinfo_id])
        if nm is None or not nm:
            continue
        low = nm.lower()
        if flags & SURF_SKY or low.startswith('tools/toolsskybox'):
            n_skip['sky'] += 1
            continue
        if flags & SURF_NODRAW or low.startswith('tools/'):
            n_skip['tools'] += 1
            continue
        if numedges <= 0:
            continue
        face_v = []
        ok = True
        for k in range(numedges):
            se = surfedges[first_edge + k] if 0 <= first_edge + k < len(surfedges) else 0
            ei = abs(se)
            if ei >= len(edges):
                ok = False
                break
            a, b = edges[ei]
            vi = a if se > 0 else b
            if vi >= len(verts):
                ok = False
                break
            face_v.append(verts[vi])
        if not ok or len(face_v) < 3:
            continue
        data = meshes.setdefault(nm, {'v': [], 'uv': [], 'f': []})
        for pt in face_v:
            v = Vector(pt)
            data['v'].append(pt)
            u = v.dot(Vector(sv[0][:3])) + sv[0][3]
            t = v.dot(Vector(sv[1][:3])) + sv[1][3]
            data['uv'].append((u, 1.0 - t))
        base = len(data['v']) - len(face_v)
        data['f'].append(list(range(base, base + len(face_v))))

    # ---- displacement terrain (lump 26 info, 33 verts) ----
    disp_verts_all = None
    do, ds = lumps[26]
    dvo, dvs = lumps[33]
    disp_count = ds // 176
    if disp_count and dvs:
        # dispvert: position 3f, dist f, alpha f (20 bytes)
        dv_count = dvs // 20
        disp_a = []
        for i in range(dv_count):
            o = dvo + i * 20
            px, py, pz = _f32(d, o), _f32(d, o + 4), _f32(d, o + 8)
            di = _f32(d, o + 12)
            disp_a.append((px * di, py * di, pz * di))
        disp_meshes = {}
        for i in range(disp_count):
            o = do + i * 176
            sx, sy, sz = _f32(d, o), _f32(d, o + 4), _f32(d, o + 8)
            vert_start = _i32(d, o + 12)
            power = _i32(d, o + 20)
            map_face = _i32(d, o + 36)
            if power < 1 or power > 4:
                continue
            if map_face < 0 or map_face >= nfaces:
                continue
            fo = f_off + map_face * 56
            first_edge = _i32(d, fo + 4)
            numedges = struct.unpack_from('<h', d, fo + 8)[0]
            ti_idx = struct.unpack_from('<h', d, fo + 10)[0]
            disp_idx = struct.unpack_from('<h', d, fo + 12)[0]
            if numedges != 4 or ti_idx < 0 or ti_idx >= len(texinfos) or disp_idx == -1:
                continue
            corner = []
            ok = True
            for k in range(numedges):
                se = surfedges[first_edge + k] if 0 <= first_edge + k < len(surfedges) else 0
                ei = abs(se)
                if ei >= len(edges):
                    ok = False
                    break
                a, b = edges[ei]
                vi = a if se > 0 else b
                if vi >= len(verts):
                    ok = False
                    break
                corner.append(verts[vi])
            if not ok or len(corner) != 4:
                continue
            # corner closest to start_position
            best = min(range(4), key=lambda k: sum((corner[k][a] - (sx, sy, sz)[a]) ** 2 for a in range(3)))
            num = (1 << power) + 1
            step = 1.0 / (num - 1)
            le = tuple(corner[(best + 1) & 3][a] - corner[best][a] for a in range(3))
            re = tuple(corner[(best + 2) & 3][a] - corner[(best + 3) & 3][a] for a in range(3))
            sv, _, _ = texinfos[ti_idx]
            nm = matname(texinfos[ti_idx]) or 'disp'
            data = disp_meshes.setdefault(nm, {'v': [], 'uv': [], 'f': []})
            base = len(data['v'])
            for ii in range(num):
                l0 = corner[best][0] + le[0] * ii * step
                l1 = corner[best][1] + le[1] * ii * step
                l2 = corner[best][2] + le[2] * ii * step
                r0 = corner[(best + 3) & 3][0] + re[0] * ii * step
                r1 = corner[(best + 3) & 3][1] + re[1] * ii * step
                r2 = corner[(best + 3) & 3][2] + re[2] * ii * step
                for jj in range(num):
                    idx = vert_start + ii * num + jj
                    ox = oy = oz = 0.0
                    if idx < len(disp_a):
                        ox, oy, oz = disp_a[idx]
                    px = l0 + (r0 - l0) * jj * step + ox
                    py = l1 + (r1 - l1) * jj * step + oy
                    pz = l2 + (r2 - l2) * jj * step + oz
                    v = Vector((px, py, pz))
                    data['v'].append((px, py, pz))
                    u = v.dot(Vector(sv[0][:3])) + sv[0][3]
                    t = v.dot(Vector(sv[1][:3])) + sv[1][3]
                    data['uv'].append((u, 1.0 - t))
            for ii in range(num - 1):
                for jj in range(num - 1):
                    idx = ii * num + jj
                    if idx & 1:
                        data['f'].append([base + idx, base + idx + 1, base + idx + num])
                        data['f'].append([base + idx + 1, base + idx + num + 1, base + idx + num])
                    else:
                        data['f'].append([base + idx, base + idx + num + 1, base + idx + num])
                        data['f'].append([base + idx, base + idx + 1, base + idx + num + 1])
        for nm, data in disp_meshes.items():
            meshes.setdefault(nm, {'v': [], 'uv': [], 'f': []})
            base = len(meshes[nm]['v'])
            meshes[nm]['v'].extend(data['v'])
            meshes[nm]['uv'].extend(data['uv'])
            for f in data['f']:
                meshes[nm]['f'].append([i + base for i in f])
        if disp_meshes:
            print('[sbsp] displacement terrain: %d materials, %d verts'
                  % (len(disp_meshes), sum(len(v['v']) for v in disp_meshes.values())))

    # ---- assemble mesh ----
    mesh = bpy.data.meshes.new(object_name + '_mesh')
    all_v, all_uv, all_f, mat_names = [], [], [], list(meshes.keys())
    for mn in mat_names:
        base = len(all_v)
        all_v.extend(meshes[mn]['v'])
        all_uv.extend(meshes[mn]['uv'])
        for f in meshes[mn]['f']:
            all_f.append((mn, [i + base for i in f]))
    mesh.from_pydata(all_v, [], [f for _, f in all_f])
    for mn in mat_names:
        mesh.materials.append(bpy.data.materials.new(mn))
    for fi, (mn, _) in enumerate(all_f):
        mesh.polygons[fi].material_index = mat_names.index(mn)
    uv = mesh.uv_layers.new(name='UVMap')
    for fi in range(len(all_f)):
        for li in mesh.polygons[fi].loop_indices:
            uv.data[li].uv = all_uv[mesh.loops[li].vertex_index]

    obj = bpy.data.objects.new(object_name, mesh)
    bpy.context.collection.objects.link(obj)
    print('[sbsp] %s: %d verts, %d polys, %d materials (skipped: %s)'
          % (path, len(all_v), len(all_f), len(mat_names),
             {k: v for k, v in n_skip.items() if v}))
    return obj


def load_texture_into_material(name, tex_dir):
    """Assign <safe>.png from tex_dir to material <name>.

    Texture files are written by core/tools/source1_tex.py as
    <material path with '/' -> '_'>, lowercase + '.png'.
    """
    if not tex_dir:
        return
    tex_dir = os.path.abspath(tex_dir)
    cand = os.path.join(tex_dir, name.lower().replace('/', '_').replace('\\', '_') + '.png')
    if not os.path.exists(cand):
        return
    mat = bpy.data.materials.get(name)
    if not mat:
        return
    mat.use_nodes = True
    bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not bsdf:
        return
    img = bpy.data.images.load(cand, check_existing=True)
    tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex.image = img
    mat.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
