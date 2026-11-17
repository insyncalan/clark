"""Row 1251: the sample picture an image template can start with. Drawn here by clark, pixel by pixel (no photograph, no licence, no
file from outside), so the same bytes come out every time. Standard library only; a plain RGB PNG with no camera details.

The picture is a calm landscape: sky, sun, two hills and a path, in soft colours that read as "a sample" and not as someone's report.
Nothing in it is text (the prompt words are agreed elsewhere and are not here). Whether a sample that is not replaced is published or
flagged first is not decided (row 1251); this module only makes the picture.
"""
import struct
import zlib

__all__ = ("sample_png", "SAMPLE_WIDTH", "SAMPLE_HEIGHT")

SAMPLE_WIDTH = 1200
SAMPLE_HEIGHT = 675                                   # 16:9, the shape the full width image frames to

_SKY_TOP, _SKY_LOW = (176, 205, 232), (232, 238, 244)
_SUN, _HILL_FAR, _HILL_NEAR, _PATH = (246, 226, 168), (150, 178, 170), (112, 150, 128), (222, 214, 190)


def _mix(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _pixel(x, y, w, h):
    far = h * (0.62 + 0.06 * (1 - ((x / w) - 0.3) ** 2 * 4))        # the far hill's top edge
    near = h * (0.74 - 0.10 * ((x / w) - 0.75) ** 2 * 4)             # the near hill's top edge
    if y >= near:
        if abs(x - (w * 0.5 + (y - near) * 0.9)) < (y - near) * 0.35 + 6:
            return _PATH
        return _mix(_HILL_NEAR, (96, 134, 112), (y - near) / (h - near))
    if y >= far:
        return _HILL_FAR
    if (x - w * 0.78) ** 2 + (y - h * 0.26) ** 2 < (h * 0.09) ** 2:
        return _SUN
    return _mix(_SKY_TOP, _SKY_LOW, y / far)


def sample_png(w=SAMPLE_WIDTH, h=SAMPLE_HEIGHT):
    """The sample picture as PNG bytes: the same every call."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    rows = bytearray()
    for y in range(h):
        rows.append(0)
        for x in range(w):
            rows.extend(_pixel(x, y, w, h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b""))
