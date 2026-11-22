"""Row 1285 ruling in the Classic Theme, on the REAL Settings page at 1400 and 900 px, light and dark: the group captions are not drawn (a flat list)
and one thin divider sits between every pair of the five groups; Cards keeps its captions. Run: python3 dev/run_tests.py test_settings_flat_1285"""
import unittest

from test_server import chrome
import test_theme_classic_1317 as t

PROBE = """(() => { const vis = (e) => { const r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 2 && r.height > 2 && s.visibility !== 'hidden'; };
  const names = [...document.querySelectorAll('.set-group-name')];
  const lines = [...document.querySelectorAll('.set-nav > .set-group')].map(g => getComputedStyle(g).borderTopWidth).filter(w => w !== '0px');
  const gs = [...document.querySelectorAll('.set-nav > .set-group')].filter(g => getComputedStyle(g).borderTopWidth !== '0px');
  const clear = (c) => c === 'transparent' || /rgba\\(.*,\\s*0\\)$/.test(c);
  const bgOf = (e) => { for (; e; e = e.parentElement) { const c = getComputedStyle(e).backgroundColor; if (!clear(c)) return c; } return 'transparent'; };
  return {n: names.length, drawn: names.filter(vis).length, lines: lines, text: names.map(e => e.textContent),
    colours: gs.map(g => getComputedStyle(g).borderTopColor), bgs: gs.map(bgOf)}; })()"""


class Flat(unittest.TestCase):
    setUpClass = classmethod(t.RealSettings.setUpClass.__func__)
    tearDownClass = classmethod(t.RealSettings.tearDownClass.__func__)
    serve, look = t.RealSettings.serve, t.RealSettings.look

    def got(self, theme, width, scheme):
        s = self.serve(theme)
        with chrome() as cdp:
            self.look(cdp, s.port, width, scheme)
            return cdp.js(PROBE, t.page_target(cdp))

    def test_classic_draws_no_caption_and_one_divider(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme):
                    g = self.got(t.NAME, width, scheme)
                    self.assertEqual(g["n"], 5, "the captions stay in the page for a screen reader")
                    self.assertEqual(g["drawn"], 0, g)
                    self.assertEqual(g["lines"], ["1px"] * 4, "one thin divider between every pair of the five groups")
                    if scheme == "dark":
                        for c, bg in zip(g["colours"], g["bgs"]):
                            self.assertNotIn(c, ("transparent", "rgba(0, 0, 0, 0)"), "the divider colour is visible in dark")
                            self.assertNotEqual(c, bg, "the divider differs from the page background in dark")

    def test_cards_keeps_its_captions(self):
        g = self.got(None, 1400, "light")
        self.assertEqual(g["drawn"], 5)
