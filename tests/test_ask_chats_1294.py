"""Row 1294 (mock-up A8): Chats kept (All projects tab) and the open project's earlier chats with Clear all chats, in a real browser at 1400 and 900.

Run: python3 dev/run_tests.py test_ask_chats_1294
The chats and the number kept are in the browser (askHistory.js), so the test seeds localStorage. Chrome is required."""
import json
import unittest

import test_ask_panel
from test_report_editor import Base
from test_server import chrome

from test_ask_tabs_1294 import Tabs, WIDTHS

CHAT = lambda i: {"id": str(i), "at": 1000 + i, "title": f"q{i}", "turns": [{"role": "user", "text": f"q{i}"}, {"role": "assistant", "text": "a"}]}  # noqa: E731


class Chats(Tabs):
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
            self.assertEqual(js("document.querySelector('#ask-chats-project h2').textContent"), "Chats and usage in ABC")
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
            js("var s = document.querySelector('#ask-chats-keep'); s.value = '10'; s.dispatchEvent(new Event('change', {bubbles: true}))")
            self.until(js, "localStorage.getItem('clark.askChatsKeep') === '10'", "the choice is kept")
            reload_to_new_page(js, seconds=20)
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.until(js, "!!document.querySelector('#ask-chats-keep') && document.querySelector('#ask-chats-keep').value === '10'", "kept after a reload")


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


if __name__ == "__main__":
    unittest.main()
