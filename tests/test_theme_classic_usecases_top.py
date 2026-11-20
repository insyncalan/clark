"""Item 1316a (Row 1316): the top of the Use cases page under the Classic Theme: Crumb, Tabs and menus, Search.

Run: python3 dev/run_tests.py test_theme_classic_usecases_top
Chrome required (fails, never skips). 1400 and 900 px, light and dark. Under Classic each element is read as computed; under Cards (no Theme)
the same element is read and must be what it was. The prototype files are not on the build box: sizes are by eye from the issue table.
The page words are untouched (nothing new is said); the hint line of the Search box is skipped as a new word.
"""
import tempfile
import unittest

from _demo import DemoStore
from clark import page
from test_published_work_no_add import open_page
from test_server import Running, chrome, wait
from test_work_filters import need_chrome

NAME = "prototype-2.0"
VARIANTS = [(w, s) for w in (1400, 900) for s in ("light", "dark")]
READ = """(() => { const g = (sel, pseudo) => { const e = document.querySelector(sel); return e ? getComputedStyle(e, pseudo || null) : null; };
  const o = {}; let s;
  s = g('#usecases #ucl-group'); o.group = s && [s.borderTopColor, s.backgroundColor, s.borderRadius];
  o.groupChev = !!document.querySelector('#ucl-group .nch') && getComputedStyle(document.querySelector('#ucl-group .nch')).display;
  o.sortChev = !!document.querySelector('#ucl-sort .nch') && getComputedStyle(document.querySelector('#ucl-sort .nch')).display;
  s = g('#ucl-sort'); o.sort = s && [s.borderTopColor, s.backgroundColor, s.borderRadius];
  o.menuChev = getComputedStyle(document.querySelector('#usecases .vtabmenu .nch')).display;
  o.menuDots = g('#usecases .vtabmenu', '::after').content;
  s = g('#ucAddPage'); o.plus = s && [s.borderTopStyle, s.borderTopColor, s.color]; o.plusRest = s && [s.borderTopColor, s.backgroundColor];
  const grey = document.createElement('i'); grey.style.color = 'var(--grey-500)'; document.body.appendChild(grey); o.grey500 = getComputedStyle(grey).color; grey.remove();
  const on = document.createElement('i'); on.style.color = 'var(--brand-blue)'; document.body.appendChild(on); o.brand = getComputedStyle(on).color; on.remove();
  for (const id of ['ucl-group', 'ucl-sort', 'ucAddPage']) { const e = document.getElementById(id); if (e) { e.style.transition = 'none'; e.setAttribute('aria-expanded', 'true'); } }
  s = g('#ucl-group'); o.groupOpen = s && [s.backgroundColor, s.color];
  s = g('#ucAddPage'); o.plusOpen = s && [s.borderTopColor, s.backgroundColor];
  const r = document.querySelector('#usecases .fline-row').getBoundingClientRect(); o.rowW = Math.round(r.width); o.boxW = Math.round(document.querySelector('#usecases .fline').getBoundingClientRect().width);
  o.mag = g('#usecases .fline', '::before').content; o.handle = g('#usecases .fline', '::after').content;
  s = g('#usecases .fline'); o.padL = s.paddingLeft;
  const c = document.querySelector('#usecases .fcount').getBoundingClientRect(); o.countBox = [Math.round(c.width), Math.round(c.height)];
  o.countText = document.querySelector('#usecases .fcount').textContent;
  const b = document.createElement('i'); b.style.color = 'var(--status-blue-text)'; document.body.appendChild(b); o.blue = getComputedStyle(b).color; b.remove();
  o.noScroll = document.documentElement.scrollWidth <= window.innerWidth;
  return o; })()"""
CRUMB = """(() => { const e = document.querySelector('.ucd-crumb'); if (!e) return null; const s = getComputedStyle(e); return [s.textTransform, s.letterSpacing, s.fontWeight, s.fontSize]; })()"""
LISTCRUMB = """(() => { const s = getComputedStyle(document.querySelector('#usecases .crumbs')); return [s.textTransform, s.letterSpacing, s.fontWeight, s.fontSize]; })()"""


class Top(unittest.TestCase):
    def setUp(self):
        need_chrome()
        demo = DemoStore()
        self.addCleanup(demo.close)
        self.demo = demo

    def read(self, theme, width, scheme):
        s = Running(data_for=self.demo.store.data_for, page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=theme))
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = open_page(cdp, f"http://127.0.0.1:{s.port}/#usecases&p=ABC", width, scheme)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#ucl-group') && !!document.querySelector('#usecases .vtabmenu')", sid)), "the page drew")
            got = cdp.js(READ, sid)
            got["listCrumb"] = cdp.js(LISTCRUMB, sid)
            cdp.js("document.querySelector('.ucl-go').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.ucd-crumb')", sid)), "the use case page drew")
            got["crumb"] = cdp.js(CRUMB, sid)
            return got

    def test_classic_draws_the_prototype_top(self):
        for w, scheme in VARIANTS:
            with self.subTest(width=w, scheme=scheme):
                g = self.read(NAME, w, scheme)
                self.assertEqual(g["crumb"][:3], ["none", "normal", "400"], "Crumb: normal case, no tracking")
                self.assertEqual(g["crumb"][3], "13px", "Crumb: 13 px")
                self.assertEqual(g["listCrumb"], ["none", "normal", "400", "13px"])
                for k in ("group", "sort"):
                    self.assertEqual(g[k][0], g["grey500"], k + ": the 1px --grey-500 border (Row 1316 controls, ruling 19-11; was borderless)")
                    self.assertEqual(g[k][1], "rgba(0, 0, 0, 0)", k + ": no fill")
                self.assertEqual((g["groupChev"], g["sortChev"], g["menuChev"]), (False, False, "none"), "no chevrons (row 1325, Classic only: Group by and Sort by are labelled buttons since Row 1316 follow-up)")
                self.assertEqual(g["menuDots"], '"…"', "the tab menu is the three dots")
                self.assertEqual(g["plus"][0], "dashed", "Row 1316 ruling 19-11: the Classic + is dashed")
                self.assertEqual(g["plus"][1], g["brand"], "the + border is brand coloured (Row 1316 controls, ruling 19-11; was grey)")
                self.assertNotEqual(g["groupOpen"][0], "rgba(0, 0, 0, 0)", "Group by open or hovered gets a fill")
                self.assertEqual(g["plusOpen"], g["plusRest"], "the + open or hovered keeps its rest look: no fill, still the brand border")
                self.assertNotEqual(g["plusOpen"][1], g["brand"], "no brand fill on the +")
                self.assertEqual(g["plus"][2], g["brand"], "and its + is brand coloured")
                self.assertEqual(g["boxW"], 560, "Search: 560 px box")
                self.assertEqual((g["mag"], g["handle"], g["padL"]), ('""', '""', "34px"), "Search: a magnifier")
                self.assertEqual(g["countBox"], [1, 1], "the count in the box is visually hidden")
                self.assertRegex(g["countText"], r"^\d+ of \d+$", "and still said")
                self.assertTrue(g["noScroll"])

    def test_cards_is_what_it_was(self):
        for w, scheme in VARIANTS:
            with self.subTest(width=w, scheme=scheme):
                g = self.read(None, w, scheme)
                self.assertEqual(g["crumb"][:3], ["uppercase", "1.3px", "700"], "Cards keeps the tracked capitals on the use case page")
                for k in ("group", "sort"):
                    self.assertEqual(g[k][2], "999px", k + ": the pill")
                    self.assertNotEqual(g[k][0], "rgba(0, 0, 0, 0)", k + ": its border")
                self.assertNotIn("none", (g["groupChev"], g["sortChev"], g["menuChev"]), "chevrons stay")
                self.assertEqual(g["menuDots"], "none")
                self.assertEqual(g["plus"][0], "dashed")
                self.assertEqual((g["plus"][1], g["plus"][2]), (g["blue"], g["blue"]), "Cards: the purple dashed +")
                self.assertGreater(g["rowW"], 560, "the full-width search box")
                self.assertEqual((g["mag"], g["padL"]), ("none", "10px"))
                self.assertGreater(g["countBox"][0], 1, "the count stays in the box")

    def test_cards_page_is_byte_for_byte_the_page_without_a_theme(self):
        d = tempfile.mkdtemp()
        base = page.page_html(d)
        self.assertEqual(page.page_html(d, theme=None), base)
        self.assertEqual(page.page_html(d, theme="not-a-theme"), base)
        classic = page.page_html(d, theme=NAME)
        self.assertNotEqual(classic, base)
        self.assertNotIn("min-width: 28px; padding: 0 8px; border: 1px dashed var(--brand-blue)", base)
        self.assertIn("min-width: 28px; padding: 0 8px; border: 1px dashed var(--brand-blue)", classic)


if __name__ == "__main__":
    unittest.main()
