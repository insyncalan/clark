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
blockquote, hr, br, a checklist box, and a link only to https: or mailto:. The sanitiser has no img, so Word carries no picture.

The same rows give the same bytes: parts in a fixed order, a fixed time, system and permission bits on every zip entry, relationship
ids numbered in order of use, no clock and nothing left to chance, and the file's author and last editor are the word clark, never a person.
(The compressed bytes also depend on the zlib in use, so compare two builds made on one machine.)

What is not carried: links between items, labels, pictures, comments, and the editor's tile order and outline colours (they are not
in the published rows). A Cancelled milestone is left out, as the page's client list leaves it out. A shown table with no rows says
"None recorded."; an empty current state or text section is left out (FR-14c).

Colours are the committed tokens (excel_colours.TOKENS); `build(..., colours={"brand-navy": "062F3A", ...})` lays a
local brand's values over them, each a #rrggbb or rrggbb that is checked, so a brand cannot put markup into the file.

Standard library only, Python 3.9.
"""
import io
import re
import zipfile
from datetime import date

from clark import excel_colours as colours_table
from clark import glance, platform, sanitise

MAX_BYTES = 5 * 1024 * 1024               # NFR-8: a file larger than this is refused (as publish.MAX_BYTES)
NONE = "None recorded."                   # creaite's own words (docx_tools.NONE)
PAGE_W, PAGE_H, MARGIN = 11906, 16838, 1134      # A4, 2 cm
TEXT_W = PAGE_W - 2 * MARGIN                      # 9638 twentieths of a point between the margins
FIXED_NAME = "clark"
ZIP_TIME = (1980, 1, 1, 0, 0, 0)
FONT = "Arial"

NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
DOC_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml"
HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
ROOT = f'xmlns:w="{NS_W}" xmlns:r="{NS_R}"'

TOKENS = dict(colours_table.TOKENS)
HEX = re.compile(r"#?([0-9A-Fa-f]{6})")
NOT_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ud800-\udfff￾￿]")

TITLES = {"current": "Current state", "glance": "At a glance", "usecases": "Use cases", "milestones": "Milestones",
          "text": "Notes", "raid": "Risks and issues", "actions": "Actions", "decisions": "Decisions"}
HIDDEN_BY_KIND = ("actions", "raid", "decisions")
HEADING_STYLE = {"h1": "Heading2", "h2": "Heading3", "h3": "Heading4"}
MAX_LEVELS = 3                                           # list levels written


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

    def link(self, address):
        if address not in self.links:
            self.links[address] = f"rId{5 + len(self.links)}"
        return self.links[address]

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


def para(runs="", style=None, keep_next=False, num=None, rule=False, fill=None, tabs=None, spacing=None):
    """One paragraph. `num` is (numId, level) for a list item; `rule` draws a line under it; `fill` shades it."""
    props = (f'<w:pStyle w:val="{style}"/>' if style else "") + ("<w:keepNext/>" if keep_next else "")
    if num:
        props += f'<w:numPr><w:ilvl w:val="{int(num[1])}"/><w:numId w:val="{int(num[0])}"/></w:numPr>'
    if rule:
        props += '<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="C4CEE3"/></w:pBdr>'
    if fill:
        props += f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>'
    if tabs:
        props += f'<w:tabs><w:tab w:val="right" w:pos="{int(tabs)}"/></w:tabs>'
    if spacing:
        props += f'<w:spacing w:before="{int(spacing[0])}" w:after="{int(spacing[1])}"/>'
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
    """Column widths in twentieths of a point that add up to the text width exactly (the last column takes the rounding)."""
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


def word_cell(text, ctx, colour=None, late=False, extra=()):
    """A cell of words. `colour` (red, amber, green, blue, grey) gives a fill and text of the same hue, the words always shown;
    `late` draws the text red; `extra` are quieter lines under it."""
    fill = color = None
    if colour in colours_table.COLOURS:
        fill, color = ctx.hexes(colour)
    elif late:
        color = ctx.tok["status-red-text"]
    body = text_paras(text, ctx, color=color)
    body += "".join(para(run(x, color=ctx.tok["grey-700"], size=16), "TableText") for x in extra if x)
    return body, fill


# ===== Rich text =====
class _Rich:
    """Maps cleaned rich text (sanitise's allow-list) to paragraphs."""

    def __init__(self, ctx):
        self.ctx, self.out, self.runs = ctx, [], []
        self.fmt = {"strong": 0, "em": 0, "s": 0}
        self.link = None
        self.stack, self.lists = [], []

    def add_text(self, text):
        if not text:
            return
        c = self.ctx
        r = run(text, bold=bool(self.fmt["strong"]), italic=bool(self.fmt["em"]), strike=bool(self.fmt["s"]),
                color=c.tok["status-blue-text"] if self.link else None, style="Hyperlink" if self.link else None)
        self.runs.append(f'<w:hyperlink r:id="{self.link}" w:history="1">{r}</w:hyperlink>' if self.link else r)

    def flush(self):
        runs, self.runs = "".join(self.runs), []
        if not re.sub(r"<[^>]*>", "", runs).strip() and "<w:br/>" not in runs:
            return
        heading = next((HEADING_STYLE[t] for t in reversed(self.stack) if t in HEADING_STYLE), None)
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
        elif name == "a":
            address = sanitise.href(dict(attrs).get("href"))
            if address and address.lower().startswith(("https://", "mailto:")):
                self.link = c.link(address)
        if name not in ("br", "hr", "input"):
            self.stack.append(name)

    def end(self, name):
        if name in self.fmt:
            self.fmt[name] = max(0, self.fmt[name] - 1)
        elif name == "a":
            self.link = None
        if name in ("p", "h1", "h2", "h3", "li", "blockquote", "ul", "ol"):
            self.flush()
        if name in self.stack:
            while self.stack and self.stack.pop() != name:
                pass
        if name in ("ul", "ol") and self.lists:
            self.lists.pop()


def rich(html, ctx):
    """Rich text as Word paragraphs, after cleaning it again with the sanitiser. Raises WordError for a text that is too long."""
    try:
        clean = sanitise.clean_html(html)
    except sanitise.SanitiseError as e:
        raise WordError(str(e)) from None
    r = _Rich(ctx)
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


def _words(row, field, own):
    """The client's wording when the row has some, else the row's own text (data-model.md: client_message is optional)."""
    return (row.get("client_message") or "").strip() or row.get(own) or ""


def _date(iso):
    return glance.show_date(iso)


def _kept(published, shown):
    """The published rows, in the shape glance reads them for a client (so the counts are the page's)."""
    data = published["data"]
    return {"data": data, "rows": glance.work_rows(data), "use_cases": data.get("use_cases") or [],
            "hidden_types": {t for t in HIDDEN_BY_KIND if t not in shown}}


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
             word_cell(u["headline"], ctx), word_cell(u["words"], ctx)] for u in strip["rows"]]
    out.append(table(ctx, ["Ref", "Use case", "Status", "Headline", "Work items"], [8, 28, 12, 32, 20], rows))
    standing = {u["id"]: u.get("standing") for u in kept["use_cases"]}
    for u in strip["rows"]:
        body = rich(standing.get(u["id"]), ctx)
        linked = [str(r["id"]) for r in glance.use_case_items(kept, u["id"]) if r.get("id")]
        if body or linked:
            out.append(_heading(f"{u['ref'] + ' ' if u['ref'] else ''}{u['title']}".strip(), 3) + body)
            if linked:
                out.append(para(run("Linked work items: " + ", ".join(linked), color=ctx.tok["grey-700"], size=18)))
    return "".join(out)


def section_milestones(published, ctx, title, sec):
    rows = []
    for m in _rows(published, "milestones"):
        if m.get("status") == "Cancelled":
            continue
        achieved = m.get("status") == "Done"
        slip = m.get("slip_days")
        name = para(run(m.get("name") or "", bold=True), "TableText")
        for line, kw in ((m.get("description"), {}), (m.get("client_message"), {}),
                         (f"Reason: {m['state_reason']}" if m.get("state_reason") else "", {"color": ctx.tok["grey-700"]})):
            if line:
                name += text_paras(line, ctx, **kw)
        if m.get("percent_complete") is not None:
            name += para(run(f"{m['percent_complete']}% complete", color=ctx.tok["grey-700"], size=16), "TableText")
        when = f"Achieved {_date(m.get('actual_date'))}" if achieved else _date(m.get("forecast_date"))
        colour = colours_table.colour_for("milestones", "state", m.get("state"))
        rows.append([word_cell(m.get("id"), ctx), (name, None), word_cell(m.get("owner"), ctx, extra=[m.get("workstream")]),
                     word_cell(_date(m.get("baseline_date")), ctx), word_cell(when, ctx),
                     word_cell(m.get("state_word") or m.get("state"), ctx, colour=colour),
                     word_cell(f"+{slip} days" if slip and not achieved else "", ctx)])
    if not rows:
        return _heading(title) + para(run(NONE))
    return _heading(title) + table(ctx, ["ID", "Milestone", "Owner", "Agreed", "Forecast", "State", "Slip"],
                                   [10, 30, 13, 11, 13, 13, 10], rows)


def _due(table_name, field, row, ctx, extra=()):
    iso = row.get(field)
    late = colours_table.is_late(table_name, field, row, ctx.today)
    return word_cell(_date(iso) + (" (overdue)" if late else "") if iso else "", ctx, late=late, extra=extra)


def section_actions(published, ctx, title, sec):
    rows = []
    for a in _rows(published, "actions"):
        update = f"Latest update: {a['latest_update']}" if a.get("latest_update") else ""
        body = text_paras(_words(a, "client_message", "description"), ctx)
        if update:
            body += text_paras(update, ctx, color=ctx.tok["grey-700"])
        rows.append([word_cell(a.get("id"), ctx), (body, None), word_cell(a.get("owner"), ctx, extra=[a.get("workstream")]),
                     word_cell(a.get("priority"), ctx, colour=colours_table.colour_for("actions", "priority", a.get("priority"))),
                     _due("actions", "due_date", a, ctx), word_cell(a.get("status"), ctx)])
    if not rows:
        return _heading(title) + para(run(NONE))
    return _heading(title) + table(ctx, ["ID", "Action", "Owner", "Priority", "Due", "Status"], [11, 38, 15, 10, 14, 12], rows)


def section_raid(published, ctx, title, sec):
    rows = []
    for r in _rows(published, "raid"):
        both = " / ".join(x for x in (r.get("impact"), r.get("likelihood")) if x)
        rows.append([word_cell(r.get("id"), ctx), word_cell(r.get("type"), ctx),
                     (text_paras(_words(r, "client_message", "description"), ctx), None),
                     word_cell(r.get("owner"), ctx, extra=[r.get("workstream")]),
                     word_cell(r.get("priority"), ctx, colour=colours_table.colour_for("raid", "priority", r.get("priority"))),
                     word_cell(both, ctx), _due("raid", "due_date", r, ctx), word_cell(r.get("status"), ctx)])
    if not rows:
        return _heading(title) + para(run(NONE))
    return _heading(title) + table(ctx, ["ID", "Type", "Item", "Owner", "Priority", "Impact / likelihood", "Due", "Status"],
                                   [9, 9, 30, 13, 9, 11, 11, 8], rows)


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
    return _heading(title) + table(ctx, ["ID", "Decision", "Status", "Made by", "Date"], [11, 40, 12, 15, 22], rows)


SIMPLE = {"current": section_current, "text": section_text, "milestones": section_milestones, "actions": section_actions,
          "raid": section_raid, "decisions": section_decisions}


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
    return HEAD + (f'<w:numbering {ROOT}>' + abstract(0, "bullet", lambda i: "•◦▪"[i])
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
    return HEAD + f'<Relationships xmlns="{NS_REL}">' + "".join(rel) + "</Relationships>"


def content_types_xml():
    o = [("/word/document.xml", f"{DOC_TYPE}.document.main+xml"), ("/word/styles.xml", f"{DOC_TYPE}.styles+xml"),
         ("/word/numbering.xml", f"{DOC_TYPE}.numbering+xml"), ("/word/settings.xml", f"{DOC_TYPE}.settings+xml"),
         ("/word/footer1.xml", f"{DOC_TYPE}.footer+xml"),
         ("/docProps/core.xml", "application/vnd.openxmlformats-package.core-properties+xml"),
         ("/docProps/app.xml", "application/vnd.openxmlformats-officedocument.extended-properties+xml")]
    return HEAD + (f'<Types xmlns="{NS_CT}"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
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
            z.writestr(info, data.encode("utf-8"), compresslevel=6)
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
    parts = [("[Content_Types].xml", content_types_xml()), ("_rels/.rels", package_rels_xml()),
             ("docProps/core.xml", core_xml(project.get("name") or project["code"], published["as_at"])),
             ("docProps/app.xml", app_xml()), ("word/document.xml", document_xml(body)),
             ("word/styles.xml", styles_xml(ctx.tok)), ("word/numbering.xml", numbering_xml(ctx.lists)),
             ("word/settings.xml", settings_xml()), ("word/footer1.xml", footer_xml(project["code"], published["as_at"], ctx.tok)),
             ("word/_rels/document.xml.rels", rels_xml(ctx))]
    data = zip_bytes(parts)
    if len(data) > MAX_BYTES:
        raise WordError(f"The report is {len(data) / 1048576:.1f} MB, which is over the {MAX_BYTES // 1048576} MB limit. "
                        "Leave out some sections or pictures and try again.")
    return data


def file_name(code, week_ending, as_at, folder=None):
    """{CODE}-report-{week_ending or as_at}.docx, made safe for Windows, OneDrive and SharePoint (platform.safe_name)."""
    return platform.safe_name(f"{code}-report-{week_ending or as_at}.docx", folder)
