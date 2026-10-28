#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""source1_tex: extract map textures (materials/VMT + VTF) for Source 1 BSPs.

Reads CS:GO / CS:S (and other Source 1) .bsp files, resolves each face
material to its VMT ($basetexture), decodes the VTF and writes PNG files into
out_dir.  Texture sources, in order:

  1. the BSP's own pak lump (LUMP_PAK, a zip) - map-local materials,
  2. the game's pak01_dir.vpk (+ pak01_NNN.vpk archives) - shared materials.

VTF decoding uses the vendor-neutral pure-python decoder (DXT1/3/5 + 8888
formats) - no external tools needed.

Usage:
  python core/tools/source1_tex.py de_dust2.bsp --game "D:\\...\\csgo" --out map_tex
"""
import os
import re
import struct
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# preferred: SourceIO native VPK reader (MIT, REDxEYE) - robust on CS:GO
# pak01_dir.vpk trees; falls back to the pure-python parser.
_NATIVE_VPK = False
try:
    import pylib as _pylib  # noqa: E402  (pylib.pyd next to this file)
    if hasattr(_pylib, 'VPKFile'):
        VPK = _pylib.VPKFile
        _NATIVE_VPK = True
except Exception as _vpke:
    print('[tex] native pylib unavailable (%s); using pure-python VPK' % _vpke,
          file=sys.stderr)
if not _NATIVE_VPK:
    from vpk import VPK  # noqa: E402  (pure-python fallback)
from vtf_decode import decode_vtf  # noqa: E402

LUMP_ENTITIES = 0
LUMP_TEXDATA = 2
LUMP_TEXINFO = 6
LUMP_FACES = 7
LUMP_TEXDATA_STRING_DATA = 43
LUMP_TEXDATA_STRING_TABLE = 44
LUMP_PAK = 40


def safe_name(name):
    return re.sub(r'[^0-9A-Za-z_\-./]', '_', name).strip('/')


def _ls(lumps, i):
    o, s = lumps[i][0], lumps[i][1]
    return o, s


def read_strings(d, lumps):
    """Return list of names from TEXDATA_STRING_DATA/TABLE lumps."""
    so, ss = _ls(lumps, LUMP_TEXDATA_STRING_DATA)
    to, ts = _ls(lumps, LUMP_TEXDATA_STRING_TABLE)
    sdata = d[so:so + ss]
    stable = d[to:to + ts]
    count = ts // 2
    offs = struct.unpack_from('<%dH' % count, stable, 0) if count else ()
    names = []
    for o in offs:
        if o >= len(sdata):
            names.append('')
            continue
        names.append(sdata[o:].split(b'\0')[0].decode('latin1', 'replace'))
    return names


def read_texdata_materials(d, lumps, names):
    """texdata lump (32-byte records) -> list of (name, w, h)."""
    to, ts = _ls(lumps, LUMP_TEXDATA)
    out = []
    for i in range(ts // 32):
        b = d[to + i * 32:to + i * 32 + 32]
        if len(b) < 32:
            break
        name_id, w, h = struct.unpack_from('<iII', b, 12)
        nm = names[name_id] if 0 <= name_id < len(names) else ''
        out.append((nm, w, h))
    return out


def parse_vmt(text):
    """Tiny VMT parser: returns dict of key->value, honoring $patch blocks."""
    keys = {}
    # kill comments and normalize
    text = re.sub(r'//[^\n]*', '', text)
    for m in re.finditer(r'"([^"]+)"\s+"([^"]*)"', text):
        k = m.group(1).lower()
        keys.setdefault(k, m.group(2))
    return keys


class MapTex:
    def __init__(self, bsp_path, game_dir):
        self.bsp_path = bsp_path
        self.game_dir = game_dir
        self.d = open(bsp_path, 'rb').read()
        self.lumps = []
        for i in range(64):
            o, s, v, dsz = struct.unpack_from('<iiII', self.d, 8 + i * 16)
            self.lumps.append((o, s, v, dsz))
        self.names = read_strings(self.d, self.lumps)
        self.materials = read_texdata_materials(self.d, self.lumps, self.names)
        self.vpk = None
        self.pak_zip = None
        po, ps = _ls(self.lumps, LUMP_PAK)
        if ps:
            try:
                self.pak_zip = zipfile.ZipFile(io.BytesIO(self.d[po:po + ps]))
            except Exception:
                self.pak_zip = None
        # locate game vpk
        for mod in ('csgo', 'cstrike'):
            vp = os.path.join(game_dir, mod, 'pak01_dir.vpk')
            if os.path.exists(vp):
                try:
                    if _NATIVE_VPK:
                        self.vpk = VPK(vp)
                    else:
                        self.vpk = VPK(vp)
                except Exception:
                    self.vpk = None
                break

    def read_material_file(self, rel):
        """'materials/xxx.vmt' / .vtf from pak or vpk."""
        rel = rel.replace('\\', '/').lstrip('/').lower()
        if self.pak_zip:
            for cand in (rel, rel.replace('.vmt', '.vtf'), rel[:-4]):
                try:
                    if cand in self.pak_zip.namelist() or \
                       cand + ('.vmt' if cand.endswith('vmt') else '') in self.pak_zip.namelist():
                        return self.pak_zip.read(cand)
                except Exception:
                    pass
        if self.vpk:
            if _NATIVE_VPK:
                return self.vpk.find_file(rel)
            return self.vpk.read(rel)
        return None

    def material_texture(self, mat_name):
        """Given a texdata material name, return (basetexture_name, vml_path)
        using VMT resolution looking first in the map pak, then the VPK."""
        low = mat_name.lower()
        if low.startswith('tools/') or low.startswith('!'):
            return None
        tries = [
            'materials/%s.vmt' % low,
        ]
        base = None
        for cand in tries:
            text = self.read_material_file(cand)
            if text is None:
                continue
            if isinstance(text, bytes):
                text = text.decode('latin1', 'replace')
            kv = parse_vmt(text)
            base = kv.get('$basetexture') or kv.get('$basetexture2') or kv.get('$baseTexture')
            if base:
                base = base.lower()
                break
            # patch materials may only redeclare; try the include
            inc = kv.get('$include') or kv.get('include')
            if inc:
                text2 = self.read_material_file('materials/%s.vmt' % inc.lower())
                if text2:
                    kv2 = parse_vmt(text2.decode('latin1', 'replace'))
                    base = kv2.get('$basetexture') or kv2.get('$basetexture2')
                    if base:
                        base = base.lower()
                        break
        if base:
            return base.lower()
        # direct vtf guess
        return low

    def extract_all(self, out_dir):
        done = {}
        skips = 0
        for nm, w, h in self.materials:
            if not nm:
                continue
            key = nm.lower()
            if key in done or key.startswith('tools/'):
                skips += 1
                continue
            base = self.material_texture(nm)
            vtf = None
            if base:
                vtf = self.read_material_file('materials/%s.vtf' % base)
            if vtf is None:
                skips += 1
                continue
            try:
                if _NATIVE_VPK:
                    px, pw, ph, _isf = _pylib.vtf.load_vtf_texture(vtf, 0, 0, 0)
                    if not px or not pw or not ph:
                        raise ValueError('empty decode')
                    rgba = bytes(px)
                else:
                    pw, ph, rgba = decode_vtf(vtf, 0)
            except Exception as e:
                print('[tex] decode failed %s (%s)' % (nm, e), file=sys.stderr)
                skips += 1
                continue
            fn = safe_name(key.replace('/', '_')) + '.png'
            path = os.path.join(out_dir, fn)
            write_png(path, pw, ph, rgba)
            done[key] = fn
        print('[tex] %d textures -> %s (%d skipped)' % (len(done), out_dir, skips))
        return done


def write_png(path, w, h, rgba):
    import zlib
    def chunk(t, data):
        return struct.pack('>I', len(data)) + t + data + \
            struct.pack('>I', zlib.crc32(t + data) & 0xffffffff)
    raw = b''.join(b'\x00' + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))
    hdr = struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', hdr) +
                chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def main():
    import argparse
    import io  # noqa: F401 (used in class)
    p = argparse.ArgumentParser()
    p.add_argument('bsp')
    p.add_argument('--game', default='')
    p.add_argument('--out', default='map_tex')
    a = p.parse_args()
    if not a.game:
        for cand in (r'D:\SteamLibrary\steamapps\common\csgo legacy',
                     r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Source',
                     r'C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive'):
            if os.path.exists(os.path.join(cand, 'csgo')):
                a.game = cand
                break
    os.makedirs(a.out, exist_ok=True)
    mt = MapTex(a.bsp, a.game)
    mt.extract_all(a.out)
    # skyname from worldspawn
    d = mt.d
    eo, es = _ls(mt.lumps, LUMP_ENTITIES)
    ent = d[eo:eo + es].decode('latin1', 'replace')
    m = re.search(r'"skyname"\s+"([^"]+)"', ent, re.I)
    if m:
        print('[tex] skyname', m.group(1))


if __name__ == '__main__':
    main()
