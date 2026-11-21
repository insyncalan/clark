"""Item 1316a (Row 1316): killers for the Classic top of the Use cases page: text colours, the hover fills, the magnifier and its handle, the hidden count, the + hover.

Run: python3 dev/run_tests.py test_theme_classic_usecases_top_killers
Chrome required (fails, never skips). 1400 and 900 px, light and dark. No new words.
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
COLOUR = """((v) => { const i = document.createElement('i'); i.style.color = 'var(' + v + ')'; document.body.appendChild(i); const c = getComputedStyle(i).color; i.remove(); return c; })"""
STATE = """(() => { const q = (s, p) => getComputedStyle(document.querySelector(s), p || null);
  const o = {}; const col = %s;
  o.muted = col('--text-muted'); o.text = col('--text'); o.grey100 = col('--grey-100'); o.onBrand = col('--text-on-brand'); o.brand = col('--brand-blue');
  for (const id of ['ucl-group', 'ucl-sort', 'ucAddPage']) { const e = document.getElementById(id); e.style.transition = 'none'; }
  const a = q('#ucl-group'), b = q('#ucl-sort'), p = q('#ucAddPage');
  o.groupRest = [a.color, a.borderTopWidth]; o.sortRest = [b.color, b.borderTopWidth]; o.plusRest = [p.color, p.backgroundColor, p.borderTopColor];
  o.grey500 = col('--grey-500');
  const dots = q('#usecases .vtabmenu', '::after'); o.dots = [dots.fontSize, dots.lineHeight, dots.letterSpacing, q('#usecases .vtabmenu').fontSize];
  o.body = col('--text');
  const rw = document.querySelector('#usecases .fline-row').getBoundingClientRect();
  const fl = document.querySelector('#usecases .fline'); const fr = fl.getBoundingClientRect();
  const m = q('#usecases .fline', '::before'), h = q('#usecases .fline', '::after');
  o.mag = [m.position, m.left, m.top, m.width, m.height, m.marginTop, m.borderTopWidth, m.borderTopStyle, m.borderTopColor, m.borderTopLeftRadius, m.boxSizing];
  o.handle = [h.position, h.left, h.top, h.width, h.height, h.marginTop, h.backgroundColor, h.transform, h.transformOrigin];
  o.fline = [Math.round(fr.left - rw.left), Math.round(fr.width), fr.height];
  const c = q('#usecases .fcount'); o.count = [c.position, c.width, c.height, c.marginTop, c.overflow, c.clipPath, c.whiteSpace];
  o.noScroll = document.documentElement.scrollWidth <= window.innerWidth;
  return o; })()""" % COLOUR
OPEN = """(() => { const e = document.getElementById(%s); e.setAttribute('aria-expanded', 'true'); const s = getComputedStyle(e); return [s.color, s.backgroundColor, s.borderTopColor]; })"""
FOCUS = "(() => { const e = document.getElementById('ucAddPage'); e.focus(); return 1; })()"
PLUSNOW = "(() => { const s = getComputedStyle(document.getElementById('ucAddPage')); return [s.color, s.backgroundColor, s.borderTopColor]; })()"
CENTRE = "(() => { const r = document.getElementById(%s).getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()"


class Killers(unittest.TestCase):
    def setUp(self):
        need_chrome()
        demo = DemoStore()
        self.addCleanup(demo.close)
        self.demo = demo

    def hover(self, cdp, sid, ident):
        xy = cdp.js(CENTRE % repr(ident), sid)
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 0, "y": 0}, sid)
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": xy[0], "y": xy[1]}, sid)

    def test_classic_top_values(self):
        for w, scheme in VARIANTS:
            with self.subTest(width=w, scheme=scheme):
                s = Running(data_for=self.demo.store.data_for, page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=NAME))
                self.addCleanup(s.close)
                with chrome() as cdp:
                    sid = open_page(cdp, f"http://127.0.0.1:{s.port}/#usecases&p=ABC", w, scheme)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#ucl-group') && !!document.querySelector('#usecases .vtabmenu')", sid)))
                    g = cdp.js(STATE, sid)
                    # Row 1316 follow-up (prototype usecases.css .ucl-btn): the labelled buttons are ink (--text), not muted
                    self.assertEqual(g["groupRest"][0], g["text"], "Group by: ink text (labelled button, Row 1316 follow-up)")
                    self.assertEqual(g["sortRest"][0], g["text"], "Sort by: ink text (labelled button, Row 1316 follow-up)")
                    self.assertEqual(g["groupRest"][1], "1px")
                    self.assertEqual(g["plusRest"][0], g["brand"], "+ is brand coloured (Row 1316 controls, ruling 19-11; was muted)")
                    self.assertNotEqual(g["plusRest"][1], g["brand"], "+ has no brand fill at rest")
                    self.assertEqual(g["plusRest"][2], g["brand"], "the + border is brand coloured (was grey)")
                    self.assertEqual(g["dots"][0], g["dots"][3], "the dots are the size of the tab menu")
                    self.assertEqual(g["dots"][1], g["dots"][0], "line height 1")
                    self.assertAlmostEqual(float(g["dots"][2][:-2]) / float(g["dots"][0][:-2]), 0.05, places=3, msg="tracking .05em")
                    m = g["mag"]
                    h = g["handle"]
                    self.assertEqual(m[:3], ["absolute", "12px", m[2]], "the ring sits 12 px in")
                    self.assertEqual((m[3], m[4], m[6], m[7]), ("9px", "9px", "2px", "solid"), "the ring is 9 px with a 2 px line")
                    self.assertEqual(m[8], g["muted"], "the ring is muted")
                    half = g["fline"][2] / 2
                    self.assertAlmostEqual(float(m[2][:-2]), half, delta=1, msg="the ring is centred on the box")
                    self.assertAlmostEqual(float(h[2][:-2]), half, delta=1, msg="the handle is centred on the box")
                    self.assertEqual(m[9], "50%")
                    self.assertEqual(m[10], "content-box")
                    self.assertEqual(m[5], "-8px", "the ring is lifted")
                    self.assertEqual((h[0], h[1], h[3], h[4], h[5]), ("absolute", "23px", "5px", "2px", "4px"), "the handle")
                    self.assertEqual(h[6], g["muted"], "the handle is muted")
                    self.assertNotEqual(h[7], "none", "the handle is turned")
                    self.assertEqual(h[7], "matrix(0.707107, 0.707107, -0.707107, 0.707107, 0, 0)", "turned 45 degrees")
                    self.assertEqual(h[8].split()[0], "0px", "from its left end")
                    c = g["count"]
                    self.assertEqual((c[0], c[1], c[2], c[3], c[4], c[6]), ("absolute", "1px", "1px", "-1px", "hidden", "nowrap"), "the count is a hidden 1 px box")
                    self.assertEqual(c[5], "inset(50%)", "and clipped")
                    self.assertTrue(g["noScroll"])

    def test_classic_top_open_hover_and_focus(self):
        for w, scheme in VARIANTS:
            with self.subTest(width=w, scheme=scheme):
                s = Running(data_for=self.demo.store.data_for, page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=NAME))
                self.addCleanup(s.close)
                with chrome() as cdp:
                    sid = open_page(cdp, f"http://127.0.0.1:{s.port}/#usecases&p=ABC", w, scheme)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#ucl-group')", sid)))
                    g = cdp.js(STATE, sid)
                    cdp.js("for (const id of ['ucl-group', 'ucl-sort', 'ucAddPage']) document.getElementById(id).style.transition = 'none'", sid)
                    # open state of each
                    for ident in ("ucl-group", "ucl-sort"):
                        r = cdp.js((OPEN % repr(ident)) + "()", sid)
                        self.assertEqual(r[0], g["text"], ident + " open: full text colour")
                        self.assertEqual(r[1], g["grey100"], ident + " open: grey fill")
                    # hover of each
                    for ident in ("ucl-group", "ucl-sort"):
                        cdp.js("document.getElementById('%s').removeAttribute('aria-expanded')" % ident, sid)
                    for ident in ("ucl-group", "ucl-sort"):
                        self.hover(cdp, sid, ident)
                        r = cdp.js("(() => { const s = getComputedStyle(document.getElementById('%s')); return [s.color, s.backgroundColor]; })()" % ident, sid)
                        self.assertEqual(r, [g["text"], g["grey100"]], ident + " hover: text and grey fill")
                    cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 0, "y": 0}, sid)
                    # + : open, hover, focus: the rest look all the way (dashed grey, no brand fill; the ruling on row 1316)
                    rest = cdp.js(PLUSNOW, sid)
                    self.assertNotEqual(rest[1], g["brand"], "the + rests without a brand fill")
                    cdp.js("(() => { const e = document.getElementById('ucAddPage'); e.setAttribute('aria-expanded', 'true'); })()", sid)
                    wait(lambda: cdp.js(PLUSNOW, sid) == rest)
                    self.assertEqual(cdp.js(PLUSNOW, sid), rest, "+ open: the rest look")
                    cdp.js("document.getElementById('ucAddPage').removeAttribute('aria-expanded')", sid)
                    self.hover(cdp, sid, "ucAddPage")
                    wait(lambda: cdp.js(PLUSNOW, sid) == rest)
                    self.assertEqual(cdp.js(PLUSNOW, sid), rest, "+ hover: the rest look")
                    cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 0, "y": 0}, sid)
                    cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9}, sid)
                    cdp.js(FOCUS, sid)
                    cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Shift", "code": "ShiftLeft", "windowsVirtualKeyCode": 16}, sid)
                    cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Shift", "code": "ShiftLeft", "windowsVirtualKeyCode": 16}, sid)
                    self.assertEqual(cdp.js("document.getElementById('ucAddPage').matches(':focus-visible')", sid), True, "the + takes keyboard focus")
                    wait(lambda: cdp.js(PLUSNOW, sid) == rest)
                    self.assertEqual(cdp.js(PLUSNOW, sid), rest, "+ focused by keyboard: the rest look")


if __name__ == "__main__":
    unittest.main()
