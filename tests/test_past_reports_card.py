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
    {"number": 3, "when": "28-10-2026 09:30", "where": "Local and to client · Word", "who": "Sam Example", "word": True, "kept": False, "week": "2026-10-30"},
    {"number": 3, "when": "28-10-2026 09:30", "where": "Local and to client", "who": "Sam Example", "word": False, "kept": True, "week": "2026-10-30"},
    {"number": 2, "when": "21-10-2026 08:15", "where": "Local · Word", "who": "Sam Example", "word": True, "kept": False, "week": "2026-10-23"},
    {"number": 1, "when": "14-10-2026 16:40", "where": "Local", "who": "Not recorded", "word": False, "kept": False, "week": None},
]
LIST = {"ok": True, "project": "PDF", "total": 4, "shown": 4, "limit": 10, "archived": 1, "publications": ROWS}
SHOWING = {**LIST, "publications": [ROWS[0], ROWS[1], {**ROWS[2], "archived": True}, ROWS[3]]}      # Show archived: Publication 2 is archived
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
        self.assertIn('export const COLUMNS = ["No.", "Week ending", "Date", "Where it went", "Files", "Who", ""];', text)
        self.assertIn('export const NOT_KEPT = "Not kept";', text)
        self.assertIn('export const NONE = "Nothing published yet. Each publish is listed here with its number.";', text)
        self.assertIn("Every copy of this project's report that clark has published, newest first. Open an older one here, so you never need to look through folders.", text)
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

    def test_the_archive_words_are_the_owners_ruling_and_the_prototypes_and_no_undo_is_in_them(self):
        text = self.logic()
        self.assertIn("export const archivedToast = (n) => `Publication ${n} archived. Restore it from Show archived.`;", text)
        self.assertIn("export const restoredToast = (n) => `Publication ${n} restored. Archive it again if you want it out of the list.`;", text)
        self.assertIn('archive: "Archive", restore: "Restore", showArchived: "Show archived"', text)
        self.assertIn('export const ARCHIVED_TAG = "Archived";', text)
        self.assertIn('export const ALL_ARCHIVED = "Every publication is archived. Show archived brings them back.";', text)
        self.assertNotRegex(text, r"(?i)\bundo\b")

    def test_the_card_is_edits_own_and_a_published_file_has_no_way_to_it(self):
        view = (PAGE / "page-view.html").read_text(encoding="utf-8")
        for name in ("/api/publications", "/api/past-report", "pastReportsApi", 'id="pubs"'):
            self.assertNotIn(name, view)
        editor = (PAGE / "page.html").read_text(encoding="utf-8")
        for name in ("/api/publications", "/api/past-report", "/api/publications/"):
            self.assertIn(name, editor)
        for path in PAGE_SRC.rglob("*.js*"):
            if path.name == "pastReportsApi.js" or "node_modules" in path.parts:
                continue
            self.assertNotIn("/api/past-report", path.read_text(encoding="utf-8"), f"{path.name}: only pastReportsApi.js names the route")

    def test_published_reports_is_its_own_page_reached_from_the_profile_circle_only(self):
        """Row 1087: the page replaces the Settings card. It is a view of its own, never a tab, and Settings no longer holds the card."""
        router = (PAGE_SRC / "router.js").read_text(encoding="utf-8")
        self.assertRegex(router, r'export const VIEWS = \[[^\]]*"published"')
        top = (PAGE_SRC / "components" / "TopBar.jsx").read_text(encoding="utf-8")
        self.assertIn('"published"', top, "the tab row leaves it out")
        views = (PAGE_SRC / "components" / "Views.jsx").read_text(encoding="utf-8")
        self.assertNotIn("<PublishedReports />", views.split("export function PublishedPage")[0], "Settings no longer draws the card")
        self.assertNotIn('"PublishedReports", "', views.split("const NEEDS_PROJECT")[0].split("const CARDS")[1], "no Settings chip for it")
        self.assertIn("published: PublishedPage", (PAGE_SRC / "components" / "App.jsx").read_text(encoding="utf-8"))
        self.assertIn('show("published")', (PAGE_SRC / "edit" / "PublishedReports.jsx").read_text(encoding="utf-8"))
        self.assertNotIn("scrollIntoView", (PAGE_SRC / "edit" / "PublishedReports.jsx").read_text(encoding="utf-8").split("export function PublishedReports")[0])

    def test_open_folder_is_not_on_the_page_and_no_server_file_is_touched_by_the_page(self):
        text = (PAGE_SRC / "edit" / "PublishedReports.jsx").read_text(encoding="utf-8")
        self.assertNotIn("Open folder", text)

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
        every = self.val("[T.logic.TITLE, T.logic.INTRO, ...T.logic.COLUMNS, T.logic.NONE, T.logic.LOADING, T.logic.NOT_KEPT, T.logic.timesLine('Gulf Standard Time'), T.logic.EARLIER_NONE, T.logic.SAVED_NOTE, T.logic.CHANGE_IN_SETTINGS, "
                         "T.logic.ARCHIVED_TAG, T.logic.ALL_ARCHIVED, T.logic.archivedToast(3), T.logic.restoredToast(3), "
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

    def test_the_page_has_the_brand_band_the_latest_one_and_the_earlier_ones_newest_first(self):
        self.mount()
        self.assertEqual(self.text("#pubs h1"), "Published reports")
        self.assertTrue(self.present("#pubs header.cover"), "the project's brand band, as on the Dashboard")
        self.assertEqual(self.text("#pubs .cover-kind"), "Example Programme")
        self.assertIn("Every copy of this project's report that clark has published, newest first.", self.text("#pubs header.cover"))
        latest = self.text("#pubs-latest")
        for want in ("Latest", "Published 28-10-2026 at 09:30", "Publication 3", "Week ending 30-10-2026",
                     "Went to the Local folder and the Client folder", "by Sam Example"):
            self.assertIn(want, latest)
        self.assertEqual(self.val("[...document.querySelectorAll('#pubs thead th')].map(th => th.textContent.replace('Open', '').trim())"),
                         ["No.", "Week ending", "Date", "Where it went", "Files", "Who", ""])
        rows = self.val("[...document.querySelectorAll('#pubs tbody tr')].map(tr => [...tr.cells].map(c => c.textContent).join('|'))")
        self.assertEqual(rows, ["2|23-10-2026|21-10-2026 08:15|Local folder|Word|Sam Example|Not keptArchive", "1|Not recorded|14-10-2026 16:40|Local folder|Page|Not recorded|Not keptArchive"])
        self.assertEqual(self.text("#pubs-latest [data-files]"), "Page, Word", "a number published as a page and a Word copy is one line")
        self.assertEqual(self.val("T.calls[0]"), ["list", "PDF"])

    def test_the_times_are_in_the_persons_own_zone_with_its_name(self):
        self.js("T.zone = 'Asia/Dubai'")
        self.mount()
        self.assertIn("Published 28-10-2026 at 13:30", self.text("#pubs-latest"))
        self.assertEqual(self.val("[...document.querySelectorAll('#pubs tbody tr')].map(tr => tr.cells[2].textContent)"), ["21-10-2026 12:15", "14-10-2026 20:40"])
        self.assertIn("Times are shown in your own time zone: Gulf Standard Time.", self.text("#pubs-note"))
        self.assertNotIn("UTC", self.text("#pubs"))

    def test_a_time_across_midnight_moves_the_day_and_a_bad_time_is_left_as_it_is(self):
        self.assertEqual(self.val("T.logic.localWhen('31-12-2026 22:30', 'Asia/Dubai')"), "01-01-2027 02:30")
        self.assertEqual(self.val("T.logic.localWhen('31-12-2026 22:30', 'UTC')"), "31-12-2026 22:30")
        self.assertEqual(self.val("T.logic.localWhen('not a time', 'UTC')"), "not a time")
        self.assertEqual(self.val("T.logic.zoneName('Asia/Dubai')"), "Gulf Standard Time")

    def test_where_it_is_saved_shows_both_folders_and_a_way_to_settings(self):
        self.js("T.folders = {local: '/Users/sam/Reports/PDF', client: 'OneDrive/Example/Weekly'}")
        self.mount()
        box = self.text("#pubs-folders")
        for want in ("Where it is saved", "Local folder", "/Users/sam/Reports/PDF", "Client folder", "OneDrive/Example/Weekly",
                     "The list comes from clark's own record of what it published, not from the folder, so other files in the folder are never shown."):
            self.assertIn(want, box)
        self.click("#pubs-folders [data-pubs-settings]")
        self.assertEqual(self.val("T.toSettings"), 1)
        self.js("T.folders = {local: null, client: null}")
        self.mount()
        self.assertIn("No local folder yet.", self.text("#pubs-folders"))
        self.assertIn("No client folder yet.", self.text("#pubs-folders"))

    def test_nothing_in_the_page_reads_the_folder_so_no_other_file_can_be_listed(self):
        self.mount()
        self.assertEqual(self.val("T.calls.map(c => c[0])"), ["list"], "the list is clark's own record, the only thing asked for")

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
        self.assertEqual(self.text(".pub-msg"), self.val("T.logic.BLOCKED"))
        self.assertEqual(self.val("T.calls[1]"), ["ready", {"code": "PDF", "n": 3}], "the real tab helper asks for the address either way")

    def test_each_row_has_archive_and_the_default_list_hides_the_archived(self):
        self.mount()
        self.assertEqual(self.val("[...document.querySelectorAll('[data-pubarchive]')].map(b => b.dataset.pubarchive)"), ["3", "2", "1"], "the latest one too")
        self.assertEqual(self.val("document.querySelector('[data-pubarchive]').getAttribute('aria-label')"), "Archive Publication 3")
        self.assertFalse(self.present("[data-pubrestore]"))
        self.assertEqual(self.val("T.calls[0]"), ["list", "PDF"], "the default list does not ask for the archived ones")
        self.assertEqual(self.text("#pubs-archived"), "Show archived 1")
        self.assertEqual(self.val("document.querySelector('#pubs-archived').getAttribute('aria-pressed')"), "false")

    def test_archive_asks_once_says_the_exact_words_with_no_undo_and_reads_the_list_again(self):
        self.replies(archive=OK({"ok": True, "code": "archived", "project": "PDF", "number": 3}))
        self.mount()
        self.replies(list=OK({**LIST, "total": 2, "shown": 2, "archived": 2, "publications": ROWS[2:]}))
        self.click("[data-pubarchive='3']")
        self.assertEqual(self.val("T.calls[1]"), ["archive", {"code": "PDF", "n": 3}])
        self.assertEqual(self.val("T.toasts"), [["done", "Publication 3 archived. Restore it from Show archived.", None]])
        self.assertEqual(self.val("T.calls[2]"), ["list", "PDF"])
        self.assertEqual(self.val("[...document.querySelectorAll('#pubs tbody tr')].map(tr => tr.dataset.pub)"), ["1"], "2 is now the latest")
        self.assertIn("Publication 2", self.text("#pubs-latest"))
        self.assertEqual(self.text("#pubs-archived"), "Show archived 2")
        self.assertEqual(self.text(".pub-msg"), "")

    def test_show_archived_lists_them_marked_with_restore_and_restore_says_its_words(self):
        self.replies(restore=OK({"ok": True, "code": "restored", "project": "PDF", "number": 2}))
        self.js("T.replies.list = (x) => (x && x.archived) ? " + lit(OK(SHOWING)) + " : " + lit(OK(LIST)))
        self.mount()
        self.click("#pubs-archived")
        self.assertEqual(self.val("T.calls[1]"), ["list", {"code": "PDF", "archived": True}])
        self.assertEqual(self.val("document.querySelector('#pubs-archived').getAttribute('aria-pressed')"), "true")
        self.assertEqual(self.val("[...document.querySelectorAll('#pubs tbody tr')].map(tr => tr.dataset.pub)"), ["2", "1"], "3 is the latest")
        self.assertEqual(self.text("tr[data-pub='2'] .tag"), "Archived")
        self.assertEqual(self.val("[...document.querySelectorAll('[data-pubrestore]')].map(b => b.dataset.pubrestore)"), ["2"])
        self.assertEqual(self.val("document.querySelector('[data-pubrestore]').getAttribute('aria-label')"), "Restore Publication 2")
        self.assertEqual(self.val("[...document.querySelectorAll('[data-pubarchive]')].map(b => b.dataset.pubarchive)"), ["3", "1"])
        self.click("[data-pubrestore='2']")
        self.assertEqual(self.val("T.calls[2]"), ["restore", {"code": "PDF", "n": 2}])
        self.assertEqual(self.val("T.toasts"), [["done", "Publication 2 restored. Archive it again if you want it out of the list.", None]])
        self.assertEqual(self.val("T.calls[3]"), ["list", {"code": "PDF", "archived": True}], "still showing the archived ones")
        self.click("#pubs-archived")
        self.assertEqual(self.val("T.calls[4]"), ["list", "PDF"])

    def test_a_refusal_is_said_in_the_servers_words_and_no_toast_is_made(self):
        said = "Publication 3 is already archived. Nothing was changed."
        self.replies(archive=OK({"ok": False, "code": "already", "message": said}, 409))
        self.mount()
        self.click("[data-pubarchive='3']")
        self.assertEqual(self.text(".pub-msg"), said)
        self.assertEqual(self.val("T.toasts"), [])
        self.replies(archive={"status": 0, "body": None})
        self.click("[data-pubarchive='3']")
        self.assertEqual(self.text(".pub-msg"), self.val("T.logic.NOT_ANSWERING"))
        self.replies(archive=OK({"ok": False, "code": "server_error", "message": "Traceback (most recent call last)"}, 500))
        self.click("[data-pubarchive='3']")
        self.assertEqual(self.text(".pub-msg"), self.val("T.logic.LIST_FAILED"))

    def test_every_publication_archived_says_so_and_show_archived_brings_them_back(self):
        self.replies(list=OK({**LIST, "total": 0, "shown": 0, "archived": 3, "publications": []}))
        self.mount()
        self.assertEqual(self.text("#pubs-none"), "Every publication is archived. Show archived brings them back.")
        self.assertFalse(self.present("#pubs-table"))

    def test_nothing_published_says_so(self):
        self.replies(list=OK({**LIST, "total": 0, "shown": 0, "archived": 0, "publications": []}))
        self.mount()
        self.assertEqual(self.text("#pubs-none"), "Nothing published yet. Each publish is listed here with its number.")
        self.assertFalse(self.present("#pubs-table"))

    def test_a_list_cut_to_ten_says_how_many_there_are(self):
        many = [{**ROWS[1], "number": n} for n in range(12, 2, -1)]
        self.replies(list=OK({**LIST, "total": 12, "shown": 10, "publications": many}))
        self.mount()
        self.assertEqual(self.val("document.querySelectorAll('#pubs tbody tr').length"), 9, "ten, one of them the latest")
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
        self.replies(list=OK({**LIST, "publications": [{**ROWS[1], "who": evil, "where": evil}, {**ROWS[3], "who": evil}]}))
        self.mount()
        self.assertFalse(self.val("!!window.pwned"))
        self.assertFalse(self.present("#pubs img"))

    def test_nothing_runs_sideways_at_1400_and_900_in_light_and_dark(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme):
                    self.load(width=width, theme=theme)
                    self.replies(list=OK(SHOWING), tab=True)
                    self.mount()
                    self.assertTrue(self.val("!!document.querySelector('[data-pubrestore]') && !!document.querySelector('[data-pubarchive]')"))
                    self.assertTrue(self.val("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), "no sideways scroll")
                    self.assertTrue(self.val("[...document.querySelectorAll('#pubs button, #pubs td, #pubs-latest, #pubs-folders, #pubs header.cover')].every(b => b.getBoundingClientRect().right <= innerWidth)"))
                    self.assertTrue(self.val("(() => { const c = getComputedStyle(document.querySelector('#pubs header.cover')).backgroundColor; return c !== 'rgba(0, 0, 0, 0)'; })()"), "the band is brand coloured")
                    self.assertTrue(self.val("(() => { const c = getComputedStyle(document.querySelector('#pubs td')).color; return c !== getComputedStyle(document.body).backgroundColor; })()"))
                    self.assertTrue(self.val("(() => { const c = getComputedStyle(document.querySelector('#pubs-latest')).backgroundColor; return c !== 'rgba(0, 0, 0, 0)'; })()"))


if __name__ == "__main__":
    unittest.main()
