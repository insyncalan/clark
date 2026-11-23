"""Row 1287, more killers: in View the status picker keeps the report icon (with its words and tab stop), the date picker says the plain
date, a selection in a description stops the click that opens the peek, and the Work items list picks its priority too. Fictional data only.

Run: python3 dev/run_tests.py test_view_picks_1287_more   (headless Chrome; fails, never skips, without it)
"""
import time
import unittest

import test_tpl_workitems as T
from test_report_editor import Pg, tearDownModule  # noqa: F401
from test_server import chrome
from clark import page, theme
from _real_server import real_server
import _testpage as testpage


def classic(test):
    # Row 1287 (Classic only): the Cards page keeps the markup it had, so these tests serve the page with the Classic theme layered, as Classic serves it
    test.s.close()
    css = theme.css("prototype-2.0")
    test.s = real_server(test.store.path, test.store.data_for, page_html=lambda: page.layer_theme(testpage.html(), css), seam=test.seam)
    test.addCleanup(test.s.close)


class ViewPickMore(T.InThePage):
    def section(self, kind, title):
        with self.store.step("dashboard", T.USER) as st:
            return st.create("report_sections", {"project": "ABC", "type": kind, "title": title, "sort_order": 1})

    def row_of(self, ref, rid):
        return f"[data-id=\"{ref}\"] .wl-row[data-id=\"{rid}\"]"

    def test_the_status_picker_wraps_the_report_icon_with_its_words_and_one_tab_stop(self):
        classic(self)
        ref = self.section("actions", "Fictional actions")
        row = self.row_of(ref, self.a_due)
        with chrome() as cdp:
            p = self.show(cdp, 1400)
            p.until(f"!!document.querySelector('{row} .c-ico .cell-pick')", "the status picker drew")
            self.assertEqual(p.js(f"document.querySelectorAll('{row} .c-ico .cell-pick .pill').length"), 0, "the report icon stays; no live pill")
            self.assertEqual(p.js(f"document.querySelectorAll('{row} .c-ico .cell-pick .ico').length"), 1)
            self.assertEqual(p.js(f"document.querySelector('{row} .c-ico .cell-pick .ico').getAttribute('role')"), "img", "the icon is not plain")
            self.assertEqual(p.js(f"document.querySelector('{row} .c-ico .cell-pick .ico').getAttribute('tabindex')"), "0")
            self.assertTrue(p.js(f"(document.querySelector('{row} .c-ico .cell-pick .ico').getAttribute('aria-label') || '').startsWith('Action')"))

    def test_the_date_picker_says_the_plain_date_and_a_decision_keeps_its_word_in_the_cell_only(self):
        classic(self)
        ref = self.section("actions", "Fictional actions")
        with self.store.step("dashboard", T.USER) as st:
            dec = st.create("decisions", {"project": "ABC", "decision": "Pick the supplier", "status": "Pending", "needed_by": "2030-02-02", "source": "demo"})
        dref = self.section("decisions", "Fictional decisions")
        tail = "(e => e.getAttribute('aria-label').split(': ').pop().replace(/\\. Change$/, ''))"
        with chrome() as cdp:
            p = self.show(cdp, 1400)
            act = self.row_of(ref, self.a_due) + " .c-date"
            p.until(f"!!document.querySelector('{act} .cell-pick')", "the actions list drew")
            said = p.js(f"{tail}(document.querySelector('{act} .cell-pick'))")
            self.assertEqual(p.js(f"document.querySelector('{act} .cell-val').textContent.trim()"), said, "an action's cell is the plain date")
            self.assertNotIn("Due", said)
            d = self.row_of(dref, dec) + " .c-date"
            p.until(f"!!document.querySelector('{d} .cell-pick')", "the decisions list drew")
            said = p.js(f"{tail}(document.querySelector('{d} .cell-pick'))")
            cell = p.js(f"document.querySelector('{d} .cell-val').textContent.trim()")
            self.assertTrue(cell.startswith("Needed by "), cell)
            self.assertEqual(cell, "Needed by " + said, "the picker says the plain date; the cell keeps the word")

    def select_then_click(self, p, title):
        p.js(f"(() => {{ const t = document.querySelector('{title}'), r = document.createRange(); r.selectNodeContents(t); const s = getSelection(); s.removeAllRanges(); s.addRange(r); t.click(); }})()")
        time.sleep(0.6)
        self.assertEqual(p.js("!!document.querySelector('#peek')"), False, "a click with text selected opens nothing")
        p.js("getSelection().removeAllRanges()")
        p.js(f"document.querySelector('{title}').click()")
        p.until("!!document.querySelector('#peek')", "a click with nothing selected opens the peek")

    def test_selected_text_in_an_actions_title_does_not_open_the_peek(self):
        ref = self.section("actions", "Fictional actions")
        title = self.row_of(ref, self.a_due) + " .c-title"
        with chrome() as cdp:
            p = self.show(cdp, 1400)
            p.until(f"!!document.querySelector('{title}')", "the actions list drew")
            self.select_then_click(p, title)

    def test_selected_text_in_a_work_items_title_does_not_open_the_peek(self):
        classic(self)
        ref = self.add({"mode": "all", "columns": ["id", "owner", "due", "status", "priority"], "owner": ["Pat Demo", "Lee Demo"]})
        title = f"[data-id=\"{ref}\"] .wil-table tbody tr[data-id=\"{self.a_due}\"] .wil-c-title"
        with chrome() as cdp:
            p = self.show(cdp, 1400)
            p.until(f"!!document.querySelector('{title}')", "the list drew")
            self.select_then_click(p, title)

    def test_the_work_items_list_picks_its_urgency_in_view(self):
        classic(self)
        ref = self.add({"mode": "all", "columns": ["id", "owner", "due", "status", "priority"], "owner": ["Pat Demo", "Lee Demo"]})
        row = f"[data-id=\"{ref}\"] .wil-table tbody tr[data-id=\"{self.a_due}\"]"
        with chrome() as cdp:
            p = self.show(cdp, 1400)
            p.until(f"!!document.querySelector('{row}')", "the list drew")
            self.assertEqual(p.js(f"document.querySelectorAll('{row} .wil-c-priority .cell-pick[data-cell$=\":priority\"]').length"), 1)

    def test_the_work_items_pickers_say_the_cell_in_their_label_never_undefined(self):
        classic(self)
        ref = self.add({"mode": "all", "columns": ["id", "owner", "due", "status", "priority"], "owner": ["Pat Demo", "Lee Demo"]})
        row = f"[data-id=\"{ref}\"] .wil-table tbody tr[data-id=\"{self.a_due}\"]"
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.until(f"!!document.querySelector('{row} .cell-pick')", "the list drew")
                for col in ("owner", "due", "status", "priority"):
                    label = p.js(f"document.querySelector('{row} .wil-c-{col} .cell-pick').getAttribute('aria-label')")
                    self.assertNotIn("undefined", label, col)
                    said = label.split(": ", 1)[1].rsplit(". Change", 1)[0]
                    self.assertTrue(said, col)
                    if col != "status":      # the status cell draws the live pill, whose words the label need not repeat
                        self.assertIn(said.split(" (")[0], p.js(f"document.querySelector('{row} .wil-c-{col} .cell-pick').textContent"), col)


if __name__ == "__main__":
    unittest.main()
