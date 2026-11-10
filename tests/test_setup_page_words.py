"""#836 step 5: the setup page's words and bytes (src/clark/setup_page.py), without a browser. Run: python3 dev/run_tests.py test_setup_page_words
The page versions of the doctor's lines (no Terminal instruction on a page, "choose Check again"), the labels, the page's own sentences,
the page served by the setup server (token, policy, no outside address), and the page versions on the service's replies.
The pages as drawn are in test_setup_page_browser. Temporary folders only; the folder window is always a fake."""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT
from test_server_setup import SetupRunning

from clark import doctor, launch, platform as pl, server as sv, setup_mode, setup_page

# What no sentence on the page may tell a person to do or name: the doctor's Terminal steps and commands.
NOT_ON_A_PAGE = ("Terminal", "python3", "bash clark.command", "double-click", "doctor", "start clark again", "xcode", "./", " --",
                 "Run ", "drag", "Return")
DASHES = ("\u2013", "\u2014")      # a folder's own name can hold " - " (OneDrive - Work): the page line is only checked for the long dashes


def said(line):
    return line.words


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

    def seen(self, **kw):
        base = dict(data=str(self.default), home=self.home, on=pl.MAC, environ={}, onedrive_roots=lambda: [self.onedrive],
                    find_chrome=lambda: "/chrome", find_claude=lambda: "/claude", app=self.home / "clark",
                    health=lambda port, mark: launch.NOTHING, free=lambda port: True)
        base.update(kw)
        return doctor.Seen(**base)

    def page(self, check, seen):
        """The page version of one check's line, as the setup service sends it."""
        line = doctor.run_check(check, seen)
        return line, setup_page.page_words(doctor.check_id(check), line.kind, line.words, seen)

    def by_name(self, name):
        return [c for c in doctor.CHECKS if doctor.check_id(c) == name][0]


class PageVersions(Case):
    """Rows 14, 16, 20, 22, 24 and 25 of the approved table, exactly."""

    def test_row_14_data_folder_that_cannot_be_saved_in(self):
        (self.home / "afile").write_text("x", encoding="utf-8")
        seen = self.seen(data=str(self.home / "afile" / "clark"))
        line, page = self.page(self.by_name("data_folder"), seen)
        self.assertEqual(line.kind, doctor.FIX)
        self.assertEqual(page, "Your clark data can't be saved in ~/afile/clark. Choose a different folder.")

    def test_row_16_onedrive_without_the_terminal_steps(self):
        inside = self.onedrive / "clark"
        line, page = self.page(self.by_name("data_not_in_onedrive"), self.seen(data=str(inside)))
        self.assertEqual(line.kind, doctor.FIX)
        self.assertIn("Terminal", line.words)                      # the doctor's own line keeps its Terminal steps
        self.assertEqual(page, f"Your clark data is set to go in ~/{inside.relative_to(self.home)}, which is inside OneDrive. "
                               "OneDrive copies files while they are being written, which damages the data. Choose a folder on this "
                               "computer that OneDrive doesn't sync. Backups can still go to OneDrive.")

    def test_row_20_browser(self):
        _, found = self.page(self.by_name("browser"), self.seen())
        _, missing = self.page(self.by_name("browser"), self.seen(find_chrome=lambda: None))
        self.assertEqual(found, "Chrome is there, so clark opens in Chrome.")
        self.assertEqual(missing, "Chrome wasn't found, so clark will open in your usual browser. Install Chrome to open clark there.")

    def test_row_22_port(self):
        _, other = self.page(self.by_name("port"), self.seen(health=lambda port, mark: launch.NOT_CLARK))
        self.assertEqual(other, "Nothing was started: clark is already open, or another program is using the connection it needs. "
                                "Close it, then choose Check again.")
        _, data = self.page(self.by_name("port"), self.seen(health=lambda port, mark: launch.OTHER_DATA))
        self.assertRegex(data, r"^Another copy of clark is already open with different data \(this one uses [^)]+\)\. "
                               r"Close that copy, then choose Check again\.$")

    def test_row_22_a_bad_start_up_number(self):
        _, page = self.page(self.by_name("port"), self.seen(environ={"CLARK_PORT": "abc"}))
        self.assertEqual(page, "The start-up number (set with CLARK_PORT) must be a whole number from 1 to 65535. Change it, then "
                               "choose Check again.")

    def test_row_24_a_check_that_could_not_finish(self):
        def broken(seen):
            raise ValueError("x")
        check = doctor.Check("The OneDrive check for your data", True, broken)
        line = doctor.run_check(check, self.seen())
        self.assertEqual(line.kind, doctor.NOT_CHECKED)
        self.assertEqual(setup_page.page_words("x", line.kind, line.words, self.seen()),
                         "The OneDrive check for your data couldn't finish. Choose Check again.")

    def test_row_24_a_check_that_cannot_run_here_is_unchanged(self):
        def not_built(seen):
            raise pl.NotBuiltYet("x")
        line = doctor.run_check(doctor.Check("The Python check", True, not_built), self.seen())
        self.assertEqual(setup_page.page_words("x", line.kind, line.words, self.seen()), "The Python check can't run on this computer yet.")

    def test_python_and_claude_say_choose_check_again(self):
        _, mac = self.page(self.by_name("python"), self.seen(version=(3, 8, 0)))
        _, other = self.page(self.by_name("python"), self.seen(version=(3, 8, 0), on="linux"))
        _, nosql = self.page(self.by_name("python"), self.seen(sqlite_version=""))
        _, claude = self.page(self.by_name("claude"), self.seen(find_claude=lambda: None))
        self.assertEqual(mac, "This Mac's Python (3.8.0) is too old for clark. Install a newer Python, then choose Check again.")
        self.assertEqual(other, "This computer's Python (3.8.0) is too old for clark, which needs 3.9 or newer. Install a newer "
                                "Python, then choose Check again.")
        self.assertEqual(nosql, "This Python can't keep clark's data. Install a full copy of Python from python.org, then choose "
                                "Check again.")
        self.assertEqual(claude, "Claude Code wasn't found, so ask clark can't run. The rest of clark works without it. To use ask "
                                 "clark, install Claude Code, then choose Check again.")

    def test_the_lines_that_were_already_fine_are_unchanged(self):
        for name in ("data_folder", "data_not_in_onedrive", "app_folder", "port", "claude", "python"):
            line, page = self.page(self.by_name(name), self.seen())
            self.assertEqual((line.kind, page), (doctor.READY, line.words), name)

    def test_no_state_of_any_check_puts_a_terminal_step_on_the_page(self):
        (self.home / "afile").write_text("x", encoding="utf-8")
        inside = self.onedrive / "clark"
        cases = [self.seen(version=(3, 8, 0)), self.seen(version=(3, 8, 0), on="linux"), self.seen(version=(3, 8, 0), on=pl.WINDOWS),
                 self.seen(sqlite_version=""), self.seen(sqlite_version="", on=pl.WINDOWS), self.seen(data=str(self.home / "afile" / "c")),
                 self.seen(data=str(inside)), self.seen(find_chrome=lambda: None), self.seen(find_claude=lambda: None),
                 self.seen(health=lambda p, m: launch.NOT_CLARK), self.seen(health=lambda p, m: launch.OTHER_DATA),
                 self.seen(health=lambda p, m: launch.OTHER_DATA, free=lambda port: False), self.seen(environ={"CLARK_PORT": "0"}),
                 self.seen(app=self.onedrive / "clark")]
        for seen in cases:
            for check in doctor.CHECKS:
                line = doctor.run_check(check, seen)
                page = setup_page.page_words(doctor.check_id(check), line.kind, line.words, seen)
                with self.subTest(check=doctor.check_id(check), words=page):
                    for bad in NOT_ON_A_PAGE + DASHES:
                        self.assertNotIn(bad, page)

    def test_a_check_that_stops_never_shows_the_computers_own_words(self):
        def stops(seen):
            raise OSError("/private/secret path")
        line = doctor.run_check(doctor.Check("The browser check", False, stops), self.seen())
        self.assertNotIn("secret", setup_page.page_words("x", line.kind, line.words, self.seen()))


class Sentences(unittest.TestCase):
    def test_the_labels_are_the_doctors_four_without_the_colon(self):
        self.assertEqual(setup_page.LABELS, {k: v.rstrip(":") for k, v in doctor.LABELS.items()})
        self.assertEqual(sorted(setup_page.LABELS.values()), ["Not checked", "Ready", "To fix", "Worth knowing"])

    def test_the_final_strings(self):
        self.assertEqual(setup_page.WORDS, {
            "title": "Setting up clark",
            "notice": "clark is being set up. Nothing is saved until the checks below pass.",
            "again": "Check again",
            "choose": "Choose a folder",
            "waiting": "Waiting for you to choose a folder.",
            "open_window": "A folder window is already open.",
            "ready": "Everything clark needs is ready. Opening clark.",
            "fix_one": "1 thing to fix before clark can start. Fix it, then choose Check again.",
            "fix_many": "{n} things to fix before clark can start. Fix each one, then choose Check again.",
            "unknown": doctor.summary([(doctor.CHECKS[0], doctor.Line(doctor.NOT_CHECKED, ""))])[0],
        })
        self.assertEqual(setup_mode.FOLDER_PROMPT, "Choose a folder for your clark data")

    def test_the_unknown_line_is_the_doctors_own(self):
        self.assertTrue(setup_page.WORDS["unknown"].startswith("Some checks can't run on this computer yet"))

    def test_no_sentence_has_a_dash_or_a_terminal_step(self):
        for key, text in list(setup_page.WORDS.items()) + [("prompt", setup_mode.FOLDER_PROMPT)]:
            with self.subTest(key=key):
                for bad in NOT_ON_A_PAGE + DASHES + (" - ",):
                    self.assertNotIn(bad, text)

    def test_the_fix_line_counts_like_the_doctors_without_its_command(self):
        two = doctor.summary([(c, doctor.Line(doctor.FIX, "")) for c in doctor.CHECKS[:2]])[0]
        self.assertTrue(two.startswith(setup_page.WORDS["fix_many"].split(" Fix each one")[0].replace("{n}", "2")))


class Served(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="clark-home-")).resolve()
        self.addCleanup(shutil.rmtree, self.home, True)
        self.default = self.home / "Library" / "Application Support" / "clark"
        self.default.parent.mkdir(parents=True)
        self.service = setup_mode.Setup(self.default, home=self.home, on=pl.MAC, onedrive_roots=lambda: [], environ={},
                                        choose_folder=lambda prompt: None, prompt=setup_mode.FOLDER_PROMPT)
        self.s = SetupRunning(self.service)
        self.addCleanup(self.s.close)

    def test_the_page_is_the_real_one_not_the_stand_in(self):
        status, headers, body = self.s.ask("GET", "/")
        text = body.decode("utf-8")
        self.assertEqual(status, 200)
        self.assertNotIn("clark is starting.", text)
        self.assertIn("<title>Setting up clark</title>", text)
        self.assertEqual(self.s.ask("GET", "/setup")[2], body)

    def test_the_token_is_in_the_boot_block_and_the_policy_covers_the_bytes(self):
        _, headers, body = self.s.ask("GET", "/")
        text = body.decode("utf-8")
        self.assertIn(json.dumps({"token": sv.TOKEN}), text)
        policy = headers["Content-Security-Policy"]
        hashes = sv.csp_hashes(text)
        self.assertEqual(len(hashes["script"]), 1)
        self.assertEqual(len(hashes["style"]), 1)
        for sha in hashes["script"] + hashes["style"]:
            self.assertIn(sha, policy)
        self.assertNotIn("unsafe-inline'", policy.split("script-src")[1].split(";")[0])

    def test_no_address_outside_this_computer_and_no_inline_handler(self):
        text = self.s.ask("GET", "/")[2].decode("utf-8")
        self.assertEqual(re.findall(r"https?://", text), [])
        self.assertEqual(re.findall(r"\son[a-z]+\s*=", text), [])
        self.assertNotIn("innerHTML", text)
        self.assertNotIn("eval(", text)

    def test_the_words_are_in_a_data_block_the_page_reads(self):
        text = self.s.ask("GET", "/")[2].decode("utf-8")
        block = re.search(r'<script type="application/json" id="setup-words">(.*?)</script>', text, re.S).group(1)
        self.assertEqual(json.loads(block), {"words": setup_page.WORDS, "labels": setup_page.LABELS})

    def test_a_service_without_a_page_keeps_the_stand_in(self):
        class Bare:
            def api_checks(self):
                return 200, {}
        self.s.httpd.setup = Bare()
        self.assertIn("clark is starting.", self.s.ask("GET", "/")[2].decode("utf-8"))

    def test_the_server_file_names_no_word_of_the_page(self):
        text = (ROOT / "src" / "clark" / "server.py").read_text(encoding="utf-8")
        for word in ("Setting up clark", "Check again", "Choose a folder"):
            self.assertNotIn(word, text)

    def test_the_page_module_imports_no_store(self):
        text = (ROOT / "src" / "clark" / "setup_page.py").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"^[ \t]*(?:from|import)[ \t]+.*\b(?:store|changes|publish\w*|history)\b.*$", text, re.M), [])


class Replies(Case):
    """The service's replies carry the page version beside the doctor's line (the doctor's own `words` are unchanged)."""

    def service(self, answer=None, **kw):
        return setup_mode.Setup(self.default, home=self.home, on=pl.MAC, choose_folder=lambda prompt: answer,
                                onedrive_roots=lambda: [self.onedrive], environ={}, prompt=setup_mode.FOLDER_PROMPT, **kw)

    def test_every_check_row_has_a_page_line(self):
        for row in self.service().report()["checks"]:
            self.assertEqual(set(row), {"id", "status", "words", "required", "page"})
            self.assertIsInstance(row["page"], str)

    def test_the_onedrive_row_keeps_the_doctors_words_and_adds_the_page_ones(self):
        service = self.service()
        service.folder = self.onedrive / "clark"
        row = [r for r in service.report()["checks"] if r["id"] == "data_not_in_onedrive"][0]
        self.assertIn("Terminal", row["words"])
        self.assertNotIn("Terminal", row["page"])
        self.assertTrue(row["page"].endswith("Backups can still go to OneDrive."))

    def test_a_refused_folder_carries_a_page_line_without_start_clark_again(self):
        service = self.service(str(self.home / "no" / "such"))
        status, body = service.api_folder()
        self.assertEqual((status, body["code"]), (409, "folder_refused"))
        self.assertIn("start clark again", body["message"])
        self.assertTrue(body["page"].endswith("Choose a different folder."))
        self.assertIn("can't be saved in", body["page"])

    def test_a_onedrive_refusal_page_line_is_the_approved_page_line_not_the_platforms(self):
        inside = self.onedrive / "clark"
        inside.mkdir()
        status, body = self.service(str(inside)).api_folder()
        self.assertEqual(body["page"], setup_page.page_onedrive("~/OneDrive - Work/clark"))
        self.assertNotEqual(body["page"], body["message"])
        self.assertIn("Settings", body["message"])

    def test_the_good_choice_report_has_the_page_lines(self):
        status, body = self.service(str(self.good)).api_folder()
        self.assertTrue(all("page" in row for row in body["checks"]))

    def test_the_service_gives_the_page(self):
        self.assertEqual(self.service().page_html(), setup_page.html(on=pl.MAC))

    def test_the_default_prompt_stays_unset(self):
        self.assertIsNone(setup_mode.Setup(self.default).prompt)


if __name__ == "__main__":
    unittest.main()
