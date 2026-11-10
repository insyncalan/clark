"""item 427, second slice: clark starts on Linux inside the shipped container, and nowhere else on Linux.

Run: python3 tests/test_platform_container.py
Container mode (platform.container_mode) is CLARK_CONTAINER=1 AND /.dockerenv or /run/.containerenv. The system is made to say
"linux" and the marker files are faked; nothing real is read, started or written outside a temporary folder.
On Linux, in container mode only, platform.onedrive_roots() answers an empty list. Outside a container Linux still raises
NotBuiltYet, Windows always does, and the Mac branch is the same as before.
"""
import io
import logging
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from clark import __main__ as launcher  # noqa: E402
from clark import platform as pl  # noqa: E402
from clark import server  # noqa: E402

LINUX = "linux"


def markers(*present):
    """os.path.exists that finds only the named container marker files (and every other path as it really is)."""
    return mock.patch("os.path.exists", lambda p: p in present or (p not in ("/.dockerenv", "/run/.containerenv") and os.path.lexists(p)))


def container(*present):
    return (mock.patch.dict("os.environ", {"CLARK_CONTAINER": "1"}), markers(*(present or ("/.dockerenv",))))


class Case(unittest.TestCase):
    def inside(self, *present):
        for patch in container(*present):
            patch.start()
            self.addCleanup(patch.stop)

    def linux(self):
        patch = mock.patch.object(sys, "platform", LINUX)
        patch.start()
        self.addCleanup(patch.stop)


class ContainerMode(Case):
    def test_not_a_container_with_nothing_set(self):
        with mock.patch.dict("os.environ", {}, clear=False), markers():
            os.environ.pop("CLARK_CONTAINER", None)
            self.assertFalse(pl.container_mode())

    def test_the_setting_alone_is_not_enough(self):
        with mock.patch.dict("os.environ", {"CLARK_CONTAINER": "1"}), markers():
            self.assertFalse(pl.container_mode())

    def test_a_marker_file_alone_is_not_enough(self):
        with markers("/.dockerenv", "/run/.containerenv"):
            os.environ.pop("CLARK_CONTAINER", None)
            self.assertFalse(pl.container_mode())

    def test_only_the_value_1_counts(self):
        for value in ("0", "", "true", "yes", "1 "):
            with mock.patch.dict("os.environ", {"CLARK_CONTAINER": value}), markers("/.dockerenv"):
                self.assertFalse(pl.container_mode(), repr(value))

    def test_docker_and_podman_markers_both_count(self):
        for marker in ("/.dockerenv", "/run/.containerenv"):
            with mock.patch.dict("os.environ", {"CLARK_CONTAINER": "1"}), markers(marker):
                self.assertTrue(pl.container_mode(), marker)

    def test_it_agrees_with_the_server_s_own_rule(self):
        """server.py (guarded) keeps its own copy of the rule so it imports nothing; the two must never differ."""
        for value in (None, "1", "0"):
            for present in ((), ("/.dockerenv",), ("/run/.containerenv",), ("/.dockerenv", "/run/.containerenv")):
                env = {"CLARK_CONTAINER": value} if value is not None else {}
                with mock.patch.dict("os.environ", env), markers(*present):
                    if value is None:
                        os.environ.pop("CLARK_CONTAINER", None)
                    self.assertEqual(pl.container_mode(), server.container_mode(), (value, present))


class OnedriveRoots(Case):
    def test_linux_in_a_container_has_none(self):
        self.inside()
        self.assertEqual(pl.onedrive_roots(on=LINUX), [])

    def test_linux_in_a_podman_container_has_none(self):
        self.inside("/run/.containerenv")
        self.assertEqual(pl.onedrive_roots(on=LINUX), [])

    def test_the_system_itself_is_read_when_no_system_is_given(self):
        self.linux()
        self.inside()
        self.assertEqual(pl.onedrive_roots(), [])

    def test_linux_outside_a_container_still_raises(self):
        self.linux()
        with markers():
            os.environ.pop("CLARK_CONTAINER", None)
            for call in (lambda: pl.onedrive_roots(), lambda: pl.onedrive_roots(on=LINUX)):
                with self.assertRaisesRegex(pl.NotBuiltYet, "Finding OneDrive on linux is not built yet"):
                    call()

    def test_linux_with_only_the_setting_still_raises(self):
        with mock.patch.dict("os.environ", {"CLARK_CONTAINER": "1"}), markers():
            with self.assertRaises(pl.NotBuiltYet):
                pl.onedrive_roots(on=LINUX)

    def test_linux_with_only_a_marker_file_still_raises(self):
        with markers("/.dockerenv"):
            os.environ.pop("CLARK_CONTAINER", None)
            with self.assertRaises(pl.NotBuiltYet):
                pl.onedrive_roots(on=LINUX)

    def test_windows_raises_even_in_a_container(self):
        self.inside()
        with self.assertRaisesRegex(pl.NotBuiltYet, "on Windows is not built yet"):
            pl.onedrive_roots(on=pl.WINDOWS)

    def test_the_mac_branch_is_the_same_in_container_mode(self):
        """Even with the setting and a marker file, the Mac looks in its own folders and finds what is there."""
        home = Path(tempfile.mkdtemp(prefix="clark-home-")).resolve()
        self.addCleanup(shutil.rmtree, home, True)
        (home / "Library" / "CloudStorage" / "OneDrive-Fictional").mkdir(parents=True)
        (home / "OneDrive Old").mkdir()
        (home / "Documents").mkdir()
        expected = sorted([home / "Library" / "CloudStorage" / "OneDrive-Fictional", home / "OneDrive Old"])
        self.assertEqual(pl.onedrive_roots(home, on=pl.MAC), expected)
        self.inside()
        self.assertEqual(pl.onedrive_roots(home, on=pl.MAC), expected)


class TheOtherMacOnlyCalls(Case):
    """Everything else that is Mac-only still raises NotBuiltYet in a container, now in Docker's words, and the callers
    already turn that into a plain refusal (a dialog says it cannot open, the log is left out, Ask says it needs a Mac)."""

    def calls(self):
        return (lambda: pl.data_dir(on=LINUX), lambda: pl.log_dir(on=LINUX), lambda: pl.never_read_places(on=LINUX),
                lambda: pl.open_file(__file__, run=None, on=LINUX), lambda: pl.reveal_file(__file__, run=None, on=LINUX),
                lambda: pl.open_url("http://127.0.0.1:8766/", run=None, on=LINUX), lambda: pl.choose_folder("Pick", on=LINUX),
                lambda: pl.choose_save_file("Save", "a.html", on=LINUX), lambda: pl.choose_open_file("Open", on=LINUX),
                lambda: pl.launcher_name(on=LINUX), lambda: pl.find_chrome({}, "/home", on=LINUX))

    def test_each_says_it_needs_the_mac_in_a_container(self):
        self.inside()
        for call in self.calls():
            with self.assertRaisesRegex(pl.NotBuiltYet, "needs the Mac, so it is not available when clark runs in Docker. To use it, start clark with clark.command instead.") as said:
                call()
            self.assertNotIn("linux", str(said.exception))
            self.assertTrue(issubclass(type(said.exception), pl.PlatformError))

    def test_each_keeps_the_old_words_outside_a_container(self):
        with markers():
            os.environ.pop("CLARK_CONTAINER", None)
            for call in self.calls():
                with self.assertRaisesRegex(pl.NotBuiltYet, "on linux is not built yet: clark runs on macOS for now"):
                    call()

    def test_login_name_needs_no_mac(self):
        self.inside()
        self.assertTrue(pl.login_name())


class StartsOnLinuxInTheContainer(Case):
    def start(self, args=()):
        folder = tempfile.mkdtemp(prefix="clark-data-")
        self.addCleanup(shutil.rmtree, folder, True)
        served = []

        def serve(**kwargs):
            served.append(kwargs)
            return 0
        out, err = io.StringIO(), io.StringIO()
        code = launcher.main(["--data", folder, "--port", "8799", *args], out=out, err=err, serve=serve,
                             environ={"CLARK_PORT": "8799"}, is_free=lambda port: True)
        return code, out.getvalue(), err.getvalue(), served, folder

    def test_clark_starts_with_the_data_folder_given(self):
        self.linux()
        self.inside()
        code, out, err, served, folder = self.start()
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(len(served), 1)
        self.assertIn("Using the data in", out)
        self.assertTrue((Path(folder) / "clark.db").exists())

    def test_clark_does_not_start_on_linux_outside_a_container(self):
        self.linux()
        with markers():
            os.environ.pop("CLARK_CONTAINER", None)
            code, out, err, served, folder = self.start()
        self.assertEqual((code, served), (1, []))
        self.assertIn("Finding OneDrive on linux is not built yet", err)

    def test_the_log_goes_in_the_data_folder_in_the_container(self):
        """Issue 742: the container is always started with --data, so its log is <data>/logs (there is no Library/Logs to use)."""
        self.linux()
        self.inside()
        log, handler, logs = launcher.start_log(Path("/data"), lambda: [])
        self.addCleanup(logging.getLogger("clark").removeHandler, handler)
        self.assertEqual(log.folder, Path("/data/logs"))

    def test_the_data_folder_check_passes_with_no_onedrive_to_check_against(self):
        self.linux()
        self.inside()
        folder = Path(tempfile.mkdtemp(prefix="clark-data-")).resolve()
        self.addCleanup(shutil.rmtree, folder, True)
        self.assertEqual(Path(pl.check_data_dir(folder)).resolve(), folder)


class ContainerOneDrive(unittest.TestCase):
    """The Mac's data folder, named by the compose file, is refused when it is in OneDrive (item 427): from inside the container OneDrive
    cannot be seen, so the name is read."""

    def host(self, path, container=True):
        env = {"CLARK_CONTAINER": "1" if container else "0", "CLARK_DATA_SOURCE": path}
        return mock.patch.dict("os.environ", env), markers("/.dockerenv")

    def test_a_onedrive_folder_is_named_whichever_way_the_app_spells_it(self):
        for path in ("/Users/sam/Library/CloudStorage/OneDrive-Fictional Ltd/clark", "/Users/sam/OneDrive/clark",
                     "/Users/sam/OneDrive - Fictional Ltd/Documents/clark", "/Users/sam/onedrive-personal/clark"):
            with self.subTest(path):
                a, b = self.host(path)
                with a, b:
                    self.assertIsNotNone(pl.container_host_in_onedrive())
                    with self.assertRaises(pl.PlatformError) as e:
                        pl.check_data_dir("/data")
                    self.assertIn("inside OneDrive", str(e.exception))
                    self.assertIn("clark", str(e.exception)); self.assertNotIn("/data", str(e.exception), "it names the Mac's folder, not the container's")

    def test_an_ordinary_folder_and_a_name_that_only_contains_onedrive_are_let_through(self):
        for path in ("/Users/sam/Library/Application Support/clark", "/Users/sam/clark-data", "/Users/sam/Documents/not-OneDrive-really/clark",
                     "/Users/sam/Library/CloudStorage/Box/clark", "/data"):
            with self.subTest(path):
                a, b = self.host(path)
                with a, b:
                    self.assertIsNone(pl.container_host_in_onedrive())
                    self.assertEqual(pl.check_data_dir("/data"), Path("/data").resolve())

    def test_it_is_never_asked_outside_a_container_and_the_backups_words_are_unchanged(self):
        a, b = self.host("/Users/sam/OneDrive/clark", container=False)
        with a, b:
            self.assertIsNone(pl.container_host_in_onedrive())
        a, b = self.host("/Users/sam/OneDrive/clark")
        with a, b:
            self.assertEqual(pl.check_data_dir("/data", what="backups"), Path("/data").resolve())    # only the data folder is the shared one

    def test_without_the_variable_nothing_is_known_and_nothing_is_refused(self):
        with mock.patch.dict("os.environ", {"CLARK_CONTAINER": "1"}), markers("/.dockerenv"):
            os.environ.pop("CLARK_DATA_SOURCE", None)
            self.assertIsNone(pl.container_host_in_onedrive())

    def test_the_compose_file_hands_the_same_setting_to_clark_as_it_shares_in(self):
        text = (Path(__file__).resolve().parents[1] / "docker" / "compose.yaml").read_text(encoding="utf-8")
        self.assertIn("source: ..", text)                                     # the folder compose is started in, with the data in its data folder
        self.assertIn('--data", "/data"', text)
        self.assertIn("source: ${CLARK_DATA_DIR:-${HOME}/Library/Application Support/clark}", text)   # a named data folder is the one shared in, and the one named to clark
        self.assertIn('CLARK_DATA_SOURCE: "${CLARK_DATA_DIR:-${HOME}/Library/Application Support/clark}"', text)   # the same default, so the OneDrive check sees the folder that is mounted


class ShownPath(unittest.TestCase):
    """#696: a path is written from "~" only when it really is under the home folder."""

    def test_outside_home_the_path_is_shown_as_it_is(self):
        for home, path in (("/Users/sam", "/tmp/clark-v100-run/OneDrive - Test/data"), ("/Users/sam", "/Users/samuel/clark"),
                           ("/private/tmp/h", "/tmp/h/clark"), ("/Users/sam", "/private/tmp/x"), ("/", "/tmp/clark/data"),
                           ("/", "/Users/sam/OneDrive/clark")):
            with self.subTest(home=home, path=path):
                self.assertEqual(pl.shown(path, home=home), path)

    def test_under_home_it_is_written_from_the_tilde(self):
        self.assertEqual(pl.shown("/Users/sam/Documents/clark", home="/Users/sam"), "~/Documents/clark")
        self.assertEqual(pl.shown("/Users/sam", home="/Users/sam"), "~")

    def test_the_onedrive_refusal_shows_the_real_path(self):
        data = "/tmp/clark-v100-run/OneDrive - Test/data"
        with mock.patch.dict("os.environ", {"HOME": "/Users/sam"}), self.assertRaises(pl.PlatformError) as e:
            pl.check_data_dir(data, roots=["/tmp/clark-v100-run/OneDrive - Test"])
        self.assertIn(f"kept in {data} because", str(e.exception))
        self.assertNotIn("~/", str(e.exception))

    def test_the_container_refusal_with_a_root_home_names_the_macs_folder_as_it_is(self):
        mac = "/Users/sam/OneDrive - Test/clark"
        with mock.patch.dict("os.environ", {"CLARK_CONTAINER": "1", "CLARK_DATA_SOURCE": mac, "HOME": "/"}), markers("/.dockerenv"), \
                self.assertRaises(pl.PlatformError) as e:
            pl.check_data_dir("/data")
        self.assertIn(f"kept in {mac} because", str(e.exception))


class StartLine(Case):
    def test_the_container_line_gives_the_docker_stop_and_no_window(self):
        self.inside()
        text = launcher.start_line("http://127.0.0.1:8766/")
        self.assertEqual(text, "Open http://127.0.0.1:8766/ to use clark. Stop it with: docker compose -f docker/compose.yaml down")
        self.assertNotIn("Ctrl", text); self.assertNotIn("window", text)

    def test_the_terminal_line_is_unchanged(self):
        with mock.patch.dict("os.environ", {}), markers():
            os.environ.pop("CLARK_CONTAINER", None)
            self.assertEqual(launcher.start_line("http://127.0.0.1:8766/"),
                             "Open http://127.0.0.1:8766/ to use clark. Leave this window open. Press Ctrl+C to stop.")


if __name__ == "__main__":
    unittest.main()
