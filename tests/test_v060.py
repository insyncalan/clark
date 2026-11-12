"""clark 0.6's hand checks as tests: the 0.6 features that have merged to main. Each release gets a test_vNNN file, so the
walk-through keeps only the judgement and live-only checks.

Run: python3 dev/run_tests.py test_v060

Same shape as test_v050.
  COVERED       already covered by a test elsewhere. test_every_covering_test_named_here_exists fails if one goes missing.
  LIVE          Live: the real page in headless Chrome (a browser file, so it fails, never skips, without Chrome). Each test builds its
                own rig and shares nothing with another. Widths 1400 and 900.
  WAITING       the feature is not on main yet; its check is written when it lands. Skipped, with the question.
  WALK_THROUGH  judgement or live only, with the reason and the one line a person follows. Skipped: 'needs a person'.

NOT YET MERGED to origin/main on 02-11-2026 (so WAITING, no test): the #130 and #132 UX sweep fixes beyond the Publish spinner,
the tick and Publication N (timeline labels, the 12 px minimum; only widths 1400 and 900 are tested). #124 the PDF option and #153 the one filter line
are in the 0.6.0 train and are COVERED by their own tests. Merged and checked here: #120 numbered publications, #87 the design-system sizes (PR 240), #559 (PR 378), #495 (PR 363) and #570. The calendar (test_calendar_scales, #76) and the filter
line in test_filter_line are 0.4 features and are covered by test_v040, not here.
The cut checks (version, release notes, hand-check sheet) skip until the cut commit sets 0.6.0, then fail if they are wrong.
"""
import ast
import pathlib
import re
import sqlite3
import subprocess
import unittest
from pathlib import Path

from _paths import ROOT, SRC

TESTS = ROOT / "tests"
VERSION = "0.6.0"

# (item, the check a person would make by eye, the test that covers it: file::Class::test)
COVERED = [
    ("#120", "Each publish gets the project's next number, 1, 2, 3, and each project has its own count",
     "test_publication_numbers::TheCounter::test_the_numbers_run_1_2_3_for_a_project_and_each_project_has_its_own"),
    ("#120", "A Local-only publish and a Word copy take a number too",
     "test_publication_numbers::TheCounter::test_a_local_only_publish_and_a_word_copy_take_a_number_too"),
    ("#120", "Two publishes at once never take the same number",
     "test_publication_numbers::TheCounter::test_two_connections_publishing_at_once_never_take_one_number"),
    ("#120", "A publication cannot be deleted, changed or replaced",
     "test_publication_numbers::TheCounter::test_a_publication_cannot_be_deleted_changed_or_replaced"),
    ("#120", "Undo never frees a number", "test_publication_numbers::TheCounter::test_undo_never_frees_a_number"),
    ("#120", "A refused publish uses no number", "test_publication_numbers::TheCounter::test_a_refused_publication_uses_no_number"),
    ("#120", "An older file's publications are numbered per project by date, and none is lost",
     "test_publication_numbers::OlderFiles::test_a_version_9_file_is_numbered_per_project_by_date_then_seq_and_keeps_every_row"),
    ("#120", "A publish says its number in the file and in the reply",
     "test_publication_numbers::ThroughThePublisher::test_the_file_says_its_number_and_the_reply_names_it_for_a_local_only_publish"),
    ("#120", "A Preview is not numbered", "test_publication_numbers::ThroughThePublisher::test_a_preview_is_not_numbered_and_takes_no_number"),
    ("#120", "A lost race takes the new file back and puts the earlier one back",
     "test_publication_numbers::ThroughThePublisher::test_publish_publish_returns_the_number_and_takes_its_file_back_on_a_lost_race"),
    ("#120", "Each publish is one History line under All and under no other filter",
     "test_publication_numbers::TheHistoryLine::test_each_publish_is_one_line_in_all_and_in_no_other_filter"),
    ("#120", "A publish through the publisher adds its History line",
     "test_publication_numbers::TheHistoryLine::test_a_publish_through_the_publisher_adds_its_line"),
    ("#120", "The published file's foot reads Publication N and the date, and a Preview has none",
     "test_publication_footer::TheFooter::test_a_published_file_reads_publication_n_and_the_date"),
    ("#120", "A file with no date reads Publication N alone",
     "test_publication_footer::TheFooter::test_a_file_with_no_date_reads_publication_n_alone"),
    ("#120", "A Preview has no footer", "test_publication_footer::TheFooter::test_a_preview_has_no_footer"),
    ("#130", "Publishing shows a spinner and then a tick with the same words, Publication N",
     "test_publish_dialog::Dialog::test_C_publish_shows_a_spinner_while_it_works_then_a_tick_with_the_same_words"),
    ("#243", "A quoted password or secret is no longer taken for a placeholder, so it is refused",
     "test_secret_screen::Screen::test_the_words_password_and_secret_are_not_placeholders"),
    ("#243", "Placeholder, redacted and example still pass as placeholders",
     "test_secret_screen::Screen::test_placeholder_redacted_and_example_are_placeholders"),
    ("#320", "If the page cannot be read again after an Undo, the toast says to reload",
     "test_templates::Box::test_if_the_page_cannot_be_read_again_after_an_undo_the_toast_says_to_reload"),
    ("#242", "A short sk- key, a short api or access key value and 'API key:' with a space are refused; near misses pass",
     "test_secret_screen::Screen::test_short_sk_and_api_key_near_misses_pass"),
    ("#242", "Ask refuses the new short key shapes",
     "test_secret_screen::Screen::test_ask_refuses_the_new_short_shapes"),
    ("#297", "Preview refuses a section style clark does not have, in the words publish uses",
     "test_preview_export_route::Preview::test_a_junk_section_style_is_refused_in_the_words_publish_uses"),
    ("#299", "A provider's failure text that holds the private marker gives the plain refusal, not the text",
     "test_ask_canary::Canary::test_a_failure_whose_text_holds_the_canary_gives_the_plain_refusal"),
    ("#131", "The ten mild motions keep a static change marker with reduced motion",
     "test_motion::Rules::test_the_changed_mark_is_paint_only_and_adds_no_space"),
    ("#124", "Publishing offers a PDF option, unticked and never remembered",
     "test_publish_dialog::Dialog::test_C_pdf_tick_is_there_unticked_and_never_remembered"),
    ("#124", "The PDF is made with Chrome, saved beside the report (and in the client folder) and holds only what is published",
     "test_pdf::PublishRealChrome::test_the_pdf_holds_only_what_is_published"),
    ("#153", "Work items has one filter line (the '/' key focuses it)",
     "test_filter_line_page::Line::test_the_slash_key_focuses_the_line_but_not_while_typing_or_with_a_menu_open"),
    ("#153", "The published file draws the older filter bar and none of the filter line",
     "test_filter_line_not_published::NotPublished::test_the_published_file_draws_the_older_bar_and_no_line"),
]

# Live: the real page. Not repeated from COVERED; these are the checks a person would make in the app itself.
LIVE = [
    ("#120", "Two publishes from the dialog read Publication 1 and then Publication 2, and the second file's foot says 2 at both widths",
     "Live::test_two_publishes_say_publication_1_then_2_and_the_second_file_foot_says_2_at_1400_and_900"),
    ("#120", "Help tells a person that each publish, a local one too, gets a number", "Live::test_help_says_each_publish_gets_a_number"),
]

# Not on main yet: (item, check, the question or where it is being built).
WAITING = [
    ("#130", "The timeline labels never overlap, text is 12 px or more", "open; the rule is desktop only (1400 and 900), so ask before writing them"),
]

# (item, check, kind, why, what the person does)
WALK_THROUGH = [
    ("#120", "The footer and the Published line read well in the real file", "judgement",
     "only a person can say the footer is clear and the History line reads as meant",
     "Publish a demo project twice (Local only), open both files, read the foot; open History under All and read the two lines."),
]


def names_in(path):
    """{class name: {test method names}} in a test file, read without importing it."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {c.name: {f.name for f in c.body if isinstance(f, ast.FunctionDef)} for c in tree.body if isinstance(c, ast.ClassDef)}


class Tables(unittest.TestCase):
    def test_every_covering_test_named_here_exists(self):
        out = []
        for item, check, where in COVERED:
            name, cls, test = where.split("::")
            path = TESTS / (name + ".py")
            found = names_in(path) if path.is_file() else {}
            if test not in found.get(cls, ()):
                out.append(f"{item} {check}: {where}")
        self.assertEqual(out, [])

    def test_each_check_is_in_one_list_only_and_each_walk_through_check_says_why_and_what_to_do(self):
        checks = [c for _, c, _ in COVERED + WAITING] + [c for _, c, _, _, _ in WALK_THROUGH]
        self.assertEqual(sorted(c for c in set(checks) if checks.count(c) > 1), [])
        for item, check, kind, why, does in WALK_THROUGH:
            self.assertIn(kind, ("judgement", "live only"), check)
            self.assertTrue(why.strip() and does.strip(), check)

    def test_each_live_check_names_a_test_in_this_file(self):
        have = names_in(pathlib.Path(__file__)).get("Live", set())
        for item, check, where in LIVE:
            self.assertIn(where.split("::")[1], have, check)

    def test_each_waiting_check_carries_its_question(self):
        for item, check, question in WAITING:
            self.assertTrue(question.strip(), check)


class Cut(unittest.TestCase):
    """Release-cut checks that can be read from the tree. They skip until the cut commit has set the version."""

    def cut_made(self):
        text = (ROOT / "src" / "clark" / "__init__.py").read_text(encoding="utf-8")
        found = re.search(r'__version__\s*=\s*"([^"]+)"', text)
        if not found or found.group(1) != VERSION:            # 0.6.1 and later have their own test_vNNN
            self.skipTest(f"the cut commit is not made yet (version is {found.group(1) if found else 'unknown'}); "
                          f"it sets {VERSION} in src/clark/__init__.py")
        return found.group(1)

    def test_the_version_is_the_release(self):
        self.assertEqual(self.cut_made(), VERSION)

    def test_the_plain_release_notes_exist_and_name_the_version(self):
        v = self.cut_made()
        notes = ROOT / "dev" / "release-notes" / f"{v}-plain.md"
        self.assertTrue(notes.is_file(), "dev/release-notes/%s-plain.md" % v)
        self.assertIn(v, notes.read_text(encoding="utf-8"))

    def test_the_hand_check_sheet_exists(self):
        v = self.cut_made()
        self.assertTrue((ROOT / "dev" / "handchecks" / f"{v}-sheet.md").is_file())


def _skips_early():
    for i, (item, check, kind, why, does) in enumerate(WALK_THROUGH):
        def t(self, _m=f"needs a person ({kind}): {why}. Do this: {does}"):
            self.skipTest(_m)
        t.__name__ = "test_%s_%d_needs_a_person" % (re.sub(r"\W", "_", item), i)
        t.__doc__ = check
        setattr(WalkEarly, t.__name__, t)
    for i, (item, check, q) in enumerate(WAITING):
        def w(self, _m=f"waiting: {q}"):
            self.skipTest(_m)
        w.__name__ = "test_%s_%d_waiting" % (re.sub(r"\W", "_", item), i)
        w.__doc__ = check
        setattr(WalkEarly, w.__name__, w)


class WalkEarly(unittest.TestCase):
    """One skipped test per walk-through or waiting check, so the run lists them by name with the reason."""


_skips_early()

if __name__ == "__main__":
    unittest.main()


class Live(unittest.TestCase):
    """The real page in headless Chrome. Each test builds its own rig (the Publish dialog's, over a temporary folder)."""

    def test_two_publishes_say_publication_1_then_2_and_the_second_file_foot_says_2_at_1400_and_900(self):
        from test_page import navigate
        from test_publish import opened
        from test_publish_dialog import Pg
        from test_publish_route import Rig
        from test_server import chrome, wait
        rig = Rig(self)
        with chrome() as cdp:
            sid = navigate(cdp, rig.httpd.server_port, "#dashboard&p=PUB")
            p = Pg(self, cdp, sid)
            p.until("!!document.querySelector('#profile-btn')", "the profile circle is in the top bar")
            for want, name in ((1, "first.html"), (2, "second.html")):
                rig.save_to = rig.local / name
                p.open_publish()
                p.go()
                p.until("document.querySelector('[data-go]').classList.contains('ok')", "published")
                self.assertRegex(p.message(), r"^Published \(Publication %d\)\. Saved locally as " % want)
                p.go()
                p.until("!document.querySelector('#publish-dialog[open]')", "the dialog closed")
            for width in (1400, 900):
                sid2 = opened(cdp, (rig.local / "second.html").as_uri(), width)
                self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid2) == "1"))
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#publication-footer').length", sid2) == 1))
                foot = cdp.js("document.querySelector('#publication-footer').textContent", sid2)
                self.assertIn("Publication 2", foot, "at %d px" % width)
                self.assertNotIn("Publication 1", foot)
                self.assertEqual(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid2), True, "no sideways scroll at %d px" % width)

    def test_help_says_each_publish_gets_a_number(self):
        text = (SRC / "clark" / "page" / "src" / "help" / "helpContent.json").read_text(encoding="utf-8")
        self.assertIn("Published (Publication 3)", text)
        self.assertIn("Each publish, a local one too, gets the project\u2019s next number", text)


def _skips():
    for i, (item, check, kind, why, does) in enumerate(WALK_THROUGH):
        def t(self, _m=f"needs a person ({kind}): {why}. Do this: {does}"):
            self.skipTest(_m)
        t.__name__ = "test_%s_%d_needs_a_person" % (re.sub(r"\W", "_", item), i)
        t.__doc__ = check
        setattr(Walk, t.__name__, t)
    for i, (item, check, q) in enumerate(WAITING):
        def w(self, _m=f"waiting: {q}"):
            self.skipTest(_m)
        w.__name__ = "test_%s_%d_waiting" % (re.sub(r"\W", "_", item), i)
        w.__doc__ = check
        setattr(Walk, w.__name__, w)


class Walk(unittest.TestCase):
    """One skipped test per walk-through or waiting check, so the run lists them by name with the reason."""


_skips()


# ===== ROWS FROM OTHER TEAMS: extra rows (#131, #87, #559, #120, #495) =====

PAGE = SRC / "clark" / "page"
SHELL = PAGE / "shell.css"
TOKENS = SRC / "clark" / "brand" / "tokens.css"


def read(path):
    return Path(path).read_text(encoding="utf-8")


def pending(case, pr, path, marker):
    """Skip `case` while PR `pr` is not merged: its marker string is not yet in the file `path`."""
    path = Path(path)
    if not path.is_file() or marker not in read(path):
        case.skipTest(f"PENDING = 'PR {pr}': not merged yet (looking for {marker!r} in {path.name}); this row runs once it lands")


def block(css, opener):
    """The text of the first {...} block that starts at `opener` in `css`, braces balanced."""
    start = css.index(opener)
    depth, i = 0, css.index("{", start)
    for j in range(i, len(css)):
        depth += css[j] == "{"
        depth -= css[j] == "}"
        if depth == 0:
            return css[start:j + 1]
    raise AssertionError("unbalanced braces after " + opener)


def motion_block(css):
    """The Motion block: the @media (prefers-reduced-motion: no-preference) block that holds the m-glow animation."""
    opener, at = "@media (prefers-reduced-motion: no-preference)", 0
    while True:
        at = css.index(opener, at)
        found = block(css[at:], opener)
        if "m-glow" in found:
            return found
        at += len(opener)


def rule(css, selector):
    """The declarations of the first rule whose selector list is exactly `selector`, or None."""
    m = re.search(r"(?m)^\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", css)
    return m.group(1) if m else None


# --------------------------------------------------------------------------------------------------------------------
# #131 (PR 178): ten mild motions
# --------------------------------------------------------------------------------------------------------------------
class Motion131(unittest.TestCase):
    PENDING = "PR 178"
    MOTION = PAGE / "src" / "stores" / "motion.js"

    def need(self):
        pending(self, 178, self.MOTION, "export function reduced")

    def test_131_1_every_motion_sits_inside_the_reduced_motion_gate(self):
        self.need()
        css = read(SHELL)
        gate = motion_block(css)
        outside = css.replace(gate, "")
        self.assertIn(':root:not([data-motion="reduce"])', gate, "the gate also honours clark's own Reduce motion setting")
        self.assertEqual(re.findall(r"animation:\s*m-[a-z-]+", outside), [], "a motion animation outside the gate")
        self.assertEqual(re.findall(r"@keyframes\s+m-[a-z-]+", outside), [], "a motion keyframe outside the gate")
        self.assertIn("m-glow", gate)

    def test_131_2_the_handle_hint_is_per_page_load_and_stores_nothing(self):
        self.need()
        js = read(self.MOTION)
        for banned in ("localStorage", "sessionStorage", "indexedDB", "document.cookie", "fetch(", "XMLHttpRequest"):
            self.assertNotIn(banned, js, "the hint must not store or send anything")
        self.assertRegex(js, r"let [^;]*\barmed\b", "an in-memory flag, so the hint shows once per page load")
        self.assertIn("if (armed) return;", js)
        self.assertIn("nothing is stored", js)

    def test_131_3_the_changed_row_mark_is_a_static_tint_and_moves_in_no_way(self):
        self.need()
        css = read(SHELL)
        outside = css.replace(motion_block(css), "")
        for sel in (".sec.is-changed", "table.items tr.changed td", ".msl-row.changed"):
            body = rule(outside, sel)
            self.assertIsNotNone(body, sel + " has a plain rule outside the motion block")
            self.assertIn("var(--status-amber-tint)", body, sel)
            self.assertNotRegex(body, r"animation|transition|transform", sel + " is still")
        self.assertIn('"Changed"', read(PAGE / "src" / "stores" / "changed.js"), "the word, so colour and motion are not the only signal")


# --------------------------------------------------------------------------------------------------------------------
# #87 (PR 240, merged): the size scale
# --------------------------------------------------------------------------------------------------------------------
class Sizes87(unittest.TestCase):
    # px font sizes that are allowed in shell.css: the display figures and the older panels, each by the start of its selector.
    ALLOWED = (".tile .n", ".fig .v", ".tr-", "table.tracker", ".hp-", ".cp-m", ".ucp-body")

    def need(self):
        pending(self, 240, TOKENS, "--size-body: 15px")        # merged on main: always passes now, kept as a guard (row 843: the base text is 15 px)

    def test_87_1_the_size_scale_is_in_tokens_css(self):
        self.need()
        css = read(TOKENS)
        want = {"body": 15, "caption": 13, "small": 14, "h3": 20, "h2": 24, "h1": 30, "display": 40}
        for name, px in want.items():
            self.assertRegex(css, rf"--size-{name}:\s*{px}px", f"--size-{name} is {px}px")
        self.assertRegex(css, r"--leading:\s*1\.5")

    def test_87_2_no_px_font_size_is_left_in_shell_css_outside_the_allowed_list(self):
        self.need()
        left = []
        for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", re.sub(r"/\*.*?\*/", "", read(SHELL), flags=re.S)):
            selector, body = m.group(1).strip(), m.group(2)
            if re.search(r"font-size:\s*[0-9.]+px", body) and not any(s.lstrip(" @{}").startswith(self.ALLOWED) or
                                                                        any(part.strip().startswith(self.ALLOWED) for part in selector.split(",")) for s in [selector]):
                left.append(selector[-60:])
        self.assertEqual(left, [], "use var(--size-*) for these, or add the display figure to ALLOWED with a reason")

    def test_87_3_the_dialog_padding_is_on_the_space_token(self):
        self.need()
        css = read(SHELL)
        form = rule(css, ".dlg-form")
        self.assertIsNotNone(form)
        self.assertRegex(form, r"padding:\s*[^;]*var\(--space-5\)")
        self.assertRegex(rule(css, ".dlg-f"), r"gap:\s*var\(--space-2\)")
        self.assertIn("var(--size-caption)", rule(css, ".dlg-sub"))


# --------------------------------------------------------------------------------------------------------------------
# #559 (PR 378): no client report tab on the served page
# --------------------------------------------------------------------------------------------------------------------
class ServedTabs559(unittest.TestCase):
    REPORT = PAGE / "src" / "stores" / "report.js"

    def test_559_1_the_served_page_offers_no_clientreport_tab(self):
        js = read(self.REPORT)
        self.assertRegex(js, r"export const tabs = signal\(SERVED_TABS\)")
        self.assertNotIn("clientreport", js, "row 1065: the view is gone from the page's store")

    def test_559_2_a_published_file_has_no_weekly_snapshot(self):
        self.assertNotIn('tabs.append("clientreport")', read(SRC / "clark" / "publish.py"), "row 1065: a published file is given no such tab")
        self.assertNotIn("Weekly snapshot", read(self.REPORT))


# --------------------------------------------------------------------------------------------------------------------
# #120 (PR 165, merged): publication numbers
# --------------------------------------------------------------------------------------------------------------------
class Numbers120(unittest.TestCase):
    SHA = "a" * 64

    def test_120_1_the_three_triggers_exist_in_the_schema(self):
        schema = read(SRC / "clark" / "schema.sql")
        for name in ("publications_no_delete", "publications_number_fixed", "publications_never_replaced"):
            self.assertRegex(schema, rf"CREATE TRIGGER IF NOT EXISTS {name}\b", name)
        self.assertRegex(read(SRC / "clark" / "store.py"), r"SCHEMA_VERSION = 22\b")      # 22 since step 22 (row 875, use case owner); 21 was step 21 (row 1061, Planned 2026); 20 since step 20 (#944, projects.brand); 19 since step 19 (row 926, Gantt section type); 18 was step 18 (row 926, the Gantt lines); 17 was step 17 (row 811, client_action); 16 was step 16 (issue 709, use_cases.commitment); 15 was step 15 (#269, publications.pdf_name); 14 was #171 (review_after_days); 13 was #368 (a web page and its Word copy share a number); 12 was #325 (the trigger guards client_path); step 10 is this item\'s

    def test_120_2_a_number_is_fixed_and_never_reused(self):
        schema = read(SRC / "clark" / "schema.sql")
        con = sqlite3.connect(":memory:")
        self.addCleanup(con.close)
        con.executescript(schema)
        con.execute("PRAGMA foreign_keys = OFF")        # the project row is not the point here; the triggers are
        add = ("INSERT INTO publications (project, local_path, file_sha256, checks, by_user, number) "
               "VALUES ('ABC', '/x/y.html', ?, 'not needed', 'u', ?)")
        con.execute(add, (self.SHA, 1))
        for sql in ("UPDATE publications SET number = 9", "DELETE FROM publications"):
            with self.assertRaises(sqlite3.DatabaseError, msg=sql):
                con.execute(sql)
        with self.assertRaises(sqlite3.DatabaseError, msg="the same number again"):
            con.execute(add, (self.SHA, 1))
        with self.assertRaises(sqlite3.DatabaseError, msg="REPLACE"):
            con.execute(add.replace("INSERT", "INSERT OR REPLACE"), (self.SHA, 1))
        con.execute(add, (self.SHA, 2))
        self.assertEqual([r[0] for r in con.execute("SELECT number FROM publications ORDER BY seq")], [1, 2])

    def test_120_3_the_footer_text_is_in_the_page_and_the_published_file_carries_the_number(self):
        app = read(PAGE / "src" / "components" / "App.jsx")
        self.assertIn('id="publication-footer"', app)
        self.assertIn("Publication {publication.value}", app)
        self.assertNotIn("View only.", app)   # row 785
        self.assertIn("Published ${plainDate(asAt.value)}. ", app)
        self.assertIn('block["publication"] = {"n": number}', read(SRC / "clark" / "publish.py"))
        self.assertIn(".pubfoot", read(SHELL))


# --------------------------------------------------------------------------------------------------------------------
# #495 (PR 363): the generated pages are built, not committed
# --------------------------------------------------------------------------------------------------------------------
class GeneratedPages495(unittest.TestCase):
    PAGES = ("src/clark/page/page.html", "src/clark/page/page-view.html")
    INIT = PAGE / "__init__.py"

    def need(self):
        pending(self, 363, self.INIT, "def ensure_built")

    def test_495_1_the_pages_are_not_tracked_and_gitignore_lists_them(self):
        self.need()
        ignore = read(ROOT / ".gitignore").splitlines()
        for p in self.PAGES:
            self.assertIn(p, ignore, p + " is in .gitignore")
        try:
            tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", *self.PAGES], capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            self.skipTest("git is not available here; the .gitignore lines above were checked")
        if tracked.returncode != 0:
            self.skipTest("this is not a git checkout; the .gitignore lines above were checked")
        self.assertEqual(tracked.stdout.strip(), "", "git must not track a generated page")

    def test_495_2_package_py_refuses_a_missing_page(self):
        self.need()
        pkg = read(ROOT / "dev" / "tools" / "package.py")
        self.assertIn("GENERATED_PAGES", pkg)
        for p in self.PAGES:
            self.assertIn(p, pkg)
        self.assertIn("has not been built", pkg)
        self.assertGreaterEqual(pkg.count("raise Refused(f\"A page the download needs has not been built"), 1)
        self.assertRegex(pkg, r"make_pages\(root, twice=release\)", "a release builds twice and compares the bytes")

    def test_495_3_ensure_built_builds_under_a_lock_and_checks_again_inside_it(self):
        self.need()
        src = read(self.INIT)
        self.assertIn("class _file_lock", src)
        self.assertIn("fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)", src, "the wait is bounded: it polls")
        self.assertIn("LOCK_WAIT", src)
        self.assertIn("_build_lock = threading.Lock()", src)
        body = src[src.index("def ensure_built"):]
        body = body[:body.index("DEMO_OPEN")]
        lock_at = body.index("with _build_lock, _file_lock():")
        self.assertIn("_checked", body[lock_at:], "the check is made again inside the locks")
        self.assertIn("source_stamp()", body[lock_at:])
        self.assertIn("os.replace(tmp, STAMP)", body, "the stamp is swapped in whole")
        self.assertIn("ensure_built()", src[src.index("def page_html"):], "the server's page goes through it")


# --------------------------------------------------------------------------------------------------------------------
# #570: Friday is the week end everywhere (non-browser rows; each skips until its marker is in the source)
# --------------------------------------------------------------------------------------------------------------------
class Friday570(unittest.TestCase):
    CHANGES = SRC / "clark" / "changes.py"
    BOARD = PAGE / "src" / "logic" / "board.js"
    HELP = PAGE / "src" / "help" / "helpContent.json"
    DEMO = ROOT / "dev" / "demo_data.py"

    def test_570_1_changes_refuses_a_week_ending_that_is_not_a_friday_and_takes_a_friday(self):
        pending(self, 570, self.CHANGES, "NOT_FRIDAY")
        import sys
        sys.path.insert(0, str(TESTS))
        from _demo import USER, DemoStore
        from clark import changes
        demo = DemoStore()
        self.addCleanup(demo.close)
        change = changes.make_change(demo.store.path, [], USER)
        req = lambda day: {"project": "ABC", "kind": "projects", "op": "update", "changes": {"week_ending": day}}      # noqa: E731
        for day, friday in (("2026-11-02", "06-11-2026"), ("2026-11-07", "13-11-2026"), ("2026-11-08", "13-11-2026")):
            status, body = change(req(day))
            self.assertEqual((status, body["ok"], body["message"]), (400, False, f"Week ending is a Friday. Pick Friday {friday}."), day)
        status, body = change(req("2026-11-06"))
        self.assertEqual((status, body.get("message")), (200, None), body)
        self.assertEqual(demo.store.read("projects", ref="ABC")["week_ending"], "2026-11-06")

    def test_570_2_board_js_ends_the_week_on_a_friday_and_no_longer_uses_sundayOf(self):
        pending(self, 570, self.BOARD, "fridayOnOrAfter")
        src = read(self.BOARD)
        self.assertRegex(src, r"export const weekEndOf\b")
        self.assertRegex(src, r"export const fridayOnOrAfter\b")
        for name in ("function bucketOf(", "function dueHalf("):
            at = src.index(name)
            body = src[at:at + 1000]
            self.assertIn("fridayOnOrAfter", body, name)
            self.assertNotIn("sundayOf", body, name)
        self.assertNotIn("sundayOf", src)

    def test_570_3_the_demo_projects_week_ending_is_a_friday_on_any_clock(self):
        pending(self, 570, self.DEMO, "friday_on_or_before")
        import importlib.util, tempfile
        from datetime import datetime, timedelta
        spec = importlib.util.spec_from_file_location("demo_data_570", str(self.DEMO))
        demo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(demo)
        for days in range(7):
            now = datetime(2026, 10, 28, 9, 0) + timedelta(days=days)
            with tempfile.TemporaryDirectory(prefix="clark-570-") as tmp:
                out = Path(tmp) / "clark.db"
                demo.build(out, now, onedrive_roots=[])
                con = sqlite3.connect(str(out))
                try:
                    weeks = [r[0] for r in con.execute("SELECT week_ending FROM projects")]
                finally:
                    con.close()
            self.assertTrue(weeks)
            for w in weeks:
                self.assertEqual(datetime.strptime(w, "%Y-%m-%d").weekday(), 4, f"{w} on {now.date()}")

    def test_570_4_help_says_the_week_ends_on_a_friday(self):
        pending(self, 570, self.HELP, "must be a Friday")
        text = read(self.HELP)
        self.assertIn("The week ends on a Friday, everywhere.", text)
        self.assertIn("**Week ending** must be a Friday", text)
        self.assertIn("on a Saturday or Sunday it runs to the coming Friday", text)


# --------------------------------------------------------------------------------------------------------------------
# What needs a person. Skipped, with the reason and what to do.
# --------------------------------------------------------------------------------------------------------------------
EXTRA_WALK_THROUGH = [
    ("131.4", "judgement", "only an eye can tell the motions are mild and help rather than distract",
     "In Edit change a heading and press Undo; press Add and open the Add dialog, then close it; switch from Dashboard to Work items and back. Then turn on Reduce motion (the Mac's or clark's own) and repeat: nothing moves."),
    ("131.5", "judgement", "whether the handle hint reads well and goes at the next press",
     "Reload and press Edit: the first handle pulses once beside the words Drag to move, + to add a template; press any key and the words go; reload, press Edit and they come back once."),
    ("87.4", "judgement", "whether the sizes look like one scale at both widths",
     "Open Dashboard, Work items and the Publish dialog at 1400 px, then at 900 px, in light and dark: body 16, small labels 14 or 13, headings clearly stepped, nothing under 13."),
    ("120.4", "live only", "the footer must be seen in a real file opened from disk",
     "Publish twice, open each file from its folder and read the foot: Publication 1 and Publication 2, each with its date once."),
    ("495.4", "live only", "a fresh checkout and a downloaded zip are the only places the build can truly be proved",
     "Clone fresh into an empty folder and run python3 -m clark --demo --open: the first start builds the pages. Unzip a release into another empty folder and run the same: no bundler runs."),
    ("570.5", "judgement", "whether a Saturday or Sunday 'This week' running to the coming Friday is what a person expects (an open question)",
     "On a Saturday or Sunday (set CLARK_NOW) open Work items: This week runs from today to the coming Friday. Say whether you would rather it ran to the Friday just gone, or to Sunday."),
]


class WalkExtra(unittest.TestCase):
    """One skipped test per walk-through row, so the run lists them by name with the reason."""


def _walk():
    for row, kind, why, does in EXTRA_WALK_THROUGH:
        def t(self, _m=f"needs a person ({kind}): {why}. Do this: {does}"):
            self.skipTest(_m)
        t.__name__ = "test_%s_needs_a_person" % row.replace(".", "_")
        setattr(WalkExtra, t.__name__, t)


_walk()

if __name__ == "__main__":
    unittest.main()
