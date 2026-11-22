"""ask: reading the text in a picture (PNG, JPG, JPEG) for the index (#1366 slice d). Standard library only.

A picture is read on this Mac only, with the Mac's own text recognition, and is never sent anywhere. On any other system, or on a Mac
where no reader is set, `reader()` is None and the index leaves the picture out ("is a picture and this computer cannot read pictures").

THE INTERFACE. A reader is a function `read(raw: bytes) -> str` (the text found, "" for none) that raises `PictureUnreadable` for a
picture it cannot read (damaged, too big). It starts no program of its own: the Mac reader (ask_vision_mac, started through platform.py) is registered with `set_reader` by
ask_index on a Mac only; elsewhere nothing is registered and every picture is left out.
"""
from clark import platform

PICTURE_TYPES = (".png", ".jpg", ".jpeg")
MAX_PICTURE_BYTES = 20 * 1024 * 1024
_READER = None


class PictureUnreadable(ValueError):
    """A picture the reader could not read."""


def set_reader(fn):
    """Register the Mac's reader (or None to clear it)."""
    global _READER
    _READER = fn


def reader():
    """The reader to use now: only on a Mac, and only when one is registered. None otherwise."""
    return _READER if platform.system() == platform.MAC else None
