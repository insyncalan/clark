"""#731: the demo data banner on the Edit page, its confirm box, and the empty screen after Remove; never in a published report.

Run: python3 dev/run_tests.py test_demo_banner
The browser parts fail, never skip, without Chrome.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from _paths import SRC  # noqa: F401
from clark import __main__ as launcher, demo_seed, page, store as clark_store
from test_page import navigate
from test_server import Running, chrome, wait

CONFIRM = "Remove the demo projects? Your own projects are not touched. A safety copy is made first."


class DemoLine(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        store = demo_seed.load_if_fresh(clark_store.open_store(self.folder / "clark.db", onedrive_roots=[]), [])
        store.close()
        self.s = Running(data_for=lambda code: None, page_html=lambda: page.page_html(tempfile.mkdtemp()),
                         projects=launcher.projects_of(self.folder / "clark.db", []))
        self.s.httpd.demo = demo_seed.Demo(self.folder / "clark.db", [])
        self.addCleanup(self.s.close)

    def js(self, cdp, sid, code):
        return cdp.js(code, sid)

    def until(self, cdp, sid, code, what):
        self.assertTrue(wait(lambda: cdp.js(code, sid), 30), what)

    def test_the_banner_asks_first_and_then_the_page_lands_on_the_empty_screen_with_one_new_project_button(self):
        with chrome() as cdp:
            sid = navigate(cdp, self.s.port, "#dashboard")
            self.until(cdp, sid, "!!document.querySelector('#demo-banner')", "the banner")
            self.assertEqual(cdp.js("document.querySelector('#demo-banner').innerText.replace(/\\s+/g, ' ').trim()", sid), "This is demo data. Remove demo data")
            cdp.js("document.querySelector('#demo-remove').click()", sid)
            self.until(cdp, sid, "!!document.querySelector('#demo-confirm')", "the box")
            self.assertEqual(cdp.js("document.querySelector('#demo-confirm h2').innerText", sid), "Remove demo data?")
            self.assertEqual(cdp.js("document.querySelector('#demo-confirm p').innerText", sid), CONFIRM)
            cdp.js("document.querySelector('#demo-cancel').click()", sid)
            self.until(cdp, sid, "!document.querySelector('#demo-confirm')", "the box closed")
            self.assertEqual(len(clark_store.open_store(self.folder / "clark.db", onedrive_roots=[]).read("projects")), 2)   # Cancel removed nothing
            cdp.js("document.querySelector('#demo-remove').click()", sid)
            self.until(cdp, sid, "!!document.querySelector('#demo-go')", "the box again")
            cdp.js("document.querySelector('#demo-go').click()", sid)
            self.until(cdp, sid, "!document.querySelector('#demo-banner') && document.querySelector('main').innerText.includes('There are no projects yet.')", "the empty screen")
            self.assertIn("No project open", cdp.js("document.querySelector('main').innerText", sid))
            self.assertEqual(cdp.js("Array.from(document.querySelectorAll('main button')).map(b => b.innerText.trim()).join('|')", sid), "New project")
            cdp.js("document.querySelector('#np-empty').click()", sid)
            self.until(cdp, sid, "!!document.querySelector('#project-form')", "the project form")

    def test_the_profile_circle_is_on_the_empty_screen_with_only_the_entries_that_need_no_project(self):
        """Row 786: no project open still has the circle; Publish, Preview and Export wait for a project."""
        with chrome() as cdp:
            sid = navigate(cdp, self.s.port, "#dashboard")
            self.until(cdp, sid, "!!document.querySelector('#demo-remove')", "the banner")
            cdp.js("document.querySelector('#demo-remove').click()", sid)
            self.until(cdp, sid, "!!document.querySelector('#demo-go')", "the box")
            cdp.js("document.querySelector('#demo-go').click()", sid)
            self.until(cdp, sid, "document.querySelector('main').innerText.includes('There are no projects yet.')", "the empty screen")
            self.until(cdp, sid, "!!document.querySelector('#profile-btn')", "the profile circle")
            cdp.js("document.querySelector('#profile-btn').click()", sid)
            self.until(cdp, sid, "!!document.querySelector('#profile-menu')", "the menu")
            shown = cdp.js("[].map.call(document.querySelectorAll('#profile-menu [role^=menuitem]'), function(e){return e.textContent.replace(/\\s+/g, ' ').trim()}).join('|')", sid)
            self.assertRegex(shown, r"Settings")
            self.assertRegex(shown, r"Help")
            self.assertNotRegex(shown, r"Publish|Preview|Export")

    def test_removing_the_demo_while_one_of_its_projects_is_open_lands_on_the_empty_screen_through_the_router(self):
        with chrome() as cdp:
            sid = navigate(cdp, self.s.port, "#work&p=TUL")
            self.until(cdp, sid, "!!document.querySelector('#demo-banner')", "the banner")
            cdp.js("document.querySelector('#demo-remove').click()", sid)
            self.until(cdp, sid, "!!document.querySelector('#demo-go')", "the box")
            cdp.js("document.querySelector('#demo-go').click()", sid)
            self.until(cdp, sid, "!document.querySelector('#demo-banner') && document.querySelector('main').innerText.includes('There are no projects yet.')", "the empty screen")
            self.assertNotIn("p=TUL", cdp.js("location.hash", sid))

    def test_a_stale_banner_after_edits_made_elsewhere_says_there_is_nothing_to_remove_and_goes(self):
        with chrome() as cdp:
            sid = navigate(cdp, self.s.port, "#dashboard")
            self.until(cdp, sid, "!!document.querySelector('#demo-banner')", "the banner")
            other = clark_store.open_store(self.folder / "clark.db", onedrive_roots=[])      # the person's edits reach both demo projects behind the page's back
            for code in ("TUL", "MOSS"):
                with other.step("dashboard", "someone@example.test") as st:
                    st.create("actions", {"project": code, "description": "Added by the person", "raised": "2026-10-01", "source": "test"})
            other.close()
            cdp.js("document.querySelector('#demo-remove').click()", sid)
            self.until(cdp, sid, "!!document.querySelector('#demo-go')", "the box")
            cdp.js("document.querySelector('#demo-go').click()", sid)
            self.until(cdp, sid, "!document.querySelector('#demo-banner') && document.querySelector('#demo-none') && document.querySelector('#demo-none').innerText === 'There is no demo data to remove.'", "the sentence in the box and no banner")
            cdp.js("document.querySelector('#demo-cancel').click()", sid)
            self.until(cdp, sid, "!document.querySelector('#demo-confirm')", "the box closed")
            self.assertEqual(len(clark_store.open_store(self.folder / "clark.db", onedrive_roots=[]).read("projects")), 2)      # nothing was removed

    def test_the_banner_is_hidden_in_print_and_a_published_report_has_no_part_of_it(self):
        css = (Path(page.PAGE).parent / "shell.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"@media print \{ \.demo-banner \{ display: none; \} \}")
        view = (Path(page.PAGE).parent / "page-view.html").read_text(encoding="utf-8")
        for word in ("Remove demo data", "This is demo data.", "/api/demo"):
            self.assertNotIn(word, view)


if __name__ == "__main__":
    unittest.main()
