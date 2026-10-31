"""#111: Settings › Safety, the page's side: the logic (src/clark/page/src/logic/safety.js) and the card (edit/Safety.jsx), over a fake
server, at 1400 and 900 pixels wide in light and dark. The routes themselves are tests/test_safety.py.

Run: python3 dev/run_tests.py test_safety_logic
The repo has no Node, so the logic runs inside headless Chrome (the #33 harness, as test_draft_email_editor.py does). Chrome is
required: these tests fail, never skip, without it. Fixture data is made up.
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

from clark import safety, server as sv  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "safety_demo.jsx"
PAGE_PY = SRC / "clark" / "page"

ROWS = [
    {"name": "clark-20301002T091400Z-daily.db", "tag": "daily", "kind": "daily", "kind_label": "Daily", "when": "02-10-2030 09:14", "size": 217088, "size_text": "212 KB"},
    {"name": "clark-20301001T101500Z-undo.db", "tag": "undo", "kind": "before an undo", "kind_label": "Before an undo", "when": "01-10-2030 10:15", "size": 1572864, "size_text": "1.5 MB"},
]
LIST = {"ok": True, "backups": ROWS, "status": "Latest backup: 02-10-2030 09:14. A daily backup is always made.", "newest_ok": True,
        "warning": None, "keep": 14, "keep_label": "How many backups to keep", "keep_help": "This many are kept."}
PREVIEW = {"ok": True, "name": ROWS[0]["name"], "when": "02-10-2030 09:14", "kind_label": "Daily", "copy": {"projects": 3, "work_items": 212, "milestones": 41},
           "now": {"projects": 3, "work_items": 230, "milestones": 41}, "last_step": 17, "same_database": True, "older": False, "older_note": None}
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


class Logic(InBrowser):
    def test_the_sentences_match_the_servers(self):
        words = self.val("T.logic.WORDS")
        for code, text in words.items():
            server_says = safety.MESSAGES.get(code) or sv.MESSAGES.get(code)
            self.assertEqual(text, server_says, code)

    def test_every_word_is_plain_and_none_starts_with_the_product_name(self):
        every = self.val("[...Object.values(T.logic.WORDS), T.logic.GENERIC, T.logic.NOT_ANSWERING, T.logic.STALE, T.logic.LOADING, T.logic.NONE_SHOWN, "
                         "T.logic.TITLE, T.logic.INTRO, ...Object.values(T.logic.LABELS)]")
        for text in every:
            low = text.lower()
            self.assertFalse([w for w in safety.JARGON + ("sql", "token", "json", "stale") if re.search(r"\b" + w, low)], text)
            self.assertFalse(text.startswith(("clark", "Clark")), text)

    def test_a_known_code_has_its_sentence_a_refusal_keeps_the_servers_and_anything_else_is_generic(self):
        self.assertEqual(self.val("T.logic.answerWords(409, {code: 'busy', message: 'ignore me'})"), safety.MESSAGES["busy"])
        self.assertEqual(self.val("T.logic.answerWords(400, {code: 'damaged', message: 'X is damaged, so it can\\'t be used. Choose another backup.'})"),
                         "X is damaged, so it can't be used. Choose another backup.")
        for expr in ("T.logic.answerWords(500, {code: 'server_error', message: 'Traceback (most recent call last)'})",
                     "T.logic.answerWords(400, {code: 'refused', message: ''})", "T.logic.answerWords(400, null)",
                     "T.logic.answerWords(400, {code: 'damaged', message: 'x'.repeat(601)})", "T.logic.answerWords(500, {code: 'busy_', message: 'a'})"):
            self.assertEqual(self.val(expr), self.val("T.logic.GENERIC"), expr)
        self.assertEqual(self.val("T.logic.answerWords(0, null)"), self.val("T.logic.NOT_ANSWERING"))
        self.assertEqual(self.val("T.logic.answerWords(403, {code: 'stale'})"), self.val("T.logic.STALE"))

    def test_server_says_codes_are_all_codes_safety_py_sends(self):
        sent = {"no_backup", "folder", "other_database", "busy", "in_use", "changed", "bad_request", "reopen", "damaged", "newer",
                "migrate_failed", "unfinished", "file_problem", "refused"}
        known = set(self.val("Object.keys(T.logic.WORDS)")) | set(self.val("T.logic.SERVER_SAYS"))
        self.assertEqual(sent - known, set())

    def test_preview_lines_count_and_pluralise(self):
        self.assertEqual(self.val(f"T.logic.previewLines({lit(PREVIEW)})"),
                         ["This backup is from 02-10-2030 09:14. It holds 3 projects, 212 work items and 41 milestones.",
                          "You have 3 projects, 230 work items and 41 milestones now."])
        one = {**PREVIEW, "copy": {"projects": 1, "work_items": 1, "milestones": 1}, "now": None, "older": True, "older_note": "Made by an older version of clark; it is brought up to date when restored."}
        self.assertEqual(self.val(f"T.logic.previewLines({lit(one)})"),
                         ["This backup is from 02-10-2030 09:14. It holds 1 project, 1 work item and 1 milestone.",
                          "Made by an older version of clark; it is brought up to date when restored."])
        other = {**PREVIEW, "same_database": False}
        self.assertIn("different database", self.val(f"T.logic.previewLines({lit(other)})")[-1])
        self.assertFalse(self.val(f"T.logic.canRestore({lit(other)})"))
        self.assertEqual(self.val(f"T.logic.confirmLine({lit(PREVIEW)})"), "Put back the backup from 02-10-2030 09:14? What you have now is kept first.")

    def test_the_done_sentence_is_kept_once_and_storage_that_fails_is_no_error(self):
        self.assertTrue(self.val("T.logic.rememberDone('Restored.', T.store)"))
        self.assertEqual(self.val("T.logic.takeDone(T.store)"), "Restored.")
        self.assertEqual(self.val("T.logic.takeDone(T.store)"), "")
        broken = "{getItem(){throw new Error('x')}, setItem(){throw new Error('x')}, removeItem(){throw new Error('x')}}"
        self.assertFalse(self.val(f"T.logic.rememberDone('a', {broken})"))
        self.assertEqual(self.val(f"T.logic.takeDone({broken})"), "")


class Card(InBrowser):
    def setUp(self):
        super().setUp()
        self.replies(list=OK(LIST), preview=OK(PREVIEW))

    def test_the_list_shows_date_kind_and_size_newest_first(self):
        self.mount()
        rows = self.val("[...document.querySelectorAll('#backup-list li')].map(li => li.querySelector('.when').textContent + '|' + li.querySelector('.kind').textContent + '|' + li.querySelector('.size').textContent)")
        self.assertEqual(rows, ["02-10-2030 09:14|Daily|212 KB", "01-10-2030 10:15|Before an undo|1.5 MB"])
        self.assertEqual(self.text("#safety-status"), LIST["status"])
        self.assertEqual(self.text("#safety-keep"), "14")

    def test_preview_shows_counts_and_changes_nothing(self):
        self.mount()
        self.click("[data-backup] [data-preview]")
        self.assertIn("It holds 3 projects, 212 work items and 41 milestones.", self.text("#backup-panel"))
        self.assertEqual(self.val("T.calls.map(c => c[0])"), ["list", "preview"])
        self.assertEqual(self.val("T.reloads"), 0)

    def test_restore_asks_first_then_reloads_and_remembers_one_sentence(self):
        self.replies(restore=OK({"ok": True, "code": "restored", "message": "Restored the backup from 02-10-2030. Your data from before is kept in case you need it.", "reload": True}))
        self.mount()
        self.click("[data-backup] [data-restore]")
        self.assertEqual(self.text("#backup-confirm"), "Put back the backup from 02-10-2030 09:14? What you have now is kept first.")
        self.assertEqual(self.val("T.calls.map(c => c[0])"), ["list", "preview"], "nothing is restored by the first click")
        self.click("[data-put-back]")
        self.assertEqual(self.val("T.calls[2]"), ["restore", {"name": ROWS[0]["name"], "step": 17}])
        self.assertEqual(self.val("T.reloads"), 1)
        self.mount()                                   # after the reload the card shows the sentence once
        self.assertEqual(self.text(".pub-msg"), "Restored the backup from 02-10-2030. Your data from before is kept in case you need it.")
        self.mount()
        self.assertEqual(self.text(".pub-msg"), "")

    def test_a_refusal_is_one_plain_sentence_and_nothing_reloads(self):
        self.replies(restore=OK({"ok": False, "code": "changed", "message": "x"}, 409))
        self.mount()
        self.click("[data-backup] [data-restore]")
        self.click("[data-put-back]")
        self.assertEqual(self.text(".pub-msg"), safety.MESSAGES["changed"])
        self.assertEqual(self.val("T.reloads"), 0)
        self.assertFalse(self.present("#backup-panel"))

    def test_a_server_that_does_not_answer_says_so_and_offers_try_again(self):
        self.replies(list={"status": 0, "body": None})
        self.mount()
        self.assertIn(self.val("T.logic.NOT_ANSWERING"), self.text("#safety"))
        self.replies(list=OK(LIST))
        self.click("[data-safety-again]")
        self.assertTrue(self.present("#backup-list"))

    def test_a_backup_of_another_database_cannot_be_put_back(self):
        self.replies(preview=OK({**PREVIEW, "same_database": False}))
        self.mount()
        self.click("[data-backup] [data-preview]")
        self.assertIn("different database", self.text("#backup-panel"))
        self.assertFalse(self.present("[data-restore-from-preview]"))
        self.click("[data-backup] [data-restore]")
        self.assertFalse(self.present("[data-put-back]"))

    def test_the_daily_warning_and_a_damaged_newest_copy_show(self):
        self.replies(list=OK({**LIST, "warning": "Today's backup couldn't be made.", "newest_ok": False,
                              "status": "The latest backup, from 02-10-2030, is damaged and can't be used."}))
        self.mount()
        self.assertEqual(self.text("#safety-warning"), "Today's backup couldn't be made.")
        self.assertTrue(self.val("document.getElementById('safety-status').className === 'error'"))

    def test_hostile_text_in_a_name_is_drawn_as_text(self):
        evil = '<img src=x onerror="window.pwned = 1">'
        self.replies(list=OK({**LIST, "backups": [{**ROWS[0], "name": evil, "kind_label": evil}]}))
        self.mount()
        self.assertFalse(self.val("!!window.pwned"))
        self.assertFalse(self.present("#backup-list img"))

    def test_nothing_runs_sideways_at_1400_and_900_in_light_and_dark(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme):
                    self.load(width=width, theme=theme)
                    self.replies(list=OK(LIST), preview=OK({**PREVIEW, "older": True, "older_note": "Made by an older version of clark; it is brought up to date when restored."}))
                    self.mount()
                    self.click("[data-backup] [data-preview]")
                    self.assertTrue(self.val("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), "no sideways scroll")
                    self.assertTrue(self.val("[...document.querySelectorAll('#safety button')].every(b => b.getBoundingClientRect().right <= innerWidth)"))
                    self.assertTrue(self.val("(() => { const c = getComputedStyle(document.querySelector('#safety .when')).color; return c !== getComputedStyle(document.body).backgroundColor; })()"))


class WhereItIsNamed(unittest.TestCase):
    def test_only_safetyapi_names_the_routes_and_a_published_file_has_none_of_it(self):
        src = PAGE_SRC
        named = [p.name for p in src.rglob("*") if p.suffix in (".js", ".jsx") and "/api/backups" in p.read_text(encoding="utf-8")]
        self.assertEqual(named, ["safetyApi.js"])
        view = (PAGE_PY / "page-view.html").read_text(encoding="utf-8")
        self.assertNotIn("/api/backups", view)
        self.assertNotIn("backup-list", view.replace(".backup-list", ""))
        self.assertIn("/api/backups", (PAGE_PY / "page.html").read_text(encoding="utf-8"))

    def test_the_card_is_mounted_in_settings_through_the_edit_tools(self):
        self.assertIn("Safety", (PAGE_SRC / "edit" / "index.js").read_text(encoding="utf-8"))
        views = (PAGE_SRC / "components" / "Views.jsx").read_text(encoding="utf-8")
        self.assertIn("tools.Safety", views)
        self.assertIn("<Safety />", views)


if __name__ == "__main__":
    unittest.main()
