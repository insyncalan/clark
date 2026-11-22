"""Row 1269, slice B: the Classic Theme CSS as Chrome computes it, at 1400 and 900 px, light and dark.

Run: python3 dev/run_tests.py test_theme_classic_css
Fails, never skips, without Chrome. The page is the shipped page with the Classic Theme layered; the section is built in the page
so the counter rule has something to number. Ruling e: the dark page gradient runs from the first dark ground to the second.
"""
import re
import tempfile
import time
import unittest
from pathlib import Path

from _paths import ROOT  # noqa: F401
from test_server import chrome

from clark import page, theme
from test_theme_prototype import blocks, decls, TOKENS

NAME = "prototype-2.0"
SIZES = (1400, 900)
DARK_FROM, DARK_TO = "#0f1523", "#121a2a"       # Whisper (rows 1310, 1311), dark


def rgb(hex_colour):
    h = hex_colour.lstrip("#")
    return "rgb(%d, %d, %d)" % tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class Tokens(unittest.TestCase):
    def test_the_dark_gradient_is_the_ruled_pair_in_both_dark_copies_and_they_are_equal(self):
        b = blocks(TOKENS)
        want = f"linear-gradient(90deg, {DARK_FROM}, {DARK_TO})"
        self.assertEqual(decls(b["dark"])["--page-grad"], want)
        self.assertEqual(decls(b["auto"])["--page-grad"], want)
        self.assertEqual(decls(b["dark"]), decls(b["auto"]))

    def test_the_page_colour_is_the_end_of_the_dark_gradient(self):
        self.assertEqual(decls(blocks(TOKENS)["dark"])["--page-bg"], DARK_TO)


class Computed(unittest.TestCase):
    def load(self, cdp, width, scheme):
        html = page.page_html(branding=page.NO_BRAND, theme=NAME)
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
        cdp.js("""(() => { const r = document.documentElement; r.setAttribute('data-theme', %r);
            const secs = document.createElement('div'); secs.className = 'secs';
            secs.innerHTML = '<div class="sec"><div class="sec-head">One</div></div><div class="sec is-hidden"><div class="sec-head">Hidden</div></div><div class="sec"><div class="sec-head">Two</div></div>';
            document.body.appendChild(secs); })()""" % scheme, sid)
        return sid

    def test_the_page_gradient_and_the_section_numbers_at_each_width_in_light_and_dark(self):
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                for w in SIZES:
                    sid = self.load(cdp, w, scheme)
                    tag = f"{scheme} {w}"
                    self.assertEqual(cdp.js("window.innerWidth", sid), w, tag)
                    img = cdp.js("getComputedStyle(document.body).backgroundImage", sid)
                    self.assertIn("linear-gradient", img, tag)
                    if scheme == "dark":
                        self.assertIn(rgb(DARK_FROM), img, tag)
                        self.assertIn(rgb(DARK_TO), img, tag)
                    got = cdp.js("[...document.querySelectorAll('.secs > .sec')].map(h => getComputedStyle(h).counterIncrement)", sid)
                    self.assertEqual(got, ["secn 1", "none", "secn 1"], tag)    # the hidden section is not counted
                    self.assertEqual(cdp.js("getComputedStyle(document.querySelector('.secs'), null).counterReset", sid), "secn 0", tag)
                    self.assertEqual(cdp.js("getComputedStyle(document.querySelector('.secs .sec-head'), '::before').content", sid), "counter(secn)", tag)
                    size = cdp.js("getComputedStyle(document.querySelector('.secs .sec-head'), '::before').fontSize", sid)
                    self.assertEqual(size, "20px", tag)
                    self.assertTrue(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), tag)


if __name__ == "__main__":
    unittest.main()
