"""#1298 (Feedback tag): where the tag shows, the dialog's kind choice, the lines added automatically and the email text (logic/feedbackTag.js).

Run: python3 dev/run_tests.py test_feedback_tag_node
Quick tier: no browser. Bundled by the pinned esbuild and run in node (skipped when node is not on the machine).
The tag, the dialog's slide and the peek offset are drawn by edit/FeedbackTag.jsx and need a browser slot (see the row's status file).
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

ENTRY = ROOT / "tests" / "fixtures" / "feedbacktag_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}
ADDRESS = "".join(["al", "an.ma", "hon@inc", "eption42.ai"])  # as in logic/feedback.js


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ft.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=FT", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    return _BUNDLE["code"]


def call(expr):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(bundle() + ";\nconsole.log(JSON.stringify(%s));" % expr, encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


def shown(**kw):
    return call("FT.tagShown(%s)" % json.dumps(kw))


class Where(unittest.TestCase):
    def test_shown_in_every_settings_page(self):
        for page in ("", "projects", "people", "profile", "folder", "brand", "appearance", "reports", "backups", "data", "claude", "logs", "version"):
            self.assertTrue(shown(view="settings", page=page), page)

    def test_shown_in_help(self):
        self.assertTrue(shown(view="dashboard", helpOpen=True))

    def test_not_on_the_dashboard_lists_or_use_cases(self):
        for v in ("dashboard", "work", "usecases", "milestones", "published"):
            self.assertFalse(shown(view=v), v)

    def test_not_on_a_published_file(self):
        self.assertFalse(shown(view="settings", page="projects", fromFile=True))
        self.assertFalse(shown(view="dashboard", helpOpen=True, fromFile=True))

    def test_not_in_the_past_view(self):
        self.assertFalse(shown(view="settings", page="projects", past=True))


class Words(unittest.TestCase):
    def test_kinds_default_problem(self):
        self.assertEqual(call("FT.KINDS"), ["Problem", "Idea", "Question"])
        self.assertEqual(call("FT.DEFAULT_KIND"), "Problem")

    def test_no_contact_line_anywhere(self):
        self.assertNotIn("reach you", json.dumps(call("FT.TAG_LABELS")))
        self.assertNotIn("Contact", call("FT.emailText({kind:'Idea',message:'x'},{version:'1.3',platform:'macOS 14.5',page:'Help'})"))

    def test_context_lines_are_the_three_added(self):
        self.assertEqual(call("FT.contextLines({version:'1.3.0',platform:'macOS 14.5',page:'Settings, Appearance'})"),
                         ["Version of clark: 1.3.0", "System: macOS 14.5", "Page: Settings, Appearance"])

    def test_context_lines_unknowns(self):
        self.assertEqual(call("FT.contextLines({})"), ["Version of clark: unknown", "System: unknown", "Page: unknown"])

    def test_email_text_has_kind_words_then_exactly_the_lines(self):
        t = call("FT.emailText({kind:'Idea',message:'  more room  '},{version:'1',platform:'macOS',page:'Help'})")
        self.assertEqual(t, "Idea\n\nmore room\n\nVersion of clark: 1\nSystem: macOS\nPage: Help")

    def test_unknown_kind_falls_back_to_problem(self):
        self.assertTrue(call("FT.emailText({kind:'zzz',message:'a'},{})").startswith("Problem\n\n"))

    def test_mail_needs_words(self):
        r = call("FT.mail({kind:'Problem',message:' '},{})")
        self.assertEqual(r["href"], "")
        self.assertEqual(r["message"], "Write your feedback first.")

    def test_mail_link_goes_to_the_settings_address_with_the_kind_in_the_subject(self):
        r = call("FT.mail({kind:'Question',message:'why?'},{version:'1',platform:'macOS',page:'Help'})")
        self.assertTrue(r["href"].startswith("mailto:" + ADDRESS.replace("@", "%40")))
        self.assertIn("Feedback%20about%20clark", r["href"])
        self.assertIn("Question", r["href"])

    def test_copy_text_starts_with_address_and_subject(self):
        t = call("FT.copyText({kind:'Problem',message:'a'},{})")
        self.assertTrue(t.startswith("To: %s\nSubject: Feedback about clark (Problem)\n\nProblem\n\na" % ADDRESS))

    def test_page_words(self):
        self.assertEqual(call("FT.pageWords({view:'settings',page:'appearance'})"), "Settings, Appearance")
        self.assertEqual(call("FT.pageWords({view:'settings',page:''})"), "Settings, Projects")
        self.assertEqual(call("FT.pageWords({view:'dashboard',helpOpen:true})"), "Help and about")

    def test_macos_version_from_the_diagnostics_report(self):
        # Row 1298: the browser's user agent is frozen at 10.15.7, so the version comes from the server's System line, never from the user agent.
        ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit"
        rep = json.dumps("Diagnostics report\n\nVersion: 1\nSystem: macOS 14.5\nLogging: normal")
        self.assertEqual(call("FT.systemWords({userAgent:%s, platform:'MacIntel'}, %s)" % (json.dumps(ua), rep)), "macOS 14.5")
        self.assertEqual(call("FT.systemWords({userAgent:'x', platform:'Linux x86_64'}, %s)" % rep), "Linux x86_64")

    def test_macos_alone_when_the_call_failed_or_has_no_system_line(self):
        ua = json.dumps("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit")
        nav = "{userAgent:%s, platform:'MacIntel'}" % ua
        for rep in ("undefined", "null", "''", json.dumps("Diagnostics report\nVersion: 1"), json.dumps("System: Linux 6.1"), json.dumps("System: macOS"), json.dumps("System: macOS \nx")):
            self.assertEqual(call("FT.systemWords(%s, %s)" % (nav, rep)), "macOS", rep)

    def test_only_a_whole_system_line_counts_and_its_spaces_are_tidied(self):
        nav = "{userAgent:'x', platform:'MacIntel'}"      # the platform alone says Mac
        self.assertEqual(call("FT.systemWords(%s, 'Version: 1\\nSystem: macOS  14.5 \\nLogging: normal')" % nav), "macOS 14.5")
        for rep in ("a System: macOS 99", "System: 14.5", "System:macOS 14.5", "system: macOS 14.5", "System:  14.5"):
            self.assertEqual(call("FT.systemWords(%s, %s)" % (nav, json.dumps(rep))), "macOS", rep)

    def test_the_mail_carries_the_endpoint_value(self):
        nav = "{userAgent:'Mac OS X 10_15_7', platform:'MacIntel'}"
        ctx = "{version:'1', platform:FT.systemWords(%s, 'x\\nSystem: macOS 14.5\\ny'), page:'Help'}" % nav
        self.assertIn("System%3A%20macOS%2014.5", call("FT.mail({kind:'Idea',message:'hi'}, %s).href" % ctx))
        ctx = "{version:'1', platform:FT.systemWords(%s, null), page:'Help'}" % nav
        self.assertIn("System%3A%20macOS%0A", call("FT.mail({kind:'Idea',message:'hi'}, %s).href" % ctx))


class Killers(unittest.TestCase):
    """Row 1298 mutation round: tests for the mutants the first 16 left alive."""

    def test_context_values_are_one_line(self):
        c = call("FT.contextLines({version:'1\\n2',platform:'a\\nb',page:'c\\nd'})")
        self.assertEqual(len(c), 3)
        self.assertEqual(c, ["Version of clark: 1 2", "System: a b", "Page: c d"])

    def test_page_words_every_settings_page_name(self):
        names = {"people": "People", "profile": "Profile", "folder": "Folder", "brand": "Brand", "appearance": "Appearance", "reports": "Reports",
                 "backups": "Backups", "data": "Export and import", "claude": "Claude and AI", "logs": "Logs and diagnostics",
                 "version": "Version and updates", "projects": "Projects"}
        for k, v in names.items():
            self.assertEqual(call("FT.pageWords({view:'settings',page:'%s'})" % k), "Settings, " + v, k)

    def test_page_words_unknown_page_and_no_page(self):
        self.assertEqual(call("FT.pageWords({view:'settings',page:'zzz'})"), "Settings, zzz")
        self.assertEqual(call("FT.pageWords({view:'settings'})"), "Settings, Projects")
        self.assertEqual(call("FT.pageWords({view:'dashboard'})"), "dashboard")

    def test_help_wins_over_settings(self):
        self.assertEqual(call("FT.pageWords({view:'settings',page:'brand',helpOpen:true})"), "Help and about")

    def test_system_version_is_not_read_from_the_user_agent(self):
        # Replaces the two user-agent version tests: Row 1298 takes the version from the diagnostics System line only.
        for raw in ("14_5_1", "13_2", "10.15"):
            ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X %s) AppleWebKit" % raw
            self.assertEqual(call("FT.systemWords({userAgent:%s,platform:'MacIntel'})" % json.dumps(ua)), "macOS", raw)
        self.assertEqual(call("FT.systemWords({userAgent:'X Mac OS X 13_2 Y',platform:'Other'})"), "macOS")
        self.assertEqual(call("FT.systemWords({userAgent:'Mac OS X',platform:'Other'}, 'System: macOS 14.5.1')"), "macOS 14.5.1")

    def test_system_user_agent_data_platform_wins(self):
        self.assertEqual(call("FT.systemWords({userAgentData:{platform:'Windows'},platform:'Linux x86_64',userAgent:'x'})"), "Windows")

    def test_subject_uses_the_safe_kind(self):
        t = call("FT.copyText({kind:'zzz',message:'a'},{})")
        self.assertIn("Subject: Feedback about clark (Problem)\n", t)
        self.assertNotIn("zzz", t)

    def test_too_long_gives_no_link_and_words(self):
        r = call("FT.mail({kind:'Idea',message:'word '.repeat(5000)},{})")
        self.assertEqual(r["href"], "")
        self.assertEqual(r["message"], "This is too long for a mail link. Use Copy as text and paste it into an email.")
        self.assertNotEqual(r["message"], "Write your feedback first.")

    def test_copy_text_carries_the_context(self):
        t = call("FT.copyText({kind:'Idea',message:'a'},{version:'9.9',platform:'macOS 14.5',page:'Help and about'})")
        self.assertTrue(t.endswith("Version of clark: 9.9\nSystem: macOS 14.5\nPage: Help and about"))

    def test_dialog_words(self):
        L = call("FT.TAG_LABELS")
        self.assertEqual(L["tag"], "Feedback")
        self.assertEqual(L["kind"], "This is a")
        self.assertEqual(L["addedNote"], "Nothing from your reports is included.")
        self.assertIn("Nothing is sent by clark itself.", L["mailNote"])


if __name__ == "__main__":
    unittest.main()
