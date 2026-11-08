"""Row 944, track T3 (tests first): the editor follows the open project's brand, in a real browser. Two projects, ONE on brand A
(navy #123456) and TWO on brand B (navy #654321), THREE on Generic. Opening another project reloads the page on GET /?project=<code>
(design note, T3: the swap is server side, so the policy's style hashes match the bytes), and the page holds one brand-local block.

Needs nothing from T1 or T2: the seam __main__ will pass is stubbed in test_brand_route (project -> brand -> folder).
Run: python3 dev/run_tests.py test_brand_follow_e2e   (one browser file at a time). Chrome is required: this test fails, never
skips, without it. Every brand here is made by the test.
"""
import json
import time
import unittest
from unittest import mock

import _paths  # noqa: F401  (puts src/ on the path)
import _testpage as testpage
from clark import server as sv
from test_brand_route import NAVY, PIC, BRAND_OF, make_brands, seam, picture_seam
from test_gantt_e2e import Browser
from test_server import Running, chrome, wait, _Collect

CODES = ("ONE", "TWO", "THREE")
DATA = {c: {"name": f"Project {c.title()}", "actions": [{"id": f"{c}-A-001", "action": "Agree the plan"}]} for c in CODES}
PROJECTS = [{"code": c, "name": f"Project {c.title()}"} for c in CODES]
NAVY_NOW = "getComputedStyle(document.documentElement).getPropertyValue('--brand-navy').trim()"
BLOCKS = "document.querySelectorAll('style#brand-local').length"


class Follow(unittest.TestCase):
    def setUp(self):
        self.folders = make_brands(self)
        self.s = Running(data_for=DATA.get, projects=lambda archived=False: PROJECTS, page_html=seam(self.folders, base=testpage.html))
        self.s.httpd.brand_picture = picture_seam(self.folders)
        self.addCleanup(self.s.close)
        self.base = f"http://127.0.0.1:{self.s.port}/"

    def go_to(self, cdp, code):
        br = Browser(self, cdp, self.s.port)
        br.visit(self.base + f"#dashboard&p={code}")
        return br

    def test_opening_project_one_then_two_swaps_the_one_brand_block(self):
        with chrome() as cdp:
            br = self.go_to(cdp, "ONE")
            self.assertEqual(br.js(NAVY_NOW), NAVY["ONE"])
            self.assertEqual(br.js(BLOCKS), 1)
            self.assertEqual(br.js("document.querySelectorAll('style#brand-demo').length"), 1, "the demo block is untouched")
            br.js("window.clarkPage.setProject('TWO')")
            br.until(f"{NAVY_NOW} === {json.dumps(NAVY['TWO'])}", "the page took project TWO's brand")
            self.assertEqual(br.js(BLOCKS), 1, "never two brand blocks")
            self.assertNotIn(NAVY["ONE"], br.js("[].map.call(document.querySelectorAll('style'), s => s.textContent).join('')"))
            br.js("window.clarkPage.setProject('ONE')")
            br.until(f"{NAVY_NOW} === {json.dumps(NAVY['ONE'])}", "and back to project ONE's")
            self.assertEqual(br.js(BLOCKS), 1)

    def test_a_reload_on_project_two_starts_with_two_and_never_paints_one(self):
        with chrome() as cdp:
            br = Browser(self, cdp, self.s.port)
            br.cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source":
                "window.__navy = []; new MutationObserver(function () { var v = getComputedStyle(document.documentElement).getPropertyValue('--brand-navy').trim(); "
                "if (v && window.__navy[window.__navy.length - 1] !== v) window.__navy.push(v); }).observe(document, {childList: true, subtree: true});"}, br.sid)
            br.visit(self.base + "#dashboard&p=TWO")
            br.until(f"{NAVY_NOW} === {json.dumps(NAVY['TWO'])}", "project TWO's brand on first load")
            self.assertNotIn(NAVY["ONE"], br.js("window.__navy"), "project ONE's navy was never seen")

    def test_a_project_on_generic_has_no_brand_block_and_not_the_one_before(self):
        with chrome() as cdp:
            br = self.go_to(cdp, "ONE")
            br.js("window.clarkPage.setProject('THREE')")
            br.until(f"{BLOCKS} === 0", "Generic has no brand block")
            self.assertNotIn(NAVY["ONE"], br.js(NAVY_NOW))
            self.assertNotIn(NAVY["TWO"], br.js(NAVY_NOW))

    def test_the_cover_picture_follows_and_the_policy_blocks_nothing(self):
        blocked = []
        handler = _Collect(blocked)
        sv.LOG.addHandler(handler)
        sv.LOG.setLevel("INFO")
        self.addCleanup(sv.LOG.removeHandler, handler)
        load = ("new Promise(function (ok) { var i = new Image(); i.onload = function () { ok([i.naturalWidth, i.naturalHeight]); }; "
                "i.onerror = function () { ok('error'); }; i.src = %s; })")
        with mock.patch.dict(sv.CSP_REPORTS, since=time.time(), n=0, dropped=0):
            with chrome() as cdp:
                br = self.go_to(cdp, "ONE")
                for code in ("ONE", "TWO"):
                    if code == "TWO":
                        br.js("window.clarkPage.setProject('TWO')")
                        br.until(f"{NAVY_NOW} === {json.dumps(NAVY['TWO'])}", "project TWO's brand")
                    want = f'url("/assets/{BRAND_OF[code]}/cover.png")'
                    self.assertEqual(br.js("getComputedStyle(document.documentElement).getPropertyValue('--image-cover').trim()"), want)
                    got = cdp.call("Runtime.evaluate", {"expression": load % json.dumps(f"/assets/{BRAND_OF[code]}/cover.png"),
                                                        "awaitPromise": True, "returnByValue": True}, br.sid)["result"]["value"]
                    self.assertEqual(got, [8, 8], code)
                self.assertEqual(blocked, [], f"the policy blocked nothing: {blocked}")

    def test_dark_scheme_keeps_the_swap(self):
        with chrome() as cdp:
            br = self.go_to(cdp, "ONE")
            br.scheme("dark")
            br.js("window.clarkPage.setProject('TWO')")
            br.until(f"{NAVY_NOW} === {json.dumps(NAVY['TWO'])}", "project TWO's brand in the dark scheme")
            self.assertEqual(br.js(BLOCKS), 1)

    def test_a_failed_page_load_for_the_new_project_keeps_the_page_usable(self):
        real = self.s.httpd.page_html
        calls = []

        def broken(project=None):
            calls.append(project)
            if project == "TWO":
                raise RuntimeError("fictional failure")
            return real(project)
        self.s.httpd.page_html = broken
        with chrome() as cdp:
            br = self.go_to(cdp, "ONE")
            br.cdp.call("Runtime.enable", {}, br.sid)
            br.js("window.clarkPage.setProject('TWO')")
            self.assertTrue(wait(lambda: "TWO" in calls, 10), "the server was asked for project TWO's page")
            time.sleep(1)
            self.assertEqual(br.js("typeof window.clarkPage"), "object", "a page is still there")
            self.assertEqual(br.js("document.body.innerText.length > 0"), True)
            self.assertEqual(br.js(BLOCKS) <= 1, True, "never two brand blocks")


if __name__ == "__main__":
    unittest.main()
