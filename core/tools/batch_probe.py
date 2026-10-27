#!/usr/bin/env python3
"""Batch-scan several demos: which parse cleanly with prefix 464, do they contain svc 40/41 stream?"""
import struct, sys, glob, os
from collections import Counter

def scan(path, prefix=464, whole=False):
    data = open(path, 'rb').read()
    if data[:6] != b'HLDEMO': return 'not-hldemo', None, None
    net_proto = struct.unpack_from('<II', data, 8)[1]
    diroff = struct.unpack_from('<iI', data, 536)[1]
    if diroff < 0 or diroff + 4 > len(data):
        return 'bad-diroff', net_proto, None
    count = struct.unpack_from('<I', data, diroff)[0]
    if count > 1024 or diroff + 4 + count * 92 > len(data) + 4:
        return 'bad-dircount', net_proto, None
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
    typec = Counter()
    for typ, desc, off, length in entries:
        if off <= 0: continue
        pos = off
        end = min(off + length, len(data))
        while pos + 12 <= end:
            ftype = data[pos]; pos += 1
            ftime, = struct.unpack_from('<f', data, pos); pos += 4
            fframe, = struct.unpack_from('<i', data, pos); pos += 4
            typec[ftype] += 1
            if ftype in (0, 1):
                nmsg += 1
                npos = pos + prefix
                if npos + 4 > end: return 'trunc', net_proto, typec
                mlen, = struct.unpack_from('<i', data, npos); npos += 4
                if mlen < 0 or npos + mlen > end:
                    if whole: return 'trunc-len', net_proto, typec
                    break
                ops[data[npos]] += 1
                pos = npos + mlen
            elif ftype == 5:
                if not whole: break
            elif ftype == 9:
                if pos + 4 > end: return 'trunc', net_proto, typec
                blen, = struct.unpack_from('<i', data, pos); pos += 4
                if blen < 0 or pos + blen > end: return 'trunc', net_proto, typec
                pos += blen
            elif ftype == 3: pos += 64
            elif ftype == 4: pos += 32
            elif ftype == 6: pos += 84
            elif ftype == 7: pos += 8
            elif ftype == 8:
                if pos + 8 > end: return 'trunc', net_proto, typec
                slen, = struct.unpack_from('<i', data, pos + 4)
                if slen < 0 or pos + slen + 16 > end: return 'trunc', net_proto, typec
                pos += 4 + slen + 16
            elif ftype == 2: pass
            else:
                if whole: return f'unknown-type-{ftype}', net_proto, typec
                break
    return 'ok', net_proto, (ops, typec)

if __name__ == '__main__':
    for path in sys.argv[1:]:
        status, net_proto, extra = scan(path, whole=True)
        if status == 'ok':
            ops, typec = extra
            interesting = sorted([(k, v) for k, v in ops.items() if k in (14, 15, 40, 41, 7)], key=lambda t: -t[1])
            print(f'{os.path.basename(path)}: OK net={net_proto} ops={dict(ops.most_common(12))}')
        else:
            print(f'{os.path.basename(path)}: {status} net={net_proto} types={dict(extra.most_common(10)) if extra else None}')
