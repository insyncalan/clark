"""Targets of 24 px in the places test_sizes does not open: a Work item's peek, a milestone's peek, the Help peek, every Help tab and Settings.

Run: python3 dev/run_tests.py test_sizes_panels
Same audit as test_sizes (text of 12 px, hit boxes of 24 by 24 CSS px, empty allow-list), at 1400 and 900 px only.
Chrome is required: this test fails, never skips, without it.
"""
import json
import unittest

from _paths import SRC  # noqa: F401

import _testpage as testpage
from test_page import navigate
from test_server import Running, chrome, wait
from test_sizes import AUDIT, ALLOWED, DATA, ONE

PAGES = [""]      # Settings is one page of cards


class SizesPanels(unittest.TestCase):
    def test_peeks_help_and_every_settings_page_have_targets_of_24px(self):
        s = Running(data_for=lambda code, archived=None: DATA.get(code), projects=lambda archived=False: ONE, page_html=lambda: testpage.html())
        self.addCleanup(s.close)
        found = []
        with chrome() as cdp:
            sid = navigate(cdp, s.port, "#work&p=ABC")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#work')", sid)), "Work drew")

            def audit(where):
                cdp.call("Runtime.evaluate", {"expression": "new Promise(r => setTimeout(r, 400))", "awaitPromise": True}, sid)
                found.extend(f"{where}: {g}" for g in sorted(set(json.loads(cdp.js(AUDIT % json.dumps(list(ALLOWED)), sid)))))

            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                for view, kind, ident in (("work", "item", None), ("milestones", "milestone", "ABC-M-001")):
                    cdp.js(f"location.hash = '#{view}&p=ABC'", sid)
                    self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector('#{view}')", sid)), f"{view} drew")
                    if ident is None:       # the first row Work lists
                        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#work-list tr[data-id]')", sid)), "Work lists a row")
                        ident = cdp.js("document.querySelector('#work-list tr[data-id]').dataset.id", sid)
                    cdp.js(f"window.clarkPage.openPeek('{ident}', '{kind}')", sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek')", sid)), f"the {kind} peek opened: {cdp.js('typeof window.clarkPage', sid)} {ident} {cdp.js('location.hash', sid)} {cdp.js('document.body.innerText.slice(0,300)', sid)}")
                    audit(f"{w}px {view} peek")
                    cdp.js("window.clarkPage.closePeek()", sid)
                    cdp.js("window.clarkPage.help.peek.open(%s)" % json.dumps(view), sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#help-peek')", sid)), f"the Help peek opened on {view}")
                    audit(f"{w}px {view} Help peek")
                    cdp.js("window.clarkPage.help.peek.close()", sid)
                cdp.js("window.clarkPage.help.open()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#help')", sid)), "Help opened")
                for i in range(cdp.js("document.querySelectorAll('#help [role=tab]').length", sid)):
                    cdp.js("document.querySelectorAll('#help [role=tab]')[%d].click()" % i, sid)
                    audit(f"{w}px Help tab {i}")
                cdp.js("window.clarkPage.help.close()", sid)
                for pg in PAGES:
                    cdp.js(f"location.hash = '#settings&p=ABC'", sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.frame.set-head')", sid)), f"Settings drew")
                    audit(f"{w}px Settings")
        self.assertEqual(found, [], "every offender, by width and place:\n" + "\n".join(found))


if __name__ == "__main__":
    unittest.main()
