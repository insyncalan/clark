"""A tiny PNG writer for the Word export's pictures (#1012): standard library only (zlib and struct), no Pillow, no other package.

A Canvas is a grid of palette indexes (one byte a pixel), so a picture is small and the colours are exactly the ones the caller
names (the design tokens, never a colour made here). Shapes are drawn without smoothing: filled rectangles, lines, filled
polygons and circles, rings and dashed lines. Every shape is clipped to the canvas, so a wild coordinate costs nothing and cannot
write outside it. A canvas bigger than MAX_PIXELS is refused before any memory is taken.

png() gives an indexed-colour PNG (colour type 3, 8 bits): the signature, IHDR, PLTE, one IDAT (rows with filter 0, deflated)
and IEND, each chunk with its CRC. The same canvas always gives the same bytes. Python 3.9.
"""
import math
import struct
import zlib

SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_PIXELS = 4_000_000
MAX_COLOURS = 256


class DrawError(ValueError):
    """The picture cannot be made (too large, too many colours, a colour that is not six hex digits)."""


def rgb(hex6):
    """(r, g, b) from six hex digits, with or without #."""
    s = str(hex6).lstrip("#")
    if len(s) != 6:
        raise DrawError("a colour is six hex digits")
    try:
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    except ValueError:
        raise DrawError("a colour is six hex digits") from None


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


class Canvas:
    def __init__(self, width, height, background):
        width, height = int(width), int(height)
        if width < 1 or height < 1 or width * height > MAX_PIXELS:
            raise DrawError("the picture is too large")
        self.w, self.h = width, height
        self.colours = []                              # hex strings, upper case; the index is the palette index
        self.px = bytearray([self.index(background)]) * (width * height)

    def index(self, hex6):
        h = str(hex6).lstrip("#").upper()
        rgb(h)
        if h not in self.colours:
            if len(self.colours) >= MAX_COLOURS:
                raise DrawError("too many colours")
            self.colours.append(h)
        return self.colours.index(h)

    def at(self, x, y):
        """The colour (six hex digits) of the pixel at x, y; None outside the canvas."""
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.colours[self.px[y * self.w + x]]
        return None

    def rect(self, x0, y0, x1, y1, colour):
        """Fill x0 <= x < x1, y0 <= y < y1."""
        c = self.index(colour)
        x0, x1 = max(0, int(x0)), min(self.w, int(x1))
        for y in range(max(0, int(y0)), min(self.h, int(y1))):
            if x1 > x0:
                self.px[y * self.w + x0:y * self.w + x1] = bytes([c]) * (x1 - x0)

    def hline(self, x0, x1, y, colour, thick=1, dash=None):
        """A horizontal line from x0 to x1 (inclusive); dash=(on, off) draws it in dashes."""
        x0, x1 = int(min(x0, x1)), int(max(x0, x1))
        if not dash:
            return self.rect(x0, y - thick // 2, x1 + 1, y - thick // 2 + thick, colour)
        on, off = max(1, dash[0]), max(1, dash[1])
        x = max(x0, -on)
        while x <= min(x1, self.w):
            self.rect(x, y - thick // 2, min(x + on, x1 + 1), y - thick // 2 + thick, colour)
            x += on + off

    def vline(self, x, y0, y1, colour, thick=1):
        self.rect(x - thick // 2, min(y0, y1), x - thick // 2 + thick, max(y0, y1) + 1, colour)

    def line(self, x0, y0, x1, y1, colour, thick=1):
        """Any line, as small squares along it."""
        n = int(max(abs(x1 - x0), abs(y1 - y0), 1))
        n = min(n, 2 * (self.w + self.h))
        for i in range(n + 1):
            x, y = round(x0 + (x1 - x0) * i / n), round(y0 + (y1 - y0) * i / n)
            self.rect(x - thick // 2, y - thick // 2, x - thick // 2 + thick, y - thick // 2 + thick, colour)

    def polygon(self, points, colour):
        """Fill a polygon (even-odd), scanline by scanline."""
        c = self.index(colour)
        ys = [p[1] for p in points]
        for y in range(max(0, math.ceil(min(ys))), min(self.h, math.floor(max(ys)) + 1)):
            xs = []
            for (ax, ay), (bx, by) in zip(points, points[1:] + points[:1]):
                if (ay <= y < by) or (by <= y < ay):
                    xs.append(ax + (y - ay) * (bx - ax) / (by - ay))
            xs.sort()
            for a, b in zip(xs[0::2], xs[1::2]):
                x0, x1 = max(0, round(a)), min(self.w, round(b) + 1)
                if x1 > x0:
                    self.px[y * self.w + x0:y * self.w + x1] = bytes([c]) * (x1 - x0)

    def circle(self, cx, cy, r, colour, inner=0, dashed=False):
        """A disc of radius r, or a ring when inner > 0 (the hole's radius); dashed leaves gaps round a ring."""
        c = self.index(colour)
        r2, i2 = r * r, inner * inner
        for y in range(max(0, math.floor(cy - r)), min(self.h, math.ceil(cy + r) + 1)):
            for x in range(max(0, math.floor(cx - r)), min(self.w, math.ceil(cx + r) + 1)):
                d = (x - cx) ** 2 + (y - cy) ** 2
                if i2 <= d <= r2 and not (dashed and int(math.atan2(y - cy, x - cx) / (2 * math.pi) * 12) % 2):
                    self.px[y * self.w + x] = c

    def png(self):
        rows = b"".join(b"\x00" + bytes(self.px[y * self.w:(y + 1) * self.w]) for y in range(self.h))
        palette = b"".join(bytes(rgb(c)) for c in self.colours)
        return (SIGNATURE + chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 3, 0, 0, 0)) + chunk(b"PLTE", palette)
                + chunk(b"IDAT", zlib.compress(rows, 6)) + chunk(b"IEND", b""))
