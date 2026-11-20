"""Row 1289 (v1.3): the slide of a peek, measured in a real browser at 1400 and 900 px (test_peek_anchor_1289 only reads the stylesheet).
Run: python3 dev/run_tests.py test_peek_slide_1289
Opening an item peek must run the animation pk-in for 500 ms with cubic-bezier(.22,1,.36,1) from translateX(100%) to rest, with no fade;
the peek starts beyond the right edge and ends flush; under reduced motion it is the short fade pk-fade with no travel.
"""
import json
import unittest

import test_peek as tp  # noqa: E402
from test_server import chrome, wait  # noqa: E402

ANIM = """(() => {
  const p = document.querySelector('#peek'), a = p.getAnimations().find(x => x.animationName);
  if (!a) return null;
  const k = a.effect.getKeyframes(), t = a.effect.getComputedTiming();
  return {name: a.animationName, dur: t.duration, ease: k[0].easing,
          from: k[0].transform || 'none', fromOpacity: k[0].opacity === undefined ? 'none' : String(k[0].opacity),
          right: p.getBoundingClientRect().right, win: document.documentElement.clientWidth};
})()"""


class Slide(unittest.TestCase):
    setUpClass = tp.Browser.__dict__["setUpClass"]
    tearDownClass = tp.Browser.__dict__["tearDownClass"]
    load_page = tp.Browser.load_page
    ids_on_page = tp.Browser.ids_on_page

    def open_first(self, cdp, sid):
        item = self.ids_on_page(cdp, sid)[0]
        cdp.js("window.__t0 = 0; location.hash = '#work&p=" + self.code + "&item=" + item + "'", sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek') && document.querySelector('#peek').dataset.peek === " + json.dumps(item), sid)))

    def test_entry_is_the_half_second_slide_from_the_right_with_no_fade(self):
        for theme, width in ((t, w) for t in ("light", "dark") for w in (1400, 900)):
            with self.subTest(theme=theme, width=width), chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                cdp.js(f"document.documentElement.dataset.theme = '{theme}'", sid)
                self.open_first(cdp, sid)
                a = cdp.js(ANIM, sid)
                self.assertIsNotNone(a, f"{width}: the peek runs an animation on opening")
                self.assertEqual(a["name"], "pk-in", width)
                self.assertEqual(a["dur"], 500, width)
                self.assertEqual(a["ease"].replace(" ", ""), "cubic-bezier(0.22,1,0.36,1)", width)
                self.assertEqual(a["from"], "translateX(100%)", width)
                self.assertEqual(a["fromOpacity"], "none", f"{width}: a pure slide, no fade")
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek').getAnimations().length === 0", sid)), width)
                b = cdp.js("(() => { const p = document.querySelector('#peek'); return [p.getBoundingClientRect().right, document.documentElement.clientWidth]; })()", sid)
                self.assertEqual(round(b[0]), b[1], f"{width}: flush right once the slide has ended")

    def test_reduced_motion_is_a_short_fade_with_no_travel(self):
        for theme, width in ((t, w) for t in ("light", "dark") for w in (1400, 900)):
            with self.subTest(theme=theme, width=width), chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                cdp.js(f"document.documentElement.dataset.theme = '{theme}'", sid)
                cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, sid)
                self.open_first(cdp, sid)
                a = cdp.js(ANIM, sid)
                self.assertIsNotNone(a, f"{width}: a fade runs")
                self.assertEqual(a["name"], "pk-fade", width)
                self.assertLess(a["dur"], 500, width)
                self.assertEqual(a["from"], "none", f"{width}: no travel")
                self.assertEqual(round(a["right"]), a["win"], f"{width}: flush right from the first frame")


if __name__ == "__main__":
    unittest.main()
