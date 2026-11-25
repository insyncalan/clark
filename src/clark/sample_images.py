"""Row 1251: the sample picture an image template can start with. Drawn here by clark, pixel by pixel (no photograph, no licence, no
file from outside), so the same bytes come out every time. Standard library only; a plain RGB PNG with no camera details.

The picture is a calm landscape: sky, sun, two hills and a path, in soft colours that read as "a sample" and not as someone's report.
Nothing in it is text (the prompt words are agreed elsewhere and are not here). Whether a sample that is not replaced is published or
flagged first is not decided (row 1251); this module only makes the picture.
"""
import struct
import zlib

__all__ = ("sample_png", "SAMPLE_WIDTH", "SAMPLE_HEIGHT", "VARIANTS")

SAMPLE_WIDTH = 1200
SAMPLE_HEIGHT = 675                                   # 16:9, the shape the full width image frames to

# Variant 0 is the one picture (unchanged); 1 to 5 are the same scene in other soft colours and with the sun in another place, so the
# six samples (now used by the picture templates other than the gallery) are six different pictures. Each: sky top, sky low, sun, far hill, near hill, near hill's foot, path, sun x.
_PALETTES = (
    ((176, 205, 232), (232, 238, 244), (246, 226, 168), (150, 178, 170), (112, 150, 128), (96, 134, 112), (222, 214, 190), 0.78),
    ((232, 200, 190), (248, 232, 222), (250, 236, 190), (170, 160, 176), (132, 124, 150), (114, 106, 134), (226, 214, 200), 0.22),
    ((190, 214, 214), (236, 244, 240), (248, 238, 200), (140, 176, 160), (96, 142, 116), (80, 124, 100), (224, 220, 196), 0.60),
    ((200, 196, 228), (238, 236, 248), (250, 230, 200), (160, 170, 196), (120, 134, 170), (104, 118, 154), (220, 218, 204), 0.40),
    ((226, 214, 176), (246, 240, 220), (250, 220, 170), (176, 170, 130), (140, 142, 104), (122, 126, 90), (230, 222, 196), 0.85),
    ((178, 200, 224), (226, 236, 246), (240, 232, 214), (136, 160, 184), (100, 130, 160), (84, 114, 144), (214, 212, 200), 0.15),
)
VARIANTS = len(_PALETTES)


def _mix(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _pixel(x, y, w, h, pal):
    sky_top, sky_low, sun, hill_far, hill_near, foot, path, sun_x = pal
    far = h * (0.62 + 0.06 * (1 - ((x / w) - 0.3) ** 2 * 4))        # the far hill's top edge
    near = h * (0.74 - 0.10 * ((x / w) - 0.75) ** 2 * 4)             # the near hill's top edge
    if y >= near:
        if abs(x - (w * 0.5 + (y - near) * 0.9)) < (y - near) * 0.35 + 6:
            return path
        return _mix(hill_near, foot, (y - near) / (h - near))
    if y >= far:
        return hill_far
    if (x - w * sun_x) ** 2 + (y - h * 0.26) ** 2 < (h * 0.09) ** 2:
        return sun
    return _mix(sky_top, sky_low, y / far)


def sample_png(w=SAMPLE_WIDTH, h=SAMPLE_HEIGHT, variant=0):
    """The sample picture as PNG bytes: the same every call. `variant` 0 to 5 (the six samples, now used by the picture templates other than the gallery)."""
    pal = _PALETTES[variant]
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    rows = bytearray()
    for y in range(h):
        rows.append(0)
        for x in range(w):
            rows.extend(_pixel(x, y, w, h, pal))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b""))
