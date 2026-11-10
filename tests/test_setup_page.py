"""The first-run setup page (row 836, step 5) in headless Chrome: every state (loading, all ready, one problem with its fix line, many
problems, refused), Check again and the folder chooser, at 1400 and 900 pixels wide in light and dark, with no sideways scroll.
The checks and the chooser are fakes behind the page's seams; the server's setup mode is not built yet.

Run: python3 dev/run_tests.py test_setup_page
Chrome is required: these tests fail, never skip, without it. Fixture lines are made up.
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
DEMO = ROOT / "tests" / "fixtures" / "setup_demo.jsx"
READY = {"id": "python", "status": "ready", "words": "Python 3.11.4 is ready."}
CHROME = {"id": "chrome", "status": "ready", "words": "Chrome is there, so clark opens in Chrome."}
DATA = {"id": "data", "status": "ready", "words": "Your clark data can be saved in ~/clark-data."}
ONEDRIVE = {"id": "onedrive", "status": "fix", "words": "Your clark data is set to go in ~/OneDrive/clark, which is inside OneDrive. "
            "OneDrive copies files while they are being written, which damages the data. Choose a folder on this computer that it doesn't sync."}
NOCHROME = {"id": "chrome", "status": "advice", "words": "Chrome wasn't found, so clark will open in your usual browser."}
MIXED = {"id": "versions", "status": "fix", "words": "These clark files are not all from the same version, so clark will not start. "
         "Move the clark folder aside (rename it) and unzip the download again."}
OK = lambda body, status=200: {"status": status, "body": body}  # noqa: E731
_PAGE = {}


def test_page_html():
    if "html" not in _PAGE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(DEMO), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        css = (build_page.TOKENS.read_text(encoding="utf-8") + (build_page.PAGE / "shell.css").read_text(encoding="utf-8"))
        css = css.replace("</style", "<\\/style")
        _PAGE["html"] = (f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8">'
                         f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>t</title>'
                         f'<style>\n{css}</style></head>\n<body><div id="root"></div>\n'
                         f'<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


class Setup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=test_page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, cls.sid)

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def load(self, width=1400, theme="light"):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        self.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.server.port}/"}, self.sid)
        self.assertTrue(wait(lambda: self.cdp.js("!!(window.T && window.T.logic)", self.sid)), "the test bundle ran")
        self.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}")

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def replies(self, **kw):
        self.js(f"Object.assign(T.replies, {json.dumps(kw)})")

    def settle(self):
        self.cdp.call("Runtime.evaluate", {"expression": "new Promise(r => setTimeout(r, 100))", "awaitPromise": True}, self.sid)
        self.assertTrue(wait(lambda: self.js("document.getAnimations().length === 0")), "the animations finished")

    def mount(self):
        self.js("T.mount()")
        self.settle()

    def click(self, selector):
        self.js(f"document.querySelector({json.dumps(selector)}).click()")
        self.settle()

    def text(self, selector):
        return self.js(f"(document.querySelector({json.dumps(selector)}) || {{}}).textContent || ''")

    def present(self, selector):
        return bool(self.js(f"!!document.querySelector({json.dumps(selector)})"))

    def lines(self):
        return json.loads(self.js("JSON.stringify([...document.querySelectorAll('[data-line]')].map(e => [e.dataset.line, e.textContent]))"))

    def no_sideways_scroll(self, label):
        self.assertTrue(self.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), label)

    def each_view(self, body):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                self.load(width, theme)
                body()
                self.no_sideways_scroll(f"{width} {theme}")

    def test_all_ready(self):
        def body():
            self.replies(checks=OK([READY, CHROME, DATA]))
            self.mount()
            self.assertEqual(self.text("h1"), "Setting up clark")
            self.assertEqual(self.lines(), [[c["id"], c["words"]] for c in (READY, CHROME, DATA)])
            self.assertEqual(self.text("#setup-ready"), "Everything is ready. Opening clark.")
            self.assertEqual(self.js("document.querySelectorAll('.upd-l')[0].textContent"), "Ready:")
            self.assertEqual(self.js("T.ready"), 1)
            self.assertFalse(self.present("p.error"))
        self.each_view(body)

    def test_advice_does_not_stop_the_page_and_is_labelled_as_the_doctor_does(self):
        self.load()
        self.replies(checks=OK({"checks": [READY, NOCHROME]}))
        self.mount()
        self.assertEqual(self.js("document.querySelectorAll('.upd-l')[1].textContent"), "Worth knowing:")
        self.assertTrue(self.present("#setup-ready"))

    def test_one_problem_shows_its_fix_line_and_no_ready_line(self):
        def body():
            self.replies(checks=OK([READY, ONEDRIVE]), folder=OK({"ok": True}))
            self.mount()
            self.assertEqual(dict(self.lines())["onedrive"], ONEDRIVE["words"])
            self.assertEqual(self.js("document.querySelectorAll('.upd-l')[1].textContent"), "To fix:")
            self.assertTrue(self.present("[data-line=onedrive].error"))
            self.assertFalse(self.present("#setup-ready"))
            self.assertEqual(self.js("T.ready"), 0)
            self.assertTrue(self.present("[data-again]") and self.present("[data-folder]"))
        self.each_view(body)

    def test_many_problems_are_all_shown_in_order(self):
        def body():
            self.replies(checks=OK([MIXED, ONEDRIVE, NOCHROME, DATA]))
            self.mount()
            self.assertEqual([i for i, _ in self.lines()], ["versions", "onedrive", "chrome", "data"])
            self.assertEqual(int(self.js("document.querySelectorAll('p.error[data-line]').length")), 2)
        self.each_view(body)

    def test_loading_then_lines(self):
        def body():
            self.js("T.replies.checks = () => new Promise(r => { T.release = () => r({status: 200, body: [{id: 'a', status: 'ready', words: 'Fine.'}]}); })")
            self.mount()
            self.assertEqual(self.text("#setup-loading"), "Checking this computer.")
            self.assertFalse(self.present("[data-again]"))
            self.js("T.release()")
            self.settle()
            self.assertFalse(self.present("#setup-loading"))
            self.assertEqual(self.lines(), [["a", "Fine."]])
        self.each_view(body)

    def test_refused_says_so_and_check_again_asks_again(self):
        def body():
            self.replies(checks=OK({"code": "stale"}, 403))
            self.mount()
            self.assertTrue(self.text("#setup-refused").startswith("The checks could not be read."))
            self.assertFalse(self.present("[data-line]") or self.present("[data-folder]"))
            self.replies(checks=OK([READY]))
            self.click("[data-again]")
            self.assertEqual(self.lines(), [["python", READY["words"]]])
            self.assertFalse(self.present("#setup-refused"))
        self.each_view(body)

    def test_a_list_that_is_not_the_shape_is_refused(self):
        self.load()
        for bad in ({"checks": "x"}, [{"id": "a", "status": "ready"}], [{"id": "a", "status": "ready", "words": 5}], [None]):
            self.replies(checks=OK(bad))
            self.mount()
            self.assertTrue(self.present("#setup-refused"), json.dumps(bad))

    def test_check_again_runs_the_checks_again_and_the_ready_callback_fires_once(self):
        self.load()
        self.replies(checks=OK([ONEDRIVE]))
        self.mount()
        self.replies(checks=OK([READY]))
        self.click("[data-again]")
        self.click("[data-again]")
        self.assertEqual(self.js("T.calls.filter(c => c === 'checks').length"), 3)
        self.assertEqual(self.js("T.ready"), 1)

    def test_the_folder_chooser_rechecks_after_a_choice_and_reports_a_refusal(self):
        self.load()
        self.replies(checks=OK([ONEDRIVE]), folder=OK({"ok": True, "cancelled": True}))
        self.mount()
        self.click("[data-folder]")
        self.assertEqual(self.text("#setup-msg"), "No folder was chosen, so nothing was changed.")
        self.assertEqual(self.js("T.calls.filter(c => c === 'checks').length"), 1)
        self.replies(folder=OK({"ok": False, "message": "Your clark data can't be saved in ~/Locked."}, 409))
        self.click("[data-folder]")
        self.assertEqual(self.text("#setup-msg"), "Your clark data can't be saved in ~/Locked.")
        self.replies(folder=OK({"nonsense": True}, 500))
        self.click("[data-folder]")
        self.assertEqual(self.text("#setup-msg"), "That folder could not be chosen. Nothing was changed.")
        self.replies(folder=OK({"ok": True}), checks=OK([READY]))
        self.click("[data-folder]")
        self.assertFalse(self.present("#setup-msg"))
        self.assertTrue(self.present("#setup-ready"))
        self.assertEqual(self.js("T.calls.filter(c => c === 'checks').length"), 2)

    def test_an_answer_that_arrives_after_the_page_is_gone_does_nothing(self):
        self.load()
        self.js("T.replies.checks = () => new Promise(r => { T.release = () => r({status: 200, body: [{id: 'a', status: 'ready', words: 'Fine.'}]}); })")
        self.mount()
        self.js("T.unmount()")
        self.js("T.release()")
        self.settle()
        self.assertEqual(self.js("T.ready"), 0)
        self.assertFalse(self.present("#setup-ready") or self.present("[data-line]"))


if __name__ == "__main__":
    unittest.main()
