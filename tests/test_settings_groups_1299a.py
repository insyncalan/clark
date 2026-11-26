"""Row 1299 (Settings, slice 1a and the "Affects:" line), on the REAL Settings page (the committed page from the real server, demo database, fictional data) at
1400 and 900 px: the menu is four groups in the mock-up's order (You, All projects, Project settings, Help and about) with each page in its group, and the
Classic theme draws "Affects: <who>" at the head of a page (the project's code on a Project settings page, All projects on an All projects page, You on a
You page, nothing on Help and about). Cards draws no such line. Old page addresses (s=folder, s=theme) still open their page.

Run: python3 dev/run_tests.py test_settings_groups_1299a
Fails, never skips, without Chrome."""
import shutil
import tempfile
import unittest

from _editor_checks import for_url

from clark import page
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

NAME = "prototype-2.0"
GROUPS = [("You", ["Profile", "Look"]), ("All projects", ["Projects overview", "Backups"]),
          ("Project settings", ["Reports and pages", "Brand and publishing", "People", "ask clark", "Data"]), ("Help and about", ["Version and updates", "Logs and diagnostics"])]
CARDS_GROUPS = [("Everyday", ["Projects", "People", "Profile"]), ("Publishing", ["Folder", "Brand", "Theme"]), ("Look and feel", ["Appearance", "Reports"]),
                ("Data and safety", ["Backups", "Data"]), ("Advanced", ["Claude and AI", "Logs and diagnostics", "Version and updates"])]
AFFECTS = {"profile": "Affects: You", "appearance": "Affects: You", "projects": "Affects: All projects", "backups": "Affects: All projects",
           "reports": "Affects: TUL", "brand": "Affects: TUL", "people": "Affects: TUL", "claude": "Affects: TUL", "data": "Affects: TUL", "version": None, "logs": None}
MENU = """(() => ({ groups: [...document.querySelectorAll('.set-nav .set-group')].map((g) => [g.querySelector('.set-group-name').textContent.trim(), [...g.querySelectorAll('.set-chip')].map((c) => c.textContent.trim())]),
  open: (document.querySelector('.set-chip[aria-current]') || {textContent: ''}).textContent.trim(),
  affects: [...document.querySelectorAll('.set-affects')].map((e) => e.textContent.trim()),
  first: (document.querySelector('.set-cards') || {firstElementChild: null}).firstElementChild ? document.querySelector('.set-cards').firstElementChild.className : '' }))()"""


class RealGroups(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()
        cls.names = {p["code"]: p["name"] for p in cls.store.read("projects")}
        cls.data = {c: cls.store.data_for(c) for c in cls.names}

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def serve(self, theme):
        s = Running(data_for=lambda code, **kw: self.data.get(code), projects=lambda archived=False: [{"code": c, "name": n} for c, n in sorted(self.names.items())],
                    page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=theme))
        self.addCleanup(s.close)
        return s

    def look(self, cdp, port, width, slug):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{port}/#settings&p=TUL&s={slug}")}, sid)
        self.assertTrue(wait(lambda: bool(cdp.js("!!document.querySelector('.set-chip[aria-current]') && !!document.querySelector('.set-cards > section, .set-cards > .setting')", sid)), 30), "timed out waiting for Settings")
        return cdp.js(MENU, sid)

    def each(self, theme, slugs):
        s = self.serve(theme)
        for width in (1400, 900):
            for slug in slugs:
                with chrome() as cdp:
                    yield f"{theme or 'cards'} {width} {slug}", slug, self.look(cdp, s.port, width, slug)

    def test_classic_menu_is_four_groups_in_the_mockups_order(self):
        for tag, slug, got in self.each(NAME, ["profile", "backups"]):
            self.assertEqual(got["groups"], [[g, p] for g, p in GROUPS], tag)

    def test_cards_menu_is_left_as_it_was(self):
        for tag, slug, got in self.each(None, ["profile", "backups"]):
            self.assertEqual(got["groups"], [[g, p] for g, p in CARDS_GROUPS], tag)

    def test_old_addresses_still_open_their_page(self):
        for tag, slug, got in self.each(NAME, ["folder", "theme"]):
            self.assertEqual(got["open"], {"folder": "Brand and publishing", "theme": "Look"}[slug], tag)
        for tag, slug, got in self.each(None, ["folder", "theme"]):
            self.assertEqual(got["open"], {"folder": "Folder", "theme": "Theme"}[slug], tag)

    def test_classic_says_who_a_page_affects(self):
        for tag, slug, got in self.each(NAME, list(AFFECTS)):
            want = AFFECTS[slug]
            self.assertEqual(got["affects"], [want] if want else [], tag)
            if want:
                self.assertIn("set-affects", got["first"], tag + ": the line is the first thing on the page")

    def test_cards_draws_no_affects_line(self):
        for tag, slug, got in self.each(None, ["profile", "reports", "projects"]):
            self.assertEqual(got["affects"], [], tag)


if __name__ == "__main__":
    unittest.main()
