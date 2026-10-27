#!/usr/bin/env python3
"""Synthetic GoldSrc demo writer used to test demo_extract end-to-end.

Produces a valid .dem with:
  - LOADING entry: svc_print + svc_serverdata + delta tables (clientdata_t,
    entity_state_t, entity_state_player_t, custom_entity_state_t, event_t)
    + svc_spawnbaseline for players 1..2
  - Playback entry: per-tick svc_time + svc_packetentities (two players
    walking: origin/sequence/frame/animtime/framerate), plus CLIENT_DATA
    camera frames every 10 ticks.

Layout of netmsg frames matches the format decoded by demo_extract
(464-byte prefix + int32 length + svc stream)."""
import struct
import sys

NET_PREFIX = 464
MAX_GS_ENTBITS = 11

# delta type flags
DT_BYTE, DT_SHORT, DT_FLOAT, DT_INTEGER, DT_ANGLE = 1, 2, 4, 8, 16
DT_TIMEWINDOW_BIG, DT_STRING, DT_SIGNED = 64, 128, 256


class Bits:
    def __init__(self):
        self.bits = []

    def b(self, v, n=1):
        for i in range(n):
            self.bits.append((v >> i) & 1)

    def s(self, v, n):
        self.b(v & ((1 << n) - 1), n)

    def string(self, s):
        for c in s.encode('latin1'):
            self.b(c, 8)
        self.b(0, 8)

    def f32(self, v):
        self.s(struct.unpack('<I', struct.pack('<f', v))[0], 32)

    def bytes(self):
        out = bytearray()
        for i in range(0, len(self.bits), 8):
            byte = 0
            for j in range(min(8, len(self.bits) - i)):
                byte |= self.bits[i + j] << j
            out.append(byte)
        return bytes(out)


# ---------------------------------------------------------------- delta tables

def entity_table_fields():
    return [
        ('origin[0]', DT_FLOAT | DT_SIGNED, 24, 8.0, 1.0),
        ('origin[1]', DT_FLOAT | DT_SIGNED, 24, 8.0, 1.0),
        ('origin[2]', DT_FLOAT | DT_SIGNED, 24, 8.0, 1.0),
        ('angles[0]', DT_ANGLE, 16, 1.0, 1.0),
        ('angles[1]', DT_ANGLE, 16, 1.0, 1.0),
        ('angles[2]', DT_ANGLE, 16, 1.0, 1.0),
        ('modelindex', DT_INTEGER, 10, 1.0, 1.0),
        ('sequence', DT_SHORT, 8, 1.0, 1.0),
        ('frame', DT_FLOAT | DT_SIGNED, 16, 1000.0, 1.0),
        ('animtime', DT_TIMEWINDOW_BIG, 16, 100.0, 1.0),
        ('framerate', DT_FLOAT | DT_SIGNED, 16, 1.0, 1.0),
        ('body', DT_SHORT, 8, 1.0, 1.0),
        ('skin', DT_BYTE, 8, 1.0, 1.0),
        ('velocity[0]', DT_FLOAT | DT_SIGNED, 16, 1.0, 1.0),
        ('velocity[1]', DT_FLOAT | DT_SIGNED, 16, 1.0, 1.0),
        ('velocity[2]', DT_FLOAT | DT_SIGNED, 16, 1.0, 1.0),
    ]


def clientdata_table_fields():
    return [
        ('origin[0]', DT_FLOAT | DT_SIGNED, 24, 8.0, 1.0),
        ('origin[1]', DT_FLOAT | DT_SIGNED, 24, 8.0, 1.0),
        ('origin[2]', DT_FLOAT | DT_SIGNED, 24, 8.0, 1.0),
        ('velocity[0]', DT_FLOAT | DT_SIGNED, 16, 1.0, 1.0),
        ('velocity[1]', DT_FLOAT | DT_SIGNED, 16, 1.0, 1.0),
        ('velocity[2]', DT_FLOAT | DT_SIGNED, 16, 1.0, 1.0),
        ('viewangles[0]', DT_FLOAT | DT_SIGNED, 16, 1.0, 1.0),
        ('viewangles[1]', DT_FLOAT | DT_SIGNED, 16, 1.0, 1.0),
        ('viewangles[2]', DT_FLOAT | DT_SIGNED, 16, 1.0, 1.0),
        ('fov', DT_FLOAT | DT_SIGNED, 8, 1.0, 1.0),
    ]


def meta_record(ftype, name, bits_, premul, postmul):
    """goldsrc_delta_t meta record as a GS delta (all 7 fields set)."""
    b = Bits()
    b.b(1, 3)  # 1 mask byte
    b.b(0b01111111, 8)
    b.s(ftype, 32)
    b.string(name)
    b.s(0, 16)      # fieldOffset (unused by demo_extract)
    b.s(min(64, len(name) + 1), 8)  # fieldSize
    b.s(bits_, 8)
    # network carries premultiply scaled by 4000 (meta field multiplier)
    b.s(struct.unpack('<I', struct.pack('<f', premul * 4000.0))[0], 32)
    b.s(struct.unpack('<I', struct.pack('<f', postmul * 4000.0))[0], 32)
    return b

def write_delta_table(bits, name, fields):
    bits.string(name)
    bits.s(len(fields), 16)
    for fname, ftype, sigbits, premul, postmul in fields:
        r = meta_record(ftype, fname, sigbits, premul, postmul)
        bits.bits.extend(r.bits)


def write_delta(bits, fields, changes, server_time):
    """changes: dict {field_index: float value}. server_time used to encode TIMEWINDOW fields."""
    idx = sorted(changes)
    mask = [0] * ((idx[-1] // 8) + 1)
    for i in idx:
        mask[i // 8] |= 1 << (i % 8)
    bits.b(len(mask), 3)
    for m in mask:
        bits.b(m, 8)
    for i in idx:
        fname, ftype, sigbits, premul, postmul = fields[i]
        v = changes[i]
        if ftype & DT_ANGLE:
            scaled = int((v % 360.0) / 360.0 * (1 << sigbits)) & ((1 << sigbits) - 1)
            bits.s(scaled, sigbits)
        elif ftype & DT_TIMEWINDOW_BIG:
            # decoder: t = (timebase*mult - i)/mult  =>  i = (timebase - v)*mult
            ti = int(round((server_time - v) * premul)) & ((1 << sigbits) - 1)
            bits.s(ti, sigbits)
        elif ftype & DT_FLOAT:
            iv = int(round(v * premul))
            iv &= (1 << sigbits) - 1 if not (ftype & DT_SIGNED) else (1 << sigbits) - 1
            bits.s(iv, sigbits)
        elif ftype & DT_INTEGER:
            bits.s(int(v) & ((1 << sigbits) - 1), sigbits)
        elif ftype & DT_SHORT:
            bits.s(int(v) & ((1 << sigbits) - 1), sigbits)
        elif ftype & DT_BYTE:
            bits.s(int(v) & ((1 << sigbits) - 1), sigbits)
        elif ftype & DT_STRING:
            bits.string(str(v))


# ---------------------------------------------------------------- demo writer

def entity_header(bits, entnum, prev, delta_mode=False):
    if delta_mode:
        bits.b(0)  # remove bit
    if entnum == prev + 1:
        bits.b(1)
    elif entnum < prev + 64:
        bits.b(0); bits.b(0); bits.s(entnum - prev, 6)
    else:
        bits.b(0); bits.b(1); bits.s(entnum, MAX_GS_ENTBITS)
    bits.b(0)  # custom delta? no
    if not delta_mode:
        bits.b(0)  # no baseline offset
    # (instanced-baseline mode is off in this synthetic demo)


def netmsg_frame(ftime, fframe, payload):
    head = struct.pack('<Bfi', 1, ftime, fframe)
    return head + bytes(NET_PREFIX) + struct.pack('<i', len(payload)) + payload


def build_demo(n_ticks=30):
    F = entity_table_fields()
    C = clientdata_table_fields()

    loading = Bits()
    loading.b(8, 8)
    loading.string("Synthetic test demo\n")
    loading.b(11, 8)                     # svc_serverdata (full GoldSrc layout)
    loading.s(47, 32)                    # protocol
    loading.s(1, 32)                     # servercount
    loading.s(0, 32)                     # checksum
    for _ in range(16):
        loading.b(0, 8)                  # clientdll md5
    loading.b(32, 8)                     # maxclients
    loading.b(0, 8)                      # playernum
    loading.b(1, 8)                      # coop flag (quake leftover)
    loading.string("cstrike")            # game folder
    loading.string("localhost")          # remote host
    loading.string("maps/de_test.bsp")   # map name
    loading.string("")                   # map cycle
    loading.b(0, 8)                      # vac2
    for tname, tfields in (("clientdata_t", C),
                           ("entity_state_t", F),
                           ("entity_state_player_t", F),
                           ("custom_entity_state_t", F),
                           ("event_t", [])):
        loading.b(14, 8)                  # svc_deltatable
        write_delta_table(loading, tname, tfields)
    # baselines (svc_spawnbaseline)
    loading.b(22, 8)
    for ent in (1, 2):
        loading.s(ent, MAX_GS_ENTBITS)
        loading.s(0, 2)                   # entity type: normal
        vals = {0: 10.0 + ent * 5.0, 1: 0.0, 2: 20.0,
                3: 0.0, 4: 0.0, 5: 0.0,
                6: 2.0, 7: 0.0, 8: 0.0, 9: 0.0, 10: 30.0,
                11: 0, 12: 0, 13: 0.0, 14: 0.0, 15: 0.0}
        write_delta(loading, F, vals, 0.0)
    loading.s(0xFFFF, 16)                 # end of baselines
    loading.s(0, 6)                       # instanced baselines count
    loading.b(1, 8)                       # svc_nop
    loading_payloads = [loading.bytes()]

    play = []
    for tick in range(n_ticks + 1):
        t = tick / 100.0
        p = Bits()
        p.b(7, 8)
        p.f32(t)
        p.b(40, 8)                        # svc_packetentities
        p.s(2, 16)                        # entity count
        prev = 0
        for ent in (1, 2):
            entity_header(p, ent, prev, delta_mode=False)
            prev = ent
            seq = (tick // 5) % 3
            vals = {
                0: 10.0 + ent * 5.0 + tick * 2.0,
                1: ent * 3.0,
                2: 20.0 + tick * 0.5,
                3: 0.0, 4: 0.0, 5: 0.0,
                7: float(seq),
                8: float(tick % 10) / 30.0,
                9: t - 0.02 * ent,         # animtime slightly in the past -> cycle > 0
                10: 30.0,
            }
            write_delta(p, F, vals, t)
        p.s(0, 16)                        # end of packet
        play.append(('netmsg', p.bytes(), t, tick))
        if tick % 10 == 0:
            play.append(('clientdata', t, tick, (100.0, 50.0, 64.0), (0.0, 45.0, 90.0), 90.0))

    return loading_payloads, play


def write_file(path, loading_payloads, play_actions):
    out = bytearray()
    out += b'HLDEMO\0\0'
    out += struct.pack('<II', 5, 47)
    out += b'de_test\0'.ljust(260, b'\0')
    out += b'cstrike\0'.ljust(260, b'\0')
    out += struct.pack('<iI', 0, 0)
    assert len(out) == 544

    offsets = []
    offsets.append(len(out))
    for payload in loading_payloads:
        out += netmsg_frame(0.0, 0, payload)
    out += struct.pack('<Bfi', 5, 0.0, 0)

    offsets.append(len(out))
    for item in play_actions:
        if item[0] == 'clientdata':
            _, t, tick, origin, angles, fov = item
            out += struct.pack('<Bfi', 4, t, tick)
            out += struct.pack('<3f', *origin)
            out += struct.pack('<3f', *angles)
            out += struct.pack('<if', 0, fov)
        else:
            _, payload, t, tick = item
            out += netmsg_frame(t, tick, payload)
    out += struct.pack('<Bfi', 5, 0.0, 0)

    dir_offset = len(out)
    out += struct.pack('<i', 2)
    for i, desc in ((0, 'LOADING'), (1, 'Playback')):
        out += struct.pack('<i', i)
        out += desc.encode('latin1').ljust(64, b'\0')
        out += struct.pack('<ii', -1, -1)
        out += struct.pack('<fiii', 0.0, 0, offsets[i], len(out) - offsets[i])

    struct.pack_into('<I', out, 540, dir_offset)
    with open(path, 'wb') as f:
        f.write(bytes(out))
    print(f'wrote {path}: {len(out)} bytes')


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'synthetic.dem'
    loading, play = build_demo()
    write_file(path, loading, play)
