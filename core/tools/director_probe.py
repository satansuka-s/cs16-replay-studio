#!/usr/bin/env python3
"""Analyze svc_director command distribution in an HLTV demo."""
import struct, sys
from collections import Counter

def main(path):
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

    cmds = Counter()
    samples = {}
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
                msg = data[pos:pos+mlen]
                pos += mlen
                i = 0
                while i + 1 < len(msg):
                    op = msg[i]; i += 1
                    if op == 1: continue
                    elif op == 7: i += 4
                    elif op in (8, 9, 26): 
                        while i < len(msg) and msg[i]: i += 1
                        i += 1
                    elif op == 50: i += 1
                    elif op == 51:
                        if i >= len(msg): break
                        sz = msg[i]; i += 1
                        if i + sz > len(msg): break
                        body = msg[i:i+sz]; i += sz
                        if body:
                            cmd = body[0]
                            cmds[cmd] += 1
                            if cmd not in samples:
                                samples[cmd] = body
                        continue
                    elif op == 5: i += 2
                    elif op == 11:
                        i += 32 + 32 + 32 + 128
                        if i + 5 > len(msg): break
                        i += 3
                        def rdstr(i):
                            while i < len(msg) and msg[i]: i += 1
                            return i + 1
                        i = rdstr(i); i = rdstr(i); i = rdstr(i); i = rdstr(i); i += 1
                    elif op == 15:
                        break  # bitstream: stop tracing
                    else:
                        break
            elif ftype == 5: break
            elif ftype == 9:
                blen, = struct.unpack_from('<i', data, pos); pos += 4
                pos += blen
            elif ftype in (3,): pos += 64
            elif ftype == 4: pos += 32
            elif ftype == 6: pos += 84
            elif ftype == 7: pos += 8
            elif ftype == 8:
                slen, = struct.unpack_from('<i', data, pos + 4)
                pos += 4 + slen + 16
            elif ftype == 2: pass
            else: break
    print('director commands:', dict(sorted(cmds.items())))
    names = {0:'NONE',1:'START',2:'EVENT',3:'MODE',4:'CAMERA',5:'TIMESCALE',6:'MESSAGE',7:'SOUND',8:'STATUS',9:'BANNER',10:'STUFFTEXT',11:'CHASE',12:'INEYE',13:'MAP',14:'CAMPATH',15:'WAYPOINTS'}
    for cmd, body in sorted(samples.items()):
        print(f'--- cmd {cmd} ({names.get(cmd,"?")}) len={len(body)} ---')
        print('   ', ' '.join(f'{b:02x}' for b in body[:64]))
        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in body[:64])
        print('   ', asc)

if __name__ == '__main__':
    main(sys.argv[1])
