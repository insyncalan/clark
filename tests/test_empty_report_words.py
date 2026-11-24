"""The words a report page gives when it has no section to draw: in a published file that has sections which are all left out, it
says there is nothing to show yet (not that there are no sections).

Run: python3 dev/run_tests.py test_empty_report_words
The finished file is opened from file:// in headless Chrome at 1400 and 900 px. Fictional data.
"""
import unittest

from _demo import USER
from _publish import PublishedFile
import test_glance_page as glance
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome


class Empty(PublishedFile, glance.Setup):
    def test_a_file_whose_sections_all_draw_nothing_says_there_is_nothing_to_show_yet(self):
        with self.store.step("dashboard", USER) as st:
            for r in self.store.read("report_sections", project="ABC"):
                if r["type"] == "text":
                    st.update("report_sections", r["id"], {"body": ""})      # a section with no words: the file leaves it out
                else:
                    st.update("report_sections", r["id"], {"hidden": 1})
        path = self.publish()
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.draw(cdp, path, width)
                self.assertEqual(p.js("document.querySelector('#no-sections').textContent"), "This report has nothing to show yet.")
                self.assertEqual(p.js("document.querySelectorAll('.sec').length"), 0)


if __name__ == "__main__":
    unittest.main()
