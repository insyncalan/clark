"""PR 1856, sweep of the docx_build glancetemplate lines: the health bar is drawn the full text width.

Run: python3 dev/run_tests.py test_glance_docx_1856_sweep
"""
import re
import unittest

from _paths import ROOT   # noqa: F401

from clark import docx_build
from test_glance_word_excel_1264_sweep import body, doc_xml, select


class HealthBarWidth(unittest.TestCase):
    def test_the_own_row_health_bar_is_the_text_width(self):
        xml = doc_xml(select(body(order=["health"], health={"own_row": True})))
        part = xml[xml.index("Project health: "):]
        extents = re.findall(r'<wp:extent cx="(\d+)"', part)
        self.assertTrue(extents)
        self.assertEqual(int(extents[0]), docx_build.TEXT_W * docx_build.EMU_PER_TWIP)


if __name__ == "__main__":
    unittest.main()
