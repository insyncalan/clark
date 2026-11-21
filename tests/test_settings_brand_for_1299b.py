"""Row 1299 line 16: the Brand page shows the group heading "Brand for <code>" over the project's brand row (Classic only), in a real browser at 1400 and 900 px,
light and dark. Run: python3 dev/run_tests.py test_settings_brand_for_1299b

What is asserted: the heading reads "Brand for PUB", is a heading, sits above the brand select and is in the heading colour; the existing label "Brand for this project"
is still there; with the Cards look (no theme layer) the heading is not drawn. Chrome is required: these tests fail, never skip, without it.
"""
import unittest

from clark import page, theme
import _testpage as testpage
from test_publish_dialog import Base
from test_publish_route import Rig
from test_server import chrome
from test_settings_bar import calm
from test_settings_head import address

WIDTHS = (1400, 900)
MODES = ("light", "dark")


class BrandFor(Base):
    classic = True

    def setUp(self):
        css = theme.css("prototype-2.0")
        layer = (lambda: page.layer_theme(testpage.html(), css)) if self.classic else testpage.html
        self.rig = Rig(self, saved=self.saved, page_html=layer)

    def test_B_the_heading_is_over_the_brand_row(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    p.width(w)
                    calm(p, mode)
                    p.js("(() => { const f = window.fetch; window.fetch = (u, o) => String(u).includes('/api/brands') ? Promise.resolve(new Response(JSON.stringify({ok: true, brands: [{id: 'generic', name: 'Generic', version: '1', own: false}], undo: false}),"
                         " {status: 200, headers: {'Content-Type': 'application/json'}})) : f(u, o); })()")      # the brand list is the page's own seam: the rig has no brand store
                    p.js(f"location.hash = '{address('brand')}'")
                    p.until("!!document.querySelector('#brands-h')", "the Brand card drew")
                    p.until("!!document.querySelector('#brand-pick') || !document.querySelector('#brands .muted')", "the brand row drew: ")
                    if not self.classic:
                        self.assertFalse(p.js("!!document.querySelector('.brand-for')"), "Cards draws no heading")
                        return
                    self.assertEqual(p.js("document.querySelector('.brand-for').textContent"), "Brand for PUB")
                    self.assertEqual(p.js("document.querySelector('.brand-for').tagName"), "H3")
                    self.assertTrue(p.js("document.querySelector('.brand-for').getBoundingClientRect().bottom <= document.querySelector('#brand-pick').getBoundingClientRect().top"), "above the select")
                    self.assertIn("Brand for this project", p.js("document.querySelector('[data-brand-pick] label').textContent"))
                    self.assertGreaterEqual(p.js("parseFloat(getComputedStyle(document.querySelector('.brand-for')).fontWeight)"), 600)


class BrandForCards(BrandFor):
    classic = False


if __name__ == "__main__":
    unittest.main()
