"""Row 1317, Projects card (Settings): Add project and the table headers in the Classic Theme, as Chrome computes them, 1400 and 900 px, light and dark.

Run: python3 dev/run_tests.py test_theme_classic_1317
Fails, never skips, without Chrome. Classic: Add project is a filled button (solid fill, no dashed border) and the headers are bold, not
capitals, not tracked. Cards: the same two elements keep the dashed Add and the tracked capitals, and the Cards page is the page it was.
Prototype files are not on this box: the look comes from the issue table.
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
# The Cards page, page_html(branding=NO_BRAND, theme=None), taken from origin/main before this row; rules.css is read only when a Theme is named.
CARDS_SHA256 = "598a68997d875884820f96e873252e059970a36401f8243b23eba9483069c499"
JS = """(() => { const q = (s) => document.querySelector(s), g = (e) => getComputedStyle(e);
  const b = g(q('#npBtn')), h = g(q('#ph'));
  return {bg: b.backgroundColor, bs: b.borderTopStyle, bc: b.borderTopColor, fg: b.color, ico: !!q('#npBtn svg, #npBtn .i'),
    tt: h.textTransform, ls: h.letterSpacing, fw: h.fontWeight, text: q('#ph').textContent}; })()"""


def tint(cdp, sid, scheme):
    return cdp.js("(() => { const r = document.documentElement; r.setAttribute('data-theme', %r); return 1; })()" % scheme, sid)


class Projects(unittest.TestCase):
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
            const s = document.createElement('section'); s.className = 'frame setting projects';
            s.innerHTML = '<button type="button" class="newb" id="npBtn"><svg class="i" viewBox="0 0 24 24"></svg><span class="w">Add project</span></button>'
              + '<table class="items proj-table"><thead><tr><th id="ph" scope="col">Name</th><th scope="col">Code</th></tr></thead></table>';
            document.body.appendChild(s); })()""" % scheme, sid)
        return cdp.js(JS, sid), sid

    def test_classic_fills_add_project_and_sets_the_headers_bold_in_their_own_case(self):
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                for w in SIZES:
                    got, sid = self.load(cdp, w, scheme, "prototype-2.0")
                    tag = f"classic {scheme} {w}"
                    want_bg = cdp.js("getComputedStyle(document.documentElement).getPropertyValue('--brand-blue').trim()", sid)
                    self.assertEqual(got["bg"], rgb(want_bg), tag)
                    self.assertEqual(got["bs"], "solid", tag)
                    self.assertEqual(got["bc"], got["bg"], tag)
                    self.assertNotEqual(got["fg"], got["bg"], tag)
                    self.assertTrue(got["ico"], tag)
                    self.assertEqual((got["tt"], got["ls"]), ("none", "normal"), tag)
                    self.assertIn(got["fw"], ("600", "700"), tag)
                    self.assertEqual(got["text"], "Name", tag)

    def test_cards_keeps_the_dashed_add_and_the_tracked_capitals_on_the_same_elements(self):
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                for w in SIZES:
                    got, sid = self.load(cdp, w, scheme, None)
                    tag = f"cards {scheme} {w}"
                    self.assertEqual(got["bs"], "dashed", tag)
                    self.assertEqual(got["tt"], "uppercase", tag)
                    self.assertNotEqual(got["ls"], "normal", tag)
                    self.assertNotIn(got["fw"], ("600", "700"), tag)

    def test_the_cards_page_is_byte_for_byte_what_it_was(self):
        html = page.page_html(branding=page.NO_BRAND, theme=None)
        self.assertEqual(hashlib.sha256(html.encode("utf-8")).hexdigest(), CARDS_SHA256)
        classic = page.page_html(branding=page.NO_BRAND, theme="prototype-2.0")
        self.assertIn(".projects #npBtn.newb", classic)
        self.assertNotIn(".projects #npBtn.newb", html)


if __name__ == "__main__":
    unittest.main()
