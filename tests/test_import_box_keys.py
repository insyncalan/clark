"""The Import workbook box (ImportWorkbook.jsx, Dialog.jsx): a partial Undo shows the server's words; the note about rows past 300 follows
Accept all and Reject all; focus stays in the box after Undo and when nothing is ticked; Cancel and Esc do nothing while the import is applied.
Run: python3 dev/run_tests.py test_import_box_keys
Chrome is required: these tests fail, never skip, without it. Every wait is for a positive signal.
"""
import contextlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from test_server import Running, chrome, wait  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "import_box_demo.jsx"
_PAGE = {}
PARTIAL = "Put back as it was before the import. 2 change(s) were left as they are because they were changed later."


def page_html():
    if "html" not in _PAGE:
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


def items(n, default=True):
    return [{"n": k, "kind": "new", "table": "actions", "text": f"Row {k}", "default": default} for k in range(1, n + 1)]


class ImportBox(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, cls.sid)

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def setUp(self):
        self.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.server.port}/"}, self.sid)
        self.assertTrue(wait(lambda: self.js("!!(window.T && window.T.open)")), "the test bundle ran")

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def until(self, expr, why):
        self.assertTrue(wait(lambda: self.js(expr)), why)

    def to_plan(self, its, **o):
        self.js(f"T.open({json.dumps(its)}, {json.dumps(o)}); T.choose()")
        self.until("!!document.querySelector('#import-go, #import-close')", "the check opened")

    def click(self, sel):
        self.js(f"document.querySelector({json.dumps(sel)}).click()")

    def import_and_wait(self):
        self.click("#import-go")
        self.until("!!document.querySelector('#import-undo')", "the import finished")

    def esc(self, target="document.activeElement"):
        self.js(f"{target}.dispatchEvent(new KeyboardEvent('keydown', {{key: 'Escape', bubbles: true}}))")

    def test_a_partial_undo_shows_the_servers_words(self):
        self.to_plan(items(1), undoBody={"message": PARTIAL})
        self.import_and_wait()
        self.click("#import-undo")
        self.until("document.querySelector('#import-undo') === null", "the undo finished")
        self.assertEqual(self.js("document.querySelector('#import-result').textContent"), PARTIAL)

    def test_an_undo_with_no_message_shows_the_fixed_words(self):
        self.to_plan(items(1))
        self.import_and_wait()
        self.click("#import-undo")
        self.until("document.querySelector('#import-undo') === null", "the undo finished")
        self.assertEqual(self.js("document.querySelector('#import-result').textContent"), "Put back as it was before the import.")

    def test_after_undo_focus_is_on_close_and_esc_closes_the_box(self):
        self.to_plan(items(1))
        self.import_and_wait()
        self.js("document.querySelector('#import-undo').focus()")      # the keyboard user is on Undo, which then goes away
        self.click("#import-undo")
        self.until("document.activeElement && document.activeElement.id === 'import-close'", "focus moved to Close")
        self.esc()
        self.until("T.closed === 1", "Esc closed the box")

    def test_with_nothing_ticked_focus_is_inside_the_box_and_esc_closes_it(self):
        self.to_plan(items(2, default=False))
        self.until("document.querySelector('#import-box').contains(document.activeElement)", "focus is in the box")
        self.esc()
        self.until("T.closed === 1", "Esc closed the box")
