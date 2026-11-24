"""Row 1294 (mock-up A8): Chats kept (All projects tab) and the open project's earlier chats with Clear all chats, in a real browser at 1400 and 900.

Run: python3 dev/run_tests.py test_ask_chats_1294
The chats and the number kept are in the browser (askHistory.js), so the test seeds localStorage. Chrome is required."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import test_ask_panel
from test_report_editor import Base
from test_server import Running, chrome

from test_ask_tabs_1294 import Tabs, WIDTHS
from test_ask_settings import make_db, service
from test_page import DATA
from clark import page

CHAT = lambda i: {"id": str(i), "at": 1000 + i, "title": f"q{i}", "turns": [{"role": "user", "text": f"q{i}"}, {"role": "assistant", "text": "a"}]}  # noqa: E731


class ThemedTabs(Tabs):
    THEME = "prototype-2.0"                       # row 1294 is Classic only: the Chats cards are drawn with the Theme

    def setUp(self):
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=self.THEME))
        self.addCleanup(self.s.close)
        d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, d, True)
        self.s.httpd.app_settings = service(make_db(d))


class Chats(ThemedTabs):
    def seed(self, js, code, n):
        js(f"localStorage.setItem('clark.askChats.{code}', {json.dumps(json.dumps([CHAT(i) for i in range(n, 0, -1)]))})")

    def test_the_project_tab_counts_and_clears_only_this_projects_chats(self):
        from _new_page import reload_to_new_page
        with chrome() as cdp:
            js = self.show(cdp)
            self.seed(js, "ABC", 4)
            self.seed(js, "XYZ", 2)
            reload_to_new_page(js, seconds=20)
            self.until(js, "!!document.querySelector('#ask-chats-clear')", "the chats card")
            self.assertEqual(js("document.querySelector('#ask-chats-project h2').textContent"), "Chats in ABC")
            self.assertEqual(js("document.querySelector('#ask-chats-note').textContent"), "Kept in this browser for ABC.")
            self.until(js, "document.querySelector('#ask-chats-clear').innerText === 'Clear all chats (4)'", "counts this project's chats only")
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.until(js, "document.documentElement.scrollWidth <= window.innerWidth", f"no sideways scroll at {w}")
            js("document.querySelector('#ask-chats-clear').click()")
            self.until(js, "document.querySelector('#ask-chats-clear').innerText === 'Clear all chats (0)' && document.querySelector('#ask-chats-clear').disabled", "cleared")
            self.assertEqual(js("localStorage.getItem('clark.askChats.ABC')"), "[]")
            self.assertEqual(len(json.loads(js("localStorage.getItem('clark.askChats.XYZ')"))), 2, "another project's chats stay")

    def test_the_all_tab_offers_10_20_30_50_100_default_30_and_keeps_the_choice(self):
        from _new_page import reload_to_new_page
        with chrome() as cdp:
            js = self.show(cdp)
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.until(js, "!!document.querySelector('#ask-chats-keep')", "the Chats card")
            self.assertEqual(js("document.querySelector('#ask-chats-all h2').textContent"), "Chats")
            self.assertEqual(js("[...document.querySelectorAll('#ask-chats-keep option')].map(o => o.textContent)"), ["10", "20", "30", "50", "100"])
            self.assertEqual(js("document.querySelector('#ask-chats-keep').value"), "30")
            self.assertEqual(js("document.querySelector('#ask-chats-line').textContent"),
                             "The most recent chats kept for each project, in this browser. Clearing them is done in a project's tab.")
            self.assertEqual(js("document.querySelector('#ask-chats-older').textContent"), "Older chats go the next time a chat is saved.")
            js("var s = document.querySelector('#ask-chats-keep'); s.value = '10'; s.dispatchEvent(new Event('change', {bubbles: true}))")
            self.until(js, "localStorage.getItem('clark.askChatsKeep') === '10'", "the choice is kept")
            reload_to_new_page(js, ready="!!document.querySelector('[data-ask-tab=all]')", what="the new page with its tabs", seconds=20)
            self.until(js, "(() => { const b = document.querySelector('[data-ask-tab=all]'); if (b && !document.querySelector('#ask-chats-keep')) b.click(); return !!document.querySelector('#ask-chats-keep'); })()", "the Chats card after the reload", seconds=20)
            self.assertEqual(js("document.querySelector('#ask-chats-keep').value"), "10", "kept after a reload")

    def test_a_stored_number_that_is_not_an_offered_one_reads_as_30(self):
        # askHistory.js readKeep: 7 and 0 are not in 10/20/30/50/100, so the select shows 30.
        from _new_page import reload_to_new_page
        with chrome() as cdp:
            js = self.show(cdp)
            for bad in ("7", "0", "100.5"):
                js(f"localStorage.setItem('clark.askChatsKeep', '{bad}')")
                reload_to_new_page(js, seconds=20)
                self.until(js, "!!document.querySelector('[data-ask-tab=all]')", "the tabs")
                js("document.querySelector('[data-ask-tab=all]').click()")
                self.until(js, "!!document.querySelector('#ask-chats-keep')", "the Chats card")
                self.assertEqual(js("document.querySelector('#ask-chats-keep').value"), "30", f"stored {bad}")

    def test_entries_in_the_store_that_are_not_chats_are_ignored(self):
        # askHistory.js chats(): null, a number, a chat without turns and one without a text id are skipped; the two real chats count.
        from _new_page import reload_to_new_page
        with chrome() as cdp:
            js = self.show(cdp)
            mixed = [None, 5, "x", {"id": "a"}, {"id": 7, "turns": []}, {"turns": []}, CHAT(1), CHAT(2)]
            js(f"localStorage.setItem('clark.askChats.ABC', {json.dumps(json.dumps(mixed))})")
            reload_to_new_page(js, seconds=20)
            self.until(js, "!!document.querySelector('#ask-chats-clear')", "the chats card")
            self.until(js, "document.querySelector('#ask-chats-clear').innerText === 'Clear all chats (2)'", "only the real chats count")

    def test_the_controls_have_names_and_fit_at_1400_and_900(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.seed(js, "ABC", 3)
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                js("document.querySelector('[data-ask-tab=all]').click()")
                self.until(js, "!!document.querySelector('#ask-chats-keep')", f"the select at {w}")
                self.assertEqual(js("document.querySelector('#ask-chats-keep').labels.length"), 1, f"one label at {w}")
                self.assertEqual(js("document.querySelector('#ask-chats-keep').labels[0].textContent"), "Chats kept", f"select name at {w}")
                self.assertEqual(js("document.querySelector('#ask-chats-keep').getAttribute('aria-label')"), None)
                self.assertTrue(js("(() => { const r = document.querySelector('#ask-chats-keep').getBoundingClientRect(); return r.width > 0 && r.right <= window.innerWidth; })()"), f"select inside at {w}")
                self.assertTrue(js("document.documentElement.scrollWidth <= window.innerWidth"), f"no overflow at {w}")
                js("document.querySelector('[data-ask-tab]:not([data-ask-tab=all])').click()")
                self.until(js, "!!document.querySelector('#ask-chats-clear')", f"the button at {w}")
                self.assertEqual(js("document.querySelector('#ask-chats-clear').tagName"), "BUTTON")
                self.assertEqual(js("document.querySelector('#ask-chats-clear').textContent"), "Clear all chats (3)", f"button name at {w}")
                self.assertTrue(js("(() => { const r = document.querySelector('#ask-chats-clear').getBoundingClientRect(); return r.width > 0 && r.right <= window.innerWidth; })()"), f"button inside at {w}")
                self.assertTrue(js("document.documentElement.scrollWidth <= window.innerWidth"), f"no overflow at {w}")

    ORDER = "[...document.querySelectorAll('section.frame.setting')].map(e => e.id)"

    def test_the_cards_follow_the_ticket_order_chats_after_instructions_and_folders(self):
        # Ticket 1294, test 1: on the All tab Chats comes after instructions and folders; on a project tab Usage is last, Chats directly before it.
        with chrome() as cdp:
            js = self.show(cdp)
            self.until(js, "!!document.querySelector('#ask-chats-project')", "the project tab")
            ids = js(self.ORDER)
            self.assertLess(ids.index("ask-folders-card"), ids.index("ask-instructions-own-card"))
            self.assertLess(ids.index("ask-instructions-own-card"), ids.index("ask-chats-project"))
            self.assertEqual(ids[-2:], ["ask-chats-project", "ask-usage-project"], "Usage is last, Chats directly before it")
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.until(js, "!!document.querySelector('#ask-chats-all')", "the All tab")
            ids = js(self.ORDER)
            self.assertLess(ids.index("ask-instructions-all-card"), ids.index("ask-chats-all"))
            self.assertLess(ids.index("ask-all-folders"), ids.index("ask-chats-all"))


class CardsUnchanged(ThemedTabs):
    THEME = None

    def test_cards_draws_no_chats_card_on_either_tab(self):
        # Classic only: Cards (no Theme) renders the Settings page as on main, so no Chats node, id or text on the project tab or the All tab.
        gone = "!document.querySelector('[id^=ask-chats]') && !/Clear all chats|Chats kept/.test(document.body.innerText)"
        with chrome() as cdp:
            js = self.show(cdp)
            self.until(js, "!!document.querySelector('#ask-used-all')", "the project tab")
            self.assertTrue(js("!document.getElementById('theme')"), "no Theme on this page")
            self.assertTrue(js(gone), "project tab")
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.until(js, "!!document.querySelector('#ask-all')", "the All tab")
            self.assertTrue(js(gone), "All tab")


class Drop(Base):
    def setUp(self):
        super().setUp()
        self.s.httpd.ask = test_ask_panel.Stub()

    opened = test_ask_panel.Panel.opened
    ask = test_ask_panel.Panel.ask

    def test_a_save_after_lowering_the_number_drops_the_oldest(self):
        with chrome() as cdp:
            p = self.opened(cdp)
            code = p.js("(location.hash.match(/p=([^&]+)/) || [])[1]")
            seed = json.dumps(json.dumps([CHAT(i) for i in range(15, 0, -1)]))
            p.js(f"localStorage.setItem('clark.askChats.{code}', {seed}); localStorage.setItem('clark.askChatsKeep', '10')")
            self.ask(p, "When is go-live?")
            p.until("document.querySelectorAll('.ask-turn').length === 2", "the answer")
            p.until(f"JSON.parse(localStorage.getItem('clark.askChats.{code}')).length === 10", "ten kept")
            ids = json.loads(p.js(f"JSON.stringify(JSON.parse(localStorage.getItem('clark.askChats.{code}')).map(c => c.title))"))
            self.assertEqual(ids[0], "When is go-live?")
            self.assertEqual(ids[1:], [f"q{i}" for i in range(15, 6, -1)], "the oldest went")

    def test_thirty_chats_are_kept_per_project_and_a_move_keeps_the_open_chat(self):
        """Row 1578 AP1 (parent 1292 AP5): 30 chats kept for each project (the 31st oldest goes), another project's chats are not touched, and a move to it and back keeps the chat that was open."""
        from _demo import USER
        with self.store.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Other Programme", "health": "On track"})
        for w in (1400, 900):
            with self.subTest(width=w), chrome() as cdp:
                p = self.opened(cdp)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                seed = lambda code, n: p.js(f"localStorage.setItem('clark.askChats.{code}', {json.dumps(json.dumps([CHAT(i) for i in range(n, 0, -1)]))})")  # noqa: E731
                seed("ABC", 30)
                seed("XYZ", 2)
                self.ask(p, "When is go-live?")
                p.until("document.querySelectorAll('.ask-turn').length === 2", "the answer")
                p.until("JSON.parse(localStorage.getItem('clark.askChats.ABC')).length === 30 && JSON.parse(localStorage.getItem('clark.askChats.ABC'))[0].title === 'When is go-live?'", "the new chat is first and 30 are kept")
                titles = json.loads(p.js("JSON.stringify(JSON.parse(localStorage.getItem('clark.askChats.ABC')).map(c => c.title))"))
                self.assertEqual(len(titles), 30)
                self.assertNotIn("q1", titles, "the oldest of the 31 went")
                self.assertIn("q2", titles, "the second oldest stays")
                self.assertEqual(len(json.loads(p.js("localStorage.getItem('clark.askChats.XYZ')"))), 2, "another project's chats stay")
                p.js("location.hash = '#dashboard&p=XYZ'")
                p.until("location.hash.indexOf('p=XYZ') >= 0", "on XYZ")
                p.js("location.hash = '#dashboard&p=ABC'")
                p.until("location.hash.indexOf('p=ABC') >= 0", "back on ABC")
                p.until("!!document.querySelector('[data-id]')", "the page is drawn")
                if not p.js("!!document.querySelector('#ask-panel')"):
                    p.key("/", code="Slash", vk=191)
                    p.until("!!document.querySelector('#ask-panel')", "the panel opened again")
                p.until("!document.querySelector('#ask-send').disabled", "ready")
                p.js("document.querySelector('#ask-history').click()")
                p.until("document.querySelectorAll('#ask-hist .ask-hist-open').length === 30", "the list shows the 30 chats of this project")
                self.assertEqual(p.js("document.querySelector('#ask-hist .ask-hist-title').textContent"), "When is go-live?", "the chat that was open is kept, newest first")
                p.js("document.querySelector('#ask-hist .ask-hist-open').click()")
                p.until("document.querySelectorAll('.ask-turn').length === 2", "the kept chat opens with its 2 turns")
                self.assertEqual(len(json.loads(p.js("localStorage.getItem('clark.askChats.ABC')"))), 30)
                self.assertEqual(len(json.loads(p.js("localStorage.getItem('clark.askChats.XYZ')"))), 2)


if __name__ == "__main__":
    unittest.main()
