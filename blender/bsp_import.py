"""GoldSrc BSP (v29/30) importer for Blender: geometry, textures (embedded in
BSP or from WAD3), UV from texinfo, per-face lightmap colour.

Self-contained; used by replay_import.py.
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


# GoldSrc dface_t (v29/v30), 20 bytes:
#   planenum u16, side u16, firstedge i32, numedges u16, texinfo u16,
#   styles[4], lightofs i32
FACE_SIZE = 20


def safe_name(name):
    return ''.join(c if c.isalnum() or c in '_-' else '_' for c in name).strip() or 'tex'


def _mip_size(w, h):
    return w * h + (w // 2) * (h // 2) + (w // 4) * (h // 4) + (w // 8) * (h // 8)


def _decode_miptex(d, base, limit, name_hint=''):
    """Decode one GoldSrc miptex (BSP or WAD3 layout).

    Layout: name[16], width u32, height u32, offsets[4] u32, mip data,
    short numcolors (usually 256), numcolors * RGB palette.
    Returns dict with name/w/h/pixels/palette or None.
    """
    if base < 0 or base + 40 > limit or base + 40 > len(d):
        return None
    name = d[base:base + 16].split(b'\0')[0].decode('latin1', 'replace')
    if not name:
        name = name_hint
    w, h = _i32(d, base + 16), _i32(d, base + 20)
    if w <= 0 or h <= 0 or w > 4096 or h > 4096:
        return None
    mip0 = _u32(d, base + 24)
    if mip0 <= 0:
        return None
    mip = _mip_size(w, h)
    px = base + mip0
    if px + mip + 2 > limit or px + mip + 2 > len(d):
        return None
    numcolors = _u16(d, px + mip)
    if numcolors <= 0 or numcolors > 256:
        # some tools omit the colour count; fall back to a full palette
        pal_start = px + mip
        numcolors = 256
    else:
        pal_start = px + mip + 2
    if pal_start + numcolors * 3 > limit or pal_start + numcolors * 3 > len(d):
        return None
    return {
        'name': name,
        'w': w,
        'h': h,
        'pixels': d[px:px + w * h],
        'palette': d[pal_start:pal_start + numcolors * 3],
        'numcolors': numcolors,
    }


# ---------------------------------------------------------------- WAD3 index

_wad_cache = {}


def _read_wad(path):
    if path in _wad_cache:
        return _wad_cache[path]
    try:
        with open(path, 'rb') as f:
            d = f.read()
    except OSError:
        _wad_cache[path] = (None, None)
        return _wad_cache[path]
    if len(d) < 12 or d[:4] != b'WAD3':
        _wad_cache[path] = (None, None)
        return _wad_cache[path]
    count, ofs = struct.unpack_from('<ii', d, 4)
    index = {}
    for i in range(min(max(count, 0), 100000)):
        o = ofs + i * 32
        if o + 32 > len(d):
            break
        fp, disk_size, size = struct.unpack_from('<iii', d, o)
        typ = d[o + 12]
        name = d[o + 16:o + 32].split(b'\0')[0].decode('latin1', 'replace')
        if typ != 0x43 or fp <= 0 or size <= 0:  # 0x43 = miptex
            continue
        if fp + size > len(d):
            continue
        index.setdefault(name.lower(), (path, fp, size))
    _wad_cache[path] = (d, index)
    return _wad_cache[path]


def build_wad_index(bsp_path):
    """Scan <mod>/*.wad and <game>/valve/*.wad for miptex lumps."""
    maps_dir = os.path.dirname(os.path.abspath(bsp_path))
    mod_dir = os.path.dirname(maps_dir)
    game_dir = os.path.dirname(mod_dir)
    dirs = [mod_dir]
    valve = os.path.join(game_dir, 'valve')
    if os.path.isdir(valve) and os.path.normcase(valve) != os.path.normcase(mod_dir):
        dirs.append(valve)
    index = {}
    for d in dirs:
        try:
            names = sorted(os.listdir(d))
        except OSError:
            continue
        for fn in names:
            if not fn.lower().endswith('.wad'):
                continue
            wad, wi = _read_wad(os.path.join(d, fn))
            if not wi:
                continue
            for k, v in wi.items():
                index.setdefault(k, v)
    print(f'[bsp] wad index: {len(index)} textures from {len(dirs)} dirs')
    return index


def _lookup_wad(index, name):
    if not index:
        return None
    entry = index.get(name.lower())
    if not entry:
        return None
    path, fp, size = entry
    wad, _ = _read_wad(path)
    if wad is None:
        return None
    return _decode_miptex(wad, fp, fp + size, name_hint=name)


# ------------------------------------------------------------------- import

def import_bsp(path, object_name=None, tex_dir=None, game_dir=None):
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

    # ---- textures (miptex directory) ----
    tex_off, tex_len = lumps['textures']
    tex_end = tex_off + tex_len if tex_off else 0

    def cstr(o, n):
        return d[o:o + n].split(b'\0')[0].decode('latin1', 'replace')

    tex_count = _i32(d, tex_off) if tex_off else 0
    miptex = []
    for i in range(min(max(tex_count, 0), 4096)):
        if tex_off + 4 + i * 4 + 4 > len(d):
            break
        to = _i32(d, tex_off + 4 + i * 4)
        if to <= 0:
            miptex.append(None)
            continue
        base = tex_off + to
        if base + 40 > tex_end:
            miptex.append(None)
            continue
        name = cstr(base, 16)
        w, h = _i32(d, base + 16), _i32(d, base + 20)
        offs = [_i32(d, base + 24 + 4 * k) for k in range(4)]
        miptex.append({'name': name, 'w': w, 'h': h, 'base': base, 'offs': offs})

    # ---- geometry ----
    v_off = lumps['vertexes'][0]
    v_count = lumps['vertexes'][1] // 12
    verts = [(_f32(d, v_off + i * 12), _f32(d, v_off + i * 12 + 4), _f32(d, v_off + i * 12 + 8))
             for i in range(v_count)]

    ti_off = lumps['texinfo'][0]
    ti_count = lumps['texinfo'][1] // 40
    tis = []
    for i in range(ti_count):
        o = ti_off + i * 40
        vecs = [(_f32(d, o + k * 4), _f32(d, o + k * 4 + 4), _f32(d, o + k * 4 + 8), _f32(d, o + k * 4 + 12))
                for k in range(2)]
        miptex_idx = _i16(d, o + 32)
        tis.append({'vecs': vecs, 'miptex': miptex_idx})

    e_off = lumps['edges'][0]
    e_count = lumps['edges'][1] // 4
    se_off = lumps['surfedges'][0]
    se_count = lumps['surfedges'][1] // 4
    f_off = lumps['faces'][0]
    face_len = lumps['faces'][1]
    fsize = FACE_SIZE
    if face_len % fsize != 0:
        for cand in (28, 22, 26):
            if face_len % cand == 0:
                fsize = cand
                break
    f_count = face_len // fsize

    def edge_verts(i):
        if i < 0 or i >= se_count:
            return None
        e = _i32(d, se_off + i * 4)
        abs_e = abs(e)
        if abs_e >= e_count:
            return None
        off = e_off + abs_e * 4
        a = _u16(d, off)
        b = _u16(d, off + 2)
        return (a, b) if e > 0 else (b, a)

    def face_fields(o):
        if fsize == 20:
            firstedge = _i32(d, o + 4)
            numedges = _u16(d, o + 8)
            texinfo_idx = _i16(d, o + 10)
            lightofs = _i32(d, o + 16)
        elif fsize == 28:
            firstedge = _i32(d, o + 4)
            numedges = _u16(d, o + 8)
            texinfo_idx = _i16(d, o + 10)
            lightofs = _i32(d, o + 24)
        else:
            firstedge = _i32(d, o + 4)
            numedges = _u16(d, o + 8)
            texinfo_idx = _i16(d, o + 12)
            lightofs = -1
        return firstedge, numedges, texinfo_idx, lightofs

    # Lightmap lump: per-face RGB block.  Size in luxels depends on the texture.
    light_off, light_len = lumps['lighting']
    face_colors = {}

    meshes = {}  # material name -> {v: [], uv: [], f: [], face_ids: []}
    for i in range(f_count):
        o = f_off + i * fsize
        if o + fsize > len(d):
            break
        firstedge, numedges, texinfo_idx, lightofs = face_fields(o)
        if numedges < 3 or numedges > 64:
            continue
        if texinfo_idx < 0 or texinfo_idx >= len(tis):
            continue
        tv = tis[texinfo_idx]
        mt = miptex[tv['miptex']] if 0 <= tv['miptex'] < len(miptex) else None
        matname = mt['name'] if mt else 'missing'
        if matname.strip().lower() == 'sky':
            # engine renders sky faces from the skybox, not from the dummy
            # 16x16 miptex; skip them so the imported skybox shows through
            continue
        data = meshes.setdefault(matname, {'v': [], 'uv': [], 'f': [], 'face_ids': []})

        face_v = []
        for k in range(numedges):
            vi = edge_verts(firstedge + k)
            if vi is None:
                break
            face_v.append(vi[0])
        if len(face_v) != numedges or len(face_v) < 3:
            continue

        new_idx = []
        for vidx in face_v:
            if not (0 <= vidx < len(verts)):
                continue
            data['v'].append(verts[vidx])
            v = Vector(verts[vidx])
            svec, tvec = tv['vecs'][0], tv['vecs'][1]
            if mt and mt['w'] and mt['h']:
                s = (v.dot(Vector(svec[:3])) + svec[3]) / mt['w']
                t = (v.dot(Vector(tvec[:3])) + tvec[3]) / mt['h']
            else:
                s = t = 0.0
            # miptex row 0 is the top row; Blender UV v=0 is the bottom.
            data['uv'].append((s, 1.0 - t))
            new_idx.append(len(data['v']) - 1)
        if len(new_idx) >= 3:
            data['f'].append(new_idx)
            data['face_ids'].append(i)

        # Per-face lightmap colour (RGB average of the actual luxel block).
        if lightofs >= 0 and light_off and mt and mt['w'] > 0 and mt['h'] > 0:
            lw = mt['w'] // 16 + 1
            lh = mt['h'] // 16 + 1
            nbytes = lw * lh * 4
            base = light_off + lightofs
            block = d[base:base + nbytes]
            if len(block) >= 4:
                n = len(block) // 4
                r = sum(block[k * 4] for k in range(n)) / (255.0 * n)
                g = sum(block[k * 4 + 1] for k in range(n)) / (255.0 * n)
                b = sum(block[k * 4 + 2] for k in range(n)) / (255.0 * n)
                face_colors[i] = (r, g, b, 1.0)

    # ---- create mesh ----
    mesh = bpy.data.meshes.new((object_name or 'map') + '_mesh')
    all_v = []
    all_uv = []
    all_f = []
    all_face_ids = []
    mat_names = list(meshes.keys())
    for mn in mat_names:
        base_v = len(all_v)
        all_v.extend(meshes[mn]['v'])
        all_uv.extend(meshes[mn]['uv'])
        for f, fid in zip(meshes[mn]['f'], meshes[mn]['face_ids']):
            all_f.append((mn, [i + base_v for i in f]))
            all_face_ids.append(fid)
    mesh.from_pydata(all_v, [], [f for _, f in all_f])
    for mn in mat_names:
        mesh.materials.append(bpy.data.materials.new(mn))
    for fi, (mn, _) in enumerate(all_f):
        mesh.polygons[fi].material_index = mat_names.index(mn)

    uv = mesh.uv_layers.new(name='UVMap')
    for fi in range(len(all_f)):
        for li in mesh.polygons[fi].loop_indices:
            uv.data[li].uv = all_uv[mesh.loops[li].vertex_index]

    obj = bpy.data.objects.new(object_name or 'map', mesh)
    bpy.context.collection.objects.link(obj)

    # Per-face lightmap average -> vertex colours (vertices are duplicated per face).
    if face_colors:
        try:
            vcol = mesh.color_attributes.new('LM', 'FLOAT_COLOR', 'POINT')
            for fi, fid in enumerate(all_face_ids):
                col = face_colors.get(fid, (1.0, 1.0, 1.0, 1.0))
                for li in mesh.polygons[fi].loop_indices:
                    vcol.data[mesh.loops[li].vertex_index].color = col
            print('[bsp] lightmap vertex colours applied (faces:', len(face_colors), ')')
        except Exception as e:
            print('[bsp] lightmap step skipped:', e)

    print(f'[bsp] {object_name or path}: {len(all_v)} verts, {len(all_f)} polys, mats {len(mat_names)}')
    if tex_dir and tex_off:
        export_bsp_textures(d, tex_off, tex_len, tex_dir, bsp_path=path)
    return obj


def export_bsp_textures(data, tex_off, tex_len, out_dir, bsp_path=None):
    os.makedirs(out_dir, exist_ok=True)
    count = _i32(data, tex_off)
    tex_end = tex_off + tex_len
    wad_index = build_wad_index(bsp_path) if bsp_path else {}
    written = set()
    n = 0
    for i in range(min(max(count, 0), 4096)):
        to = _i32(data, tex_off + 4 + i * 4)
        if to <= 0 or tex_off + to + 40 > tex_end:
            continue
        base = tex_off + to
        name = data[base:base + 16].split(b'\0')[0].decode('latin1', 'replace')
        if name.strip().lower() == 'sky':
            continue  # dummy 16x16 placeholder, the skybox replaces it
        mip0 = _u32(data, base + 24)
        mt = None
        if mip0 > 0:
            mt = _decode_miptex(data, base, tex_end)
        if mt is None:
            mt = _lookup_wad(wad_index, name)
        if mt is None:
            continue
        key = mt['name'].lower()
        if key in written:
            continue
        written.add(key)
        path = os.path.join(out_dir, safe_name(mt['name']) + '.tga')
        _write_tga(path, mt)
        n += 1
    print(f'[bsp] textures -> {out_dir} ({n})')
    return n


def _write_tga(path, mt):
    w, h = mt['w'], mt['h']
    pal, px = mt['palette'], mt['pixels']
    ncol = len(pal) // 3
    with open(path, 'wb') as f:
        f.write(bytes([0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0]))
        f.write(struct.pack('<HH', w, h))
        f.write(bytes([24, 0x20]))  # 24-bit, top-left origin
        out = bytearray()
        for idx in px:
            if idx < ncol:
                out += bytes((pal[idx * 3 + 2], pal[idx * 3 + 1], pal[idx * 3]))
            else:
                out += b'\0\0\0'
        f.write(out)


# Remember the last BSP path so export_bsp_textures can find sibling WADs.
_current_bsp_path = ''


def _import_bsp_entry(path, object_name=None, tex_dir=None, game_dir=None):
    global _current_bsp_path
    _current_bsp_path = os.path.abspath(path)
    return import_bsp(path, object_name, tex_dir, game_dir)


def load_texture_into_material(name, tex_dir):
    """Find <safe_name>.tga near tex_dir and assign it to the material."""
    if not tex_dir:
        return
    tex_dir = os.path.abspath(tex_dir)
    cand = os.path.join(tex_dir, safe_name(name) + '.tga')
    if not os.path.exists(cand):
        cand = os.path.join(tex_dir, name + '.tga')
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
