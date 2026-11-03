"""#636: clark's window opens in Google Chrome or Microsoft Edge, on the Mac and on Windows, and says which.

Run: python3 dev/run_tests.py test_find_browser
Everything is a fake: the system (`on=`), the environment, whether a file is there, and the program starter. No browser is
started and no real folder is looked at. What a real Windows machine does is on the hand-check list (#623).
"""
import ntpath
import subprocess
import unittest

import _paths  # noqa: F401  (puts src on the path)

from clark import doctor, launch, platform as pl

PF, PF86, LOCAL = r"C:\Program Files", r"C:\Program Files (x86)", r"C:\Users\fictional\AppData\Local"
WINDOWS_ENV = {"ProgramFiles": PF, "ProgramFiles(x86)": PF86, "LOCALAPPDATA": LOCAL}
CHROME = ntpath.join(PF, "Google", "Chrome", "Application", "chrome.exe")
CHROME86 = ntpath.join(PF86, "Google", "Chrome", "Application", "chrome.exe")
CHROME_MINE = ntpath.join(LOCAL, "Google", "Chrome", "Application", "chrome.exe")
EDGE86 = ntpath.join(PF86, "Microsoft", "Edge", "Application", "msedge.exe")
EDGE = ntpath.join(PF, "Microsoft", "Edge", "Application", "msedge.exe")


def have(*found):
    return lambda path: path in found


def on_windows(*found, environ=None):
    return pl.find_browser(WINDOWS_ENV if environ is None else environ, exists=have(*found), on=pl.WINDOWS)


class FindOnWindows(unittest.TestCase):
    def test_chrome_in_each_place_in_order(self):
        self.assertEqual(on_windows(CHROME, CHROME86, CHROME_MINE, EDGE86), CHROME)
        self.assertEqual(on_windows(CHROME86, CHROME_MINE, EDGE86), CHROME86)
        self.assertEqual(on_windows(CHROME_MINE, EDGE86), CHROME_MINE)

    def test_edge_only(self):
        self.assertEqual(on_windows(EDGE86), EDGE86)
        self.assertEqual(on_windows(EDGE), EDGE)

    def test_neither(self):
        self.assertIsNone(on_windows())
        self.assertIsNone(on_windows(CHROME, EDGE86, environ={}), "no folders named: nothing is guessed")

    def test_clark_browser_comes_first(self):
        self.assertEqual(on_windows(r"D:\stub.exe", CHROME, EDGE86, environ={**WINDOWS_ENV, "CLARK_BROWSER": r"D:\stub.exe"}),
                         r"D:\stub.exe")
        self.assertIsNone(on_windows(CHROME, EDGE86, environ={**WINDOWS_ENV, "CLARK_BROWSER": r"D:\gone.exe"}),
                          "a named browser that isn't there: the default browser is used, not Chrome or Edge")

    def test_find_chrome_is_the_same_function(self):
        self.assertIs(pl.find_chrome, pl.find_browser)


class FindOnTheMac(unittest.TestCase):
    def test_edge_after_chrome(self):
        home = "/Users/fictional"
        self.assertEqual(pl.find_browser({}, home, have(pl.CHROME_MAC, pl.EDGE_MAC), pl.MAC), pl.CHROME_MAC)
        self.assertEqual(pl.find_browser({}, home, have(pl.EDGE_MAC), pl.MAC), pl.EDGE_MAC)
        self.assertIsNone(pl.find_browser({}, home, have(), pl.MAC))

    def test_another_system_is_not_built_yet(self):
        with self.assertRaisesRegex(pl.NotBuiltYet, "on linux is not built yet"):
            pl.find_browser({"CLARK_BROWSER": "/stub"}, exists=have("/stub"), on="linux")


class AppWindow(unittest.TestCase):
    def test_the_app_window_command_on_windows(self):
        calls = []
        pl.open_app_window("http://127.0.0.1:8766/", EDGE86, popen=lambda a, **kw: calls.append((a, kw)), on=pl.WINDOWS)
        (argv, kw), = calls
        self.assertEqual(argv, [EDGE86, "--app=http://127.0.0.1:8766/"])
        self.assertEqual(kw["stdin"], subprocess.DEVNULL)
        self.assertIsNot(kw.get("shell"), True)

    def test_only_a_web_address_on_windows_too(self):
        with self.assertRaisesRegex(pl.PlatformError, "Only web addresses"):
            pl.open_app_window("file:///C:/x", EDGE86, popen=lambda *a, **k: None, on=pl.WINDOWS)

    def test_another_system_is_not_built_yet(self):
        with self.assertRaisesRegex(pl.NotBuiltYet, "on linux is not built yet"):
            pl.open_app_window("http://127.0.0.1:1/", "c", popen=lambda *a, **k: None, on="linux")


class SaysWhich(unittest.TestCase):
    def test_browser_names(self):
        for path, name in ((EDGE86, "Microsoft Edge"), (CHROME_MINE, "Google Chrome"), (pl.CHROME_MAC, "Google Chrome"),
                           (pl.EDGE_MAC, "Microsoft Edge"), ("/stub/browser", "the browser set in CLARK_BROWSER")):
            self.assertEqual(launch.browser_name(path), name)

    def open_with(self, found):
        said, windows, pages = [], [], []
        code = launch.open_clark("http://127.0.0.1:8766/", said.append, {}, lambda env: found,
                                 lambda u, c: windows.append((u, c)), pages.append)
        return code, said, windows, pages

    def test_the_launcher_says_which_browser(self):
        code, said, windows, pages = self.open_with(EDGE86)
        self.assertEqual((code, said, windows, pages),
                         (0, ["Opened clark in its own window, in Microsoft Edge."], [("http://127.0.0.1:8766/", EDGE86)], []))
        self.assertEqual(self.open_with(CHROME)[1], ["Opened clark in its own window, in Google Chrome."])

    def test_the_launcher_says_when_none_was_found(self):
        code, said, windows, pages = self.open_with(None)
        self.assertEqual((code, windows, pages), (0, [], ["http://127.0.0.1:8766/"]))
        self.assertEqual(said, ["Chrome or Edge wasn't found, so clark opened in your default browser. Install Google Chrome "
                                "or Microsoft Edge to give clark its own window."])

    def test_the_doctor_says_which_browser(self):
        line = doctor.check_browser(doctor.Seen(on=pl.WINDOWS, environ={**WINDOWS_ENV},
                                                find_chrome=lambda: on_windows(EDGE86)))
        self.assertEqual(line, doctor.Line(doctor.READY, "Microsoft Edge is there, so clark opens in its own window."))
        line = doctor.check_browser(doctor.Seen(on=pl.WINDOWS, find_chrome=lambda: None))
        self.assertEqual(line.kind, doctor.ADVICE)
        self.assertEqual(line.words, "Chrome or Edge wasn't found, so clark will open in your usual browser. Install Google "
                                     "Chrome or Microsoft Edge to give clark its own window.")


if __name__ == "__main__":
    unittest.main()
