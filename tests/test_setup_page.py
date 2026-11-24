"""#836 step 5: the real setup page (src/clark/setup_page.py) and the page versions of the doctor's words. Run: python3 dev/run_tests.py test_setup_page
No browser here (tests/test_setup_page_browser.py has it). Temporary folders only; the folder window is always a fake function."""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT, SRC
from test_server_setup import SetupRunning

from clark import doctor, launch, platform as pl, server as sv, setup_mode, setup_page

# Every string the page itself draws, written out (the FINAL STRINGS table of the pull request). A change here is a change of words.
WORDS = {
    "heading": "Setting up clark",
    "notice": "clark is being set up. Nothing is saved until the checks below pass.",
    "check_again": "Check again",
    "choose": "Choose a folder",
    "waiting": "Waiting for you to choose a folder.",
    "busy": "A folder window is already open.",
    "ready": "Ready",
    "fix": "To fix",
    "advice": "Worth knowing",
    "not checked": "Not checked",
    "one_fix": "1 thing to fix before clark can start. Fix it, then choose Check again.",
    "many_fix": "{n} things to fix before clark can start. Fix each one, then choose Check again.",
    "unknown": "Some checks can't run on this computer yet, so we can't say whether clark will start. Try starting it; if it won't, tell the "
               "clark team.",
    "all_ready": "Everything clark needs is ready.",
    "opening": "Everything clark needs is ready. Opening clark.",
}
FOLDER_PROMPT = "Choose a folder for your clark data"
BAD_WORDS = ("Terminal", "terminal", "python3", "clark.command", "clark.doctor", "double-click", "start clark again", "run bash",
             "–", "—", " - ", "--")


class Case(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="clark-home-")).resolve()
        self.addCleanup(shutil.rmtree, self.home, True)
        self.default = self.home / "Library" / "Application Support" / "clark"
        self.default.parent.mkdir(parents=True)
        self.onedrive = self.home / "OneDrive - Work"
        self.onedrive.mkdir()
        self.good = self.home / "Elsewhere"
        self.good.mkdir()

    def service(self, folder=None, only=None, **seams):
        checks = doctor.CHECKS if only is None else tuple(c for c in doctor.CHECKS if doctor.check_id(c) in only)
        return setup_mode.Setup(folder or self.default, home=self.home, on=pl.MAC, onedrive_roots=lambda: [self.onedrive], environ={},
                                checks=checks, seams=seams)

    def row(self, folder=None, which="python", **seams):
        report = self.service(folder, only=(which,), **seams).report()
        return report["checks"][0]


class Words(unittest.TestCase):
    def test_the_pages_own_strings_are_exactly_the_written_out_ones(self):
        self.assertEqual(setup_page.WORDS, WORDS)
        self.assertEqual(setup_mode.FOLDER_PROMPT, FOLDER_PROMPT)

    def test_no_dash_no_terminal_no_command_in_the_pages_strings(self):
        for key, text in list(WORDS.items()) + [("prompt", FOLDER_PROMPT)]:
            for bad in BAD_WORDS:
                self.assertNotIn(bad, text, key)

    def test_the_draft_labels_are_not_used(self):
        page = setup_page.html()
        for draft in ("Worth fixing", "Needs fixing", "Needs attention", "setup mode"):
            self.assertNotIn(draft, page)

    def test_the_status_labels_are_the_doctors_without_the_colon(self):
        for kind, label in doctor.LABELS.items():
            self.assertEqual(setup_page.WORDS[kind], label.rstrip(":"))


class PageVersions(Case):
    """Rows 14 16 20 22 24 of the words table: the page says what a button does, never a command or a Terminal step."""

    def test_14_the_data_folder_that_cannot_be_saved_in(self):
        blocker = self.home / "a-file"
        blocker.write_text("x", encoding="utf-8")
        row = self.row(blocker / "clark", "data_folder")
        self.assertEqual((row["status"], row["words"]),
                         (doctor.FIX, "Your clark data can't be saved in ~/a-file/clark. Choose a different folder."))

    def test_14_the_refusal_of_a_chosen_folder_has_the_same_page_words(self):
        link = self.home / "link"
        link.symlink_to(self.good)
        with self.assertRaises(setup_mode.Refused) as caught:
            self.service().accept(str(link))
        self.assertEqual(caught.exception.words, "Your clark data can't be saved in ~/link. Choose a different folder.")

    def test_14_the_good_line_is_the_doctors_own(self):
        self.assertEqual(self.row(self.good, "data_folder")["words"], "Your clark data can be saved in ~/Elsewhere.")

    def test_16_onedrive(self):
        row = self.row(self.onedrive / "clark", "data_not_in_onedrive")
        self.assertEqual((row["status"], row["words"]), (doctor.FIX, (
            "Your clark data is set to go in ~/OneDrive - Work/clark, which is inside OneDrive. OneDrive copies files while they are "
            "being written, which damages the data. Choose a folder on this computer that OneDrive doesn't sync. Backups can still go "
            "to OneDrive.")))

    def test_16_the_ready_line_is_the_doctors_own(self):
        self.assertEqual(self.row(self.good, "data_not_in_onedrive")["words"], "Your clark data isn't inside OneDrive.")

    def test_20_chrome(self):
        found = self.row(self.good, "browser", find_chrome=lambda: "/x/Chrome")
        self.assertEqual((found["status"], found["words"]), (doctor.READY, "Chrome is there, so clark opens in Chrome."))
        lost = self.row(self.good, "browser", find_chrome=lambda: None)
        self.assertEqual((lost["status"], lost["words"]), (doctor.ADVICE, "Chrome wasn't found, so clark will open in your usual "
                                                                          "browser. Install Chrome to open clark there."))

    def test_22_the_port(self):
        for kind, expect in ((launch.NOT_CLARK, "Nothing was started: clark is already open, or another program is using the "
                                                "connection it needs. Close it, then open clark again."),
                             (launch.OTHER_DATA, "Another copy of clark is already open with different data (this one uses "
                                                 "~/Elsewhere). Close that copy, then choose Check again.")):
            with self.subTest(kind=kind):
                row = self.row(self.good, "port", health=lambda port, mark, k=kind: k, free=lambda port: True)
                self.assertEqual((row["status"], row["words"]), (doctor.FIX, expect))

    def test_22_the_second_line_with_a_terminal_command_is_not_on_the_page(self):
        row = self.row(self.good, "port", health=lambda port, mark: launch.NOT_CLARK, free=lambda port: port != 8766)
        self.assertNotIn("Terminal", row["words"])
        self.assertNotIn("--port", row["words"])

    def test_22_a_bad_start_up_number(self):
        service = setup_mode.Setup(self.good, home=self.home, on=pl.MAC, environ={"CLARK_PORT": "x"}, onedrive_roots=lambda: [],
                                   checks=tuple(c for c in doctor.CHECKS if doctor.check_id(c) == "port"))
        row = service.report()["checks"][0]
        self.assertEqual(row["words"], "The start-up number (set with CLARK_PORT) must be a whole number from 1 to 65535. Change it, "
                                       "then choose Check again.")

    def test_24_a_check_that_stops(self):
        boom = doctor.Check("The OneDrive check for your data", True, lambda seen: 1 / 0)
        boom = boom._replace(run=_named(boom.run, "check_data_not_in_onedrive"))
        row = setup_mode.Setup(self.good, home=self.home, on=pl.MAC, environ={}, checks=(boom,)).report()["checks"][0]
        self.assertEqual((row["status"], row["words"]),
                         (doctor.NOT_CHECKED, "The OneDrive check for your data couldn't finish. Choose Check again."))

    def test_24_a_check_that_cannot_run_here_is_the_doctors_own_line(self):
        def not_here(seen):
            raise pl.NotBuiltYet("x")
        check = doctor.Check("The browser check", False, _named(not_here, "check_browser"))
        row = setup_mode.Setup(self.good, home=self.home, on=pl.MAC, environ={}, checks=(check,)).report()["checks"][0]
        self.assertEqual(row["words"], "The browser check can't run on this computer yet.")

    def test_the_other_rows_are_the_doctors_words_unchanged(self):
        for which in ("python", "app_folder", "claude"):
            doc = doctor.run_check([c for c in doctor.CHECKS if doctor.check_id(c) == which][0],
                                   self.service(self.good, only=(which,), find_claude=lambda: "/x").seen(self.good))
            self.assertEqual(self.row(self.good, which, find_claude=lambda: "/x")["words"], doc.words)

    def test_no_reachable_fix_or_advice_line_tells_a_person_to_use_a_terminal(self):
        blocker = self.home / "a-file"
        blocker.write_text("x", encoding="utf-8")
        seen = [self.row(blocker / "clark", "data_folder"), self.row(self.onedrive / "clark", "data_not_in_onedrive"),
                self.row(self.good, "browser", find_chrome=lambda: None), self.row(self.good, "browser", find_chrome=lambda: "/x"),
                self.row(self.good, "port", health=lambda p, m: launch.NOT_CLARK, free=lambda p: True),
                self.row(self.good, "port", health=lambda p, m: launch.OTHER_DATA, free=lambda p: True),
                self.row(self.good, "app_folder")]
        for row in seen:
            for bad in BAD_WORDS:
                self.assertNotIn(bad, row["words"], row["id"])

    def test_the_doctors_own_lines_are_not_edited(self):
        """The command line still has its Terminal words: only the page has its own."""
        seen = doctor.Seen(data=str(self.onedrive / "clark"), home=self.home, on=pl.MAC, onedrive_roots=lambda: [self.onedrive])
        self.assertIn("Terminal", doctor.check_data_not_in_onedrive(seen).words)
        self.assertIn("start clark again", doctor.cant_save_line(seen).words)


def _named(fn, name):
    fn.__name__ = name
    return fn


class Served(Case):
    def setUp(self):
        super().setUp()
        self.service_ = setup_mode.Setup(self.default, home=self.home, on=pl.MAC, onedrive_roots=lambda: [self.onedrive], environ={},
                                         prompt=setup_mode.FOLDER_PROMPT, choose_folder=lambda p: None)
        self.s = SetupRunning(self.service_)
        self.addCleanup(self.s.close)

    def page(self):
        status, headers, body = self.s.ask("GET", "/")
        self.assertEqual(status, 200)
        return headers, body.decode("utf-8")

    def test_the_real_page_is_served_at_slash_and_setup(self):
        _, text = self.page()
        self.assertEqual(self.s.ask("GET", "/setup")[2].decode("utf-8"), text)
        self.assertNotIn("clark is starting.", text)
        self.assertIn(WORDS["heading"], text)
        self.assertIn(json.dumps({"token": sv.TOKEN}), text)

    def test_the_stand_in_stays_only_for_a_setup_object_with_no_page(self):
        bare = mock.Mock(spec=["api_checks"])
        s = SetupRunning(bare)
        self.addCleanup(s.close)
        self.assertIn("clark is starting.", s.ask("GET", "/")[2].decode("utf-8"))

    def test_the_prompt_is_the_approved_one_and_the_folder_route_is_wired(self):
        self.assertEqual(setup_mode.Setup(self.default).prompt, setup_mode.FOLDER_PROMPT)

    def test_every_string_of_the_page_is_in_the_table_and_the_table_is_all_in_the_page(self):
        _, text = self.page()
        for key, value in WORDS.items():
            probe = value.split("{n}")[-1] if "{n}" in value else value
            self.assertIn(json.dumps(probe)[1:-1].replace("<", "\\u003c"), text, key)

    def test_plain_page_no_framework_no_outside_address_no_style_attribute_no_innerhtml(self):
        _, text = self.page()
        self.assertNotRegex(text, r"https?://(?!127\.0\.0\.1|localhost)")
        self.assertNotIn(" style=", text)
        self.assertNotIn("innerHTML", text)
        self.assertNotIn("outerHTML", text)
        self.assertNotIn("insertAdjacentHTML", text)
        self.assertNotIn("eval(", text)
        self.assertEqual(len(re.findall(r"<script(?![^>]*type=\"application/json\")", text)), 1)
        self.assertEqual(len(re.findall(r"<style", text)), 1)
        self.assertLess(len(text.encode("utf-8")), 20000)

    def test_accessible_shape(self):
        _, text = self.page()
        self.assertIn('<html lang="en-GB"', text)
        self.assertIn("<title>Setting up clark</title>", text)
        self.assertEqual(len(re.findall(r"<h1[ >]", text)), 1)
        self.assertIn('width=device-width', text)
        self.assertNotRegex(text, r'tabindex="[1-9]')
        self.assertIn('role="status"', text)
        self.assertIn('role="alert"', text)
        self.assertIn("prefers-color-scheme: dark", text)
        self.assertIn("color-scheme", text)
        self.assertIn(":focus-visible", text)
        self.assertEqual(len(re.findall(r"<button\b", text)), 2)
        self.assertNotIn("transition", text)
        self.assertNotIn("animation", text)

    def test_the_policy_covers_the_pages_own_blocks_and_nothing_outside(self):
        headers, text = self.page()
        policy = headers["Content-Security-Policy"]
        hashes = sv.csp_hashes(text)
        self.assertEqual(len(hashes["script"]), 1)
        self.assertEqual(len(hashes["style"]), 1)
        self.assertIn(hashes["script"][0], policy)
        self.assertIn("connect-src 'self'", policy)

    def test_no_other_text_of_the_page_names_a_route_the_setup_server_does_not_have(self):
        _, text = self.page()
        routes = set(re.findall(r"/api/[a-z/]+", text))
        self.assertEqual(routes, {"/api/setup/checks", "/api/setup/folder", "/api/setup/done", "/api/here"})
        self.assertLessEqual(routes, set(sv.SETUP_GET_ROUTES) | set(sv.SETUP_POST_ROUTES) | {sv.HERE_ROUTE})

    def test_the_page_module_imports_nothing_that_touches_data(self):
        src = (SRC / "clark" / "setup_page.py").read_text(encoding="utf-8")
        for name in ("store", "changes", "publish", "movement", "milestone_moves"):
            self.assertNotRegex(src, rf"(?m)^\s*(import|from)\s+.*\b{name}\b")
        self.assertNotIn("/api/movement", src)


if __name__ == "__main__":
    unittest.main()
