"""Port a Legacy of Goku II song into Buu's Fury (both use Webfoot's sequencer).

Song table entries (BF 0x083BB78C, LoG2 slice 0x1D4BE4; 20 bytes): [u32 track list][u32 song data start][u32 sample
bank][u32 bank B][u32 tempo | channels << 8]. The song data runs from its start to the track list, a list of absolute
pointers into the data that ends where the next song's data starts. The sample bank = 101 12-byte records [u32 sample
ptr][u32][u32 rate << 16 | length]; LoG2's samples all lie in 0x088E4148..0x0894A95C.
Porting one song alone (bank B + that song) played nothing; keeping LoG2's layout from bank B through song 0 (bank B is
read past its 14 bytes, into song 0's data) works, so a port copies: the sample block, the bank (sample pointers
relocated), bank B + song 0 (track list relocated), then the wanted song (track list relocated), and points a BF table
entry at it. BF song 45 = the startup song (intro + title screen). LoG2 song 7 = "Era of Darkness" (matched against the
user's MP3, envelope correlation 0.97; next best 0.69)."""
import struct
BF_TABLE, L2_TABLE = 0x3BB78C, 0x1D4BE4
L2B, BASE = 0x08800000, 0x08000000
L2_SAMPLES, L2_BANK, L2_BANKB, L2_NREC = 0x088E4148, 0x0894A95C, 0x0894AE18, 101


def _song(l2, k):
    """(data bytes [start .. end of the track list], start, end)"""
    end, start = struct.unpack_from('<2I', l2, L2_TABLE + 20 * k)
    nxt = struct.unpack_from('<I', l2, L2_TABLE + 20 * (k + 1) + 4)[0]
    return bytearray(l2[start - L2B:nxt - L2B]), start, end


def _reloc(data, start, end, new):
    for o in range(end - start, len(data), 4):
        p = struct.unpack_from('<I', data, o)[0]
        assert start <= p < end, 'track pointer %x outside the song' % p
        struct.pack_into('<I', data, o, p - start + new)


def port(rom, l2, song, at, slot=45):
    """Copy LoG2 song `song` (with LoG2's sample set) to ROM offset `at`; BF entry `slot` plays it. Returns the end."""
    tempo = struct.unpack_from('<I', l2, L2_TABLE + 20 * song + 16)[0]
    smp = l2[L2_SAMPLES - L2B:L2_BANK - L2B]
    rom[at:at + len(smp)] = smp; s_at = at; at = (at + len(smp) + 3) & ~3
    bk = bytearray(l2[L2_BANK - L2B:L2_BANK - L2B + 12 * L2_NREC])
    for i in range(L2_NREC):
        struct.pack_into('<I', bk, 12 * i, struct.unpack_from('<I', bk, 12 * i)[0] - L2_SAMPLES + BASE + s_at)
    rom[at:at + len(bk)] = bk; b_at = at; at += len(bk)
    bb = l2[L2_BANKB - L2B:L2_BANKB - L2B + 14]
    rom[at:at + 14] = bb; bb_at = at; at += 14
    s0, st0, en0 = _song(l2, 0); assert st0 == L2_BANKB + 14
    _reloc(s0, st0, en0, BASE + at); rom[at:at + len(s0)] = s0; at += len(s0)
    if song:
        at = (at + 3) & ~3
        d, st, en = _song(l2, song); _reloc(d, st, en, BASE + at); rom[at:at + len(d)] = d; d_at = at; at += len(d)
    else:
        d_at, st, en = bb_at + 14, st0, en0
    struct.pack_into('<5I', rom, BF_TABLE + 20 * slot, BASE + d_at + (en - st), BASE + d_at, BASE + b_at, BASE + bb_at, tempo)
    return (at + 3) & ~3


def add(rom, l2, song, at, slot, ref_slot=45):
    """Another LoG2 song sharing the samples, bank and bank B + song 0 that port() already placed for `ref_slot`."""
    tempo = struct.unpack_from('<I', l2, L2_TABLE + 20 * song + 16)[0]
    b_at, bb_at = struct.unpack_from('<2I', rom, BF_TABLE + 20 * ref_slot + 8)
    if song == 0:                                    # song 0 already sits right after bank B (port keeps that layout)
        d, st, en = _song(l2, 0)
        struct.pack_into('<5I', rom, BF_TABLE + 20 * slot, bb_at + 14 + (en - st), bb_at + 14, b_at, bb_at, tempo)
        return at
    d, st, en = _song(l2, song); _reloc(d, st, en, BASE + at); rom[at:at + len(d)] = d
    struct.pack_into('<5I', rom, BF_TABLE + 20 * slot, BASE + at + (en - st), BASE + at, b_at, bb_at, tempo)
    return (at + len(d) + 3) & ~3


def apply_plan(rom, l2, plan, at, area_entry):
    """log4/music.json: LoG2 songs into free BF slots, BF table-entry copies, and each area's track (AreaEntry +0x24).
    Track names: "BF n" (BF song table index) or "LoG2 n" (mapped through l2_slots; LoG2 7 = slot 45)."""
    l2_slots = {int(k): v for k, v in plan['l2_slots'].items()}
    for k, slot in sorted(l2_slots.items()):
        if slot != 45: at = add(rom, l2, k, at, slot)
    bf0 = bytes(rom[BF_TABLE:BF_TABLE + 20 * 53])                 # copies read the table as it was before them
    for dst, src in plan.get('copies', {}).items():
        rom[BF_TABLE + 20 * int(dst):BF_TABLE + 20 * int(dst) + 20] = bf0[20 * src:20 * src + 20]
    n = 0
    for track, areas in plan['areas'].items():
        g, k = track.split(); k = int(k)
        idx = k if g == 'BF' else l2_slots[k]
        for wa in areas:
            w, a = map(int, wa.split(':'))
            struct.pack_into('<I', rom, area_entry(rom, w, a) + 0x24, idx); n += 1
    return at, n
