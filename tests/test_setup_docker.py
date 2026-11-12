"""item 836 Docker check on the setup page: when clark runs in Docker the page shows one more check, about the Mac folder the
container shares in as the data folder (CLARK_DATA_SOURCE), and hides "Choose a folder" (the folder window needs the Mac).
Run: python3 dev/run_tests.py test_setup_docker

The Terminal doctor is NOT changed (doctor.CHECKS keeps its seven checks): the row is added by the setup service only inside a
container. Words: the refusal sentences are starter_check's and cloud_folder's, unchanged; the one ready line is a PROPOSAL
(listed in the strings file for the row, not approved). Fictional paths; every system call is a fake. No server, no browser.
"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from clark import doctor, platform as pl, setup_mode, setup_page, typed

NOT_CHECKED_WORDS = f"The Docker check couldn't finish. Run {typed.doctor()} again."   # doctor.run_check's own sentence
SEEN = dict(version=(3, 9, 6), sqlite_version="3.37.0")
OK_LINE = "clark is running in Docker, and your data is kept in {host}."
ONEDRIVE = ("Your data can't be kept in {host} because it is inside OneDrive ({name}). OneDrive copies files while they are being "
            "written, which damages the database. Choose a folder on this computer that OneDrive doesn't sync.")
CLOUD = ("Your data can't be kept in {host} because it is inside {service}. {service} copies files while they are being written, "
         "which damages the database. Choose a folder on this computer that {service} doesn't sync.")


def seen_for(source):
    environ = {} if source is None else {"CLARK_DATA_SOURCE": source}
    return doctor.Seen(data="/data", on=pl.MAC, environ=environ, **SEEN)


class Check(unittest.TestCase):
    def test_a_plain_mac_folder_is_ready(self):
        host = "/Users/pat/Documents/clark-data"
        line = doctor.check_docker(seen_for(host))
        self.assertEqual((line.kind, line.words), (doctor.READY, OK_LINE.format(host=host)))

    def test_no_source_named_is_not_checked_in_the_existing_words_never_ready(self):
        line = doctor.check_docker(seen_for(None))
        self.assertEqual((line.kind, line.words), (doctor.NOT_CHECKED, NOT_CHECKED_WORDS))
        line = doctor.check_docker(seen_for(""))
        self.assertEqual(line.kind, doctor.NOT_CHECKED)
        self.assertNotIn("None", line.words)

    def test_onedrive_is_to_fix_in_the_refusals_own_words(self):
        host = "/Users/pat/OneDrive - Work/clark"
        line = doctor.check_docker(seen_for(host))
        self.assertEqual((line.kind, line.words), (doctor.FIX, ONEDRIVE.format(host=host, name="OneDrive - Work")))

    def test_each_synced_service_is_to_fix(self):
        for host, service in (("/Users/pat/Dropbox/clark", "Dropbox"),
                              ("/Users/pat/Library/Mobile Documents/com~apple~CloudDocs/clark", "iCloud Drive"),
                              ("/Users/pat/Google Drive/clark", "Google Drive")):
            with self.subTest(service=service):
                line = doctor.check_docker(seen_for(host))
                self.assertEqual((line.kind, line.words), (doctor.FIX, CLOUD.format(host=host, service=service)))

    def test_the_words_have_no_terminal_step_and_no_dash(self):
        for host in ("/Users/pat/OneDrive/x", "/Users/pat/Dropbox/x", "/Users/pat/ok"):
            words = doctor.check_docker(seen_for(host)).words
            for bad in ("Terminal", "python3", "start clark again", "—", "–", " - "):
                self.assertNotIn(bad, words)

    def test_the_terminal_doctor_is_unchanged(self):
        self.assertEqual(len(doctor.CHECKS), 7)
        self.assertNotIn("docker", [doctor.check_id(c) for c in doctor.CHECKS])
        self.assertEqual(doctor.check_id(doctor.Check("x", True, doctor.check_docker)), "docker")


class Report(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="clark-home-")).resolve()
        self.addCleanup(shutil.rmtree, self.home, True)
        self.data = self.home / "data"
        self.data.mkdir()

    def report(self, source, container=True):
        environ = {} if source is None else {"CLARK_DATA_SOURCE": source}
        service = setup_mode.Setup(self.data, home=self.home, on=pl.MAC, onedrive_roots=lambda: [], environ=environ)
        with mock.patch.object(pl, "container_mode", return_value=container):
            return service.api_checks()[1]

    def test_outside_docker_there_is_no_docker_row(self):
        report = self.report("/Users/pat/OneDrive/x", container=False)
        self.assertNotIn("docker", [row["id"] for row in report["checks"]])
        self.assertIs(report["container"], False)

    def test_inside_docker_the_row_is_last_required_and_says_its_page_words(self):
        report = self.report("/Users/pat/ok")
        self.assertIs(report["container"], True)
        row = report["checks"][-1]
        self.assertEqual((row["id"], row["status"], row["required"]), ("docker", doctor.READY, True))
        self.assertEqual(row["page"], OK_LINE.format(host="/Users/pat/ok"))

    def test_no_source_named_the_row_is_not_checked_never_ready_and_the_start_waits(self):
        report = self.report(None)
        row = report["checks"][-1]
        self.assertEqual((row["id"], row["status"]), ("docker", doctor.NOT_CHECKED))
        self.assertEqual(row["page"], "The Docker check couldn't finish. Choose Check again.")
        self.assertFalse(report["ready"])

    def test_a_synced_folder_stops_the_start(self):
        report = self.report("/Users/pat/Dropbox/clark")
        self.assertEqual(report["checks"][-1]["status"], doctor.FIX)
        self.assertFalse(report["ready"])
        self.assertEqual(report["checks"][-1]["page"], report["checks"][-1]["words"])

    def test_a_good_folder_does_not_stop_the_start(self):
        self.assertEqual([r["status"] for r in self.report("/Users/pat/ok")["checks"] if r["id"] == "docker"], [doctor.READY])


class Choose(Report):
    """Inside a container the service refuses the folder window itself: the hidden button is not the only guard."""

    def test_inside_docker_choose_is_refused_as_a_window_that_cannot_open_and_no_fake_is_asked(self):
        asked = []
        service = setup_mode.Setup(self.data, home=self.home, on=pl.MAC, onedrive_roots=lambda: [], environ={"CLARK_DATA_SOURCE": "/Users/pat/ok"},
                                   choose_folder=lambda prompt: asked.append(prompt), prompt="Pick")
        with mock.patch.object(pl, "container_mode", return_value=True):
            with self.assertRaises(setup_mode.Refused) as caught:
                service.choose("Pick")
            status, body = service.api_folder()
        self.assertEqual(caught.exception.code, "dialog_failed")
        self.assertEqual((status, body["code"], body["message"]), (409, "dialog_failed", caught.exception.words))
        self.assertEqual(body["message"], pl.mac_only_in_docker("The folder dialog"))
        self.assertIn("when clark runs in Docker", body["message"])
        self.assertEqual(asked, [])
        self.assertFalse((self.home / setup_mode.POINTER_NAME).exists())


class Page(unittest.TestCase):
    def test_the_page_hides_choose_a_folder_in_docker(self):
        self.assertIn("report.container", setup_page.SCRIPT)
        self.assertIn("choose.hidden = !needs || report.ready || report.container === true", setup_page.SCRIPT)

    def test_the_docker_row_has_a_page_line_function_that_keeps_the_refusal_unchanged(self):
        words = CLOUD.format(host="/Users/pat/Dropbox/x", service="Dropbox")
        self.assertEqual(setup_page.page_words("docker", doctor.FIX, words, seen_for("/Users/pat/Dropbox/x")), words)


if __name__ == "__main__":
    unittest.main()
