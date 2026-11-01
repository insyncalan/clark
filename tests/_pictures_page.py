"""The Pictures group's bare page (#96): the four view parts and the shrink step bundled by the pinned esbuild in a temporary
folder (tests/fixtures/pictures_demo.js), served by a test server, for the parity and shrink tests. Fictional data only."""
import contextlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC
from test_server import Running, chrome, wait

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "pictures_demo.js"
_PAGE = {}


def bare_page():
    if "html" not in _PAGE:
        sys.path.insert(0, str(ROOT / "dev" / "tools"))
        import build_page
        import esbuild
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(DEMO), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        _PAGE["html"] = (f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><title>t</title></head>\n'
                         f'<body><div id="root"></div>\n<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


class BarePage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=bare_page)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{cls.server.port}/"}, cls.sid)
        assert wait(lambda: cls.cdp.js("!!window.P", cls.sid)), "the test bundle ran"

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def val(self, expr, wait_for_promise=False):
        if wait_for_promise:
            self.cdp.js(f"window.__got = undefined; Promise.resolve({expr}).then(v => window.__got = JSON.stringify(v), e => window.__got = 'ERROR ' + e.message)", self.sid)
            self.assertTrue(wait(lambda: self.cdp.js("window.__got !== undefined", self.sid), 20), expr)
            got = self.cdp.js("window.__got", self.sid)
        else:
            got = self.cdp.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()", self.sid)
        self.assertIsNotNone(got, expr)
        self.assertFalse(got.startswith("ERROR"), f"{expr}: {got}")
        return json.loads(got) if got != "undefined" else None

    def parity(self, kind, bodies):
        """The page's shown() of each stored body is what published() puts in the file (FR-11: View is what the client sees)."""
        from _pictures import published
        for value in bodies:
            with self.subTest(kind=kind, value=str(value)[:80]):
                want = published(kind, value)
                got = self.val(f"P.shown({json.dumps(kind)}, {json.dumps(value)})")
                self.assertEqual(got, want["content"] if want else None)
                section = {"id": "ABC-S-099", "type": kind, "body": json.dumps(value)}
                self.assertEqual(self.val(f"P.isEmpty({json.dumps(kind)}, {json.dumps(section)})"), want is None)
                if want:
                    filed = {"id": "ABC-S-099", "type": kind, **want}
                    self.assertIs(self.val(f"P.isEmpty({json.dumps(kind)}, {json.dumps(filed)})"), False, "the file's content draws")
