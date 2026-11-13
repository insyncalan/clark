"""#443, row 1087: the Published reports page (reached from the profile circle; no longer a Settings card), the page's side: the words (src/clark/page/src/logic/pastReports.js), the card
(edit/PublishedPage.jsx, edit/PublishedReports.jsx) over a fake server, and the profile menu's entry. The routes themselves are tests/test_past_reports.py.

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

ROWS = [      # `at` is UTC; the page shows it in the person's own zone (the tests pin Asia/Dubai, four hours ahead)
    {"number": 3, "when": "28-10-2026 09:30", "at": "2026-10-28T09:30:00Z", "week": "2026-10-23", "pdf": True, "where": "Local and to client", "who": "Sam Example", "word": False, "kept": True},
    {"number": 2, "when": "21-10-2026 08:15", "at": "2026-10-21T08:15:00Z", "week": "2026-10-16", "pdf": False, "where": "Local · Word", "who": "Sam Example", "word": True, "kept": False},
    {"number": 1, "when": "14-10-2026 16:40", "at": "2026-10-14T16:40:00Z", "week": None, "pdf": False, "where": "Local", "who": "Not recorded", "word": False, "kept": False},
]
LIST = {"ok": True, "project": "PDF", "total": 3, "shown": 3, "limit": 10, "archived": 1, "publications": ROWS}
SHOWING = {**LIST, "publications": [ROWS[0], {**ROWS[1], "archived": True}, ROWS[2]]}      # Show archived: Publication 2 is archived
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
        css = (build_page.TOKENS.read_text(encoding="utf-8") + (build_page.PAGE / "shell.css").read_text(encoding="utf-8")
               + build_page.EDIT_CSS.read_text(encoding="utf-8"))      # row 1087: the page's own styles are in edit.css, as in the served page
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
        self.assertIn('export const COLUMNS = ["No.", "Week ending", "Published", "Went to", "Files", ""];', text)
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
        for name in ("/api/publications", "/api/past-report", "pastReportsApi", 'id="pubs"', "pubs-page", "PublishedReports"):
            self.assertNotIn(name, view)
        editor = (PAGE / "page.html").read_text(encoding="utf-8")
        for name in ("/api/publications", "/api/past-report", "/api/publications/"):
            self.assertIn(name, editor)
        for path in PAGE_SRC.rglob("*.js*"):
            if path.name == "pastReportsApi.js" or "node_modules" in path.parts:
                continue
            self.assertNotIn("/api/past-report", path.read_text(encoding="utf-8"), f"{path.name}: only pastReportsApi.js names the route")

    def test_row_1087_the_pages_words_are_not_in_the_published_file(self):
        view = (PAGE / "page-view.html").read_text(encoding="utf-8")
        for word in ("Where it is saved", "Earlier reports", "Went to", "Change in Settings", "Not chosen yet", "so other files in the folder are never shown",
                     "Times are shown in your time zone", "Open an older one here", "pubs-where", "pubs-latest", "pubs-intro"):
            self.assertNotIn(word, view, word)
        self.assertNotIn('published: "Published reports"', (PAGE_SRC / "stores" / "report.js").read_text(encoding="utf-8"))

    def test_the_profile_menu_has_the_entry_after_export_and_before_settings(self):
        text = (PAGE_SRC / "edit" / "ProfileMenu.jsx").read_text(encoding="utf-8")
        export = text.index('name: "Export to Excel"')
        published = text.index('name: "Published reports"')
        settings = text.index('name: "Settings"')
        self.assertTrue(export < published < settings)
        self.assertIn("showPublished()", text)

    def test_row_1087_it_is_a_page_reached_only_from_the_profile_circle_not_a_tab_not_a_card(self):
        router = (PAGE_SRC / "router.js").read_text(encoding="utf-8")
        self.assertRegex(router, r'export const VIEWS = \[[^\]]*"published"')
        bar = (PAGE_SRC / "components" / "TopBar.jsx").read_text(encoding="utf-8")
        self.assertIn('"published"', bar, "the tab bar leaves it out, as it leaves Settings out")
        views = (PAGE_SRC / "components" / "Views.jsx").read_text(encoding="utf-8")
        self.assertNotIn("PublishedReports", views, "the Settings page no longer draws the card")
        self.assertIn("PublishedPage", (PAGE_SRC / "components" / "App.jsx").read_text(encoding="utf-8") + (PAGE_SRC / "edit" / "index.js").read_text(encoding="utf-8"))
        for name in ("ReviewDays", "Diagnostics"):
            self.assertIn(name, views)


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
        cls.cdp.call("Emulation.setTimezoneOverride", {"timezoneId": "Asia/Dubai"}, cls.sid)      # row 1087: times are shown in the person's own zone

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
        every = self.val("[T.logic.TITLE, T.logic.INTRO, ...T.logic.COLUMNS, T.logic.NONE, T.logic.LOADING, T.logic.NOT_KEPT, T.logic.timesLine('Gulf Standard Time'), ...Object.values(T.logic.PAGE), "
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

    def test_row_1087_the_page_has_the_title_the_cover_where_it_is_saved_the_latest_and_the_earlier_ones(self):
        self.mount()
        self.assertEqual(self.text("#pubs-page h1"), "Published reports")
        self.assertTrue(self.present("#pubs-page .cover"), "the brand's cover band, as on the Dashboard")
        self.assertIn("Example Programme", self.text("#pubs-page .cover"))
        self.assertFalse(self.val("[...document.querySelectorAll('h2')].some(h => h.textContent.includes('Published reports'))"), "a page, not a Settings card with its own heading")
        self.assertEqual(self.val("[...document.querySelectorAll('#pubs-where dd')].map(d => d.textContent)"), ["/Users/example/clark reports/PDF", "Example Drive/Client reports"])
        self.assertEqual(self.val("[...document.querySelectorAll('#pubs-where dt')].map(d => d.textContent)"), ["Local folder", "Client folder"])
        self.assertEqual(self.text("#pubs-latest h2"), "Publication 3 · Week ending 23-10-2026")
        self.assertEqual(self.text("#pubs-latest p.muted"), "Published 28-10-2026 at 13:30 · Local folder, Client folder · Page, PDF · by Sam Example")
        self.assertEqual(self.text("#pubs-page .cover-line"), "Example Programme", "the cover line holds the project only: the intro is its own line, so no stray dot starts a wrapped line")
        self.assertEqual(self.text("#pubs-page .pubs-intro"), self.val("T.logic.INTRO"))
        latest = self.text("#pubs-latest")
        for part in ("Latest", "Publication 3", "Week ending 23-10-2026", "28-10-2026 at 13:30", "Local folder, Client folder", "Page, PDF", "Sam Example"):
            self.assertIn(part, latest)
        self.assertEqual(self.val("[...document.querySelectorAll('#pubs thead th')].map(th => th.textContent.replace('Open', '').trim())"), ["No.", "Week ending", "Published", "Went to", "Files", ""])
        rows = self.val("[...document.querySelectorAll('#pubs tbody tr')].map(tr => [...tr.cells].map(c => c.textContent).join('|'))")
        self.assertEqual(rows, ["2|16-10-2026|21-10-2026 at 12:15by Sam Example|Local folder|Word|Not keptArchive", "1|Not recorded|14-10-2026 at 20:40by Not recorded|Local folder|Page|Not keptArchive"])
        self.assertEqual(self.val("T.calls[0]"), ["list", "PDF"])
        # the band is the project's own: its colour and picture come from the brand tokens (as a brand's tokens.css sets them), not from a default
        pic = "data:image/gif;base64,R0lGODlhAQABAIAAAAUEBAAAACwAAAAAAQABAAACAkQBADs="
        look = f"""(() => {{ const c = document.querySelector('#pubs-page .cover'); return {{ bg: getComputedStyle(c).backgroundColor, pic: getComputedStyle(c, '::before').backgroundImage }}; }})()"""
        plain = self.val(look)
        self.assertEqual(plain["pic"], "none", "no own look: no picture")
        self.js(f"document.documentElement.style.setProperty('--brand-navy', 'rgb(12, 99, 34)'); document.documentElement.style.setProperty('--image-cover', 'url({pic})')")
        own = self.val(look)
        self.assertEqual(own["bg"], "rgb(12, 99, 34)", "the band takes the project's own colour")
        self.assertIn(pic, own["pic"], "the band shows the project's own picture")

    def test_row_1087_a_latest_with_no_week_says_no_week_instead_of_week_ending_not_recorded(self):
        self.replies(list=OK({**LIST, "total": 1, "shown": 1, "publications": [ROWS[2]]}))
        self.mount()
        self.assertEqual(self.text("#pubs-latest h2"), "Publication 1")
        self.assertNotIn("Not recorded Week", self.text("#pubs-latest"))

    def test_row_1087_times_are_in_the_persons_own_zone_and_the_zone_is_named(self):
        self.mount()
        self.assertIn("Times are shown in your time zone, Gulf Standard Time.", self.text("#pubs-note"))
        self.assertNotIn("UTC", self.text("#pubs"))
        self.assertEqual(self.val("T.logic.whenIn('2026-10-28T09:30:00Z', 'Asia/Dubai')"), "28-10-2026 at 13:30")
        self.assertEqual(self.val("T.logic.whenIn('2026-10-28T23:30:00Z', 'Asia/Dubai')"), "29-10-2026 at 03:30", "the day moves with the zone")
        self.assertEqual(self.val("T.logic.whenIn('2026-10-28T09:30:00Z', 'UTC')"), "28-10-2026 at 09:30")
        self.assertEqual(self.val("T.logic.whenIn(null, 'UTC')"), "Not recorded")
        self.assertEqual(self.val("T.logic.whenIn('nonsense', 'UTC')"), "Not recorded")

    def test_row_1087_no_folder_chosen_says_so_and_open_folder_is_not_offered(self):
        self.js("T.setFolders(null, null)")
        self.mount()
        self.assertEqual(self.val("[...document.querySelectorAll('#pubs-where dd')].map(d => d.textContent)"), ["Not chosen yet", "Not chosen yet"])
        self.assertFalse(self.present("[data-pub-folder]"))
        self.assertIn("The list comes from clark's own record of what it published, not from the folder, so other files in the folder are never shown.", self.text("#pubs-where"))

    def test_row_1087_change_in_settings_goes_to_settings(self):
        self.mount()
        self.click("#pubs-settings")
        self.assertEqual(self.val("T.went"), ["settings"])

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
        self.assertEqual(self.val("[...document.querySelectorAll('[data-pubarchive]')].map(b => b.dataset.pubarchive)"), ["3", "2", "1"], "the latest has its own Archive too")
        self.assertEqual(self.val("document.querySelector('[data-pubarchive]').getAttribute('aria-label')"), "Archive Publication 3")
        self.assertFalse(self.present("[data-pubrestore]"))
        self.assertEqual(self.val("T.calls[0]"), ["list", "PDF"], "the default list does not ask for the archived ones")
        self.assertEqual(self.text("#pubs-archived"), "Show archived 1")
        self.assertEqual(self.val("document.querySelector('#pubs-archived').getAttribute('aria-pressed')"), "false")

    def test_archive_asks_once_says_the_exact_words_with_no_undo_and_reads_the_list_again(self):
        self.replies(archive=OK({"ok": True, "code": "archived", "project": "PDF", "number": 3}))
        self.mount()
        self.replies(list=OK({**LIST, "total": 2, "shown": 2, "archived": 2, "publications": ROWS[1:]}))
        self.click("[data-pubarchive='3']")
        self.assertEqual(self.val("T.calls[1]"), ["archive", {"code": "PDF", "n": 3}])
        self.assertEqual(self.val("T.toasts"), [["done", "Publication 3 archived. Restore it from Show archived.", None]])
        self.assertEqual(self.val("T.calls[2]"), ["list", "PDF"])
        self.assertEqual(self.val("[...document.querySelectorAll('#pubs tbody tr')].map(tr => tr.dataset.pub)"), ["1"], "Publication 2 is now the latest, and is not in the earlier ones")
        self.assertEqual(self.val("document.querySelector('#pubs-latest').dataset.latest"), "2")
        self.assertEqual(self.text("#pubs-archived"), "Show archived 2")
        self.assertEqual(self.text(".pub-msg"), "")
        self.assertEqual(self.js("document.activeElement && document.activeElement.id"), "pubs-archived", "the archived row left the table: the focus goes to Show archived")

    def test_show_archived_lists_them_marked_with_restore_and_restore_says_its_words(self):
        self.replies(restore=OK({"ok": True, "code": "restored", "project": "PDF", "number": 2}))
        self.js("T.replies.list = (x) => (x && x.archived) ? " + lit(OK(SHOWING)) + " : " + lit(OK(LIST)))
        self.mount()
        self.click("#pubs-archived")
        self.assertEqual(self.val("T.calls[1]"), ["list", {"code": "PDF", "archived": True}])
        self.assertEqual(self.val("document.querySelector('#pubs-archived').getAttribute('aria-pressed')"), "true")
        self.assertEqual(self.val("[...document.querySelectorAll('#pubs tbody tr')].map(tr => tr.dataset.pub)"), ["2", "1"], "3 is the latest, above")
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
        self.assertEqual(self.js("document.activeElement && document.activeElement.dataset.pubarchive"), "3", "a refused Archive keeps the focus on its button")
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
        self.assertFalse(self.present("#pubs-latest"))

    def test_nothing_published_says_so(self):
        self.replies(list=OK({**LIST, "total": 0, "shown": 0, "archived": 0, "publications": []}))
        self.mount()
        self.assertEqual(self.text("#pubs-none"), "Nothing published yet. Each publish is listed here with its number.")
        self.assertFalse(self.present("#pubs-table"))

    def test_a_list_cut_to_ten_says_how_many_there_are(self):
        many = [{**ROWS[0], "number": n} for n in range(12, 2, -1)]
        self.replies(list=OK({**LIST, "total": 12, "shown": 10, "publications": many}))
        self.mount()
        self.assertEqual(self.val("document.querySelectorAll('#pubs tbody tr').length"), 9, "ten in all: the latest above and nine earlier ones")
        self.assertEqual(self.val("document.querySelectorAll('[data-pubopen]').length"), 10)
        self.assertIn("Showing the latest 10 of 12. The older ones are kept.", self.text("#pubs-note"))

    def test_a_server_that_does_not_answer_says_so_and_offers_try_again(self):
        self.replies(list={"status": 0, "body": None})
        self.mount()
        self.assertIn(self.val("T.logic.NOT_ANSWERING"), self.text("#pubs"))
        self.replies(list=OK(LIST))
        self.click("[data-pubs-again]")
        self.assertTrue(self.present("#pubs-table"))

    def test_row_1087_a_destination_the_server_does_not_say_is_not_called_a_local_folder(self):
        # past_reports.py says "Local" or "Local and to client", with " · Word" after either; anything else is not a destination the page knows.
        self.assertEqual(self.val("['Local', 'Local · Word', 'Local and to client', 'Local and to client · Word'].map(w => T.logic.rowView({number: 1, where: w}).went)"),
                         ["Local folder", "Local folder", "Local folder, Client folder", "Local folder, Client folder"])
        self.assertEqual(self.val("['Somewhere else', '', null, 7, undefined].map(w => T.logic.rowView({number: 1, where: w}).went)"), ["Not recorded"] * 5)

    def test_row_1087_the_intro_is_readable_on_the_cover_band_at_1400_and_900_in_light_and_dark(self):
        probe = """(() => { const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
          const lum = (c) => { const [r, g, b] = rgb(c).map(v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }); return .2126 * r + .7152 * g + .0722 * b; };
          const i = document.querySelector('#pubs-page .pubs-intro'), t = document.querySelector('#pubs-page .cover h1'), band = getComputedStyle(document.querySelector('#pubs-page .cover')).backgroundColor;
          const a = lum(getComputedStyle(i).color), b = lum(band);
          return {intro: getComputedStyle(i).color, title: getComputedStyle(t).color, ratio: (Math.max(a, b) + .05) / (Math.min(a, b) + .05)}; })()"""
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme):
                    self.load(width=width, theme=theme)
                    self.replies(list=OK(LIST), tab=True)
                    self.mount()
                    got = self.val(probe)
                    self.assertEqual(got["intro"], got["title"], "the intro is the cover title's colour")
                    self.assertGreaterEqual(got["ratio"], 4.5, "readable on the band")

    def test_hostile_text_in_a_row_is_drawn_as_text(self):
        evil = '<img src=x onerror="window.pwned = 1">'
        self.replies(list=OK({**LIST, "publications": [{**ROWS[0], "who": evil, "where": evil, "week": evil, "at": evil}, {**ROWS[1], "who": evil}]}))
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
                    self.assertTrue(self.val("[...document.querySelectorAll('#pubs .tag')].every(t => t.getClientRects().length === 1 && t.getBoundingClientRect().height < 30)"), "the Archived tag is on one line")
                    self.assertTrue(self.val("[...document.querySelectorAll('#pubs td.num, #pubs td.files')].every(td => getComputedStyle(td).whiteSpace === 'nowrap')"))
                    self.assertTrue(self.val("[...document.querySelectorAll('#pubs button, #pubs td')].every(b => b.getBoundingClientRect().right <= innerWidth)"))
                    self.assertTrue(self.val("(() => { const c = getComputedStyle(document.querySelector('#pubs td')).color; return c !== getComputedStyle(document.body).backgroundColor; })()"))
                    self.assertTrue(self.val("(() => { const c = getComputedStyle(document.querySelector('#pubs-page .pp-frame')).backgroundColor; return c !== 'rgba(0, 0, 0, 0)'; })()"))


if __name__ == "__main__":
    unittest.main()
