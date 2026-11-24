"""Row 1290: the "Search: ..." chip (the plain words) on a published file's Work items tab is grey (class "fchip word") in Classic only.
Cards is frozen: its chip keeps class "fchip" and the same computed look as a field chip. Real page run (a published file in headless Chrome),
1400 and 900 px. Fictional data.
Run: CLARK_CHROME=/usr/local/bin/creaite-chrome python3 dev/run_tests.py test_filter_chip_word_classic_1290.py"""
import tempfile
import unittest
from pathlib import Path

import _publish_fixture as fx
import test_publish_uc_list_1114 as pub
from clark import page, publish
from test_publish import EMPTY_BRANDING, opened
from test_server import chrome, wait

LOOK = """(() => { const f = (e) => { const c = getComputedStyle(e); return { cls: e.className, bg: c.backgroundColor, fg: c.color }; };
  const d = document.createElement('i'); d.style.background = 'var(--grey-100)'; document.body.appendChild(d); const grey = getComputedStyle(d).backgroundColor; d.remove();
  const w = document.querySelector('#work .factive [data-chip="search"]'), o = document.createElement('span'); o.className = 'fchip'; w.parentNode.appendChild(o);   // a plain chip, as every other filter chip is drawn
  const field = f(o); o.remove();
  return { word: w && f(w), field, grey, wide: document.documentElement.scrollWidth <= window.innerWidth }; })()"""


class WordChip(unittest.TestCase):
    def look(self, classic, width):
        plant = fx.load()
        p = publish.select(fx.inputs(plant))
        text = publish.render(p, page.page_html(EMPTY_BRANDING, view=True, theme=pub.THEME if classic else None), plant["as_at"], p["data"]["project"]["name"])
        with tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
            path = Path(tmp) / "w.html"
            path.write_text(text, encoding="utf-8")
            sid = opened(cdp, path.as_uri())
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"))
            self.assertEqual(cdp.js("!!document.getElementById('theme')", sid), classic)
            cdp.js("document.querySelector('[data-view=work]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#q')", sid)), "the Work items tab drew its search box")
            cdp.js("(q => { q.focus(); q.value = 'the'; q.dispatchEvent(new Event('input', { bubbles: true })); })(document.querySelector('#q'))", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#work [data-chip=search]')", sid)), "the Search chip drew")
            return cdp.js(LOOK, sid)

    def test_classic_word_chip_has_the_word_class_and_the_grey_rule_applies_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                g = self.look(True, width)
                self.assertEqual(g["word"]["cls"], "fchip word", g)
                self.assertEqual(g["word"]["bg"], g["grey"], g)
                self.assertTrue(g["wide"], g)

    def test_cards_word_chip_is_unchanged_no_word_class_not_grey_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                g = self.look(False, width)
                self.assertEqual(g["word"]["cls"], "fchip", g)
                self.assertNotEqual(g["word"]["bg"], g["grey"], g)
                self.assertEqual((g["word"]["bg"], g["word"]["fg"]), (g["field"]["bg"], g["field"]["fg"]), g)


if __name__ == "__main__":
    unittest.main()
