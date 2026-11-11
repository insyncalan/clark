"""Plan 1044: the milestone timeline carries no dead CSS, and the left-most label is whole.

Run: python3 dev/run_tests.py test_milestones_dead_css
`.mv-lab.gl` styled a class no label carries any more (the late text is `.slip`); the rule is gone. The left-most milestone label
starts inside the strip (never at x below 0) at 1400 and 900 px. The browser part needs Chrome and fails, never skips, without it.
"""
import re
import shutil
import tempfile
import unittest

from _paths import SRC

from clark import page
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target


class DeadCss(unittest.TestCase):
    def test_no_rule_styles_a_gl_label(self):
        css = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"\.mv-lab\.gl\b", css), "no label carries the class gl, so no rule is kept for it")
        jsx = (SRC / "clark" / "page" / "src" / "components" / "MsTimeline.jsx").read_text(encoding="utf-8")
        self.assertNotRegex(jsx, r"mv-lab[^`]*\bgl\b", "MsTimeline.jsx never adds gl to a label")


class LeftLabel(unittest.TestCase):
    def test_the_left_most_label_starts_inside_the_strip(self):
        store, folder, _ = load_demo()
        self.addCleanup(shutil.rmtree, str(folder), True)
        self.addCleanup(store.close)
        projects = store.read("projects")
        s = Running(data_for=store.data_for, projects=lambda archived=False: projects, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = page_target(cdp)
                cdp.call("Page.enable", {}, sid)
                cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#milestones&p=MOSS"}, sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.mv-lab')", sid)))
                left = cdp.js("Math.min(...[...document.querySelectorAll('.mv-strip .mv-lab')].map(l => l.offsetLeft - l.getBoundingClientRect().width / 2))", sid)
                self.assertGreaterEqual(left, 0, f"{width}px: the left-most label starts inside the strip")
