"""Row 1223 (ticket test 13): the Image at HALF width, in a real browser on the same bare page as test_tpl_imagecap_full_page. A half width
section is the content width less the gap, over two (about 640 px at a 1400 px page); at 900 px a pair stacks, so the Image is full width
(800 px here). Edit: the image fills the section, the toolbar wraps without clipping or sideways scroll, the height handle works. View: the
image fills the section, a small one is centred, no tools. Pins what the page does; the half width is the page's section pair, not new code.

Run: python3 dev/run_tests.py test_tpl_imagecap_half_1223
Needs Chrome (the harness): fails, never skips, without it. Fictional data only."""
import unittest

import test_tpl_imagecap_full_page as base

HALF = 640
SHARED = ("setUpClass", "tearDownClass", "val", "until", "setup_page", "mount", "calls", "body", "add", "settled", "click", "height", "mouse", "drag", "press", "key", "framed")


class Half(unittest.TestCase):
    pass


for _name in SHARED:
    if _name in base.Page.__dict__:
        setattr(Half, _name, base.Page.__dict__[_name])

class HalfWidth(Half):
    WIDTHS = ((1400, HALF), (900, 800))        # (page, the section's width): half at 1400, stacked (full) at 900

    def test_edit_fills_the_section_and_the_toolbar_fits_at_1400_and_900(self):
        for page, width in self.WIDTHS:
            for theme in ("light", "dark"):
                self.mount(None, "edit", width, page, theme)
                self.val("drop(2400, 1200, 'bands')", True)
                self.until("document.querySelector('.fi-stage')", "the stage")
                self.until("document.querySelector('.fi-pic').complete", "loaded")
                m = self.val("""(function(){const s = document.querySelector('.fi-stage').getBoundingClientRect(), b = document.querySelector('.fi-bar').getBoundingClientRect();
                  const out = [...document.querySelectorAll('.fi-bar button, .fi-bar [role=radio]')].filter(e => { const r = e.getBoundingClientRect(); return r.width && (r.left < s.left - 1 || r.right > s.right + 1); }).length;
                  return {fits: document.documentElement.scrollWidth <= window.innerWidth, stage: s.width, bar: b.left >= s.left - 1 && b.right <= s.right + 1, out, tools: document.querySelectorAll('.fi-bar button, .fi-bar [role=radio]').length};})()""")
                self.assertTrue(m["fits"] and m["bar"], (page, theme, m))
                self.assertEqual(m["out"], 0, ("a tool is clipped", page, theme, m))
                self.assertGreater(m["tools"], 5)
                self.assertAlmostEqual(m["stage"], width, delta=2)

    def test_the_height_handle_works_at_half_width(self):
        self.mount(None, "edit", HALF, 1400)
        self.val("drop(2400, 1200, 'bands')", True)
        self.until("document.querySelector('[data-height-handle]')", "the handle")
        self.until("document.querySelector('.fi-pic').complete", "loaded")
        self.settled(1)
        h = self.height()
        self.drag("[data-height-handle]", 0, 0, move=False)
        self.assertAlmostEqual(self.height(), h, delta=1, msg="picked up without moving: the height does not change")
        self.drag("[data-height-handle]", 0, 40)
        self.until(f"Math.abs(document.querySelector('.fi-stage').getBoundingClientRect().height - {h + 40}) < 2", "40 px taller")
        self.assertAlmostEqual(self.val("document.querySelector('.fi-stage').getBoundingClientRect().width"), HALF, delta=2)

    def test_view_fills_the_section_and_a_small_image_is_centred_at_1400_and_900(self):
        big, small = self.framed(2000, 800), self.framed(300, 200)
        for page, width in self.WIDTHS:
            for theme in ("light", "dark"):
                self.mount({"v": 2, "pictures": {"image": big}, "caption": "Fictional"}, "view", width, page, theme)
                self.until("document.querySelector('.tpl-fullimg-img').complete", "loaded")
                m = self.val("(function(){const i = document.querySelector('.tpl-fullimg-img').getBoundingClientRect(); return {fits: document.documentElement.scrollWidth <= window.innerWidth, img: i.width, tools: document.querySelectorAll('button, input, [role=slider], [role=toolbar], textarea').length};})()")
                self.assertTrue(m["fits"], (page, theme))
                self.assertAlmostEqual(m["img"], width, delta=1)
                self.assertEqual(m["tools"], 0)
                self.mount({"v": 2, "pictures": {"image": small}}, "view", width, page, theme)
                self.until("document.querySelector('.tpl-fullimg-img').complete", "loaded")
                m = self.val("(function(){const s = document.querySelector('.tpl-fullimg-frame').getBoundingClientRect(), i = document.querySelector('.tpl-fullimg-img').getBoundingClientRect(); return {img: i.width, l: i.left - s.left, r: s.right - i.right, fits: document.documentElement.scrollWidth <= window.innerWidth};})()")
                self.assertTrue(m["fits"])
                self.assertAlmostEqual(m["img"], 300, delta=1)
                self.assertAlmostEqual(m["l"], m["r"], delta=1)


if __name__ == "__main__":
    unittest.main()
