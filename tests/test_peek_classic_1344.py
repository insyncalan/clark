"""Row 1344 (v1.3): the peek in the Classic Theme draws its left edge, its shadow and its entry as the approved peek mock-up does
(1 px edge rgb(205, 211, 224), shadow -10px 0 30px at .14, a 0.5 s slide that fades in and is opaque by 60 %). Measured in Chrome on the real page
at 1400 and 900 px, light and dark; Cards is the control and keeps its own edge, shadow and pure slide.

Run: python3 dev/run_tests.py test_peek_classic_1344
Fails, never skips, without Chrome. Dark keeps the Theme's own tokens (the dark look is a later audit)."""
import json
import shutil
import tempfile
import unittest

from _editor_checks import for_url

from clark import page
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

NAME = "prototype-2.0"
PROBE = """(() => {
  const p = document.querySelector('#peek'), cs = getComputedStyle(p), a = p.getAnimations().find(x => x.animationName);
  const at = (ms) => { if (!a) return null; a.pause(); a.currentTime = ms; const s = getComputedStyle(p); return {op: s.opacity, left: Math.round(p.getBoundingClientRect().left)}; };
  const k = a ? a.effect.getKeyframes() : [], t = a ? a.effect.getComputedTiming() : {};
  const out = {iter: t.iterations, edge: cs.borderLeftColor, edgeW: cs.borderLeftWidth, shadow: cs.boxShadow, name: a ? a.animationName : null, dur: t.duration,
    ease: k.length ? k[0].easing : null, fromOpacity: k.length && k[0].opacity !== undefined ? String(k[0].opacity) : 'none',
    start: at(0), mid: at(150), sixty: at(300), end: at(500), win: document.documentElement.clientWidth,
    grey200: (() => { const i = document.createElement('i'); i.style.color = 'var(--grey-200)'; document.body.appendChild(i); const c = getComputedStyle(i).color; i.remove(); return c; })(),
    token: (() => { const i = document.createElement('i'); i.style.boxShadow = 'var(--shadow)'; document.body.appendChild(i); const c = getComputedStyle(i).boxShadow; i.remove(); return c; })()};
  return out; })()"""
MOCKUP_SHADOW = "rgba(19, 35, 42, 0.14) -10px 0px 30px 0px"


class ClassicPeek(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()
        cls.names = {p["code"]: p["name"] for p in cls.store.read("projects")}
        cls.data = {c: cls.store.data_for(c) for c in cls.names}

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def serve(self, theme):
        s = Running(data_for=lambda code, **kw: self.data.get(code), projects=lambda archived=False: [{"code": c, "name": n} for c, n in sorted(self.names.items())],
                    page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=theme))
        self.addCleanup(s.close)
        return s

    def measure(self, theme, width, scheme, reduced=False, attr=None, leaving=False):
        s = self.serve(theme)
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme},
                                                                 {"name": "prefers-reduced-motion", "value": "reduce" if reduced else "no-preference"}]}, sid)
            cdp.call("Page.navigate", {"url": "about:blank"}, sid)
            cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{s.port}/#work&p=TUL")}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length > 0", sid), 30), "timed out waiting for the Work items list")
            item = cdp.js("document.querySelector('#work tbody tr[data-id]').dataset.id", sid)
            cdp.js("location.hash = '#work&p=TUL&item=' + " + json.dumps(item), sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek')", sid), 30), "the peek opened")
            if attr:
                cdp.js("document.documentElement.dataset.theme = " + json.dumps(attr), sid)
            if leaving:
                return cdp.js("(() => { const p = document.querySelector('#peek'); p.classList.add('leaving'); return getComputedStyle(p).animationName; })()", sid)
            return cdp.js(PROBE, sid)

    def each(self, theme, scheme):
        for width in (1400, 900):
            yield f"{theme or 'cards'} {scheme} {width}", self.measure(theme, width, scheme)

    def test_light_edge_shadow_and_a_fading_slide_as_the_mockup(self):
        for tag, c in self.each(NAME, "light"):
            self.assertEqual((c["edge"], c["edgeW"]), ("rgb(205, 211, 224)", "1px"), tag)
            self.assertEqual(c["shadow"], MOCKUP_SHADOW, tag)
            self.assertEqual((c["name"], c["dur"]), ("pk-in-fade", 500), tag)
            self.assertEqual(c["ease"].replace(" ", ""), "cubic-bezier(0.22,1,0.36,1)", tag)
            self.assertEqual(c["fromOpacity"], "0", tag + ": it fades in")
            self.assertEqual(c["start"], {"op": "0", "left": c["win"]}, tag + ": invisible and beyond the right edge at the start")
            self.assertTrue(0 < float(c["mid"]["op"]) < 1, tag + f": part way at 150 ms ({c['mid']['op']})")
            self.assertEqual(c["sixty"]["op"], "1", tag + ": opaque at 60 % (300 ms)")
            self.assertEqual(c["end"]["op"], "1", tag)
            self.assertEqual(c["iter"], 1, tag + ": it runs once")
            self.assertLess(c["end"]["left"], c["win"], tag + ": on screen once the slide has ended")

    def test_dark_keeps_the_themes_own_edge_and_shadow(self):
        for tag, c in self.each(NAME, "dark"):
            self.assertEqual((c["edge"], c["shadow"]), (c["grey200"], c["token"]), tag + ": dark edge and shadow are the Theme's tokens, not the mock-up's light ones")
            self.assertNotEqual(c["shadow"], MOCKUP_SHADOW, tag)
            self.assertEqual(c["name"], "pk-in-fade", tag + ": the fade is in dark too")

    def test_dark_set_by_the_switch_keeps_the_themes_own_edge_and_shadow(self):
        for width in (1400, 900):
            c = self.measure(NAME, width, "light", attr="dark")
            self.assertEqual((c["edge"], c["shadow"]), (c["grey200"], c["token"]), f"data-theme=dark {width}")
            self.assertNotEqual(c["shadow"], MOCKUP_SHADOW, width)

    def test_the_exit_keeps_its_own_slide_out(self):
        for width in (1400, 900):
            self.assertEqual(self.measure(NAME, width, "light", leaving=True), "pk-out", f"{width}: a closing peek slides out, it does not play the entry")

    def test_reduced_motion_keeps_the_short_fade_with_no_travel(self):
        for width in (1400, 900):
            c = self.measure(NAME, width, "light", reduced=True)
            self.assertEqual(c["name"], "pk-fade", width)
            self.assertLess(c["dur"], 500, width)

    def test_cards_keeps_its_own_edge_shadow_and_pure_slide(self):
        for scheme in ("light", "dark"):
            for tag, c in self.each(None, scheme):
                self.assertEqual((c["edge"], c["shadow"]), (c["grey200"], c["token"]), tag)
                self.assertNotEqual(c["shadow"], MOCKUP_SHADOW, tag)
                self.assertEqual((c["name"], c["dur"], c["fromOpacity"]), ("pk-in", 500, "none"), tag + ": a slide with no fade")


if __name__ == "__main__":
    unittest.main()
