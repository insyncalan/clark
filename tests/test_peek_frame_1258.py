"""Row 1258 (v1.1.1), the peek's frame, toolbar and ID tag as the approved mockup (comms/mockups/peek-redesign/peek-mockup.html, layout A) draws them.
Run: python3 dev/run_tests.py test_peek_frame_1258

Measured on the mockup at 1400 and 900 px: the panel was a card 16 px in from the right and the bottom, radius 16 (row 1289 reverses that: flush right, banner to window bottom, square), with a 1 px border;
the toolbar is 59 px high (12 + 34 + 12 + a 1 px rule) with 34 px buttons of radius 8; the ID tag is mono 12 px / 600
on #F6F8FC, radius 6, 20 px high (81 px wide for a nine-character ID); the project line is 13 px. The live page keeps its banner; the peek starts on its bottom edge.

Part 1 reads the stylesheets; part 2 measures a real browser at 1400 and 900 px, every kind of work item on the demo page, and a milestone.
"""
import json
import re
import unittest

from _paths import ROOT

import test_peek as tp  # noqa: E402
from test_server import chrome, wait  # noqa: E402

PAGE = ROOT / "src" / "clark" / "page"
CSS = (PAGE / "shell.css").read_text(encoding="utf-8")
EDIT_CSS = (PAGE / "src" / "edit" / "edit.css").read_text(encoding="utf-8")
PEEK_JSX = (PAGE / "src" / "components" / "Peek.jsx").read_text(encoding="utf-8")


def rule(text, selector):
    m = re.search(r"^" + re.escape(selector) + r" \{([^}]*)\}", text, re.M)
    assert m, selector
    return m.group(1)


class FrameCss(unittest.TestCase):
    def test_the_card_frame(self):
        self.assertNotRegex(CSS, r"(?m)^\.peek:not\(\.hpk\) \{")      # row 1289: the card is gone, see test_peek_anchor_1289

    def test_the_narrow_window_keeps_the_16_px_on_both_sides(self):
        self.assertRegex(CSS, r"@media \(max-width: 999px\) \{ \.peek:not\(\.hpk\) \{ width: 100% !important; \}")

    def test_the_toolbar_is_59_high_with_34_buttons(self):
        self.assertRegex(rule(CSS, ".pk-tb"), r"min-height:\s*59px")
        self.assertRegex(rule(CSS, ".pk-tb .pkp-btn"), r"width:\s*34px;\s*height:\s*34px")

    def test_the_id_tag_and_the_project_line(self):
        tag = rule(EDIT_CSS, ".peek .pkh-id")
        for want in (r"height:\s*20px", r"border-radius:\s*6px", r"background:\s*#F6F8FC", r"font-size:\s*12px", r"font-weight:\s*600", r"ui-monospace"):
            self.assertRegex(tag, want)
        self.assertRegex(rule(EDIT_CSS, ".peek .pkh-line"), r"font-size:\s*var\(--size-caption\)")      # 13 px on the scale (the browser test measures 13px)

    def test_the_dark_tag_takes_the_grey_50_token_in_both_dark_rules(self):
        self.assertRegex(EDIT_CSS, r':root\[data-theme="dark"\] \.peek \.pkh-id \{ background: var\(--grey-50\); \}')
        self.assertRegex(EDIT_CSS, r'prefers-color-scheme: dark\) \{ :root:not\(\[data-theme="light"\]\) \.peek \.pkh-id \{ background: var\(--grey-50\); \}')

    def test_dragging_the_edge_allows_for_the_16_px(self):
        self.assertIn("clientWidth - e.clientX", PEEK_JSX)


GEOM = """(() => {
  const q = s => document.querySelector(s), box = e => { const b = e.getBoundingClientRect(), c = getComputedStyle(e);
    return {top: b.top, bottom: b.bottom, right: b.right, w: b.width, h: b.height, radius: c.borderTopLeftRadius, border: c.borderTopWidth + ' ' + c.borderTopColor,
            shadow: c.boxShadow, bg: c.backgroundColor, fs: c.fontSize, fw: c.fontWeight, ff: c.fontFamily}; };
  const btns = [...document.querySelectorAll('#peek .pk-tb .pkp-btn')].map(box);
  return {peek: box(q('#peek')), tb: box(q('#peek .pk-tb')), btns, id: box(q('#peek [data-pk-id]')), proj: q('#peek [data-pk-project]') && box(q('#peek [data-pk-project]')),
          banner: q('header.top').getBoundingClientRect().bottom, win: document.documentElement.clientWidth, height: innerHeight};
})()"""


class FrameBrowser(unittest.TestCase):
    setUpClass = tp.Browser.__dict__["setUpClass"]
    tearDownClass = tp.Browser.__dict__["tearDownClass"]
    load_page = tp.Browser.load_page
    ids_on_page = tp.Browser.ids_on_page

    def test_every_kind_of_peek_is_the_mockups_card_with_its_toolbar_and_id_tag(self):
        for width in (1400, 900):
            with chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                ids = self.ids_on_page(cdp, sid)
                kinds = {}
                for i in ids:
                    kinds.setdefault(i.split("-")[1], i)
                self.assertGreaterEqual(len(kinds), 2)
                for kind, item in kinds.items():
                    where = f"{width} {kind}"
                    with self.subTest(where):
                        cdp.js(f"location.hash = '#work&p={self.code}&item={item}'", sid)
                        self.assertTrue(wait(lambda: cdp.js("(() => { const p = document.querySelector('#peek'); return !!p && p.dataset.peek === " + json.dumps(item) + " && !!p.querySelector('[data-pk-id]'); })()", sid)), where)
                        self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek').getAnimations().length === 0", sid)), where)
                        g = cdp.js(GEOM, sid)
                        pk = g["peek"]
                        self.assertEqual(round(pk["top"]), round(g["banner"]), f"{where}: top on the banner's bottom edge (row 1289)")
                        self.assertEqual(round(pk["bottom"]), g["height"], f"{where}: bottom on the window's bottom")
                        self.assertEqual(round(pk["right"]), g["win"], f"{where}: flush to the right edge")
                        self.assertEqual(pk["radius"], "0px", where)
                        if width == 1400:
                            self.assertEqual(round(pk["w"]), 640, where)
                        else:
                            self.assertEqual(round(pk["w"]), g["win"], f"{where}: the narrow peek fills the window")
                        self.assertEqual(round(g["tb"]["h"]), 59, f"{where}: toolbar 59 px")
                        self.assertGreaterEqual(len(g["btns"]), 5, where)
                        for b in g["btns"]:
                            self.assertEqual((round(b["w"]), round(b["h"]), b["radius"]), (34, 34, "8px"), f"{where}: toolbar button")
                        tag = g["id"]
                        self.assertEqual((round(tag["h"]), tag["radius"], tag["bg"], tag["fs"], tag["fw"]), (20, "6px", "rgb(246, 248, 252)", "12px", "600"), where)
                        self.assertIn("monospace", tag["ff"], where)
                        if item == "HRB-A-018" or len(item) == 9:
                            self.assertEqual(round(tag["w"]), 81, f"{where}: 81 px for a nine-character ID")
                        self.assertEqual(g["proj"]["fs"], "13px", f"{where}: project line")

    def test_the_milestone_peek_is_the_same_card_with_the_same_toolbar_and_tag(self):
        ms = next(m["id"] for m in self.data["milestones"] if m["id"] not in self.data.get("report_hidden", []))
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                cdp.js(f"clarkPage.openPeek({json.dumps(ms)}, 'milestone')", sid)
                self.assertTrue(wait(lambda: cdp.js("(document.querySelector('#peek') || {dataset: {}}).dataset.peek", sid) == ms))
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek').getAnimations().length === 0", sid)))
                g = cdp.js(GEOM, sid)
                pk = g["peek"]
                self.assertEqual((round(pk["top"]), round(pk["bottom"]), round(pk["right"])), (round(g["banner"]), g["height"], g["win"]), width)
                self.assertEqual(pk["radius"], "0px", width)
                self.assertEqual(round(g["tb"]["h"]), 59, width)
                for b in g["btns"]:
                    self.assertEqual((round(b["w"]), round(b["h"]), b["radius"]), (34, 34, "8px"), width)
                self.assertEqual((round(g["id"]["h"]), g["id"]["radius"], g["id"]["bg"], g["id"]["fs"], g["id"]["fw"]), (20, "6px", "rgb(246, 248, 252)", "12px", "600"), width)
                self.assertEqual(g["proj"]["fs"], "13px", width)

    def test_dark_keeps_the_card_and_the_tag_reads_in_the_dark_tone(self):
        for width in (1400, 900):
            with chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                cdp.js("document.documentElement.dataset.theme = 'dark'", sid)
                cdp.js(f"location.hash = '#work&p={self.code}&item={self.ids_on_page(cdp, sid)[0]}'", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-pk-id]')", sid)))
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek').getAnimations().length === 0", sid)))
                g = cdp.js(GEOM, sid)
                self.assertEqual(g["peek"]["radius"], "0px", width)
                self.assertNotEqual(g["id"]["bg"], "rgb(246, 248, 252)", f"{width}: the tag is not the light tone in dark")
                grey50 = cdp.js("(() => { const d = document.createElement('i'); d.style.background = 'var(--grey-50)'; document.body.append(d); const c = getComputedStyle(d).backgroundColor; d.remove(); return c; })()", sid)
                self.assertEqual(g["id"]["bg"], grey50, f"{width}: the dark tag is exactly the --grey-50 tone")

    def test_dragging_the_edge_sets_the_width_to_the_gap_between_the_pointer_and_the_16_px_margin(self):
        with chrome() as cdp:
            s, sid = self.load_page(cdp, 1400)
            cdp.js(f"location.hash = '#work&p={self.code}&item={self.ids_on_page(cdp, sid)[0]}'", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek .pk-edge')", sid)))
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek').getAnimations().length === 0", sid)))
            win = cdp.js("document.documentElement.clientWidth", sid)
            cdp.js("""(() => { const e = document.querySelector('#peek .pk-edge'), o = {bubbles: true, pointerId: 1};
              e.dispatchEvent(new PointerEvent('pointerdown', {...o, clientX: 760}));
              e.dispatchEvent(new PointerEvent('pointermove', {...o, clientX: 700}));
              e.dispatchEvent(new PointerEvent('pointerup', {...o, clientX: 700})); })()""", sid)
            self.assertTrue(wait(lambda: round(cdp.js("document.querySelector('#peek').getBoundingClientRect().width", sid)) == win - 700))
            self.assertEqual(round(cdp.js("document.querySelector('#peek').getBoundingClientRect().right", sid)), win)


if __name__ == "__main__":
    unittest.main()
