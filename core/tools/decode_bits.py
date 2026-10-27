#!/usr/bin/env python3
"""Decode the first packetentities/deltapacketentities packages from an HLTV demo
using two delta.lst variants, to find which table layout matches."""
import struct, sys

MAXB = 11

def norm_fields(path):
    fields = []
    cur = None
    for ln in open(path, encoding='utf-8-sig', errors='replace'):
        ln = ln.strip()
        if not ln or ln.startswith('//'): continue
        if ln.endswith('{'):
            cur = ln.split()[0]
            continue
        if ln == '}': cur = None; continue
        if cur is None or not ln.startswith('DEFINE_DELTA'): continue
        post = ln.startswith('DEFINE_DELTA_POST')
        body = ln.split('(', 1)[1].rsplit(')', 1)[0]
        args = [a.strip() for a in body.split(',')]
        flags = 0
        for tok in args[1].replace('|', ' ').split():
            flags |= {'DT_BYTE':1,'DT_SHORT':2,'DT_FLOAT':4,'DT_INTEGER':8,'DT_ANGLE':16,'DT_TIMEWINDOW_8':32,'DT_TIMEWINDOW_BIG':64,'DT_STRING':128,'DT_SIGNED':256}.get(tok, 0)
        mult = float(args[3])
        fields.append((cur, args[0], flags, int(args[2]), mult))
    return fields

class BR:
    def __init__(self, data, base=0):
        self.d = data; self.bit = base
    def bitlen(self): return len(self.d)*8 - self.bit
    def ub(self, n):
        v = 0
        for i in range(n):
            v |= ((self.d[(self.bit+i)>>3] >> ((self.bit+i)&7)) & 1) << i
        self.bit += n
        return v
    def sb(self, n):
        v = self.ub(n)
        if n < 32 and (v & (1 << (n-1))): v |= ~((1 << n) - 1)
        return v

def read_delta(br, fields, timebase):
    out = {}
    c = br.ub(3)
    mask = [br.ub(8) for _ in range(c)]
    for i, (tname, fname, flags, bits, mult) in enumerate(fields):
        if not (mask[i >> 3] & (1 << (i & 7))): continue
        if flags & 16:  # ANGLE
            v = br.ub(bits) * (360.0 / (1 << bits))
        elif flags & 64:  # TIMEWINDOW_BIG
            v = (timebase * mult - br.sb(bits)) / mult
        elif flags & 32:  # TIMEWINDOW_8
            v = (timebase * 100.0 - br.sb(bits)) / 100.0
        else:
            raw = br.sb(bits) if (flags & 256) else br.ub(bits)
            v = float(raw)
            if mult != 1.0: v /= mult
        out[fname] = v
    return out

def get_msgs(path):
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
    out = []
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
                mlen, = struct.unpack_from('<i', data, pos); pos += 4
                msg = data[pos:pos+mlen]
                pos += mlen
                out.append((desc, ftime, fframe, msg))
            elif ftype == 5: break
            elif ftype == 9:
                blen, = struct.unpack_from('<i', data, pos); pos += 4
                pos += blen
            elif ftype == 3: pos += 64
            elif ftype == 4: pos += 32
            elif ftype == 2: pass
            else: break
    return out

def find_packets(msgs, want_op):
    for desc, t, fr, msg in msgs:
        i = 0
        while i + 1 < len(msg):
            op = msg[i]; i += 1
            if op == 1: continue
            elif op == 7: i += 4
            elif op == 50: i += 1
            elif op == 51:
                sz = msg[i]; i += 1
                i += sz
            elif op == 11:  # serverdata: enough to skip roughly
                i += 4 + 4 + 4 + 128 + 3
                for _ in range(4):
                    while i < len(msg) and msg[i]: i += 1
                    i += 1
                i += 1
            elif op == 54:
                while i < len(msg) and msg[i]: i += 1
                i += 2
            elif op == 14:
                while i < len(msg) and msg[i]: i += 1
                i += 1
                # meta bitstream: not needed for extracted test (we only trace 40/41)
                # approximate: skip ~23 bytes per field
                nf = struct.unpack_from('<H', msg, i)[0]
                i += 2 + nf * 27
            elif op in (40, 41):
                if op == want_op:
                    return desc, t, fr, msg, i - 1
                else:
                    return None  # first entity msg encountered with other op
            else:
                break
    return None

def parse_packet(msg, start, fields_by_table, timebase):
    br = BR(msg, start * 8)
    br.ub(8)  # op
    count = br.ub(16)
    is_delta = msg[start] == 41
    if is_delta: br.ub(8)
    results = []
    ent = 0
    while True:
        if br.bitlen() < 16: break
        save = br.bit
        if br.ub(16) == 0: break
        br.bit = save
        if is_delta: br.ub(1)  # remove
        if br.ub(1):
            ent += 1
        else:
            if not br.ub(1):
                ent += br.ub(6)
            else:
                ent = br.ub(MAXB)
        custom = br.ub(1)
        br.ub(1)  # offset/instanced reserved
        table = fields_by_table['custom_entity_state_t'] if custom else \
                (fields_by_table['entity_state_player_t'] if 0 < ent <= 32 else fields_by_table['entity_state_t'])
        vals = read_delta(br, table, timebase)
        results.append((ent, custom, vals))
        if len(results) > 3: break
    return count, results

def main(path=None):
    path = path or sys.argv[1]
    f_4554 = norm_fields(r'D:\Counter-Strike Build 4554\cstrike\delta.lst')
    f_gc = norm_fields(r'D:\CS 1.6 GoldClient\cstrike\delta.lst')
    def group(fs):
        d = {}
        for t, n, fl, b, m in fs:
            d.setdefault(t, []).append((n, fl, b, m))
        return d
    g_4554 = group(f_4554)
    g_gc = group(f_gc)
    msgs = get_msgs(path)
    # locate svc 40/41 occurrences (first packetentities packages)
    for desc, t, fr, msg in msgs:
        idxs = [i for i in range(len(msg)) if msg[i] == 40]
        if idxs:
            print(f'msg {desc} t={t:.2f} fr={fr} len={len(msg)}: op40 at {idxs[:6]}')
            i = idxs[0]
            print('  ctx:', ' '.join(f'{b:02x}' for b in msg[max(0,i-8):i+48]))
            break
    for desc, t, fr, msg in msgs:
        idxs = [i for i in range(len(msg)) if msg[i] == 41]
        if idxs:
            print(f'msg {desc} t={t:.2f} fr={fr} len={len(msg)}: op41 at {idxs[:6]}')
            i = idxs[0]
            print('  ctx:', ' '.join(f'{b:02x}' for b in msg[max(0,i-8):i+56]))
            break
    return

if __name__ == '__main__':
    main(sys.argv[1])
