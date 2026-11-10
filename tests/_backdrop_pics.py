"""Pictures for the page-backdrop tests and by-eye shots (row 1023): real PNGs made here, so no brand file is committed.

solid(rgb) is one flat colour (the worst case for contrast: black in light, white in dark); swirl() is a soft wave of two colours, the
look of a brand's cover. decode(png_bytes) reads a screenshot back to (width, height, rows of (r, g, b)), 8-bit, not interlaced.
"""
import math
import struct
import zlib


def _chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def _png(w, h, rows):
    raw = b"".join(b"\0" + bytes(r) for r in rows)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + _chunk(b"IDAT", zlib.compress(raw, 6))
            + _chunk(b"IEND", b""))


def solid(rgb, w=650, h=245):
    return _png(w, h, [bytes(rgb) * w for _ in range(h)])


def swirl(a=(10, 30, 70), b=(60, 200, 230), w=650, h=245):
    rows = []
    for y in range(h):
        row = bytearray()
        for x in range(w):
            t = 0.5 + 0.5 * math.sin(x / 38.0 + 2.2 * math.sin(y / 31.0 + x / 120.0)) * math.cos(y / 53.0 - x / 90.0)
            row += bytes(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
        rows.append(bytes(row))
    return _png(w, h, rows)


def decode(data):
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat, w = 8, b"", 0
    while pos < len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        if kind == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
            assert depth == 8 and ctype in (2, 6) and interlace == 0, (depth, ctype, interlace)
            bpp = 3 if ctype == 2 else 4
        elif kind == b"IDAT":
            idat += body
        pos += 12 + n
    raw, stride, prev, rows, p = zlib.decompress(idat), w * bpp, bytearray(w * bpp), [], 0
    for _ in range(h):
        f, line = raw[p], bytearray(raw[p + 1:p + 1 + stride])
        p += 1 + stride
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b, c = prev[i], (prev[i - bpp] if i >= bpp else 0)
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + ((a + b) >> 1)) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line)
        prev = line
    return w, h, [[(r[x * bpp], r[x * bpp + 1], r[x * bpp + 2]) for x in range(w)] for r in rows]
