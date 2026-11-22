"""Row 1503: the page a Settings test of the new-projects screen stands on: two projects (ABC and XYZ), the Settings service, the page served with Classic's look.

Shared by tests/test_ask_new_projects_kill_1503.py and the test_ask_np_kill_1503_* files."""
import copy
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from test_ask_settings import make_db, service
from test_page import DATA, navigate  # noqa: F401  (navigate is used by the tests that import this module)
from test_server import Running, wait

from clark import page
from clark import store as st


class SettingsBase(unittest.TestCase):
    def setUp(self):
        first, other = copy.deepcopy(DATA["ABC"]), copy.deepcopy(DATA["ABC"])
        other["project"]["code"], other["project"]["name"] = "XYZ", "Other Programme"
        data = {"ABC": first, "XYZ": other}
        listed = [{"code": "ABC", "name": "Example Programme", "open": 1}, {"code": "XYZ", "name": "Other Programme", "open": 1}]
        self.s = Running(data_for=lambda code, archived=None: data.get(code), projects=lambda archived=False: listed, page_html=lambda: page.page_html(tempfile.mkdtemp(), theme="prototype-2.0"))
        self.addCleanup(self.s.close)
        d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, d, True)
        db = make_db(d)
        store = st.open_store(db, onedrive_roots=[])
        with store.step("dashboard", "tester", place="menu") as step:
            step.create("projects", {"code": "XYZ", "name": "Other Programme"})
        store.close()
        self.svc = self.s.httpd.app_settings = service(db)

    def until(self, js, expr, what):
        self.assertTrue(wait(lambda: js(expr), 20), f"{what}: {expr}")

    def move_to(self, js, code):
        """Choose another project in the header's menu, with the page for it not to be had (as when the server cannot answer GET /?project=): the page then moves in place,
        which is the one way a document goes from one project to another."""
        js("(() => { const f = window.fetch; window.fetch = (u, i) => String(u).startsWith('/?project=') ? Promise.resolve({ ok: false, status: 503 }) : f(u, i); })()")
        js("document.querySelector('#project-name').click()")
        self.until(js, "[...document.querySelectorAll('#project-menu [role=menuitemradio]')].some((e) => e.textContent.indexOf('Other Programme') >= 0)", "the menu lists XYZ")
        js("[...document.querySelectorAll('#project-menu [role=menuitemradio]')].find((e) => e.textContent.indexOf('Other Programme') >= 0).click()")
        self.until(js, "location.hash.indexOf('p=XYZ') >= 0", "the address names XYZ")

    def back_to_asking(self, js):
        """A move to another project lands on the Projects page of Settings (the move carries no Settings page): open Claude and AI and the project's tab again."""
        self.until(js, "[...document.querySelectorAll('.set-chip')].some((e) => e.textContent === 'Claude and AI')", "the Settings pages")
        js("[...document.querySelectorAll('.set-chip')].find((e) => e.textContent === 'Claude and AI').click()")
        self.until(js, "!!document.querySelector('[data-ask-tab]:not([data-ask-tab=all])')", "the project's tab")
        js("document.querySelector('[data-ask-tab]:not([data-ask-tab=all])').click()")

    def show(self, cdp, hash_="#settings&p=ABC&s=claude"):
        self.sid = navigate(cdp, self.s.port, hash_)          # no ?project=: the page is served on Generic, so a move to another project stays in this document
        js = lambda e: cdp.js(e, self.sid)          # noqa: E731
        self.until(js, "!!document.querySelector('[data-ask-tab]')", "the tabs")
        return js
