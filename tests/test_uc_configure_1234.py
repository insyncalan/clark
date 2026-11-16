"""Row 1234: the Configure button and panel of the Use case summary (Edit only), at 1400 and 900 px, and the published bundle holds none of its words.
Run: ~/ag/slot.sh with, inside tests/: PYTHONPATH=../src:../vendor:. python3 -m unittest test_uc_configure_1234
Words are the ruled ones (16-11 00:58); anything else is in an UNRULED_ constant of edit/ucConfigureWords.js.
"""
import json
import re
import time
import unittest

from _paths import SRC
from test_glance_page import Setup, tearDownModule  # noqa: F401
from test_server import chrome

from _uc_view import put_view
from clark import page

PAGE_SRC = SRC / "clark" / "page" / "src"
WORDS_FILE = PAGE_SRC / "edit" / "ucConfigureWords.js"
SAME = "Edit uses the same number and scroll, so what you see is what viewers get."
# Whole phrases only the editor draws; short common words (Configure, All, Show all, Number shown) are checked in their own tests.
PHRASES = ["Configure use cases", "Use cases shown", "Viewers can scroll the list", SAME,
           "scrolls up and down to the rest", "viewers see only the first"]


class Configure(Setup):
    def edit(self, p):
        p.js("document.querySelector('[data-mode=edit]').click()")
        p.until("!!document.querySelector('#ucAdd')", "Edit")

    def stored(self):
        """The view the server holds: the JSON in the usecases section's body."""
        row = next(r for r in self.store.read("report_sections", "ABC") if r["type"] == "usecases")
        return json.loads(row["body"]) if row["body"] else None

    def wait_body(self, p, check, what):
        for _ in range(100):
            v = self.stored()
            if v and check(v):
                return v
            time.sleep(0.1)
        self.fail(what)

    def test_view_has_no_configure_button(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.until("!!document.querySelector('.uc')", "summary")
                self.assertIsNone(p.js("document.querySelector('[data-uc-configure]')"))

    def test_edit_button_opens_the_panel_with_the_approved_words(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.edit(p)
                self.assertEqual(p.js("document.querySelector('[data-uc-configure]').textContent"), "Configure")
                p.js("document.querySelector('[data-uc-configure]').click()")
                p.until("!!document.querySelector('#ucCfg')", "panel")
                self.assertEqual(p.js("document.querySelector('#uccfg-title').textContent"), "Configure use cases")
                self.assertEqual(p.js("document.querySelector('label[for=ucCfgN]').textContent"), "Number shown")
                self.assertEqual(p.js("document.querySelector('#ucCfgN').getAttribute('aria-label')"), "Use cases shown")
                self.assertEqual(p.js("document.querySelector('label[for=ucCfgS]').textContent"), "Viewers can scroll the list")
                self.assertEqual(p.js("document.querySelector('[data-uc-cfg-same]').textContent"), SAME)
                self.assertEqual(p.js("document.querySelector('#ucCfgN').lastElementChild.textContent"), "All")
                self.assertEqual(p.js("document.querySelector('[data-uc-of]').textContent"), "of 2")
                self.assertEqual(p.js("document.querySelector('[data-uc-cfg-help]').textContent"),
                                 "On: the list is 5 rows tall and scrolls up and down to the rest. Off: viewers see only the first 5.")
                self.assertTrue(p.js("(r => r.left >= 0 && r.right <= innerWidth)(document.querySelector('#ucCfg').getBoundingClientRect())"), "fits the width")

    def test_changes_are_saved_in_the_section_body_and_the_help_follows(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                put_view(self, None)
                p = self.show(cdp, width)
                self.edit(p)
                p.js("document.querySelector('[data-uc-configure]').click()")
                p.until("!!document.querySelector('#ucCfgN')", "panel")
                p.js("(s => { s.value = '1'; s.dispatchEvent(new Event('change', {bubbles: true})); })(document.querySelector('#ucCfgN'))")
                self.wait_body(p, lambda v: v["n"] == 1, "n saved")
                p.js("document.querySelector('#ucCfgS').click()")
                v = self.wait_body(p, lambda v: v["scroll"] is True, "scroll saved")
                self.assertEqual(v, {"n": 1, "scroll": True, "tracker": "top"}, "exactly n, scroll, tracker")
                p.until("document.querySelector('[data-uc-cfg-help]').textContent.includes('the list is 1 rows tall')", "help follows")
                p.js("(s => { s.value = 'all'; s.dispatchEvent(new Event('change', {bubbles: true})); })(document.querySelector('#ucCfgN'))")
                self.wait_body(p, lambda v: v["n"] == "all", "all saved")
                p.until("document.querySelector('[data-uc-cfg-help]').textContent.includes('the list is 2 rows tall')", "help follows all")
                self.assertIsNone(p.js("localStorage.getItem('clark.ucView')"), "nothing kept in the browser")
                p.reload()
                self.edit(p)
                p.js("document.querySelector('[data-uc-configure]').click()")
                p.until("!!document.querySelector('#ucCfgN')", "panel again")
                self.assertEqual(p.js("document.querySelector('#ucCfgN').value"), "all", "read back from the body after a reload")
                self.assertTrue(p.js("document.querySelector('#ucCfgS').checked"))

    def test_two_changes_made_before_the_page_has_drawn_the_first_keep_both(self):
        """A second change in the same moment builds on the first (a stale drawn view once saved n back to 5): both fields reach the body."""
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                put_view(self, None)
                p = self.show(cdp, width)
                self.edit(p)
                p.js("document.querySelector('[data-uc-configure]').click()")
                p.until("!!document.querySelector('#ucCfgN')", "panel")
                p.js("(s => { s.value = '1'; s.dispatchEvent(new Event('change', {bubbles: true})); document.querySelector('#ucCfgS').click(); })(document.querySelector('#ucCfgN'))")
                v = self.wait_body(p, lambda v: v["scroll"] is True, "scroll saved")
                self.assertEqual(v, {"n": 1, "scroll": True, "tracker": "top"}, "the second change kept the first")

    def test_a_saved_view_is_recorded_as_made_in_the_table(self):
        """The place a save names is what History says about it: place "cell" reads as the table, "report" as the page."""
        from clark import history
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                put_view(self, None)
                p = self.show(cdp, width)
                self.edit(p)
                p.js("document.querySelector('[data-uc-configure]').click()")
                p.until("!!document.querySelector('#ucCfgN')", "panel")
                p.js("(s => { s.value = '1'; s.dispatchEvent(new Event('change', {bubbles: true})); })(document.querySelector('#ucCfgN'))")
                self.wait_body(p, lambda v: v["n"] == 1, "n saved")
                ref = next(r["id"] for r in self.store.read("report_sections", "ABC") if r["type"] == "usecases")
                rows = self.store.con.execute("SELECT place FROM item_events WHERE item_id = ? ORDER BY event_id DESC", (ref,)).fetchall()
                self.assertTrue(rows, "the save is in the history")
                self.assertEqual(rows[0][0], "cell")
                self.assertEqual(history.how_text("page", rows[0][0], None), history.HOW_TABLE)
                self.assertNotEqual(history.how_text("page", rows[0][0], None), history.HOW_REPORT)

    def test_the_panel_draws_the_stored_view(self):
        put_view(self, {"n": 3, "scroll": True, "tracker": "off"})
        with chrome() as cdp:
            p = self.show(cdp)
            self.edit(p)
            p.js("document.querySelector('[data-uc-configure]').click()")
            p.until("!!document.querySelector('#ucCfgN')", "panel")
            self.assertEqual(p.js("document.querySelector('#ucCfgN').value"), "3")
            self.assertTrue(p.js("document.querySelector('#ucCfgS').checked"))

    def test_escape_closes_and_gives_focus_back(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.edit(p)
            p.js("document.querySelector('[data-uc-configure]').focus(); document.querySelector('[data-uc-configure]').click()")
            p.until("!!document.querySelector('#ucCfg')", "panel")
            p.js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
            p.until("!document.querySelector('#ucCfg')", "closed")
            self.assertTrue(p.js("document.activeElement === document.querySelector('[data-uc-configure]')"))


class Source(unittest.TestCase):
    def test_unapproved_strings_are_only_in_unruled_constants(self):
        text = WORDS_FILE.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("export const") and '"' in line and not line.startswith("//"):
                name = line.split()[2]
                if name.startswith("UNRULED_"):
                    continue
                self.assertIn(name, {"CONFIGURE", "TITLE", "NUMBER_LABEL", "SHOWN_LABEL", "ALL_WORD", "OF", "SCROLL_LABEL", "SAME_NOTE",
                                     "SCROLL_HELP", "DONE",
                                     "TRACKER_LABEL", "TRACKER_GROUP", "TRACKER_WORDS", "TRACKER_HELP"}, f"{name} is neither approved nor UNRULED_")
        edit = (PAGE_SRC / "edit" / "UseCasesEdit.jsx").read_text(encoding="utf-8")
        body = edit[edit.index("function ConfigureBox"):edit.index("/** The growing Add button")]
        self.assertFalse(re.search(r">\s*[A-Za-z][A-Za-z ]+\s*<", body), "no bare words in the panel markup")

    def test_the_words_are_in_no_shared_source(self):
        for p in PAGE_SRC.rglob("*"):
            if p.suffix not in (".js", ".jsx", ".css") or "edit" in p.relative_to(PAGE_SRC).parts:
                continue
            text = p.read_text(encoding="utf-8")
            for w in PHRASES:
                self.assertNotIn(w, text, f"{w!r} in shared source {p.relative_to(PAGE_SRC)}")
        for p in (PAGE_SRC / "components").glob("UseCases*.jsx"):
            self.assertNotIn("Configure", p.read_text(encoding="utf-8"), p.name)


class PublishedBundle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        page.ensure_built()
        cls.view = page.VIEW_PAGE.read_text(encoding="utf-8")
        cls.edit = page.PAGE.read_text(encoding="utf-8")

    def test_the_published_bundle_holds_none_of_the_words(self):
        for w in PHRASES:
            self.assertNotIn(w, self.view, w)
        self.assertFalse(re.search(r'["\'>]Configure["\'<]', self.view), "no Configure button")
        self.assertNotIn("data-uc-configure", self.view)
        self.assertNotIn("clark.ucView", self.view)
        self.assertNotIn('"ucView"', self.view)

    def test_the_check_can_fail(self):
        for w in PHRASES:
            self.assertIn(w, self.edit, f"{w!r} is in the editor build")


if __name__ == "__main__":
    unittest.main()
