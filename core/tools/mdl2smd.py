#!/usr/bin/env python3
"""GoldSrc MDL (studio v10) -> SMD decompiler: reference pose + per-sequence
animations + skin textures (TGA). Self-contained, format per Valve public/studio.h.

Output layout per model dir:
  <name>.smd             reference (mesh + bind pose + skeleton)
  seq/<label>.smd        per-sequence animation files
  <name>.tga             skin textures (first skin family)
  manifest.json          { "model":..., "sequences": [ {index,label,fps} ... ] }

Usage: python mdl2smd.py input.mdl [out_dir]
"""
import json
import os
import struct
import sys

# ---- struct helpers ----
def u32(d, off): return struct.unpack_from('<I', d, off)[0]
def i32(d, off): return struct.unpack_from('<i', d, off)[0]
def u16(d, off): return struct.unpack_from('<H', d, off)[0]
def i16(d, off): return struct.unpack_from('<h', d, off)[0]
def f32(d, off): return struct.unpack_from('<f', d, off)[0]
def cstr(d, off, n):
    raw = d[off:off+n]
    return raw.split(b'\0')[0].decode('latin1', 'replace')

HDR = 244  # studiohdr_t size (computed below)

def read_header(d):
    h = {}
    h['id'] = u32(d, 0)
    h['version'] = u32(d, 4)
    h['name'] = cstr(d, 8, 64)
    h['length'] = u32(d, 72)
    def vec(off):
        return (f32(d, off), f32(d, off+4), f32(d, off+8))
    h['eyeposition'] = vec(76)
    h['numbones'] = u32(d, 140)
    h['boneindex'] = u32(d, 144)
    h['numseq'] = u32(d, 164)
    h['seqindex'] = u32(d, 168)
    h['numseqgroups'] = u32(d, 172)
    h['seqgroupindex'] = u32(d, 176)
    h['numtextures'] = u32(d, 180)
    h['textureindex'] = u32(d, 184)
    h['texturedataindex'] = u32(d, 188)
    h['numskinref'] = u32(d, 192)
    h['numskinfamilies'] = u32(d, 196)
    h['skinindex'] = u32(d, 200)
    h['numbodyparts'] = u32(d, 204)
    h['bodypartindex'] = u32(d, 208)
    return h

def read_bones(d, h):
    bones = []
    for i in range(h['numbones']):
        off = h['boneindex'] + i * 112
        b = {
            'name': cstr(d, off, 32),
            'parent': i32(d, off + 32),
            'pos': (f32(d, off+56), f32(d, off+60), f32(d, off+64)),
        }
        # value[6] at off+56 (after bc[6] ints at 36..60)
        # correct: name32 + parent4 + flags4 + bc:6*4=24 => at 64..88: value[6]*4=24, scale:88..112
        b['pos'] = (f32(d, off + 64), f32(d, off + 68), f32(d, off + 72))
        bones.append(b)
    return bones

# label[32] + fps(4) flags(4) activity(4) actweight(4) numevents(4) eventindex(4)
# numframes(4) numpivots(4) pivotindex(4) motiontype(4) motionbone(4) linearmovement(12)
# automoveposindex(4) automoveangleindex(4) bbmin(12) bbmax(12) numblends(4) animindex(4)
# blendtype(2*4) blendstart(2*4) blendend(2*4) blendparent(4) seqgroup(4) entrynode(4)
# exitnode(4) nodeflags(4) nextseq(4)
SEQ_DESC = 176

def read_sequences(d, h):
    seqs = []
    for i in range(h['numseq']):
        off = h['seqindex'] + i * SEQ_DESC
        if off + SEQ_DESC > len(d):
            break
        s = {
            'label': cstr(d, off, 32),
            'fps': f32(d, off + 32),
            'flags': u32(d, off + 36),
            'numframes': u32(d, off + 56),
            'numblends': u32(d, off + 120),
            'animindex': u32(d, off + 124),
            'seqgroup': i32(d, off + 156),
            'loop': (u32(d, off + 36) & 1) == 1,
        }
        seqs.append(s)
    return seqs

def read_textures(d, h):
    tex = []
    for i in range(h['numtextures']):
        off = h['textureindex'] + i * 80
        t = {
            'name': cstr(d, off, 64),
            'width': u32(d, off + 72),
            'height': u32(d, off + 76),
            'index': u32(d, off + 76 + 0),
        }
        # name64 flags4 width4 height4 index4
        t['index'] = u32(d, off + 80 - 4)
        tex.append(t)
    return tex

def texdata(d, h, tex):
    """Return 24-bit RGB pixels per texture (full skin family 0)."""
    out = []
    for t in tex:
        # t.index is the raw palette-indexed pixels + palette, relative to texturedataindex
        base = h['texturedataindex'] + t['index']
        w, hgt = t['width'], t['height']
        if base + w * hgt + 768 > len(d) or w <= 0 or hgt <= 0:
            out.append(None)
            continue
        idx = d[base:base + w * hgt]
        pal = d[base + w * hgt: base + w * hgt + 768]
        rgb = bytearray()
        for c in idx:
            rgb += bytes((pal[c*3], pal[c*3+1], pal[c*3+2]))
        out.append(rgb)
    return out

def read_vert_data(d, h):
    """Collect all sub-models: vertices, tris with (bone, s, t), norms."""
    models = []
    for bi in range(h['numbodyparts']):
        boff = h['bodypartindex'] + bi * 76
        nummodels = u32(d, boff + 64)
        modeloff = u32(d, boff + 72)
        for mi in range(nummodels):
            moff = h['bodypartindex'] + bi * 76
            modelbase = moff  # base offsets are relative to whole file in v10
            modelbase = u32(d, boff + 72) if False else modeloff  # relative to bodypart? -> actually global
            # mstudiomodel_t fields:
            # name64 type4 boundingradius4 nummesh4 meshindex4 numverts4 vertinfoindex4
            # vertindex4 numnorms4 norminfoindex4 normindex4 numgroups4 groupindex4
            mo = modeloff
            nummesh = u32(d, mo + 72)
            meshindex = u32(d, mo + 76)
            numverts = u32(d, mo + 80)
            vertinfo = u32(d, mo + 84)
            vertindex = u32(d, mo + 88)
            numnorms = u32(d, mo + 92)
            norminfo = u32(d, mo + 96)
            normindex = u32(d, mo + 100)
            # v10 models store these indices either relative to model start
            # or absolute to file start; autodetect by bounds + plausibility
            def pick(idx, size):
                if idx + size <= len(d) and mo + idx + size > len(d):
                    return idx            # absolute
                if mo + idx + size <= len(d):
                    # try to guess: absolute if it points way outside model block
                    return idx if idx > mo else mo + idx
                return None
            vertbase = pick(vertindex, 12 * numverts)
            vertinfbase = pick(vertinfo, numverts)
            meshbase = pick(meshindex, 20 * nummesh)
            normbase = pick(normindex, 12 * numnorms)
            norminfbase = pick(norminfo, numnorms)
            if vertbase is None or vertinfbase is None or meshbase is None:
                continue  # malformed model, skip
            verts = []
            for v in range(numverts):
                vo = vertbase + v * 12
                bone = d[vertinfbase + v]
                verts.append((f32(d, vo), f32(d, vo+4), f32(d, vo+8), bone))
            norms = []
            for v in range(numnorms if normbase else 0):
                no = normbase + v * 12
                norms.append((f32(d, no), f32(d, no+4), f32(d, no+8)))
            tris = []
            for m in range(nummesh):
                moff2 = meshbase + m * 20
                numtris = u32(d, moff2)
                triindex = u32(d, moff2 + 4)
                skinref = u32(d, moff2 + 8)
                tribase = pick(triindex, numtris * 24)
                if tribase is None:
                    continue
                for t in range(numtris):
                    to = tribase + t * 24
                    tri = []
                    for k in range(3):
                        vo = to + k * 8
                        v_idx = u16(d, vo)
                        real_v = v_idx & 0x7FFF
                        n_idx = u16(d, vo + 2)
                        s = i16(d, vo + 4)
                        tt = i16(d, vo + 6)
                        tri.append((real_v, n_idx, s, tt))
                    tris.append((skinref, tri))
            models.append({
                'verts': verts, 'norms': norms, 'tris': tris,
                'numverts': numverts, 'numnorms': numnorms,
            })
    return models

def find_skin_texture(d, h, skinref):
    off = h['skinindex'] + skinref * 2
    return u16(d, off)

# ---- SMD emission ----
def write_smd_header(f):
    f.write('version 1\n')

def write_nodes(f, bones):
    f.write('nodes\n')
    for i, b in enumerate(bones):
        f.write('%d "%s" %d\n' % (i, b['name'], b['parent']))
    f.write('end\n')

def write_skeleton(f, bones, frame=0):
    f.write('skeleton\n')
    f.write('time %d\n' % frame)
    for i, b in enumerate(bones):
        x, y, z = b['pos']
        # SMD rot order: X Y Z in radians; GoldSrc rest = identity rotation
        f.write('%d %f %f %f 0.000000 0.000000 0.000000\n' % (i, x, y, z))
    f.write('end\n')

def write_triangles(f, models, tex_widths=None):
    f.write('triangles\n')
    texname = 'model'
    for m in models:
        for skinref, tri in m['tris']:
            # material name by skinref -> texture name
            f.write('%s\n' % texname)
            for (v_idx, n_idx, s, tt) in tri:
                v = m['verts'][v_idx]
                we = tex_widths[skinref] if tex_widths and skinref < len(tex_widths) else 1.0
                f.write('%d %f %f %f %f %f %f %f\n' % (
                    0, v[0], v[1], v[2], 0.0, 0.0, 0.0, float(s) / we)) if False else None
        # simpler: per-triangle with real uv
    f.write('end\n')

def write_anim(f, bones, frames):
    f.write('skeleton\n')
    for i, fr in enumerate(frames):
        f.write('time %d\n' % i)
        for bi, b in enumerate(bones):
            if bi < len(fr):
                bone = fr[bi]
            else:
                bone = b['pos']
            f.write('%d %f %f %f %f %f %f\n' % (bi, bone[0], bone[1], bone[2], 0, 0, 0))
    f.write('end\n')

def read_anim_stream(d, start, count, base_rest):
    """Decode mstudioanimvalue stream into `count` values (short, radians/units)."""
    vals = []
    p = start
    last = base_rest
    while len(vals) < count and 0 <= p and p + 2 <= len(d):
        tag = u16(d, p); p += 2
        valid = tag & 0xFF
        total = (tag >> 8) & 0xFF
        if valid == 0:
            vals.extend([last] * (count - len(vals)))
            break
        if valid == 1:
            if p + 2 > len(d):
                break
            val = i16(d, p); p += 2
            n = total if total > 0 else 1
            for _ in range(n):
                vals.append(val)
            last = val
        else:
            for _ in range(valid):
                if p + 2 > len(d):
                    break
                val = i16(d, p); p += 2
                vals.append(val)
                last = val
    return vals[:count]

def extract_anim(d, h, seq, bones):
    """Return list of frames; each frame: per-bone 6-axis values (rot radians)."""
    if seq['seqgroup'] != 0 or seq['animindex'] == 0 or seq['numframes'] == 0:
        return None
    animbase = seq['animindex']
    nframes = seq['numframes']
    numbones = h['numbones']
    frames = []
    rest = [0.0] * 6
    for f in range(nframes):
        frame_vals = []
        for b in range(numbones):
            panim = animbase + ((f * numbones) + b) * 12
            if panim + 12 > len(d):
                frame_vals.append(list(rest))
                continue
            offs = [i16(d, panim + x * 2) for x in range(6)]
            ax_vals = []
            for ax in range(6):
                off = offs[ax]
                if off == 0:
                    ax_vals.append(rest[ax])
                else:
                    p = panim + off
                    vs = read_anim_stream(d, p, nframes, rest[ax])
                    ax_vals.append(vs[f] if f < len(vs) else rest[ax])
            frame_vals.append(ax_vals)
        frames.append(frame_vals)
    return frames

def write_anim_file(d, h, seq, index, bones, out_dir):
    frames = extract_anim(d, h, seq, bones)
    if frames is None:
        return None
    safe = ''.join(c if c.isalnum() or c in '_-' else '_' for c in seq['label']).strip() or ('seq_%03d' % index)
    path = os.path.join(out_dir, 'seq', safe + '.smd')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write('version 1\n')
        f.write('nodes\n')
        for i, b in enumerate(bones):
            f.write('%d "%s" %d\n' % (i, b['name'], b['parent']))
        f.write('end\n')
        f.write('skeleton\n')
        for fno, fr in enumerate(frames):
            f.write('time %d\n' % fno)
            for bi, b in enumerate(bones):
                if bi < len(fr):
                    ax = fr[bi]
                    pos = b['pos']
                    # GoldSrc stores rotations in fixed-point: 32768 == 2pi
                    f.write('%d %f %f %f %f %f %f\n' % (bi,
                        pos[0] + ax[0], pos[1] + ax[1], pos[2] + ax[2],
                        ax[3] * 3.14159265 / 32768.0,
                        ax[4] * 3.14159265 / 32768.0,
                        ax[5] * 3.14159265 / 32768.0))
                else:
                    f.write('%d %f %f %f 0.000000 0.000000 0.000000\n' % (bi, b['pos'][0], b['pos'][1], b['pos'][2]))
        f.write('end\n')
    return path

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    mdl = open(sys.argv[1], 'rb').read()
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(sys.argv[1])[0] + '_smd'
    os.makedirs(out_dir, exist_ok=True)
    h = read_header(mdl)
    print('id=%08x version=%d name=%s bones=%d seq=%d tex=%d' % (
        h['id'], h['version'], h['name'], h['numbones'], h['numseq'], h['numtextures']))
    bones = read_bones(mdl, h)
    seqs = read_sequences(mdl, h)
    tex = read_textures(mdl, h)
    models = read_vert_data(mdl, h)
    model_name = os.path.basename(out_dir)

    manifest = {'model': h['name'], 'sequences': []}

    # reference smd
    ref_path = os.path.join(out_dir, model_name + '_reference.smd')
    with open(ref_path, 'w') as f:
        write_smd_header(f)
        write_nodes(f, bones)
        write_skeleton(f, bones, 0)
        f.write('triangles\n')
        bad = 0
        for mi, m in enumerate(models):
            for skinref, tri in m['tris']:
                tname = 'skin_%d' % skinref
                f.write('%s\n' % tname)
                for (v_idx, n_idx, s, tt) in tri:
                    if v_idx >= len(m['verts']):
                        bad += 1
                        continue
                    v = m['verts'][v_idx]
                    f.write('0 %f %f %f %f %f %f %f\n' % (v[0], v[1], v[2],
                                                            -1, -1, -1, s))
        f.write('end\n')
        print('skipped bad vert indices:', bad)
    print('reference:', ref_path)

    # textures -> tga
    data = texdata(mdl, h, tex)
    for i, t in enumerate(tex):
        if data[i] is None:
            continue
        tga = os.path.join(out_dir, t['name'] + '.tga')
        with open(tga, 'wb') as f:
            f.write(bytes([0,0,2,0,0,0,0,0,0,0,0,0]))
            f.write(struct.pack('<HH', t['width'], t['height']))
            f.write(bytes([24, 0x20]))
            # flip vertically (SMD v origin bottom-left; keep simple)
            px = data[i]
            rows = [px[r*t['width']:(r+1)*t['width']] for r in range(t['height'])]
            for r in reversed(rows):
                # convert RGB -> BGR
                for x in range(0, len(r), 3):
                    f.write(bytes((r[x+2], r[x+1], r[x])))
    # anims: reference-only skeleton (no per-frame extraction here if anim parser
    # isn't ready; animate via demo sequence/frame later using bones linear interp)
    seq_names = []
    seq_files = {}
    for i, s in enumerate(seqs):
        p = write_anim_file(mdl, h, s, i, bones, out_dir)
        if p:
            seq_files[i] = os.path.basename(p)
        seq_names.append(s['label'])
        manifest['sequences'].append({'index': i, 'label': s['label'], 'fps': s['fps'],
                                      'frames': s['numframes'], 'loop': s['loop'],
                                      'blends': s['numblends'], 'file': seq_files.get(i, '')})
    with open(os.path.join(out_dir, 'manifest.json'), 'w') as f:
        json.dump(manifest, f, indent=1)
    print('sequences:', seq_names[:20])
    print('ok:', out_dir)
    return 0

if __name__ == '__main__':
    sys.exit(main())
