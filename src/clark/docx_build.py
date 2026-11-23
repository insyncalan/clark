"""Build the Word report (.docx) from a report's published rows (#48; BRD FR-72; design-48-word.md sections 1 to 3).

A pure function: `build(published)` takes what `publish.select()` returns ({"data", "sections", "tabs", "as_at"}) and gives the
file's bytes. It touches no database, file, clock or network. The Word file carries what the HTML file carries and never more:
the build reads only named fields of the published rows, so a key `select()` did not keep is never written, and a hidden section
is not in `sections` to begin with. There is one report (FR-82), so there is no separate team file.

A .docx is a zip of XML parts, written here as strings: [Content_Types].xml, _rels/.rels, docProps/core.xml and app.xml, and under
word/ the document, styles, numbering, settings, one footer and the document's relationships. Every value that reaches the XML goes
through esc() or attr(), which remove what XML 1.0 cannot hold and escape & < > (and the quote), so a value such as </w:t> is only
text; an attribute is built from a checked value (a colour of six hex digits, a number the module counted, a link address that
sanitise.href passed and that starts https: or mailto:), never from row text.

Rich text (current_state, a use case's standing, a text section's body) is cleaned again with sanitise.clean_html and mapped from
its token stream: p, h1 to h3 (one level down, so the section title stays the top), strong, em, s, ul and ol to three levels,
blockquote, hr, br, a checklist box, and a link only to https: or mailto:. The sanitiser has no img, so row text never brings a picture; the only pictures are the ones this module draws (docx_graphics:
the Health bar, the milestone plan, a milestone's progress bar and the Gantt tab), written as PNG parts under word/media; the plan and the Gantt carry each lane's name and the months as pixels, never as markup.

The same rows give the same bytes: parts in a fixed order, a fixed time, system and permission bits on every zip entry, relationship
ids numbered in order of use, no clock and nothing left to chance, and the file's author and last editor are the word clark, never a person.
(The compressed bytes also depend on the zlib in use, so compare two builds made on one machine.)

What is not carried: links between items, labels, comments, and the editor's tile order and outline colours (they are not
in the published rows). A Cancelled milestone is left out, as the page's client list leaves it out. A shown table with no rows says
"None recorded."; an empty current state or text section is left out (FR-14c).

Colours and the font are the committed look's (excel_colours.TOKENS, read from tokens.css by look.py); `build(..., colours={"brand-navy": "062F3A", ...})` lays a
local brand's values over them, each a #rrggbb or rrggbb that is checked, so a brand cannot put markup into the file.

Standard library only, Python 3.9.
"""
import io
import re
import zipfile
from datetime import date

from clark import excel_colours as colours_table
from clark import docx_fullimage, docx_graphics, docx_read, glance, glance_print, look, platform, sanitise

MAX_BYTES = 5 * 1024 * 1024               # NFR-8: a file larger than this is refused (as publish.MAX_BYTES)
NONE = "None recorded."                   # creaite's own words (docx_tools.NONE)
PAGE_W, PAGE_H, MARGIN = 11906, 16838, 1134      # A4, 2 cm
TEXT_W = PAGE_W - 2 * MARGIN                      # 9638 twentieths of a point between the margins
FIXED_NAME = "clark"
ZIP_TIME = (1980, 1, 1, 0, 0, 0)
FONT = look.office_font()                 # the look's --font-office, a font Office has

NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
DOC_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml"
HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
ROOT = f'xmlns:w="{NS_W}" xmlns:r="{NS_R}"'

TOKENS = {k: v for k, v in colours_table.TOKENS.items() if k not in colours_table.EXPORT_TOKENS}      # item 1390: the workbook-only tokens are not Word's
HEX = re.compile(r"#?([0-9A-Fa-f]{6})")
NOT_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ud800-\udfff￾￿]")

TITLES = {"current": "Current state", "glance": "At a glance", "usecases": "Use cases", "milestones": "Milestones",
          "text": "Notes", "raid": "Risks and issues", "actions": "Actions", "decisions": "Decisions", "gantt": "Gantt",
          "imagecap": "Image", "workitems": "Work items", "reportheadline": "Report headline",
          "glancetemplate": "At a glance", "callout": "Callout", "textimage": "Text and Image Side by Side"}                            # row 1223: only a Full width image (body version 2) is written, and it has no heading; an Image with caption (version 1) is left out, as it was
CALLOUT_FILL = {"violet": "blue", "amber": "amber", "red": "red", "green": "green", "grey": "grey"}      # row 1272: Violet is the page's blue token; Plain has no fill
HEALTH_PILL = {"on_track": ("On track", "green"), "at_risk": ("At risk", "amber"), "off_track": ("Off track", "red")}   # row 1261: the pill's words and tone
HIDDEN_BY_KIND = ("actions", "raid", "decisions")
HEADING_STYLE = {"h1": "Heading2", "h2": "Heading3", "h3": "Heading4"}
MAX_LEVELS = 4                                           # list levels written


class WordError(ValueError):
    """The file was not made, in words a person can act on."""


# ===== Escaping =====
def esc(value):
    """`value` as text for an XML element: characters XML 1.0 cannot hold removed, & < > escaped."""
    return NOT_XML.sub("", "" if value is None else str(value)).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def attr(value):
    """`value` as text for a double-quoted XML attribute."""
    return esc(value).replace('"', "&quot;")


def palette(colours=None):
    """The colour table: the demo tokens with a local brand's values laid over them. A value that is not six hex digits is ignored."""
    out = dict(TOKENS)
    for k, v in (colours or {}).items():
        m = HEX.fullmatch(str(v).strip())
        if k in out and m:
            out[k] = m.group(1).upper()
    return out


class _Ctx:
    """What one build collects as it goes: the colours, the as-at date, the links used (address -> relationship id) and the
    ordered lists started (each one restarts at 1)."""

    def __init__(self, colours, as_at):
        self.tok, self.as_at = colours, as_at
        self.today = date.fromisoformat(as_at)
        self.links, self.lists = {}, 0
        self.images = {}                               # PNG bytes -> (relationship id, part name): the same picture is one part
        self.next_rid, self.drawings = 5, 0

    def rid(self):
        self.next_rid += 1
        return f"rId{self.next_rid - 1}"

    def link(self, address):
        if address not in self.links:
            self.links[address] = self.rid()
        return self.links[address]

    def image(self, png, ext="png"):
        if png not in self.images:
            self.images[png] = (self.rid(), f"image{len(self.images) + 1}.{ext}")
        return self.images[png]

    def new_list(self):
        self.lists += 1
        return self.lists + 1                          # numId 1 is the bullet list

    def hexes(self, name):
        fill, text = colours_table.COLOURS[name]
        return self.tok[fill], self.tok[text]


# ===== Paragraphs, runs, tables =====
def run(text, bold=False, italic=False, strike=False, color=None, size=None, style=None):
    """One Word run. A newline is a line break and a tab is a tab."""
    props = (f'<w:rStyle w:val="{style}"/>' if style else "") + ("<w:b/>" if bold else "") + ("<w:i/>" if italic else "") \
        + ("<w:strike/>" if strike else "") + (f'<w:color w:val="{color}"/>' if color else "") \
        + (f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>' if size else "")
    body = []
    for i, line in enumerate(NOT_XML.sub("", str(text)).split("\n")):
        if i:
            body.append("<w:br/>")
        for j, piece in enumerate(line.split("\t")):
            if j:
                body.append("<w:tab/>")
            if piece:
                body.append(f'<w:t xml:space="preserve">{esc(piece)}</w:t>')
    return f"<w:r>{'<w:rPr>' + props + '</w:rPr>' if props else ''}{''.join(body)}</w:r>"


def para(runs="", style=None, keep_next=False, num=None, rule=False, fill=None, tabs=None, spacing=None, align=None):
    """One paragraph. `num` is (numId, level) for a list item; `rule` draws a line under it; `fill` shades it."""
    props = (f'<w:pStyle w:val="{style}"/>' if style else "") + ("<w:keepNext/>" if keep_next else "")
    if num:
        props += f'<w:numPr><w:ilvl w:val="{int(num[1])}"/><w:numId w:val="{int(num[0])}"/></w:numPr>'
    if rule:
        props += f'<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="{TOKENS["grey-300"]}"/></w:pBdr>'
    if fill:
        props += f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>'
    if tabs:
        props += f'<w:tabs><w:tab w:val="right" w:pos="{int(tabs)}"/></w:tabs>'
    if spacing:
        props += f'<w:spacing w:before="{int(spacing[0])}" w:after="{int(spacing[1])}"/>'
    if align in ("center", "left", "right"):
        props += f'<w:jc w:val="{align}"/>'
    return f"<w:p>{'<w:pPr>' + props + '</w:pPr>' if props else ''}{runs}</w:p>"


def text_paras(text, ctx, style="TableText", **kw):
    """Plain text (a value from a row) as paragraphs, one for each line."""
    lines = [ln for ln in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    lines = [ln for ln in lines if ln.strip()] or [""]
    return "".join(para(run(ln, **kw), style) for ln in lines)


def cell(width, paras, fill=None):
    """One table cell holding paragraph XML."""
    shade = f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>' if fill else ""
    return f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{shade}</w:tcPr>{paras or para()}</w:tc>'


def widths(weights):
    """Column widths in twentieths of a point that add up to the text width exactly (the last column takes the rounding). The
    weights of the data tables are themselves twentieths of a point (each sums to TEXT_W): an ID, a date or a status word is
    given the width its longest word needs, so no word or date is broken across two lines."""
    total = sum(weights)
    cols = [TEXT_W * w // total for w in weights]
    cols[-1] += TEXT_W - sum(cols)
    return cols


def table(ctx, headers, weights, rows, borders=True):
    """A fixed-width table. `rows` is a list of rows; a row is a list of cells, each `(paragraph xml, fill hex or None)`. The
    header row repeats on each page and no row splits across a page."""
    cols = widths(weights)
    line = f'w:val="single" w:sz="4" w:space="0" w:color="{ctx.tok["grey-300"]}"'
    edges = (f'<w:tblBorders><w:top {line}/><w:bottom {line}/><w:insideH {line}/></w:tblBorders>' if borders else "")
    out = [f'<w:tbl><w:tblPr><w:tblW w:w="{TEXT_W}" w:type="dxa"/>{edges}<w:tblLayout w:type="fixed"/>'
           '<w:tblCellMar><w:top w:w="40" w:type="dxa"/><w:left w:w="80" w:type="dxa"/><w:bottom w:w="40" w:type="dxa"/>'
           '<w:right w:w="80" w:type="dxa"/></w:tblCellMar><w:tblLook w:val="04A0"/></w:tblPr><w:tblGrid>'
           + "".join(f'<w:gridCol w:w="{w}"/>' for w in cols) + "</w:tblGrid>"]
    if headers:
        head = "".join(cell(w, para(run(h, bold=True, color=ctx.tok["white"], size=18), "TableText"), ctx.tok["brand-navy"])
                       for w, h in zip(cols, headers))
        out.append(f"<w:tr><w:trPr><w:cantSplit/><w:tblHeader/></w:trPr>{head}</w:tr>")
    for r in rows:
        out.append("<w:tr><w:trPr><w:cantSplit/></w:trPr>" + "".join(cell(w, p, f) for w, (p, f) in zip(cols, r)) + "</w:tr>")
    return "".join(out) + "</w:tbl>" + para(spacing=(0, 120))


NS_WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
EMU_PER_TWIP = 635


def picture(ctx, drawn, width_twips, alt, ext="png"):
    """A run holding an inline picture (a Word drawing) of `drawn` = (png, pixel width, pixel height), `width_twips` wide with
    its shape kept. `alt` is the picture's alternative text, made only of words the report already shows."""
    png, w, h = drawn
    rid, name = ctx.image(png, ext)
    ctx.drawings += 1
    cx = int(width_twips) * EMU_PER_TWIP
    cy = max(1, cx * h // w)
    return (f'<w:r><w:drawing><wp:inline xmlns:wp="{NS_WP}" distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
            f'<wp:docPr id="{ctx.drawings}" name="{docx_read.OWN_PICTURE_NAME}{ctx.drawings}" descr="{attr(alt)}"/>'
            f'<a:graphic xmlns:a="{NS_A}"><a:graphicData uri="{NS_PIC}"><pic:pic xmlns:pic="{NS_PIC}"><pic:nvPicPr>'
            f'<pic:cNvPr id="{ctx.drawings}" name="{name}" descr="{attr(alt)}"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill>'
            f'<a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/>'
            f'<a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
            "</a:graphicData></a:graphic></wp:inline></w:drawing></w:r>")


def picture_para(ctx, make, width_twips, style=None, ext="png", **kw):
    """A paragraph holding a picture, or "" when it cannot be made. `make()` gives (drawn, alt text) or None. A picture is only an
    addition to words the report already carries, so any failure in drawing it (a number too large to read, a bug) leaves the
    words alone and writes no picture."""
    try:
        made = make()
        if not made:
            return ""
        drawn, alt = made
        return para(picture(ctx, drawn, width_twips, alt, ext), style, **kw)
    except Exception:
        return ""


def word_cell(text, ctx, colour=None, late=False, extra=()):
    """A cell of words. `colour` (red, amber, green, blue, grey) gives a fill and text of the same hue, the words always shown;
    `late` draws the text red; `extra` are quieter lines under it."""
    fill = color = None
    if colour == "urgent":      # row 1021: Urgent is a solid maroon cell with bold white words (the page's maroon tile)
        fill, color = ctx.tok["tone-urgent"], ctx.tok["white"]
        return text_paras(text, ctx, color=color, bold=True), fill
    if colour in colours_table.COLOURS:
        fill, color = ctx.hexes(colour)
    elif late:
        color = ctx.tok["tone-red-text"]
    body = text_paras(text, ctx, color=color)
    body += "".join(para(run(x, color=ctx.tok["grey-700"], size=16), "TableText") for x in extra if x)
    return body, fill


# ===== Rich text =====
FONT_COLOUR_TOKEN = {"rt-c-grey": "text-muted", "rt-c-brand": "brand-blue", "rt-c-red": "tone-red-text", "rt-c-amber": "tone-amber-text",
                     "rt-c-green": "tone-green-text", "rt-c-blue": "tone-blue-text"}      # row 1364: the page's six font colours, each the same token the stylesheet uses


class _Rich:
    """Maps cleaned rich text (sanitise's allow-list) to paragraphs."""

    def __init__(self, ctx, floor=2):
        self.ctx, self.out, self.runs = ctx, [], []
        self.floor = floor                             # the shallowest heading level inside: below a Heading3 parent nothing may sit higher
        self.fmt = {"strong": 0, "em": 0, "s": 0}
        self.link = None
        self.colours = []                              # row 1364: the token of each open span (None for a span that carries no colour)
        self.stack, self.lists = [], []

    def add_text(self, text):
        if not text:
            return
        c = self.ctx
        token = next((t for t in reversed(self.colours) if t), None)
        r = run(text, bold=bool(self.fmt["strong"]), italic=bool(self.fmt["em"]), strike=bool(self.fmt["s"]),
                color=c.tok[token] if token else c.tok["status-blue-text"] if self.link else None, style="Hyperlink" if self.link else None)
        self.runs.append(f'<w:hyperlink r:id="{self.link}" w:history="1">{r}</w:hyperlink>' if self.link else r)

    def flush(self):
        runs, self.runs = "".join(self.runs), []
        if not re.sub(r"<[^>]*>", "", runs).strip() and "<w:br/>" not in runs:
            return
        heading = next((HEADING_STYLE[t] for t in reversed(self.stack) if t in HEADING_STYLE), None)
        if heading and int(heading[-1]) < self.floor:
            heading = f"Heading{self.floor}"
        if heading:
            self.out.append(para(runs, heading, keep_next=True))
        elif "li" in self.stack and self.lists:
            self.out.append(para(runs, "ListParagraph", num=(self.lists[-1][1], min(len(self.lists) - 1, MAX_LEVELS - 1))))
        elif "blockquote" in self.stack:
            self.out.append(para(runs, "Quote"))
        else:
            self.out.append(para(runs))

    def start(self, name, attrs):
        c = self.ctx
        if name in ("p", "h1", "h2", "h3", "li", "blockquote", "ul", "ol"):
            self.flush()
        if name in ("ul", "ol"):
            numid = 1 if name == "ul" else (self.lists[-1][1] if self.lists and self.lists[-1][0] == "ol" else c.new_list())
            self.lists.append((name, numid))
        if name == "hr":
            self.flush()
            self.out.append(para(rule=True, spacing=(60, 60)))
        elif name == "br":
            self.runs.append(run("\n"))
        elif name == "input":
            self.add_text("☑ " if "checked" in dict(attrs) else "☐ ")
        elif name in self.fmt:
            self.fmt[name] += 1
        elif name == "span":
            self.colours.append(FONT_COLOUR_TOKEN.get(dict(attrs).get("class")))
        elif name == "a":
            address = sanitise.href(dict(attrs).get("href"))
            if address and address.lower().startswith(("https://", "mailto:")):
                self.link = c.link(address)
        if name not in ("br", "hr", "input"):
            self.stack.append(name)

    def end(self, name):
        if name in self.fmt:
            self.fmt[name] = max(0, self.fmt[name] - 1)
        elif name == "span":
            if self.colours:
                self.colours.pop()
        elif name == "a":
            self.link = None
        if name in ("p", "h1", "h2", "h3", "li", "blockquote", "ul", "ol"):
            self.flush()
        if name in self.stack:
            while self.stack and self.stack.pop() != name:
                pass
        if name in ("ul", "ol") and self.lists:
            self.lists.pop()


def rich(html, ctx, floor=2):
    """Rich text as Word paragraphs, after cleaning it again with the sanitiser. Raises WordError for a text that is too long."""
    try:
        clean = sanitise.clean_html(html)
    except sanitise.SanitiseError as e:
        raise WordError(str(e)) from None
    r = _Rich(ctx, floor)
    for t in sanitise.tokens(clean):
        if t[0] == "text":
            r.add_text(sanitise.decode(t[1]))
        elif t[0] == "start":
            r.start(t[1], t[2])
        else:
            r.end(t[1])
    r.flush()
    return "".join(r.out)


# ===== Sections =====
def _heading(title, level=1):
    return para(run(title), f"Heading{level}", keep_next=True)


def _rows(published, key):
    return list(published["data"].get(key) or [])


def _open(rows):
    """Only the open items (the app's own rule, glance.is_open: not Closed, Cancelled, Made or Withdrawn)."""
    return [r for r in rows if glance.is_open(r)]


def _words(row, field, own):
    """The client's wording when the row has some, else the row's own text (data-model.md: client_message is optional)."""
    return (row.get("client_message") or "").strip() or row.get(own) or ""


def _date(iso):
    return glance.show_date(iso)


def _kept(published, shown):
    """The published rows, in the shape glance reads them for a client (so the counts are the page's)."""
    data = published["data"]
    hidden = {t for t in HIDDEN_BY_KIND if t not in shown}
    listed = {i for s in published["sections"] if s.get("type") == "workitems" for i in s.get("items") or ()}
    rows = glance.work_rows(data)
    # row 1268: a row of a section left off the file is counted only when a Work items list in the file names it
    rows = [r for r in rows if r["id"] in listed or not any(r["kind"] in glance.KINDS_OF_TILE[n] and glance.SECTION_OF_TILE[n] in hidden
                                                          for n in glance.KINDS_OF_TILE)]
    return {"data": data, "rows": rows, "use_cases": data.get("use_cases") or [], "hidden_types": hidden}


def section_current(published, ctx, title, sec):
    body = rich((published["data"].get("project") or {}).get("current_state"), ctx)
    return _heading(title) + body if body else ""


def section_text(published, ctx, title, sec):
    body = rich(sec.get("body"), ctx)
    return _heading(title) + body if body else ""


def section_glance(published, ctx, title, sec, kept):
    tiles = glance.tiles({"project": published["data"].get("project") or {}}, published["as_at"], for_client=True, kept=kept)
    out = [_heading(title)]
    health = next((t for t in tiles if t["tile"] == "health"), None)
    if health:
        fill = text = None
        if health["colour"]:
            fill, text = ctx.hexes(health["colour"])
        out.append(para(run("Project health: ", bold=True) + run(health["value"], bold=True, color=text), fill=fill,
                        spacing=(60, 60)))
        out.append(picture_para(ctx, lambda: (docx_graphics.health_bar(health["colour"], ctx.tok), "Project health: " + str(health["value"])),
                                TEXT_W, keep_next=True, spacing=(0, 60)))
        if health["reason"].strip():
            out.append(text_paras(health["reason"], ctx, style=None))
    others = [t for t in tiles if t["tile"] != "health"]
    if others:
        weights = [1] * len(others)
        cells = []
        for t in others:
            fill = text = None
            if t["colour"]:
                fill, text = ctx.hexes(t["colour"])
            cells.append((para(run(t["title"], color=ctx.tok["grey-700"], size=16), "TableText")
                          + para(run(str(t["value"]), bold=True, color=text, size=32), "TableText")
                          + para(run(t["detail"], size=16), "TableText"), fill))
        out.append(table(ctx, None, weights, [cells]))
    return "".join(out)


def section_usecases(published, ctx, title, sec, kept):
    strip = glance.use_case_strip(None, None, published["as_at"], for_client=True, kept=kept)
    out = [_heading(title)]
    if not strip["rows"]:
        return "".join(out) + para(run(NONE))
    out.append(para(run(strip["total_words"] + ": " + ", ".join(f"{c['count']} {c['status']}" for c in strip["counts"]))))
    rows = [[word_cell(u["ref"], ctx), word_cell(u["title"], ctx), word_cell(u["status"], ctx, colour=u["colour"]),
             word_cell(u.get("commitment") or "", ctx), word_cell(u["headline"], ctx), word_cell(u["words"], ctx)] for u in strip["rows"]]
    out.append(table(ctx, ["Ref", "Use case", "Status", "Commitment", "Headline", "Work items"], [700, 2300, 1100, 1350, 3088, 1100], rows))
    standing = {u["id"]: u.get("standing") for u in kept["use_cases"]}
    for u in strip["rows"]:
        body = rich(standing.get(u["id"]), ctx, floor=4)           # its parent is a Heading3, so a heading inside is Heading4
        linked = [str(r["id"]) for r in glance.use_case_items(kept, u["id"]) if r.get("id")]
        if body or linked:
            out.append(_heading(f"{u['ref'] + ' ' if u['ref'] else ''}{u['title']}".strip(), 3) + body)
            if linked:
                out.append(para(run("Linked work items: " + ", ".join(linked), color=ctx.tok["grey-700"], size=18)))
    return "".join(out)


def section_milestones(published, ctx, title, sec):
    rows, kept = [], []
    for m in _rows(published, "milestones"):
        if m.get("status") == "Cancelled":
            continue
        kept.append(m)
        achieved = m.get("status") == "Done"
        slip = m.get("slip_days")
        name = para(run(m.get("name") or "", bold=True), "TableText")
        for line, kw in ((sanitise.rich_plain_text(m.get("description")), {}), (sanitise.rich_plain_text(m.get("client_message")), {}),     # row 1078: the client wording is rich too
                         (f"Reason: {m['state_reason']}" if m.get("state_reason") else "", {"color": ctx.tok["grey-700"]})):
            if line:
                name += text_paras(line, ctx, **kw)
        if m.get("percent_complete") is not None:
            name += para(run(f"{m['percent_complete']}% complete", color=ctx.tok["grey-700"], size=16), "TableText")
            name += picture_para(ctx, lambda: (docx_graphics.progress_bar(m["percent_complete"], ctx.tok), f"{m['percent_complete']}% complete"),
                                 1440, "TableText")
        when = ("Achieved" + (f" {_date(m['actual_date'])}" if m.get("actual_date") else "")) if achieved else _date(m.get("forecast_date"))
        colour = colours_table.colour_for("milestones", "state", m.get("state"))
        rows.append([word_cell(m.get("id"), ctx), (name, None), word_cell(m.get("owner"), ctx, extra=[m.get("workstream")]),
                     word_cell(_date(m.get("baseline_date")), ctx), word_cell(when, ctx),
                     word_cell(m.get("state_word") or m.get("state"), ctx, colour=colour),
                     word_cell(f"+{slip} day{'' if slip == 1 else 's'}" if slip and not achieved else "", ctx)])
    if not rows:
        return _heading(title) + para(run(NONE))
    def plan():                                        # one lane for each milestone, in the order of the table; the words are the table's
        drawn = docx_graphics.plan(kept, published["as_at"], ctx.tok)
        if not drawn:
            return None
        image, lanes = drawn
        words = "; ".join(f"{r['row'].get('name') or ''}, {_date(r['row'].get('baseline_date'))}, "
                          f"{r['row'].get('state_word') or r['row'].get('state') or ''}" for r in lanes)
        if len(words) > PLAN_ALT_MAX:                  # 200 long names would make an alt text of many thousand characters: cut at a word
            words = words[:PLAN_ALT_MAX].rsplit(" ", 1)[0]
        return image, words
    chart = picture_para(ctx, plan, TEXT_W, keep_next=True, spacing=(0, 60))
    return _heading(title) + chart + table(ctx, ["ID", "Milestone", "Owner", "Agreed", "Forecast", "State", "Slip"],
                                           [1200, 3038, 1150, 1100, 1100, 1100, 950], rows)


PLAN_ALT_MAX = 1500

GANTT_STATUS = {"done": "Done", "late": "Late", "inprogress": "In progress", "notstarted": "Not started"}     # the page's WORDS (gantt/logic/gantt.js)
GANTT_LEGEND = ("Phase", "Task (lighter part = done)", "Milestone", "Achieved", "Today")


def _gantt_status(r, today):
    """The page's statusOf: Done (100%), Late (ended before today and not done), In progress, Not started."""
    if r["pct"] >= 100:
        return "done"
    if r["end"] < today:
        return "late"
    return "inprogress" if r["pct"] > 0 or (r["start"] <= today and r["type"] != "milestone") else "notstarted"


def _gantt_numbers(drawn):
    """The page's outline numbers: phases 1, 2, 3; a task under a phase 2.1; a milestone M-1; a task with no phase T-1."""
    phases = {r["line"].get("id"): r for r in drawn if r["type"] == "phase" and isinstance(r["line"].get("id"), str)}
    num, p, m, t, under = {}, 0, 0, 0, {}
    for i, r in enumerate(drawn):
        if r["type"] == "phase":
            p += 1
            num[i] = str(p)
    by_id = {r["line"].get("id"): num[i] for i, r in enumerate(drawn) if i in num and isinstance(r["line"].get("id"), str)}
    for i, r in enumerate(drawn):
        if r["type"] == "milestone":
            m += 1
            num[i] = f"M-{m}"
        elif r["type"] == "task":
            up = r["line"].get("parent")
            if isinstance(up, str) and up in phases and up in by_id:
                under[up] = under.get(up, 0) + 1
                num[i] = f"{by_id[up]}.{under[up]}"
            else:
                t += 1
                num[i] = f"T-{t}"
    return [num[i] for i in range(len(drawn))]


def section_gantt(published, ctx, title, sec):
    """The Gantt tab as pictures (docx_graphics.gantt) with the words as Word text under each: the number, name, start, end, how far
    along and the status of every line the picture holds, in the picture's order. The lines are published data.gantt's (an eye-off
    line was never copied). No Gantt in the file, or no line, is no section."""
    g = published["data"].get("gantt")
    try:
        made = docx_graphics.gantt((g or {}).get("lines"), published["as_at"], ctx.tok) if isinstance(g, dict) else None
    except Exception:                                                                       # a picture is only an addition: nothing to draw from, no section
        made = None
    if not made:
        return ""
    out = [_heading(title)]
    if made["pictures"]:
        out.append(para(run(f"{_date(made['start'].isoformat())} to {_date(made['end'].isoformat())}", color=ctx.tok["grey-700"], size=16), keep_next=True))
        out.append(para(run(" · ".join(GANTT_LEGEND), color=ctx.tok["grey-700"], size=16), keep_next=True))
    if made["left_out"]:
        shown = len(made["drawn"])
        out.append(para(run(f"{shown} of {shown + made['left_out']} lines shown", color=ctx.tok["grey-700"], size=16)))
    try:
        numbers = _gantt_numbers(made["drawn"])
    except Exception:
        numbers = [""] * len(made["drawn"])
    at = 0
    for image, run_lines in made["pictures"]:
        status = [GANTT_STATUS[_gantt_status(r, ctx.today)] for r in run_lines]
        out.append(picture_para(ctx, lambda: (image, "; ".join(f"{r['line'].get('name') or ''}, {_date(r['start'].isoformat())}, {s}"
                                                                for r, s in zip(run_lines, status))), TEXT_W, keep_next=True, spacing=(0, 60)))
        rows = []
        for r, s in zip(run_lines, status):
            line = r["line"]
            name = para(run(line.get("name") or "", bold=r["type"] == "phase"), "TableText")
            rows.append([word_cell(numbers[at], ctx), (name, None), word_cell(_date(r["start"].isoformat()), ctx),
                         word_cell(_date(r["end"].isoformat()), ctx), word_cell(f"{r['pct']}%", ctx),
                         word_cell(s, ctx, colour={"done": "green", "late": "red"}.get(_status_key(s)))])
            at += 1
        out.append(table(ctx, ["No", "Phase / task", "Start", "End", "Done", "Status"], [800, 4238, 1150, 1150, 900, 1400], rows))
    return "".join(out)


def section_imagecap(published, ctx, title, sec):
    """Row 1223: the Full width image, as framed (the file holds only the framed copy), as wide as the text; one narrower than the text at its
    own size, centred (or the full width when its fit is stretch) on its fill (brand colour or grey; Word cannot blur). The caption in small
    grey type under it, none when there is none. No heading. An Image with caption (no `full` in its content) is not in the Word report, as
    before. An image that cannot be read leaves the section out; the words alone are never shown without it."""
    c = sec.get("content") if isinstance(sec.get("content"), dict) else {}
    if not c.get("full"):
        return ""
    got = docx_fullimage.decode(c.get("image"))
    if not got:
        return ""
    raw, ext, w, h = got
    stretch = c.get("fit") == "stretch"
    twips = docx_fullimage.width_twips(w, h, TEXT_W, stretch)
    narrow = twips < TEXT_W and not stretch
    fill = {"brand": ctx.tok["brand-blue"], "blur": ctx.tok["grey-100"]}.get(c.get("fill", "blur")) if narrow else None
    caption = str(c.get("caption") or "").strip()
    alt = str(c.get("alt") or "")
    pic = picture_para(ctx, lambda: ((raw, w, h), alt), twips, ext=ext, keep_next=bool(caption), fill=fill,
                       align="center" if narrow else None, spacing=(120, 40))
    if not pic:
        return ""
    return pic + (para(run(caption, color=ctx.tok["grey-700"], size=16), spacing=(0, 120)) if caption else "")


def section_textimage(published, ctx, title, sec):
    """Row 1232: Text and Image Side by Side (an old Text and image section reads the same). The section heading, then the image as framed
    (the file holds only the framed copy) with its caption, and the words; the image comes first when it is on the left, after the words
    otherwise. A small image sits at its own size, centred. An image that cannot be read leaves the words alone; nothing to say leaves
    the section out."""
    c = sec.get("content") if isinstance(sec.get("content"), dict) else {}
    html = c.get("html")
    words = rich(html, ctx) if isinstance(html, str) and html.strip() else "".join(
        para(run(str(w))) for w in (c.get("words") or []) if isinstance(w, str) and w.strip())
    pic = ""
    got = docx_fullimage.decode(c.get("image"))
    if got:
        raw, ext, w, h = got
        twips = docx_fullimage.width_twips(w, h, TEXT_W * 2 // 3, False)
        caption = str(c.get("caption") or "").strip()
        pic = picture_para(ctx, lambda: ((raw, w, h), str(c.get("alt") or "")), twips, ext=ext, keep_next=bool(caption),
                           align="center" if twips < TEXT_W * 2 // 3 else None, spacing=(120, 40))
        if pic and caption:
            pic += para(run(caption, color=ctx.tok["grey-700"], size=16), spacing=(0, 120))
    if not pic and not words:
        return ""
    first = c.get("side") == "left"                  # Word does not know the section width: left puts the image first, anything else after the words
    own = " ".join(str(c.get("heading") or "").split())            # the view draws this one line above the picture and the words, under the section heading
    return _heading(title) + (_heading(own, 2) if own else "") + (pic + words if first else words + pic)


def _status_key(word):
    return {v: k for k, v in GANTT_STATUS.items()}[word]


def _due(table_name, field, row, ctx, extra=()):
    iso = row.get(field)
    late = colours_table.is_late(table_name, field, row, ctx.today)
    return word_cell(_date(iso) + (" (overdue)" if late else "") if iso else "", ctx, late=late, extra=extra)


def _status_cell(row, kind, ctx):
    """The status as the page says it (glance.client_pill): Overdue, Delayed, Due soon or On track on an action; Red, Amber or Green
    on a risk or issue. Any other RAID type (an assumption, a dependency) is not on the page's lists: it keeps its own status."""
    if kind not in ("action", "risk", "issue"):
        return word_cell(row.get("status"), ctx)
    pill = glance.client_pill({"kind": kind, "status": row.get("status"), "priority": row.get("priority"), "due_date": row.get("due_date")},
                              ctx.as_at)
    if pill["text"] in ("Closed", "Made", "Completed"):
        return word_cell(pill["text"], ctx, colour="blue")      # Completed, made and closed read blue, as on the page, whatever the priority
    if row.get("priority") == "Urgent" and glance.is_open(row):
        return word_cell(pill["text"], ctx, colour="urgent")      # an open Urgent item keeps the maroon cell when it is also overdue; the due column says (overdue)
    return word_cell(pill["text"], ctx, colour={"r": "red", "a": "amber", "g": "green", "n": "grey"}.get(pill["class"]))


def section_actions(published, ctx, title, sec):
    rows = []
    for a in _open(_rows(published, "actions")):
        words = sanitise.rich_plain_text(a.get("latest_update"))
        update = f"Latest update: {words}" if words else ""
        body = text_paras(_words(a, "client_message", "description"), ctx)
        if update:
            body += text_paras(update, ctx, color=ctx.tok["grey-700"])
        rows.append([word_cell(a.get("id"), ctx), (body, None), word_cell(a.get("owner"), ctx, extra=[a.get("workstream")]),
                     word_cell(a.get("priority"), ctx, colour=colours_table.colour_for("actions", "priority", a.get("priority"))),
                     _due("actions", "due_date", a, ctx), _status_cell(a, "action", ctx)])
    if not rows:
        return _heading(title) + para(run(NONE))
    return _heading(title) + table(ctx, ["ID", "Action", "Owner", "Priority", "Due", "Status"], [1200, 4038, 1250, 950, 1100, 1100], rows)


def section_raid(published, ctx, title, sec):
    rows = []
    for r in _open(_rows(published, "raid")):
        both = " / ".join(x for x in (r.get("impact"), r.get("likelihood")) if x)
        rows.append([word_cell(r.get("id"), ctx), word_cell(r.get("type"), ctx),
                     (text_paras(_words(r, "client_message", "description"), ctx), None),
                     word_cell(r.get("owner"), ctx, extra=[r.get("workstream")]),
                     word_cell(r.get("priority"), ctx, colour=colours_table.colour_for("raid", "priority", r.get("priority"))),
                     word_cell(both, ctx), _due("raid", "due_date", r, ctx), _status_cell(r, str(r.get("type") or "").lower(), ctx)])
    if not rows:
        return _heading(title) + para(run(NONE))
    return _heading(title) + table(ctx, ["Id", "Type", "Title", "Owner", "Priority", "Impact / likelihood", "Review by", "Status"],      # the page's header words
                                   [1200, 1200, 1888, 1150, 950, 1050, 1100, 1100], rows)


def section_decisions(published, ctx, title, sec):
    rows = []
    for d in _rows(published, "decisions"):
        pending = d.get("status") == "Pending"
        when = (_date(d.get("needed_by")) if d.get("needed_by") else "No date needed by") if pending else _date(d.get("date"))
        label = ("Needed by " if pending and d.get("needed_by") else "Made " if d.get("status") == "Made" else "")
        late = colours_table.is_late("decisions", "needed_by", d, ctx.today)
        extra = [f"Revisit {_date(d['revisit'])}" if d.get("revisit") else "",
                 f"Replaces {d['replaces']}" if d.get("replaces") else ""]
        rows.append([word_cell(d.get("id"), ctx), (text_paras(_words(d, "client_message", "decision"), ctx), None),
                     word_cell(d.get("status"), ctx, colour=colours_table.colour_for("decisions", "status", d.get("status"))),
                     word_cell(d.get("made_by"), ctx),
                     word_cell(label + when + (" (overdue)" if late else ""), ctx, late=late, extra=extra)])
    if not rows:
        return _heading(title) + para(run(NONE))
    return _heading(title) + table(ctx, ["ID", "Decision", "Status", "Made by", "Date"], [1200, 4138, 1100, 1400, 1800], rows)


WORK_COLUMNS = {"type": ("Type", 1000), "id": ("ID", 1200), "owner": ("Owner", 1350), "due": ("Due", 1200), "status": ("Status", 1200),
                "priority": ("Priority", 950), "workstream": ("Workstream", 1300), "milestone": ("Milestone", 1500)}      # row 1268: the page's list columns, with the width each needs
WORK_DEFAULT = ("type", "id", "owner", "due", "priority")


def _late_words(iso, ctx):
    """Row 1268: the words the on-screen Work items list puts beside a late date (workItems.js dueCell): Yesterday, or N days late."""
    n = (ctx.today - date.fromisoformat(str(iso)[:10])).days
    return "Yesterday" if n == 1 else f"{n} days late"


def _list_due(iso, late, ctx, extra=()):
    return word_cell(_date(iso) + (" " + _late_words(iso, ctx) if late and iso else "") if iso else "", ctx, late=late, extra=extra)


def section_workitems(published, ctx, title, sec):
    """Row 1268: a Work items list prints the rows it names, in its order, as one table: the Item and the columns the list chose (its `columns`, in the page's order)."""
    by_id = {r.get("id"): (t, r) for t in ("actions", "raid", "decisions") for r in _rows(published, t)}
    names = {m.get("id"): m.get("name") for m in _rows(published, "milestones")}
    chosen = [c for c in (sec.get("columns") or ()) if c in WORK_COLUMNS] or list(WORK_DEFAULT)
    order = [c for c in ("type", "id") if c in chosen] + ["item"] + [c for c in WORK_COLUMNS if c in chosen and c not in ("type", "id")]
    rows = []
    for i in sec.get("items") or ():
        if i not in by_id:
            continue
        t, r = by_id[i]
        if t == "decisions":
            pending = r.get("status") == "Pending"
            when = _date(r.get("needed_by") if pending else r.get("date")) if (r.get("needed_by") if pending else r.get("date")) else ""
            late = colours_table.is_late("decisions", "needed_by", r, ctx.today)
            cells = {"type": word_cell("Decision", ctx), "id": word_cell(i, ctx), "item": (text_paras(_words(r, "client_message", "decision"), ctx), None),
                     "owner": word_cell(r.get("made_by"), ctx), "priority": word_cell(None, ctx), "workstream": word_cell(None, ctx), "milestone": word_cell(None, ctx),
                     "due": word_cell(when + (" " + _late_words(r.get("needed_by"), ctx) if late and when and pending else ""), ctx, late=late), "status": word_cell(r.get("status"), ctx, colour=colours_table.colour_for("decisions", "status", r.get("status")))}
        else:
            kind = "action" if t == "actions" else str(r.get("type") or "").lower()
            body = text_paras(_words(r, "client_message", "description"), ctx)
            words = sanitise.rich_plain_text(r.get("latest_update")) if t == "actions" else ""
            if words:
                body += text_paras(f"Latest update: {words}", ctx, color=ctx.tok["grey-700"])      # row 1307: an action's update line under its text, as in the Actions section
            cells = {"type": word_cell(kind.capitalize(), ctx), "id": word_cell(i, ctx), "item": (body, None),
                     "owner": word_cell(r.get("owner"), ctx), "workstream": word_cell(r.get("workstream"), ctx), "milestone": word_cell(names.get(r.get("milestone")), ctx),
                     "priority": word_cell(r.get("priority"), ctx, colour=colours_table.colour_for(t, "priority", r.get("priority"))),
                     "due": _list_due(r.get("due_date"), colours_table.is_late(t, "due_date", r, ctx.today), ctx), "status": _status_cell(r, kind, ctx)}
        rows.append([cells[c] for c in order])
    if not rows:
        return ""
    caption = para(run(sec["caption"], color=ctx.tok["grey-700"], size=18)) if sec.get("caption") else ""
    fixed = {c: WORK_COLUMNS[c][1] for c in order if c != "item"}
    weights = [fixed.get(c, max(2000, TEXT_W - sum(fixed.values()))) for c in order]
    return _heading(title) + caption + table(ctx, ["Item" if c == "item" else WORK_COLUMNS[c][0] for c in order], weights, rows)


def section_reportheadline(published, ctx, title, sec):
    """Row 1261: the Report headline as the page draws it, one flat block with no heading: a rule, the health pill (the word, shaded in
    the health's colour; none when health is not set), the headline in bold, the supporting sentence in grey, a rule. A content with
    none of the three is left out. The words are the published content's own; none are added."""
    c = sec.get("content") if isinstance(sec.get("content"), dict) else {}
    health, headline, sentence = (c[k].strip() if isinstance(c.get(k), str) else "" for k in ("health", "headline", "sentence"))
    if c.get("pill") is False:      # row 1261: the eye is off, so the pill is not drawn (the page and the file leave it out)
        health = ""
    if not (health or headline or sentence):
        return ""
    out = [para(rule=True, spacing=(120, 0))]
    if health in HEALTH_PILL:
        word, colour = HEALTH_PILL[health]
        fill, text = ctx.hexes(colour)
        out.append(para(run(word, bold=True, color=text), fill=fill, keep_next=bool(headline or sentence), spacing=(120, 60)))
    if headline:
        out.append(para(run(headline, bold=True, size=28), keep_next=bool(sentence), spacing=(60, 60)))
    if sentence:
        out.append(para(run(sentence, color=ctx.tok["grey-700"]), spacing=(0, 60)))
    out.append(para(rule=True, spacing=(0, 120)))
    return "".join(out)


def section_glancetemplate(published, ctx, title, sec):
    """Row 1264 slice 7: the glance template as the View draws it: the tiles in the body's order (only the kept ones), the health tile
    in its place or on a row of its own, each as label, figure, tag and note, as many to a line as the View draws (3 or 4, 2 at half width). Nothing to show leaves the section out."""
    got = glance_print.read(published, sec)
    out = [_heading(title)]
    h = got["health_row"]
    if h:
        fill = text = None
        if h["colour"]:
            fill, text = ctx.hexes(h["colour"])
        out.append(para(run(h["label"] + ": ", bold=True) + run(h["figure"], bold=True, color=text), fill=fill, spacing=(60, 60), keep_next=bool(h["colour"])))
        if h["colour"]:
            out.append(picture_para(ctx, lambda: (docx_graphics.health_bar(h["colour"], ctx.tok), h["label"] + ": " + h["figure"]), TEXT_W, keep_next=True, spacing=(0, 60)))
        if h["note"]:
            out.append(text_paras(h["note"], ctx, style=None))
    tiles = got["tiles"]
    if tiles:
        cells = []
        for t in tiles:
            fill = text = None
            if t["colour"]:
                fill, text = ctx.hexes(t["colour"])
            body = para(run(t["label"], color=ctx.tok["grey-700"], size=16), "TableText")
            if t["figure"]:
                body += para(run(t["figure"], bold=True, color=text, size=32), "TableText")
            if t["tag"]:
                body += para(run(t["tag"], bold=True, size=16), "TableText")
            if t["note"]:
                body += para(run(t["note"], size=16), "TableText")
            cells.append((body, fill))
        per = got["per_line"]
        lines = [cells[i:i + per] for i in range(0, len(cells), per)]
        lines = [r + [(para("", "TableText"), None)] * (per - len(r)) for r in lines]
        out.append(table(ctx, None, [1] * per, lines))
    return "".join(out) if (h or tiles) else ""


def section_callout(published, ctx, title, sec):
    """Row 1272 (1291), ruling M8780: a callout as a text block, in Dashboard order: the heading (the callout's own title, else "Callout"; left out when its
    heading is off), one bold line "Category: <category>. Colour: <colour>. Icon: <icon>." (empty parts left out; Plain and No icon say nothing extra),
    then the words. Tile on: the line and words sit in one shaded box (the colour is a help, never the carrier). A callout is left out only when its title, category, colour, icon and words are all empty (row 1272, ruling M8851)."""
    c = sec.get("content") if isinstance(sec.get("content"), dict) else {}
    cat, col, ico = (str(c.get(k) or "").strip() for k in ("category", "colour_name", "icon_name"))
    parts = [f"{label}: {w}." for label, w in (("Category", cat), ("Colour", "" if col == "Plain" else col), ("Icon", ico)) if w]
    line = " ".join(parts)
    name = str(c.get("title") or "").strip()
    body = rich(c["html"], ctx) if c.get("html") else "".join(text_paras(p, ctx, style=None) for p in c.get("paras") or ())
    if not (name or line or body):
        return ""
    inner = (para(run(line, bold=True), "TableText") if line else "") + body
    out = _heading(name or "Callout") if c.get("heading", True) else ""
    if c.get("tile", True):
        fill = ctx.hexes(CALLOUT_FILL[c["colour"]])[0] if c.get("colour") in CALLOUT_FILL else None
        return out + table(ctx, None, [1], [[(inner, fill)]])
    return out + inner


SIMPLE = {"callout": section_callout, "workitems": section_workitems, "imagecap": section_imagecap, "textimage": section_textimage, "current": section_current, "text": section_text, "milestones": section_milestones, "actions": section_actions,
          "raid": section_raid, "decisions": section_decisions, "gantt": section_gantt,
          "reportheadline": section_reportheadline, "glancetemplate": section_glancetemplate}


def title_block(published, ctx):
    p = published["data"].get("project") or {}
    week = p.get("week_ending")
    out = [para(run(p.get("name") or p.get("code") or "Report"), "Title"),
           para(run(f"Week ending {_date(week)}" if week else f"As at {_date(published['as_at'])}"), "Subtitle")]
    pairs = [("Project code", p.get("code")), ("Client", p.get("client_name")), ("Sponsor", p.get("sponsor")),
             ("Phase", p.get("phase")), ("As at", _date(published["as_at"]))]
    rows = [[(para(run(k, color=ctx.tok["grey-700"], size=18), "TableText"), None), word_cell(v, ctx)] for k, v in pairs if v]
    out.append(table(ctx, None, [20, 80], rows, borders=False))
    return "".join(out)


def sections(published, ctx):
    """The report's body, section by section, in the published order: a list of (section type, XML). A section with nothing to
    say (an empty current state or text) is an empty string and is left out."""
    shown = [s for s in published["sections"] if s.get("type") in TITLES]
    kept = _kept(published, {s["type"] for s in shown})
    out = []
    for s in shown:
        t = s["type"]
        title = s.get("title") or TITLES[t]
        if t == "glance":
            xml = section_glance(published, ctx, title, s, kept)
        elif t == "usecases":
            xml = section_usecases(published, ctx, title, s, kept)
        else:
            xml = SIMPLE[t](published, ctx, title, s)
        if xml:
            out.append((t, xml))
    return out


# ===== The parts =====
def styles_xml(tok):
    def style(sid, name, based=None, nxt=None, ppr="", rpr="", kind="paragraph", q=True):
        default = ' w:default="1"' if sid in ("Normal", "DefaultParagraphFont") else ""
        return (f'<w:style w:type="{kind}" w:styleId="{sid}"{default}>'
                f'<w:name w:val="{name}"/>' + (f'<w:basedOn w:val="{based}"/>' if based else "")
                + (f'<w:next w:val="{nxt}"/>' if nxt else "") + ("<w:qFormat/>" if q else "")
                + (f"<w:pPr>{ppr}</w:pPr>" if ppr else "") + (f"<w:rPr>{rpr}</w:rPr>" if rpr else "") + "</w:style>")

    ink, navy, muted = tok["brand-ink"], tok["brand-navy"], tok["grey-700"]

    def colour(c):
        return f'<w:color w:val="{c}"/>'

    return HEAD + (
        f'<w:styles {ROOT}><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:eastAsia="{FONT}" '
        f'w:cs="{FONT}"/>{colour(ink)}<w:sz w:val="20"/><w:szCs w:val="20"/><w:lang w:val="en-GB" w:eastAsia="en-GB" '
        'w:bidi="ar-SA"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="100" w:line="264" w:lineRule="auto"/>'
        "</w:pPr></w:pPrDefault></w:docDefaults>"
        + style("Normal", "Normal")
        + style("DefaultParagraphFont", "Default Paragraph Font", kind="character", q=False)
        + style("Title", "Title", "Normal", "Normal", '<w:spacing w:before="0" w:after="60"/>',
                f'<w:b/>{colour(navy)}<w:sz w:val="52"/><w:szCs w:val="52"/>')
        + style("Subtitle", "Subtitle", "Normal", "Normal", '<w:spacing w:after="160"/>',
                f'{colour(muted)}<w:sz w:val="24"/><w:szCs w:val="24"/>')
        + style("Heading1", "heading 1", "Normal", "Normal", '<w:keepNext/><w:spacing w:before="360" w:after="120"/><w:outlineLvl w:val="0"/>',
                f'<w:b/>{colour(navy)}<w:sz w:val="32"/><w:szCs w:val="32"/>')
        + style("Heading2", "heading 2", "Normal", "Normal", '<w:keepNext/><w:spacing w:before="240" w:after="80"/><w:outlineLvl w:val="1"/>',
                f'<w:b/>{colour(navy)}<w:sz w:val="26"/><w:szCs w:val="26"/>')
        + style("Heading3", "heading 3", "Normal", "Normal", '<w:keepNext/><w:spacing w:before="200" w:after="60"/><w:outlineLvl w:val="2"/>',
                f'<w:b/>{colour(navy)}<w:sz w:val="23"/><w:szCs w:val="23"/>')
        + style("Heading4", "heading 4", "Normal", "Normal", '<w:keepNext/><w:spacing w:before="160" w:after="40"/><w:outlineLvl w:val="3"/>',
                f'<w:b/>{colour(ink)}<w:sz w:val="21"/><w:szCs w:val="21"/>')
        + style("ListParagraph", "List Paragraph", "Normal", None, '<w:spacing w:after="40"/>')
        + style("Quote", "Quote", "Normal", "Normal",
                f'<w:pBdr><w:left w:val="single" w:sz="18" w:space="8" w:color="{tok["grey-300"]}"/></w:pBdr>'
                '<w:ind w:left="360"/>', f'<w:i/>{colour(muted)}')
        + style("TableText", "Table Text", "Normal", None, '<w:spacing w:before="0" w:after="20" w:line="240" w:lineRule="auto"/>',
                '<w:sz w:val="18"/><w:szCs w:val="18"/>')
        + style("Footer", "footer", "Normal", None, f'<w:tabs><w:tab w:val="right" w:pos="{TEXT_W}"/></w:tabs>',
                f'{colour(muted)}<w:sz w:val="16"/><w:szCs w:val="16"/>')
        + style("Hyperlink", "Hyperlink", "DefaultParagraphFont", None, rpr=f'{colour(tok["status-blue-text"])}<w:u w:val="single"/>',
                kind="character", q=False)
        + "</w:styles>")


def numbering_xml(ordered_lists):
    def abstract(n, fmt, glyph):
        levels = "".join(
            f'<w:lvl w:ilvl="{i}"><w:start w:val="1"/><w:numFmt w:val="{fmt}"/><w:lvlText w:val="{glyph(i)}"/>'
            f'<w:lvlJc w:val="left"/><w:pPr><w:ind w:left="{360 * (i + 1)}" w:hanging="360"/></w:pPr></w:lvl>'
            for i in range(MAX_LEVELS))
        return f'<w:abstractNum w:abstractNumId="{n}"><w:multiLevelType w:val="hybridMultilevel"/>{levels}</w:abstractNum>'

    nums = '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>' + "".join(
        f'<w:num w:numId="{n + 1}"><w:abstractNumId w:val="1"/><w:lvlOverride w:ilvl="0"><w:startOverride w:val="1"/>'
        "</w:lvlOverride></w:num>" for n in range(1, ordered_lists + 1))
    return HEAD + (f'<w:numbering {ROOT}>' + abstract(0, "bullet", lambda i: "•◦▪‣"[i])
                   + abstract(1, "decimal", lambda i: f"%{i + 1}.") + nums + "</w:numbering>")


def footer_xml(code, as_at, tok):
    def field(instr):
        return f'<w:fldSimple w:instr=" {instr} "><w:r><w:t>1</w:t></w:r></w:fldSimple>'
    return HEAD + (f'<w:ftr {ROOT}><w:p><w:pPr><w:pStyle w:val="Footer"/></w:pPr>{run(f"{code} report, as at {_date(as_at)}")}'
                   f'<w:r><w:tab/></w:r>{run("Page ")}{field("PAGE")}{run(" of ")}{field("NUMPAGES")}</w:p></w:ftr>')


def settings_xml():
    return HEAD + (f'<w:settings {ROOT}><w:zoom w:percent="100"/><w:defaultTabStop w:val="720"/>'
                   '<w:characterSpacingControl w:val="doNotCompress"/></w:settings>')


def rels_xml(ctx):
    base = f"{NS_R}"
    rel = [f'<Relationship Id="rId1" Type="{base}/styles" Target="styles.xml"/>',
           f'<Relationship Id="rId2" Type="{base}/numbering" Target="numbering.xml"/>',
           f'<Relationship Id="rId3" Type="{base}/settings" Target="settings.xml"/>',
           f'<Relationship Id="rId4" Type="{base}/footer" Target="footer1.xml"/>']
    rel += [f'<Relationship Id="{rid}" Type="{base}/hyperlink" Target="{attr(address)}" TargetMode="External"/>'
            for address, rid in ctx.links.items()]
    rel += [f'<Relationship Id="{rid}" Type="{base}/image" Target="media/{name}"/>' for rid, name in ctx.images.values()]
    return HEAD + f'<Relationships xmlns="{NS_REL}">' + "".join(rel) + "</Relationships>"


def content_types_xml(pictures=False, jpeg=False):
    o = [("/word/document.xml", f"{DOC_TYPE}.document.main+xml"), ("/word/styles.xml", f"{DOC_TYPE}.styles+xml"),
         ("/word/numbering.xml", f"{DOC_TYPE}.numbering+xml"), ("/word/settings.xml", f"{DOC_TYPE}.settings+xml"),
         ("/word/footer1.xml", f"{DOC_TYPE}.footer+xml"),
         ("/docProps/core.xml", "application/vnd.openxmlformats-package.core-properties+xml"),
         ("/docProps/app.xml", "application/vnd.openxmlformats-officedocument.extended-properties+xml")]
    return HEAD + (f'<Types xmlns="{NS_CT}"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   + ('<Default Extension="png" ContentType="image/png"/>' if pictures else "")
                   + ('<Default Extension="jpeg" ContentType="image/jpeg"/>' if jpeg else "")
                   + "".join(f'<Override PartName="{p}" ContentType="{t}"/>' for p, t in o) + "</Types>")


def package_rels_xml():
    return HEAD + (f'<Relationships xmlns="{NS_REL}">'
                   f'<Relationship Id="rId1" Type="{NS_R}/officeDocument" Target="word/document.xml"/>'
                   '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" '
                   'Target="docProps/core.xml"/>'
                   f'<Relationship Id="rId3" Type="{NS_R}/extended-properties" Target="docProps/app.xml"/></Relationships>')


def core_xml(title, as_at):
    stamp = f"{as_at}T00:00:00Z"
    return HEAD + ('<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
                   'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
                   'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
                   f"<dc:title>{esc(title)}</dc:title><dc:creator>{FIXED_NAME}</dc:creator>"
                   f"<cp:lastModifiedBy>{FIXED_NAME}</cp:lastModifiedBy>"
                   f'<dcterms:created xsi:type="dcterms:W3CDTF">{stamp}</dcterms:created>'
                   f'<dcterms:modified xsi:type="dcterms:W3CDTF">{stamp}</dcterms:modified></cp:coreProperties>')


def app_xml():
    return HEAD + ('<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
                   f"<Application>{FIXED_NAME}</Application></Properties>")


def document_xml(body):
    return HEAD + (f'<w:document {ROOT}><w:body>{body}<w:sectPr><w:footerReference w:type="default" r:id="rId4"/>'
                   f'<w:pgSz w:w="{PAGE_W}" w:h="{PAGE_H}"/><w:pgMar w:top="{MARGIN}" w:right="{MARGIN}" w:bottom="{MARGIN}" '
                   f'w:left="{MARGIN}" w:header="567" w:footer="567" w:gutter="0"/></w:sectPr></w:body></w:document>')


def zip_bytes(parts):
    """The parts as a zip, the same bytes for the same parts: fixed order and time, system and permission bits."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts:
            info = zipfile.ZipInfo(name, date_time=ZIP_TIME)
            info.compress_type, info.create_system, info.external_attr = zipfile.ZIP_DEFLATED, 3, 0o644 << 16
            z.writestr(info, data if isinstance(data, bytes) else data.encode("utf-8"), compresslevel=6)
    return buf.getvalue()


# ===== The file =====
def check_published(published):
    """Refuse something that is not select()'s output, in words."""
    try:
        data, shown, as_at = published["data"], published["sections"], published["as_at"]
        date.fromisoformat(as_at)
    except (KeyError, TypeError, ValueError):
        raise WordError("The report could not be made: its rows are missing, or the report date is not a real day. Restart clark and try again.") from None
    if not isinstance(data, dict) or not isinstance(shown, list) or not (data.get("project") or {}).get("code"):
        raise WordError("The report could not be made: there is no project to put in it. Restart clark and try again.")


def build(published, colours=None):
    """The Word report's bytes from `publish.select()`'s output. The same rows give the same bytes. Raises WordError, in plain
    words, if the rows are not a report, a text is too long, or the file would be over MAX_BYTES."""
    check_published(published)
    project = published["data"]["project"]
    ctx = _Ctx(palette(colours), published["as_at"])
    body = title_block(published, ctx) + "".join(xml for _, xml in sections(published, ctx))
    parts = [("[Content_Types].xml", content_types_xml(any(n.endswith(".png") for _, n in ctx.images.values()), any(n.endswith(".jpeg") for _, n in ctx.images.values()))), ("_rels/.rels", package_rels_xml()),
             ("docProps/core.xml", core_xml(project.get("name") or project["code"], published["as_at"])),
             ("docProps/app.xml", app_xml()), ("word/document.xml", document_xml(body)),
             ("word/styles.xml", styles_xml(ctx.tok)), ("word/numbering.xml", numbering_xml(ctx.lists)),
             ("word/settings.xml", settings_xml()), ("word/footer1.xml", footer_xml(project["code"], published["as_at"], ctx.tok)),
             ("word/_rels/document.xml.rels", rels_xml(ctx))]
    parts += [(f"word/media/{name}", png) for png, (_, name) in ctx.images.items()]
    data = zip_bytes(parts)
    if len(data) > MAX_BYTES:
        raise WordError(f"The report is {len(data) / 1048576:.1f} MB, which is over the {MAX_BYTES // 1048576} MB limit. "
                        "Leave out some sections or pictures and try again.")
    return data


def file_name(code, week_ending, as_at, folder=None):
    """{CODE}-report-{week_ending or as_at}.docx, made safe for Windows, OneDrive and SharePoint (platform.safe_name)."""
    return platform.safe_name(f"{code}-report-{week_ending or as_at}.docx", folder)
