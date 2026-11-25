"""Row 1194 AP13 (slice D): a new report starts with Documents and links; a saved report keeps its Supporting documents section.

Run: python3 dev/run_tests.py test_default_sections_1194
"""
import unittest

from _demo import DemoStore, USER
from clark import changes, default_sections, order


class DefaultSections1194(unittest.TestCase):
    def test_a_new_report_starts_with_documents_and_links_and_a_saved_one_keeps_its_old_section(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        s = demo.store
        new = order.in_order(s.read("report_sections", "ABC"))               # a new project's seeded sections
        self.assertIn(("doclinks", "Documents and links"), [(r["type"], r["title"]) for r in new])
        self.assertNotIn("docs", [r["type"] for r in new])
        self.assertNotIn("Supporting documents", [r["title"] for r in new])
        self.assertEqual([(e["type"], e["title"]) for e in default_sections.DEFAULT_SECTIONS][-1], ("doclinks", "Documents and links"))
        # a saved report with the old section: it is still a known type, loads, edits and reads back unchanged (no conversion, no migration)
        with s.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": "docs", "title": "Supporting documents", "sort_order": order.end_slot(new)})
        with s.step("dashboard", USER) as st:
            st.update("report_sections", ref, {"title": "Our documents"})
        saved = [r for r in s.read("report_sections", "ABC") if r["type"] == "docs"]
        self.assertEqual([(r["type"], r["title"]) for r in saved], [("docs", "Our documents")])
        self.assertEqual(changes.BUILT_IN_TITLES["docs"], "Supporting documents", "the old section stays re-addable for saved reports")


if __name__ == "__main__":
    unittest.main()
