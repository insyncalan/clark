"""Hostile-input and mutation tests for the rows bundle's product code (PR 1338), Python side: glance.py's tile words
(None high, of N open risks and issues, No date set, Oldest needed by) and the launcher opening Chrome at clark.localhost
(platform.open_in_chrome, launch.launch / open_clark). Each test names the hand-made mutant it kills.

Run: python3 -m unittest test_rows_bundle_hostile   (from tests/; no browser needed)
"""
import unittest

from _paths import ROOT, SRC  # noqa: F401

from clark import glance as g  # noqa: E402
from clark import launch, platform as pl  # noqa: E402


def risk(status="Open", priority="Low", kind="risk", **kw):
    return {"kind": kind, "status": status, "priority": priority, **kw}


def decision(status="Pending", needed_by=None, **kw):
    return {"kind": "decision", "status": status, "needed_by": needed_by, **kw}


class RiskWords(unittest.TestCase):
    def detail(self, rows):
        return g._risks_tile(rows)["detail"]

    def test_empty_and_only_closed_say_none_open(self):
        self.assertEqual(self.detail([]), "None open")
        for closed in ("Closed", "Cancelled", "Made", "Withdrawn"):
            self.assertEqual(self.detail([risk(closed, "High")]), "None open", closed)

    def test_none_high_needs_open_and_no_high_not_just_few(self):
        # mutant: `elif not high` -> `elif len(open_) > 1 and not high` (a single low risk fell through to "of 1 open")
        self.assertEqual(self.detail([risk(priority="Low")]), "None high")
        # mutant: guard dropped (`elif True`): high rows must still say how many are open
        self.assertEqual(self.detail([risk(priority="High")]), "of 1 open risk or issue")
        # mutant: order swapped so None high is tested before None open: empty must stay None open
        self.assertEqual(self.detail([]), "None open")

    def test_odd_priorities_are_not_high(self):
        for p in (None, "", "high", "HIGH", " High", "Urgent ", "Critical", 0, 1, [], ["High"], {"a": 1}, "Ｈigh", "Hi\u0000gh", "Highé"):
            with self.subTest(priority=p):
                self.assertEqual(self.detail([risk(priority=p)]), "None high")
                self.assertEqual(g._risks_tile([risk(priority=p)])["auto_colour"], "amber")
                self.assertEqual(g._risks_tile([risk(priority=p)])["value"], 0)

    def test_urgent_and_high_both_count(self):
        # mutant: HIGH = ("High",) or ("Urgent",) only
        for p in ("Urgent", "High"):
            t = g._risks_tile([risk(priority=p), risk(priority="Low")])
            self.assertEqual((t["value"], t["detail"], t["auto_colour"]), (1, "of 2 open risks and issues", "red"), p)

    def test_singular_and_plural_edges(self):
        # mutant: `== 1` -> `<= 1` or `< 2` (same), `== 1` -> `== 2`, singular/plural swapped
        for n, words in ((1, "of 1 open risk or issue"), (2, "of 2 open risks and issues"), (3, "of 3 open risks and issues"),
                         (10, "of 10 open risks and issues"), (99999, "of 99999 open risks and issues")):
            rows = [risk(priority="High")] + [risk(priority="Low") for _ in range(n - 1)]
            self.assertEqual(self.detail(rows), words, n)

    def test_huge_counts(self):
        rows = [risk(priority="High") for _ in range(50000)]
        t = g._risks_tile(rows)
        self.assertEqual((t["value"], t["open"], t["high"], t["detail"]), (50000, 50000, 50000, "of 50000 open risks and issues"))

    def test_actions_and_decisions_never_count_as_risks(self):
        # mutant: kind filter `not in ("action", "decision")` -> `!= "action"`
        rows = [{"kind": "action", "status": "Open", "priority": "High"}, decision(priority="High")]
        rows[1]["priority"] = "High"
        t = g._risks_tile(rows)
        self.assertEqual((t["detail"], t["open"], t["value"]), ("None open", 0, 0))

    def test_every_non_action_non_decision_kind_counts(self):
        for kind in ("risk", "issue", "assumption", "dependency", "weird‮", "", "ризик"):
            self.assertEqual(self.detail([risk(kind=kind, priority="High")]), "of 1 open risk or issue", kind)

    def test_status_missing_or_odd_counts_as_open(self):
        # mutant: is_open inverted for None
        for status in (None, "", "open", "Pending", "closed", 0, "Ｃlosed"):
            self.assertEqual(self.detail([risk(status=status, priority="High")]), "of 1 open risk or issue", repr(status))

    def test_unicode_in_other_fields_changes_nothing(self):
        rows = [risk(priority="High", description="ünḯcôdé \U0001F600 <b>x</b>", owner="Zoë ​", id="R-٣")]
        self.assertEqual(self.detail(rows), "of 1 open risk or issue")

    def test_colour_follows_words(self):
        self.assertEqual(g._risks_tile([])["auto_colour"], "green")
        self.assertEqual(g._risks_tile([risk()])["auto_colour"], "amber")
        self.assertEqual(g._risks_tile([risk(priority="High")])["auto_colour"], "red")


class DecisionWords(unittest.TestCase):
    def tile(self, rows):
        return g._decisions_tile(rows)

    def test_none_waiting(self):
        self.assertEqual(self.tile([])["detail"], "None waiting")
        for s in ("Made", "Withdrawn", "Closed", "Cancelled", None, "pending", "Pending "):
            t = self.tile([decision(status=s, needed_by="2026-01-01")])
            self.assertEqual((t["value"], t["detail"]), (0, "None waiting"), repr(s))

    def test_no_date_set_for_every_kind_of_not_a_day(self):
        # mutant: day_number guard dropped (dated = all needed_by that are truthy)
        for bad in (None, "", " ", "2026-02-30", "2026-13-01", "2026-00-10", "2026-1-3", "03-11-2026", "2026-11-03T10:00", "2026-11-03\n",
                    " 2026-11-03", "2026/11/03", "tomorrow", "٢٠٢٦-11-03", 20261103, 0, [], {}, "２０２６-11-03", "0000-00-00", "2026-04-31"):
            with self.subTest(needed_by=bad):
                t = self.tile([decision(needed_by=bad)])
                self.assertEqual((t["detail"], t["oldest"], t["oldest_shown"], t["value"]), ("No date set", None, "", 1))

    def test_oldest_is_the_earliest_valid_day(self):
        # mutant: sorted(...)[0] -> [-1]; sorted -> min of unsorted first
        rows = [decision(needed_by="2026-11-20"), decision(needed_by="2026-11-03"), decision(needed_by="2027-01-01"), decision()]
        t = self.tile(rows)
        self.assertEqual((t["detail"], t["oldest"], t["oldest_shown"]), ("Oldest needed by 03-11-2026", "2026-11-03", "03-11-2026"))

    def test_invalid_dates_do_not_hide_a_valid_one_or_win_the_sort(self):
        rows = [decision(needed_by="2026-02-30"), decision(needed_by="0000-00-00"), decision(needed_by="2030-05-06"), decision(needed_by="")]
        self.assertEqual(self.tile(rows)["detail"], "Oldest needed by 06-05-2030")

    def test_single_dated_and_ties_and_leap_day(self):
        self.assertEqual(self.tile([decision(needed_by="2028-02-29")])["detail"], "Oldest needed by 29-02-2028")
        self.assertEqual(self.tile([decision(needed_by="2027-02-29")])["detail"], "No date set")
        t = self.tile([decision(needed_by="2026-05-05"), decision(needed_by="2026-05-05")])
        self.assertEqual((t["value"], t["detail"]), (2, "Oldest needed by 05-05-2026"))

    def test_only_pending_dates_count(self):
        # mutant: pending filter dropped: a made decision's old needed_by must not be quoted
        rows = [decision(status="Made", needed_by="2020-01-01"), decision(needed_by="2026-12-12")]
        self.assertEqual(self.tile(rows)["detail"], "Oldest needed by 12-12-2026")

    def test_only_decisions_count(self):
        rows = [{"kind": "action", "status": "Pending", "needed_by": "2026-01-01"}, {"kind": "risk", "status": "Pending", "needed_by": "2026-01-01"}]
        self.assertEqual(self.tile(rows)["detail"], "None waiting")

    def test_huge_counts_and_colour(self):
        t = self.tile([decision() for _ in range(30000)])
        self.assertEqual((t["value"], t["detail"], t["auto_colour"]), (30000, "No date set", "amber"))
        self.assertEqual(self.tile([])["auto_colour"], "green")

    def test_words_are_exact(self):
        # the page's exact words (ruling 06-11): a changed letter, case or full stop is caught
        self.assertEqual(self.tile([decision()])["detail"], "No date set")
        self.assertNotIn("Oldest needed by ", self.tile([decision()])["detail"])
        self.assertTrue(self.tile([decision(needed_by="2026-03-04")])["detail"].startswith("Oldest needed by "))


class OverdueWords(unittest.TestCase):
    def test_zero_one_many_open_actions(self):
        act = lambda s="Open", due="2099-01-01": {"kind": "action", "status": s, "due_date": due}
        self.assertEqual(g._overdue_tile([], "2026-11-11")["detail"], "No open actions")
        self.assertEqual(g._overdue_tile([act("Closed")], "2026-11-11")["detail"], "No open actions")
        self.assertEqual(g._overdue_tile([act()], "2026-11-11")["detail"], "of 1 open action")
        self.assertEqual(g._overdue_tile([act(), act()], "2026-11-11")["detail"], "of 2 open actions")
        t = g._overdue_tile([act(due="2026-11-10"), act(due="2026-11-11"), act(due="2026-02-30"), act(due=None)], "2026-11-11")
        self.assertEqual((t["value"], t["detail"]), (1, "of 4 open actions"))


# ---------------------------------------------------------------- launcher: Chrome at clark.localhost

class OpenInChrome(unittest.TestCase):
    def run_open(self, url, chrome="/stub/chrome"):
        calls = []
        pl.open_in_chrome(url, chrome, popen=lambda a, **kw: calls.append((a, kw)), on=pl.MAC)
        return calls

    def test_no_app_flag_in_any_form(self):
        # mutant: "--app=" + url put back
        (argv, kw), = self.run_open("http://clark.localhost:8766/")
        self.assertEqual(argv, ["/stub/chrome", "http://clark.localhost:8766/"])
        self.assertFalse(any(a.startswith("--") for a in argv))

    def test_the_url_is_one_argument_even_with_odd_characters(self):
        for url in ("http://clark.localhost:1/?a=1&b=2", "http://clark.localhost:1/#x", "http://clark.localhost:1/%E2%82%AC", "http://clark.localhost:1/€",
                    "https://x/" + "a" * 5000):
            with self.subTest(url=url[:40]):
                (argv, kw), = self.run_open(url)
                self.assertEqual(argv, ["/stub/chrome", url])

    def test_refused_addresses_never_start_chrome(self):
        # mutant: scheme check weakened (re.match without anchoring, or \Z dropped, or http only)
        for bad in ("", "clark.localhost:8766", "ftp://x/", "HTTP://x/", "http:/x", "http://", "http:// x", "http://x/\n--app=evil", "http://x/\n", "https://x\n", "http://x/\t", "http://x/ y",
                    "--new-window", "-x http://x/", " http://x/", "javascript:alert(1)", "data:text/html,x", "file:///etc/passwd", "chrome://settings", " http://x/",
                    "http://x/ ", "http://x/\r\nHost: y", "https://", None, 0, ["http://x/"]):
            with self.subTest(url=bad):
                calls = []
                with self.assertRaises(pl.PlatformError) as e:
                    pl.open_in_chrome(bad, "/stub", popen=lambda a, **kw: calls.append(a), on=pl.MAC)
                self.assertEqual(calls, [])
                self.assertIn("http:// or https://", str(e.exception))

    def test_chrome_given_as_a_path_object_is_one_string_argument(self):
        from pathlib import Path
        (argv, kw), = self.run_open("http://clark.localhost:1/", Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"))
        self.assertEqual(argv, ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "http://clark.localhost:1/"])

    def test_it_is_detached_with_no_shell_and_no_inherited_streams(self):
        import subprocess
        (argv, kw), = self.run_open("http://clark.localhost:1/")
        self.assertIs(kw["start_new_session"], True)
        for k in ("stdin", "stdout", "stderr"):
            self.assertIs(kw[k], subprocess.DEVNULL, k)
        self.assertNotIn("shell", kw)

    def test_os_errors_become_the_plain_sentence_only_those(self):
        for exc in (FileNotFoundError(2, "x"), PermissionError(13, "x"), OSError(8, "Exec format error"), NotADirectoryError()):
            def popen(a, **kw):
                raise exc
            with self.assertRaisesRegex(pl.PlatformError, r"^Chrome could not be started, so clark's window did not open\.$"):
                pl.open_in_chrome("http://x/", "/c", popen=popen, on=pl.MAC)

        def boom(a, **kw):
            raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            pl.open_in_chrome("http://x/", "/c", popen=boom, on=pl.MAC)

    def test_not_on_a_mac_nothing_is_started(self):
        calls = []
        with self.assertRaises(pl.NotBuiltYet):
            pl.open_in_chrome("http://x/", "/c", popen=lambda *a, **k: calls.append(a), on=pl.WINDOWS)
        self.assertEqual(calls, [])

    def test_popen_is_called_once(self):
        self.assertEqual(len(self.run_open("http://x/")), 1)


class Addresses(unittest.TestCase):
    def test_address_and_plain_address_for_edge_ports(self):
        # mutant: the two swapped; scheme https; trailing slash dropped
        for port in (1, 80, 8766, 65535, "8766"):
            self.assertEqual(launch.address(port), f"http://clark.localhost:{port}/")
            self.assertEqual(launch.plain_address(port), f"http://127.0.0.1:{port}/")

    def test_the_address_passes_open_in_chromes_own_check_for_every_port(self):
        for port in (1, 65535):
            self.assertEqual(len(OpenInChrome.run_open(self, launch.address(port))), 1)
            self.assertEqual(len(OpenInChrome.run_open(self, launch.plain_address(port))), 1)


class OpenClark(unittest.TestCase):
    def run_it(self, chrome, window_exc=None, browser_exc=None, port=8800):
        said, win, brw = [], [], []

        def open_window(url, c):
            win.append((url, c))
            if window_exc:
                raise window_exc

        def open_browser(url):
            brw.append(url)
            if browser_exc:
                raise browser_exc
        code = launch.open_clark(port, said.append, {"E": "1"}, lambda env: chrome, open_window, open_browser)
        return code, said, win, brw

    def test_chrome_found_opens_clark_localhost_not_the_browser(self):
        code, said, win, brw = self.run_it("/stub")
        self.assertEqual((code, said, win, brw), (0, ["Opened clark in Chrome."], [("http://clark.localhost:8800/", "/stub")], []))

    def test_chrome_not_found_uses_the_plain_address_and_says_so(self):
        # mutant: open_browser(address(port)) (Safari cannot resolve *.localhost); old "Install Chrome" sentence back
        for none in (None, "", 0, False):
            code, said, win, brw = self.run_it(none)
            self.assertEqual((code, win, brw), (0, [], ["http://127.0.0.1:8800/"]), repr(none))
            self.assertEqual(said, ["Chrome wasn't found, so clark opened in your default browser."])

    def test_failure_names_the_plain_address_in_both_branches(self):
        for chrome in ("/stub", None):
            code, said, win, brw = self.run_it(chrome, window_exc=pl.PlatformError("No."), browser_exc=pl.PlatformError("No."))
            self.assertEqual(code, 1)
            self.assertEqual(said, ["No. The clark server is still running. To use it, open this address in your browser: http://127.0.0.1:8800/"])

    def test_a_failure_does_not_say_it_opened(self):
        code, said, *_ = self.run_it("/stub", window_exc=pl.PlatformError("No."))
        self.assertFalse(any("Opened" in s or "opened" in s for s in said))

    def test_other_exceptions_are_not_swallowed(self):
        with self.assertRaises(ValueError):
            self.run_it("/stub", window_exc=ValueError("x"))

    def test_chrome_is_asked_with_the_environment(self):
        seen = []
        launch.open_clark(1, lambda s: None, {"HOME": "/h"}, lambda env: seen.append(env) or None, lambda *a: None, lambda u: None)
        self.assertEqual(seen, [{"HOME": "/h"}])

    def test_unicode_in_a_platform_message_is_passed_on_whole(self):
        code, said, *_ = self.run_it("/stub", window_exc=pl.PlatformError("Chrome ☃ ‮ not there."))
        self.assertTrue(said[0].startswith("Chrome ☃ ‮ not there. The clark server"))


class LaunchPassesThePortThrough(unittest.TestCase):
    """launch() hands the PORT (not a prebuilt URL) to open_clark: a running clark of ours is opened at clark.localhost, and a
    foreign program on the port is never opened at all."""

    def test_open_clark_receives_port_and_default_openers(self):
        import inspect
        sig = inspect.signature(launch.launch).parameters
        self.assertIs(sig["open_window"].default, pl.open_in_chrome)
        self.assertIs(sig["open_browser"].default, pl.open_url)
        self.assertIs(sig["find_chrome"].default, pl.find_chrome)

    def test_launch_with_no_chrome_opens_the_default_browser_at_the_plain_address(self):
        """Through launch() itself: a running clark of ours, no Chrome. Mutant: launch() passes address(port) (clark.localhost)
        to the default browser, which Safari cannot resolve."""
        from test_launch_running import Running, THIS

        class T(Running):
            def runTest(self):
                self.stub(version=THIS[0], folder=THIS[1])
                code = launch.launch(self.port, self.folder, self.said.append, {"PATH": "/bin"}, start=lambda *a, **k: self.fail("started"),
                                     find_chrome=lambda e: None, open_window=lambda u, c: self.fail("window"),
                                     open_browser=self.browser.append, finish=lambda f, say: True)
                self.assertEqual(code, 0)
                self.assertEqual(self.browser, [f"http://127.0.0.1:{self.port}/"])
                self.assertEqual(self.said[-1], "Chrome wasn't found, so clark opened in your default browser.")
        r = unittest.TextTestRunner(stream=__import__("io").StringIO()).run(T())
        self.assertTrue(r.wasSuccessful(), r.failures + r.errors)


if __name__ == "__main__":
    unittest.main()
