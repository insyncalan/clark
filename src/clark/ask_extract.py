"""ask index (Row 1366 slice c rest): PowerPoint (.pptx) and web page (.html, .htm) text, standard library only.

Both return [(part name, lines)] like the Excel reader in `ask_index`, and raise ValueError for a file that is hostile or damaged
(the index counts that as `type`, never as a password). A file with no text returns [] (the index counts it as `type`, like a PDF with no text).

PPTX: `zipfile` + `xml.parsers.expat`. Only ppt/slides/slideN.xml and ppt/notesSlides/notesSlideN.xml are opened, one passage run per
slide ("slide N": its text, then its notes; a hidden slide, show="0", and its notes are not read). Limits: MAX_MEMBERS entries in the zip, MAX_UNCOMPRESSED bytes in all (declared sizes
AND the bytes really read, since a header can lie), MAX_XML bytes per part. A DOCTYPE or any entity declaration is refused, so no
entity is expanded and none is fetched.

HTML: `html.parser`; the text a reader sees. Not read: script, style, noscript, template, head (and the page's comments).
"""
import io
import re
import zipfile
from html.parser import HTMLParser
from xml.parsers import expat

MAX_MEMBERS = 5000
MAX_UNCOMPRESSED = 100 * 1024 * 1024
MAX_XML = 8 * 1024 * 1024
MAX_SLIDES = 2000
MAX_HTML_BYTES = 5 * 1024 * 1024
MAX_HTML_LINES = 200000
_SLIDE = re.compile(r"^ppt/slides/slide(\d+)\.xml$")
_NOTES = re.compile(r"^ppt/notesSlides/notesSlide(\d+)\.xml$")


def _xml_lines(data, root=None):
    """Lines of text in a DrawingML part: the text of each a:t, one line per a:p. `root`, a dict, gets the attributes of the first element."""
    p = expat.ParserCreate()
    p.buffer_text = True
    lines, cur, state = [], [], {"in_t": False}

    def refuse(*_a):
        raise ValueError("xml declares a doctype or entity")

    def start(name, attrs):
        if root is not None and not root:
            root.update(attrs)
        if name.endswith(":t") or name == "t":
            state["in_t"] = True

    def end(name):
        if name.endswith(":t") or name == "t":
            state["in_t"] = False
        elif name.endswith(":p") or name == "p":
            text = "".join(cur).strip()
            if text:
                lines.append(text)
            del cur[:]

    def chars(s):
        if state["in_t"]:
            cur.append(s)

    p.StartDoctypeDeclHandler = refuse
    p.EntityDeclHandler = refuse
    p.StartElementHandler, p.EndElementHandler, p.CharacterDataHandler = start, end, chars
    try:
        p.Parse(data, True)
    except expat.ExpatError as e:
        raise ValueError("xml") from e
    return lines


def _member(z, info):
    with z.open(info) as f:
        data = f.read(MAX_XML + 1)
    if len(data) > MAX_XML:
        raise ValueError("part too big")
    return data


def pptx_groups(raw, truncated=False):
    """[(f"slide N", lines)] in slide order; slide text then notes."""
    if truncated:
        raise ValueError("too big")
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
        infos = z.infolist()
        if len(infos) > MAX_MEMBERS or sum(i.file_size for i in infos) > MAX_UNCOMPRESSED:
            raise ValueError("zip limits")
        slides, notes = {}, {}
        for i in infos:
            m = _SLIDE.match(i.filename)
            if m:
                slides[int(m.group(1))] = i
                continue
            m = _NOTES.match(i.filename)
            if m:
                notes[int(m.group(1))] = i
        if len(slides) > MAX_SLIDES:
            raise ValueError("too many slides")
        out = []
        for n in sorted(set(slides) | set(notes)):
            lines = []
            for info in (slides.get(n), notes.get(n)):
                if info is None:
                    continue
                data = _member(z, info)
                head = {}
                lines += _xml_lines(data, head)
                if info is slides.get(n) and head.get("show") in ("0", "false"):
                    lines = []                       # a hidden slide is not shown to anyone: neither it nor its notes are indexed
                    break
            if lines:
                out.append((f"slide {n}", lines))
        return out
    except ValueError:
        raise
    except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, EOFError, RuntimeError, NotImplementedError, expat.ExpatError) as e:
        raise ValueError("pptx") from e


_SKIP = {"script", "style", "noscript", "template", "head"}
_BREAK = {"p", "div", "br", "li", "ul", "ol", "tr", "table", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "header",
          "footer", "blockquote", "pre", "hr", "td", "th", "title", "main", "nav", "aside", "form", "dd", "dt", "dl"}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines, self.cur, self.skip = [], [], 0

    def _flush(self):
        text = " ".join("".join(self.cur).split())
        if text:
            self.lines.append(text)
        del self.cur[:]

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self.skip += 1
        if tag in _BREAK:
            self._flush()

    def handle_startendtag(self, tag, attrs):
        if tag in _BREAK:
            self._flush()

    def handle_endtag(self, tag):
        if tag in _SKIP and self.skip:
            self.skip -= 1
        if tag in _BREAK:
            self._flush()

    def handle_data(self, data):
        if not self.skip and len(self.lines) < MAX_HTML_LINES:
            self.cur.append(data)


def html_groups(raw, truncated=False):
    """[(None, lines)] the visible text of a web page, or [] when it has none."""
    if truncated or len(raw) > MAX_HTML_BYTES:
        raise ValueError("too big")
    p = _Text()
    try:
        p.feed(raw.decode("utf-8", errors="replace"))
        p.close()
    except Exception as e:
        raise ValueError("html") from e
    p._flush()
    return [(None, p.lines)] if p.lines else []
