"""Row 1299 AP2: on the Classic theme the 13 slugs of the old menu (s=...) still open the right page: its card is drawn and the menu marks the page that holds it.
Complements test_settings_groups_1299a (folder and theme only). Run: python3 dev/run_tests.py test_settings_slugs_1299. Chrome is required: fails, never skips, without it."""
import shutil
import tempfile
import unittest

from _editor_checks import for_url

from clark import page
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

NAME = "prototype-2.0"
# slug -> (the card heading that must draw, the menu item that is marked)
SLUGS = {"folder": ("client-folder-h", "Brand and publishing"), "appearance": ("personal-h", "Look"), "theme": ("theme-settings-h", "Look"),
         "projects": ("projects-h", "Projects overview"), "claude": ("ask-settings-h", "ask clark"), "version": ("update-h", "Version and updates"),
         "logs": ("diagnostics-h", "Logs and diagnostics"), "data": ("data-card-h", "Data"), "backups": ("safety-h", "Backups"),
         "reports": ("review-days-h", "Reports and pages"), "people": ("people-h", "People"), "profile": ("profile-h", "Profile"), "brand": ("brands-h", "Brand and publishing")}


class Slugs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()
        cls.names = {p["code"]: p["name"] for p in cls.store.read("projects")}
        cls.data = {c: cls.store.data_for(c) for c in cls.names}

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def test_every_old_slug_opens_its_page(self):
        s = Running(data_for=lambda code, **kw: self.data.get(code), projects=lambda archived=False: [{"code": c, "name": n} for c, n in sorted(self.names.items())],
                    page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=NAME))
        self.addCleanup(s.close)
        for slug, (head, item) in SLUGS.items():
            with self.subTest(slug=slug), chrome() as cdp:
                sid = page_target(cdp)
                cdp.call("Page.enable", {}, sid)
                cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                cdp.call("Page.navigate", {"url": "about:blank"}, sid)
                cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{s.port}/#settings&p=TUL&s={slug}")}, sid)
                self.assertTrue(wait(lambda: bool(cdp.js(f"!!document.getElementById('{head}')", sid)), 30), f"{slug}: card {head} not drawn")
                self.assertEqual(cdp.js("(document.querySelector('.set-chip[aria-current]') || {textContent: ''}).textContent.trim()", sid), item, slug)


if __name__ == "__main__":
    unittest.main()
