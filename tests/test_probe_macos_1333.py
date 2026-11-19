"""Row 1333 probe (reads only, always passes): prints what the browser on this runner reports, so the macOS nightly failures can be told apart.
Run: python3 dev/run_tests.py test_probe_macos_1333
Lines start with PROBE: the reduced-motion media value, the 900 px header height, the Classic radius of '#md'::before, the settings menu hover fill, and which element has focus after the feedback tag opens.
"""
import json
import unittest

import test_peek as tp  # noqa: E402
from test_server import chrome  # noqa: E402


class Probe(unittest.TestCase):
    setUpClass = tp.Browser.__dict__["setUpClass"]
    tearDownClass = tp.Browser.__dict__["tearDownClass"]
    load_page = tp.Browser.load_page

    def test_probe(self):
        for width in (1400, 900):
            with chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                out = cdp.js("""(() => ({
                  reduce: matchMedia('(prefers-reduced-motion: reduce)').matches,
                  noPref: matchMedia('(prefers-reduced-motion: no-preference)').matches,
                  dpr: devicePixelRatio, ua: navigator.userAgent,
                  header: (document.querySelector('header, #top, .topbar') || {getBoundingClientRect: () => ({height: null})}).getBoundingClientRect().height,
                  mdRadius: (document.querySelector('#md') ? getComputedStyle(document.querySelector('#md'), '::before').borderRadius : 'no #md'),
                  font: getComputedStyle(document.body).fontFamily, fontSize: getComputedStyle(document.body).fontSize,
                  active: document.activeElement ? document.activeElement.tagName + '#' + document.activeElement.id : null }))()""", sid)
                print("PROBE:", width, json.dumps(out), flush=True)


if __name__ == "__main__":
    unittest.main()
