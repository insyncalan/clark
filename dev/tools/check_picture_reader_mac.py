"""Check the Mac's picture reader (#1366): draws a picture of the words "CLARK PICTURE TEST", reads it with the same reader clark uses
(src/clark/ask_vision_mac.py, the Vision framework through the system's osascript) and says PASS or FAIL.

Run on a Mac, from the folder of a clark source checkout (standard library only, nothing is sent anywhere, no file is left behind
except the picture if you ask for it):
    python3 dev/tools/check_picture_reader_mac.py              # prints PASS or FAIL, the text it recognised and the time
    python3 dev/tools/check_picture_reader_mac.py --keep pic.png   # also saves the picture it drew, to look at

PASS: the words clark, picture and test were all recognised (capitals or not). Exit 0 for PASS, 1 for FAIL, 2 when this is not a Mac.
The picture is drawn here with Python's zlib and struct from a 5x7 letter shape, scaled up (black letters on white).
This script is the only proof that Vision reads a picture: the tests on other systems use a stand-in.
"""
import os
import struct
import sys
import time
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

TEXT = "CLARK PICTURE TEST"
EXPECTED = ("clark", "picture", "test")
SCALE = 8
GLYPHS = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    " ": ("00000",) * 7,
}


def make_png(text=TEXT, scale=SCALE, margin=4):
    """PNG bytes (8-bit grey) of `text` in black on white, from the 5x7 letters above, each dot `scale` pixels wide."""
    cols = len(text) * 6 - 1                       # 5 columns a letter and 1 between
    width, height = (cols + 2 * margin) * scale, (7 + 2 * margin) * scale
    rows = []
    for y in range(height):
        gy = y // scale - margin
        line = bytearray([255] * width)
        if 0 <= gy < 7:
            for i, ch in enumerate(text):
                for gx, bit in enumerate(GLYPHS[ch][gy]):
                    if bit == "1":
                        x0 = (margin + i * 6 + gx) * scale
                        line[x0:x0 + scale] = bytes(scale)
        rows.append(b"\x00" + bytes(line))         # filter type 0 for every row

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b"")


def main(argv):
    if sys.platform != "darwin":
        print("FAIL: this check runs on a Mac only (this system is %s)" % sys.platform)
        return 2
    png = make_png()
    if "--keep" in argv and argv.index("--keep") + 1 < len(argv):
        with open(argv[argv.index("--keep") + 1], "wb") as f:
            f.write(png)
    from clark import ask_picture, ask_vision_mac
    start = time.monotonic()
    try:
        text = ask_vision_mac.read(png)
        problem = ""
    except ask_picture.PictureUnreadable as e:
        text, problem = "", "the reader said it could not read the picture (%s)" % e
    seconds = time.monotonic() - start
    low = text.lower()
    missing = [w for w in EXPECTED if w not in low]
    ok = not problem and not missing
    print("%s: recognised %r in %.2f seconds%s" % ("PASS" if ok else "FAIL", text, seconds,
                                                  "" if ok else " (" + (problem or "missing: " + ", ".join(missing)) + ")"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
