"""#193: the single-key shortcuts switch is on by default, is remembered in the browser, and is read live. The letter keys
themselves are checked in the page's own browser tests. Run: python3 dev/run_tests.py test_single_keys"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
from _clean_html import wait_for
from _paths import ROOT, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402
from test_server import chrome  # noqa: E402

STORE = ROOT / "src" / "clark" / "page" / "src" / "stores"


class Store:
    """stores/keyPrefs.js bundled alone as `KP`, in a Chrome tab."""

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        out = tmp / "kp.js"
        done = esbuild.run(["--bundle", "--format=iife", "--global-name=KP", "--target=es2020", "--tsconfig-raw={}",
                            *build_page.preact_flags(), str(STORE / "keyPrefs.js"), f"--outfile={out}"],
                           cwd=STORE, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        (tmp / "page.html").write_text("<!doctype html><meta charset=utf-8><body><script src=kp.js></script></body>", encoding="utf-8")
        self.chrome = chrome()
        self.cdp = self.chrome.__enter__()
        tid = next(t["targetId"] for t in self.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        self.sid = self.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        self.cdp.call("Page.enable", {}, self.sid)
        self.cdp.call("Page.navigate", {"url": (tmp / "page.html").as_uri()}, self.sid)
        assert wait_for(lambda: self.cdp.js("typeof KP === 'object'", self.sid) is True, 60), "the script did not load"
        return self

    def __exit__(self, *exc):
        self.chrome.__exit__(*exc)
        self.tmp.cleanup()

    def ev(self, expr):
        return self.cdp.js(expr, self.sid)

    def reload(self):
        self.cdp.call("Page.reload", {}, self.sid)
        assert wait_for(lambda: self.cdp.js("typeof KP === 'object'", self.sid) is True, 60), "the script did not reload"


class Switch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = Store().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.page.__exit__(None, None, None)

    def setUp(self):
        self.page.ev("localStorage.removeItem('clark.single-keys')")
        self.page.reload()                          # the switch is read when the page starts: each test starts it fresh

    def test_on_by_default(self):
        self.assertIs(self.page.ev("KP.singleKeys.value"), True)

    def test_off_is_remembered_and_read_live(self):
        self.page.ev("KP.setSingleKeys(false)")
        self.assertIs(self.page.ev("KP.singleKeys.value"), False)
        self.assertEqual(self.page.ev("localStorage.getItem('clark.single-keys')"), "off")

    def test_back_on_is_remembered(self):
        self.page.ev("KP.setSingleKeys(false)")
        self.page.ev("KP.setSingleKeys(true)")
        self.assertEqual(self.page.ev("localStorage.getItem('clark.single-keys')"), "on")


if __name__ == "__main__":
    unittest.main()
