"""Row 1622: the test helper js() waits for a promise, so a pause written as a promise really pauses.

Run: python3 dev/run_tests.py test_js_await_1622
Before this row js() did not ask Chrome to wait, so js("new Promise(r => setTimeout(r, 1500))") came back at once and every
such "sleep" in the tests was a no-op. Chrome is required (it fails, never skips, without Chrome)."""
import time
import unittest
from pathlib import Path

from test_server import CHROME, chrome


def page_session(cdp):
    tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
    return cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]


class Js(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert Path(CHROME).is_file(), f"Chrome is needed for the required browser tests: set CLARK_CHROME, or put google-chrome or chromium on the PATH ({CHROME!r})"

    def test_a_promise_of_300_ms_is_waited_for(self):
        with chrome() as cdp:
            sid = page_session(cdp)
            start = time.monotonic()
            value = cdp.js("new Promise(r => setTimeout(() => r('done'), 300))", sid)
            took = time.monotonic() - start
            self.assertEqual(value, "done", "js() hands back what the promise settled with, not the promise")
            self.assertGreaterEqual(took, 0.3, f"js() came back after {took:.3f} s, before the 300 ms promise was over")

    def test_a_value_that_is_not_a_promise_comes_back_as_before(self):
        with chrome() as cdp:
            sid = page_session(cdp)
            self.assertEqual(cdp.js("1 + 1", sid), 2)
            self.assertEqual(cdp.js("({a: [1, 'x']})", sid), {"a": [1, "x"]})
            self.assertIsNone(cdp.js("undefined", sid), "no value is still None")


if __name__ == "__main__":
    unittest.main()
