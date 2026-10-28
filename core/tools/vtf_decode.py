"""VTF (Valve Texture Format) decoder for Source 1 games (CS:GO/CSS).

Pure-python: header, mip chain, resource block, DXT1/3/5 + common 8888 formats.
Structures verified against Valve's vtf spec and SourceIO (MIT) enum layout.

Usage:
    from vtf_decode import decode_vtf
    w, h, rgba = decode_vtf(open(path,'rb').read())
"""
import struct

FORMAT_RGBA8888 = 0
FORMAT_ABGR8888 = 1
FORMAT_RGB888 = 2
FORMAT_BGR888 = 3
FORMAT_RGB565 = 4
FORMAT_I8 = 5
FORMAT_IA88 = 6
FORMAT_P8 = 7
FORMAT_A8 = 8
FORMAT_ARGB8888 = 11
FORMAT_BGRA8888 = 12
FORMAT_DXT1 = 13
FORMAT_DXT3 = 14
FORMAT_DXT5 = 15
FORMAT_BGRX8888 = 16
FORMAT_BGR565 = 17
FORMAT_BGRA4444 = 19
FORMAT_BGRA5551 = 21
FORMAT_RGBA16161616F = 24
FORMAT_RGBA16161616 = 25

_RSRC_LOW_RES = 1
_RSRC_HIGH_RES = 0x30


def _mip_count(w, h):
    n = 1
    while w > 1 or h > 1:
        w = max(w // 2, 1)
        h = max(h // 2, 1)
        n += 1
    return n


def _mip_sizes(w, h, fmt, mips):
    bpp = {FORMAT_RGBA8888: 4, FORMAT_ABGR8888: 4, FORMAT_ARGB8888: 4,
           FORMAT_BGRA8888: 4, FORMAT_BGRX8888: 4, FORMAT_RGB888: 3,
           FORMAT_BGR888: 3, FORMAT_I8: 1, FORMAT_IA88: 2, FORMAT_A8: 1,
           FORMAT_RGB565: 2, FORMAT_BGR565: 2, FORMAT_BGRA4444: 2,
           FORMAT_BGRA5551: 2, FORMAT_RGBA16161616F: 8,
           FORMAT_RGBA16161616: 8}.get(fmt)
    if bpp is None and fmt in (FORMAT_DXT1, FORMAT_DXT3, FORMAT_DXT5):
        blocks = (max(w, 3) // 4) * (max(h, 3) // 4)
        if fmt == FORMAT_DXT1:
            return [blocks * 8 for _ in range(mips)]
        return [blocks * 16 for _ in range(mips)]
    if bpp is None:
        raise ValueError('unsupported VTF format %d' % fmt)
    out = []
    for _ in range(mips):
        out.append(w * h * bpp)
        w = max(w // 2, 1)
        h = max(h // 2, 1)
    return out


def _decompress_dxt(block, fmt):
    """One 4x4 block -> 16 RGBA pixels."""
    if fmt == FORMAT_DXT1:
        c0, c1 = struct.unpack_from('<HH', block, 0)
        table = block[4:8]
        r0, g0, b0 = _rgb565(c0)
        r1, g1, b1 = _rgb565(c1)
        if c0 > c1:
            pal = [(r0, g0, b0, 255), (r1, g1, b1, 255),
                   ((2 * r0 + r1) // 3, (2 * g0 + g1) // 3, (2 * b0 + b1) // 3, 255),
                   ((r0 + 2 * r1) // 3, (g0 + 2 * g1) // 3, (b0 + 2 * b1) // 3, 255)]
        else:
            pal = [(r0, g0, b0, 255), (r1, g1, b1, 255),
                   ((r0 + r1) // 2, (g0 + g1) // 2, (b0 + b1) // 2, 255),
                   (0, 0, 0, 0)]
        out = bytearray(16 * 4)
        for i in range(16):
            idx = (table[i // 2] >> (4 * (i & 1))) & 3
            out[i * 4:i * 4 + 4] = bytes(pal[idx])
        return bytes(out)
    # DXT3 / DXT5 share the colour block
    a0, a1 = block[0], block[1]
    if fmt == FORMAT_DXT3:
        alph = block[0:8]
        col = block[8:16]
    else:
        alph_tab = block[2:8]
        col = block[8:16]
        if a0 > a1:
            a_pal = [a0, a1,
                     (6 * a0 + a1) // 7, (5 * a0 + 2 * a1) // 7, (4 * a0 + 3 * a1) // 7,
                     (3 * a0 + 4 * a1) // 7, (2 * a0 + 5 * a1) // 7, (a0 + 6 * a1) // 7]
        else:
            a_pal = [a0, a1,
                     (4 * a0 + a1) // 5, (3 * a0 + 2 * a1) // 5, (2 * a0 + 3 * a1) // 5,
                     (a0 + 4 * a1) // 5, 0, 255]
    c0, c1 = struct.unpack_from('<HH', col, 0)
    table = col[4:8]
    r0, g0, b0 = _rgb565(c0)
    r1, g1, b1 = _rgb565(c1)
    if c0 > c1:
        pal = [(r0, g0, b0), (r1, g1, b1),
               ((2 * r0 + r1) // 3, (2 * g0 + g1) // 3, (2 * b0 + b1) // 3),
               ((r0 + 2 * r1) // 3, (g0 + 2 * g1) // 3, (b0 + 2 * b1) // 3)]
    else:
        pal = [(r0, g0, b0), (r1, g1, b1),
               ((r0 + r1) // 2, (g0 + g1) // 2, (b0 + b1) // 2),
               (0, 0, 0)]
    out = bytearray(16 * 4)
    for i in range(16):
        ci = (table[i // 2] >> (4 * (i & 1))) & 3
        out[i * 4:i * 4 + 3] = bytes(pal[ci])
        if fmt == FORMAT_DXT3:
            a = (alph[i // 2] >> (4 * (i & 1))) & 0xF
            out[i * 4 + 3] = a * 17
        else:
            ai = (alph_tab[(i * 3) // 8] >> ((i * 3) % 8)) & 7
            if (i * 3) % 8 > 5:
                ai |= (alph_tab[(i * 3) // 8 + 1] << (8 - (i * 3) % 8)) & 7
            out[i * 4 + 3] = a_pal[ai]
    return bytes(out)


def _rgb565(v):
    return ((v >> 11) & 0x1F) * 255 // 31, ((v >> 5) & 0x3F) * 255 // 63, (v & 0x1F) * 255 // 31


def _decode_plane(w, h, fmt, data):
    """Full-size plane -> RGBA bytes."""
    if fmt in (FORMAT_DXT1, FORMAT_DXT3, FORMAT_DXT5):
        bw = max(w, 1) // 4 if w >= 4 else 1
        bh = max(h, 1) // 4 if h >= 4 else 1
        bw = (w + 3) // 4
        bh = (h + 3) // 4
        out = bytearray(w * h * 4)
        for by in range(bh):
            for bx in range(bw):
                blk = data[(by * bw + bx) * (8 if fmt == FORMAT_DXT1 else 16):
                           (by * bw + bx + 1) * (8 if fmt == FORMAT_DXT1 else 16)]
                px = _decompress_dxt(blk, fmt)
                for yy in range(4):
                    for xx in range(4):
                        x = bx * 4 + xx
                        y = by * 4 + yy
                        if x < w and y < h:
                            out[(y * w + x) * 4:(y * w + x) * 4 + 4] = \
                                px[(yy * 4 + xx) * 4:(yy * 4 + xx) * 4 + 4]
        return bytes(out)
    if fmt == FORMAT_RGBA8888:
        return data[:w * h * 4]
    if fmt == FORMAT_BGRA8888:
        return b''.join(bytes((data[i + 2], data[i + 1], data[i], data[i + 3]))
                        for i in range(0, w * h * 4, 4))
    if fmt == FORMAT_ARGB8888:
        return b''.join(bytes((data[i + 1], data[i + 2], data[i + 3], data[i]))
                        for i in range(0, w * h * 4, 4))
    if fmt == FORMAT_ABGR8888:
        return b''.join(bytes((data[i + 3], data[i + 2], data[i + 1], data[i]))
                        for i in range(0, w * h * 4, 4))
    if fmt == FORMAT_RGB888:
        return b''.join(bytes((data[i], data[i + 1], data[i + 2], 255))
                        for i in range(0, w * h * 3, 3))
    if fmt == FORMAT_BGR888:
        return b''.join(bytes((data[i + 2], data[i + 1], data[i], 255))
                        for i in range(0, w * h * 3, 3))
    if fmt == FORMAT_BGRX8888:
        return b''.join(bytes((data[i + 2], data[i + 1], data[i], 255))
                        for i in range(0, w * h * 4, 4))
    if fmt == FORMAT_RGB565:
        out = bytearray(w * h * 4)
        for i in range(w * h):
            v = struct.unpack_from('<H', data, i * 2)[0]
            r, g, b = _rgb565(v)
            out[i * 4:i * 4 + 4] = bytes((r, g, b, 255))
        return bytes(out)
    if fmt == FORMAT_I8:
        return b''.join(bytes((data[i], data[i], data[i], 255)) for i in range(w * h))
    if fmt == FORMAT_A8:
        return b''.join(bytes((255, 255, 255, data[i])) for i in range(w * h))
    if fmt == FORMAT_RGBA16161616F:
        import struct as _s
        out = bytearray(w * h * 4)
        for i in range(w * h):
            vals = _s.unpack_from('<4e', data, i * 8)
            for k in range(4):
                out[i * 4 + k] = max(0, min(255, int(vals[k] * 255)))
        return bytes(out)
    raise ValueError('format %d not implemented' % fmt)


def decode_vtf(data, mip=0):
    """Decode VTF -> (w, h, rgba bytes). mip=0 is the largest."""
    if data[:4] != b'VTF\0':
        raise ValueError('not a VTF')
    ver_major, ver_minor = struct.unpack_from('<HH', data, 4)
    headersize = struct.unpack_from('<I', data, 8)[0]
    width, height = struct.unpack_from('<HH', data, 12)
    flags, frames = struct.unpack_from('<IH', data, 16)
    firstframe = struct.unpack_from('<H', data, 22)[0]
    reflectivity = struct.unpack_from('<3f', data, 24)
    bumpmapsize = struct.unpack_from('<f', data, 40)[0]
    highresfmt = struct.unpack_from('<I', data, 44)[0]
    lowresfmt = struct.unpack_from('<B', data, 48)[0]
    lowresw, lowresh = struct.unpack_from('<BB', data, 49)
    depth = struct.unpack_from('<H', data, 51)[0]
    numresources = struct.unpack_from('<I', data, 52)[0]
    pad2 = struct.unpack_from('<I', data, 56)[0]
    # unknown data
    hiressize = struct.unpack_from('<I', data, 60)[0] if headersize >= 64 else 0
    lowressize = struct.unpack_from('<I', data, 64)[0] if headersize >= 68 else 0
    body = data[headersize:]
    high = None
    offset = 0
    if numresources > 0:
        # resource entries: (type, data) pairs; high-res data resource holds the image
        entries = []
        for i in range(numresources):
            rtype, rdata = struct.unpack_from('<II', body, i * 8)
            entries.append((rtype, rdata))
        offset = numresources * 8
        for rtype, rdata in entries:
            if rtype == _RSRC_HIGH_RES:
                high = body[offset + rdata:]
    if high is None:
        high = body[offset:]
    if not hiressize:
        hiressize = len(high)
    # mip chain is stored smallest-first; the largest mip is the LAST block
    mips = _mip_count(width, height)
    sizes = _mip_sizes(width, height, highresfmt, mips)
    total = sum(sizes)
    if len(high) < total:
        raise ValueError('VTF image data too small (%d < %d)' % (len(high), total))
    chain = high[len(high) - total:]
    # ask for mip index (0 = largest) -> position in smallest-first chain
    idx = mips - 1 - mip
    off = 0
    for i in range(idx):
        off += sizes[i]
    blk = chain[off:off + sizes[idx]]
    mw = max(width >> mip, 1)
    mh = max(height >> mip, 1)
    return mw, mh, _decode_plane(mw, mh, highresfmt, blk)
