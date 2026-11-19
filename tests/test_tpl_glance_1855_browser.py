"""Row 1264 slice 9 (PR 1855), the survivors that need a browser: the health wrapper stretches with its tile (computed style and height at 1400
and 900), and the empty Edit text ("No tiles. Use " and the exact label of the Add button) while View keeps its own sentence. Fictional data.

Run: python3 dev/run_tests.py test_tpl_glance_1855_browser
"""
import re
import unittest

from _paths import SRC
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome
import test_tpl_glance_layout_1264 as L

SHELL = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
HIDDEN_ALL = {"v": 1, "builtin": {"overdue": {"hidden": True}, "risks": {"hidden": True}, "decisions": {"hidden": True}}}


class HealthStretch(L.Layout):
    def setUp(self):
        super().setUp()
        self.set_body({"v": 1})

    def probe(self, p):
        return p.js(f"""(function(){{ var s = document.querySelector('{self.sel()}'), g = s.querySelector('.tpl-gt'), w = g.querySelector('.tpl-gt-health'),
          h = w.getBoundingClientRect().height, o = g.querySelector('[data-tile=overdue]').getBoundingClientRect().height, t = w.firstElementChild.getBoundingClientRect().height;
          return {{grid: getComputedStyle(g).alignItems, wrap: getComputedStyle(w).display, wrapH: h, tileH: t, nextH: o}}; }})()""")

    def test_h1_the_grid_stretches_the_wrapper_is_flex_and_its_tile_fills_the_line_at_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                got = self.probe(self.page(cdp, width))
                self.assertEqual((got["grid"], got["wrap"]), ("stretch", "flex"))
                self.assertAlmostEqual(got["wrapH"], got["nextH"], delta=1.0, msg="the wrapper is as tall as its neighbour")
                self.assertAlmostEqual(got["tileH"], got["wrapH"], delta=1.0, msg="the health tile fills its wrapper")


class EmptyWords(L.Layout):
    def empty(self, p, edit):
        return p.js(f"""(function(){{ var s = document.querySelector('{self.sel()}'), e = s.querySelector('{"[data-gt-empty]" if edit else ".tile-empty"}');
          var add = s.querySelector('.tileadd'), m = document.createElement('div'); m.style.cssText = 'padding-left: var(--space-4); color: var(--text-muted); font-size: var(--size-small)'; document.body.appendChild(m);
          var want = getComputedStyle(m), cs = e && getComputedStyle(e), same = !!e && cs.paddingLeft === want.paddingLeft && cs.color === want.color && cs.fontSize === want.fontSize; m.remove();
          return {{text: e ? e.textContent.trim() : null, add: add ? add.textContent.trim() : null, same: same}}; }})()""")

    def page_hidden(self, cdp, edit, width=1400):
        self.set_body(HIDDEN_ALL)
        p = self.visit(cdp)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        if edit:
            p.edit()
        p.until(f"!!document.querySelector('{self.sel()}')", "the section drew")
        p.until(f"!!document.querySelector('{self.sel('[data-tile], .tile-empty')}')", "tiles drew")
        return p

    def test_e1_edit_with_every_tile_hidden_says_no_tiles_use_and_the_exact_label_of_the_add_button(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                got = self.empty(self.page_hidden(cdp, True, width), True)
                self.assertTrue(got["add"], "the Add button is there")
                self.assertEqual(got["text"], f"No tiles. Use {got['add']}.")
                self.assertTrue(got["same"], "the sentence takes the View sentence's padding, colour and size (space and text tokens)")

    def test_e2_view_keeps_its_own_sentence(self):
        with chrome() as cdp:
            got = self.empty(self.page_hidden(cdp, False), False)
        self.assertEqual(got["text"], "No tiles on this section.")

    def test_e4_edit_draws_one_hint_paragraph_with_the_app_words_and_the_two_sentences(self):
        self.set_body({"v": 1})
        with chrome() as cdp:
            got = self.page(cdp, 1400, edit=True).js(f"[...document.querySelectorAll('{self.sel('.glance-hint')}')].map(e => e.textContent)")
        self.assertEqual(len(got), 1, got)
        self.assertTrue(got[0].startswith("Drag a tile to move it"))
        self.assertTrue(got[0].endswith(f"page. {L.HINT_EYE} {L.HINT_ADD}"), "one space between the app words and the two sentences")

    def test_e5_a_shown_own_tile_is_a_list_so_edit_says_no_tiles_does_not(self):
        self.set_body({**HIDDEN_ALL, "bespoke": [{"id": "t1", "label": "Fictional own"}]})
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector('{self.sel('[data-tile]')}')", "tiles drew")
            got = self.empty(p, True)
        self.assertIsNone(got["text"])

    def test_e3_edit_with_a_tile_showing_says_nothing_of_the_kind(self):
        self.set_body({"v": 1})
        with chrome() as cdp:
            got = self.empty(self.page(cdp, 1400, edit=True), True)
        self.assertIsNone(got["text"])


class Breakpoint(unittest.TestCase):
    def test_b1_the_editor_tile_cell_and_the_view_tile_share_the_760_breakpoint(self):
        own = re.search(r"@media \(max-width: (\d+)px\) \{ \.tcell\.own \{ flex-basis: 100%; \} \}", SHELL)
        view = re.search(r"@media \(max-width: (\d+)px\) \{ \.tpl-gt-tile \{ flex-basis: 100%; \} \}", SHELL)
        self.assertTrue(own and view)
        self.assertEqual((own.group(1), view.group(1)), ("760", "760"))


if __name__ == "__main__":
    unittest.main()
