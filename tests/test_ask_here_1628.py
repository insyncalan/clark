"""Row 1628: "Turn on asking" in a project answered not_ready ("This computer's saved data can't keep that setting yet. Nothing was changed.").

Run: python3 dev/run_tests.py test_ask_here_1628
The cause, read in the code and its history (the owner's own file was not read): schema step 33 first shipped with ask_files and ask_files_off alone;
a day later row 1294 put app_settings.ask_new_projects and projects.ask_off into the same step with no new version. A file that reached version 33
or later in that day never got the two columns, so app_settings.py's check "ask_new_projects in app_settings' columns" was false. Step 39 runs
step 33 again, adding only what is missing. These tests make such a file (version 38, both columns gone) and turn asking on through the real
server and, in Classic, the real page at 1400 and 900. Cards draws no per-project row (tests/test_ask_new_projects_ui.py pins that), so there the
answer is read from the server only. Fictional data only. Chrome is required for the page test.
"""
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from _editor_checks import for_project
from test_ask_route import Running as Route
from test_ask_settings import make_db, service
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import page, store as st

WIDTHS = (1400, 900)
NOT_READY = "This computer's saved data can't keep that setting yet."


def file_like_the_one_that_failed(folder):
    """A clark.db with project ABC at version 38 whose app_settings has no ask_new_projects and whose projects has no ask_off: what a file that
    reached step 33 before the two columns joined it looks like once the later steps ran."""
    db = make_db(folder)
    con = sqlite3.connect(db)
    try:
        con.execute("ALTER TABLE app_settings DROP COLUMN ask_new_projects")
        con.execute("ALTER TABLE projects DROP COLUMN ask_off")
        con.execute("UPDATE meta SET v = '38' WHERE k = 'schema_version'")
        con.commit()
    finally:
        con.close()
    return db


def columns(db):
    con = sqlite3.connect(db)
    try:
        return ({r[1] for r in con.execute("PRAGMA table_info(app_settings)")}, {r[1] for r in con.execute("PRAGMA table_info(projects)")},
                con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0])
    finally:
        con.close()


class AskHere1628(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)

    def test_the_step_is_39_and_runs_step_33_again(self):
        self.assertEqual((st.ASK_COLUMNS_AGAIN_STEP, st.SCHEMA_VERSION), (39, 39))
        self.assertIn((39, st.migrate_ask_columns_again), st.MIGRATIONS)

    def test_a_file_like_the_one_that_failed_turns_asking_on(self):
        db = file_like_the_one_that_failed(self.d)
        apps, projects, version = columns(db)
        self.assertNotIn("ask_new_projects", apps)
        self.assertNotIn("ask_off", projects)
        self.assertEqual(version, "38")
        svc = service(db)
        status, got = svc.change_new({"project": "ABC", "off_here": False})
        self.assertEqual((status, got.get("ok"), got.get("off_here")), (200, True, False), got)
        self.assertNotIn(NOT_READY, str(got))
        apps, projects, version = columns(db)
        self.assertIn("ask_new_projects", apps)
        self.assertIn("ask_off", projects)
        self.assertEqual(version, "39")
        store = st.open_store(db, onedrive_roots=[])
        try:
            self.assertTrue(store.settings_ready())
            self.assertEqual((store.ask_new_projects_on(), store.ask_off_here("ABC")), (True, False), "the columns' defaults: on, and the project asks")
        finally:
            store.close()

    def test_a_file_that_has_the_columns_is_not_changed_by_step_39(self):
        db = make_db(self.d)
        svc = service(db)
        self.assertEqual(svc.change_new({"project": "ABC", "off_here": True})[0], 200)
        con = sqlite3.connect(db)
        try:
            con.execute("UPDATE meta SET v = '38' WHERE k = 'schema_version'")
            con.commit()
        finally:
            con.close()
        store = st.open_store(db, onedrive_roots=[])
        try:
            self.assertTrue(store.ask_off_here("ABC"), "a value already set stays as it was")
        finally:
            store.close()
        self.assertEqual(columns(db)[2], "39")

    def test_turn_on_asking_in_a_project_answers_200_and_says_on(self):
        """The real server on a file like the one that failed: the POST answers 200, ok, off_here false and never the not_ready words."""
        db = file_like_the_one_that_failed(self.d)
        s = Route()
        self.addCleanup(s.close)
        s.httpd.app_settings = service(db)
        status, got = s.api("POST", "/api/ask-new-projects", {"project": "ABC", "off_here": False})
        self.assertEqual((status, got.get("ok"), got.get("off_here")), (200, True, False), got)
        self.assertNotIn(NOT_READY, str(got))

    def test_the_classic_page_turns_asking_on_and_says_on_at_1400_and_900(self):
        """Classic (the only theme with the project's own row): the row reads off on the old file (no ask_off reads as off), the button turns it
        on, the line says "Asking is on for ABC." and no line of the not_ready words is on the page."""
        for w in WIDTHS:
            with self.subTest(width=w):
                d = Path(tempfile.mkdtemp(prefix="clark-test-", dir=self.d))
                db = file_like_the_one_that_failed(d)
                s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.page_html(tempfile.mkdtemp(), theme="prototype-2.0"))
                self.addCleanup(s.close)
                s.httpd.app_settings = service(db)
                with chrome() as cdp:
                    sid = navigate(cdp, s.port, for_project("#settings&p=ABC&s=claude"))
                    js = lambda e: cdp.js(e, sid)          # noqa: E731
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                    self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-here]')"), 20), "the project's button")
                    if js("document.querySelector('#ask-here-state').textContent") == "Asking is off for ABC.":
                        js("document.querySelector('[data-ask-here]').click()")
                    self.assertTrue(wait(lambda: js("document.querySelector('#ask-here-state').textContent === 'Asking is on for ABC.'"), 20),
                                    f"on for the project; the line: {js('(document.querySelector(\"#ask-here-state\") || {}).textContent')!r}")
                    self.assertTrue(wait(lambda: not js("document.body.innerText.includes(" + repr(NOT_READY) + ")"), 5), "no not_ready line")
                    self.assertEqual(js("document.body.innerText.split(" + repr(NOT_READY) + ").length - 1"), 0)
                self.assertFalse(service(db).read_new("ABC")[1]["off_here"])

    def test_asking_turned_on_is_still_on_after_a_restart(self):
        db = file_like_the_one_that_failed(self.d)
        s = Route()
        s.httpd.app_settings = service(db)
        self.assertEqual(s.api("POST", "/api/ask-new-projects", {"project": "ABC", "off_here": True})[0], 200)
        self.assertEqual(s.api("POST", "/api/ask-new-projects", {"project": "ABC", "off_here": False})[0], 200)
        s.close()
        again = Route()
        self.addCleanup(again.close)
        again.httpd.app_settings = service(db)
        status, got = again.api("GET", "/api/ask-new-projects?project=ABC")
        self.assertEqual((status, got.get("off_here"), got.get("saved")), (200, False, True), got)


if __name__ == "__main__":
    unittest.main()
