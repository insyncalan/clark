"""Hostile-input and mutation tests for Settings > Data's two Word buttons (rows bundle, PR 1338, row 831): dataCard.js words, and
Data.jsx in a real browser at 1400 and 900 px ONLY. With no project both Word buttons are disabled and say why; with one each
opens ITS OWN box and nothing else.

Run: python3 -m unittest test_rows_bundle_hostile_data   (from tests/; headless Chrome; fails, never skips, without it)
"""
import json
import re
import tempfile
import unittest

from _paths import ROOT, SRC  # noqa: F401

from clark import page  # noqa: E402
from test_publish_dialog import Base  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402

WIDTHS = (1400, 900)
DATA_CARD_JS = SRC / "clark" / "page" / "src" / "logic" / "dataCard.js"
DATA_JSX = SRC / "clark" / "page" / "src" / "edit" / "Data.jsx"


class Words(unittest.TestCase):
    """dataCard.js read as text (it is the single source of the words; the browser tests below see them rendered)."""

    def test_the_two_word_labels_exact_with_the_ellipsis_character(self):
        # mutants: "..." for the one-character ellipsis, "to"/"from" swapped, trailing space, Word dropped
        text = DATA_CARD_JS.read_text(encoding="utf-8")
        self.assertIn('wordExport: "Export to Word…"', text)
        self.assertIn('wordImport: "Import from Word…"', text)
        self.assertNotIn("Word...", text)

    def test_the_why_words_are_one_sentence(self):
        self.assertIn('IMPORT_NEEDS_PROJECT = "Add a project first."', DATA_CARD_JS.read_text(encoding="utf-8"))

    def test_data_jsx_guards_every_one_of_the_four_buttons(self):
        """Source guard for what the browser tests prove: each of the four buttons has disabled={!data.value}, an
        aria-describedby to its own note, and a note shown only with no project."""
        src = DATA_JSX.read_text(encoding="utf-8")
        for bid in ("export-workbook", "import-workbook", "word-export", "word-import"):
            m = re.search(rf'id="{bid}"[^>]*', src)
            self.assertTrue(m, bid)
            tag = m.group(0)
            self.assertIn("disabled={!data.value}", tag, bid)
            self.assertIn(f'aria-describedby={{data.value ? undefined : "{bid.replace("-workbook", "") if bid.endswith("workbook") else bid}-why"}}', tag, bid)
        self.assertEqual(src.count("{data.value ? null : <p"), 4)


class WithAProject(Base):
    def open_settings(self, p):
        p.js("document.querySelector('#profile-btn').click()")
        p.until("!!document.querySelector('#profile-menu')", "the menu opened")
        p.js("document.querySelector('#profile-menu [data-kind=settings], #profile-menu [data-kind=who]').click()")
        p.until("!!document.querySelector('#data-card')", "the Data card drew")

    def test_enabled_and_each_opens_its_own_box_only(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w)
                self.open_settings(p)
                for bid in ("export-workbook", "import-workbook", "word-export", "word-import"):
                    self.assertFalse(p.js(f"document.getElementById('{bid}').disabled"), bid)
                    self.assertIsNone(p.js(f"document.getElementById('{bid}').getAttribute('aria-describedby')"), bid)
                self.assertEqual(p.js("document.querySelectorAll('#data-card .dc-note').length"), 1, "only the card's own note, no 'Add a project first.'")
                self.assertNotIn("Add a project first", p.js("document.getElementById('data-card').innerText"))
                # export opens the export box and not the import one (mutant: onClick swapped)
                p.js("document.getElementById('word-export').click()")
                p.until("!!document.querySelector('#word-export-dialog[open]')", "the export box")
                self.assertFalse(p.js("!!document.querySelector('#word-import-dialog')"))
                p.js("document.querySelector('#word-export-dialog').close()")
                p.until("!document.querySelector('#word-export-dialog[open]')", "closed")
                p.js("document.getElementById('word-import').click()")
                p.until("!!document.querySelector('#word-import-dialog[open]')", "the import box")
                self.assertFalse(p.js("!!document.querySelector('#word-export-dialog[open]')"))
                self.assertLessEqual(p.js("document.documentElement.scrollWidth"), w)

    def test_a_double_click_does_not_stack_boxes(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            p.js("document.getElementById('word-export').click(); document.getElementById('word-export').click()")
            p.until("!!document.querySelector('#word-export-dialog[open]')", "the export box")
            self.assertEqual(p.js("document.querySelectorAll('#word-export-dialog').length"), 1)


class NoProject(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        import shutil
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def serve(self):
        s = Running(data_for=lambda code, **kw: None, projects=lambda archived=False: [], page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        return s

    def visit(self, cdp, port, width):
        tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{port}/#settings"}, sid)
        self.assertTrue(wait(lambda: bool(cdp.js("!!document.querySelector('#word-import')", sid)), 30), "the Data card did not draw")
        return sid

    def test_both_word_buttons_are_disabled_say_why_and_open_nothing(self):
        s = self.serve()
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, s.port, width)
                for bid in ("word-export", "word-import"):
                    self.assertTrue(cdp.js(f"document.getElementById('{bid}').disabled", sid), bid)
                    self.assertEqual(cdp.js(f"document.getElementById('{bid}').getAttribute('aria-describedby')", sid), f"{bid}-why")
                    self.assertEqual(cdp.js(f"document.getElementById('{bid}-why').textContent", sid), "Add a project first.")
                    self.assertEqual(cdp.js(f"document.getElementById('{bid}').textContent.trim()", sid),
                                     "Export to Word…" if bid == "word-export" else "Import from Word…")
                    # the described-by target really is the note that is on the page
                    self.assertTrue(cdp.js(f"document.getElementById(document.getElementById('{bid}').getAttribute('aria-describedby')).offsetWidth > 0", sid))
                cdp.js("document.getElementById('word-export').click(); document.getElementById('word-import').click()", sid)
                self.assertEqual(cdp.js("document.querySelectorAll('dialog[open]').length", sid), 0)
                self.assertFalse(cdp.js("!!document.getElementById('word-export-dialog') || !!document.getElementById('word-import-dialog')", sid))
                self.assertEqual(cdp.js("document.querySelectorAll('#data-card .dc-note').length", sid), 5, "four why notes and the card's own note")
                self.assertTrue(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), "no sideways scroll")

    def test_all_four_buttons_agree_with_no_project(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.visit(cdp, s.port, 1400)
            self.assertEqual(cdp.js("JSON.stringify([...document.querySelectorAll('#data-card button')].map(b => [b.id, b.disabled]))", sid),
                             json.dumps([["export-workbook", True], ["import-workbook", True], ["word-export", True], ["word-import", True]], separators=(",", ":")))


if __name__ == "__main__":
    unittest.main()
