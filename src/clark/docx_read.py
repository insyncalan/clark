"""Read the text of a Word file (.docx) as a plain list of blocks (#48; BRD FR-72, design-48-word.md sections 4 to 6).

A pure function: `read(data, name)` takes the file's bytes (never a path), opens nothing else, starts nothing and calls nothing
outside this module, and returns `Read(blocks, notes)`. The blocks, in document order, are plain dicts:
  {"kind": "heading", "level": 1..9, "text": ...}     (a Title is level 1)
  {"kind": "paragraph", "text": ...}
  {"kind": "list_item", "level": 0..8, "ordered": bool, "text": ...}
  {"kind": "table", "rows": [[cell text, ...], ...]}   (a nested table is flattened into its cell's text)
`notes` are plain-words sentences about what was not read (hidden text, pictures and text boxes, link addresses, comments).
Text only: no styling, no pictures, no comments, and a link's address is never read (its words stay).

A file from outside is hostile until read. Anything unsafe raises WordRefused, whose message is plain words naming the file, and
nothing is returned. The rules are the table in design-48-word.md section 5:
- size: the file, the unpacked size of every part (added up from the directory first, and each part is then read through a limit),
  the number of parts, a very high squeeze ratio; a part stored any way but stored or deflated is refused;
- names: `..`, a leading / or \\, a drive letter, a backslash, a control character, a repeated name (case ignored);
- a damaged, cut short or empty file; a password (the flag in the directory, or an older Office file); no main text;
- macros (a vba part, a macro-enabled content type), embedded objects (word/embeddings, word/activeX, an oleObject or package
  relationship), and any relationship that points outside the file except a hyperlink (an attached template, a linked picture);
- XML: any <!DOCTYPE or <!ENTITY (billion laughs, external and parameter entities) is refused by the parser's own handlers as well
  as by a scan, text that is not UTF-8 or declares another encoding, and a stream deeper than MAX_DEPTH or longer than MAX_ELEMENTS;
- a paragraph over MAX_PARAGRAPH characters, more than MAX_BLOCKS blocks or MAX_TEXT characters in all.
The XML is read as a stream with the parser in pyexpat, with no tree, so memory stays small and a limit stops the read at once. No
entity is ever defined, so none is fetched; a test makes any network call fail.

Text a person cannot see is not read: deleted text of tracked changes (inserted text is read), runs marked hidden, text in text boxes
and pictures. Zero-width, direction-control and tag characters are removed, as are control characters.

Standard library only, Python 3.9.
"""
import io
import re
import unicodedata
import zipfile
import zlib
from typing import NamedTuple
from xml.parsers import expat

MAX_FILE_BYTES = 25 * 1024 * 1024        # the file as saved (as excel.MAX_FILE_BYTES)
MAX_UNPACKED_BYTES = 50 * 1024 * 1024    # all its parts, unpacked (as excel.MAX_UNPACKED_BYTES)
MAX_PART_BYTES = 20 * 1024 * 1024        # any one part, unpacked
MAX_MEMBERS = 200                        # parts in the zip (as excel.MAX_MEMBERS)
MAX_RATIO = 200                          # unpacked : packed, for a part over RATIO_FROM
RATIO_FROM = 1024 * 1024
SMALL_PART_BYTES = 2 * 1024 * 1024       # the content types, relationships, styles and numbering: small by nature
MAX_DEPTH = 64                           # open elements
MAX_ELEMENTS = 2_000_000
MAX_PARAGRAPH = 200_000                  # characters in one paragraph (sanitise.MAX_CHARS)
MAX_BLOCKS = 50_000
MAX_TEXT = 5_000_000                     # characters in all
CHUNK = 64 * 1024

W_NAMESPACES = ("http://schemas.openxmlformats.org/wordprocessingml/2006/main",     # transitional (what Word writes)
                "http://purl.oclc.org/ooxml/wordprocessingml/main")                  # strict
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"      # an older Word file, or an Office file with a password

# Elements whose whole content is not read: deleted text, pictures and drawings, text boxes, the old-style fallback of a drawing.
SKIP = {"del", "moveFrom", "drawing", "pict", "object", "txbxContent", "delText", "instrText", "delInstrText"}
NOT_TEXT = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ud800-\udfff￾￿]")
UNSEEN = re.compile("[​-‏‪-‮⁠-⁤⁦-⁩﻿\U000e0000-\U000e007f]")
SPACES = re.compile(r"[ \t  -   　]+")
HEADING_NAME = re.compile(r"heading\s*([1-9])")
HEADING_ID = re.compile(r"[Hh]eading([1-9])")
DOCTYPE = re.compile(r"<!\s*(doctype|entity)", re.I)
ENCODING = re.compile(r"""\A﻿?\s*<\?xml[^>]*?\bencoding\s*=\s*["']([^"']+)["']""", re.I)

MACRO_NAME = re.compile(r"(^|/)vba(project|data|projectsignature)", re.I)
HYPERLINK_TYPES = ("http://schemas.openxmlformats.org/officedocument/2006/relationships/hyperlink",      # compared lower case
                   "http://purl.oclc.org/ooxml/officedocument/relationships/hyperlink")
EMBED_NAME = re.compile(r"^word/(embeddings|activex)/|oleobject", re.I)
BAD_TYPE = ("macroenabled", "vbaproject", "oleobject", "activex", "ms-office.vba")
EMBED_REL = ("/oleobject", "/package", "/activexcontrol", "/vbaproject", "/vbadata", "/vbaprojectsignature")


class WordRefused(ValueError):
    """The file was not read, in words a person can act on. Nothing was returned."""


class Read(NamedTuple):
    blocks: list
    notes: list


def _mb(n):
    return f"{n / 1048576:.1f} MB"


# ===== The plain-words messages (design-48-word.md section 6) =====
def _damaged(name):
    return WordRefused(f"{name} could not be opened. It may be damaged, or it may not be a Word file. Open it in Word and save a "
                       "copy, then choose it again.")


def _password(name):
    return WordRefused(f"{name} is password protected, or is an older kind of Word file. Open it in Word, remove the password "
                       "and save a copy as a Word document, then choose it again.")


def _not_safe(name):
    """One text for the three files that cannot be read safely (an odd packing, text clark can't read, something inside it)."""
    return WordRefused(f"{name} could not be read safely, so it was not opened. Open it in Word, save a copy, and choose the copy.")


def _too_big(name, kind, got, most):
    if kind == "file":
        return WordRefused(f"{name} is {_mb(got)}, more than the {_mb(most)} clark will open. "
                           "Save a smaller copy and try again.")
    return WordRefused(f"{name} would open to about {_mb(got)}, more than the {_mb(most)} clark will open, so it was not read. "
                       "Remove large pictures or split it, then try again.")


def _too_complex(name):
    return WordRefused(f"{name} is too complex for clark to read, so it was not read. Save a simpler copy and try again.")


# ===== The zip =====
def _check_names_and_sizes(name, infos):
    """Refuse a zip whose directory is hostile, before any part is read."""
    if len(infos) > MAX_MEMBERS:
        raise _too_complex(name)
    seen, total = set(), 0
    for i in infos:
        n = i.filename
        parts = n.split("/")
        if (not n or "\\" in n or n.startswith("/") or re.match(r"[A-Za-z]:", n) or ".." in parts or len(n) > 255
                or any(ord(c) < 32 or ord(c) == 127 for c in n)):
            raise _not_safe(name)
        key = n.casefold()
        if key in seen:
            raise _not_safe(name)
        seen.add(key)
        if i.flag_bits & 0x1 or i.flag_bits & 0x40:
            raise _password(name)
        if i.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise _damaged(name)
        if i.file_size > MAX_PART_BYTES:
            raise _too_big(name, "part", i.file_size, MAX_PART_BYTES)
        if i.file_size > RATIO_FROM and i.file_size > MAX_RATIO * max(i.compress_size, 1):
            raise _not_safe(name)
        total += i.file_size
    if total > MAX_UNPACKED_BYTES:
        raise _too_big(name, "all", total, MAX_UNPACKED_BYTES)


def _part(z, name, part, limit=MAX_PART_BYTES):
    """The bytes of one part, read through a limit (a size the directory understated is stopped here too)."""
    try:
        member = z.open                                # a zip member is read as bytes, never as text
        with member(part) as f:
            raw = f.read(limit + 1)
    except (zipfile.BadZipFile, zlib.error, EOFError, OverflowError, NotImplementedError, RuntimeError, ValueError, OSError):
        raise _damaged(name) from None
    if len(raw) > limit:
        raise _too_big(name, "part", len(raw), limit)
    return raw


# ===== The XML, as a stream =====
class _Stop(Exception):
    """Raised inside a handler to end the read at once."""


def _local(tag):
    ns, _, local = tag.rpartition("|")
    return ns, local


def _attr(attrs, local):
    """The value of the attribute `local` (any namespace, as Word writes w:val), or None."""
    for k, v in attrs.items():
        if k.rpartition("|")[2] == local:
            return v
    return None


def _run(name, raw, start=None, end=None, text=None):
    """Feed one XML part to the callbacks as a stream. Refuses a DOCTYPE or an entity (the parser's own handlers say so too), text
    that is not UTF-8, another declared encoding, a stream too deep or too long, and anything the parser calls an error."""
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise _not_safe(name) from None
    m = ENCODING.match(decoded[:300])
    if (m and m.group(1).lower().replace("_", "-") not in ("utf-8", "utf8")) or DOCTYPE.search(decoded) or "\x00" in decoded:
        raise _not_safe(name)
    state = {"depth": 0, "elements": 0}
    p = expat.ParserCreate(namespace_separator="|")

    def refuse(*_args):
        raise _Stop(_not_safe(name))

    def on_start(tag, attrs):
        state["depth"] += 1
        state["elements"] += 1
        if state["depth"] > MAX_DEPTH or state["elements"] > MAX_ELEMENTS:
            raise _Stop(_not_safe(name))
        if start:
            start(tag, attrs, state["depth"])

    def on_end(tag):
        if end:
            end(tag, state["depth"])
        state["depth"] -= 1

    p.StartElementHandler, p.EndElementHandler = on_start, on_end
    if text:
        p.CharacterDataHandler = text
        p.buffer_text = True
    p.StartDoctypeDeclHandler = refuse
    p.EntityDeclHandler = refuse
    p.ExternalEntityRefHandler = refuse
    p.SkippedEntityHandler = refuse
    p.NotationDeclHandler = refuse
    p.UnparsedEntityDeclHandler = refuse
    p.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    try:
        for i in range(0, len(raw), CHUNK):
            p.Parse(raw[i:i + CHUNK], False)
        p.Parse(b"", True)
    except _Stop as e:
        raise e.args[0] from None
    except expat.ExpatError:
        raise _damaged(name) from None
    except (RecursionError, MemoryError):
        raise _not_safe(name) from None


# ===== The small parts: content types, relationships, styles, numbering =====
def _check_types(name, raw):
    """Refuse a macro-enabled or object content type; return the main document's content type."""
    found = {}

    def start(tag, attrs, depth):
        ns, local = _local(tag)
        if ns == CT_NS and local in ("Default", "Override"):
            ctype = _attr(attrs, "ContentType") or ""
            if any(b in ctype.lower() for b in BAD_TYPE):
                found["bad"] = ctype
            if local == "Override" and _attr(attrs, "PartName") == "/word/document.xml":
                found["main"] = ctype

    _run(name, raw, start)
    if "bad" in found:
        raise _macros_or_objects(name, found["bad"])
    return found.get("main", "")


def _macros_or_objects(name, what):
    w = what.lower()
    if "macro" in w or "vba" in w:
        return WordRefused(f"{name} has macros in it, and clark never opens macros. Open it in Word and save a copy as an ordinary "
                           "Word document (the type that cannot hold macros), then choose it again.")
    return WordRefused(f"{name} has a file or object inside it (such as a spreadsheet). clark won't open it. Remove it in Word "
                       "and save a copy.")


def _check_rels(name, raw):
    """Refuse an embedded object, a macro, or a relationship that points outside the file and is not a hyperlink."""
    def start(tag, attrs, depth):
        ns, local = _local(tag)
        if ns == REL_NS and local == "Relationship":
            rtype = (_attr(attrs, "Type") or "").lower()
            if rtype.endswith(EMBED_REL):
                raise _Stop(_macros_or_objects(name, rtype))
            if (_attr(attrs, "TargetMode") or "").lower() == "external" and rtype not in HYPERLINK_TYPES:
                raise _Stop(WordRefused(f"{name} is linked to something outside the file (a template or a picture at an address). "
                                        "clark won't open it. Break the link in Word and save a copy."))

    _run(name, raw, start)


def _styles(name, raw):
    """{style id: {"name", "outline", "based", "num"}} from styles.xml (the parts of a style that say heading or list)."""
    out, cur = {}, {}
    flags = {"numpr": False}

    def start(tag, attrs, depth):
        ns, local = _local(tag)
        if ns not in W_NAMESPACES:
            return
        val = _attr(attrs, "val")
        if local == "style":
            cur.clear()
            cur.update(id=_attr(attrs, "styleId"), name="", outline=None, based=None, num=None, ilvl=0)
        elif not cur:
            return
        elif local == "name" and depth == 3:
            cur["name"] = (val or "").lower()
        elif local == "basedOn" and depth == 3:
            cur["based"] = val
        elif local == "outlineLvl":
            cur["outline"] = _int(val)
        elif local == "numPr":
            flags["numpr"] = True
        elif flags["numpr"] and local == "numId":
            cur["num"] = val
        elif flags["numpr"] and local == "ilvl":
            cur["ilvl"] = _int(val) or 0

    def end(tag, depth):
        ns, local = _local(tag)
        if ns in W_NAMESPACES and local == "numPr":
            flags["numpr"] = False
        elif ns in W_NAMESPACES and local == "style" and cur.get("id"):
            out[cur["id"]] = dict(cur)
            cur.clear()

    _run(name, raw, start, end)
    return out


def _numbering(name, raw):
    """{numId: {ilvl: numFmt}} from numbering.xml."""
    abstract, nums, ctx = {}, {}, {}

    def start(tag, attrs, depth):
        ns, local = _local(tag)
        if ns not in W_NAMESPACES:
            return
        val = _attr(attrs, "val")
        if local == "abstractNum":
            ctx.clear()
            ctx["abs"] = _attr(attrs, "abstractNumId")
            abstract.setdefault(ctx["abs"], {})
        elif local == "lvl" and "abs" in ctx:
            ctx["lvl"] = _int(_attr(attrs, "ilvl")) or 0
        elif local == "numFmt" and "abs" in ctx and "lvl" in ctx:
            abstract[ctx["abs"]].setdefault(ctx["lvl"], val)
        elif local == "num":
            ctx.clear()
            ctx["num"] = _attr(attrs, "numId")
        elif local == "abstractNumId" and "num" in ctx:
            nums[ctx["num"]] = val

    def end(tag, depth):
        ns, local = _local(tag)
        if ns in W_NAMESPACES and local == "abstractNum":
            ctx.clear()

    _run(name, raw, start, end)
    return {n: abstract.get(a, {}) for n, a in nums.items()}


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


# ===== The text =====
def clean_text(text):
    """One paragraph's text: control, zero-width, direction and tag characters removed, spaces squeezed, each line trimmed, blank
    lines dropped (a line break inside a paragraph stays as a newline)."""
    text = UNSEEN.sub("", NOT_TEXT.sub("", text))
    lines = (SPACES.sub(" ", unicodedata.normalize("NFC", ln)).strip() for ln in text.split("\n"))
    return "\n".join(ln for ln in lines if ln)


class _Body:
    """The state of one pass over word/document.xml."""

    def __init__(self, name, styles, numbering):
        self.name, self.styles, self.numbering = name, styles, numbering
        self.blocks, self.counts = [], {"hidden": 0, "pictures": 0, "links": 0}
        self.skip = 0                 # the depth of the element being skipped, or 0
        self.para = None              # the paragraph being read
        self.run_hidden = False
        self.in_run = False
        self.in_t = False
        self.in_ppr = False
        self.in_numpr = False
        self.tables = []              # open tables: {"rows": [...], "row": [...], "cell": [...]}
        self.total = 0
        self.body_seen = False

    def refuse_long(self):
        return WordRefused(f"One paragraph in {self.name} is far too long (over {MAX_PARAGRAPH:,} characters), so the file was not "
                           "read. Break that paragraph into shorter ones, then choose the file again.")

    def add(self, s):
        if self.skip or not self.in_run or self.para is None or not s:
            return
        if self.run_hidden:
            return
        self.para["len"] += len(s)
        self.total += len(s)
        if self.para["len"] > MAX_PARAGRAPH:
            raise _Stop(self.refuse_long())
        if self.total > MAX_TEXT:
            raise _Stop(WordRefused(f"{self.name} holds more text than clark will read, so it was not read. "
                                    "Remove some text, or put part of it in a second file."))
        self.para["text"].append(s)

    def start(self, tag, attrs, depth):
        ns, local = _local(tag)
        if ns == MC and local == "Fallback" and not self.skip:
            self.skip = depth
            return
        if ns not in W_NAMESPACES:
            return
        if local == "body":
            self.body_seen = True
        if self.skip:
            return
        if local in SKIP:
            self.skip = depth
            if local in ("drawing", "pict", "object"):
                self.counts["pictures"] += 1             # a text box lives inside one of these
            return
        val = _attr(attrs, "val")
        if local == "p":
            self.para = {"text": [], "len": 0, "style": None, "num": None, "ilvl": 0, "outline": None}
        elif local == "pPr":
            self.in_ppr = True
        elif local == "pStyle" and self.para is not None and self.in_ppr:
            self.para["style"] = val
        elif local == "numPr" and self.in_ppr:
            self.in_numpr = True
        elif local == "numId" and self.in_numpr and self.para is not None:
            self.para["num"] = val
        elif local == "ilvl" and self.in_numpr and self.para is not None:
            self.para["ilvl"] = _int(val) or 0
        elif local == "outlineLvl" and self.in_ppr and self.para is not None:
            self.para["outline"] = _int(val)
        elif local == "r":
            self.in_run, self.run_hidden = True, False
        elif local == "vanish" and self.in_run:
            if (val or "true").lower() not in ("0", "false", "off"):
                self.run_hidden = True
                self.counts["hidden"] += 1
        elif local == "t":
            self.in_t = True
        elif local == "tab" and self.in_run and not self.in_ppr:
            self.add(" ")
        elif local in ("br", "cr") and self.in_run:
            self.add("\n")
        elif local == "noBreakHyphen":
            self.add("-")
        elif local == "hyperlink":
            self.counts["links"] += 1
        elif local == "tbl":
            self.tables.append({"rows": [], "row": None, "cell": None})
        elif local == "tr" and self.tables:
            self.tables[-1]["row"] = []
        elif local == "tc" and self.tables:
            self.tables[-1]["cell"] = []

    def text(self, data):
        if self.in_t:
            self.add(data)

    def end(self, tag, depth):
        ns, local = _local(tag)
        if self.skip:
            if depth == self.skip:
                self.skip = 0
            return
        if ns not in W_NAMESPACES:
            return
        if local == "t":
            self.in_t = False
        elif local == "r":
            self.in_run = self.run_hidden = False
        elif local == "pPr":
            self.in_ppr = False
        elif local == "numPr":
            self.in_numpr = False
        elif local == "p":
            self.finish_paragraph()
        elif local == "tc" and self.tables:
            t = self.tables[-1]
            t["row"].append("\n".join(t["cell"] or []))
            t["cell"] = None
        elif local == "tr" and self.tables:
            t = self.tables[-1]
            if any(c.strip() for c in t["row"] or []):
                t["rows"].append(t["row"])
            t["row"] = None
        elif local == "tbl" and self.tables:
            done = self.tables.pop()
            if self.tables:                                  # nested: its text goes into the cell it sits in
                outer = self.tables[-1]
                if outer["cell"] is not None:
                    outer["cell"] += [" | ".join(c.replace("\n", " ") for c in row) for row in done["rows"]]
            elif done["rows"]:
                self.emit({"kind": "table", "rows": done["rows"]})

    def emit(self, block):
        self.blocks.append(block)
        if len(self.blocks) > MAX_BLOCKS:
            raise _Stop(WordRefused(f"{self.name} holds more than {MAX_BLOCKS:,} paragraphs and rows, so it was not read. "
                                    "Remove some text, or put part of it in a second file."))

    def style_chain(self, style_id):
        """The paragraph's style and what it is based on, nearest first (at most ten, so a loop cannot hang)."""
        out, seen = [], set()
        while style_id and style_id in self.styles and style_id not in seen and len(out) < 10:
            seen.add(style_id)
            out.append(self.styles[style_id])
            style_id = self.styles[style_id].get("based")
        return out

    def heading_level(self, p, chain):
        if p["outline"] is not None:
            return p["outline"] + 1 if 0 <= p["outline"] <= 8 else None
        for s in chain:
            m = HEADING_NAME.fullmatch(s["name"])
            if m:
                return int(m.group(1))
            if s["name"] == "title":
                return 1
            if s["outline"] is not None:
                return s["outline"] + 1 if 0 <= s["outline"] <= 8 else None
        m = HEADING_ID.fullmatch(p["style"] or "")
        if m:
            return int(m.group(1))
        return 1 if p["style"] == "Title" else None

    def list_info(self, p, chain):
        """(level, ordered) when the paragraph is a list item, else None."""
        num, ilvl = p["num"], p["ilvl"]
        if num is None:
            for s in chain:
                if s["num"] is not None:
                    num, ilvl = s["num"], s["ilvl"]
                    break
        if num == "0":
            return None
        if num is not None:
            fmt = self.numbering.get(num, {}).get(ilvl, "bullet")
            return min(ilvl, 8), fmt not in ("bullet", "none")
        label = " ".join(s["name"] for s in chain[:1]) or (p["style"] or "").lower()
        if label.startswith("list number"):
            return 0, True
        if label.startswith("list bullet"):
            return 0, False
        return None

    def finish_paragraph(self):
        p, self.para = self.para, None
        if p is None:
            return
        text = clean_text("".join(p["text"]))
        if self.tables and self.tables[-1]["cell"] is not None:
            if text:
                self.tables[-1]["cell"].append(text)
            return
        if not text:
            return
        chain = self.style_chain(p["style"])
        level = self.heading_level(p, chain)
        if level is not None:
            self.emit({"kind": "heading", "level": level, "text": text})
            return
        item = self.list_info(p, chain)
        if item:
            self.emit({"kind": "list_item", "level": item[0], "ordered": item[1], "text": text})
        else:
            self.emit({"kind": "paragraph", "text": text})


def _plural(n, one, many):
    return one if n == 1 else many


def read(data, name="This file"):
    """The text of the Word file `data` (bytes) as Read(blocks, notes); raises WordRefused, in plain words, for anything
    unsafe or unreadable. `name` is how the file is called in a message."""
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise _damaged(name)
    data = bytes(data)
    if len(data) > MAX_FILE_BYTES:
        raise _too_big(name, "file", len(data), MAX_FILE_BYTES)
    if data.startswith(OLE_SIGNATURE):
        raise _password(name)
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        infos = z.infolist()
    except (zipfile.BadZipFile, EOFError, OverflowError, NotImplementedError, RuntimeError, ValueError, OSError):
        raise _damaged(name) from None
    with z:
        _check_names_and_sizes(name, infos)
        names = {i.filename for i in infos}
        for n in sorted(names):
            if MACRO_NAME.search(n):
                raise _macros_or_objects(name, "vba")
            if EMBED_NAME.search(n):
                raise _macros_or_objects(name, "oleobject")
        if "[Content_Types].xml" not in names or "word/document.xml" not in names:
            raise WordRefused(f"{name} does not look like a Word document, so it was not read. Choose a Word file.")
        main = _check_types(name, _part(z, name, "[Content_Types].xml", SMALL_PART_BYTES))
        if "wordprocessingml" not in main.lower():
            raise WordRefused(f"{name} does not look like a Word document, so it was not read. Choose a Word file.")
        for n in sorted(names):
            if n.endswith(".rels"):
                _check_rels(name, _part(z, name, n, SMALL_PART_BYTES))
        styles = _styles(name, _part(z, name, "word/styles.xml", SMALL_PART_BYTES)) if "word/styles.xml" in names else {}
        numbering = (_numbering(name, _part(z, name, "word/numbering.xml", SMALL_PART_BYTES))
                     if "word/numbering.xml" in names else {})
        body = _Body(name, styles, numbering)
        _run(name, _part(z, name, "word/document.xml"), body.start, body.end, body.text)
        comments = "word/comments.xml" in names
    if not body.body_seen:
        raise WordRefused(f"{name} does not look like a Word document, so it was not read. Choose a Word file.")
    c, notes = body.counts, []
    if c["hidden"]:
        notes.append(f"Text marked as hidden in Word ({c['hidden']} {_plural(c['hidden'], 'place', 'places')}) was not read.")
    if c["pictures"]:
        notes.append(f"{c['pictures']} {_plural(c['pictures'], 'picture, drawing or text box was', 'pictures, drawings or text boxes were')} "
                     "not read.")
    if c["links"]:
        notes.append(("The web address of 1 link was not read; the words stay." if c["links"] == 1 else
                      f"The web addresses of {c['links']} links were not read; the words stay."))
    if comments:
        notes.append("Comments were not read.")
    return Read(body.blocks, notes)
