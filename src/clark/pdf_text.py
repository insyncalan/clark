"""The text of a PDF that Chrome made, for the checks on what a PDF holds (publish_pdf.py). Standard library only.

Chrome (Skia) writes classic objects with Flate streams, and shows text as hex strings of glyph numbers in fonts that carry a
ToUnicode map. This reads exactly that: each font's map, then every text-showing operator of every page stream, in order.
It is not a general PDF reader: a file it cannot make sense of gives "" or raises Undecodable, and the caller treats that as a failure, never as clean.
Two more cases are never clean either: a stream that would inflate past MAX_INFLATED (raises TooBig), and text shown in a font
with no map, or with a glyph the map does not cover (raises Undecodable), because what such text says cannot be checked.
"""
import re
import zlib

OBJ = re.compile(rb"(?<![0-9])(\d+)\s+0\s+obj\b(.*?)\bendobj", re.S)
STREAM = re.compile(rb"^(.*?)\bstream\r?\n(.*)\r?\nendstream\s*$", re.S)
HEX = r"<([0-9a-fA-F\s]*)>"
MAX_INFLATED = 64 * 1024 * 1024          # all the streams of one PDF together, after inflating
FONT = r"[^\s/\[\]()<>]+"                # a font's resource name


class TooBig(Exception):
    """The PDF would inflate to more than MAX_INFLATED bytes."""


class Undecodable(Exception):
    """Text in the PDF is in a font whose glyphs cannot be turned back into text, so it cannot be checked."""


def objects(data):
    """{number: (dictionary bytes, stream bytes or None)} with streams inflated."""
    found = {}
    room = MAX_INFLATED
    for m in OBJ.finditer(data):
        body = m.group(2)
        s = STREAM.match(body.strip(b"\r\n"))
        head, raw = (s.group(1), s.group(2)) if s else (body, None)
        if raw is not None and b"FlateDecode" in head:
            try:
                inflater = zlib.decompressobj()
                raw = inflater.decompress(raw, room + 1)
            except zlib.error as e:             # a stream that will not inflate is never skipped: what it holds cannot be checked
                raise Undecodable("a stream that cannot be inflated") from e
            else:
                room -= len(raw)
                if room < 0 or inflater.unconsumed_tail:
                    raise TooBig("a stream inflates past the limit")
                if not inflater.eof:
                    raise Undecodable("a stream that ends too soon")
        found[int(m.group(1))] = (head, raw)
    return found


def _units(hexstr):
    h = re.sub(r"\s+", "", hexstr)
    if len(h) % 4:
        h += "0" * (4 - len(h) % 4)
    raw = bytes.fromhex(h)
    return raw.decode("utf-16-be", "replace")


class Map(dict):
    """{code: text}, with `width`: how many hex digits one shown character takes (the CMap's code space says: 4 for <0000> <FFFF>)."""
    width = None


def cmap(stream):
    """{code: text} from a ToUnicode CMap."""
    text = stream.decode("latin-1")
    out = Map()
    space = re.search(r"begincodespacerange\s*<([0-9a-fA-F]+)>", text)
    if space:
        out.width = len(space.group(1))
    for block in re.findall(r"beginbfchar(.*?)endbfchar", text, re.S):
        for a, b in re.findall(HEX + r"\s*" + HEX, block):
            out[int(re.sub(r"\s+", "", a), 16)] = _units(b)
    for block in re.findall(r"beginbfrange(.*?)endbfrange", text, re.S):
        for lo, hi, rest in re.findall(HEX + r"\s*" + HEX + r"\s*(\[[^\]]*\]|<[0-9a-fA-F\s]*>)", block):
            lo, hi = int(lo, 16), int(hi, 16)
            if rest.startswith("["):
                for i, item in enumerate(re.findall(HEX, rest)):
                    out[lo + i] = _units(item)
            else:
                start = _units(rest[1:-1])
                for i in range(hi - lo + 1):
                    out[lo + i] = start[:-1] + chr(ord(start[-1]) + i) if start else ""
    return out


def _decode(hexstr, table):
    """The text of one shown string. Raises Undecodable if there is a string but no map, or a glyph the map does not cover."""
    h = re.sub(r"\s+", "", hexstr)
    if not h:
        return ""
    if table is None:
        raise Undecodable("text in a font with no map")
    width = table.width or (4 if any(k > 255 for k in table) else 2)
    out = []
    for i in range(0, len(h) - width + 1, width):
        code = int(h[i:i + width], 16)
        if code not in table:
            raise Undecodable("a glyph the font's map does not cover")
        out.append(table[code])
    return "".join(out)


def text_of(data):
    """The text shown in the PDF `data` (bytes), one run after another with a space between runs; "" if none could be read."""
    objs = objects(data)
    fonts = {}
    for num, (head, _raw) in objs.items():
        m = re.search(rb"/ToUnicode\s+(\d+)\s+0\s+R", head)
        if m and int(m.group(1)) in objs and objs[int(m.group(1))][1] is not None:
            fonts[num] = cmap(objs[int(m.group(1))][1])
    name_to_obj = {}
    for head, _raw in objs.values():
        for n, o in re.findall(rb"/(" + FONT.encode() + rb")\s+(\d+)\s+0\s+R", head):
            name_to_obj[n.decode()] = int(o)
    pieces = []
    token = re.compile(r"/(" + FONT + r")\s+[\d.]+\s+Tf|\[([^\]\[]*)\]\s*TJ|" + HEX + r"\s*Tj|\bET\b")      # no pattern here can backtrack
    for head, raw in objs.values():
        if raw is None or b"Tf" not in raw:
            continue
        table = None
        for m in token.finditer(raw.decode("latin-1")):
            if m.group(1):
                table = fonts.get(name_to_obj.get(m.group(1)))
            elif m.group(2) is not None:
                pieces.append("".join(_decode(h, table) for h in re.findall(HEX, m.group(2))))
            elif m.group(3) is not None:
                pieces.append(_decode(m.group(3), table))
            else:
                pieces.append(" ")
    return re.sub(r"[ \t]+", " ", "".join(pieces)).strip()
