"""Row 1317, Settings Title and Sidebar (Classic Theme), as Chrome computes them, 1400 and 900 px, light and dark.

Run: python3 dev/run_tests.py test_theme_classic_1317a
Fails, never skips, without Chrome. Classic: the Settings title is 30 px, the group names are sentence case (not capitals, not tracked)
and the open page is a tinted bar with the brand marker. Cards: the same elements keep the installed look, and the Cards page is the page it was.
Prototype files are not on this box: the look comes from the issue table, by eye +/-2 px.
"""
import hashlib
import tempfile
import time
import unittest
from pathlib import Path

from _paths import ROOT  # noqa: F401
from test_server import chrome

from clark import page
from test_theme_classic_css import rgb

SIZES = (1400, 900)
CARDS_SHA256 = "b8bbbc7c0becd510ecf0d0b5b04167d818a2a9d926528f5a23ec83849b2d5e47"
JS = """(() => { const q = (s) => document.querySelector(s), g = (e) => getComputedStyle(e);
  const h = g(q('.set-head h1')), n = g(q('.set-group-name')), c = g(q('.set-chip[aria-current]')), p = g(q('.set-bar')), d = g(q('.set-chip:not([aria-current])'));
  return {h1: h.fontSize, h1w: h.fontWeight, tt: n.textTransform, ls: n.letterSpacing, gfs: n.fontSize, gw: n.fontWeight,
    cbg: c.backgroundColor, cr: c.borderTopLeftRadius, cr3: c.borderTopRightRadius, pr: p.borderTopLeftRadius, cfw: c.fontWeight, pbg: p.backgroundColor, cr2: d.borderTopLeftRadius,
    tint: g(document.documentElement).getPropertyValue('--brand-blue-tint').trim(), text: q('.set-group-name').textContent}; })()"""


class Sidebar(unittest.TestCase):
    def load(self, cdp, width, scheme, theme):
        html = page.page_html(branding=page.NO_BRAND, theme=theme)
        path = Path(tempfile.mkdtemp(prefix="clark-test-")) / "p.html"
        path.write_text(html, encoding="utf-8")
        self.addCleanup(lambda: (path.unlink(), path.parent.rmdir()))
        tid = cdp.call("Target.createTarget", {"url": "about:blank"})["targetId"]
        sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
        end = time.monotonic() + 20
        while cdp.js("document.readyState", sid) != "complete" and time.monotonic() < end:
            time.sleep(0.05)
        cdp.js("""(() => { document.documentElement.setAttribute('data-theme', %r);
            const s = document.createElement('div'); s.className = 'set-layout';
            s.innerHTML = '<section class="frame set-head"><h1>Settings</h1></section><nav class="set-bar"><ul class="set-nav">'
              + '<li class="set-group"><span class="set-group-name">Everyday</span><ul class="plain"><li><button type="button" class="set-chip" aria-current="page">Projects</button></li><li><button type="button" class="set-chip">People</button></li></ul></li></ul></nav>';
            document.body.appendChild(s); })()""" % scheme, sid)
        return cdp.js(JS, sid), sid

    def test_classic_sets_a_grey_panel_sentence_case_group_names_and_a_square_edged_open_bar(self):
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                for w in SIZES:
                    got, sid = self.load(cdp, w, scheme, "prototype-2.0")
                    tag = f"classic {scheme} {w}"
                    grey = cdp.js("getComputedStyle(document.documentElement).getPropertyValue('--grey-100').trim()", sid)
                    self.assertEqual(got["pbg"], rgb(grey), tag)
                    self.assertEqual((got["tt"], got["ls"]), ("none", "normal"), tag)
                    self.assertEqual(got["text"], "Everyday", tag)
                    self.assertEqual(got["cbg"], rgb(got["tint"]), tag)
                    self.assertEqual(got["cr"], "0px", tag)
                    self.assertEqual(got["cr3"], "10px", tag)
                    self.assertEqual(got["cr2"], "10px", tag)
                    self.assertEqual(got["pr"], "12px", tag)
                    self.assertEqual(got["h1"], "30px", tag)

    def test_classic_hover_on_another_page_is_still_seen_against_the_panel(self):
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                for w in SIZES:
                    got, sid = self.load(cdp, w, scheme, "prototype-2.0")
                    tag = f"classic hover {scheme} {w}"
                    box = cdp.js("(() => { const r = document.querySelector('.set-chip:not([aria-current])').getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; })()", sid)
                    cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": box[0], "y": box[1]}, sid)
                    hov = cdp.js("getComputedStyle(document.querySelector('.set-chip:not([aria-current])')).backgroundColor", sid)
                    self.assertNotEqual(hov, got["pbg"], tag)
                    self.assertNotEqual(hov, "rgba(0, 0, 0, 0)", tag)

    def test_cards_keeps_the_capitals_the_pill_and_the_panel_on_the_same_elements(self):
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                for w in SIZES:
                    got, sid = self.load(cdp, w, scheme, None)
                    tag = f"cards {scheme} {w}"
                    self.assertEqual(got["tt"], "uppercase", tag)
                    self.assertNotEqual(got["ls"], "normal", tag)
                    self.assertEqual((got["cr"], got["cr2"]), ("10px", "10px"), tag)
                    self.assertNotEqual(got["pbg"], rgb(cdp.js("getComputedStyle(document.documentElement).getPropertyValue('--grey-100').trim()", sid)), tag)
                    self.assertEqual(got["h1"], "30px", tag)

    def test_the_cards_page_is_byte_for_byte_what_it_was(self):
        html = page.page_html(branding=page.NO_BRAND, theme=None)
        self.assertEqual(hashlib.sha256(html.encode("utf-8")).hexdigest(), CARDS_SHA256)
        classic = page.page_html(branding=page.NO_BRAND, theme="prototype-2.0")
        self.assertIn(".set-group-name { text-transform: none", classic)
        self.assertNotIn(".set-group-name { text-transform: none", html)


if __name__ == "__main__":
    unittest.main()
