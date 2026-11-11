"""Empty states that must not say something untrue: the Use cases link box and the Work items list (live and published).

Run: python3 dev/run_tests.py test_empty_words
The link box says "Every open work item is linked to this use case already." only when there are open items and all are linked; with
no open items it says "There are no open work items to link." The Work items page already says "This project has no work items yet." for a project with no items (the filter words are never reached
then); the list keeps its filter words when items exist but none match. Widths 1400 and 900 only.
"""
import unittest

from test_glance_page import Setup, tearDownModule  # noqa: F401
from test_server import chrome

ALL_LINKED = "Every open work item is linked to this use case already."
NONE_OPEN = "There are no open work items to link."
NO_ITEMS_PAGE = "This project has no work items yet."


class LinkBox(Setup):
    def box(self, cdp, width):
        p = self.show(cdp, width)
        p.js("document.querySelector('[data-mode=edit]').click()")
        p.until("!!document.querySelector('.uc [data-uc-status]')", "Edit")
        p.js("document.querySelector('.ucrow .ucref').scrollIntoView({block: 'center'})")
        p.js("document.querySelector('.ucrow .ucref').click()")
        p.until("!!document.querySelector('.ucdetail [data-uc-link]')", "the row opened")
        p.js("document.querySelector('[data-uc-link]').click()")
        p.until("!!document.querySelector('form.uclink')", "the box")
        return p

    def none_text(self, p):
        return p.js("(document.querySelector('form.uclink [data-none]') || {}).textContent")

    def test_no_open_work_items_says_there_are_none_to_link(self):
        self.store.con.execute("UPDATE actions SET status = 'Closed'")
        self.store.con.execute("UPDATE raid SET status = 'Closed'")
        self.store.con.execute("UPDATE decisions SET status = 'Made', date = '2026-10-01'")
        self.store.con.commit()
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.box(cdp, width)
                self.assertEqual(self.none_text(p), NONE_OPEN)

    def test_all_open_work_items_linked_keeps_the_linked_words(self):
        uc = self.store.con.execute("SELECT id FROM use_cases WHERE ref = '1.1'").fetchone()[0]
        for table in ("actions", "raid", "decisions"):
            self.store.con.execute(f"UPDATE {table} SET use_case = ?", (uc,))
        self.store.con.commit()
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.box(cdp, width)
                self.assertEqual(self.none_text(p), ALL_LINKED)

    def test_typed_words_that_match_nothing_still_say_nothing_matches(self):
        with chrome() as cdp:
            p = self.box(cdp, 1400)
            p.cdp.call("Input.insertText", {"text": "zzqqxx"}, p.sid)
            p.until("!!document.querySelector('form.uclink [data-none]')", "the empty line")
            self.assertEqual(self.none_text(p), "Nothing matches.")


class WorkList(Setup):
    def work(self, cdp, width, until):
        p = self.show(cdp, width, hash_="#work&p=ABC", settings=True)
        p.until(until, "the Work items page drew")
        return p

    def test_a_project_with_no_items_says_so_and_never_says_nothing_matches(self):
        for table in ("actions", "raid", "decisions"):
            self.store.con.execute(f"DELETE FROM {table}")
        self.store.con.commit()
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.work(cdp, width, "document.querySelector('#work') && document.querySelector('#work').innerText.includes('no work items')")
                text = p.js("document.querySelector('#work').innerText")
                self.assertIn(NO_ITEMS_PAGE, text)
                self.assertNotIn("match", text)
                self.assertEqual(p.js("document.querySelectorAll('#work-list .empty').length"), 0)

    def test_items_that_do_not_match_keep_the_filter_words(self):
        with chrome() as cdp:
            p = self.work(cdp, 1400, "!!document.querySelector('#work-list')")
            p.js("document.querySelector('#work input[type=search], #work input').focus()")
            p.cdp.call("Input.insertText", {"text": "zzqqxx"}, p.sid)
            p.until("!!document.querySelector('#work-list .empty p')", "the empty state")
            text = p.js("document.querySelector('#work-list .empty p').textContent")
            self.assertIn("match", text)
