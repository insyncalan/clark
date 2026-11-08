"""Row 107, single load: an address that names a project in its hash (#dashboard&p=CODE) but has no ?project= is served ONCE when that
project is on Generic (the page cannot know the brand from the hash, so it reads the project's data first and goes to GET /?project=<code>
only if the project has a brand of its own). Before, report.js replaced the address at the start of EVERY such load, so the page loaded
twice and a slow computer's first poll landed in the window ("Inspected target navigated or closed"). The count is the server's: one
GET / is one document load. A brand of its own still gets its own page (test_brand_follow_e2e), and an address that already carries the
project's ?project= is one load as before.
Run: python3 dev/run_tests.py test_single_load_e2e   (one browser file at a time). Chrome is required: this test fails, never skips.
"""
import unittest

import _paths  # noqa: F401  (puts src/ on the path)
import _testpage as testpage
from test_brand_route import NAVY, make_brands, seam
from test_gantt_e2e import Browser
from test_server import Running, chrome

BRANDS = {"ONE": "one-brand"}                     # the stand-in for projects.brand; every other code is Generic


def data(code):
    return {"project": {"code": code, "name": f"Project {code.title()}", "brand": BRANDS.get(code, "generic")},
            "actions": [{"id": f"{code}-A-001", "action": "Agree the plan"}]}


class SingleLoad(unittest.TestCase):
    def setUp(self):
        self.folders = make_brands(self)
        self.seen = []
        self.s = Running(data_for=lambda code, archived=None: data(code), projects=lambda archived=False: [],
                         page_html=seam(self.folders, seen=self.seen, base=testpage.html))
        self.addCleanup(self.s.close)
        self.base = f"http://127.0.0.1:{self.s.port}/"

    def show(self, cdp, address, name):
        br = Browser(self, cdp, self.s.port)
        br.cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": "window.__first = window.__first || performance.now();"}, br.sid)
        br.visit(self.base + address)
        br.until(f"document.body.innerText.includes({name!r})", "the project's page is drawn")
        return br

    def test_a_generic_project_in_the_hash_is_one_load(self):
        with chrome() as cdp:
            br = self.show(cdp, "#dashboard&p=THREE", "Project Three")
            self.assertEqual(self.seen, [None], "the page was served once: no GET /?project=THREE")
            self.assertEqual(br.js("location.search"), "")
            self.assertEqual(br.js("document.querySelectorAll('style#brand-local').length"), 0)

    def test_a_brand_of_its_own_still_gets_its_own_page(self):
        with chrome() as cdp:
            br = self.show(cdp, "#dashboard&p=ONE", "Project One")
            self.assertEqual(self.seen, [None, "ONE"], "the brand is the server's: the page is asked for once more")
            br.until(f"getComputedStyle(document.documentElement).getPropertyValue('--brand-navy').trim() === {NAVY['ONE']!r}", "ONE's navy")
            self.assertEqual(br.js("location.search"), "?project=ONE")

    def test_the_address_that_names_its_project_is_one_load(self):
        with chrome() as cdp:
            self.show(cdp, "?project=ONE#dashboard&p=ONE", "Project One")
            self.assertEqual(self.seen, ["ONE"])

    def test_a_generic_project_from_a_branded_page_is_the_plain_page(self):
        with chrome() as cdp:
            br = self.show(cdp, "?project=ONE#dashboard&p=THREE", "Project Three")
            self.assertEqual(self.seen, ["ONE", "THREE"], "the branded page cannot stay for another project")
            self.assertEqual(br.js("document.querySelectorAll('style#brand-local').length"), 0)


if __name__ == "__main__":
    unittest.main()
