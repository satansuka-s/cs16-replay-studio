import struct, sys

def load_png_rgb(path):
    # minimal PNG reader (only non-interlaced 8-bit RGB/RGBA)
    d = open(path, 'rb').read()
    assert d[:8] == b'\x89PNG\r\n\x1a\n'
    pos = 8
    idat = b''
    w = h = 0
    bit = col = 0
    while pos < len(d):
        ln = struct.unpack_from('>I', d, pos)[0]
        typ = d[pos + 4:pos + 8]
        data = d[pos + 8:pos + 8 + ln]
        if typ == b'IHDR':
            w, h, bit, col, _, _, _ = struct.unpack_from('>IIBBBBB', data, 0)
        elif typ == b'IDAT':
            idat += data
        elif typ == b'IEND':
            break
        pos += 12 + ln
    import zlib
    raw = zlib.decompress(idat)
    bypp = 4 if col == 6 else (3 if col == 2 else 1)
    stride = w * bypp
    out = bytearray(w * h * 3)
    prev = bytearray(stride)
    for y in range(h):
        f = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        if f == 1:
            for i in range(bypp, stride):
                line[i] = (line[i] + line[i - bypp]) & 0xFF
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif f == 3:
            for i in range(stride):
                a = line[i - bypp] if i >= bypp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif f == 4:
            for i in range(stride):
                a = line[i - bypp] if i >= bypp else 0
                b = prev[i]
                c = prev[i - bypp] if i >= bypp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        prev = line
        for x in range(w):
            i = x * bypp
            out[(y * w + x) * 3] = line[i] if bypp == 1 else line[i]
            out[(y * w + x) * 3 + 1] = line[i] if bypp == 1 else line[i + 1]
            out[(y * w + x) * 3 + 2] = line[i] if bypp == 1 else (line[i + 2] if bypp == 3 else line[i + 2])
    return w, h, bytes(out)


def stats(path):
    w, h, px = load_png_rgb(path)
    n = w * h
    mag = sum(1 for i in range(0, n * 3, 3) if px[i] > 200 and px[i + 1] < 60 and px[i + 2] > 200)
    # avg color of non-magenta pixels in sky region (top 20%)
    top = min(h, h // 5)
    cnt = [0, 0, 0]
    tot = 0
    for y in range(top):
        for x in range(w):
            i = (y * w + x) * 3
            if px[i] > 200 and px[i + 1] < 60 and px[i + 2] > 200:
                continue
            cnt[0] += px[i]; cnt[1] += px[i + 1]; cnt[2] += px[i + 2]
            tot += 1
    avg = tuple(round(c / max(tot, 1)) for c in cnt) if tot else None
    # overall avg
    oavg = [0, 0, 0]
    for i in range(0, n * 3, 3):
        oavg[0] += px[i]; oavg[1] += px[i + 1]; oavg[2] += px[i + 2]
    oavg = tuple(round(c / n) for c in oavg)
    # horizontal profile: avg brightness per column band
    band = 12
    prof = []
    for b in range(band):
        s = t = 0
        for y in range(h):
            for x in range(b * w // band, (b + 1) * w // band):
                i = (y * w + x) * 3
                s += (px[i] + px[i + 1] + px[i + 2]) // 3
                t += 1
        prof.append(round(s / t))
    print('%s: %dx%d magenta=%.1f%% top-avg=%s overall-avg=%s brightness-profile=%s' %
          (path, w, h, 100.0 * mag / n, avg, oavg, prof))


for p in sys.argv[1:]:
    stats(p)
