#!/usr/bin/env python3
"""Determine netmsg prefix length for a demo by end-to-end scan consistency."""
import struct, sys
from collections import Counter

def scan(path, prefix):
    data = open(path, 'rb').read()
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
    ops = Counter()
    nmsg = 0
    nframe = 0
    endpos = None
    for typ, desc, off, length in entries:
        if off <= 0: continue
        pos = off
        end = min(off + length, len(data))
        while pos + 12 <= end:
            ftype = data[pos]; pos += 1
            ftime, = struct.unpack_from('<f', data, pos); pos += 4
            fframe, = struct.unpack_from('<i', data, pos); pos += 4
            nframe += 1
            if ftype in (0, 1):
                nmsg += 1
                npos = pos + prefix
                if npos + 4 > end: return endpos, nmsg, nframe, ops, 'trunc-header'
                mlen, = struct.unpack_from('<i', data, npos); npos += 4
                if mlen < 0 or npos + mlen > end: return endpos, nmsg, nframe, ops, 'trunc-len'
                ops[data[npos]] += 1
                pos = npos + mlen
                endpos = pos
            elif ftype == 5:
                break
            elif ftype == 9:
                if pos + 4 > end: return endpos, nmsg, nframe, ops, 'trunc-dbuf'
                blen, = struct.unpack_from('<i', data, pos); pos += 4
                if blen < 0 or pos + blen > end: return endpos, nmsg, nframe, ops, 'trunc-dbuf2'
                pos += blen
            elif ftype == 3: pos += 64
            elif ftype == 4: pos += 32
            elif ftype == 6: pos += 84
            elif ftype == 7: pos += 8
            elif ftype == 8:
                if pos + 8 > end: return endpos, nmsg, nframe, ops, 'trunc-snd'
                slen, = struct.unpack_from('<i', data, pos + 4)
                if slen < 0 or pos + slen + 16 > end: return endpos, nmsg, nframe, ops, 'trunc-snd2'
                pos += 4 + slen + 16
            elif ftype == 2: pass
            else:
                return pos - 9, nmsg, nframe, ops, f'unknown-type-{ftype}'
    return endpos, nmsg, nframe, ops, 'ok'

if __name__ == '__main__':
    path = sys.argv[1]
    for prefix in (464, 496, 452, 480, 512):
        endpos, nmsg, nframe, ops, status = scan(path, prefix)
        print(f'prefix={prefix}: status={status} nmsg={nmsg} frames={nframe} last_pos={endpos} top_ops={ops.most_common(8)}')
