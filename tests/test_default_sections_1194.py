"""Row 1194: a saved report keeps its Supporting documents section, and the section can be renamed and reads back unchanged.

The other half of the old AP13 test (a new report starts with Documents and links) is pinned on main by row 1266, see tests/test_default_sections_1266.py.
Run: python3 dev/run_tests.py test_default_sections_1194
"""
import unittest

from _demo import DemoStore, USER
from clark import changes, order


class SavedDocsSection1194(unittest.TestCase):
    def test_a_saved_docs_section_renamed_reads_back_unchanged_and_the_old_title_stays_re_addable(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        s = demo.store
        existing = order.in_order(s.read("report_sections", "ABC"))
        # a saved report with the old section: it is still a known type, loads, edits and reads back unchanged (no conversion, no migration)
        with s.step("dashboard", USER) as st:
            st.create("report_sections", {"project": "ABC", "type": "docs", "title": "Supporting documents", "sort_order": order.end_slot(existing)})
        self.assertEqual([(r["type"], r["title"]) for r in s.read("report_sections", "ABC") if r["type"] == "docs"], [("docs", "Supporting documents")])
        ref = next(r["id"] for r in s.read("report_sections", "ABC") if r["type"] == "docs")
        with s.step("dashboard", USER) as st:
            st.update("report_sections", ref, {"title": "Our documents"})
        saved = [r for r in s.read("report_sections", "ABC") if r["type"] == "docs"]
        self.assertEqual([(r["type"], r["title"]) for r in saved], [("docs", "Our documents")])
        self.assertEqual(changes.BUILT_IN_TITLES["docs"], "Supporting documents", "the old section stays re-addable for saved reports")


if __name__ == "__main__":
    unittest.main()
