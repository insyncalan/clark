"""Row 832 and row 805 take the white card off the EDITOR pages (Work items, Milestones, Use cases). The published file keeps its card, as the
prototype's published page draws every tab in a white bordered card, and keeps the visible count line of its own filter row.

Run: python3 dev/run_tests.py test_published_frames
Headless Chrome (required: fails, never skips, without it). The published file is opened from disk.
Desktop only: 1400 and 900 px, light and dark.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from test_board import make_data
from clark import publish
from test_published_work_no_add import EMPTY_BRANDING, TODAY, VARIANTS, open_page
from test_server import chrome, wait
from test_work_filters import need_chrome

CARD = ("(sel) => { const e = document.querySelector(sel), c = getComputedStyle(e);"
        " return {bg: c.backgroundColor, border: c.borderTopWidth, shadow: c.boxShadow !== 'none', pad: parseFloat(c.paddingLeft), tall: e.getBoundingClientRect().height > 0}; }")


class PublishedFrames(unittest.TestCase):
    def setUp(self):
        need_chrome()
        demo, data = make_data()
        with demo.store.step("dashboard", USER) as st:               # one card the client sees
            st.update("actions", data["actions"][0]["id"], {"client_visible": 1})
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(demo.close)
        self.addCleanup(shutil.rmtree, folder, True)
        self.path = Path(publish.publish(demo.store, "ABC", folder, by_user=USER, now=TODAY, branding=EMPTY_BRANDING)["path"])

    def tab(self, cdp, sid, word, sel):
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
        cdp.js(f"[...document.querySelectorAll('.tab')].find(t => /{word}/i.test(t.textContent)).click()", sid)
        self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector({sel!r})", sid)), f"the {word} tab drew")

    def card(self, word, sel):
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = open_page(cdp, self.path.as_uri(), width, scheme)
                self.tab(cdp, sid, word, sel)
                got = cdp.js(f"({CARD})({sel!r})", sid)
                self.assertNotEqual(got["bg"], "rgba(0, 0, 0, 0)", "the published page keeps its white card")
                self.assertEqual(got["border"], "1px", "and its border")
                self.assertTrue(got["shadow"], "and its shadow")
                self.assertEqual(got["pad"], 28.0 if width == 1400 else 16.0, "and its padding")

    def test_the_published_work_items_page_keeps_its_card(self):
        self.card("Work items", "#work.frame.work.pub")

    def test_the_published_milestones_page_keeps_its_card(self):
        self.card("Milestones", "#milestones.frame.milestones.pub")
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme, part="viewer"), chrome() as cdp:
                sid = open_page(cdp, self.path.as_uri(), width, scheme)
                self.tab(cdp, sid, "Milestones", "#milestones .msv")
                got = cdp.js("(() => { const c = getComputedStyle(document.querySelector('#milestones .msv')); return [c.borderTopWidth, c.paddingLeft]; })()", sid)
                self.assertEqual(got, ["0px", "0px"], "the viewer inside is not a second card")

    def test_the_published_use_cases_page_keeps_its_card(self):
        self.card("Use cases", "#usecases-file")

    def test_the_published_work_items_count_line_is_still_drawn(self):
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = open_page(cdp, self.path.as_uri(), width, scheme)
                self.tab(cdp, sid, "Work items", "#work-count")
                got = cdp.js("(() => { const r = document.querySelector('#work-count').getBoundingClientRect(); return [r.width > 1, r.height > 1, !!document.querySelector('#work .factive.pub')]; })()", sid)
                self.assertEqual(got, [True, True, True], "the count is a visible line in the published filter row")


if __name__ == "__main__":
    unittest.main()
