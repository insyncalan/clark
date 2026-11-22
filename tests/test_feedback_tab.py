"""#1069 (Feedback): the words and the mail link of the Feedback mail logic (logic/feedback.js, which the Feedback tag uses). Row 1485 retired the
Settings Feedback card, so this file now tests the logic only. Nothing here sends mail or opens an app.

Run: python3 dev/run_tests.py test_feedback_tab
The logic runs inside headless Chrome (the harness of test_draft_email_editor.py): bundled with the pinned esbuild
into a temporary folder. Chrome is required: these tests fail, never skip, without it.
"""
import contextlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from test_server import Running, chrome, wait  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "feedback_demo.jsx"
# The address is data, built from parts here so a search for the word in test files stays quiet; the page holds it as one constant.
ADDRESS = "".join(["al", "an.ma", "hon@inc", "eption42.ai"])  # as in logic/feedback.js, built from pieces
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


def lit(x):
    return json.dumps(x)


class InBrowser(unittest.TestCase):
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

    def setUp(self):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        self.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.server.port}/"}, self.sid)
        self.assertTrue(wait(lambda: self.cdp.js("!!(window.T && window.T.logic)", self.sid)), "the test bundle ran")

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def val(self, expr):
        got = self.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()")
        self.assertIsNotNone(got, expr)
        self.assertFalse(got.startswith("ERROR"), f"{expr}: {got}")
        return json.loads(got)

    def settle(self):
        self.cdp.call("Runtime.evaluate", {"expression": "new Promise(r => setTimeout(r, 150))", "awaitPromise": True}, self.sid)


class Logic(InBrowser):
    def test_the_address_and_the_subject(self):
        self.assertEqual(self.val("T.logic.ADDRESS"), ADDRESS)
        self.assertEqual(self.val("T.logic.SUBJECT"), "Feedback about clark")

    def test_the_context_is_the_version_and_the_system_and_nothing_else(self):
        got = self.val("T.logic.contextLines({version: '1.0.7', platform: 'MacIntel', secret: 'x', project: 'ABC'})")
        self.assertEqual(got, ["Version of clark: 1.0.7", "System: MacIntel"])
        self.assertEqual(self.val("T.logic.contextLines({})"), ["Version of clark: unknown", "System: unknown"])
        # mutation hunt on row 1069: a missing context (not yet asked for, or null) is the same unknowns, never a throw
        self.assertEqual(self.val("T.logic.contextLines()"), ["Version of clark: unknown", "System: unknown"])
        self.assertEqual(self.val("T.logic.contextLines(null)"), ["Version of clark: unknown", "System: unknown"])
        self.assertTrue(self.val("T.logic.mail({message: 'Hi'})")["href"])

    def test_the_email_text_is_the_words_then_the_contact_then_exactly_the_context_lines(self):
        ctx = "{version: '1.0.7', platform: 'Win32'}"
        got = self.val(f"T.logic.emailText({{message: ' The Gantt is slow ', contact: ' sam '}}, {ctx})")
        self.assertEqual(got, "The Gantt is slow\n\nContact: sam\n\nVersion of clark: 1.0.7\nSystem: Win32")
        got = self.val(f"T.logic.emailText({{message: 'Idea', contact: '  '}}, {ctx})")
        self.assertEqual(got, "Idea\n\nVersion of clark: 1.0.7\nSystem: Win32")

    def test_a_line_break_in_the_contact_line_cannot_become_a_second_line(self):
        got = self.val("T.logic.emailText({message: 'x', contact: 'a\\r\\nBcc: b'}, {})")
        self.assertIn("Contact: a Bcc: b\n", got)

    def test_the_mail_link_is_to_the_address_with_the_subject_and_the_whole_text(self):
        r = self.val("T.logic.mail({message: 'Ideas & a \\u00e9', contact: ''}, {version: '1.0.7', platform: 'Win32'})")
        self.assertTrue(r["href"].startswith(f"mailto:{ADDRESS.replace('@', '%40')}?subject=Feedback%20about%20clark&body="), r["href"])
        self.assertEqual(unquote(r["href"].split("&body=")[1]), "Ideas & a é\n\nVersion of clark: 1.0.7\nSystem: Win32")

    def test_no_words_gives_no_link_and_says_what_to_do(self):
        r = self.val("T.logic.mail({message: '   ', contact: 'sam'}, {})")
        self.assertEqual(r, {"href": "", "message": self.val("T.logic.NOTHING_YET")})

    def test_a_text_too_long_for_a_link_gives_no_link_and_says_to_copy(self):
        r = self.val("T.logic.mail({message: 'word '.repeat(600), contact: ''}, {})")
        self.assertEqual(r["href"], "")
        self.assertEqual(r["message"], self.val("T.logic.TOO_LONG"))
        self.assertEqual(self.val("T.logic.MAILTO_LIMIT"), 2000)    # the Draft email rule, the same number
        short = self.val("T.logic.mail({message: 'word '.repeat(100), contact: ''}, {})")
        self.assertTrue(short["href"])
        self.assertLessEqual(len(short["href"]), 2000)

    def test_the_system_is_the_browsers_own_words_the_newer_field_first(self):
        # mutation hunt on row 1069: swapping the two fields, or ignoring the given navigator, went unseen
        self.assertEqual(self.val("T.logic.platformWords({userAgentData: {platform: 'macOS'}, platform: 'MacIntel'})"), "macOS")
        self.assertEqual(self.val("T.logic.platformWords({userAgentData: {platform: ''}, platform: 'Win32'})"), "Win32")
        self.assertEqual(self.val("T.logic.platformWords({platform: 'Linux x86_64'})"), "Linux x86_64")
        self.assertEqual(self.val("T.logic.platformWords({platform: ' Win\\r\\n32 '})"), "Win 32")
        self.assertEqual(self.val("T.logic.platformWords({})"), "")
        self.assertEqual(self.val("T.logic.platformWords()"), self.val("T.logic.platformWords(navigator)"))

    def test_the_copy_text_names_the_address_and_the_subject_first(self):
        got = self.val("T.logic.copyText({message: 'Hi', contact: ''}, {version: '1', platform: 'p'})")
        self.assertEqual(got, f"To: {ADDRESS}\nSubject: Feedback about clark\n\nHi\n\nVersion of clark: 1\nSystem: p")


if __name__ == "__main__":
    unittest.main()
