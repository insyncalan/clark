"""Row 1234: the Use case summary's scroll list and a use case just put on the page, the cases a mutation audit of UseCases.jsx found uncovered.

Run: ~/ag/slot.sh with, inside tests/: PYTHONPATH=../src:../vendor:. python3 -m unittest test_uc_summary_mm_1234
Three mutants survived: Show all drawn while the list scrolls (View with scroll on, and Edit with a count kept), the scroll height dropped,
and a use case put on the page that does not open its row. A fourth (Edit parts in a published file) cannot be told apart from the real
code: the published page boots with no Edit parts and is always View, so nothing can reach it. Laptop widths only: 1400 and 900 px.
"""
import json
import unittest

from test_server import chrome
from test_use_case_summary_1234 import Demo, tearDownModule  # noqa: F401

SCROLLER = "document.querySelector('.ucrows')"
ROWS = "document.querySelectorAll('.ucrows > .ucrow').length"
BUTTON = "document.querySelector('[data-ucall]')"
SCROLLING = {"n": 4, "scroll": True}


class ScrollList(Demo):
    def test_a_scrolling_list_in_view_has_no_show_all_and_is_n_rows_high(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.set_local(p, **SCROLLING)
                self.assertEqual(p.js(ROWS), self.total, "every use case is in the list, reached by scrolling")
                self.assertIsNone(p.js(BUTTON), "nothing is hidden, so there is no Show all")
                self.assertEqual(p.js(f"getComputedStyle({SCROLLER}).overflowY"), "auto")
                self.assertIn("* 4)", p.js(f"{SCROLLER}.style.maxHeight"), "the height is n rows")
                self.assertGreater(p.js(f"{SCROLLER}.scrollHeight"), p.js(f"{SCROLLER}.clientHeight"), "and there is more than fits")

    def test_edit_with_a_count_kept_has_no_show_all_and_is_n_rows_high(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.set_local(p, n=4, scroll=False)
                self.assertIsNone(p.js(BUTTON), "once a number is set View shows only the first 4 and has no Show all (1234, 16-11 ruling)")
                self.edit(p)
                self.assertIsNone(p.js(BUTTON), "Edit scrolls, so there is no Show all")
                self.assertIn("* 4)", p.js(f"{SCROLLER}.style.maxHeight"))
                self.assertEqual(p.js(ROWS), self.total)


class PutOnThePage(Demo):
    def click(self, p, selector):
        p.js(f"document.querySelector({json.dumps(selector)}).scrollIntoView({{block: 'center'}})")
        x, y, _ = p.box(selector)
        p.mouse("mouseMoved", x, y)
        p.mouse("mousePressed", x, y, 1)
        p.mouse("mouseReleased", x, y)

    def open_add(self, p):
        """Row 1234: the dashboard has no Add tile; the box opens from the Use cases page's + (#ucAddPage)."""
        p.js("location.hash = '#usecases&p=ABC'")
        p.until("!!document.querySelector('#ucAddPage')", "the Use cases page")
        self.click(p, "#ucAddPage")

    def back_to_dashboard(self, p):
        p.js("location.hash = '#dashboard&p=ABC'")
        p.until("!!document.querySelector('.glance')", "the dashboard")

    def type_in(self, p, selector, text):
        p.js(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); e.focus(); e.select(); }})()")
        p.cdp.call("Input.insertText", {"text": text}, p.sid)

    def test_a_use_case_put_on_the_page_opens_its_row(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.edit(p)
                self.open_add(p)
                p.until("!!document.querySelector('#ucF')", "the box")
                ref = f"9.{width}"
                self.type_in(p, "#ucI", ref)
                self.type_in(p, "#ucT", f"Late {ref}")
                p.js("document.querySelector('#ucF').requestSubmit()")
                p.until("!document.querySelector('#ucF')", "the box closed")
                p.until("(document.querySelector('.toast-text') || {}).textContent.indexOf('added, hidden') > 0", "the added toast")
                made = {r["ref"]: r for r in self.store.read("use_cases", "ABC")}[ref]
                self.back_to_dashboard(p)
                p.js("document.querySelector('[data-mode=edit]').click()")
                p.until("!!document.querySelector('[data-uc-configure]')", "Edit again")
                p.js("document.querySelector('[data-uc-back]').click()")
                p.until("!!document.querySelector('form.picker')", "the picker")
                p.js("document.querySelector('form.picker tbody input[value=\"%s\"]').click()" % made["id"])
                p.js("document.querySelector('form.picker button[type=submit]').click()")
                p.until("!document.querySelector('form.picker')", "the picker closed")
                row = f"document.querySelector('.ucrow[data-uc=\"{made['id']}\"]')"
                p.until(f"!!{row}", "the new row is drawn")
                p.until(f"{row}.classList.contains('open') && !!{row}.querySelector('.ucdetail')", "its row opened")


if __name__ == "__main__":
    unittest.main()
