"""#443: Settings › Published reports, the page's side: the words (src/clark/page/src/logic/pastReports.js), the card
(edit/PublishedReports.jsx) over a fake server, and the profile menu's entry. The routes themselves are tests/test_past_reports.py.

Run: python3 dev/run_tests.py test_past_reports_card
The card tests run inside headless Chrome (the #33 harness, as test_safety_logic.py does); Chrome is required there and they fail,
never skip, without it. The Static tests need no browser. Fixture data is made up.
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

from clark import past_reports  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402

PAGE = SRC / "clark" / "page"
PAGE_SRC = PAGE / "src"
DEMO = ROOT / "tests" / "fixtures" / "published_reports_demo.jsx"

ROWS = [
    {"number": 3, "when": "28-10-2026 09:30", "where": "Local and to client", "who": "Sam Example", "word": False, "kept": True},
    {"number": 2, "when": "21-10-2026 08:15", "where": "Local · Word", "who": "Sam Example", "word": True, "kept": False},
    {"number": 1, "when": "14-10-2026 16:40", "where": "Local", "who": "Not recorded", "word": False, "kept": False},
]
LIST = {"ok": True, "project": "PDF", "total": 3, "shown": 3, "limit": 10, "publications": ROWS}
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


class Static(unittest.TestCase):
    """Source checks that need no browser."""

    def logic(self):
        return (PAGE_SRC / "logic" / "pastReports.js").read_text(encoding="utf-8")

    def test_the_words_are_the_prototypes_with_the_owners_ruling(self):
        text = self.logic()
        self.assertIn('export const TITLE = "Published reports";', text)
        self.assertIn('export const COLUMNS = ["#", "Date and time", "Where", "Who", ""];', text)
        self.assertIn('export const NOT_KEPT = "Not kept";', text)
        self.assertIn('export const NONE = "Nothing published yet. Each publish is listed here with its number.";', text)
        self.assertIn("Every time you publish, the report gets the next number for this project and a copy of the page is kept. "
                      "Open shows the copy as it was published. Every copy is kept; this list shows the latest 10.", text)
        self.assertNotIn("last 10 copies are kept", text, "the prototype's last-10 rule is the one the ruling (#348) drops")

    def test_the_servers_own_sentences_the_page_shows_are_ones_the_server_sends(self):
        codes = re.search(r"SERVER_SAYS = \[(.*?)\]", self.logic()).group(1)
        codes = set(re.findall(r'"([a-z_]+)"', codes))
        self.assertEqual(codes, {"not_kept", "copy_changed", "no_publication", "project_not_found"})
        self.assertEqual(codes - set(past_reports.MESSAGES), set())
        for code in codes:
            low = past_reports.MESSAGES[code].lower()
            for jargon in ("sha", "hash", "path", "json", "token", "sql", "database", "folder"):
                self.assertNotRegex(low, r"\b" + jargon, code)
            self.assertFalse(past_reports.MESSAGES[code].startswith(("clark", "Clark")), code)

    def test_the_card_is_edits_own_and_a_published_file_has_no_way_to_it(self):
        view = (PAGE / "page-view.html").read_text(encoding="utf-8")
        for name in ("/api/publications", "/api/past-report", "pastReportsApi", 'id="pubs"'):
            self.assertNotIn(name, view)
        editor = (PAGE / "page.html").read_text(encoding="utf-8")
        for name in ("/api/publications", "/api/past-report"):
            self.assertIn(name, editor)
        for path in PAGE_SRC.rglob("*.js*"):
            if path.name == "pastReportsApi.js" or "node_modules" in path.parts:
                continue
            self.assertNotIn("/api/past-report", path.read_text(encoding="utf-8"), f"{path.name}: only pastReportsApi.js names the route")

    def test_the_profile_menu_has_the_entry_after_export_and_before_settings(self):
        text = (PAGE_SRC / "edit" / "ProfileMenu.jsx").read_text(encoding="utf-8")
        export = text.index('name: "Export to Excel"')
        published = text.index('name: "Published reports"')
        settings = text.index('name: "Settings"')
        self.assertTrue(export < published < settings)
        self.assertIn("showPublished()", text)


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


class Words(InBrowser):
    def test_every_word_is_plain_and_none_starts_with_the_product_name(self):
        every = self.val("[T.logic.TITLE, T.logic.INTRO, ...T.logic.COLUMNS, T.logic.NONE, T.logic.LOADING, T.logic.NOT_KEPT, T.logic.TIMES, "
                         "T.logic.LIST_FAILED, T.logic.OPEN_FAILED, T.logic.BLOCKED, T.logic.NOT_ANSWERING, T.logic.STALE, ...Object.values(T.logic.LABELS)]")
        for text in every:
            low = text.lower()
            self.assertFalse([w for w in ("sql", "token", "json", "sha", "hash", "stale") if re.search(r"\b" + w, low)], text)
            self.assertFalse(text.startswith(("clark", "Clark")), text)

    def test_a_known_code_keeps_the_servers_sentence_and_anything_else_is_the_fallback(self):
        said = past_reports.MESSAGES["copy_changed"].format(number=4)
        self.assertEqual(self.val(f"T.logic.openWords(409, {{code: 'copy_changed', message: {lit(said)}}})"), said)
        fallback = self.val("T.logic.OPEN_FAILED")
        for expr in ("T.logic.openWords(500, {code: 'server_error', message: 'Traceback (most recent call last)'})",
                     "T.logic.openWords(404, {code: 'not_kept', message: ''})", "T.logic.openWords(400, null)",
                     "T.logic.openWords(404, {code: 'not_kept', message: 'x'.repeat(601)})", "T.logic.openWords(404, {code: 'other_code', message: 'a'})"):
            self.assertEqual(self.val(expr), fallback, expr)
        self.assertEqual(self.val("T.logic.openWords(0, null)"), self.val("T.logic.NOT_ANSWERING"))
        self.assertEqual(self.val("T.logic.openWords(403, {code: 'stale'})"), self.val("T.logic.STALE"))
        self.assertEqual(self.val("T.logic.listWords(500, {message: 'Traceback'})"), self.val("T.logic.LIST_FAILED"))

    def test_the_cut_line_is_said_only_when_the_list_is_cut(self):
        self.assertEqual(self.val("T.logic.cutLine(12, 10)"), "Showing the latest 10 of 12. The older ones are kept.")
        self.assertEqual(self.val("T.logic.cutLine(10, 10)"), "")


class Card(InBrowser):
    def setUp(self):
        super().setUp()
        self.replies(list=OK(LIST), ready=OK({"ok": True, "code": "past_ready", "message": "Opening Publication 3 as it was published.", "number": 3, "url": "/past?id=abcdefghijklmnop"}), tab=True)

    def test_the_card_has_the_title_the_columns_and_the_rows_newest_first(self):
        self.mount()
        self.assertEqual(self.text("#pubs h2"), "Published reports · Example Programme")
        self.assertEqual(self.val("[...document.querySelectorAll('#pubs thead th')].map(th => th.textContent.replace('Open', '').trim())"), ["#", "Date and time", "Where", "Who", ""])
        rows = self.val("[...document.querySelectorAll('#pubs tbody tr')].map(tr => [...tr.cells].map(c => c.textContent).join('|'))")
        self.assertEqual(rows, ["3|28-10-2026 09:30|Local and to client|Sam Example|Open", "2|21-10-2026 08:15|Local · Word|Sam Example|Not kept", "1|14-10-2026 16:40|Local|Not recorded|Not kept"])
        self.assertIn("Every copy is kept; this list shows the latest 10.", self.text("#pubs"))
        self.assertEqual(self.val("T.calls[0]"), ["list", "PDF"])

    def test_only_a_kept_page_has_open(self):
        self.mount()
        self.assertEqual(self.val("[...document.querySelectorAll('[data-pubopen]')].map(b => b.dataset.pubopen)"), ["3"])
        self.assertEqual(self.val("document.querySelector('[data-pubopen]').getAttribute('aria-label')"), "Open Publication 3")

    def test_open_asks_for_the_one_visit_address_and_points_a_new_tab_at_it(self):
        self.mount()
        self.click("[data-pubopen='3']")
        self.assertEqual(self.val("T.calls[1]"), ["ready", {"code": "PDF", "n": 3}])
        self.assertEqual(self.val("T.tabs"), ["/past?id=abcdefghijklmnop"])
        self.assertEqual(self.text(".pub-msg"), "")

    def test_a_copy_that_changed_is_said_plainly_and_no_tab_is_pointed_anywhere(self):
        said = past_reports.MESSAGES["copy_changed"].format(number=3)
        self.replies(ready=OK({"ok": False, "code": "copy_changed", "message": said}, 409))
        self.mount()
        self.click("[data-pubopen='3']")
        self.assertEqual(self.text(".pub-msg"), said)
        self.assertEqual(self.val("T.tabs"), [])

    def test_a_blocked_pop_up_says_what_to_do(self):
        self.replies(tab=False)
        self.mount()
        self.click("[data-pubopen='3']")
        self.assertEqual(self.text(".pub-msg"), self.val("T.logic.OPEN_FAILED"))

    def test_nothing_published_says_so(self):
        self.replies(list=OK({**LIST, "total": 0, "shown": 0, "publications": []}))
        self.mount()
        self.assertEqual(self.text("#pubs-none"), "Nothing published yet. Each publish is listed here with its number.")
        self.assertFalse(self.present("#pubs-table"))

    def test_a_list_cut_to_ten_says_how_many_there_are(self):
        many = [{**ROWS[0], "number": n} for n in range(12, 2, -1)]
        self.replies(list=OK({**LIST, "total": 12, "shown": 10, "publications": many}))
        self.mount()
        self.assertEqual(self.val("document.querySelectorAll('#pubs tbody tr').length"), 10)
        self.assertIn("Showing the latest 10 of 12. The older ones are kept.", self.text("#pubs-note"))

    def test_a_server_that_does_not_answer_says_so_and_offers_try_again(self):
        self.replies(list={"status": 0, "body": None})
        self.mount()
        self.assertIn(self.val("T.logic.NOT_ANSWERING"), self.text("#pubs"))
        self.replies(list=OK(LIST))
        self.click("[data-pubs-again]")
        self.assertTrue(self.present("#pubs-table"))

    def test_hostile_text_in_a_row_is_drawn_as_text(self):
        evil = '<img src=x onerror="window.pwned = 1">'
        self.replies(list=OK({**LIST, "publications": [{**ROWS[0], "who": evil, "where": evil}]}))
        self.mount()
        self.assertFalse(self.val("!!window.pwned"))
        self.assertFalse(self.present("#pubs img"))

    def test_nothing_runs_sideways_at_1400_and_900_in_light_and_dark(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme):
                    self.load(width=width, theme=theme)
                    self.replies(list=OK(LIST), tab=True)
                    self.mount()
                    self.assertTrue(self.val("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), "no sideways scroll")
                    self.assertTrue(self.val("[...document.querySelectorAll('#pubs button, #pubs td')].every(b => b.getBoundingClientRect().right <= innerWidth)"))
                    self.assertTrue(self.val("(() => { const c = getComputedStyle(document.querySelector('#pubs td')).color; return c !== getComputedStyle(document.body).backgroundColor; })()"))
                    self.assertTrue(self.val("(() => { const c = getComputedStyle(document.querySelector('#pubs')).backgroundColor; return c !== 'rgba(0, 0, 0, 0)'; })()"))


if __name__ == "__main__":
    unittest.main()
