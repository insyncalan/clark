"""Row 1152: on the editor Dashboard the section tiles are as wide as the report header, and a tile heading is 19 px (18 px in Compact).

Run: python3 dev/run_tests.py test_dash_tiles_header
1400 and 900 px, in View and in Edit. The header band and each tile are measured in the real page.
"""
import unittest

from _publish import PublishedFile
from test_glance_page import Setup
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

EDGES = "(r => [Math.round(r.left), Math.round(r.right)])"


class TileWidth(Setup):
    def test_tiles_line_up_with_the_header_and_the_heading_is_19px(self):
        for width in (1400, 900):
            for edit in (False, True):
                with self.subTest(width=width, edit=edit), chrome() as cdp:
                    p = self.show(cdp, width)
                    if edit:
                        p.edit()
                        p.until("!!document.querySelector('#report-hint')", "Edit drew")
                    band = p.js(EDGES + "(document.querySelector('#report').getBoundingClientRect())")      # item 1177: the banner is gone; the report frame it sat in is the edge
                    tiles = p.js("[...document.querySelectorAll('.sec.slot-full')].map(e => (r => [Math.round(r.left), Math.round(r.right)])(e.getBoundingClientRect()))")
                    self.assertTrue(tiles, "tiles drew")
                    for t in tiles:
                        self.assertEqual(t, band, "a tile's edges are the header's edges")
                    self.assertEqual(p.js("getComputedStyle(document.querySelector('.sec-h')).fontSize"), "19px")

    def test_compact_heading_is_18px(self):
        with chrome() as cdp:
            p = self.show(cdp, 1400, standard=True)
            self.assertEqual(p.js("document.documentElement.dataset.density"), "compact")
            self.assertEqual(p.js("getComputedStyle(document.querySelector('.sec-h')).fontSize"), "18px")



class PublishedHeading(PublishedFile, Setup):
    def test_published_page_heading_stays_24px(self):
        path = self.publish()
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.draw(cdp, path, width)
                self.assertEqual(p.js("getComputedStyle(document.querySelector('.sec-h')).fontSize"), "24px")


if __name__ == "__main__":
    unittest.main()
