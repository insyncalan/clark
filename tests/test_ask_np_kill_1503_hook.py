"""Row 1503: the survivors of the mutation sweep in the hook behind a project's own asking line (edit/NewProjects.jsx, useNew).

Run: python3 dev/run_tests.py test_ask_np_kill_1503_hook
The page never moves from one project to another under the mounted line, so these run the line on a bare page (tests/fixtures/ask_here_hook_demo.jsx) where the
same line is drawn again for another project, in the same place: the old project's value goes while the next is read, the next project is read, and an answer
that comes late for a project that was left, or after the line is gone, shows nothing. Classic markup, 1400. Chrome is required."""
import contextlib
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS
import sys

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from test_server import Running, chrome, wait  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "ask_here_hook_demo.jsx"
LINE = "document.querySelector('#ask-here-state')"
_PAGE = {}


def demo_html():
    if "html" not in _PAGE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(DEMO), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        css = (build_page.TOKENS.read_text(encoding="utf-8") + (build_page.PAGE / "shell.css").read_text(encoding="utf-8")).replace("</style", "<\\/style")
        _PAGE["html"] = (f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><title>t</title><style>\n{css}</style></head>\n'
                         f'<body><div id="root"></div>\n<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


class Hook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=demo_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def setUp(self):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        self.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.server.port}/"}, self.sid)
        self.assertTrue(wait(lambda: self.js("!!window.T"), 20), "the test bundle ran")

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def until(self, expr, what):
        self.assertTrue(wait(lambda: self.js(expr), 10), f"{what}: {expr}")

    def line(self):
        return self.js(f"{LINE} ? {LINE}.textContent : null")

    def settle(self):
        self.cdp.call("Runtime.evaluate", {"expression": "new Promise(r => setTimeout(r, 300))", "awaitPromise": True}, self.sid)

    def shown_for_abc_off(self):
        self.js("T.show('ABC')")
        self.until("T.reads.length === 1", "ABC is read")
        self.js("T.answer('ABC', true)")
        self.until(f"!!{LINE} && {LINE}.textContent === 'Asking is off for ABC.'", "ABC reads off")

    def test_the_old_projects_value_goes_while_the_next_is_read(self):
        """ABC reads off; the line is drawn for XYZ, whose read waits: nothing of ABC's value stands under XYZ's name."""
        self.shown_for_abc_off()
        self.js("T.show('XYZ')")
        self.until("T.reads.length === 2", "XYZ is read")
        self.settle()
        self.assertIsNone(self.line(), "no line while XYZ is read")
        self.assertFalse(self.js("!!document.querySelector('[data-ask-here]')"), "no button while XYZ is read")
        self.js("T.answer('XYZ', false)")
        self.until(f"!!{LINE} && {LINE}.textContent === 'Asking is on for XYZ.'", "XYZ reads on")

    def test_the_next_project_is_read_and_each_shows_its_own_value(self):
        """The line moves from ABC (off) to XYZ (on) and back: each is read (in that order) and shows its own value."""
        self.shown_for_abc_off()
        self.js("T.show('XYZ')")
        self.until("T.reads.length === 2", "a read for XYZ went out")
        self.assertEqual(self.js("T.reads"), ["ABC", "XYZ"])
        self.js("T.answer('XYZ', false)")
        self.until(f"!!{LINE} && {LINE}.textContent === 'Asking is on for XYZ.'", "XYZ reads on")
        self.js("T.show('ABC')")
        self.until("T.reads.length === 3", "a read for ABC went out again")
        self.js("T.answer('ABC', true)")
        self.until(f"!!{LINE} && {LINE}.textContent === 'Asking is off for ABC.'", "ABC reads off again")
        self.assertEqual(self.js("T.reads"), ["ABC", "XYZ", "ABC"])

    def test_a_late_answer_for_a_project_that_was_left_shows_nothing_while_the_next_waits(self):
        """ABC's read is out; the line moves to XYZ (waiting); ABC's answer (off) comes: no line, XYZ is not given ABC's value."""
        self.js("T.show('ABC')")
        self.until("T.reads.length === 1", "ABC is read")
        self.js("T.show('XYZ')")
        self.until("T.reads.length === 2", "XYZ is read")
        self.js("T.answer('ABC', true)")
        self.settle()
        self.assertIsNone(self.line(), "ABC's late answer did not draw a line for XYZ")

    def test_a_late_answer_for_a_project_that_was_left_does_not_replace_the_next_ones_value(self):
        """ABC's read is out; the line moves to XYZ, which answers (on); then ABC's answer (off) comes: XYZ still reads on."""
        self.js("T.show('ABC')")
        self.until("T.reads.length === 1", "ABC is read")
        self.js("T.show('XYZ')")
        self.until("T.reads.length === 2", "XYZ is read")
        self.js("T.answer('XYZ', false)")
        self.until(f"!!{LINE} && {LINE}.textContent === 'Asking is on for XYZ.'", "XYZ reads on")
        self.js("T.answer('ABC', true)")
        self.settle()
        self.assertEqual(self.line(), "Asking is on for XYZ.")

    def test_an_answer_after_the_line_is_gone_draws_nothing_and_a_later_line_is_its_own(self):
        """ABC's read is out; the line is taken away; ABC's answer comes: nothing is drawn. Drawn again for XYZ it reads XYZ, not the answer that came."""
        self.js("T.show('ABC')")
        self.until("T.reads.length === 1", "ABC is read")
        self.js("T.hide()")
        self.js("T.answer('ABC', true)")
        self.settle()
        self.assertIsNone(self.line(), "nothing drawn for an answer that came after the line went")
        self.js("T.show('ABC')")
        self.until("T.reads.length === 2", "a new line reads again")
        self.js("T.answer('ABC', false)")
        self.until(f"!!{LINE} && {LINE}.textContent === 'Asking is on for ABC.'", "the new line reads its own answer")


if __name__ == "__main__":
    unittest.main()
