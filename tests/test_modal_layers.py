"""#425: everything outside a modal dialog is inert while it is open (src/clark/page/src/edit/modalLayers.js), and exactly what the
dialog made inert is restored when it closes. Run: python3 dev/run_tests.py test_modal_layers
The helper and the Draft email editor run on a bare page shaped like the real one (tests/fixtures/modal_layers_demo.jsx) in headless
Chrome (the #33 harness); no screen on main opens the Draft email yet, so it is mounted the way its host will mount it. The source
tests need no browser. Chrome is required for the page tests: they fail, never skip, without it.
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
DEMO = ROOT / "tests" / "fixtures" / "modal_layers_demo.jsx"
LAYERS = ["header.top", "#main", "#peek", "#ask-panel", "#help-layer"]
_PAGE = {}


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


class Source(unittest.TestCase):
    def test_the_add_box_uses_the_shared_helper_and_no_list_of_its_own(self):
        src = (PAGE_SRC / "edit" / "AddDialog.jsx").read_text(encoding="utf-8")
        self.assertIn("inertBehind(", src)
        self.assertNotIn("BEHIND", src, "the box no longer lists #main and .top by hand")
        self.assertNotIn('setAttribute("inert"', src)


class InBrowser(unittest.TestCase):
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
        self.assertTrue(wait(lambda: self.cdp.js("!!(window.T && window.T.build)", self.sid)), "the test bundle ran")
        self.js("T.build()")

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def inert(self, selector):
        return self.js(f"document.querySelector({json.dumps(selector)}).hasAttribute('inert')")

    def open_draft(self):
        self.js("T.openDraft()")
        self.assertTrue(wait(lambda: self.js("!!document.querySelector('.de') && document.getElementById('peek').hasAttribute('inert')")), "the Draft email opened and the page behind it is held")

    def states(self):
        return {s: self.inert(s) for s in LAYERS + [".toast", ".toasts", "#draft-scrim"] if self.js(f"!!document.querySelector({json.dumps(s)})")}


class Layers(InBrowser):
    def test_the_draft_email_makes_every_other_layer_inert_and_a_toast_button_unreachable(self):
        self.js("document.getElementById('main-b').focus()")
        self.open_draft()
        got = self.states()
        for layer in LAYERS:
            self.assertTrue(got[layer], f"{layer} is inert while the Draft email is open")
        self.assertTrue(got[".toast"], "the toast with Undo and Close is inert")
        self.assertFalse(got[".toasts"], "the message area stays live for a screen reader")
        self.assertFalse(got["#draft-scrim"], "the dialog itself is not inert")
        self.assertTrue(self.js("document.activeElement.closest('.de') !== null"), "focus is inside the dialog")
        self.assertFalse(self.js("[...document.querySelectorAll('button, input')].some(e => !e.closest('.de') && !e.closest('[inert]') && !e.closest('.toasts'))"),
                         "no control outside the dialog can be reached")

    def test_closing_it_gives_back_exactly_what_it_took_and_focus_goes_back(self):
        self.js("document.getElementById('main-b').focus()")
        self.open_draft()
        self.js("document.querySelector('.de button.pk-btn').click()")      # Close
        self.assertTrue(wait(lambda: not self.js("!!document.querySelector('.de')")), "Close closed it")
        self.assertEqual(self.js("T.closed"), 1)
        self.assertFalse(any(self.states().values()), f"nothing is inert any more: {self.states()}")
        self.assertEqual(self.js("document.activeElement.id"), "main-b", "focus went back to what opened it")

    def test_something_that_was_inert_before_stays_inert_after(self):
        self.js("document.getElementById('peek').setAttribute('inert', '')")
        self.js("T.openDraft()")
        self.assertTrue(wait(lambda: self.js("!!document.querySelector('.de') && document.getElementById('main').hasAttribute('inert')")))
        self.js("T.closeDraft()")
        self.assertTrue(self.inert("#peek"), "the peek was inert before and still is")
        self.assertFalse(self.inert("#main"))
        self.assertFalse(self.inert("#ask-panel"))

    def test_a_second_dialog_does_not_undo_the_first(self):
        a = self.js("T.hold('main')")                          # a dialog that holds the page behind it (its own element is #main here)
        self.assertTrue(self.inert("#peek"))
        self.js("T.openDraft()")                               # a second one opens over it
        self.assertTrue(wait(lambda: self.js("!!document.querySelector('.de') && document.getElementById('main').hasAttribute('inert')")))
        self.assertTrue(self.inert("#peek"))
        self.js("T.closeDraft()")
        self.assertTrue(self.inert("#peek"), "the first dialog still has the peek inert")
        self.assertFalse(self.inert("#main"), "#main is the first dialog's own element")
        self.js(f"T.release({a})")
        self.assertFalse(any(self.states().values()), f"all released: {self.states()}")
        self.js(f"T.release({a})")                             # a second release does nothing (no error, nothing re-set)
        self.assertFalse(any(self.states().values()))

    def test_the_last_dialog_to_close_releases_the_page(self):
        a = self.js("T.hold('main')")
        b = self.js("T.hold('peek')")
        self.assertTrue(self.inert("#ask-panel"))
        self.js(f"T.release({a})")
        self.assertTrue(self.inert("#ask-panel"), "the second dialog still holds the ask panel")
        self.assertFalse(self.inert("#peek"), "the peek is the second dialog's own element")
        self.js(f"T.release({b})")
        self.assertFalse(any(self.states().values()), self.states())


if __name__ == "__main__":
    unittest.main()
