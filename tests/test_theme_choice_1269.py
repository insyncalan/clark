"""Row 1269: the Theme card in Settings (Publishing group, next to Brand), in a real browser at 1400 and 900 px, light and dark.
Run: python3 dev/run_tests.py test_theme_choice_1269

The card shows the server's choice (Clark Classic is the default), choosing the other one POSTs it to /api/theme and it survives a reload,
and a save the server refuses keeps the old choice and says why. The page keeps nothing in the browser's storage. Chrome is required."""
import re
import tempfile
import unittest
from pathlib import Path

from _new_page import reload_to_new_page
from _editor_checks import for_project
from test_appearance import scheme
from test_ask_settings import make_db, service
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import page, store as st

WIDTHS = (1400, 900)
MODES = ("light", "dark")
EDIT = Path(page.PAGE).parent / "src" / "edit"
CHECKED = "(document.querySelector('#theme-settings input[name=theme-choice]:checked') || {}).value"
FAIL = """const real = window.fetch; window.__posts = [];
window.fetch = function (url, opts) {
  if (String(url).indexOf('/api/theme') >= 0 && opts && opts.method === 'POST') { window.__posts.push(opts.body);
    return Promise.resolve(new Response(JSON.stringify({ok: false, code: 'busy', message: 'The data file is busy. Nothing was changed.'}), {status: 409, headers: {'Content-Type': 'application/json'}})); }
  return real.apply(this, arguments); };"""


def stored(db):
    store = st.open_store(db, onedrive_roots=[])
    try:
        return store.theme()
    finally:
        store.close()


class Choice(unittest.TestCase):
    def setUp(self):
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(self.s.close)
        folder = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.db = make_db(folder, cleanup=self.addCleanup)
        self.s.httpd.app_settings = service(self.db)

    def show(self, cdp, w, mode):
        sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=theme"))
        js = lambda e: cdp.js(e, sid)          # noqa: E731
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        scheme(type("P", (), {"cdp": cdp, "sid": sid})(), mode)
        self.assertTrue(wait(lambda: js("!!document.querySelector('#theme-settings input[name=theme-choice]')"), 20), "the Theme card drew its choices")
        return js

    def until(self, js, expr, expected, what):
        seen = []
        self.assertTrue(wait(lambda: (seen.__setitem__(slice(None), [js(expr)]), seen[0] == expected)[1], 20), f"{what}: wanted {expected!r}, saw {seen}")

    def test_the_card_shows_the_servers_choice_and_the_other_one_is_kept_across_a_reload(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    self.s.httpd.app_settings.change_theme({"theme": "classic"})
                    js = self.show(cdp, w, mode)
                    self.assertEqual(js("document.querySelector('#theme-settings h2').textContent"), "Theme")
                    self.assertEqual(js("[...document.querySelectorAll('#theme-settings label')].map(l => l.querySelector('span').textContent)"),
                                     ["Clark Classic (default)", "Clark Cards"])
                    self.assertEqual(js(CHECKED), "classic")
                    self.assertTrue(js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")
                    js("document.querySelector('#theme-settings input[value=cards]').click()")
                    self.until(js, CHECKED, "cards", "Clark Cards chosen")
                    self.assertTrue(wait(lambda: stored(self.db) == "cards", 20), "the server holds it")
                    self.assertEqual(js("localStorage.length"), 0, "nothing in the browser's storage")
                    reload_to_new_page(js, seconds=20)
                    self.until(js, CHECKED, "cards", "still Clark Cards after a reload")
                    js("document.querySelector('#theme-settings input[value=classic]').click()")
                    self.assertTrue(wait(lambda: stored(self.db) == "classic", 20), "back to Clark Classic")

    def test_the_card_starts_on_what_the_server_holds(self):
        with chrome() as cdp:
            self.s.httpd.app_settings.change_theme({"theme": "cards"})
            js = self.show(cdp, 1400, "light")
            self.assertEqual(js(CHECKED), "cards")

    def test_a_failed_save_keeps_the_old_choice_and_says_why(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    js = self.show(cdp, w, mode)
                    js(FAIL)
                    js("document.querySelector('#theme-settings input[value=cards]').click()")
                    self.until(js, "(document.querySelector('#theme-settings .pub-msg') || {}).innerText.length > 0", True, "a reason is shown")
                    self.assertIn("busy", js("document.querySelector('#theme-settings .pub-msg').innerText"))
                    self.assertEqual(js(CHECKED), "classic", "the old choice is kept")
                    self.assertEqual(stored(self.db), "classic")
                    self.assertEqual(js("window.__posts.length"), 1)

    def test_the_card_uses_no_browser_storage(self):
        for name in ("themeState.js", "ThemeSettings.jsx"):
            text = (EDIT / name).read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"localStorage|sessionStorage|indexedDB|document\.cookie", text), name)


if __name__ == "__main__":
    unittest.main()
