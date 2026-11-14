"""Item 1850 diagnostic (never merged): what does the CI Mac's Chrome report for prefers-reduced-motion, before and after the CDP pin?
It fails on purpose so the log prints the numbers."""
import json
import unittest
import urllib.parse

from test_server import chrome, wait

PAGE = ("<style>@media (prefers-reduced-motion: no-preference){#a{animation:x 2s linear infinite}}@keyframes x{to{opacity:.5}}</style>"
        "<div id=a>hi</div>")
Q = "[matchMedia('(prefers-reduced-motion: reduce)').matches, matchMedia('(prefers-reduced-motion: no-preference)').matches, getComputedStyle(document.getElementById('a')).animationName]"


class Diag(unittest.TestCase):
    def test_report(self):
        seen = []
        with chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            seen.append(("version", cdp.call("Browser.getVersion").get("product")))
            cdp.call("Page.navigate", {"url": "data:text/html," + urllib.parse.quote(PAGE)}, sid)
            wait(lambda: cdp.js("!!document.getElementById('a')", sid))
            seen.append(("as loaded", cdp.js(Q, sid)))
            for v in ("no-preference", "reduce", "no-preference"):
                cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": v}]}, sid)
                seen.append(("pin " + v, cdp.js(Q, sid)))
            cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "no-preference"}]}, sid)
            cdp.call("Page.reload", {}, sid)
            wait(lambda: cdp.js("!!document.getElementById('a')", sid))
            seen.append(("after reload with pin kept", cdp.js(Q, sid)))
        self.fail("DIAG " + json.dumps(seen))


if __name__ == "__main__":
    unittest.main()
