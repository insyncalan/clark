"""Row 1299 AP2: every address Settings had before the restructure still opens its page, on the REAL Settings page (the built page from the real
server, demo database, fictional data) in the Classic theme at 1400 and 900 px. The 13 old slugs are the router's SETTINGS_PAGES: folder,
appearance, theme, projects, claude, version, logs, data, backups, reports, people, profile, brand. Eleven are still a page of their own; Folder
is now part of Brand and publishing and Theme is part of Look, so s=folder and s=theme open those pages, with the card the old page held on them.

Run: python3 dev/run_tests.py test_settings_slugs_1299
Fails, never skips, without Chrome."""
import re
import shutil
import tempfile
import unittest

from _editor_checks import for_url
from _paths import SRC

from clark import page
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

NAME = "prototype-2.0"
# old slug: (the page it opens, that page's name in the menu, the heading of the card the old page was for)
OLD = {
    "folder": ("brand", "Brand and publishing", "client-folder-h"),
    "appearance": ("appearance", "Look", "personal-h"),
    "theme": ("appearance", "Look", "theme-settings-h"),
    "projects": ("projects", "Projects overview", "projects-h"),
    "claude": ("claude", "ask clark", "ask-settings-h"),
    "version": ("version", "Version and updates", "update-h"),
    "logs": ("logs", "Logs and diagnostics", "diagnostics-h"),
    "data": ("data", "Data", "data-card-h"),
    "backups": ("backups", "Backups", "safety-h"),
    "reports": ("reports", "Reports and pages", "review-days-h"),
    "people": ("people", "People", "people-h"),
    "profile": ("profile", "Profile", "essentials-h"),
    "brand": ("brand", "Brand and publishing", "brands-h"),
}
LOOK = """((head) => ({ page: (document.querySelector('.set-cards') || {dataset: {}}).dataset.page || '',
  open: [...document.querySelectorAll('.set-chip[aria-current]')].map((c) => c.textContent.trim()),
  head: !!document.querySelector('.set-cards #' + head) }))"""


class OldSlugs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()
        cls.names = {p["code"]: p["name"] for p in cls.store.read("projects")}
        cls.data = {c: cls.store.data_for(c) for c in cls.names}

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def serve(self):
        s = Running(data_for=lambda code, **kw: self.data.get(code), projects=lambda archived=False: [{"code": c, "name": n} for c, n in sorted(self.names.items())],
                    page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=NAME))
        self.addCleanup(s.close)
        return s

    def look(self, cdp, port, width, slug):
        want = OLD[slug]
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{port}/#settings&p=TUL&s={slug}")}, sid)
        got = {}

        def there():
            got.update(cdp.js(f"{LOOK}('{want[2]}')", sid) or {})
            return got.get("page") == want[0] and got.get("head")
        wait(there, 30)      # the asserts below say what was missing
        return got

    def test_the_13_old_slugs_are_the_routers_pages(self):
        router = (SRC / "clark" / "page" / "src" / "router.js").read_text(encoding="utf-8")
        listed = re.search(r"export const SETTINGS_PAGES = \[([^\]]*)\];", router)
        self.assertTrue(listed, "router.js SETTINGS_PAGES not found")
        self.assertEqual(sorted(re.findall(r'"([a-z]+)"', listed.group(1))), sorted(OLD), "the router no longer reads one of the 13 old slugs (or reads a new one this test does not open)")
        self.assertEqual(len(OLD), 13)

    def test_old_slugs_open_their_page(self):
        s = self.serve()
        for width in (1400, 900):
            for slug, (opens, name, head) in OLD.items():
                with chrome() as cdp:
                    got = self.look(cdp, s.port, width, slug)
                tag = f"{width} s={slug}"
                self.assertEqual(got.get("page"), opens, f"{tag}: the page that opened")
                self.assertEqual(got.get("open"), [name], f"{tag}: the one menu entry marked as open")
                self.assertTrue(got.get("head"), f"{tag}: the card #{head} is on the page")


if __name__ == "__main__":
    unittest.main()
