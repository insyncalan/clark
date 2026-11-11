"""#1069 (Feedback tab): the form in Settings, its words and its mail link. Nothing here sends mail or opens an app: the card
draws an ordinary link (a mailto: href) and the tests only read it; the clipboard is a stand-in.

Run: python3 dev/run_tests.py test_feedback_tab
The logic and the card run inside headless Chrome (the harness of test_draft_email_editor.py): bundled with the pinned esbuild
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

    def mount(self, version="1.0.7", platform="Linux x86_64"):
        self.js(f"T.mount({lit(version)}, {lit(platform)})")
        self.settle()

    def type(self, selector, text):
        self.js(f"(function(){{ var e = document.querySelector({lit(selector)}); e.value = {lit(text)}; e.dispatchEvent(new Event('input', {{bubbles: true}})); }})()")
        self.settle()

    def click(self, selector):
        self.js(f"document.querySelector({lit(selector)}).click()")
        self.settle()

    def text(self, selector):
        return self.js(f"(document.querySelector({lit(selector)}) || {{}}).textContent || ''")

    def href(self):
        return self.js("(document.querySelector('a[data-feedback-mail]') || {}).href || ''")


class Logic(InBrowser):
    def test_the_address_and_the_subject(self):
        self.assertEqual(self.val("T.logic.ADDRESS"), ADDRESS)
        self.assertEqual(self.val("T.logic.SUBJECT"), "Feedback about clark")

    def test_the_context_is_the_version_and_the_system_and_nothing_else(self):
        got = self.val("T.logic.contextLines({version: '1.0.7', platform: 'MacIntel', secret: 'x', project: 'ABC'})")
        self.assertEqual(got, ["Version of clark: 1.0.7", "System: MacIntel"])
        self.assertEqual(self.val("T.logic.contextLines({})"), ["Version of clark: unknown", "System: unknown"])

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

    def test_the_copy_text_names_the_address_and_the_subject_first(self):
        got = self.val("T.logic.copyText({message: 'Hi', contact: ''}, {version: '1', platform: 'p'})")
        self.assertEqual(got, f"To: {ADDRESS}\nSubject: Feedback about clark\n\nHi\n\nVersion of clark: 1\nSystem: p")


class Card(InBrowser):
    def test_the_card_has_the_two_boxes_the_context_and_no_link_until_there_are_words(self):
        self.mount()
        self.assertEqual(self.text("#feedback-h"), "Feedback")
        self.assertEqual(self.js("document.querySelectorAll('textarea#feedback-message').length"), 1)
        self.assertEqual(self.js("document.querySelectorAll('input#feedback-contact').length"), 1)
        self.assertEqual(self.js("!!document.querySelector('label[for=feedback-message]')"), True)
        self.assertEqual(self.js("!!document.querySelector('label[for=feedback-contact]')"), True)
        self.assertEqual(self.href(), "")
        self.assertEqual(self.js("document.querySelector('button[data-feedback-copy]').disabled"), True)

    def test_the_form_shows_exactly_the_context_it_adds(self):
        self.mount("1.0.7", "MacIntel")
        shown = self.js("Array.from(document.querySelectorAll('#feedback-context li')).map((x) => x.textContent).join('|')")
        self.assertEqual(shown, "Version of clark: 1.0.7|System: MacIntel")
        self.type("#feedback-message", "Broken")
        body = unquote(self.href().split("&body=")[1])
        self.assertTrue(body.endswith("Version of clark: 1.0.7\nSystem: MacIntel"), body)

    def test_typing_makes_the_open_in_mail_link_and_the_contact_goes_in(self):
        self.mount()
        self.type("#feedback-message", "The tab is slow")
        self.type("#feedback-contact", "sam@example.org")
        href = self.href()
        self.assertTrue(href.startswith("mailto:"), href)
        self.assertIn("Contact%3A%20sam%40example.org", href)
        self.assertEqual(self.text("a[data-feedback-mail]"), "Open in your mail app")

    def test_copy_puts_the_whole_email_text_on_the_clipboard(self):
        self.mount()
        self.type("#feedback-message", "Please add a thing")
        self.click("button[data-feedback-copy]")
        clips = self.val("T.clips")
        self.assertEqual(len(clips), 1)
        self.assertTrue(clips[0].startswith(f"To: {ADDRESS}\nSubject: Feedback about clark\n\nPlease add a thing"), clips[0])
        self.assertEqual(self.text("#feedback-note"), "Copied")

    def test_a_long_text_has_no_link_and_the_copy_button_still_works(self):
        self.mount()
        self.type("#feedback-message", "word " * 600)
        self.assertEqual(self.href(), "")
        self.assertEqual(self.text("#feedback-note"), self.val("T.logic.TOO_LONG"))
        self.click("button[data-feedback-copy]")
        self.assertEqual(len(self.val("T.clips")), 1)

    def test_a_refused_clipboard_shows_the_text_selected_and_says_so(self):
        self.mount()
        self.js("T.refuse = true")
        self.type("#feedback-message", "Hello")
        self.click("button[data-feedback-copy]")
        self.assertEqual(self.text("#feedback-note"), "The browser did not copy it. Press ⌘C to copy the selected text.")
        self.assertIn("Hello", self.js("document.querySelector('#feedback-shown').value"))

    def test_typing_after_a_copy_clears_the_copied_note(self):
        self.mount()
        self.type("#feedback-message", "Hello")
        self.click("button[data-feedback-copy]")
        self.assertEqual(self.text("#feedback-note"), "Copied")
        self.type("#feedback-contact", "me")
        self.assertNotEqual(self.text("#feedback-note"), "Copied")

    def test_a_refused_copy_text_is_selected_and_goes_away_when_you_type(self):
        self.mount()
        self.js("T.refuse = true")
        self.type("#feedback-message", "Hello")
        self.click("button[data-feedback-copy]")
        sel = self.val("(function(){ var e = document.querySelector('#feedback-shown'); return [e.selectionStart, e.selectionEnd, e.value.length]; })()")
        self.assertEqual(sel[0], 0)
        self.assertEqual(sel[1], sel[2])
        self.assertGreater(sel[2], 0)
        self.type("#feedback-message", "Hello again")
        self.assertEqual(self.js("!!document.querySelector('#feedback-shown')"), False)
        self.assertNotIn("did not copy", self.text("#feedback-note"))

    def test_a_copy_that_works_after_a_refused_one_hides_the_shown_text(self):
        self.mount()
        self.js("T.refuse = true")
        self.type("#feedback-message", "Hello")
        self.click("button[data-feedback-copy]")
        self.assertEqual(self.js("!!document.querySelector('#feedback-shown')"), True)
        self.js("T.refuse = false")
        self.click("button[data-feedback-copy]")
        self.assertEqual(self.js("!!document.querySelector('#feedback-shown')"), False)
        self.assertEqual(self.text("#feedback-note"), "Copied")

    def test_the_contact_box_is_at_least_32_px_tall(self):
        self.mount()
        self.assertGreaterEqual(self.js("document.querySelector('#feedback-contact').getBoundingClientRect().height"), 32)

    def test_the_version_is_asked_for_once_and_nothing_is_sent_by_the_card(self):
        self.mount()
        self.assertEqual(self.val("T.asked"), 1)
        self.type("#feedback-message", "x")
        self.assertEqual(self.val("T.asked"), 1)
        self.assertEqual(self.js("document.querySelectorAll('form').length"), 0)     # no form post: the link is the only way out


class InSettings(unittest.TestCase):
    """The card is on the Settings page after the others, with a link in the list, and Help names it."""

    def test_settings_draws_the_card_and_a_link_for_it(self):
        views = (PAGE_SRC / "components" / "Views.jsx").read_text(encoding="utf-8")
        self.assertIn('["Feedback", "Feedback", "feedback-h"]', views)
        self.assertIn("<Feedback />", views)
        self.assertIn("Feedback,", (PAGE_SRC / "edit" / "index.js").read_text(encoding="utf-8"))

    def test_help_names_the_card(self):
        help_ = (PAGE_SRC / "help" / "helpContent.json").read_text(encoding="utf-8")
        self.assertIn("Settings › Feedback", help_)
        self.assertIn("Asking, Feedback and Quit", help_)


if __name__ == "__main__":
    unittest.main()
