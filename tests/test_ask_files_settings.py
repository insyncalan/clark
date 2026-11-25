"""Row 1294: the Files cards on the ask clark page, in a real browser (desktop widths 1400 and 900), and the ask_files columns' migration.

Run: python3 dev/run_tests.py test_ask_files_settings
Ticket 1294, test 1: the cards come in the ticket's order. On the All projects tab the standing instructions come, then Files, then the source folders;
on a project's tab the project's source folders and standing instructions come, then Files. The switches and buttons are named for a screen
reader. The page's fetch of /api/ask-files is replaced by the answers the server gives. Chrome is required: fails, never skips.
"""
import json
import sqlite3
import tempfile
import unittest

from _editor_checks import for_project
from _paths import SRC  # noqa: F401
from test_ask_settings import make_db, service
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import page
from clark import store as st

WIDTHS = (1400, 900)
FAKE = """
window.__f = {calls: [], on: true, off_here: false};
const real = window.fetch;
window.fetch = function (url, opts) {
  if (String(url).indexOf('/api/ask-files') < 0) return real.apply(this, arguments);
  const body = opts && opts.body ? JSON.parse(opts.body) : null;
  window.__f.calls.push(body);
  if (body && body.on !== undefined) window.__f.on = body.on;
  if (body && body.off_here !== undefined) window.__f.off_here = body.off_here;
  return Promise.resolve(new Response(JSON.stringify({ok: true, on: window.__f.on, off_here: window.__f.off_here, allowed: true, apply_id: 7}), {status: 200, headers: {'Content-Type': 'application/json'}}));
};
"""
ORDER = "[...document.querySelectorAll('section.setting')].map(s => s.id).filter(i => %s)"
ALL_ORDER = ["ask-instructions-all-card", "ask-files-all", "ask-all-folders"]
PROJECT_ORDER = ["ask-folders-card", "ask-instructions-own-card", "ask-files-project"]
ALL_SECTIONS = ["ask-all", "ai-settings", "ask-connectors", "ask-instructions-all-card", "ask-files-all", "slash-all", "ask-all-folders", "ask-chats-all", "ask-safety", "ask-usage-all"]
PROJECT_SECTIONS = ["ask-settings", "ask-used-all", "ask-connectors-project", "ask-folders-card", "ask-instructions-own-card", "slash-project", "ask-files-project", "ask-chats-project", "ask-usage-project"]


class FilesCards(unittest.TestCase):
    theme = "prototype-2.0"          # Classic: the Files cards are drawn here only; Cards is frozen (see test_ask_files_cards_1294)

    def setUp(self):
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=self.theme))
        self.addCleanup(self.s.close)
        self.s.httpd.app_settings = service(make_db(tempfile.mkdtemp(), cleanup=self.addCleanup))

    def show(self, cdp, tab):
        sid = self.sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
        js = lambda e: cdp.js(e, sid)          # noqa: E731
        js(FAKE)
        js("location.hash = '#dashboard&p=ABC'")
        wait(lambda: js("!document.querySelector('#ask-settings')"), 10)
        js("location.hash = '#settings&p=ABC&s=claude'")
        self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-settings')"), 20))
        if tab == "all":
            js("document.querySelector('[data-ask-tab=all]').click()")
        return js

    def test_the_all_projects_tab_has_instructions_then_files_then_the_folders_at_1400_and_900(self):
        with chrome() as cdp:
            js = self.show(cdp, "all")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-files-switch]')"), 10))
            ids = "['ask-instructions-all-card','ask-files-all','ask-all-folders'].indexOf(i) >= 0"
            self.assertEqual(js("JSON.stringify(" + ORDER % ids + ")"), '["ask-instructions-all-card","ask-files-all","ask-all-folders"]')
            self.assertEqual(js("document.querySelector('#ask-files-all h2').innerText"), "Files")
            self.assertEqual(js("[...document.querySelectorAll('#ask-files-all button')].map(b => (b.getAttribute('role') || 'button') + '/' + b.getAttribute('aria-label') + '/' + b.getAttribute('aria-checked')).join()"), "switch/Files/true")
            self.assertFalse(js("!!document.querySelector('#ask-files-project')"), "the project's card is not on the All tab")
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.assertTrue(wait(lambda: js("document.documentElement.scrollWidth <= window.innerWidth"), 10), f"no sideways scroll at {w}")
                self.assertTrue(wait(lambda: js("(function(){const r = document.querySelector('[data-files-switch]').getBoundingClientRect(); return r.width > 0 && r.right <= window.innerWidth})()"), 10), f"the switch is on the page at {w}")
            js("document.querySelector('[data-files-switch]').click()")
            self.assertTrue(wait(lambda: js("document.querySelector('[data-files-switch]').getAttribute('aria-checked')") == "false", 10))
            self.assertEqual(js("document.querySelector('[data-files-undo]').innerText"), "Undo")
            self.assertEqual(js("document.querySelector('[data-files-undo]').tagName + '/' + document.querySelector('[data-files-undo]').type"), "BUTTON/button")
            js("document.querySelector('[data-files-undo]').click()")
            self.assertEqual(js("JSON.stringify(window.__f.calls.filter(Boolean))"), '[{"on":false},{"undo":7}]')

    def test_a_project_tab_has_folders_and_instructions_then_files_at_1400_and_900(self):
        with chrome() as cdp:
            js = self.show(cdp, "project")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-files-here]')"), 10))
            ids = "['ask-folders-card','ask-instructions-own-card','ask-files-project'].indexOf(i) >= 0"
            self.assertEqual(js("JSON.stringify(" + ORDER % ids + ")"), '["ask-folders-card","ask-instructions-own-card","ask-files-project"]')
            self.assertEqual(js("document.querySelector('#ask-files-project h2').innerText"), "Files in ABC")
            self.assertEqual(js("[...document.querySelectorAll('#ask-files-project button')].map(b => (b.getAttribute('role') || 'button') + '/' + b.getAttribute('aria-label') + '/' + b.getAttribute('aria-checked')).join()"), "switch/Files in ABC/true")
            self.assertFalse(js("!!document.querySelector('#ask-files-all')"), "the All card is not on a project's tab")
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.assertTrue(wait(lambda: js("document.documentElement.scrollWidth <= window.innerWidth"), 10), f"no sideways scroll at {w}")
                self.assertTrue(wait(lambda: js("(function(){const r = document.querySelector('[data-files-here]').getBoundingClientRect(); return r.width > 0 && r.right <= window.innerWidth})()"), 10), f"the switch is on the page at {w}")
            js("document.querySelector('[data-files-here]').click()")
            self.assertTrue(wait(lambda: js("document.querySelector('[data-files-here]').getAttribute('aria-checked')") == "false", 10))
            self.assertEqual(js("JSON.stringify(window.__f.calls.slice(-1)[0])"), '{"project":"ABC","off_here":true}')

    def test_there_is_no_pictures_switch_on_either_tab_at_1400_and_900(self):
        """Row 1294 AP4: nothing reads a picture yet, so Files for asking has no Pictures switch: the card has the one Files control and only its own words, and nothing on the tab speaks of pictures."""
        kinds = "button, input, select, textarea, a, [role], [tabindex]"
        card_probe = ("(function(){const c = document.querySelector('%s');"
                      " const attrs = e => ['title', 'alt', 'placeholder', 'aria-label'].map(a => e.getAttribute(a) || '').join(' ');"
                      " return JSON.stringify({controls: [...c.querySelectorAll('" + kinds + "')].map(e => e.tagName + '/' + (e.getAttribute('role') || '') + '/' + (e.getAttribute('aria-label') || '')),"
                      " text: c.textContent.replace(/\\s+/g, ' ').trim(),"
                      " names: [c, ...c.querySelectorAll('*')].map(attrs).map(x => x.trim()).filter(x => x)})})()")
        scan = ("JSON.stringify([...document.querySelectorAll('#ask-settings, #ask-settings *')].filter(e => !/^(SCRIPT|STYLE)$/.test(e.tagName)).flatMap(e => {"
                " const own = [...e.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(' ').replace(/\\s+/g, ' ').trim();"
                " const names = ['title', 'alt', 'placeholder', 'aria-label', 'value'].map(a => e.getAttribute(a) || '').join(' ').trim();"
                " return [own, names].filter(x => /picture|image|photo|screenshot/i.test(x));}))")
        sections = "JSON.stringify([...document.querySelectorAll('section.setting')].map(s => s.id))"
        line = "Files: text, Markdown and CSV (5 files of 10 MB, for that question only). A project can turn these off for itself."
        cases = (("all", "#ask-files-all", "[data-files-switch]", ALL_SECTIONS,
                  {"controls": ["BUTTON/switch/Files", "DIV/alert/"], "text": "Files" + line, "names": ["Files"]}),
                 ("project", "#ask-files-project", "[data-files-here]", PROJECT_SECTIONS,
                  {"controls": ["BUTTON/switch/Files in ABC", "DIV/alert/"], "text": "Files in ABCFiles On for all projects. Turn it off here for ABC only.", "names": ["Files in ABC"]}))
        for tab, card, switch, order, expected in cases:
            for w in WIDTHS:
                with self.subTest(tab=tab, width=w), chrome() as cdp:
                    js = self.show(cdp, tab)
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                    self.assertTrue(wait(lambda: js("!!document.querySelector('%s')" % switch), 10))
                    self.assertEqual(json.loads(js(card_probe % card)), expected, "the card has the one Files control and only its own words")
                    self.assertEqual(json.loads(js(sections)), order, "the tab has exactly these cards")
                    for hit in json.loads(js(scan)):
                        self.assertIn("text, Markdown and CSV", hit, "a word about pictures on the Claude tab outside the known Files line")
                        self.assertEqual(hit, line)

    # The migration (schema 32 to 33): the two columns, added once, no value changed.
    def test_the_migration_keeps_an_old_file_and_a_second_run_keeps_a_set_switch(self):
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        con.execute("CREATE TABLE app_settings (id INTEGER PRIMARY KEY, theme TEXT)")
        con.execute("CREATE TABLE projects (code TEXT PRIMARY KEY)")
        con.execute("INSERT INTO app_settings VALUES (1, 'cards')")
        con.execute("INSERT INTO projects VALUES ('ABC')")
        con.execute("INSERT INTO projects VALUES ('OTH')")
        st.migrate_ask_files(con)
        self.assertEqual([tuple(r) for r in con.execute("SELECT theme, ask_files FROM app_settings")], [("cards", 1)], "the old row is kept and Files are on")
        self.assertEqual([tuple(r) for r in con.execute("SELECT code, ask_files_off FROM projects ORDER BY code")], [("ABC", 0), ("OTH", 0)])
        con.execute("UPDATE app_settings SET ask_files = 0")
        con.execute("UPDATE projects SET ask_files_off = 1 WHERE code = 'ABC'")
        st.migrate_ask_files(con)
        self.assertEqual([tuple(r) for r in con.execute("SELECT theme, ask_files FROM app_settings")], [("cards", 0)], "a second run keeps a switch that is set")
        self.assertEqual([tuple(r) for r in con.execute("SELECT code, ask_files_off FROM projects ORDER BY code")], [("ABC", 1), ("OTH", 0)])
        empty = sqlite3.connect(":memory:")
        empty.row_factory = sqlite3.Row
        st.migrate_ask_files(empty)      # no table at all: nothing to do, nothing fails
        self.assertGreaterEqual(st.SCHEMA_VERSION, 33)
        self.assertIn((33, st.migrate_ask_files), st.MIGRATIONS)


if __name__ == "__main__":
    unittest.main()
