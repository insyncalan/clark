"""Row 1363: Classic is the only theme the user sees. Settings > Theme offers no Cards; a stored 'cards' value stays in the
file untouched but Classic is applied (served page, published file); nothing can switch the setting to Cards.
Fictional data only. Run: python3 dev/run_tests.py test_theme_classic_only_1363   (the browser test needs Chrome)"""
import shutil
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
from _new_page import reload_to_new_page
from _editor_checks import for_project
from test_appearance import scheme
from test_ask_settings import make_db, service
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import __main__ as launcher, page, publish, theme
from clark.store import open_store

NAME = "prototype-2.0"
WIDTHS = (1400, 900)
MODES = ("light", "dark")


def stored(db):
    s = open_store(db, onedrive_roots=[])
    try:
        return s.con.execute("SELECT theme FROM app_settings WHERE id = 1").fetchone()[0]
    finally:
        s.close()


def put(db, value):
    s = open_store(db, onedrive_roots=[])
    try:
        with s.con:
            s.con.execute("UPDATE app_settings SET theme = ? WHERE id = 1", (value,))
    finally:
        s.close()


class Applied(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.db = self.dir / "clark.db"
        open_store(self.db, onedrive_roots=[]).close()

    def served(self):
        return launcher.page_of(self.db, onedrive_roots=[])(None)

    def test_every_setting_maps_to_the_classic_folder(self):
        for value in ("classic", "cards", None, "", 5, "../x"):
            self.assertEqual(theme.name_for(value), NAME, value)

    def test_a_stored_cards_value_serves_the_classic_page(self):
        put(self.db, "cards")
        html = self.served()
        self.assertEqual(html.count('id="theme"'), 1)
        self.assertEqual(html, page.page_html(branding=page.NO_BRAND, theme=NAME))

    def test_a_stored_cards_value_is_published_in_classic(self):
        put(self.db, "cards")
        s = open_store(self.db, onedrive_roots=[])
        try:
            self.assertEqual(publish.theme_of(s), NAME)
        finally:
            s.close()

    def test_the_stored_value_is_not_rewritten(self):
        put(self.db, "cards")
        self.served()
        s = open_store(self.db, onedrive_roots=[])
        try:
            self.assertEqual(s.theme(), "cards")
            theme.of_store(s)
        finally:
            s.close()
        self.assertEqual(stored(self.db), "cards")

    def test_the_default_page_function_is_unchanged(self):
        self.assertNotIn('id="theme"', page.page_html(branding=page.NO_BRAND))


class Route(unittest.TestCase):
    def setUp(self):
        folder = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.db = make_db(folder, cleanup=self.addCleanup)
        self.svc = service(self.db)

    def test_cards_cannot_be_chosen_and_nothing_is_written(self):
        put(self.db, "classic")
        status, body = self.svc.change_theme({"theme": "cards"})
        self.assertEqual(status, 400)
        self.assertEqual(stored(self.db), "classic")

    def test_reading_leaves_a_stored_cards_value_alone(self):
        put(self.db, "cards")
        self.svc.read_theme()
        self.assertEqual(stored(self.db), "cards")


class Control(unittest.TestCase):
    def setUp(self):
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(self.s.close)
        folder = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.db = make_db(folder, cleanup=self.addCleanup)
        self.s.httpd.app_settings = service(self.db)

    def test_the_theme_card_offers_only_classic_whatever_is_stored(self):
        for value in ("classic", "cards"):
            put(self.db, value)
            for w in WIDTHS:
                for mode in MODES:
                    with self.subTest(stored=value, width=w, mode=mode), chrome() as cdp:
                        sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=theme"))
                        js = lambda e: cdp.js(e, sid)          # noqa: E731
                        cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                        scheme(type("P", (), {"cdp": cdp, "sid": sid})(), mode)
                        self.assertTrue(wait(lambda: js("!!document.querySelector('#theme-settings')"), 20))
                        self.assertEqual(js("[...document.querySelectorAll('#theme-settings label')].map(l => l.querySelector('span').textContent)"), ["Classic"])
                        self.assertEqual(js("document.querySelectorAll('#theme-settings input[value=cards]').length"), 0)
                        self.assertEqual(js("document.querySelectorAll('#theme-settings input[type=radio]:checked').length"), 1)
                        self.assertNotIn("Cards", js("document.querySelector('#theme-settings').innerText"))
                        self.assertTrue(js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")
                        self.assertEqual(stored(self.db), value, "viewing does not rewrite the stored value")


if __name__ == "__main__":
    unittest.main()
