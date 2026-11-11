"""Row 880 (motion): a group opens with its rows gliding in. Run: python3 dev/run_tests.py test_motion_group

Opening a group, its column names and rows rise 4 px and fade in over --dur-layout with --ease-enter (opacity and transform only, no height
moves; the heading stays). Closing is at once, as before. Under reduced motion the rows show at once. Checked at 1400 and 900 px, light and dark.
"""
import json
import re
import unittest
from _editor_checks import for_url

from _paths import ROOT
import _testpage as testpage

from _real_server import real_server
from test_server import chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402

EDIT = (ROOT / "src/clark/page/src/edit/edit.css").read_text(encoding="utf-8")
PUBLISHED = (ROOT / "src/clark/page/page-view.html").read_text(encoding="utf-8") if (ROOT / "src/clark/page/page-view.html").exists() else ""
CSS = (ROOT / "src/clark/page/shell.css").read_text(encoding="utf-8")
# A group just opened (the thead and tbody the table draws with the class) holding its column names and one row, and a group heading beside it.
MAKE = """(() => { const t = document.createElement('table'); t.innerHTML = '<thead class="opening"><tr class="grp"><th>g</th></tr><tr class="colh"><th>c</th></tr></thead><tbody class="opening"><tr class="r"><td>x</td></tr></tbody>'; document.body.appendChild(t);
  const g = n => getComputedStyle(t.querySelector(n)); return JSON.stringify({colh: [g('.colh').animationName, g('.colh').animationDuration], row: g('.r').animationName, head: g('.grp').animationName}); })()"""


class MotionGroup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()
        cls.code = next(iter(cls.ids))

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        import shutil
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def load(self, cdp, width, scheme, motion):
        projects = self.store.read("projects")
        s = real_server(self.store.path, self.store.data_for, who="Demo User", projects=lambda archived=False: projects,
                        page_html=lambda: testpage.html())
        self.addCleanup(s.close)
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme},
                                                              {"name": "prefers-reduced-motion", "value": motion}]}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{s.port}/#dashboard&p={self.code}")}, sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#profile-btn')", sid)))
        return sid

    def test_row_880_opened_rows_glide_in_and_are_still_when_reduced(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                for motion, want, dur in (("no-preference", "m-rise", "0.38s"), ("reduce", "none", "0s")):
                    with self.subTest(width=width, scheme=scheme, motion=motion), chrome() as cdp:
                        sid = self.load(cdp, width, scheme, motion)
                        got = json.loads(cdp.js(MAKE, sid))
                        self.assertEqual((got["colh"][0], got["colh"][1]), (want, dur))
                        self.assertEqual(got["row"], want)
                        self.assertEqual(got["head"], "none", "the heading stays still")

    def test_row_880_is_edit_only_uses_tokens_and_the_page_marks_only_an_opened_group_in_the_edit_build(self):
        i = EDIT.index("row 880:")
        block = EDIT[i:]
        self.assertIn("prefers-reduced-motion: no-preference", block)
        self.assertRegex(block, r'\[data-motion="reduce"\]\) tbody\.opening > tr:not\(\.grp\) \{ animation: m-rise var\(--dur-layout\) var\(--ease-enter\) 1; \}')
        self.assertNotIn("tbody.opening", CSS, "the published file's stylesheet has no glide")
        self.assertNotIn("tbody.opening", PUBLISHED, "nor does the published page")
        body = re.search(r"@keyframes m-rise \{(.*?)\}\s*\}", CSS, re.S).group(1)
        self.assertNotRegex(body, r"height|margin|padding|top|left|width")
        jsx = (ROOT / "src/clark/page/src/components/WorkItems.jsx").read_text(encoding="utf-8")
        self.assertRegex(jsx, r"justOpened\s*=\s*shut\s*&&\s*!fromFile\.value\s*\?\s*c\.key")
        self.assertRegex(jsx, r'class=\{justOpened === c\.key && !shut && !fromFile\.value \? "opening"')

    def test_row_1131_lows_heads_have_scope_col_thead_is_pinned_and_both_ends_are_awaited(self):
        jsx = (ROOT / "src/clark/page/src/components/WorkItems.jsx").read_text(encoding="utf-8")
        heads = re.search(r"function Heads\(.*?\n\}\n", jsx, re.S).group(0)
        ths = re.findall(r"<th\b[^>]*>", heads)
        self.assertGreaterEqual(len(ths), 7)
        for th in ths:
            self.assertIn('scope="col"', th)
        self.assertRegex(EDIT, r'\[data-motion="reduce"\]\) thead\.opening > tr:not\(\.grp\)')
        self.assertRegex(jsx, r'<thead data-group=\{c\.key\} class=\{justOpened === c\.key && !shut && !fromFile\.value \? "opening"')
        # the group is marked done only when neither the thead nor the tbody is still gliding
        opened = re.search(r"const opened = .*", jsx).group(0)
        self.assertIn(".opening", opened.split("remove(\"opening\")", 1)[1])


if __name__ == "__main__":
    unittest.main()
