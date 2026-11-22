"""Row 1260 gap G11: in Classic the Add tile is the dashed "+" at the far right of the saved-views tabs row on Work items and Use cases,
and Milestones has none there; Cards keeps the tile in the page head on Work items. No new words (the tile keeps its name).

Run: python3 dev/run_tests.py test_add_tile_tabs_row_1260
Headless Chrome (required: fails, never skips, without it), at 1400 and 900 px.
"""
import json
import tempfile
import unittest

from _real_server import real_server
from clark import page
from test_server import chrome
from test_work_board_page import Base, setUpModule, tearDownModule  # noqa: F401

ROW = ".fvrow"
PROBE = """(() => {
  const row = document.querySelector(%s), t = document.getElementById(%s);
  if (!t) return JSON.stringify({tile: false});
  const tr = t.getBoundingClientRect(), r = row ? row.getBoundingClientRect() : null;
  const others = row ? [...row.children].filter(c => c.getBoundingClientRect().width > 0 && !c.contains(t) && !t.contains(c)) : [];
  return JSON.stringify({tile: true, inRow: !!(row && row.contains(t)), dashed: getComputedStyle(t).borderTopStyle,
    right: r ? Math.round(r.right - tr.right) : null, farRight: others.every(c => c.getBoundingClientRect().right <= tr.left + 1),
    inHead: !!t.closest('.head'), label: t.getAttribute('aria-label'), w: Math.round(tr.width)});
})()"""


class AddTile(Base):
    theme = "prototype-2.0"

    def setUp(self):
        super().setUp()
        self.s.close()
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=self.theme))
        self.addCleanup(self.s.close)

    def probe(self, cdp, sid, row, tid):
        return json.loads(cdp.js(PROBE % (json.dumps(row), json.dumps(tid)), sid))

    def test_work_items_tile_is_dashed_at_the_far_right_of_the_tabs_row(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                got = self.probe(cdp, sid, "#work " + ROW, "newBtn")
                self.assertTrue(got["inRow"], got)
                self.assertEqual(got["dashed"], "dashed")
                self.assertTrue(got["farRight"], got)
                self.assertLessEqual(got["right"], 2, got)
                self.assertFalse(got["inHead"], got)
                self.assertTrue(got["label"], got)

    def test_use_cases_tile_is_dashed_at_the_far_right_of_the_tabs_row(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width, hash_="#usecases&p=ABC", wait_for="#usecases")
                got = self.probe(cdp, sid, "#usecases " + ROW, "ucAddPage")
                self.assertTrue(got["inRow"], got)
                self.assertEqual(got["dashed"], "dashed", "Row 1316 ruling 19-11: the Use cases + is dashed in Classic")
                self.assertTrue(got["farRight"], got)
                self.assertLessEqual(got["right"], 2, got)
                self.assertEqual(got["label"], "Add use case")

    def test_milestones_has_no_tile_in_a_tabs_row(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width, hash_="#milestones&p=ABC", wait_for="#milestones")
                n = cdp.js("document.querySelectorAll('#milestones .fvrow .newb').length", sid)
                self.assertEqual(n, 0)


class CardsUnchanged(AddTile):
    theme = None

    def test_work_items_tile_stays_in_the_page_head(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                got = self.probe(cdp, sid, "#work " + ROW, "newBtn")
                self.assertTrue(got["inHead"], got)
                self.assertFalse(got["inRow"], got)

    test_work_items_tile_is_dashed_at_the_far_right_of_the_tabs_row = None
    test_use_cases_tile_is_dashed_at_the_far_right_of_the_tabs_row = None
    test_milestones_has_no_tile_in_a_tabs_row = None


if __name__ == "__main__":
    unittest.main()
