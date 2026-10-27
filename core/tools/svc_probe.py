#!/usr/bin/env python3
"""Deep probe on demo payloads: netmsg/buffer size distribution."""
import struct, sys

def read_demo(path):
    data = open(path, 'rb').read()
    demo_proto, net_proto = struct.unpack_from('<II', data, 8)
    mapname = data[16:276].split(b'\0')[0].decode('latin1')
    gamedir = data[276:536].split(b'\0')[0].decode('latin1')
    diroff = struct.unpack_from('<iI', data, 536)[1]
    count = struct.unpack_from('<I', data, diroff)[0]
    p = diroff + 4
    entries = []
    for _ in range(count):
        typ, = struct.unpack_from('<i', data, p); p += 4
        desc = data[p:p+64].split(b'\0')[0].decode('latin1'); p += 64
        flags, cdtrack = struct.unpack_from('<ii', data, p); p += 8
        track, frames, off, length = struct.unpack_from('<fiii', data, p); p += 16
        entries.append((typ, desc, off, length))
    return net_proto, mapname, gamedir, entries, data

def main(path):
    net_proto, mapname, gamedir, entries, data = read_demo(path)
    print(f'{path}: net_proto={net_proto} map={mapname} gamedir={gamedir}')
    sizes = []
    for typ, desc, off, length in entries:
        if off <= 0: continue
        pos = off
        end = min(off + length, len(data))
        while pos + 12 <= end:
            ftype = data[pos]; pos += 1
            ftime, = struct.unpack_from('<f', data, pos); pos += 4
            fframe, = struct.unpack_from('<i', data, pos); pos += 4
            if ftype in (0, 1):
                pos += 464
                if pos + 4 > end: break
                mlen, = struct.unpack_from('<i', data, pos); pos += 4
                if mlen < 0 or pos + mlen > end: break
                pos += mlen
                sizes.append(('netmsg', fframe, mlen))
            elif ftype == 100:
                if pos + 4 > end: break
                mlen, = struct.unpack_from('<i', data, pos); pos += 4
                if mlen < 0 or pos + mlen > end: break
                sizes.append(('f100', fframe, mlen))
                pos += mlen
            elif ftype == 9:
                if pos + 4 > end: break
                blen, = struct.unpack_from('<i', data, pos); pos += 4
                if blen < 0 or pos + blen > end: break
                sizes.append(('dbuf', fframe, blen, -1))
                pos += blen
            elif ftype == 5: break
            elif ftype == 3: pos += 64
            elif ftype == 4: pos += 32
            elif ftype == 6: pos += 84
            elif ftype == 7: pos += 8
            elif ftype == 8:
                if pos + 8 > end: break
                slen, = struct.unpack_from('<i', data, pos + 4)
                if slen < 0 or pos + slen + 16 > end: break
                pos += 4 + slen + 16
            elif ftype == 2: pass
            else:
                print(f'  [halt] type {ftype} at {pos-9}'); break
    print('entries:', [(d, o, l) for _, d, o, l in entries])
    for s in sizes[:80]:
        print(' ', s)
    print('count:', len(sizes), 'payload total:', sum(s[2] for s in sizes))

if __name__ == '__main__':
    main(sys.argv[1])
