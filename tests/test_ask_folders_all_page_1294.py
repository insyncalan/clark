"""Row 1294, slice 4: the folders for all projects on the ask clark page, in a real browser at 1400 and 900, against the real folder service.

Run: python3 dev/run_tests.py test_ask_folders_all_page_1294
The All projects tab has "Source folders for all projects" (Remove, Choose folder, a typed location when no window can open); the project's tab lists
them tagged "All projects" with a Change button that opens the All projects tab, then the project's own, and "N of 20". Chrome is required."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _editor_checks import for_project
from test_ask_settings import make_db, service
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import ask_folders, page, platform as pl

WIDTHS = (1400, 900)


class Page(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(pl, "system", return_value=pl.MAC)
        patch.start()
        self.addCleanup(patch.stop)
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(self.s.close)
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.home = self.d / "home"
        self.data = self.d / "data"
        self.shared, self.own = self.home / "shared", self.home / "own"
        for p in (self.shared, self.own, self.data):
            p.mkdir(parents=True)
        db = make_db(self.data)
        self.s.httpd.app_settings = service(db)
        self.picked = [self.shared]
        self.s.httpd.ask_folders = self.svc = ask_folders.AskFolders(db, [], data_dir=self.data, home=self.home, by_user=lambda: "tester",
                                                                     choose_folder=lambda prompt, start=None: self.picked.pop(0) if self.picked else None)

    def show(self, cdp, tab):
        self.sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
        js = lambda e: cdp.js(e, self.sid)          # noqa: E731
        self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-tab]')"), 20))
        if tab == "all":
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-all-folders')"), 10))
        return js

    def until(self, js, expr, what):
        self.assertTrue(wait(lambda: js(expr), 15), f"{what}: {expr}")

    def test_choose_on_the_all_projects_tab_lists_it_and_the_project_tab_tags_it_with_a_change_button_then_its_own_and_the_count(self):
        with chrome() as cdp:
            js = self.show(cdp, "all")
            self.assertEqual(js("document.querySelector('#ask-all-folders h2').textContent"), "Source folders for all projects")
            self.until(js, "!!document.querySelector('#ask-all-folders-none')", "read")
            self.assertEqual(js("document.querySelector('#ask-all-folders-none').textContent"), "No folders are set for all projects.")
            order = js("[...document.querySelectorAll('.frame.setting')].map(e => e.id)")
            self.assertEqual(order[-1], "ask-all-folders", order)
            self.assertLess(order.index("ai-settings"), order.index("ask-all-folders"))
            js("document.querySelector('[data-ask-all-choose]').click()")
            self.until(js, "(document.querySelector('#ask-all-folder-list') || {innerText: ''}).innerText.startsWith(%r)" % str(self.shared), "listed")
            self.assertEqual(js("!!document.querySelector('#ask-all-folders-none')"), False)
            self.assertEqual(ask_folders.shared_folders(self.data), [str(self.shared)])
            self.assertEqual(js("document.querySelector('[data-ask-all-remove]').innerText"), "Remove")
            self.assertEqual(js("document.querySelector('[data-ask-all-choose]').innerText"), "Choose folder")
            js("document.querySelector('[data-ask-tab=project]').click()")
            self.until(js, "!!document.querySelector('#ask-folders-shared')", "the project tab lists it")
            self.assertEqual(js("document.querySelector('#ask-folders-shared li').innerText.replace(/\\s+/g, ' ')"), f"{self.shared} All projects Change")
            self.assertFalse(js("!!document.querySelector('#ask-folders-shared [data-ask-remove]')"), "a shared folder has no Remove on a project's tab")
            self.assertEqual(js("document.querySelector('#ask-folders-count').innerText"), "1 of 20")
            self.picked.append(self.own)
            js("document.querySelector('[data-ask-choose]').click()")
            self.until(js, "(document.querySelector('#ask-folders') || {innerText: ''}).innerText.startsWith(%r)" % str(self.own), "own listed")
            self.assertEqual(js("document.querySelector('#ask-folders-count').innerText"), "2 of 20")
            self.assertLess(js("document.querySelector('#ask-folders-shared').getBoundingClientRect().top"), js("document.querySelector('#ask-folders').getBoundingClientRect().top"))
            js("document.querySelector('[data-ask-change-shared]').click()")
            self.until(js, "!!document.querySelector('#ask-all-folders')", "Change opens the All projects tab")
            self.assertEqual(js("document.querySelector('[data-ask-tab=all]').getAttribute('aria-current')"), "true")

    def test_remove_on_the_all_projects_tab_leaves_the_folder_on_disk_and_a_projects_own_alone(self):
        self.svc.change({"project": "ABC", "action": "add", "path": str(self.own)})
        ask_folders.AskFolders.change_all(self.svc, {"scope": "all", "action": "add", "path": str(self.shared)})
        (self.shared / "keep.txt").write_text("x", encoding="utf-8")
        with chrome() as cdp:
            js = self.show(cdp, "all")
            self.until(js, "!!document.querySelector('[data-ask-all-remove]')", "listed")
            js("document.querySelector('[data-ask-all-remove]').click()")
            self.until(js, "!!document.querySelector('#ask-all-folders-none')", "removed")
            self.assertTrue((self.shared / "keep.txt").exists())
            self.assertEqual(ask_folders.shared_folders(self.data), [])
            self.assertEqual(self.svc.read("ABC")[1]["folders"], [str(self.own)])
            self.until(js, "document.activeElement === document.querySelector('[data-ask-all-choose]')", "focus goes to Choose folder")

    def test_a_too_wide_folder_is_refused_in_plain_words_and_nothing_is_listed_and_no_window_gives_a_typed_location(self):
        with chrome() as cdp:
            js = self.show(cdp, "all")
            self.until(js, "!!document.querySelector('[data-ask-all-choose]')", "read")
            self.picked[:] = [self.home]
            js("document.querySelector('[data-ask-all-choose]').click()")
            self.until(js, "(document.querySelector('#ask-all-folders .pub-msg') || {innerText: ''}).innerText.includes('too wide')", "refused")
            self.assertTrue(js("document.querySelector('#ask-all-folders .pub-msg').innerText.endsWith('Nothing was changed.')"))
            self.assertEqual(js("document.querySelector('#ask-all-folders .pub-msg').getAttribute('role')"), "alert")
            self.assertFalse(js("!!document.querySelector('#ask-all-folder-list')"))
            with mock.patch.object(pl, "container_mode", return_value=False):
                self.svc.choose_folder = mock.Mock(side_effect=pl.NotBuiltYet("x"))
                js("document.querySelector('[data-ask-all-choose]').click()")
                self.until(js, "!!document.querySelector('#ask-all-folder-path')", "typed location offered")
            self.assertTrue(js("document.querySelector('[data-ask-all-add]').disabled"))
            js("(() => { const i = document.querySelector('#ask-all-folder-path'); i.value = %r; i.dispatchEvent(new Event('input', {bubbles: true})); })()" % str(self.own))
            self.until(js, "!document.querySelector('[data-ask-all-add]').disabled", "Add enabled")
            js("document.querySelector('[data-ask-all-add]').click()")
            self.until(js, "(document.querySelector('#ask-all-folder-list') || {innerText: ''}).innerText.startsWith(%r)" % str(self.own), "typed one listed")
            self.assertEqual(js("document.querySelector('#ask-all-folder-path').value"), "")

    def test_both_tabs_fit_at_1400_and_900_and_the_projects_tab_without_shared_folders_shows_no_tag_or_count(self):
        with chrome() as cdp:
            js = self.show(cdp, "project")
            self.until(js, "!!document.querySelector('[data-ask-choose]')", "folders read")
            self.assertFalse(js("!!document.querySelector('#ask-folders-shared') || !!document.querySelector('#ask-folders-count')"))
        ask_folders.AskFolders.change_all(self.svc, {"scope": "all", "action": "add", "path": str(self.shared)})
        with chrome() as cdp:
            js = self.show(cdp, "project")
            self.until(js, "!!document.querySelector('#ask-folders-shared')", "shared shown")
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.until(js, "document.documentElement.scrollWidth <= window.innerWidth", f"no sideways scroll on the project tab at {w}")
                js("document.querySelector('[data-ask-tab=all]').click()")
                self.until(js, "!!document.querySelector('#ask-all-folders')", "all tab")
                self.until(js, "document.documentElement.scrollWidth <= window.innerWidth", f"no sideways scroll on the All tab at {w}")
                self.until(js, "!!document.querySelector('[data-ask-all-remove]')", "the shared folder is listed")
                self.assertTrue(js("['#ask-all-folders', '[data-ask-all-choose]', '[data-ask-all-remove]'].every(q => document.querySelector(q).offsetHeight > 0)"))
                js("document.querySelector('[data-ask-tab=project]').click()")


if __name__ == "__main__":
    unittest.main()
