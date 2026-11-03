"""#631: the page sends its own time zone as X-Clark-Tz (src/clark/page/src/zone.js): on every call in api.js and on the "still
here" every 10 seconds (app.js), in headless Chrome against the real server, with Chrome's zone set to Dubai and then New York.

Run: python3 dev/run_tests.py test_zone_page
The published page (page-view.html) has none of it.
"""
import re
import tempfile
import unittest
from unittest import mock

from _paths import ROOT  # noqa: F401

from clark import appfiles, idle, page, server as sv  # noqa: E402
from test_page import DATA, navigate  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402

SRC = ROOT / "src" / "clark" / "page" / "src"


class Source(unittest.TestCase):
    def test_every_call_in_api_js_carries_the_zone(self):
        js = (SRC / "api.js").read_text(encoding="utf-8")
        calls = re.findall(r'"X-Clark-Token": token\(\)[^}]*', js)
        self.assertGreater(len(calls), 10)
        self.assertEqual([c for c in calls if "...zoneHeaders()" not in c], [], "a call without the zone")
        self.assertIn('import { zoneHeaders } from "./zone.js";', js)

    def test_the_header_name_is_the_servers(self):
        js = (SRC / "zone.js").read_text(encoding="utf-8")
        self.assertIn(f'export const ZONE_HEADER = "{sv.ZONE_HEADER}";', js)
        self.assertIn("resolvedOptions().timeZone", js)

    def test_the_published_page_has_none_of_it(self):
        view = (ROOT / "src" / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        self.assertNotIn(sv.ZONE_HEADER, view)


class Live(unittest.TestCase):
    def setUp(self):
        self.s = Running(data_for=DATA.get, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(self.s.close)
        self.zones = []
        for patch in (mock.patch.dict(sv.OPEN_GET_ROUTES, appfiles.open_files()), mock.patch.object(sv, "IDLE", idle.Idle(stop_after=60)),
                      mock.patch.object(sv, "ZONE", self.zones.append)):
            patch.start()
            self.addCleanup(patch.stop)

    def test_still_here_carries_the_browsers_zone_and_follows_a_change(self):
        with chrome() as cdp:
            sid = navigate(cdp, self.s.port, "#dashboard&p=ABC")
            self.assertTrue(wait(lambda: len(self.zones) >= 1), "the page said it is here")
            for name in ("Asia/Dubai", "America/New_York"):
                cdp.call("Emulation.setTimezoneOverride", {"timezoneId": name}, sid)
                self.assertEqual(cdp.js("Intl.DateTimeFormat().resolvedOptions().timeZone", sid), name)
                cdp.js("document.dispatchEvent(new Event('visibilitychange'))", sid)
                self.assertTrue(wait(lambda: name in self.zones), f"{name} was not sent: {self.zones}")


if __name__ == "__main__":
    unittest.main()
