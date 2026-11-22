"""Row 1500 in the Classic Theme: the Settings sidebar group spacing (12 px above a group, the first group 0, 4 px between the pages of a group)
also at 900 and 1099 px, as Chrome computes it on the REAL Settings page (demo database, fictional data), light and dark. Cards is pinned by
test_settings_sidebar_1401.test_cards_unchanged.
Widths: 1400, 1099 and 900 (900 is paused team-wide for hand checks; this test measures it in headless Chrome).

Run: python3 dev/run_tests.py test_settings_sidebar_1500"""
import re
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from _editor_checks import for_url

from clark import page
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

NAME = "prototype-2.0"
THEME = Path(__file__).resolve().parent.parent / "src" / "clark" / "themes" / NAME
WIDTHS = (1400, 1099, 900)

PROBE = """(() => { const g = (e, p) => getComputedStyle(e)[p];
  const groups = [...document.querySelectorAll('.set-nav > .set-group')];
  const first = groups[0], later = groups[1];
  const pl = document.querySelector('.set-nav .plain'), lis = pl ? [...pl.children] : [];
  const gap = lis.length > 1 ? Math.round(lis[1].getBoundingClientRect().top - lis[0].getBoundingClientRect().bottom) : -1;
  return { firstMargin: g(first, 'marginTop'), laterMargin: later ? g(later, 'marginTop') : 'none', gap: gap, n: groups.length }; })()"""


class RealSettings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()
        cls.names = {p["code"]: p["name"] for p in cls.store.read("projects")}
        cls.data = {c: cls.store.data_for(c) for c in cls.names}

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def look(self, width, scheme):
        s = Running(data_for=lambda code, **kw: self.data.get(code), projects=lambda archived=False: [{"code": c, "name": n} for c, n in sorted(self.names.items())],
                    page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=NAME))
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
            cdp.call("Page.navigate", {"url": "about:blank"}, sid)
            cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{s.port}/#settings&p=TUL")}, sid)
            self.assertTrue(wait(lambda: bool(cdp.js("!!document.querySelector('.set-chip[aria-current]') && !!document.querySelector('.set-nav .plain')", sid)), 30),
                            "timed out waiting for the real Settings page")
            time.sleep(0.3)
            return cdp.js(PROBE, sid)

    def test_group_margin_12px_at_900_and_1099(self):
        for scheme in ("light", "dark"):
            for width in WIDTHS:
              with self.subTest(width=width, scheme=scheme):
                c = self.look(width, scheme)
                tag = f"classic {scheme} {width}"
                self.assertGreater(c["n"], 1, tag + ": more than one group")
                self.assertEqual(c["firstMargin"], "0px", tag + ": the first group has no gap above it")
                self.assertEqual(c["laterMargin"], "12px", tag + ": 12 px above a group")

    def test_page_gap_4px_at_900_and_1099(self):
        for scheme in ("light", "dark"):
            for width in WIDTHS:
              with self.subTest(width=width, scheme=scheme):
                c = self.look(width, scheme)
                self.assertEqual(c["gap"], 4, f"classic {scheme} {width}: 4 px between the pages of a group")

    def test_spacing_rule_is_not_behind_min_width_1100(self):
        """The page-gap rule must not sit inside a min-width: 1100px block of the Classic CSS."""
        css = "".join((THEME / f).read_text(encoding="utf-8") for f in ("rules.css", "rules-2.css"))
        self.assertRegex(css, r"\.set-nav \.plain\s*\{\s*gap:\s*4px")
        for m in re.finditer(r"@media[^{]*min-width:\s*1100px[^{]*\{", css):
            depth, i = 1, m.end()
            while depth and i < len(css):
                depth += {"{": 1, "}": -1}.get(css[i], 0)
                i += 1
            block = css[m.end():i]
            self.assertNotRegex(block, r"\.set-nav \.plain\s*\{[^}]*gap", "the page gap is not behind min-width 1100px")
            self.assertNotRegex(block, r"\.set-group(:first-child)?\s*\{[^}]*margin-top", "the group margin is not behind min-width 1100px")


if __name__ == "__main__":
    unittest.main()
