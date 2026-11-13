"""Issue 1146: a published client report has ONE slim sticky bar (the logo, the project name with the report line, the tabs, the date,
the place for the switcher icon, the profile circle), where the file had a top bar and a banner card. The editor keeps both. In a real browser.

Run: python3 dev/run_tests.py test_published_one_bar        (needs Chrome; run only while the machine's load is under 70)
Computed style, at 1400 and 900 px, light and dark. Fictional data.
"""
import base64
import json
import re
import unittest

import _backdrop_pics as pics
from test_cover_band import artwork
from test_glance_page import Published, Setup
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

from _paths import SRC

CSS = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
CASES = ((1400, False), (1400, True), (900, False), (900, True))

BAR = """(() => {
  const r = (e) => { const b = e.getBoundingClientRect(); return {top: b.top, bottom: b.bottom, left: b.left, right: b.right, h: b.height}; };
  const bar = document.querySelector('header.top'), q = (s) => bar.querySelector(s), tab = q('.tab[aria-selected="true"]');
  const st = (e, k) => getComputedStyle(e)[k], frame = document.querySelector('.frame.report');
  const date = q('.asat'), badge = q('.cm-badge'), tabs = q('.tabs'), name = q('.top-name'), line = q('.top-line');
  return {bars: document.querySelectorAll('header.top').length, covers: document.querySelectorAll('header.cover, #cover').length,
    tops: document.querySelectorAll('header.top, header.cover').length,
    bar: r(bar), pos: st(bar, 'position'), logo: !!q('.logo'), nameSize: st(name, 'fontSize'), nameTag: name.tagName, lineSize: st(line, 'fontSize'),
    lineText: line.textContent, nameText: name.textContent, tabs: r(tabs), tab: r(tab), tabPad: [st(tab, 'paddingTop'), st(tab, 'paddingBottom')],
    tabLine: parseFloat(st(tab, 'lineHeight')), tabNames: [...bar.querySelectorAll('.tab')].map((t) => t.textContent),
    date: date ? {shown: st(date, 'display'), box: r(date), text: date.textContent} : null, badge: r(badge), name: r(name), line: r(line),
    slot: !!q('.top-slot[data-slot="theme"]'), slotShown: st(q('.top-slot'), 'display'),
    frameTop: frame.getBoundingClientRect().top, glance: !!document.querySelector('.glance'), wide: document.documentElement.scrollWidth <= innerWidth,
    after: parseFloat(getComputedStyle(tab, '::after').height), afterBottom: getComputedStyle(tab, '::after').bottom,
    margins: [...document.querySelectorAll('.sec')].map((s) => st(s, 'scrollMarginTop')), secs: document.querySelectorAll('.sec').length,
    topbarVar: getComputedStyle(document.documentElement).getPropertyValue('--topbar').trim(),
    firstOffset: (() => { const f = frame.firstElementChild; return f ? f.getBoundingClientRect().top - frame.getBoundingClientRect().top : null; })()};
})()"""


class InTheFile(Published):
    def close(self):
        if getattr(self, "_cm", None):
            self._cm.__exit__(None, None, None)
            self._cm = None

    def bar(self, width, dark):
        """The published file open at a width, light or dark; the browser of the case before is closed first."""
        self.close()
        if not getattr(self, "_path", None):
            self._path = self.publish()
            self.addCleanup(self.close)
        path = self._path
        self._cm = chrome()
        cdp = self._cm.__enter__()
        p = self.draw(cdp, path, width, dark)
        p.until("!!document.querySelector('.top-file .tab') && !!document.querySelector('.glance')", "the bar and the tiles drew")
        return cdp, p

    def test_one_bar_replaces_the_bar_and_the_banner(self):
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark):
                cdp, p = self.bar(width, dark)
                b = p.js(BAR)
                self.assertEqual((b["bars"], b["covers"], b["tops"]), (1, 0, 1), "one header, and no banner card")
                self.assertTrue(b["logo"])
                self.assertEqual(b["nameSize"], "24px")
                self.assertEqual(b["lineSize"], "13px")
                self.assertEqual(b["nameTag"], "H1", "the Dashboard keeps its one heading, now in the bar")
                self.assertIn("WEEKLY REPORT", b["lineText"].upper())
                self.assertTrue(b["wide"], "no sideways scroll")
                self.assertTrue(b["slot"], "the place for the switcher icon is there")
                self.assertEqual(b["slotShown"], "none", "and takes no room while empty")
                self.assertTrue(b["glance"])
                self.assertGreater(b["name"]["bottom"], 0)
                self.assertLessEqual(b["badge"]["right"], width + 0.5)

    def test_the_bar_is_68_px_and_sticky_at_1400_and_two_rows_at_900(self):
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark):
                cdp, p = self.bar(width, dark)
                b = p.js(BAR)
                self.assertEqual(b["pos"], "sticky")
                if width == 1400:
                    self.assertEqual(b["bar"]["h"], 68)
                    self.assertEqual(b["topbarVar"], "68px")
                    self.assertAlmostEqual(b["tabs"]["top"] + b["tabs"]["h"] / 2, 34, delta=3, msg="the tabs sit on the one row")
                    self.assertNotEqual(b["date"]["shown"], "none")
                    self.assertTrue(b["date"]["text"].startswith("As at "))
                    self.assertLess(b["date"]["box"]["right"], b["badge"]["left"], "the date, then the profile circle")
                    self.assertLess(b["tabs"]["right"], b["date"]["box"]["left"] + 1)
                else:
                    self.assertEqual(b["bar"]["h"], 100)
                    self.assertEqual(b["topbarVar"], "100px")
                    self.assertEqual(b["date"]["shown"], "none", "the date is dropped")
                    self.assertGreaterEqual(b["tabs"]["top"], b["line"]["bottom"] - 1, "the tabs are a strip under the name")
                    self.assertGreaterEqual(b["tabs"]["right"] - b["tabs"]["left"], width - 60, "the strip runs the width")
                p.js("window.scrollTo(0, 600)")
                p.until("window.scrollY > 100", "scrolled")
                self.assertEqual(p.js("document.querySelector('header.top').getBoundingClientRect().top"), 0, "it stays at the top")

    def test_the_underline_is_right_under_the_label(self):
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark):
                cdp, p = self.bar(width, dark)
                b = p.js(BAR)
                self.assertEqual(b["tabPad"], ["8px", "9px"])
                self.assertAlmostEqual(b["tab"]["h"] - b["tabLine"], 17, delta=0.6, msg="the tab is its text plus 8 above and 9 below")
                self.assertEqual((b["after"], b["afterBottom"]), (3, "0px"), "the cyan line is at the foot of that short tab")
                self.assertEqual(b["tabNames"][:2], ["Dashboard", "Work items"])

    def test_the_first_card_is_10_px_under_the_bar_and_the_banner_space_is_closed(self):
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark):
                cdp, p = self.bar(width, dark)
                b = p.js(BAR)
                self.assertAlmostEqual(b["frameTop"] - b["bar"]["bottom"], 10, delta=1)
                self.assertLessEqual(b["firstOffset"], 6, "the frame begins at its first section, no empty band above At a glance")

    def test_every_section_clears_the_bar_when_jumped_to(self):
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark):
                cdp, p = self.bar(width, dark)
                b = p.js(BAR)
                self.assertGreater(b["secs"], 2)
                want = f"{b['bar']['h'] + 16:g}px"
                self.assertEqual(set(b["margins"]), {want}, "the bar's height and air above every section")
                p.js("document.querySelectorAll('.sec')[2].scrollIntoView()")
                p.until("window.scrollY > 0", "scrolled")
                top = p.js("document.querySelectorAll('.sec')[2].getBoundingClientRect().top")
                self.assertGreaterEqual(top, b["bar"]["h"], "the section's top is under the bar, not behind it")

    def test_the_narrow_rules_are_in_one_media_block(self):
        text = CSS[CSS.index("Issue 1146"):]
        text = text[:text.index("@media print")]
        self.assertEqual(len(re.findall(r"@media \(max-width", text)), 1, "one block holds the narrow bar")
        self.assertEqual(len(re.findall(r"@media \(max-width: 900px\) \{[^@]*\.top-file \{ flex-wrap: wrap", text)), 1)

    def test_print_is_not_sticky(self):
        cdp, p = self.bar(1400, False)
        self.assertEqual(p.js("getComputedStyle(document.querySelector('header.top')).position"), "sticky")
        cdp.call("Emulation.setEmulatedMedia", {"media": "print"}, p.sid)
        self.assertEqual(p.js("getComputedStyle(document.querySelector('header.top')).position"), "static", "placed once, never stuck or repeated")
        self.assertNotEqual(p.js("getComputedStyle(document.querySelector('header.top')).display"), "none", "and it is printed")

    def test_print_keeps_the_picture_wash_inside_the_bar(self):
        wash = """(() => { const h = document.querySelector('header.top'), s = getComputedStyle(h, '::before');
          return {pos: getComputedStyle(h).position, wash: parseFloat(s.height), bar: h.getBoundingClientRect().height}; })()"""
        for width in (1400, 900):
            with self.subTest(width=width):
                cdp, p = self.bar(width, False)
                p.js("document.documentElement.style.setProperty('--image-cover', %s)" % json.dumps(artwork()))
                cdp.call("Emulation.setEmulatedMedia", {"media": "print"}, p.sid)
                got = p.js(wash)
                self.assertNotEqual(got["pos"], "sticky", "still not stuck on paper")
                self.assertGreater(got["bar"], 0)
                self.assertAlmostEqual(got["wash"], got["bar"], delta=0.5, msg="the wash fills the bar, not the page")

    def test_the_picture_is_a_wash_over_the_right_45_percent_and_none_without_it(self):
        wash = """(() => { const s = getComputedStyle(document.querySelector('header.top'), '::before'), b = document.querySelector('header.top').getBoundingClientRect();
          return {image: s.backgroundImage, left: parseFloat(s.left), w: parseFloat(s.width), bar: b.width, opacity: s.opacity, mask: s.maskImage || s.webkitMaskImage, bg: getComputedStyle(document.querySelector('header.top')).backgroundImage}; })()"""
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark):
                cdp, p = self.bar(width, dark)
                got = p.js(wash)
                self.assertEqual(got["image"], "none", "no brand picture: the plain navy gradient")
                self.assertIn("linear-gradient", got["bg"])
                p.js("document.documentElement.style.setProperty('--image-cover', %s)" % json.dumps(artwork()))
                got = p.js(wash)
                self.assertIn("data:image/png", got["image"])
                self.assertAlmostEqual(got["w"] / got["bar"], 0.45, delta=0.01)
                self.assertEqual(float(got["opacity"]), 0.42)
                self.assertNotIn(got["mask"], ("", "none"), "faded in from the left")

    def test_text_keeps_4_5_to_1_over_the_picture(self):
        for width, dark in CASES:
            for name, data in (("swirl", pics.swirl()), ("bright", pics.solid((60, 200, 230)))):
                with self.subTest(width=width, dark=dark, picture=name):
                    cdp, p = self.bar(width, dark)
                    url = "url(data:image/png;base64," + base64.b64encode(data).decode() + ")"
                    p.js("document.documentElement.style.setProperty('--image-cover', %s)" % json.dumps(url))
                    low = worst(cdp, p)
                    self.assertGreaterEqual(low[0], 4.5, f"{low[1]} is {low[0]:.2f}:1")


TEXTS = """(() => { const out = [], w = document.createTreeWalker(document.querySelector('header.top'), NodeFilter.SHOW_TEXT);
  for (let n; (n = w.nextNode());) { if (!n.textContent.trim()) continue; const el = n.parentElement, cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility !== 'visible') continue;
    const rg = document.createRange(); rg.selectNodeContents(n);
    for (const r of rg.getClientRects()) if (r.width > 2 && r.height > 2 && r.right <= innerWidth && r.bottom <= innerHeight) out.push({t: n.textContent.trim().slice(0, 30), x: r.left, y: r.top, w: r.width, h: r.height, fg: cs.color}); }
  return out; })()"""
HIDE = ("(function(){var s=new CSSStyleSheet();s.replaceSync('header.top *{color:transparent!important;-webkit-text-fill-color:transparent!important;text-shadow:none!important}');"
        "window.__hide=s;document.adoptedStyleSheets=[...document.adoptedStyleSheets,s];})()")


def lum(c):
    def g(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * g(c[0]) + 0.7152 * g(c[1]) + 0.0722 * g(c[2])


def ratio(a, b):
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def colour(text):
    """(r, g, b, alpha) of a computed colour, 0-255, from rgb(...) or color(srgb ...)."""
    nums = [float(v) for v in re.findall(r"[\d.]+", text.split("/")[0])]
    alpha = float(re.findall(r"[\d.]+", text.split("/")[1])[0]) if "/" in text else (nums[3] if len(nums) > 3 and text.startswith("rgba") else 1.0)
    scale = 255 if text.startswith("color(") else 1
    return [v * scale for v in nums[:3]] + [alpha]


def worst(cdp, p):
    """The lowest contrast of the bar's texts against the pixels drawn behind them (the page drawn once with its text made clear)."""
    p.until("document.getAnimations().every(a => a.playState === 'finished')", "settled")
    items = p.js(TEXTS)
    assert items, "the bar holds text"
    p.js(HIDE)
    w, h, rows = pics.decode(base64.b64decode(cdp.call("Page.captureScreenshot", {"format": "png"}, p.sid)["data"]))
    low = (99.0, None)
    for it in items:
        r, g, b, a = colour(it["fg"])
        for y in range(int(it["y"]), min(h, int(it["y"] + it["h"]) + 1), 2):
            for x in range(int(it["x"]), min(w, int(it["x"] + it["w"]) + 1), 2):
                bg = rows[y][x]
                eff = [a * c + (1 - a) * k for c, k in zip((r, g, b), bg)]
                rr = ratio(eff, bg)
                if rr < low[0]:
                    low = (rr, f"{it['t']!r} on {bg} at {int(it['x'])},{int(it['y'])}")
    return low


class TheEditor(Setup):
    """The editor keeps its own top bar and its banner; only the published file changes."""

    def test_the_editor_is_unchanged(self):
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.show(cdp, width, dark)
                got = p.js("""(() => ({bars: document.querySelectorAll('header.top').length, file: document.querySelectorAll('.top-file, .top-id, .top-slot').length,
                  cover: document.querySelectorAll('header.cover').length, h: document.querySelector('header.top').getBoundingClientRect().height,
                  pos: getComputedStyle(document.querySelector('header.top')).position, bar: getComputedStyle(document.documentElement).getPropertyValue('--topbar').trim(),
                  margin: getComputedStyle(document.querySelector('.sec')).scrollMarginTop}))()""")
                self.assertEqual((got["bars"], got["file"], got["cover"]), (1, 0, 1), "the bar and the banner are both still there")
                self.assertEqual((got["h"], got["bar"], got["pos"]), (56, "56px", "sticky"))
                self.assertEqual(got["margin"], "0px")


if __name__ == "__main__":
    unittest.main()
