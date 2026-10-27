#!/usr/bin/env python3
"""Extract textures from a Half-Life/GoldSrc BSP (v29/v30) into TGA files.
Lump 2 = TEXTURES (miptex entries, 8-bit paletted). Useful for custom maps where
the importer cannot read embedded textures.

Usage: python bsp_tex_extract.py map.bsp [out_dir]
"""
import os
import struct
import sys

def r32(b, o):
    return struct.unpack_from('<I', b, o)[0]

def write_tga(path, w, h, pal, pixels):
    # uncompressed 8-bit indexed TGA (palette as 24-bit BGR)
    with open(path, 'wb') as f:
        f.write(bytes([0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0]))
        f.write(struct.pack('<HH', w & 0xFFFF, h & 0xFFFF))
        f.write(bytes([8, 0x20]))
        f.write(bytes(pixels))
        f.close()

def write_tga24(path, w, h, pal, pixels):
    # uncompressed 24-bit (normalize palette to full color)
    with open(path, 'wb') as f:
        f.write(bytes([0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0]))
        f.write(struct.pack('<HH', w & 0xFFFF, h & 0xFFFF))
        f.write(bytes([24, 0x20]))
        out = bytearray()
        for idx in pixels:
            r, g, b = pal[idx * 3], pal[idx * 3 + 1], pal[idx * 3 + 2]
            out += bytes((b, g, r))  # TGA stores BGR
        f.write(bytes(out))
        f.close()

def main():
    path = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(path)[0] + "_tex"
    os.makedirs(out_dir, exist_ok=True)
    data = open(path, 'rb').read()
    # BSP v29/30: 17 lumps
    lump_off = [r32(data, 8 + i * 8) for i in range(17)]
    lump_len = [r32(data, 12 + i * 8) for i in range(17)]
    tex_off, tex_len = lump_off[2], lump_len[2]
    if tex_len < 4:
        print('no texture lump'); return 1
    count = r32(data, tex_off)
    print(f'texture lump: offset={tex_off} size={tex_len} count={count}')
    entries = []
    pos = tex_off + 4
    for i in range(min(count, 4096)):
        off = r32(data, pos); pos += 4
        entries.append(off)
    if count == 0:
        # some maps store textures differently: try lump 14 (sentient?) / warn
        print('warning: texture lump empty; try wad_extract.py on companion .wad files')
    n = 0
    for off in entries:
        if off == -1 or off == 0 or off + 2 + 2 + 4 + 4 > tex_off + tex_len:
            continue
        try:
            name = data[tex_off + off:tex_off + off + 16].split(b'\0')[0].decode('latin1')
            w, h = struct.unpack_from('<II', data, tex_off + off + 16)
            if w <= 0 or w > 1024 or h <= 0 or h > 1024:
                continue
            mip0_off = struct.unpack_from('<I', data, tex_off + off + 32)[0]
            base = tex_off + off + mip0_off
            if base + w * h > tex_off + tex_len:
                continue
            pal_off = base + w * h + (w // 2) * (h // 2) + (w // 4) * (h // 4) + (w // 8) * (h // 8)
            if pal_off + 768 > tex_off + tex_len:
                continue
            pal = data[pal_off:pal_off + 768]
            pixels = data[base:base + w * h]
            safe = ''.join(c if c.isalnum() or c in '_-' else '_' for c in name).strip()
            if not safe:
                safe = f'tex_{n}'
            write_tga24(os.path.join(out_dir, safe + '.tga'), w, h, pal, pixels)
            n += 1
        except Exception:
            continue
    print(f'{path}: exported {n} textures to {out_dir}')

if __name__ == '__main__':
    sys.exit(main())
