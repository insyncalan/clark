"""item 836 doctor rows 14, 16, 20, 22, 24 and 25: each row's text pinned in the Terminal doctor AND in the page data model.
Run: python3 dev/run_tests.py test_setup_rows

The rows are numbered as in the WORDS TABLE for item 836 slice 2 (plan issue item 1017). Slice 2 has no page yet; the page's data model is
what the setup service hands it (setup_mode.Setup.report: [{id, status, words}], and the folder refusal's `message`). The Terminal
doctor (doctor.doctor) and that data model must say the same words today, because the page only draws them. The table says several
of these sentences are wrong on a page (Terminal steps, "run ... again") and recommends page versions. Those page versions are NOT
approved (rule 8), so nothing here asserts a new sentence. What each row pins:

  * TERMINAL: the doctor's exact line, in a source checkout (typed.clark -> `python3 -m clark`) and in a download (CLARK_TYPED set).
  * PAGE: the same exact text from the setup service, so the day the owner approves a page version the one place that changes is
    the page side of that row's test, and the Terminal side must not move with it.
  * Row 25 has no sentence in the data model: the page counts the rows whose status is "fix". The model must carry no summary of
    its own, and the count must be the one the Terminal summary says.

Temporary home and folders only; every system call is a fake. No server, no port, no browser. Fixture folders are made up.
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from clark import doctor, launch, platform as pl, setup_mode

CHECK_ONEDRIVE = "The OneDrive check for your data"
SEEN = dict(version=(3, 9, 6), sqlite_version="3.37.0")


class Page(setup_mode.Setup):
    """The setup service with the doctor's other seams (browser, Claude Code, the port, the clark folder) replaced."""

    def __init__(self, *a, seams=None, **kw):
        super().__init__(*a, **kw)
        self.seams = seams or {}

    def seen(self, folder=None):
        base = super().seen(folder)
        for name, value in self.seams.items():
            setattr(base, name, value)
        return base


class Rows(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="clark-home-")).resolve()
        self.addCleanup(shutil.rmtree, self.home, True)
        self.app = self.home / "Documents" / "clark"
        self.app.mkdir(parents=True)
        self.default = self.home / "Library" / "Application Support" / "clark"
        self.default.parent.mkdir(parents=True)
        self.onedrive = self.home / "OneDrive - Work"
        self.onedrive.mkdir()
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("CLARK_TYPED", None)

    def seams(self, **over):
        seams = dict(find_chrome=lambda: "/fictional/chrome", find_claude=lambda: "/fictional/bin/claude",
                     health=lambda port, mark: launch.NOTHING, free=lambda port: False)
        seams.update(over)
        return seams

    def terminal(self, data, checks=doctor.CHECKS, port=None, **over):
        """The doctor's lines for `data`, exactly as printed, and its exit code."""
        lines = []
        seen = doctor.Seen(data=str(data), port=port, on=pl.MAC, home=self.home, environ={}, app=self.app,
                           onedrive_roots=lambda: [self.onedrive], **SEEN, **self.seams(**over))
        return doctor.doctor(seen, say=lines.append, checks=checks), lines

    def page(self, data, checks=doctor.CHECKS, **over):
        """The setup service's report for `data`: {id: row}, and the whole report."""
        service = Page(data, home=self.home, on=pl.MAC, onedrive_roots=lambda: [self.onedrive], environ={}, checks=checks,
                       seams=dict(self.seams(**over), app=self.app, **SEEN))
        report = service.api_checks()[1]
        return {row["id"]: row for row in report["checks"]}, report

    def both(self, data, check_id, label, words, status, **over):
        """The row `check_id` says `words` with `status`, in the Terminal doctor and in the page data model alike."""
        _, lines = self.terminal(data, **over)
        self.assertIn(f"{label} {words}", lines)
        rows, _ = self.page(data, **over)
        self.assertEqual(rows[check_id]["words"], words)
        self.assertEqual(rows[check_id]["status"], status)

    # Row 14: the data folder can't be saved in. The same sentence is the folder window's refusal (`message`).
    def test_row_14_data_folder_cant_be_saved_in(self):
        blocker = self.home / "a-file"
        blocker.write_text("x", encoding="utf-8")
        words = ("Your clark data can't be saved in ~/a-file/clark-data. Check you can save files there, then start clark "
                 "again.")
        self.both(blocker / "clark-data", "data_folder", "To fix:", words, "fix")     # under a file: nothing can be made there

    def test_row_14_the_folder_windows_refusal_says_the_same_words(self):
        link = self.home / "a-link"
        link.symlink_to(self.home)
        service = Page(self.default, home=self.home, on=pl.MAC, onedrive_roots=lambda: [self.onedrive], environ={},
                       prompt="Pick", choose_folder=lambda prompt: str(link))
        status, body = service.api_folder()
        self.assertEqual(status, 409)
        self.assertEqual(body["code"], "folder_refused")
        self.assertEqual(body["message"], "Your clark data can't be saved in ~/a-link. Check you can save files there, then "
                                          "start clark again.")

    # Row 16: the data folder is inside OneDrive. The line carries the typed command, so both forms are pinned.
    ONEDRIVE_HEAD = ("Your clark data is set to go in ~/OneDrive/clark, which is inside OneDrive. OneDrive copies files "
                     "while they are being written, which damages the data. Choose a folder on this computer that OneDrive "
                     "doesn't sync. Then open Terminal, type cd and a space, drag clark's folder into the Terminal window and "
                     "press Return. Type ")
    ONEDRIVE_TAIL = " and a space, drag the folder you chose into the window, and press Return. Backups can still go to OneDrive."

    def test_row_16_onedrive_in_a_checkout(self):
        words = self.ONEDRIVE_HEAD + "python3 -m clark --data" + self.ONEDRIVE_TAIL
        self.both(self.onedrive / "clark", "data_not_in_onedrive", "To fix:", words, "fix")

    def test_row_16_onedrive_in_a_download(self):
        os.environ["CLARK_TYPED"] = "1"
        words = self.ONEDRIVE_HEAD + "bash clark.command --data" + self.ONEDRIVE_TAIL
        self.both(self.onedrive / "clark", "data_not_in_onedrive", "To fix:", words, "fix")

    def test_row_16_a_folder_outside_onedrive_is_ready(self):
        self.both(self.home / "Elsewhere", "data_not_in_onedrive", "Ready:", "Your clark data isn't inside OneDrive.", "ready")

    # Row 20: the browser line, both ways.
    def test_row_20_chrome_found(self):
        self.both(self.default, "browser", "Ready:", "Chrome is there, so clark opens in Chrome.", "ready")

    def test_row_20_chrome_not_found(self):
        words = "Chrome wasn't found, so clark will open in your usual browser."
        self.both(self.default, "browser", "Worth knowing:", words, "advice", find_chrome=lambda: None)

    # Row 22: the port. The launcher's name is the Mac's and the doctor puts the answer on one line.
    def test_row_22_port_in_use_by_another_program(self):
        words = ("Nothing was started: clark is already open in another Terminal window, or another program is using the "
                 "connection it needs. Close that Terminal window or program, then double-click "
                 "clark.command again.")
        with mock.patch.object(launch, "launcher_file", return_value="clark.command"):     # the Mac's launcher; this host may not be one
            self.both(self.default, "port", "To fix:", words, "fix", health=lambda port, mark: launch.NOT_CLARK)

    def test_row_22_another_copy_with_different_data(self):
        words = ("Another copy of clark is already open with different data (this one uses "
                 f"{pl.with_tilde(self.default)}). Close that copy, then start clark again.")      # launch.report names the folder itself
        self.both(self.default, "port", "To fix:", words, "fix", health=lambda port, mark: launch.OTHER_DATA)

    def test_row_22_a_bad_start_up_number_is_only_the_terminals(self):
        only = (doctor.Check("The check that nothing is in the way", True, doctor.check_port),)
        _, lines = self.terminal(self.default, checks=only, port="abc")
        self.assertIn("To fix: The start-up number (set with --port) must be a whole number from 1 to 65535. Change it, then "
                      "run python3 -m clark.doctor again.", lines)
        rows, _ = self.page(self.default)          # the page's service never passes a number, so it cannot say this line
        self.assertEqual(rows["port"]["status"], "ready")

    # Row 24: a check that cannot run here, or stopped.
    def checks_that(self, error):
        def check_data_not_in_onedrive(seen):
            raise error
        return (doctor.Check(CHECK_ONEDRIVE, True, check_data_not_in_onedrive),)

    def test_row_24_cant_run_on_this_computer_yet(self):
        checks = self.checks_that(pl.NotBuiltYet("not built"))
        _, lines = self.terminal(self.default, checks=checks)
        words = f"{CHECK_ONEDRIVE} can't run on this computer yet."
        self.assertIn(f"Not checked: {words}", lines)
        rows, report = self.page(self.default, checks=checks)
        self.assertEqual(rows["data_not_in_onedrive"], {"id": "data_not_in_onedrive", "status": "not checked", "words": words,
                                                        "required": True, "page": words})      # nothing here sends a person to Terminal, so the page says it as is
        self.assertFalse(report["ready"])

    def test_row_24_couldnt_finish_in_a_checkout(self):
        checks = self.checks_that(RuntimeError("secret detail"))
        _, lines = self.terminal(self.default, checks=checks)
        words = f"{CHECK_ONEDRIVE} couldn't finish. Run python3 -m clark.doctor again."
        self.assertIn(f"Not checked: {words}", lines)
        rows, _ = self.page(self.default, checks=checks)
        self.assertEqual(rows["data_not_in_onedrive"]["words"], words)
        self.assertEqual(rows["data_not_in_onedrive"]["status"], "not checked")
        self.assertNotIn("secret", "".join(lines) + rows["data_not_in_onedrive"]["words"])      # never the computer's own text

    def test_row_24_couldnt_finish_in_a_download(self):
        os.environ["CLARK_TYPED"] = "1"
        checks = self.checks_that(RuntimeError("x"))
        _, lines = self.terminal(self.default, checks=checks)
        words = f"{CHECK_ONEDRIVE} couldn't finish. Run bash clark.command --check again."
        self.assertIn(f"Not checked: {words}", lines)
        rows, _ = self.page(self.default, checks=checks)
        self.assertEqual(rows["data_not_in_onedrive"]["words"], words)

    # Row 25: the summary line. Terminal only; the page model has no sentence for it, only the rows whose status is "fix".
    def two_fixes(self):
        return self.onedrive / "clark", dict(health=lambda port, mark: launch.NOT_CLARK)

    def test_row_25_one_thing_to_fix(self):
        code, lines = self.terminal(self.onedrive / "clark")
        self.assertEqual(code, 1)
        self.assertEqual(lines[-1], "1 thing to fix before clark can start. Fix it, then run python3 -m clark.doctor again.")
        _, report = self.page(self.onedrive / "clark")
        self.assertEqual([r["id"] for r in report["checks"] if r["status"] == "fix"], ["data_not_in_onedrive"])
        self.assertFalse(report["ready"])

    def test_row_25_two_things_to_fix_in_a_checkout_and_a_download(self):
        data, over = self.two_fixes()
        _, lines = self.terminal(data, **over)
        self.assertEqual(lines[-1], "2 things to fix before clark can start. Fix each one, then run python3 -m clark.doctor again.")
        _, report = self.page(data, **over)
        self.assertEqual(sorted(r["id"] for r in report["checks"] if r["status"] == "fix"), ["data_not_in_onedrive", "port"])
        os.environ["CLARK_TYPED"] = "1"
        _, lines = self.terminal(data, **over)
        self.assertEqual(lines[-1], "2 things to fix before clark can start. Fix each one, then run bash clark.command --check again.")

    def test_row_25_the_page_model_carries_no_summary_sentence(self):
        data, over = self.two_fixes()
        _, report = self.page(data, **over)
        self.assertEqual(sorted(report), ["checks", "container", "folder", "ok", "ready"])
        for row in report["checks"]:
            self.assertEqual(sorted(row), ["id", "page", "required", "status", "words"])
            self.assertNotIn("to fix before clark", row["words"])
            self.assertNotIn("to fix before clark", row["page"])
            self.assertNotIn("python3 -m clark.doctor", row["page"])          # the page says "Check again", never a command
            self.assertNotIn("bash clark.command", row["page"])
            self.assertTrue(row["page"])
        service = Page(data, home=self.home, on=pl.MAC, onedrive_roots=lambda: [self.onedrive], environ={},
                       seams=dict(self.seams(**over), app=self.app, **SEEN))
        status, body = service.api_done()
        self.assertEqual(status, 409)
        self.assertEqual(sorted(body), ["checks", "code", "ok", "ready"])         # not_ready: the rows, no sentence of its own
        self.assertEqual(body["code"], "not_ready")


if __name__ == "__main__":
    unittest.main()
