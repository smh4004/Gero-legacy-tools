"""Minimal BPS patch writer/applier (byuu's format)."""
import zlib


def _num(n):
    out = bytearray()
    while True:
        x = n & 0x7F
        n >>= 7
        if n == 0:
            out.append(0x80 | x)
            return out
        out.append(x)
        n -= 1


def _readnum(d, p):
    data, shift = 0, 1
    while True:
        x = d[p]; p += 1
        data += (x & 0x7F) * shift
        if x & 0x80:
            return data, p
        shift <<= 7
        data += shift


def make(source, target, meta=b''):
    out = bytearray(b'BPS1')
    out += _num(len(source)) + _num(len(target)) + _num(len(meta)) + meta
    i, n = 0, len(target)
    trel = 0                       # TargetCopy relative pointer
    lit = bytearray(); lit_start = 0

    def flush():
        nonlocal lit
        if lit:
            out.extend(_num(((len(lit) - 1) << 2) | 1)); out.extend(lit); lit = bytearray()

    while i < n:
        j = i
        while j < n and j < len(source) and source[j] == target[j]:
            j += 1
        if j - i >= 4 or (j == n and j > i):
            flush(); out += _num(((j - i - 1) << 2) | 0); i = j; continue
        # run of one repeated byte -> 1 literal + overlapping TargetCopy
        r = i
        while r < n and target[r] == target[i] and not (r < len(source) and source[r] == target[r]):
            r += 1
        if r - i >= 16:
            lit.append(target[i]); flush()
            src = i; d = src - trel
            out += _num(((r - i - 2) << 2) | 3) + _num((abs(d) << 1) | (1 if d < 0 else 0))
            trel = src + (r - i - 1)
            i = r; continue
        lit.append(target[i]); i += 1
    flush()
    out += zlib.crc32(source).to_bytes(4, 'little')
    out += zlib.crc32(target).to_bytes(4, 'little')
    out += zlib.crc32(out).to_bytes(4, 'little')
    return bytes(out)


def apply(source, patch):
    assert patch[:4] == b'BPS1'
    p = 4
    ss, p = _readnum(patch, p); ts, p = _readnum(patch, p); ms, p = _readnum(patch, p)
    p += ms
    out = bytearray(); end = len(patch) - 12
    srel = trel = 0
    while p < end:
        d, p = _readnum(patch, p)
        act, ln = d & 3, (d >> 2) + 1
        if act == 0:
            out += source[len(out):len(out) + ln]
        elif act == 1:
            out += patch[p:p + ln]; p += ln
        elif act == 2:
            o, p = _readnum(patch, p); srel += (-1 if o & 1 else 1) * (o >> 1)
            out += source[srel:srel + ln]; srel += ln
        else:
            o, p = _readnum(patch, p); trel += (-1 if o & 1 else 1) * (o >> 1)
            for _ in range(ln):
                out.append(out[trel]); trel += 1
    assert zlib.crc32(source) == int.from_bytes(patch[-12:-8], 'little'), 'source CRC mismatch'
    assert zlib.crc32(out) == int.from_bytes(patch[-8:-4], 'little'), 'target CRC mismatch'
    return bytes(out)
