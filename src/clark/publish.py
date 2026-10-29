"""Publish one HTML report for a project: Local, boxed layout (#39; BRD FR-80, FR-81, FR-83).

One UTF-8 file, {CODE}-report-{week_ending or date}.html: the committed page (clark/page, #35, so a local brand's tokens
are layered) plus three insertions and nothing else: a <meta> Content-Security-Policy straight after <meta charset>, the
report's data in <script type="application/json" id="clark-data"> before </body>, and the project's name as the <title>
with data-mode="view" on <html>. The page's own script finds that block and runs in view mode (no fetch, no token, no
Settings tab). The file has no clark-boot token block and refers to no outside address, and opens from file:// with no server.

What goes in is chosen BEFORE the file is made, by select(): allow-lists, never deny-lists. A row is published only if it is
not archived, its client_visible flag is on, it is not in report_hidden and it carries no label whose behaviour or default
choice is "exclude" (Sensitive always, names compared without case). Each table has a PUBLISH_FIELDS tuple of the columns the
view shows, and nothing else is ever copied, so internal_note, movement, source and the project's folders are not in the file.
select(), clean_html(), render(), csp_meta() and file_name() are pure; read_inputs() reads the database once, read-only.

- Q1 yes: a hidden section of type actions, raid, decisions, milestones or usecases drops that kind's rows and its tab.
- Q2 yes (Head ruling on #39): publish() records the verified file with Store.log_publication, once, after the write is read
  back and compared: a `publications` row with the file's SHA-256 and nothing else (no step, no write to the project row). The
  folder to offer next time is read back from the latest publication (Store.last_publish_folder).
- Q3 no route and no button: the folder arrives as an argument; the Save dialog is a later route's job (platform.choose_save_file).
  `python3 -m clark.publish CODE FOLDER` is for manual runs.
- Q4 yes: a milestone's state_reason and the project's health_reason are published (the text the client reads under the
Not here: To client (#43), Word, comments (#40), spine and cover layouts (#46: they render boxed in v0.1), the editor's section UI (#65).

Standard library only, Python 3.9.
"""
import argparse
import base64
import getpass
import hashlib
from datetime import date
import html as htmllib
import json
import os
import re
import sys
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

from clark import milestones, page, platform
from clark.store import Invalid as StoreInvalid, open_store
from clark.server import csp_hashes        # the one place the policy's hashes are worked out (#33); never copied

MAX_BYTES = 5 * 1024 * 1024               # NFR-8: a file larger than this is refused
VERSION = 1                               # the data block's shape; the page refuses another
KINDS = ("milestones", "actions", "raid", "decisions", "use_cases")
SECTION_OF_KIND = {"milestones": "milestones", "actions": "actions", "raid": "raid", "decisions": "decisions",
                   "use_cases": "usecases"}
WORK_KINDS = ("actions", "raid", "decisions")
# What the editor offers when report_sections has no rows (#65 is not built): this order, none hidden.
DEFAULT_SECTIONS = tuple({"id": f"s-{t}", "type": t, "title": title, "body": "", "beside": 0, "hidden": 0, "sort_order": n}
                         for n, (t, title) in enumerate((("current", "Current state"), ("glance", "At a glance"),
                                                         ("usecases", "Use cases"), ("milestones", "Milestones"),
                                                         ("raid", "Risks and issues"), ("actions", "Actions"),
                                                         ("decisions", "Decisions")), 1))
SECTION_TYPES = ("current", "glance", "usecases", "milestones", "text", "raid", "actions", "decisions")   # not "docs" (v0.1)

# The columns the view shows, per table. Anything not named here is never copied into the file.
PUBLISH_FIELDS = {
    "projects": ("code", "name", "sponsor", "phase", "health", "health_reason", "client_name", "current_state", "week_ending", "layout"),
    "milestones": ("id", "name", "description", "baseline_date", "forecast_date", "status", "sort_order", "percent_complete",
                   "state_reason", "owner", "actual_date", "client_message", "workstream"),
    "workstreams": ("id", "name", "status"),
    "actions": ("id", "description", "workstream", "owner", "priority", "due_date", "status", "raised", "closed",
                "latest_update", "client_message", "milestone", "use_case"),
    "raid": ("id", "type", "workstream", "description", "owner", "due_date", "impact", "likelihood",
             "priority", "status", "raised", "closed", "client_message", "milestone", "use_case"),
    "decisions": ("id", "decision", "made_by", "client_message", "date", "status", "needed_by",
                  "revisit", "replaces", "use_case"),
    "use_cases": ("id", "ref", "title", "status", "headline", "standing", "sort_order"),
    "links": ("from_item", "to_item", "kind"),
}
RICH = {"projects": ("current_state",), "use_cases": ("standing",)}     # HTML the editor wrote: through clean_html
# Read from the database as well, only to decide (never copied): the gates, and what a milestone's state is worked out from.
GATES = {"milestones": ("client_visible", "archived", "state", "state_set"), "workstreams": ("archived",),
         "actions": ("client_visible", "archived"), "raid": ("client_visible", "archived"),
         "decisions": ("client_visible", "archived"), "use_cases": ("client_visible", "archived")}
ORDER = {"milestones": "sort_order, id", "workstreams": "id", "actions": "id", "raid": "id", "decisions": "id",
         "use_cases": "sort_order, id"}
CODE = re.compile(r"[A-Z][A-Z0-9]{2,6}")


class PublishError(RuntimeError):
    """The file was not made, in words a person can act on."""


# ===== Rich text: an allow-list cleaner (creaite's clean_markup, cut down) =====
DROP_WITH_TEXT = {"script", "style", "iframe", "object", "embed", "form", "template", "noscript", "svg", "math", "textarea",
                  "select"}                                   # these and everything inside them; link, meta... just go
VOID = {"br", "hr", "img"}
ALLOWED_TAGS = {"p", "br", "hr", "b", "strong", "i", "em", "u", "s", "sub", "sup", "code", "pre", "blockquote", "span", "div",
                "ul", "ol", "li", "h2", "h3", "h4", "a", "img", "table", "thead", "tbody", "tr", "th", "td"}
ALLOWED_ATTRS = {"a": ("href", "title"), "img": ("src", "alt", "title"), "td": ("colspan", "rowspan"),
                 "th": ("colspan", "rowspan")}
DATA_IMAGE = re.compile(r"data:image/(png|jpeg|gif|webp);base64,[A-Za-z0-9+/=]*", re.I)
SPAN = re.compile(r"[0-9]{1,3}")


def safe_href(value):
    """True for a link a reader may follow: https:, mailto: or a link within the page. Anything else (javascript:, data:, a
    relative or protocol-relative address) is not."""
    v = re.sub(r"[\x00-\x20]+", "", value or "").lower()
    return v.startswith(("https://", "mailto:", "#"))


class _Cleaner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.open, self.skip, self.depth = [], [], None, 0

    def handle_starttag(self, tag, attrs):
        if self.skip:
            self.depth += tag == self.skip
            return
        if tag in DROP_WITH_TEXT:
            self.skip, self.depth = tag, 1
            return
        if tag not in ALLOWED_TAGS:
            return                                                # unwrapped: its text stays
        keep, given = [], dict(attrs)
        for name in ALLOWED_ATTRS.get(tag, ()):
            value = given.get(name)
            if value is None:
                continue
            if name == "href" and not safe_href(value):
                continue
            if name == "src" and not DATA_IMAGE.fullmatch(value.strip()):
                return                                            # an image that isn't embedded is dropped whole
            if name in ("colspan", "rowspan") and not SPAN.fullmatch(value.strip()):
                continue
            keep.append(f' {name}="{htmllib.escape(value.strip() if name == "src" else value, quote=True)}"')
        if tag == "img" and not any(a.startswith(" src=") for a in keep):
            return
        if tag == "a":
            keep.append(' rel="noopener noreferrer"')
        self.out.append(f"<{tag}{''.join(keep)}>")
        if tag not in VOID:
            self.open.append(tag)

    def handle_endtag(self, tag):
        if self.skip:
            if tag == self.skip:
                self.depth -= 1
                if self.depth == 0:
                    self.skip = None
            return
        if tag in self.open:
            while self.open:
                done = self.open.pop()
                self.out.append(f"</{done}>")
                if done == tag:
                    break

    def handle_data(self, data):
        if not self.skip:
            self.out.append(htmllib.escape(data, quote=False))

    def close_all(self):
        self.close()
        while self.open:
            self.out.append(f"</{self.open.pop()}>")


def clean_html(text):
    """`text` (HTML the editor wrote) reduced to the allow-list: no script, style, iframe, object, form, link or meta, no
    on* or style attributes, an img only if it is embedded (data:image/png, jpeg, gif or webp), a link only to https:,
    mailto: or this page. Text is always escaped again, so what comes back is well formed and can't reach outside."""
    if not isinstance(text, str) or not text:
        return ""
    c = _Cleaner()
    c.feed(text)
    c.close_all()
    return "".join(c.out)


# ===== Choosing what is published (pure) =====
def _excluded_labels(rules):
    """The label names (lower case) that keep a row out: Sensitive, and any label whose behaviour or default choice is
    exclude."""
    out = {"sensitive"}
    out.update(str(r.get("name", "")).casefold() for r in rules or ()
               if r.get("behaviour") == "exclude" or r.get("default_choice") == "exclude")
    return out


REASON_LIMIT = 2000                                             # the writer's cap on a project's health reason (store.REASON_LIMIT)
_UNSEEN = frozenset({"Cc", "Cf", "Cs", "Co", "Zl", "Zp"})


def reason_text(value):
    """clark (#45 review): a project's health reason as the file carries it, whatever is stored (an old row, or one written
    around the writer): line breaks kept (a Windows one made plain), every other control, format, surrogate, private-use or
    separator character dropped (a bidi override, a zero-width space), cut at REASON_LIMIT characters. None stays None."""
    if value is None:
        return None
    text = str(value).replace("\r\n", "\n")
    return "".join(c for c in text if c == "\n" or unicodedata.category(c) not in _UNSEEN)[:REASON_LIMIT]


def _pick(row, fields):
    return {f: row.get(f) for f in fields}


def select(inputs):
    """What goes in the file, from `inputs` (read_inputs' shape: data as Store.data_for gives it, and hidden, sections,
    label_rules, changes, undone, as_at). Returns {"data", "sections", "tabs", "as_at"}. Everything not allowed is absent,
    not hidden: dropped rows, fields outside PUBLISH_FIELDS, and what only they reach (links, labels, workstreams)."""
    d, as_at = inputs["data"], inputs["as_at"]
    project = d.get("project") or {}
    code = project.get("code")
    if not code:
        raise PublishError("There is no project to publish.")
    sections = sorted(inputs.get("sections") or DEFAULT_SECTIONS, key=lambda s: (s.get("sort_order", 0), str(s.get("id"))))
    hidden_types = {s.get("type") for s in sections if s.get("hidden")}
    hidden_ids = set(inputs.get("hidden") or ())
    blocked = _excluded_labels(inputs.get("label_rules"))
    item_labels = d.get("labels") or {}

    def keep(row, table):
        return (row.get("archived") == 0 and ("client_visible" not in GATES[table] or row.get("client_visible") == 1)
                and row.get("project", code) == code and row.get("id") not in hidden_ids
                and not any(str(n).casefold() in blocked for n in item_labels.get(row.get("id"), ())))

    rows = {k: ([r for r in d.get(k) or () if keep(r, k)] if SECTION_OF_KIND[k] not in hidden_types else [])
            for k in KINDS}
    ids = {k: {r["id"] for r in rows[k]} for k in KINDS}
    linkable = ids["milestones"] | ids["actions"] | ids["raid"] | ids["decisions"]

    def ref(c, field, kind):
        """A pointer at a row that isn't published reads as nothing."""
        if field in c and c[field] not in ids[kind]:
            c[field] = None

    out = {}
    for k in KINDS:
        out[k] = []
        for r in rows[k]:
            c = _pick(r, PUBLISH_FIELDS[k])
            for f in RICH.get(k, ()):
                c[f] = clean_html(c[f])
            ref(c, "milestone", "milestones")
            ref(c, "use_case", "use_cases")
            ref(c, "replaces", "decisions")
            if k == "milestones":
                mine = [x for x in inputs.get("changes") or () if x.get("item_id") == r["id"]]
                state = milestones.milestone_state(r, as_at)
                c.update(state=state, state_word=milestones.client_word(state), slip_days=milestones.slip_days(r, as_at),
                         original_date=milestones.original_date(mine, r["id"], r.get("baseline_date"),
                                                                inputs.get("undone") or ()))
            out[k].append(c)
    used = {str(r.get("workstream")).casefold() for k in ("milestones", "actions", "raid") for r in rows[k] if r.get("workstream")}
    out["workstreams"] = [_pick(w, PUBLISH_FIELDS["workstreams"]) for w in d.get("workstreams") or ()
                          if w.get("archived") == 0 and (str(w.get("name")).casefold() in used or w.get("id") in used)]
    out["links"] = [_pick(x, PUBLISH_FIELDS["links"]) for x in d.get("links") or ()
                    if x.get("from_item") in linkable and x.get("to_item") in linkable]
    out["labels"] = {i: list(item_labels[i]) for i in sorted(linkable) if item_labels.get(i)}
    proj = _pick(project, PUBLISH_FIELDS["projects"])
    proj["health_reason"] = reason_text(proj["health_reason"])
    proj["current_state"] = "" if "current" in hidden_types else clean_html(proj["current_state"])
    out["project"] = proj

    shown = []
    pairs = set()                  # ids that open a row of two whose halves BOTH show: rows are read from every section, then the hidden are left out
    i = 0
    while i < len(sections):
        if sections[i].get("beside") and i + 1 < len(sections):
            if all(not x.get("hidden") and x.get("type") in SECTION_TYPES for x in sections[i:i + 2]):
                pairs.add(sections[i]["id"])
            i += 1
        i += 1
    for s in sections:
        if s.get("hidden") or s.get("type") not in SECTION_TYPES:
            continue
        c = {"id": s["id"], "type": s["type"], "title": s.get("title") or "", "beside": 1 if s["id"] in pairs else 0}
        if s["type"] == "text":
            c["body"] = clean_html(s.get("body"))
        shown.append(c)
    tabs = ["dashboard"]
    if any(SECTION_OF_KIND[k] not in hidden_types for k in WORK_KINDS):
        tabs.append("work")
    if "milestones" not in hidden_types:
        tabs.append("milestones")
    return {"data": out, "sections": shown, "tabs": tabs, "as_at": as_at}


# ===== The file (pure) =====
def _once(text, old, new):
    if text.count(old) < 1:
        raise PublishError("The page clark builds has changed shape, so no report could be made from it. Rebuild the page "
                           f"(python3 dev/tools/build_page.py). Missing: {old[:40]}")
    return text.replace(old, new, 1)


# A <style> start or end tag as the HTML parser reads it: the name must be followed by white space, / or >, and the letters are
# ASCII only (re.A: U+017F and U+212A are not s and k in a tag, so the scan and the page agree).
STYLE_START = re.compile(r"<style(?=[\t\n\f\r />])", re.I | re.A)
STYLE_END = re.compile(r"</style(?=[\t\n\f\r />])", re.I | re.A)


def style_texts(text):
    """The text inside each <style>...</style>, in order, as a list. Linear in the length of `text`: each step is a plain
    search forward that never goes back, and every search that finds nothing ends the scan (a lazy regex with an open-ended
    tail is quadratic on <style></style </style ...). As a browser does, a style with no end tag runs to the end of the text
    and is read in full, so a missing </style> hides nothing; a start tag with no > is not a tag and ends the scan."""
    found, pos = [], 0
    while True:
        start = STYLE_START.search(text, pos)
        if start is None:
            return found
        opened = text.find(">", start.end())
        if opened < 0:
            return found
        end = STYLE_END.search(text, opened + 1)
        if end is None:
            found.append(text[opened + 1:])
            return found
        found.append(text[opened + 1:end.start()])
        closed = text.find(">", end.end())
        if closed < 0:
            return found
        pos = closed + 1


def check_brand(page_text):
    """Refuse a brand that reaches outside the file: an @import, or a url() that isn't data:. A font has to be embedded in
    tokens.css as data. (The policy would block it too, but a report with a missing font is refused, not published.)"""
    for css in style_texts(page_text):
        if re.search(r"@import", css, re.I):
            raise PublishError("The brand's tokens.css uses @import, which would reach outside the file: embed the font in "
                               "tokens.css instead.")
        for m in re.finditer(r"url\(\s*([\"']?)(.*?)\1\s*\)", css, re.S | re.I):
            if not m.group(2).strip().lower().startswith("data:"):
                raise PublishError("The brand's tokens.css names a font or image by address, which would reach outside the "
                                   "file: embed the font in tokens.css instead.")


# The block data_block() writes, and only where render() puts it: straight before the last </body>, on a line of its own. Its
# text has no `<` (data_block writes every one as \u003c), so the match cannot start at an imitation earlier in the file and
# run on past the first </script>. An opener anywhere else is page markup and is scanned like the rest (#106).
DATA_BLOCK = re.compile(r'<script type="application/json" id="clark-data">[^<]*</script>\n\Z')


def without_data_block(text):
    """`text` with the one clark-data block the builder inserted cut out: the one that ends exactly where the last </body> begins.
    Nothing else is cut, whatever it looks like."""
    end = text.rfind("</body>")
    m = DATA_BLOCK.search(text, 0, end) if end >= 0 else None
    return text if m is None else text[:m.start()] + text[m.end():]


LINK_START = re.compile(r"<link\b", re.I | re.A)         # ASCII letters only: U+212A is not a k in a tag (as for STYLE_START)
ICON_PAYLOAD = re.compile(r"base64,([A-Za-z0-9+/=]+)")


def icon_link(text, start):
    """The SHA-256 of the picture if the <link at text[start] is clark's own icon link (#73), else None. It is if its whole text,
    up to the first >, equals page.icon_link() of the picture its payload decodes to, character for character: the one spelling
    the build writes (rel, type, href in that order, double quotes, one space between, no other attribute), so nothing can ride
    in the spacing, an attribute or a different spelling. The picture must be one of page.ICON_LINKS' (by SHA-256 of its bytes)."""
    tag = text[start:text.find(">", start) + 1]
    m = ICON_PAYLOAD.search(tag)
    if not tag or not m:
        return None
    try:
        picture = base64.b64decode(m.group(1), validate=True)
    except ValueError:
        return None
    digest = hashlib.sha256(picture).hexdigest()
    if digest not in page.ICON_LINKS:
        return None
    rel, mime = page.ICON_LINKS[digest]
    return digest if tag == page.icon_link(rel, mime, base64.b64encode(picture).decode("ascii")) else None


def has_other_links(text):
    """True if the text has a <link that is not exactly one of clark's three icon links, or the same one twice. Wherever it
    stands (a comment, a script, a template), every <link in the text is checked and only the exact spelling passes."""
    found = [icon_link(text, m.start()) for m in LINK_START.finditer(text)]
    return None in found or len(set(found)) != len(found)


def outside_addresses(text):
    """What in a finished file reaches outside it, as a list of plain-words problems (empty when it is clean). The rules of
    #39's test of the finished bytes, in one place so #43 runs the same ones on the copy in the client folder: no <link> (but
    clark's own three icon links, each the pinned picture itself as data:, #73), no script src, no src/href/action/... that is an address, no meta refresh, no @import (an @font-face is fine: the font is data:), no url() that isn't
    data:, and no Google Fonts. The clark-data block the builder inserted (without_data_block: by its place before the last
    </body>, not by what it looks like) is left out: it is data, not markup. Style text is read in any letter case."""
    text = without_data_block(text)
    found = []
    if has_other_links(text):
        found.append("a <link> tag")
    for pattern, what in ((r"<script[^>]*\bsrc=", "a script loaded by address"),
                          (r"""(?i)\b(src|srcset|href|action|poster|data|formaction|background|ping)\s*=\s*["']?(https?:)?//""",
                           "an attribute that names an outside address"),
                          (r"""(?i)<meta[^>]*http-equiv=["']?refresh""", "a page refresh")):
        if re.search(pattern, text):
            found.append(what)
    css = "".join(style_texts(text))
    if re.search(r"@import", css, re.I):
        found.append("a stylesheet that imports another")
    if [u for u in re.findall(r"url\(([^)]*)\)", css, re.I) if not u.strip("\"' ").lower().startswith("data:")]:
        found.append("a stylesheet address that isn't embedded data")
    if "fonts.googleapis" in text:
        found.append("a Google Fonts address")
    if [a for a in re.findall(r"""(?i)\b(?:src|href)\s*=\s*["']([^"']+)""", text) if a.startswith(("http:", "https:", "//"))]:
        found.append("a link or source that is an outside address")
    return found


def csp_meta(html):
    """The <meta> policy for the file as it will be sent, with the hash of its script and of each inline style (taken from
    these exact bytes, so call it last and insert it first in <head>). No 'self': a file:// page has an opaque origin."""
    h = csp_hashes(html)
    scripts, styles = " ".join(h["script"]) or "'none'", " ".join(h["style"]) or "'none'"
    policy = "; ".join(["default-src 'none'", f"script-src {scripts}", f"style-src-elem {styles}", "img-src data:",
                        "font-src data:", "connect-src 'none'", "object-src 'none'", "base-uri 'none'", "form-action 'none'"])
    return f'<meta http-equiv="Content-Security-Policy" content="{policy}">'


def add_glance(published, inputs):
    """#45: put the At a glance figures and the use case strip in `published["data"]["glance"]`, worked out here, at publish time,
    as at the publish date (a static file must not move with the day it is opened). They are counted from `select`'s own
    output, the rows it already kept, so a figure cannot include a row select dropped; select itself is not changed.
    Counts and fixed labels only, never a stored text: {"tiles": [{tile, label, value, detail, colour, outline}], "strip":
    {total, words: {status: n}, rows: [{id, open, overdue}]}}. colour and outline are one of G A R N, or '' (automatic outline).
    A hidden tile is absent, so is one whose section is hidden. Project health is carried even when its tile is hidden (it is the
    project's health, which the file carries anyway), but when the At a glance section is hidden the section is not in the file at
    all: Health goes with it (Head's ruling, #89 review). The strip is absent when the
    Use cases section is hidden or no use case is kept. Returns `published`."""
    from clark import glance                  # glance imports this module, so it is imported here, not at the top
    as_at = inputs["as_at"]
    kept = glance.kept_from(published, inputs.get("sections"))
    settings = glance.tile_settings(inputs.get("glance_tiles"))
    project = published["data"]["project"]
    shown = glance.tiles({"project": project}, as_at, tile_order=settings["order"], hidden=settings["hidden"] - {"health"},
                         outlines=settings["outlines"], for_client=True, kept=kept)
    if "glance" in kept["hidden_types"]:      # the At a glance section is left off the page: its figures are not carried either
        shown = []
    tiles = [{"tile": t["tile"], "label": t["title"], "value": t["value"], "detail": t["detail"],
              "colour": t["class"].upper(), "outline": settings["outlines"].get(t["tile"]) or ""} for t in shown]
    out = {"tiles": tiles}
    if kept["use_cases"] and "usecases" not in kept["hidden_types"]:
        strip = glance.use_case_strip(None, None, as_at, for_client=True, kept=kept)
        out["strip"] = {"total": strip["total"], "words": {c["status"]: c["count"] for c in strip["counts"]},
                        "rows": [{"id": r["id"], "open": r["open"], "overdue": r["overdue"]} for r in strip["rows"]]}
    published["data"]["glance"] = out
    return published


def data_block(published, as_at):
    """The <script type="application/json" id="clark-data"> block. < > & are \\u escapes, so the text can neither close the
    block nor be read as markup, and ensure_ascii makes U+2028 and U+2029 escapes too."""
    body = json.dumps({"v": VERSION, "as_at": as_at, "data": published["data"], "sections": published["sections"],
                       "tabs": published["tabs"]}, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    for ch in "<>&":
        body = body.replace(ch, "\\u%04x" % ord(ch))
    return f'<script type="application/json" id="clark-data">{body}</script>'


def render(published, page_text, as_at, title):
    """The whole file as text: `page_text` (clark.page.page_html()) with the title, view mode, the data block and, last, the
    policy that covers the finished bytes. Raises PublishError if the page has a token block or the brand reaches outside."""
    if 'id="clark-boot"' in page_text:
        raise PublishError("The page has a server token in it. A published file never has one.")
    check_brand(page_text)
    h = _once(page_text, '<html lang="en-GB">', '<html lang="en-GB" data-mode="view">')
    h = re.sub(r"<title>.*?</title>", lambda m: f"<title>{htmllib.escape(title or 'clark', quote=True)}</title>", h, count=1,
               flags=re.S)
    i = h.rfind("</body>")
    if i < 0:
        raise PublishError("The page clark builds has no end of body, so no report could be made from it.")
    h = h[:i] + data_block(published, as_at) + "\n" + h[i:]
    charset = '<meta charset="utf-8">'
    return _once(h, charset, charset + csp_meta(h))


def file_name(code, week_ending, as_at, folder=None):
    """{CODE}-report-{week_ending or as_at}.html, made safe for Windows, OneDrive and SharePoint (platform.safe_name)."""
    return platform.safe_name(f"{code}-report-{week_ending or as_at}.html", folder)


# ===== Reading (Store.publish_inputs: one read-only connection, one read transaction) =====
def read_inputs(store, code, as_at=None):
    """Everything select() needs, read from the store in ONE read-only transaction (so a write can't come between two reads).
    Only the columns in PUBLISH_FIELDS (and GATES, to decide) are asked for: internal_note, movement and source never leave the
    database. The SQL itself lives in store.py, the only module that touches the database."""
    if not CODE.fullmatch(code or ""):
        raise PublishError("Give the project's code (3 to 7 capital letters or digits).")
    fields = {t: tuple(dict.fromkeys(PUBLISH_FIELDS.get(t, ()) + GATES.get(t, ()) + (("project",) if t in KINDS + ("workstreams",) else ())))
              for t in ("projects",) + KINDS + ("workstreams",)}
    fields["projects"] += tuple(c for c in ("archived",) if c not in fields["projects"])      # #126: publish() refuses an archived project
    try:
        got = store.publish_inputs(code, fields)
    except Exception as e:             # a database that can't be read: said in words, whatever sqlite called it
        raise PublishError(f"The database could not be read ({e}).") from e
    if got is None:
        raise PublishError(f"There is no project with the code {code}.")
    got["as_at"] = as_at or milestones.today()
    return got


# ===== Making the file =====
def publish(store, code, folder, *, by_user, overwrite=False, now=None, branding=None):
    """Write {folder}/{CODE}-report-{date}.html and return {"path", "sha256", "bytes", "seq"}. The file is encoded once,
    hashed once, written with platform.write_file (a temporary file, then replaced: never half a file), read back and
    compared; only then is it recorded with Store.log_publication (once). An existing file of that name is refused unless
    overwrite=True, and the name is reserved with an exclusive create first, so two publishes at once can't both take it.
    `now` is the publish date (YYYY-MM-DD); due dates and Overdue read as at that date."""
    as_at = str(now or milestones.today())
    try:
        if not re.fullmatch(r"\d{4}-\d\d-\d\d", as_at):          # Python 3.11 and later also read 20261028
            raise ValueError
        date.fromisoformat(as_at)
    except ValueError:
        raise PublishError(f"{as_at!r} is not a date. Give the publish date as YYYY-MM-DD.") from None
    folder = Path(folder)
    if not folder.is_dir():
        raise PublishError(f"{platform.folder_phrase(folder, True)} isn't there. Choose a folder that exists.")
    inputs = read_inputs(store, code, as_at)
    if inputs["data"]["project"].get("archived"):           # #126: checked here, not in select (glance.kept_rows calls select and must still work)
        raise PublishError("An archived project can't be published. Restore it first.")
    published = add_glance(select(inputs), inputs)
    project = published["data"]["project"]
    text = render(published, page.page_html(branding, view=True), as_at, project["name"])      # #65: the view-only page
    body = text.encode("utf-8")
    if len(body) > MAX_BYTES:
        raise PublishError(f"The report is {len(body) / 1048576:.1f} MB, which is over the {MAX_BYTES // 1048576} MB limit.")
    dest = folder / file_name(code, project["week_ending"], as_at, folder)
    reserved = False
    if not overwrite:
        try:
            os.close(os.open(dest, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))      # exclusive: the name is ours or refused
            reserved = True
        except FileExistsError:
            raise PublishError(f"{dest.name} is already in that folder. Choose another name, or replace it.") from None
        except OSError as e:
            raise PublishError(f"{dest.name} could not be saved ({e.strerror or e}). Nothing was written.") from e
    digest = hashlib.sha256(body).hexdigest()
    try:
        try:
            platform.write_file(dest, body)
        except OSError as e:
            raise PublishError(f"{dest.name} could not be saved ({e.strerror or e}). Nothing was written.") from e
        if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
            raise PublishError(f"{dest.name} was not saved as it was made (the folder may be syncing). Try again.")
    except BaseException:
        if reserved:                       # take the empty name back if nothing real was put there
            try:
                if dest.stat().st_size == 0:
                    dest.unlink()
            except OSError:
                pass
        raise
    try:
        seq = store.log_publication(code, dest, project["week_ending"], digest, by_user)
    except Exception as e:             # the file is good; only the record failed: say so, so nobody publishes it twice
        raise PublishError(f"{dest.name} was saved in {platform.folder_phrase(folder)}, but clark could not record it. The file is fine. "
                           "Publish again to record it, or ask for help if it happens again.") from e
    return {"path": str(dest), "sha256": digest, "bytes": len(body), "seq": seq}


def main(argv):
    """python3 -m clark.publish CODE FOLDER [--db clark.db] [--overwrite]: one report, for manual runs and CI."""
    ap = argparse.ArgumentParser(prog="python3 -m clark.publish", description=main.__doc__.split(": ", 1)[1])
    ap.add_argument("code")
    ap.add_argument("folder")
    ap.add_argument("--db", help="the database (default: clark.db in clark's data folder)")
    ap.add_argument("--by", dest="by_user", default=getpass.getuser(), help="who is publishing (default: this login)")
    ap.add_argument("--overwrite", action="store_true", help="replace a file of the same name")
    args = ap.parse_args(argv)
    try:
        store = open_store(args.db or platform.data_dir() / "clark.db")
        try:
            done = publish(store, args.code, args.folder, by_user=args.by_user, overwrite=args.overwrite)
        finally:
            store.close()
    except (PublishError, platform.PlatformError, StoreInvalid) as e:
        print(e)
        return 1
    print(f"wrote {done['path']} ({done['bytes']:,} bytes, sha256 {done['sha256']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
