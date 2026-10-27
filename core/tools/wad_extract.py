#!/usr/bin/env python3
"""Extract textures from WAD2/WAD3 files (Half-Life/GoldSrc) into TGA (24-bit).
WADs are used by (custom) maps for their textures.

Usage: python wad_extract.py textures.wad [out_dir]
"""
import os
import struct
import sys


def main():
    path = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(path)[0] + "_wad"
    os.makedirs(out_dir, exist_ok=True)
    data = open(path, 'rb').read()
    magic = data[:4]
    if magic not in (b'WAD2', b'WAD3'):
        print('not a WAD2/WAD3 file')
        return 1
    count, dir_off = struct.unpack_from('<II', data, 4)
    n = 0
    for i in range(count):
        off = dir_off + i * 32
        if off + 32 > len(data):
            break
        # entry: {int32 offset; int32 size; int32 pad; int32 type; char name[16]}
        lump_off, lump_size, _pad, lump_type, name = struct.unpack_from('<IIII16s', data, off)
        name = name.split(b'\0')[0].decode('latin1')
        if lump_type not in (0x40, 0x43, 0x44):  # miptex variants
            continue
        if lump_off + 40 > len(data):
            continue
        w, h = struct.unpack_from('<II', data, lump_off + 16)
        if w <= 0 or w > 1024 or h <= 0 or h > 1024:
            continue
        # mip data follows the 40-byte header; palette (768 bytes) after 4 mips
        data_start = lump_off + 40
        mip_total = w * h + (w // 2) * (h // 2) + (w // 4) * (h // 4) + (w // 8) * (h // 8)
        pal_off = data_start + mip_total
        if pal_off + 768 > len(data):
            continue
        pal = data[pal_off:pal_off + 768]
        pixels = data[data_start:data_start + w * h]
        safe = ''.join(c if c.isalnum() or c in '_-' else '_' for c in name).strip()
        if not safe:
            safe = f'tex_{n}'
        out = bytearray()
        for idx in pixels:
            r, g, b = pal[idx * 3], pal[idx * 3 + 1], pal[idx * 3 + 2]
            out += bytes((b, g, r))
        with open(os.path.join(out_dir, safe + '.tga'), 'wb') as f:
            f.write(bytes([0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0]))
            f.write(struct.pack('<HH', w & 0xFFFF, h & 0xFFFF))
            f.write(bytes([24, 0x20]))
            f.write(bytes(out))
        n += 1
    print(f'{path}: exported {n} textures to {out_dir}')


if __name__ == '__main__':
    sys.exit(main())
