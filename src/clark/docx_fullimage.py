"""Row 1223: the Full width image (an imagecap section with a body of version 2) in the Word report. Pure: reads the framed image the
published file carries (a data: address of a PNG or JPEG) and its pixel size from its own header, and works out how wide Word draws it.
No drawing XML here (docx_build.py makes it).

The image in the file is already the framed copy (the part cropped or framed out is not in it), so it is drawn whole. Word cannot blur,
so a small image's blurred fill is drawn as a quiet grey band; brand colour and plain are kept."""
import base64
import re

DATA = re.compile(r"^data:image/(png|jpeg);base64,([A-Za-z0-9+/]+={0,2})$")
PX_TWIPS = 15                       # one screen pixel (96 per inch) is 15 twentieths of a point
MAX_HEIGHT = 11000                  # twentieths of a point: about 19 cm, so one image fits on an A4 page under its caption
WORDS_DEFAULT = ""                  # no description: the picture's alternative text is left empty, never invented


def decode(address):
    """(bytes, 'png' or 'jpeg', width px, height px) of a data: address, or None when it is not a PNG or JPEG clark can size."""
    m = DATA.match(address) if isinstance(address, str) else None
    if not m:
        return None
    try:
        raw = base64.b64decode(m.group(2), validate=True)
    except ValueError:
        return None
    size = png_size(raw) if m.group(1) == "png" else jpeg_size(raw)
    return (raw, m.group(1), size[0], size[1]) if size and size[0] > 0 and size[1] > 0 else None


def png_size(raw):
    if raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[12:16] != b"IHDR":
        return None
    return int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big")


def jpeg_size(raw):
    if raw[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 < len(raw):
        if raw[i] != 0xFF:
            return None
        marker = raw[i + 1]
        if marker == 0xFF:
            i += 1
            continue
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        length = int.from_bytes(raw[i + 2:i + 4], "big")
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            return int.from_bytes(raw[i + 7:i + 9], "big"), int.from_bytes(raw[i + 5:i + 7], "big")
        i += 2 + length
    return None


def width_twips(w, h, text_w, stretch):
    """How wide Word draws it: the text width, but an image narrower than the text sits at its own size (never enlarged) unless `stretch`.
    Never taller than MAX_HEIGHT, the shape kept."""
    wide = text_w if stretch else min(text_w, w * PX_TWIPS)
    return max(1, min(wide, MAX_HEIGHT * w // h))
