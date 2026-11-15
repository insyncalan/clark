"""Hunt on v1.0.7, published file: at 900 px the top bar's tabs shrink and scroll inside their own bar (the 1000 px rule must come
after the item 681 'flex: none' rule, or it loses and the bar runs past the window). Checked in Chrome on the computed style, 1400 and 900."""
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from _demo import USER
from clark import publish
from test_gantt_table_section import Base
from test_published_work_no_add import EMPTY_BRANDING, TODAY, open_page
from test_server import chrome, wait

PROBE = ("(() => { const t = document.querySelector('.tabs'), cs = getComputedStyle(t); return {shrink: cs.flexShrink, ox: cs.overflowX, "
         "sw: t.scrollWidth, cw: t.clientWidth, doc: document.documentElement.scrollWidth, win: innerWidth}; })()")


class PublishedTabs(Base):
    def setUp(self):
        super().setUp()
        self.ok(kind="gantt_lines", op="new", values={"type": "task", "name": "x", "start": "2026-11-02", "end": "2026-11-13", "health": "Green", "show": 1})
        self.ok(kind="projects", op="update", changes={"show_gantt_client": 1, "gantt_tab_name": "Long Gantt tab name goes on"})
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        self.path = Path(publish.publish(self.s, "ABC", folder, by_user=USER, now=TODAY, branding=EMPTY_BRANDING)["path"])

    def probe(self, width):
        with chrome() as cdp:
            sid = open_page(cdp, self.path.as_uri() + "#dashboard", width, "light")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tabs .tab')", sid)))
            time.sleep(0.4)
            return cdp.js(PROBE, sid)

    def test_at_900_the_tabs_shrink_and_scroll_inside_the_bar(self):
        got = self.probe(900)
        self.assertEqual(got["shrink"], "1", got)
        self.assertEqual(got["ox"], "auto", got)
        self.assertGreaterEqual(got["cw"], 800, f"issue 1146: the tabs are a strip the width of the two-row bar, and scroll inside it when they do not fit: {got}")
        self.assertLessEqual(got["doc"], got["win"], f"the page does not run past the window: {got}")

    def test_at_1400_the_page_is_not_wider_than_the_window(self):
        got = self.probe(1400)
        self.assertLessEqual(got["doc"], got["win"], got)


if __name__ == "__main__":
    unittest.main()
