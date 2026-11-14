"""Row 1107: the use case page's Milestones card shows the milestones a use case is linked to directly and the ones its work items
reach, and says which is which (src/clark/page/src/components/UseCaseDetail.jsx; the data is store.data_for's uc_milestones).
Browser parts at 1400 and 900 px, light and dark; they fail, never skip, without Chrome. Fictional data only.
Run: python3 dev/run_tests.py test_uc_milestones_page
"""
import unittest

import _paths  # noqa: F401
import test_use_case_detail as base
from _demo import USER
from clark import store as sm
from clark.store import open_store
from test_inline_edits import click
from test_server import chrome

VIA, DIRECT = "TUL-M-005", "TUL-M-002"          # demo: the work items reach TUL-M-005; TUL-M-002 is linked straight and also TUL-M-005


class Card(base.Detail):
    def link(self, *milestones):
        st = open_store(self.path, onedrive_roots=[])
        try:
            with st.step("dashboard", USER) as step:
                for m in milestones:
                    sm.link_use_case_milestone(step, base.UC, m)
        finally:
            st.close()

    def live(self):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return sm.use_case_milestone_ids(st.con, base.UC)
        finally:
            st.close()

    def how(self, cdp, sid):
        return cdp.js("Object.fromEntries([...document.querySelectorAll('[data-ucd] [data-ms]')].map(e => [e.dataset.ms, [e.dataset.how, e.querySelector('[data-ms-how]').textContent]]))", sid)

    def test_each_milestone_says_how_it_is_reached_at_both_widths_light_and_dark(self):
        self.link(DIRECT, VIA)
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = self.open_detail(cdp, width, scheme, edit=False)
                    self.assertEqual(self.how(cdp, sid), {DIRECT: ["direct", "Linked directly"], VIA: ["both", "Linked directly and through work items"]})
                    self.assertIn("Through work items means", cdp.js("document.querySelector('[data-ms-note]').textContent", sid))
                    self.assertEqual(cdp.js("document.querySelector('.ucd-sub').textContent.split(' · ').pop()", sid), "2 milestones")
                    self.assertTrue(cdp.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth", sid), "no sideways scroll")

    def test_without_a_direct_link_the_old_milestone_says_through_work_items_and_offers_no_removal(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_detail(cdp, width, "light", edit=True)
                self.assertEqual(self.how(cdp, sid), {VIA: ["work", "Through work items"]})
                self.assertEqual(cdp.js("document.querySelectorAll('[data-ucd] [data-ms] [data-ms-remove], [data-ucd] [data-ms] [data-ms-unlink]').length", sid), 0, "nothing is linked directly, so nothing to remove")

    def test_a_direct_only_milestone_has_unlink_and_unlink_and_link_are_one_step_with_one_undo(self):
        self.link(DIRECT)
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_detail(cdp, width, "light", edit=True)
                self.assertEqual(self.how(cdp, sid)[DIRECT], ["direct", "Linked directly"])
                self.assertEqual(cdp.js(f"document.querySelectorAll('[data-ucd] [data-ms={DIRECT}] [data-ms-remove]').length", sid), 0)
                before = self.steps()
                click(cdp, sid, f"[data-ucd] [data-ms={DIRECT}] [data-ms-unlink]")
                self.until(cdp, sid, f"!document.querySelector('[data-ucd] [data-ms={DIRECT}]')", "the milestone left the card")
                self.assertEqual(self.steps(), before + 1, "one step")
                self.assertEqual(self.live(), [])
                self.undo(cdp, sid)
                self.until(cdp, sid, f"!!document.querySelector('[data-ucd] [data-ms={DIRECT}]')", "Undo brought the link back")
                click(cdp, sid, f"[data-ucd] [data-ms={DIRECT}] [data-ms-unlink]")        # leave the file as it was for the next width
                self.until(cdp, sid, f"!document.querySelector('[data-ucd] [data-ms={DIRECT}]')", "gone again")
                click(cdp, sid, "[data-undo]")
                self.until(cdp, sid, f"!!document.querySelector('[data-ucd] [data-ms={DIRECT}]')", "and back")

    def test_a_milestone_that_is_both_has_unlink_only_and_the_peek_names_the_use_cases_linked_to_it(self):
        self.link(DIRECT, VIA)
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_detail(cdp, width, "light", edit=True)
                for ms, unlink, remove in ((DIRECT, 1, 0), (VIA, 1, 0)):
                    self.assertEqual(cdp.js(f"document.querySelectorAll('[data-ucd] [data-ms={ms}] [data-ms-unlink]').length", sid), unlink, ms)
                    self.assertEqual(cdp.js(f"document.querySelectorAll('[data-ucd] [data-ms={ms}] [data-ms-remove]').length", sid), remove, ms)
                click(cdp, sid, f"[data-ucd] [data-ms-open={DIRECT}]")
                self.until(cdp, sid, "!!document.querySelector('#peek [data-ms-ucs]')", "the milestone peek names its use cases")
                said = cdp.js("document.querySelector('#peek [data-ms-ucs]').textContent", sid)
                self.assertEqual(said, "1.1 Paper files scanned and indexed", "the use case linked straight to it, by reference and title")

    def test_add_a_milestone_menu_links_it_directly(self):
        with chrome() as cdp:
            sid = self.open_detail(cdp, 1400, "light", edit=True)
            self.assertEqual(cdp.js("document.querySelectorAll('[data-ucd] [data-ms-link]').length", sid), 1)
            click(cdp, sid, "[data-ucd] [data-ms-link] button")
            click(cdp, sid, f"[role=menu] [data-kind='{DIRECT}']")
            self.until(cdp, sid, f"!!document.querySelector('[data-ucd] [data-ms={DIRECT}]')", "the milestone is on the card")
            self.assertEqual(self.how(cdp, sid)[DIRECT], ["direct", "Linked directly"])


for _name in dir(base.Detail):          # the base page tests run in test_use_case_detail; only this file's own run here
    if _name.startswith("test_") and _name not in Card.__dict__:
        setattr(Card, _name, None)

if __name__ == "__main__":
    unittest.main()
