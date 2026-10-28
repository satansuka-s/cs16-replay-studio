"""GoldSrc BSP (v29/30) importer for Blender: geometry, textures (from BSP lump),
UV from texinfo. Self-contained; used by replay_import.py.
"""
import bpy
import math
import os
import struct
from mathutils import Vector


def _u32(d, o): return struct.unpack_from('<I', d, o)[0]
def _i32(d, o): return struct.unpack_from('<i', d, o)[0]
def _i16(d, o): return struct.unpack_from('<h', d, o)[0]
def _u16(d, o): return struct.unpack_from('<H', d, o)[0]
def _f32(d, o): return struct.unpack_from('<f', d, o)[0]


def import_bsp(path, object_name=None, tex_dir=None):
    d = open(path, 'rb').read()
    version = _i32(d, 0)
    if version not in (29, 30):
        print(f'[bsp] unsupported version {version}')
        return None
    lumps = {}
    names = ['entities', 'planes', 'textures', 'vertexes', 'visibility', 'nodes',
             'texinfo', 'faces', 'lighting', 'clipnodes', 'leaves', 'marksurfaces',
             'edges', 'surfedges', 'models', 'cubemaps']
    for i, nm in enumerate(names):
        o = 4 + i * 8
        lumps[nm] = (_i32(d, o), _i32(d, o + 4))

    # ---- textures (miptex) ----
    tex_off, tex_len = lumps['textures']
    def cstr(o, n):
        raw = d[o:o+n]
        return raw.split(b'\0')[0].decode('latin1', 'replace')
    tex_count = _i32(d, tex_off) if tex_off else 0
    texinfo = []
    for i in range(min(tex_count, 2048)):
        if tex_off + 4 + i * 4 + 4 > len(d):
            break
        to = _i32(d, tex_off + 4 + i * 4)
        if to <= 0:
            texinfo.append(None)
            continue
        base = tex_off + to
        name = cstr(base, 16) if base + 16 <= len(d) else 'tex%d' % i
        w, h = 0, 0
        if base + 36 <= len(d):
            w, h = _i32(d, base + 16), _i32(d, base + 20)
        texinfo.append({'name': name, 'w': w, 'h': h, 'base': base})

    # ---- geometry ----
    v_off = lumps['vertexes'][0]
    v_count = lumps['vertexes'][1] // 12
    verts = [(_f32(d, v_off + i*12), _f32(d, v_off + i*12+4), _f32(d, v_off + i*12+8))
             for i in range(v_count)]

    ti_off = lumps['texinfo'][0]
    ti_count = lumps['texinfo'][1] // 40
    tis = []
    for i in range(ti_count):
        o = ti_off + i * 40
        vecs = [(_f32(d, o + k*4), _f32(d, o + k*4 + 4), _f32(d, o + k*4 + 8), _f32(d, o + k*4 + 12)) for k in range(2)]
        miptex = _i16(d, o + 32)
        tis.append({'vecs': vecs, 'miptex': miptex})

    e_off = lumps['edges'][0]
    se_off = lumps['surfedges'][0]
    f_off = lumps['faces'][0]

    def edge_verts(i):
        """Return pair of vertex indices for edge i (absolute index)."""
        e = _i32(d, se_off + i * 4)
        abs_e = abs(e)
        off = e_off + (abs_e - 1) * 4
        a = _u16(d, off)
        b = _u16(d, off + 2)
        return (b, a) if e < 0 else (a, b)  # winding flip for negative

    if len(lumps['faces']) >= 2 and lumps['faces'][1] % 20 == 0:
        fsize = 20
        f_count = lumps['faces'][1] // fsize
    elif lumps['faces'][1] % 22 == 0:
        fsize = 22
        f_count = lumps['faces'][1] // fsize
    elif lumps['faces'][1] % 28 == 0:
        fsize = 28
        f_count = lumps['faces'][1] // fsize
    else:
        f_count = lumps['faces'][1] // 26
        fsize = 26
    meshes = {}  # material name -> {v: [], uv: [], faces: []}
    used = 0
    for i in range(f_count):
        o = f_off + i * fsize
        if o + fsize > len(d):
            break
        if fsize in (20, 28):
            side = _i32(d, o + 4)
            firstedge = _i32(d, o + 8)
            numedges = _i32(d, o + 12)
            texinfo_idx = _u16(d, o + 16)
        else:
            side = d[o + 2]
            firstedge = _i32(d, o + 4)
            numedges = _i32(d, o + 8)
            texinfo_idx = _i16(d, o + 12)
        if numedges <= 0 or numedges > 64:
            continue
        if texinfo_idx < 0 or texinfo_idx >= len(tis):
            continue
        tv = tis[texinfo_idx]
        mt = texinfo[tv['miptex']] if 0 <= tv['miptex'] < len(texinfo) else None
        matname = mt['name'] if mt else 'missing'
        data = meshes.setdefault(matname, {'v': [], 'uv': [], 'f': []})
        loop = []
        for k in range(numedges):
            vi = edge_verts(firstedge + k)
            for idx in (vi if side == 0 else (vi[1], vi[0])):
                pass
            # choose vertex by winding
            idx = vi[0] if side == 0 else vi[1]
            loop.append((firstedge + k, idx)) if False else None
            if k == 0:
                pass
        # build polygon: order all vertices
        face_v = []
        for k in range(numedges):
            vi = edge_verts(firstedge + k)
            idx = vi[0] if side == 0 else vi[1]
            face_v.append(idx)
        if len(face_v) < 3:
            continue
        new_idx = []
        for vidx in face_v:
            if 0 <= vidx < len(verts):
                data['v'].append(verts[vidx])
                # uv from texinfo
                v = Vector(verts[vidx])
                svec, tvec = tv['vecs'][0], tv['vecs'][1]
                if mt and mt['w'] and mt['h']:
                    s = (v.dot(Vector(svec[:3])) + svec[3]) / mt['w']
                    t = (v.dot(Vector(tvec[:3])) + tvec[3]) / mt['h']
                else:
                    s = t = 0.0
                data['uv'].append((s, 1.0 - t))
                new_idx.append(len(data['v']) - 1)
            else:
                new_idx.append(0)
        data['f'].append(new_idx)
        used += 1

    # ---- lighting: per-face lightmap average (lump 8) -> vertex colors ----
    light_off, light_len = lumps['lighting']

    def i32_at(fsize, o):
        off = o + 20 if fsize == 20 else o + 24
        return _i32(d, off)

    face_lights = {}
    for i in range(f_count):
        o = f_off + i * fsize
        if o + fsize + 4 > len(d):
            break
        # lightofs lives at face offset 20 for 20-byte faces (HL style) or 24 for 28-byte
        lo = i32_at(fsize, o)
        if lo >= 0 and lo + 16 <= light_len and light_off:
            face_lights[i] = lo

    # average one 16x16 (or smaller) lightmap block per face
    avg = {}
    for i, lo in face_lights.items():
        base = light_off + lo
        block = d[base:base + 256]
        if len(block) < 256:
            block = d[base:base + 128] + bytes(128)
        s = sum(block) / 256.0
        avg[i] = s / 255.0  # 0..1 brightness
    # apply to polygon vertex colors after mesh creation
    avg = {}

    # ---- create mesh ----
    mesh = bpy.data.meshes.new((object_name or 'map') + '_mesh')
    all_v = []
    all_uv = []
    all_f = []
    mat_names = list(meshes.keys())
    for mn in mat_names:
        base_v = len(all_v)
        all_v.extend(meshes[mn]['v'])
        all_uv.extend(meshes[mn]['uv'])
        for f in meshes[mn]['f']:
            all_f.append((mn, [i + base_v for i in f]))
    mesh.from_pydata(all_v, [], [f for _, f in all_f])
    for mn in mat_names:
        mesh.materials.append(bpy.data.materials.new(mn))
    for fi, (mn, _) in enumerate(all_f):
        mesh.polygons[fi].material_index = mat_names.index(mn)
    uv = mesh.uv_layers.new(name='UVMap')
    for fi, (_, f) in enumerate(all_f):
        plen = len(f)
        for k, vidx in enumerate(f):
            uv.data[mesh.loops[fi * plen + k]].uv = all_uv[vidx]
    obj = bpy.data.objects.new(object_name or 'map', mesh)
    bpy.context.collection.objects.link(obj)
    # apply per-face lightmap average to vertex colors (LM attr)
    if avg:
        try:
            vcol = mesh.color_attributes.new('LM', 'POINT', 'FLOAT_COLOR')
            used_face = 0
            for i in range(f_count):
                o = f_off + i * fsize
                if o + fsize > len(d):
                    break
                if i in face_lights and used_face < len(mesh.polygons):
                    for loop in mesh.polygons[used_face].loop_indices:
                        vcol.data[mesh.loops[loop].vertex_index].color = (
                            avg[i], avg[i], avg[i], 1.0)
                used_face += 1
            print('[bsp] lightmap vertex colors applied (faces:', len(face_lights), ')')
        except Exception as e:
            print('[bsp] lightmap step skipped:', e)
    print(f'[bsp] {object_name or path}: {len(all_v)} verts, {len(all_f)} polys, mats {mat_names[:8]}')
    if tex_dir and tex_off:
        export_bsp_textures(d, tex_off, tex_len, tex_dir)
    return obj


def export_bsp_textures(data, tex_off, tex_len, out_dir):
    import os as _os
    _os.makedirs(out_dir, exist_ok=True)
    def u32(o): return struct.unpack_from('<I', data, o)[0]
    count = u32(tex_off)
    n = 0
    for i in range(min(count, 4096)):
        to = u32(tex_off + 4 + i * 4)
        if to <= 0 or tex_off + to + 40 > tex_off + tex_len:
            continue
        base = tex_off + to
        name = data[base:base+16].split(b'\0')[0].decode('latin1', 'replace')
        w, h = struct.unpack_from('<II', data, base + 16)
        if w <= 0 or h > 1024 or base + 32 + 4 > tex_off + tex_len:
            continue
        mip0 = struct.unpack_from('<I', data, base + 32)[0]
        px = base + mip0
        if px + w * h + 768 > tex_off + tex_len:
            continue
        pal = data[px + w*h + (w//2)*(h//2) + (w//4)*(h//4) + (w//8)*(h//8):
                   px + w*h + (w//2)*(h//2) + (w//4)*(h//4) + (w//8)*(h//8) + 768]
        idx = data[px:px + w*h]
        safe = ''.join(c if c.isalnum() or c in '_-' else '_' for c in name).strip() or 'tex%d' % i
        path = _os.path.join(out_dir, safe + '.tga')
        with open(path, 'wb') as f:
            f.write(bytes([0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0]))
            f.write(struct.pack('<HH', w, h))
            f.write(bytes([24, 0x20]))
            for r in range(h):
                row = idx[r*w:(r+1)*w]
                for c in reversed(row):
                    rr, gg, bb = pal[c*3], pal[c*3+1], pal[c*3+2]
                    f.write(bytes((bb, gg, rr)))
        n += 1
    print(f'[bsp] textures -> {out_dir} ({n})')
    return n


def load_texture_into_material(name, tex_dir):
    """Find name.tga / name_tga.jpg near tex_dir and assign to the material."""
    if not tex_dir:
        return
    cand = os.path.join(tex_dir, name + '.tga')
    if not os.path.exists(cand):
        cand = os.path.join(tex_dir, name + '.jpg')
    if not os.path.exists(cand):
        return
    mat = bpy.data.materials.get(name)
    if not mat:
        return
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    img = bpy.data.images.load(cand)
    tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex.image = img
    mat.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
