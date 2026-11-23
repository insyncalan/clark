"""Row 1288: the Classic rich editor's measured values and places, by the names the ticket's Definition of done uses (computed style, 1400 and 900).

Run: python3 dev/run_tests.py test_rich_editor_1288
Covers AP1, AP2, AP3, AP4, AP6, AP7, AP13 (the AI menu and AI places, AP8, go with the AI menu part).
test_tpl_rich_words and test_milestone_peek_828 (AP10). Chrome is required: the test fails, never skips, without it.
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
                grab = ("[...document.querySelectorAll(%s)].filter(e => !e.hasAttribute('data-rt-bubble-ai')).flatMap(e => { const c = getComputedStyle(e); return [c.color, c.backgroundColor, c.borderTopColor]; })")
                seen = {}
                seen["toolbar"] = h.ev(grab % json.dumps(".rt-bar .rt-btn, .rt-bar .rt-sep"))
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


if __name__ == "__main__":
    unittest.main()
