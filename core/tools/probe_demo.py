#!/usr/bin/env python3
"""Probe a GoldSrc demo file at the message level - verbose frame trace + svc histogram."""
import struct, sys, collections

def main(path):
    data = open(path, 'rb').read()
    demo_proto, net_proto = struct.unpack_from('<II', data, 8)
    mapname = data[16:276].split(b'\0')[0].decode('latin1')
    mapcrc, diroff = struct.unpack_from('<iI', data, 536)
    print(f'file={path} net_protocol={net_proto} gamedir={data[276:536].split(b"\\0")[0]!r}')
    count = struct.unpack_from('<I', data, diroff)[0]
    p = diroff + 4
    entries = []
    for _ in range(count):
        typ, = struct.unpack_from('<i', data, p); p += 4
        desc = data[p:p+64].split(b'\0')[0].decode('latin1'); p += 64
        flags, cdtrack = struct.unpack_from('<ii', data, p); p += 8
        track, frames, off, length = struct.unpack_from('<fiii', data, p); p += 16
        entries.append((typ, desc, off, length))
        print(f'  entry: type={typ} desc={desc!r} offset={off} length={length}')

    svc_hist = collections.Counter()
    svc_samples = collections.defaultdict(list)
    n_frames = 0
    verbose_done = 0
    for typ, desc, off, length in entries:
        if off <= 0:
            continue
        pos = off
        end = min(off + length, len(data))
        while pos + 12 <= end:
            ftype = data[pos]; pos += 1
            ftime, = struct.unpack_from('<f', data, pos); pos += 4
            fframe, = struct.unpack_from('<i', data, pos); pos += 4
            n_frames += 1
            if ftype in (0, 1):
                npos = pos + 464
                if npos + 4 > end:
                    print(f'  [trunc] netmsg header overflow at {pos-9}'); break
                mlen, = struct.unpack_from('<i', data, npos); npos += 4
                npos2 = npos + mlen
                if mlen < 0 or npos2 > end:
                    print(f'  [trunc] netmsg len={mlen} at frame {n_frames} (pos {pos-9})'); break
                msg = data[npos:npos2]
                pos = npos2
                if verbose_done < 12:
                    print(f'  frame {n_frames}: type={ftype} t={ftime:.3f} f={fframe} msg_len={mlen} op={msg[0] if msg else -1} head={msg[:24].hex(" ")}')
                    verbose_done += 1
                if msg:
                    svc_hist[msg[0]] += 1
                    if len(svc_samples[msg[0]]) < 3:
                        svc_samples[msg[0]].append(msg)
            elif ftype == 5:
                print(f'  frame {n_frames}: NEXT_SECTION @ {pos-9}')
                break
            elif ftype == 9:
                if pos + 4 > end: print('  [trunc] dbuf'); break
                blen, = struct.unpack_from('<i', data, pos); pos += 4
                if blen < 0 or pos + blen > end: print(f'  [trunc] dbuf len={blen}'); break
                pos += blen
            elif ftype == 3:
                pos += 64
            elif ftype == 4:
                pos += 32
            elif ftype == 6:
                pos += 84
            elif ftype == 7:
                pos += 8
            elif ftype == 8:
                if pos + 8 > end: print('  [trunc] snd'); break
                chan, = struct.unpack_from('<i', data, pos); pos += 4
                slen, = struct.unpack_from('<i', data, pos); pos += 4
                if slen < 0 or pos + slen + 16 > end: print('  [trunc] snd-data'); break
                pos += slen + 16
            elif ftype == 2:
                pass
            else:
                print(f'  [halt] unknown frame type {ftype} at {pos-9}')
                break
    print(f'frames scanned: {n_frames}')
    print('svc histogram:', dict(sorted(svc_hist.items())))
    def hexs(b, n=96):
        return ' '.join(f'{x:02x}' for x in b[:n])
    for op, msgs in sorted(svc_samples.items()):
        print(f'--- svc {op} ---')
        for m in msgs:
            print(f'  len={len(m)}: {hexs(m)}')

if __name__ == '__main__':
    main(sys.argv[1])
