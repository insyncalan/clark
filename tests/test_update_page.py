"""Settings › Version and updates, the page's side: the logic (src/clark/page/src/logic/update.js) and the card (edit/Update.jsx),
over a fake server, at 1400 and 900 pixels wide in light and dark. The routes themselves are tests/test_updater.py.

Run: python3 dev/run_tests.py test_update_page
The repo has no Node, so the logic runs inside headless Chrome (the harness test_safety_logic.py uses). Chrome is required: these
tests fail, never skip, without it. Fixture data is made up.
"""
import contextlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from clark import server as sv, update_install as ui, updater as up, updates  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "update_demo.jsx"
PAGE_PY = SRC / "clark" / "page"

STATUS = {"ok": True, "version": "0.3.0", "installed": "Version 0.3.0, released 20-10-2026.", "blocked": None,
          "available": {"version": "0.3.1", "label": "Review 0.3.1"}, "line": None, "last": None, "notice": None, "installing": False}
REVIEW = {"heading": "Version 0.3.0 → 0.3.1. Released 27-10-2026.", "notes": "Fixes a typo.\nAdds a thing.\n",
          "notes_text": "Fixes a typo.\nAdds a thing.\n",
          "replaced": {"label": "Replaced (1 file)", "names": ["src/clark/__init__.py"]},
          "added": {"label": "Added (1 file)", "names": ["src/clark/new.py"]},
          "removed": {"label": "Removed (0 files)", "names": []}, "by_hand": None,
          "checksum": "ab" * 32, "checksum_text": "Checksum of this file: " + "ab" * 32 + ". Compare it with the one on the releases page.",
          "kept": updates.KEPT, "reinstall": False}
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


def lit(x):
    return json.dumps(x)


# The contrast of an element's text with the first background colour behind it, as WCAG counts it.
CONTRAST = """(el => {
  const rgb = s => s.match(/[0-9.]+/g).slice(0, 4).map(Number);
  const lum = c => { const v = c.slice(0, 3).map(x => { x /= 255; return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); });
                     return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]; };
  let n = el, bg = null;
  while (n && n.nodeType === 1) { const c = rgb(getComputedStyle(n).backgroundColor); if (c.length < 4 || c[3] > 0) { bg = c; break; } n = n.parentElement; }
  if (!bg) bg = [255, 255, 255];
  const a = lum(rgb(getComputedStyle(el).color)), b = lum(bg);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
})"""


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
        self.load()

    def load(self, width=1400, height=900, theme="light"):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        self.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.server.port}/"}, self.sid)
        self.assertTrue(wait(lambda: self.cdp.js("!!(window.T && window.T.logic)", self.sid)), "the test bundle ran")
        self.js(f"document.documentElement.dataset.theme = {lit(theme)}")

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def val(self, expr):
        got = self.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()")
        self.assertIsNotNone(got, expr)
        self.assertFalse(got.startswith("ERROR"), f"{expr}: {got}")
        return json.loads(got)

    def settle(self):
        self.cdp.call("Runtime.evaluate", {"expression": "new Promise(r => setTimeout(r, 150))", "awaitPromise": True}, self.sid)

    def replies(self, **kw):
        self.js(f"Object.assign(T.replies, {lit(kw)})")

    def mount(self):
        self.js("T.mount()")
        self.settle()

    def click(self, selector):
        self.js(f"document.querySelector({lit(selector)}).click()")
        self.settle()

    def text(self, selector):
        return self.js(f"(document.querySelector({lit(selector)}) || {{}}).textContent || ''")

    def present(self, selector):
        return bool(self.js(f"!!document.querySelector({lit(selector)})"))

    def calls(self):
        return self.val("T.calls.map(c => c[0])")


class Logic(InBrowser):
    def test_the_sentences_match_the_servers(self):
        for code, text in self.val("T.logic.WORDS").items():
            self.assertEqual(text, up.MESSAGES.get(code) or sv.MESSAGES.get(code), code)

    def test_every_code_the_server_sends_is_known(self):
        sent = set(updates.MESSAGES) | set(ui.MESSAGES) | {"blocked", "data_changed"}
        known = set(self.val("Object.keys(T.logic.WORDS)")) | set(self.val("T.logic.SERVER_SAYS"))
        self.assertEqual(set(), (sent | set(up.MESSAGES) - {"generic", "not_here"}) - known)

    def test_every_word_is_plain_and_none_starts_with_the_product_name(self):
        every = self.val("[...Object.values(T.logic.WORDS), T.logic.GENERIC, T.logic.NOT_ANSWERING, T.logic.STALE, T.logic.LOADING, "
                         "T.logic.TITLE, T.logic.INTRO, T.logic.CANCELLED, T.logic.COPIED, T.logic.NOT_COPIED, T.logic.SLOW, "
                         "T.logic.DISARMED, ...Object.values(T.logic.LABELS)]")
        for text in every:
            self.assertIsNone(re.search(r"(?i)\b(zip|manifest|sha|path|token|json|database|stale)\b", text.replace("Choose zip…", "")), text)
            self.assertFalse(text.startswith(("clark", "Clark")), text)

    def test_answers_known_server_said_and_generic(self):
        self.assertEqual(self.val("T.logic.answerWords(409, {code: 'busy', message: 'ignore me'})"), up.MESSAGES["busy"])
        self.assertEqual(self.val(f"T.logic.answerWords(409, {{code: 'layout', message: {lit(updates.MESSAGES['layout'])}}})"),
                         updates.MESSAGES["layout"])
        for expr in ("T.logic.answerWords(500, {code: 'server_error', message: 'Traceback'})", "T.logic.answerWords(409, {code: 'layout', message: ''})",
                     "T.logic.answerWords(409, null)", "T.logic.answerWords(409, {code: 'layout', message: 'x'.repeat(601)})"):
            self.assertEqual(self.val(expr), self.val("T.logic.GENERIC"), expr)
        self.assertEqual(self.val("T.logic.answerWords(0, null)"), self.val("T.logic.NOT_ANSWERING"))
        self.assertEqual(self.val("T.logic.answerWords(403, {code: 'stale'})"), self.val("T.logic.STALE"))

    def test_the_restart_waits_for_the_new_run(self):
        self.assertEqual("reload", self.val_async("T.logic.waitForRestart((() => { const seq = ['old', 'down', 'down', 'new']; "
                                                  "return () => Promise.resolve(seq.shift() || 'new'); })(), () => Promise.resolve())"))
        self.assertEqual("slow", self.val_async("T.logic.waitForRestart(() => Promise.resolve('down'), () => Promise.resolve(), 5)"))

    def val_async(self, expr):
        got = self.cdp.call("Runtime.evaluate", {"expression": f"({expr}).then(x => JSON.stringify(x))", "awaitPromise": True,
                                                 "returnByValue": True}, self.sid)
        return json.loads(got["result"]["value"])


class Card(InBrowser):
    def setUp(self):
        super().setUp()
        self.replies(status=OK(STATUS), review=OK({"ok": True, "review_id": "r1", "review": REVIEW}),
                     install=OK({"ok": True, "restart": True, "message": up.INSTALLING.format(to="0.3.1")}), who="new")

    def test_installed_and_review_or_up_to_date(self):
        self.mount()
        self.assertEqual(self.text("#update-installed"), "Version 0.3.0, released 20-10-2026.")
        self.assertEqual(self.text("[data-review]"), "Review 0.3.1")
        self.assertEqual(self.text("[data-choose]"), "Choose zip…")
        self.replies(status=OK({**STATUS, "available": None, "line": "Up to date."}))
        self.mount()
        self.assertFalse(self.present("[data-review]"))
        self.assertEqual(self.text("#update-line"), "Up to date.")

    def test_a_copy_that_cannot_update_itself_says_why_and_offers_nothing(self):
        self.replies(status=OK({**STATUS, "available": None, "blocked": updates.MESSAGES["git"]}))
        self.mount()
        self.assertEqual(self.text("#update-blocked"), updates.MESSAGES["git"])
        self.assertFalse(self.present("[data-review]") or self.present("[data-choose]"))

    def test_review_then_install_is_a_second_click_and_the_page_reloads_when_the_new_run_answers(self):
        self.mount()
        self.click("[data-review]")
        self.assertEqual(self.calls(), ["status", "review"], "nothing is installed by the first click")
        self.assertEqual(self.val("T.calls[1][1]"), {"from": "downloads", "reinstall": False})
        panel = self.text("#update-panel")
        for line in (REVIEW["heading"], "Fixes a typo.", REVIEW["checksum_text"], updates.KEPT, "Replaced (1 file)", "Added (1 file)", "Removed (0 files)"):
            self.assertIn(line, panel)
        self.assertEqual("update-heading", self.val("document.activeElement.id"), "focus moves to the review")
        self.assertFalse(self.val("document.querySelector('#update-panel details').open"), "the file names are behind Show the files")
        self.click("[data-install]")
        self.assertEqual(self.val("T.calls[2]"), ["install", "r1"])
        self.assertEqual(1, self.val("T.reloads"))

    def test_copy_puts_the_notes_on_the_clipboard_and_says_so(self):
        self.mount()
        self.click("[data-review]")
        self.click("[data-copy]")
        self.assertEqual(self.val("T.copied"), [REVIEW["notes_text"]])
        self.assertEqual(self.text(".pub-msg"), self.val("T.logic.COPIED"))
        self.js("T.copyFails = true")
        self.click("[data-copy]")
        self.assertEqual(self.text(".pub-msg"), self.val("T.logic.NOT_COPIED"))
        self.js("T.copyFails = false")

    def test_no_notes_says_so_and_offers_no_copy(self):
        self.replies(review=OK({"ok": True, "review_id": "r1", "review": {**REVIEW, "notes": "", "notes_text": updates.NO_NOTES}}))
        self.mount()
        self.click("[data-review]")
        self.assertEqual(self.text("#update-notes"), updates.NO_NOTES)
        self.assertFalse(self.present("[data-copy]"))

    def test_a_refusal_is_one_plain_sentence_and_the_same_version_offers_install_again(self):
        self.replies(review=OK({"ok": False, "code": "same", "message": updates.MESSAGES["same"].format(theirs="0.3.0"), "again": True}, 409))
        self.mount()
        self.click("[data-choose]")
        self.assertEqual(self.val("T.calls[1][1]"), {"from": "file", "reinstall": False})
        self.assertEqual(self.text(".pub-msg"), updates.MESSAGES["same"].format(theirs="0.3.0"))
        self.assertEqual(self.text("[data-install-again]"), "Install again")
        self.replies(review=OK({"ok": True, "review_id": "r2", "review": {**REVIEW, "reinstall": True}}))
        self.click("[data-install-again]")
        self.assertEqual(self.val("T.calls[2][1]"), {"from": "file", "reinstall": True})
        self.assertEqual(self.text("[data-install]"), "Install again")

    def test_a_chooser_that_is_cancelled_changes_nothing(self):
        self.replies(review=OK({"ok": True, "cancelled": True}))
        self.mount()
        self.click("[data-choose]")
        self.assertEqual(self.text(".pub-msg"), self.val("T.logic.CANCELLED"))
        self.assertFalse(self.present("#update-panel"))

    def test_an_install_that_fails_says_why_and_nothing_reloads(self):
        self.replies(install=OK({"ok": False, "code": "space", "message": ui.MESSAGES["space"]}, 409))
        self.mount()
        self.click("[data-review]")
        self.click("[data-install]")
        self.assertEqual(self.text(".pub-msg"), ui.MESSAGES["space"])
        self.assertEqual(0, self.val("T.reloads"))

    def test_undo_is_arm_then_confirm_and_changed_data_offers_the_app_and_settings_only(self):
        last = {**STATUS, "available": None, "line": "Up to date.", "last": {"from": "0.3.0", "to": "0.3.1", "line": "Last update: 0.3.0 → 0.3.1 on 01-11-2026."}}
        self.replies(status=OK(last), arm=OK({"ok": True, "arm_id": "a1", "choice": "full", "seconds": 5, "line": up.ARMED_FULL.format(to="0.3.0")}),
                     undo=OK({"ok": True, "restart": True, "message": up.UNDOING.format(to="0.3.0")}))
        self.mount()
        self.assertIn("Last update: 0.3.0", self.text("#update-last"))
        self.click("[data-undo]")
        self.assertEqual(self.calls(), ["status", "arm"], "the first click only arms")
        self.assertEqual(self.text("#update-armed"), up.ARMED_FULL.format(to="0.3.0"))
        self.click("[data-undo-confirm]")
        self.assertEqual(self.val("T.calls[2]"), ["undo", {"id": "a1", "appOnly": False}])
        self.assertEqual(1, self.val("T.reloads"))
        self.replies(arm=OK({"ok": True, "arm_id": "a2", "choice": "app_only", "seconds": 5, "line": up.ARMED_APP_ONLY}))
        self.mount()
        self.click("[data-undo]")
        self.assertEqual(self.text("[data-undo-confirm]"), "Put back the app and settings only")
        self.click("[data-undo-confirm]")
        self.assertEqual(self.val("T.calls.at(-2)"), ["undo", {"id": "a2", "appOnly": True}])

    def test_the_arm_runs_out(self):
        last = {**STATUS, "last": {"from": "0.3.0", "to": "0.3.1", "line": "Last update."}}
        self.replies(status=OK(last), arm=OK({"ok": True, "arm_id": "a1", "choice": "full", "seconds": 5, "line": "Armed."}))
        self.mount()
        self.click("[data-undo]")
        self.cdp.call("Runtime.evaluate", {"expression": "new Promise(r => setTimeout(r, 5300))", "awaitPromise": True}, self.sid)
        self.assertFalse(self.present("[data-undo-confirm]"))
        self.assertEqual(self.text(".pub-msg"), self.val("T.logic.DISARMED"))

    def test_the_notice_from_the_last_restart_is_said_in_the_one_polite_live_region(self):
        self.replies(status=OK({**STATUS, "notice": "Version 0.3.1 is installed."}))
        self.mount()
        self.assertEqual(self.val("[...document.querySelectorAll('#update [aria-live]')].map(e => [e.getAttribute('aria-live'), e.getAttribute('role')])"),
                         [["polite", "status"]])
        self.assertEqual(self.text(".pub-msg"), "Version 0.3.1 is installed.")
        self.assertFalse(self.present("#update [role=alert]"))

    def test_hostile_text_is_drawn_as_text(self):
        evil = '<img src=x onerror="window.pwned = 1">'
        self.replies(status=OK({**STATUS, "installed": evil}), review=OK({"ok": True, "review_id": "r", "review": {**REVIEW, "notes_text": evil, "notes": evil,
                                                                                                             "added": {"label": evil, "names": [evil]}}}))
        self.mount()
        self.click("[data-review]")
        self.assertFalse(self.val("!!window.pwned"))
        self.assertFalse(self.present("#update img"))

    def test_keyboard_reaches_every_control(self):
        self.mount()
        self.assertTrue(self.val("[...document.querySelectorAll('#update button')].every(b => b.tabIndex === 0)"))
        self.js("document.querySelector('[data-review]').focus()")
        self.cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "text": "\r"}, self.sid)
        self.cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13}, self.sid)
        self.settle()
        self.assertTrue(self.present("#update-panel"))

    def test_nothing_runs_sideways_and_the_text_reads_at_1400_and_900_in_light_and_dark(self):
        last = {**STATUS, "last": {"from": "0.3.0", "to": "0.3.1", "line": "Last update: 0.3.0 → 0.3.1 on 01-11-2026."}}
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme):
                    self.load(width=width, theme=theme)
                    self.replies(status=OK(last), review=OK({"ok": True, "review_id": "r1", "review": {**REVIEW, "by_hand": "1 file was changed by hand."}}))
                    self.mount()
                    self.click("[data-review]")
                    self.js("document.querySelector('#update-panel details').open = true")
                    self.assertTrue(self.val("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), "no sideways scroll")
                    self.assertTrue(self.val("[...document.querySelectorAll('#update button')].every(b => b.getBoundingClientRect().right <= innerWidth)"))
                    worst = self.val(f"Math.min(...[...document.querySelectorAll('#update p, #update li, #update pre, #update summary, #update h2')]"
                                     f".filter(e => e.textContent.trim()).map({CONTRAST}))")
                    self.assertGreaterEqual(worst, 4.5)


class WhereItIsNamed(unittest.TestCase):
    def test_only_updateapi_names_the_routes_and_a_published_file_has_none_of_it(self):
        named = [p.name for p in PAGE_SRC.rglob("*") if p.suffix in (".js", ".jsx") and "/api/update" in p.read_text(encoding="utf-8")]
        self.assertEqual(named, ["updateApi.js"])
        view = (PAGE_PY / "page-view.html").read_text(encoding="utf-8")
        self.assertNotIn("/api/update", view)
        self.assertNotIn("Version and updates", view)
        self.assertIn("/api/update", (PAGE_PY / "page.html").read_text(encoding="utf-8"))

    def test_the_card_is_mounted_in_settings_through_the_edit_tools(self):
        self.assertIn("Update", (PAGE_SRC / "edit" / "index.js").read_text(encoding="utf-8"))
        views = (PAGE_SRC / "components" / "Views.jsx").read_text(encoding="utf-8")
        self.assertIn("tools.Update", views)
        self.assertIn("<Update />", views)


if __name__ == "__main__":
    unittest.main()
