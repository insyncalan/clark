"""Row 1316 gap: the Classic Use cases search box is 560px wide at 1400 (the view icons stand beside it, not inside the 560).
Run: python3 dev/run_tests.py test_gap_1316   Chrome required."""
import tempfile
import unittest

from _demo import DemoStore
from clark import page
from test_published_work_no_add import open_page
from test_server import Running, chrome, wait
from test_work_filters import need_chrome

JS = """(() => { const b = document.querySelector('#usecases .fline').getBoundingClientRect(), t = document.querySelector('#usecases .fline-tail').getBoundingClientRect();
  return {box: Math.round(b.width), tailOutside: t.left >= b.right - 0.5, scroll: document.documentElement.scrollWidth <= window.innerWidth}; })()"""


class Gap1316(unittest.TestCase):
    def test_box_560_at_1400(self):
        need_chrome()
        demo = DemoStore()
        self.addCleanup(demo.close)
        s = Running(data_for=demo.store.data_for, page_html=lambda: page.page_html(tempfile.mkdtemp(), theme="prototype-2.0"))
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = open_page(cdp, f"http://127.0.0.1:{s.port}/#usecases&p=ABC", 1400, "light")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#usecases .fline-tail')", sid), 45), "the page drew")
            g = cdp.js(JS, sid)
        self.assertEqual(g["box"], 560, "search box 560px at 1400 (was 389)")
        self.assertTrue(g["tailOutside"], "the view icons stand beside the box")
        self.assertTrue(g["scroll"])


if __name__ == "__main__":
    unittest.main()
