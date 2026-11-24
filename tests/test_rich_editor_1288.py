"""Row 1288: the Classic rich editor's measured values and places, by the names the ticket's Definition of done uses (computed style, 1400 and 900).

Run: python3 dev/run_tests.py test_rich_editor_1288
Covers AP1 to AP4, AP7, AP8, AP10 to AP14 (AP6, the AI menu's colours, is not here: the product has no 5B colours yet).
AP10 to AP14 also lean on test_tpl_rich_words, test_milestone_peek_828, test_rich_storage_1288c and test_ai_places. Chrome is required: the test fails, never skips, without it.
"""
import json
import re
import unittest
from unittest import mock

from _paths import ROOT

import _rich_page as rp  # noqa: E402
import build_page  # noqa: E402
from clark import page, theme  # noqa: E402,F401
from test_server import chrome  # noqa: E402
import test_ai_places as tap  # noqa: E402  (the module, not its test classes)
import test_rich_storage_1288c as rs  # noqa: E402
from clark import excel_client, publish, sanitise, section_bodies  # noqa: E402

WIDTHS = (1400, 900)
JS = ROOT / "src" / "clark" / "page" / "src"
BOX = ("(b => { const c = getComputedStyle(b), r = b.getBoundingClientRect(); return {w: r.width, h: r.height, mw: c.minWidth, r: c.borderTopLeftRadius,"
       " p: c.paddingTop + ' ' + c.paddingRight + ' ' + c.paddingBottom + ' ' + c.paddingLeft, g: c.columnGap, f: c.fontSize, col: c.color, bg: c.backgroundColor,"
       " bc: c.borderTopColor, m: c.marginTop + ' ' + c.marginRight + ' ' + c.marginBottom + ' ' + c.marginLeft}; })(%s)")
Q = "document.querySelector(%s)"


def setUpModule():       # the Classic theme's rules are appended to the page's own CSS (as test_rich_menus_tight_1288 does), and the theme layer marks the page Classic
    orig, css = build_page.page_css, theme.css("prototype-2.0")
    p = mock.patch.object(build_page, "page_css", lambda *a, **k: orig(build_page.ENTRY) + "\n" + css)      # the served page's CSS: it holds edit.css, where the AI menu's rules are
    p.start()
    unittest.addModuleCleanup(p.stop)


def layer(h):
    h.ev("var o = document.getElementById('theme'); if (o) o.remove(); var s = document.createElement('style'); s.id = 'theme'; s.textContent = '/* classic */'; document.head.appendChild(s); true")


def box(h, sel):
    assert h.until(f"!!document.querySelector({json.dumps(sel)})"), f"{sel} is not drawn"
    return h.ev(BOX % (Q % json.dumps(sel)))


def rgb(s):
    if s.startswith("color("):          # color(srgb 0.48 0.53 0.65): channels 0 to 1
        return [round(float(x) * 255) for x in re.findall(r"[\d.]+", s)[:3]]
    return [int(x) for x in re.findall(r"\d+", s)[:3]]


class Editor(unittest.TestCase):
    def show_editor(self, h, w, value="<p>Some words here</p>", ai="current"):
        layer(h)
        h.resize(w)
        h.mount(value, ai=ai)

    def test_toolbar_has_one_quote_divider_dropdown_1288(self):
        with rp.Harness(chrome) as h:
            for w in WIDTHS:
                self.show_editor(h, w)
                names = h.ev("[...document.querySelectorAll('.rt-bar .rt-btn')].map(b => b.getAttribute('aria-label') || b.textContent)")
                self.assertEqual([n for n in names if "Quote" in n or "Divider" in n], ["More blocks: Quote, Divider"], f"{w}: {names}")
                more = box(h, ".rt-bar .rt-more")
                self.assertEqual((more["h"], more["r"]), (34, "8px"), f"{w}: {more}")
                self.assertGreaterEqual(more["w"], 34, w)
                self.assertEqual(h.ev("document.querySelector('.rt-bar .rt-more').title"), "More blocks: Quote, Divider", w)
                self.assertEqual(h.ev("document.querySelector('.rt-bar .rt-more').getAttribute('aria-label')"), "More blocks: Quote, Divider", w)
                bold = box(h, ".rt-bar .rt-btn[aria-label='Bold']")
                self.assertEqual((bold["w"], bold["h"], bold["r"]), (34, 34, "8px"), f"{w}: {bold}")

    def test_style_button_box_1288(self):
        with rp.Harness(chrome) as h:
            for w in WIDTHS:
                self.show_editor(h, w)
                s = box(h, ".rt-bar .rt-style")
                self.assertEqual((s["p"], s["g"], s["f"]), ("0px 8px 0px 10px", "10px", "15px"), f"{w}: {s}")
                self.assertGreaterEqual(s["w"], 150, f"{w}: {s}")
                self.assertEqual(s["mw"], "150px", w)

    def test_style_menu_own_size_1288(self):
        with rp.Harness(chrome) as h:
            for w in WIDTHS:
                self.show_editor(h, w)
                h.ev("document.querySelector('.rt-bar .rt-style').click(); true")
                menu = box(h, ".rt-bar [role=menu]")
                self.assertEqual(menu["mw"], "224px", f"{w}: {menu}")
                self.assertGreaterEqual(menu["w"], 224, w)
                sizes = h.ev("Object.fromEntries([...document.querySelectorAll('.rt-bar [role=menu] [role=menuitemradio]')].map(b => [b.dataset.kind, getComputedStyle(b).fontSize]))")
                self.assertEqual(sizes, {"paragraph": "15px", "h1": "20px", "h2": "18px", "h3": "16px"}, f"{w}: each line at its own size")
                row = box(h, ".rt-bar [role=menu] [data-kind=paragraph]")
                self.assertEqual(row["p"], "7px 10px 7px 10px", f"{w}: {row}")
                self.assertEqual(h.ev("document.querySelector('.rt-bar [role=menu] [aria-checked=true]').dataset.kind"), "paragraph", f"{w}: the tick is on the current style")
                h.key("Escape", 0, "Escape", 27)

    def test_bubble_style_menu_1288(self):
        with rp.Harness(chrome) as h:
            for w in WIDTHS:
                self.show_editor(h, w)
                h.select_all()
                self.assertTrue(h.until("!!document.querySelector('.rt-bubble [data-rt-bubble-ai]')"), w)
                names = h.ev("[...document.querySelectorAll('.rt-bubble > *')].map(b => b.querySelector('.rt-style') ? 'STYLE' : (b.getAttribute('aria-label') || b.textContent))")
                self.assertEqual(names, ["STYLE", "Bold", "Italic", "Strikethrough", "A", "Link", "Ask AI…"], f"{w}: {names}")
                ask = box(h, ".rt-bubble [data-rt-bubble-ai]")
                self.assertEqual((ask["col"], ask["p"], ask["f"], ask["h"]), ("rgb(70, 53, 184)", "0px 10px 0px 10px", "13px", 34), f"{w}: {ask}")
                self.assertEqual(box(h, ".rt-bubble .rt-btn[aria-label='Bold']")["w"], 34, w)
                self.assertEqual(h.ev("getComputedStyle(document.querySelector('.rt-bubble')).columnGap"), "6px", w)
                h.ev("document.querySelector('.rt-bubble .rt-style').click(); true")
                self.assertTrue(h.until("document.querySelectorAll('.rt-bubble [role=menu] [role=menuitemradio]').length === 4"), w)
                h.ev("document.querySelector('.rt-bubble [data-kind=h2]').click(); true")
                self.assertTrue(h.until("!!document.querySelector('.rt-host h2')"), f"{w}: the bubble's style menu sets the style")

    def test_menus_tight_computed_values_1288(self):
        with rp.Harness(chrome) as h:
            for w in WIDTHS:
                self.show_editor(h, w)
                h.ev("document.querySelector('.rt-bar .rt-more').click(); true")
                p = box(h, ".rt-bar [role=menu]")
                self.assertEqual((p["r"], p["p"]), ("12px", "4px 4px 4px 4px"), f"{w}: {p}")
                r = box(h, ".rt-bar [role=menu] [role=menuitem]")
                self.assertEqual((r["p"], r["f"], r["r"]), ("4px 10px 4px 10px", "13.5px", "6px"), f"{w}: {r}")

    def test_no_colour_in_toolbar_style_bubble_slash_1288(self):
        with rp.Harness(chrome) as h:
            palette = {(0x46, 0x35, 0xB8), (0x7C, 0x4D, 0xFF), (0x2F, 0x7D, 0x4A), (0x3B, 0x6F, 0xD4), (0xB7, 0x79, 0x1F), (0x9E, 0x7B, 0xFF)}
            for w in WIDTHS:
                self.show_editor(h, w)
                # Exempt, by name: the Ask AI button (its own brand colour) and the Font colour control (row 1364; ruling 24-11 05:0x). Nothing else may carry a colour.
                grab = ("[...document.querySelectorAll(%s)].filter(e => !e.hasAttribute('data-rt-bubble-ai') && e.getAttribute('aria-label') !== 'Font colour').flatMap(e => { const c = getComputedStyle(e); return [c.color, c.backgroundColor, c.borderTopColor]; })")
                seen = {}
                seen["toolbar"] = h.ev(grab % json.dumps(".rt-bar .rt-btn, .rt-bar .rt-sep"))
                # The Font colour control is the ONLY coloured control: it is named once in the bar, and with a colour chosen its underline is the only coloured edge there.
                self.assertEqual(h.ev("document.querySelectorAll(\".rt-bar [aria-label='Font colour']\").length"), 1, f"{w}: one Font colour button")
                h.ev("document.querySelector('.rt-bar .rt-A').setAttribute('data-colour', 'red'); true")
                coloured = h.ev("[...document.querySelectorAll('.rt-bar .rt-btn, .rt-bar .rt-A')].filter(e => { const c = getComputedStyle(e).borderBottomColor.match(/\\d+/g).map(Number); return Math.max(...c.slice(0, 3)) - Math.min(...c.slice(0, 3)) > 60; }).map(e => e.className.split(' ')[0] + ':' + (e.getAttribute('aria-label') || e.textContent))")
                self.assertEqual(coloured, ["rt-A:A"], f"{w}: the Font colour underline is the only coloured control: {coloured}")
                h.ev("document.querySelector('.rt-bar .rt-A').removeAttribute('data-colour'); true")
                h.ev("document.querySelector('.rt-bar .rt-style').click(); true")
                self.assertTrue(h.until("!!document.querySelector('.rt-bar [role=menu]')"), f"{w}: style menu")
                seen["style menu"] = h.ev(grab % json.dumps(".rt-bar [role=menu], .rt-bar [role=menu] [role=menuitemradio], .rt-bar [role=menu] .mi, .rt-bar [role=menu] .ck"))
                h.ev("window.unmount(); true")
                self.show_editor(h, w)
                h.select_all()
                self.assertTrue(h.until("!!document.querySelector('.rt-bubble')"), f"{w}: bubble")
                seen["bubble"] = h.ev(grab % json.dumps(".rt-bubble, .rt-bubble .rt-btn"))
                h.ev("window.unmount(); true")
                h.mount("", ai="current")
                h.type("/")
                self.assertTrue(h.until("!!document.querySelector('.rt-slash')"), f"{w}: slash")
                seen["slash"] = h.ev(grab % json.dumps(".rt-slash, .rt-slash .rt-opt:not(.rt-ask), .rt-slash .rt-slash-filter"))
                for where, cols in seen.items():
                    self.assertTrue(cols, f"{w} {where}: nothing read")
                    for c in cols:
                        t = tuple(rgb(c))
                        self.assertNotIn(t, palette, f"{w} {where}: {c} is a palette colour")
                        if len(re.findall(r"\d+", c)) >= 3 and "rgba" in c and c.endswith(", 0)"):
                            continue
                        self.assertLessEqual(max(t) - min(t), 60, f"{w} {where}: {c} is a colour, not a grey")


SRC_EDIT = JS / "edit"
OLD_TEXT = 'Line one: a < b & "c" it\'s <b>not bold</b>\nLine two\n\nLine four'     # fictional old plain text, with markup characters in it


def source(rel):
    return (JS / rel).read_text(encoding="utf-8")


def rich_mounts():
    """Every <RichField ... /> in the page source: [(file, field, has oneLine)]."""
    out = []
    for f in sorted(JS.rglob("*.jsx")):
        for m in re.finditer(r"<RichField\b(.*?)/>", f.read_text(encoding="utf-8"), re.S):
            field = re.search(r'\bfield="([^"]+)"', m.group(1))
            out.append((f.relative_to(JS).as_posix(), field.group(1) if field else None, bool(re.search(r"\boneLine\b", m.group(1)))))
    return out


def labels(name, third=True):
    """The words of a list constant in RichText.jsx (BAR, BUBBLE_ALL: the third item of each entry; STYLES, SLASH: the second)."""
    body = re.search(r"const " + name + r" = \[(.*?)\n?\];", source("edit/RichText.jsx"), re.S).group(1)
    return re.findall(r'\["\w+", "[^"]*", "([^"]+)"\]' if third else r'\["\w+", "([^"]+)"\]', body)


class Ap10Places(unittest.TestCase):
    def test_places_full_oneline_notrich_1288(self):
        """AP10: Milestone Description is One line; Link preview words and One document words are Not rich; the other rich places are Full.
        One case per place, then what One line and Full draw at 1400 and 900."""
        mounts = rich_mounts()
        by_field = {}
        for f, field, one in mounts:
            by_field.setdefault(field, set()).add((f, one))
        self.assertEqual(by_field["description"], {("edit/MilestonePeek.jsx", True)}, "Milestone Description: One line")
        for rel, word in (("edit/templates/LinkCard.jsx", "Link preview words"), ("edit/templates/OneDoc.jsx", "One document words")):
            text = source(rel)
            self.assertNotIn("RichField", text, f"{word}: Not rich")
            self.assertIn("<textarea", text, f"{word}: a plain box")
        full = {"raid_own": "edit/templates/raidEdit.jsx", "caption": "edit/templates/pictureEdit.jsx", "client_message": None, "latest_update": "edit/PeekLatest.jsx",
                "callout": "edit/templates/Callout.jsx", "textimage": None, "standing": None, "internal_note": "edit/Movement.jsx", "health_reason": "edit/GlanceEdit.jsx"}
        for field, rel in full.items():
            self.assertIn(field, by_field, field)
            for f, one in by_field[field]:
                self.assertFalse(one, f"{f} {field}: Full, not One line")
            if rel:
                self.assertIn(rel, {f for f, _ in by_field[field]}, field)
        self.assertIn("edit/ItemRowsEdit.jsx", {f for f, _ in by_field["client_message"]}, "Item row Client wording")
        self.assertEqual({field for _, field, one in mounts if one}, {"description", "mv_who", "mv_reason", "mv_source"}, "the only One line places")
        with rp.Harness(chrome) as h:
            for w in WIDTHS:
                for one_line in (True, False):
                    layer(h)
                    h.resize(w)
                    h.mount("<p>Some words here</p>", ai="current", one_line=one_line)
                    got = h.ev("({style: !!document.querySelector('.rt-bar .rt-style'), more: !!document.querySelector('.rt-bar .rt-more'), "
                               "bullets: !!document.querySelector('.rt-bar [aria-label=\"Bulleted list\"]'), bold: !!document.querySelector('.rt-bar [aria-label=\"Bold\"]')})")
                    self.assertEqual(got, {"style": not one_line, "more": not one_line, "bullets": not one_line, "bold": True} if not one_line else
                                     {"style": False, "more": False, "bullets": False, "bold": False}, f"{w} one_line={one_line}: {got}")
                    h.ev("window.unmount(); true")


class Ap11Ap12Storage(rs.Base):
    def test_html_storage_publish_export_1288(self):
        """AP11: RAID own words, Picture caption and Item row Client wording are Full editors that store the editor's HTML (cleaned), and the file
        and the exports carry it: an item's wording as HTML in the file and as words in Word and the client workbook; a card's own words and a caption as
        the one line of words the file has always held."""
        for rel, field in (("edit/templates/raidEdit.jsx", "raid_own"), ("edit/templates/pictureEdit.jsx", "caption"), ("edit/ItemRowsEdit.jsx", "client_message")):
            self.assertIn((rel, field, False), rich_mounts(), f"{rel}: the Full editor (not oneLine)")
        for kind, make, where, file_of in rs.LINES:
            with self.subTest(kind):
                html = "<p>Fine <strong>words</strong></p><ul><li>two</li></ul>"
                stored = json.loads(section_bodies.check(kind, json.dumps(make(html)), rs.rules()))
                self.assertEqual(where(stored), "<p>Fine <strong>words</strong></p><ul><li>two</li></ul>", "stored as the editor's HTML")
                ctx = section_bodies.Context({"raid": [{"id": "ABC-001", "description": "t", "client_message": ""}]})
                self.assertEqual(file_of(rs.published(kind, stored, ctx)), "Fine words two", "the file carries the words on one line, never markup")
        for table in self.ref:
            with self.subTest(table):
                self.send(table, "<p>Fine <em>words</em></p><ul><li>two</li></ul>")
                self.assertEqual(self.stored(table), "<p>Fine <em>words</em></p><ul><li>two</li></ul>", "stored as HTML")
                self.assertEqual(self.published(table), "<p>Fine <em>words</em></p><ul><li>two</li></ul>", "published as HTML")
                self.assertIn((table, "client_message"), publish.LEGACY_RICH)
                words = excel_client.value_of(table, {rs.TITLE[table]: "t", "client_message": self.stored(table)}, "client_message")
                self.assertIn("Fine words", words.replace("\n", " "), "exported as its words")
                self.assertNotIn("<", words, "exported with no markup")


class Ap12OldText(unittest.TestCase):
    def test_old_plain_text_reads_right_1288(self):
        """AP12: old saved plain text in RAID own words, Picture caption and Item row Client wording opens as paragraphs: no lost line, the < and the
        tags in it are text; at 1400 and 900."""
        for rel in ("edit/templates/raidEdit.jsx", "edit/templates/pictureEdit.jsx", "edit/ItemRowsEdit.jsx"):
            self.assertIn("richOrPlain(", source(rel), f"{rel}: an old plain value goes through richOrPlain")
        with rp.Harness(chrome) as h:
            html = h.ev(f"window.CE.richOrPlain({json.dumps(OLD_TEXT)})")
            for w in WIDTHS:
                h.resize(w)
                h.mount(html)
                self.assertEqual(h.ev("[...document.querySelectorAll('.rt-host p')].map(p => p.textContent)"), OLD_TEXT.split("\n"), f"{w}: no line lost")
                self.assertEqual(h.ev("document.querySelectorAll('.rt-host b, .rt-host script').length"), 0, f"{w}: no markup drawn")
                self.assertIn("<b>not bold</b>", h.ev("document.querySelector('.rt-host').textContent"), f"{w}: the tags in an old line are its words")
                self.assertEqual(h.ev("window.saves.length"), 0, f"{w}: looking saves nothing")
                h.ev("window.unmount(); true")


class Ap13Places(tap.PageCase):
    def test_ai_places_new_places_1288(self):
        """AP13: aiPlaces matches the new places; client_message is listed once in each table. (Pure table: no width.)"""
        for key, place in (("raid.own_words", "current"), ("picture.caption", "current"), ("milestone.description", "plain"), ("milestone.client_wording", "client_message")):
            self.assertEqual(self.page.ev(f"AP.placeFor({json.dumps(key)})"), place, key)
        for field, key in (("raid_own", "raid.own_words"), ("caption", "picture.caption"), ("description", "milestone.description"), ("client_message", "milestone.client_wording")):
            self.assertEqual(self.page.ev(f"AP.keyForField({json.dumps(field)})"), key, field)
        for key in ("linkcard.text", "onedoc.text"):
            self.assertNotIn(key, self.place_of, key)
        text = source("logic/aiPlaces.js")
        self.assertEqual(len(re.findall(r'^\s*"milestone\.client_wording"\s*:', text, re.M)), 1)
        self.assertEqual(len(re.findall(r"^\s*client_message\s*:", text, re.M)), 1)


def show(h, w, value="<p>Some words here</p>", ai="current"):
    layer(h)
    h.resize(w)
    h.mount(value, ai=ai)


class Ap14Kept(unittest.TestCase):
    TOOLBAR = ["Bold", "Italic", "Strikethrough", "Font colour", "Bulleted list", "Numbered list", "Checklist", "More blocks: Quote, Divider", "Link", "Undo", "Redo"]
    STYLES = ["Text", "Heading 1", "Heading 2", "Heading 3"]
    BUBBLE = ["Bold", "Italic", "Strikethrough", "Font colour", "Link"]
    SLASH = ["Heading 1", "Heading 2", "Heading 3", "Bulleted list", "Numbered list", "Checklist", "Quote", "Divider"]

    def test_every_editor_item_kept_1288(self):
        """AP14: every item of today's RichText.jsx lists is still drawn, by its label, at 1400 and 900: toolbar BAR, Text style menu STYLES, BUBBLE, "/" menu SLASH,
        the link box and the hint."""
        bar = labels("BAR")
        self.assertEqual([b for b in bar if b not in ("Quote", "Divider")], [b for b in self.TOOLBAR if b != "More blocks: Quote, Divider"] , "BAR in RichText.jsx has an item the test does not know")
        self.assertEqual({"Quote", "Divider"} - set(bar), set(), "Quote and Divider are still in BAR")
        self.assertEqual(labels("STYLES", False), self.STYLES)
        self.assertEqual(labels("BUBBLE_ALL"), self.BUBBLE)
        self.assertEqual(labels("SLASH", False), self.SLASH)
        self.assertIn("Cmd+Enter saves. Esc cancels.", source("edit/RichText.jsx"))
        with rp.Harness(chrome) as h:
            for w in WIDTHS:
                show(h, w)
                names = h.ev("[...document.querySelectorAll('.rt-bar .rt-btn')].filter(b => !b.classList.contains('rt-style')).map(b => b.getAttribute('aria-label'))")
                self.assertEqual(names, self.TOOLBAR, f"{w}: toolbar")
                self.assertTrue(h.ev("!!document.querySelector('.rt-bar .rt-style')"), f"{w}: the Text style button")
                self.assertEqual(h.ev("document.querySelector('.rt-bar .rt-keys').textContent"), "Cmd+Enter saves. Esc cancels.", f"{w}: hint")
                h.ev("document.querySelector('.rt-bar .rt-more').click(); true")
                self.assertTrue(h.until("document.querySelectorAll('.rt-bar [role=menu] [role=menuitem]').length === 2"), w)
                self.assertEqual(h.ev("[...document.querySelectorAll('.rt-bar [role=menu] [role=menuitem]')].map(b => b.textContent.trim())"), ["Quote", "Divider"], f"{w}: More blocks")
                h.key("Escape", 0, "Escape", 27)
                h.ev("document.querySelector('.rt-bar .rt-style').click(); true")
                self.assertTrue(h.until("document.querySelectorAll('.rt-bar [role=menu] [role=menuitemradio]').length === 4"), w)
                self.assertEqual(h.ev("[...document.querySelectorAll('.rt-bar [role=menu] [role=menuitemradio]')].map(b => b.textContent.replace('\u2713', '').trim())"), self.STYLES, f"{w}: Text style menu")
                h.key("Escape", 0, "Escape", 27)
                h.ev("document.querySelector('.rt-bar [aria-label=Link]').click(); true")
                self.assertTrue(h.until("!!document.querySelector('.rt-link input[aria-label=\"Link address\"]')"), f"{w}: link box")
                self.assertEqual(h.ev("[...document.querySelectorAll('.rt-link button')].map(b => b.textContent)"), ["Apply", "Cancel"], w)
                h.ev("window.unmount(); true")
                show(h, w)
                h.select_all()
                self.assertTrue(h.until("!!document.querySelector('.rt-bubble')"), w)
                got = h.ev("[...document.querySelectorAll('.rt-bubble .rt-btn:not(.rt-style):not([data-rt-bubble-ai])')].map(b => b.getAttribute('aria-label'))")
                self.assertEqual(got, self.BUBBLE, f"{w}: bubble")
                h.ev("window.unmount(); true")
                layer(h)
                h.mount("", ai="current")
                h.type("/")
                self.assertTrue(h.until("!!document.querySelector('.rt-slash')"), w)
                self.assertEqual(h.ev("[...document.querySelectorAll('.rt-slash .rt-opt:not(.rt-ask)')].map(b => b.textContent.trim())"), self.SLASH, f"{w}: / menu")
                h.ev("window.unmount(); true")


if __name__ == "__main__":
    unittest.main()
