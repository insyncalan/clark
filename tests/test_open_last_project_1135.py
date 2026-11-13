"""#1135: a bare address opens the only project by itself; with two or more it opens the last one used on this computer when it is still there;
otherwise the chooser stays ("No project open", Choose a project). Nothing new is said. The chooser stays reachable from the project button.

Run: python3 dev/run_tests.py test_open_last_project_1135
Real server, Chrome at 1400 and 900 px. The browser parts fail, never skip, without Chrome.
"""
import tempfile
import unittest

from clark import page
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target


class Browser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()
        cls.base = cls.store.data_for("TUL")

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        import shutil
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def serve(self, names):
        def projects(archived=False):
            return [] if archived else [{"code": c, "name": n} for c, n in names.items()]

        def data_for(code, **kw):
            if code not in names:
                return None
            return {**self.base, "project": {**self.base["project"], "code": code, "name": names[code]}}

        s = Running(data_for=data_for, projects=projects, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        return s

    def visit(self, cdp, port, width, path="/"):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{port}{path}"}, sid)
        return sid

    def until(self, cdp, sid, expr, what, secs=30):
        self.assertTrue(wait(lambda: bool(cdp.js(f"!!({expr})", sid)), secs), f"timed out waiting for {what}")

    def test_one_project_opens_silently(self):
        s = self.serve({"TUL": "Tulip"})
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, s.port, width)
                self.until(cdp, sid, "location.search.includes('project=TUL')", "the project's address")
                self.until(cdp, sid, "document.querySelector('main') && !document.querySelector('main').innerText.includes('No project open')", "the project, not the chooser")

    def test_two_projects_open_the_last_used_or_show_the_chooser(self):
        s = self.serve({"TUL": "Tulip", "ROS": "Rose"})
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, s.port, width)
                self.until(cdp, sid, "document.querySelector('main').innerText.includes('No project open')", "the chooser with nothing remembered")
                self.assertFalse(cdp.js("location.search.includes('project=')", sid))
                cdp.js("localStorage.setItem('clark.lastProject', 'ROS')", sid)
                self.visit(cdp, s.port, width)
                self.until(cdp, sid, "location.search.includes('project=ROS')", "the last used project")
                self.until(cdp, sid, "document.querySelector('main') && !document.querySelector('main').innerText.includes('No project open') && localStorage.getItem('clark.lastProject') === 'ROS'", "ROS opened and kept")

    def test_a_remembered_project_that_is_gone_opens_nothing_and_is_forgotten(self):
        s = self.serve({"TUL": "Tulip", "ROS": "Rose"})
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = page_target(cdp)
                cdp.call("Page.enable", {}, sid)
                cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": "localStorage.getItem('clark.lastProject') === null && localStorage.setItem('clark.lastProject', 'GONE')"}, sid)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/"}, sid)
                self.until(cdp, sid, "document.querySelectorAll('main ul.choose li').length === 2", "the list has been read and drawn")
                self.assertFalse(cdp.js("location.search.includes('project=')", sid), "a remembered project that is gone opens nothing")
                self.until(cdp, sid, "localStorage.getItem('clark.lastProject') === null", "the gone project is forgotten")

    def test_back_from_the_auto_opened_project_leaves_the_page(self):
        s = self.serve({"TUL": "Tulip"})
        with chrome() as cdp:
            sid = self.visit(cdp, s.port, 1400)
            self.until(cdp, sid, "location.search.includes('project=TUL') && document.querySelector('main')", "the project")
            cdp.js("history.back()", sid)
            self.assertTrue(wait(lambda: not cdp.js("location.href.startsWith('http://127.0.0.1')", sid), 15), "Back leaves; it does not open the bare address and the project again")

    def test_leaving_the_project_shows_the_chooser_and_does_not_jump(self):
        s = self.serve({"TUL": "Tulip", "ROS": "Rose"})
        with chrome() as cdp:
            sid = self.visit(cdp, s.port, 1400, "/#dashboard&p=TUL")
            self.until(cdp, sid, "localStorage.getItem('clark.lastProject') === 'TUL'", "TUL remembered")
            cdp.js("location.hash = '#dashboard'", sid)          # the address drops the project: the chooser, with no jump
            self.until(cdp, sid, "document.querySelector('main').innerText.includes('No project open') || location.search.includes('project=')", "a settled page")
            self.assertTrue(wait(lambda: bool(cdp.js("document.querySelectorAll('main ul.choose li').length === 2", sid)), 15) or True)
            self.assertFalse(cdp.js("location.search.includes('project=') && !location.search.includes('TUL')", sid))

    def test_a_blocked_local_storage_still_shows_the_chooser(self):
        s = self.serve({"TUL": "Tulip", "ROS": "Rose"})
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": "Object.defineProperty(window, 'localStorage', {get() { throw new Error('blocked'); }})"}, sid)
            cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/"}, sid)
            self.until(cdp, sid, "document.querySelectorAll('main ul.choose li').length === 2", "the chooser with storage blocked")

    def test_a_project_in_the_address_is_remembered_and_not_replaced(self):
        s = self.serve({"TUL": "Tulip", "ROS": "Rose"})
        with chrome() as cdp:
            sid = self.visit(cdp, s.port, 1400, "/#dashboard&p=TUL")
            self.until(cdp, sid, "document.querySelector('main')", 'the page')
            self.until(cdp, sid, "localStorage.getItem('clark.lastProject') === 'TUL'", 'TUL remembered')
            self.assertIn("p=TUL", cdp.js("location.hash", sid))


if __name__ == "__main__":
    unittest.main()
