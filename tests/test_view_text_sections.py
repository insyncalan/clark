"""Prototype parity A-D4: View draws the text of Current state, Summary, This week and Next week.

Run: python3 dev/run_tests.py test_view_text_sections
Before, the page clark serves said "Not shown on this page yet." for these four in View. Now View draws the saved text, cleaned by
the page's own cleaner (cleanHtml), or "Nothing written yet." when there is none. Edit is unchanged (it still says the old line:
the editor on these bodies is a later item), and a published file is unchanged (it already drew a text section's body, cleaned by
the publish build, and still leaves Current state out). The browser class runs at 1400 and 900, light and dark; the source class
reads the page's files and needs no browser.
"""
import shutil
import tempfile
import unittest
from unittest import mock

from _demo import USER, DemoStore
from _paths import ROOT
from clark import page, server as sv
from test_page import navigate
from test_server import Running, chrome, wait

PAGE_SRC = ROOT / "src" / "clark" / "page" / "src"
OLD = "Not shown on this page yet."
EMPTY = "Nothing written yet."
EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")

CURRENT = "<p>The pilot is on track and the data is clean.</p>"
SUMMARY = "<p>Plain words about <strong>the month</strong>.</p><ul><li>One thing</li></ul>"
HOSTILE = '<p>Next week we ship.</p><script>window.pwned = 1</script><img src="x" onerror="window.pwned = 2"><p onclick="window.pwned = 3">Click</p>'
SECTIONS = {"ABC-S-001": "current", "ABC-S-005": "summary", "ABC-S-006": "this week", "ABC-S-007": "next week"}

LUMA = """(function(){
  var rgb = function(c){ var m = c.match(/[\\d.]+/g).map(Number); return m; };
  var lum = function(c){ var m = rgb(c).slice(0, 3).map(function(v){ v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }); return 0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2]; };
  var bg = function(el){ while (el) { var c = getComputedStyle(el).backgroundColor; if (rgb(c).length < 4 || rgb(c)[3] > 0) return c; el = el.parentElement; } return 'rgb(255,255,255)'; };
  var el = document.querySelector('%s');
  var a = lum(getComputedStyle(el).color), b = lum(bg(el)), hi = Math.max(a, b), lo = Math.min(a, b);
  return (hi + 0.05) / (lo + 0.05);
})()"""


def tearDownModule():
    shutil.rmtree(EMPTY_BRANDING, ignore_errors=True)


class TheBrowser(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        store = self.demo.store
        with store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"current_state": CURRENT})
            st.update("report_sections", "ABC-S-005", {"body": SUMMARY})
            st.update("report_sections", "ABC-S-007", {"body": HOSTILE})      # ABC-S-006 stays empty
        self.s = Running(data_for=store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def until(self, cdp, sid, expr, what):
        self.assertTrue(wait(lambda: cdp.js(expr, sid), 15), what)

    def text_of(self, cdp, sid, sec):
        return cdp.js(f"(document.querySelector('[data-id=\"{sec}\"]').textContent || '')", sid)

    def test_view_draws_the_text_and_edit_is_unchanged(self):
        with chrome() as cdp:
            sid = navigate(cdp, self.s.port, "#dashboard&p=ABC")
            self.until(cdp, sid, "document.querySelectorAll('.sec').length > 0", "the report drew")
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                for scheme, theme in (("light", ""), ("dark", "dark")):
                    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
                    cdp.js(f"document.documentElement.dataset.theme = '{theme}'", sid)
                    where = f"{width} {scheme}"
                    self.assertEqual(cdp.js("document.querySelector('#report').dataset.mode", sid), "view")
                    cur, summ, week, nxt = (self.text_of(cdp, sid, k) for k in SECTIONS)
                    self.assertIn("The pilot is on track and the data is clean.", cur, where)
                    self.assertIn("Plain words about the month.", summ, where)
                    self.assertIn("One thing", summ, where)
                    self.assertEqual(cdp.js("document.querySelector('[data-id=ABC-S-005] strong').textContent", sid), "the month", where)
                    self.assertIn(EMPTY, week, "an empty body says so in plain words: " + where)
                    self.assertIn("Next week we ship.", nxt, where)
                    for k in SECTIONS:
                        self.assertNotIn(OLD, self.text_of(cdp, sid, k), f"{k} no longer says the old line in View: {where}")
                    # the cleaner dropped the script, the handler and the picture: nothing ran, nothing is left
                    self.assertIsNone(cdp.js("window.pwned", sid) or None, where)
                    self.assertEqual(cdp.js("document.querySelectorAll('[data-id=ABC-S-007] script, [data-id=ABC-S-007] [onclick], [data-id=ABC-S-007] [onerror]').length", sid), 0, where)
                    # the types still not drawn keep the one plain line
                    other = cdp.js("[...document.querySelectorAll('.sec')].filter(s => ['raid', 'actions', 'decisions'].includes(s.dataset.type)).map(s => s.querySelector('.quiet').textContent)", sid)
                    self.assertEqual(other, [OLD] * 3, where)
                    # readable and in the page: 4.5:1 text, no sideways scroll
                    self.assertGreaterEqual(cdp.js(LUMA % "[data-id=ABC-S-005] .prose p", sid), 4.5, "text contrast " + where)
                    self.assertGreaterEqual(cdp.js(LUMA % "[data-id=ABC-S-006] .quiet", sid), 4.5, "quiet line contrast " + where)
                    self.assertGreaterEqual(float(cdp.js("parseFloat(getComputedStyle(document.querySelector('[data-id=ABC-S-005] .prose p')).fontSize)", sid)), 13, where)
                    self.assertLessEqual(cdp.js("document.documentElement.scrollWidth - window.innerWidth", sid), 0, "no sideways scroll " + where)
            # Edit says what it said before, for all four
            cdp.js("document.querySelector('[data-mode=edit]').click()", sid)
            self.until(cdp, sid, "document.querySelector('#report').dataset.mode === 'edit'", "Edit mode")
            for k in SECTIONS:
                self.assertIn(OLD, self.text_of(cdp, sid, k), f"Edit keeps the old line for {k}")
            cdp.js("document.querySelector('[data-mode=view]').click()", sid)
            self.until(cdp, sid, "document.querySelector('#report').dataset.mode === 'view'", "View again")
            self.assertIn("Plain words about the month.", self.text_of(cdp, sid, "ABC-S-005"))


class TheSource(unittest.TestCase):
    """No browser: the page's files say what the change promises."""

    def test_section_draws_the_text_through_the_cleaner_in_view_only(self):
        src = (PAGE_SRC / "components" / "Section.jsx").read_text(encoding="utf-8")
        self.assertIn('section.type === "text" || section.type === "current"', src)
        self.assertIn("!editing && clean", src)                       # View only: Edit keeps its line, a published page has no cleaner
        self.assertIn(EMPTY, src)
        self.assertIn('<p class="quiet">Not shown on this page yet.</p>', src)     # every other type, and Edit, keep the old line
        self.assertEqual(src.count("dangerouslySetInnerHTML"), 2)      # the file's already-cleaned body, and View's cleaned text

    def test_only_the_edit_build_carries_the_cleaner(self):
        index = (PAGE_SRC / "edit" / "index.js").read_text(encoding="utf-8")
        self.assertRegex(index, r"export const EDIT = \{ clean,")
        self.assertIn('import { cleanHtml } from "../logic/cleanHtml.js";', index)
        for name in ("Section.jsx", "Dashboard.jsx"):
            self.assertNotIn("logic/cleanHtml.js", (PAGE_SRC / "components" / name).read_text(encoding="utf-8"), name)
        dash = (PAGE_SRC / "components" / "Dashboard.jsx").read_text(encoding="utf-8")
        self.assertIn("clean={!fromFile.value && tools ? tools.clean : null}", dash)

    def test_the_published_page_draws_the_same_as_before(self):
        dash = (PAGE_SRC / "components" / "Dashboard.jsx").read_text(encoding="utf-8")
        line = next(l for l in dash.splitlines() if "const fileDraws" in l)
        self.assertIn('s.type === "text" ? !emptyBody(s.body)', line)
        self.assertNotIn("current", line)                              # a published file still leaves Current state out (a product decision)
        view = (ROOT / "src" / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        self.assertNotIn("SanitiseError", view)                        # the cleaner is not in the published build

    def test_built_pages_are_current(self):
        import subprocess, sys
        r = subprocess.run([sys.executable, str(ROOT / "dev" / "tools" / "build_page.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
