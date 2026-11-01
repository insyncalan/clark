"""Prototype parity B-7: a Type badge in the Work items table is one line, never "Dependenc / y".

Run: python3 dev/run_tests.py test_type_column_one_line
The real page and a real server over the fictional demo data, at 1400 and 900 px, in View and in Edit: every Type badge
("Dependency" is the longest word) is on one line, sits inside its Type cell, no other cell of the table has text wider than
its box, and the page does not scroll sideways. A second pass makes every badge wider than the real font does (letter spacing)
to show the rule, not the font's luck, keeps the word whole. The shared CSS (shell.css) is also pinned without Chrome.
The browser parts are required: they fail, never skip, without Chrome (set CLARK_CHROME to its path).
"""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401  (puts src/ on the path)

from clark import page, server as sv  # noqa: E402
from clark.store import open_store  # noqa: E402
from test_server import CHROME, Running, chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402

EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")
SHELL = SRC / "clark" / "page" / "shell.css"

# Each Type badge: its word, its lines, and whether it sits inside its cell; then the cells that clip or spill and the page's width.
MEASURE = r"""(() => {
  const lines = (node) => { const r = document.createRange(); r.selectNodeContents(node); return new Set([...r.getClientRects()].filter((x) => x.width > 0).map((x) => Math.round(x.top))).size; };
  const types = [...document.querySelectorAll('table.items td.c-type .type')].map((t) => { const c = t.closest('td').getBoundingClientRect(), b = t.getBoundingClientRect();
    return { text: t.textContent.trim(), lines: lines(t), h: Math.round(b.height), width: Math.round(b.width), cell: Math.round(c.width), inside: b.left >= c.left - 1 && b.right <= c.right + 1 }; });
  const wide = [...document.querySelectorAll('table.items tbody td')].filter((e) => e.scrollWidth > e.clientWidth + 1).map((e) => e.className);
  const cols = [...document.querySelectorAll('table.items thead th')].map((th) => th.className + ':' + Math.round(th.getBoundingClientRect().width));
  return JSON.stringify({ types, wide, cols, sw: document.documentElement.scrollWidth, vw: innerWidth });
})()"""
WIDER = "table.items .type { letter-spacing: .1em !important; }"      # about 13 px more across "Dependency" than the real font


def tearDownModule():
    shutil.rmtree(EMPTY_BRANDING, ignore_errors=True)


class Source(unittest.TestCase):
    """No Chrome: the shared stylesheet keeps a Type badge on one line above the phone layout."""

    def test_a_type_badge_does_not_wrap_above_the_phone_layout(self):
        css = SHELL.read_text(encoding="utf-8")
        m = re.search(r"@media \(min-width: 641px\) \{([^}]*\{[^}]*\})\s*\}", css)
        self.assertTrue(m and "table.items .type" in m.group(1), "a rule for table.items .type above the phone layout")
        self.assertIn("white-space: nowrap", m.group(1))
        self.assertIn("overflow-wrap: normal", m.group(1), "the cell's overflow-wrap: anywhere must not reach the badge")

    def test_the_type_column_stays_wide_enough_for_the_longest_word(self):
        css = SHELL.read_text(encoding="utf-8")
        self.assertRegex(css, r"table\.items \.c-type \{ width: 116px; \}")
        self.assertRegex(css, r"@media \(max-width: 900px\) \{ table\.items \.c-type \{ width: 116px; \}")


class TypeColumn(unittest.TestCase):
    def setUp(self):
        assert Path(CHROME).is_file(), f"Google Chrome is needed for the required browser tests ({CHROME}); set CLARK_CHROME"
        self.store, self.folder, _ = load_demo()
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.addCleanup(self.store.close)
        self.path = self.folder / "clark.db"
        self.s = Running(data_for=self.read, projects=lambda: [{"code": "TUL", "name": "Tulip"}], page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def read(self, code):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return st.data_for(code)
        finally:
            st.close()

    def measure(self, cdp, width, mode, extra_css=""):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/#work&p=TUL&f=mode:all"}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid) > 0), "the list drew")
        if mode == "edit":
            cdp.js("document.querySelector('[data-mode=edit]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('table.items .cell-pick')", sid)), "Edit shows the cells' pickers")
        if extra_css:
            cdp.js("(() => { const sh = new CSSStyleSheet(); sh.replaceSync(%s); document.adoptedStyleSheets = [...document.adoptedStyleSheets, sh]; })()" % json.dumps(extra_css), sid)
        return json.loads(cdp.js(MEASURE, sid))

    def check(self, got, where):
        words = {t["text"] for t in got["types"]}
        self.assertIn("Dependency", words, where + ": the longest Type word is on the page")
        self.assertGreaterEqual(len(words), 5, where + ": the kinds of work item are on the page")
        for t in got["types"]:
            self.assertEqual(t["lines"], 1, f"{where}: '{t['text']}' is broken across lines ({got['cols']})")
            self.assertLessEqual(t["h"], 26, f"{where}: '{t['text']}' is taller than one line")
            self.assertTrue(t["inside"], f"{where}: '{t['text']}' ({t['width']} px) runs outside its {t['cell']} px cell")
        self.assertEqual(got["wide"], [], where + ": a cell has text wider than its box (clipped)")
        self.assertLessEqual(got["sw"], got["vw"], where + ": the page scrolls sideways")

    def test_the_type_badge_is_one_line_at_1400_and_900_in_view_and_edit(self):
        with chrome() as cdp:
            for width in (1400, 900):
                for mode in ("view", "edit"):
                    self.check(self.measure(cdp, width, mode), f"{width} px, {mode}")

    def test_the_word_stays_whole_even_in_a_wider_font(self):
        with chrome() as cdp:
            for width in (1400, 900):
                for mode in ("view", "edit"):
                    self.check(self.measure(cdp, width, mode, WIDER), f"{width} px, {mode}, wider letters")


if __name__ == "__main__":
    unittest.main()
