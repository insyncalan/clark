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
from test_server import chrome

VIA, DIRECT = "TUL-M-005", "TUL-M-002"          # demo: the work items reach TUL-M-005; TUL-M-002 is linked straight and also TUL-M-005


class Card(base.Detail):
    def link(self, *milestones):
        st = open_store(self.path, onedrive_roots=[])
        try:
            with st.step("dashboard", USER):
                for m in milestones:
                    sm.link_use_case_milestone(st.con, base.UC, m, USER)
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

    def test_without_a_direct_link_the_old_milestone_says_through_work_items_and_only_it_can_be_removed(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_detail(cdp, width, "light", edit=True)
                self.assertEqual(self.how(cdp, sid), {VIA: ["work", "Through work items"]})
                self.assertEqual(cdp.js("document.querySelectorAll('[data-ucd] [data-ms] [data-ms-remove]').length", sid), 1)

    def test_a_direct_only_milestone_has_no_remove_because_no_work_item_names_it(self):
        self.link(DIRECT)
        with chrome() as cdp:
            sid = self.open_detail(cdp, 1400, "light", edit=True)
            self.assertEqual(self.how(cdp, sid)[DIRECT], ["direct", "Linked directly"])
            self.assertEqual(cdp.js(f"document.querySelectorAll('[data-ucd] [data-ms={DIRECT}] [data-ms-remove]').length", sid), 0)


for _name in dir(base.Detail):          # the base page tests run in test_use_case_detail; only this file's own run here
    if _name.startswith("test_") and _name not in Card.__dict__:
        setattr(Card, _name, None)

if __name__ == "__main__":
    unittest.main()
