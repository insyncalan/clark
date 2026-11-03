"""#201: the words a person reads when clark cannot start because its address is taken. Each message names the cause and one next
step in plain words; the server's line, the launcher's line and START-HERE agree on the cause; none starts with the product name
and none sends a person to restart the Mac (the way out is the other connection the launcher offers, then the check). Run: python3 dev/run_tests.py test_launcher_words"""
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
from _paths import ROOT, TOOLS
from clark import launch, platform, server

sys.path.insert(0, str(TOOLS))
import package  # noqa: E402

LAUNCHER = mock.patch.object(platform, "launcher_name", return_value="clark.command")      # the launcher's name is only known on a Mac


def setUpModule():
    LAUNCHER.start()


def tearDownModule():
    LAUNCHER.stop()


CAUSE = "clark is already open in another"
CAUSE_TAIL = "or another program is using the connection it needs"


class TheServersLine(unittest.TestCase):
    def test_words(self):
        self.assertEqual(server.PORT_TAKEN, "Nothing was started: clark is already open in another window, or another program is using the "
                                            "connection it needs. Close the other window or program, then start clark again.")


class TheLaunchersLine(unittest.TestCase):
    def say(self, free):
        return launch.report(launch.NOT_CLARK, 8800, Path("/tmp/clark-data"), free=free)

    def test_the_cause_and_the_one_next_step(self):
        text = self.say(lambda p: False)
        self.assertEqual(text, "Nothing was started: clark is already open in another Terminal window, or another program is using the "
                               f"connection it needs. Close that Terminal window or program, then double-click {platform.launcher_name()} again.")

    def test_off_a_mac_the_line_still_reads_and_names_the_launcher_in_general_words(self):
        with mock.patch.object(platform, "launcher_name", side_effect=platform.NotBuiltYet("not built")):
            text = self.say(lambda p: False)
        self.assertIn("then double-click the clark launcher again.", text)

    def test_off_a_mac_a_free_port_nearby_and_either_kind_of_port_still_read_and_do_not_raise(self):
        with mock.patch.object(platform, "launcher_name", side_effect=platform.NotBuiltYet("not built")):
            for kind in (launch.NOT_CLARK, launch.OTHER_DATA):
                text = launch.report(kind, 8800, Path("/tmp/clark-data"), free=lambda p: p == 8801)
                self.assertTrue(text)
                self.assertNotIn("--port", text, "no command to type off a Mac")

    def test_the_step_covers_another_program_as_well_as_a_window(self):
        self.assertIn("Close that Terminal window or program, then double-click", self.say(lambda p: False))

    def test_a_free_port_is_only_a_second_line_for_a_person_who_cannot_close_the_other(self):
        text = self.say(lambda p: p == 8801)
        first, second = text.split("\n")
        self.assertEqual(first, self.say(lambda p: False))
        self.assertEqual(second, f"If you can't close it, open Terminal in the clark folder and type: ./{platform.launcher_name()} --port 8801")


class StartHere(unittest.TestCase):
    def test_the_paragraph(self):
        self.assertIn("If it says nothing was started because clark is already open in another\nTerminal window, or another program is using the "
                      "connection it needs, close\nthat Terminal window or program, then double-click clark.command again.\n", package.START_HERE_MAC)

    def test_it_ends_the_matter_with_a_real_next_step_not_a_restart(self):
        flat = " ".join(package.START_HERE_MAC.split())
        self.assertIn("If you can't close it, the message also gives a line to type in Terminal that starts clark on a different connection. "
                      "Type it as shown and press Return. If that does not work either, run the check described below: it says what to fix.", flat)
        self.assertIn("python3 -m clark.doctor", package.START_HERE_MAC)
        self.assertNotIn("restart", flat.lower())


class TheyAgree(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.LINES = (server.PORT_TAKEN, launch.report(launch.NOT_CLARK, 8800, Path("/tmp/clark-data"), free=lambda p: False),
                     " ".join(package.START_HERE_MAC.split()))

    def test_every_line_gives_the_same_cause(self):
        for text in self.LINES:
            flat = " ".join(text.split())
            self.assertIn(CAUSE, flat)
            self.assertIn(CAUSE_TAIL, flat)

    def test_none_starts_with_the_product_name_and_none_says_to_restart_the_mac(self):
        for text in self.LINES[:2]:
            self.assertFalse(text.lower().startswith("clark"), text)
        for text in self.LINES:
            self.assertNotIn("restart", text.lower())
        for path in list((ROOT / "src").rglob("*.py")) + [TOOLS / "package.py"]:
            self.assertNotIn("restart your Mac", path.read_text(encoding="utf-8"), path.name)

    def test_the_old_vague_wording_is_gone(self):
        for path in list((ROOT / "src" / "clark").glob("*.py")) + [TOOLS / "package.py"]:
            text = path.read_text(encoding="utf-8")
            self.assertFalse(re.search(r"using what clark needs to start", text), path.name)


class TheOtherLaunchMessages(unittest.TestCase):
    """Each other message the launcher says: what happened, and one next step, in plain words."""

    def folder(self):
        return Path("/tmp/clark-data")

    def test_a_clark_that_did_not_finish_starting_says_what_to_do_and_where_the_record_is(self):
        said = []
        process = mock.Mock(poll=lambda: 1)
        code = launch.launch(8800, self.folder(), said.append, {}, start=lambda *a, **k: process, find_chrome=lambda e: None,
                             health=lambda p, m: launch.NOTHING, wait=lambda *a, **k: launch.NOTHING, free=lambda p: False)
        self.assertEqual(code, 1)
        self.assertEqual(said[-1], "Nothing opened, because clark did not finish starting. Close this window, then double-click clark.command "
                                   "again. If it still does not start, send the file /tmp/clark-data/server.log to the clark team. It records what went wrong.")

    def test_a_program_the_mac_will_not_run_names_the_cause_and_the_step(self):
        def popen(argv, **kw):
            raise OSError(13, "Permission denied")
        with self.assertRaises(platform.PlatformError) as e:
            platform.start_detached(["a"], {}, Path(tempfile.mkdtemp()) / "server.log", popen=popen, on=platform.MAC)
        text = str(e.exception)
        self.assertTrue(text.startswith("Nothing was started, because this Mac would not run clark. Close this window and try again."), text)

    def test_a_window_chrome_would_not_open_says_clark_is_still_running_and_gives_the_address(self):
        def popen(argv, **kw):
            raise PermissionError(13, "Permission denied")
        said = []

        def open_window(url, chrome):
            platform.open_app_window(url, chrome, popen=popen, on=platform.MAC)
        code = launch.open_clark("http://127.0.0.1:8800/", said.append, {}, lambda e: "/stub", open_window, lambda u: None)
        self.assertEqual(code, 1)
        self.assertEqual(said, ["Chrome could not be started, so clark's window did not open. The clark server is still running. "
                                "To use it, open this address in your browser: http://127.0.0.1:8800/"])

    def test_a_start_up_number_that_is_not_a_number_says_what_to_change(self):
        from clark.__main__ import Usage, port_number
        with self.assertRaises(Usage) as e:
            port_number("abc", "--port")
        self.assertEqual(str(e.exception), "The start-up number (set with --port) must be a whole number from 1 to 65535. Change it, then start clark again.")

    def test_the_doctors_onedrive_line_says_every_step_without_pointing_at_another_file(self):
        from clark import doctor
        seen = doctor.Seen(data="/x/OneDrive-Co/clark", on=platform.MAC, home="/x", onedrive_roots=lambda: [Path("/x/OneDrive-Co")])
        words = doctor.check_data_not_in_onedrive(seen).words
        self.assertNotIn("START-HERE", words)
        self.assertIn("drag the folder you chose into the window, and press Return.", words)


if __name__ == "__main__":
    unittest.main()
