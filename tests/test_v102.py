"""clark 1.0.2's hand checks as tests: the 1.0.2 items that have merged to main after 1.0.1. Each release gets a test_vNNN file, so the
walk-through keeps only the judgement and live-only checks.

Run: python3 dev/run_tests.py test_v102

Same shape as test_v101.
  COVERED       already covered by a test elsewhere. test_every_covering_test_named_here_exists fails if one goes missing.
  WAITING       the feature is not on main yet (a pull request is open, or none yet); each row names its pull request and a marker
                in the source that appears when it lands. Skipped, with the pull request. When the cut commit has set the version
                and a marker is there, the row fails until it is moved to COVERED with its test, so a landed change is never
                forgotten at the cut.
  WALK_THROUGH  judgement or live only, with the reason and the one line a person follows. Skipped: 'needs a person'.

Written after 1.0.1 was published (tag v1.0.1): everything merged after the tag, and a WAITING row for every other 1.0.2 row
that a customer sees. The cut checks (version, release notes, hand-check sheet, DRAFT lines) skip until the cut commit sets 1.0.2,
then fail if wrong. The notes' own rules (title with (Beta), the Beta line, plain words) are read from the tree now.

The data layout does not change in 1.0.2 (layout 16 stays): the notes say so and the store must still say 16.
"""
import ast
import re
import unittest

from _paths import ROOT

TESTS = ROOT / "tests"
VERSION = "1.0.2"
SCHEMA = 16              # 1.0.1 moved to layout 16; 1.0.2 does not change it

# (item, the check a person would make by eye, the test that covers it: file::Class::test)
COVERED = [
    ("#753", "In the Use cases list and on a use case the show-on-report choice is the eye alone, its words are the tooltip.",
     "test_use_cases_list::List::test_the_eye_is_an_icon_alone_with_a_tooltip_and_never_meets_the_commitment_chip"),
    ("#753", "On a use case the eye is one button with its words and toggles with one Undo.",
     "test_use_case_detail::Detail::test_the_eye_is_one_button_with_its_words_and_toggles_with_one_undo"),
    ("#729", "ask clark can change a use case's status, headline and Where it stands, in one step with one Undo.",
     "test_ask_use_cases::UseCaseChanges::test_a_status_headline_and_standing_change_is_applied_once_and_undone_in_one_step"),
    ("#729", "ask clark reads the Commitment flag but a change to it is refused.",
     "test_ask_use_cases::UseCaseChanges::test_the_model_may_read_the_commitment_flag_but_a_proposal_to_change_it_is_refused"),
    ("#729", "The change card shows a use case change in plain words and applies with Undo.",
     "test_ask_change_page::TheCard::test_a_use_case_change_shows_in_plain_words_and_applies_with_undo"),
    ("#735", "With no branding folder the Excel Cover shows clark's own icon.",
     "test_excel_cover_brand::LogoRule::test_a_no_folder_shows_clarks_own_logo"),
    ("#735", "A branding folder with no logo gives a Cover with no logo, never clark's mark.",
     "test_excel_cover_brand::LogoRule::test_c_a_folder_without_a_logo_has_no_logo_and_not_clarks_mark"),
    ("#735", "A logo that resolves to outside the branding folder is never read.",
     "test_excel_cover_brand::LogoRule::test_d_a_symlink_to_a_logo_outside_the_folder_is_never_read"),
    ("#735", "The brand's cover picture sits in a row of its own under the subtitle.",
     "test_excel_cover_brand::Wave::test_e_a_cover_picture_is_drawn_below_the_subtitle"),
    ("#735", "The Cover title is larger and the band has a distinct edge.",
     "test_excel_cover_brand::Band::test_f_the_title_is_larger_and_the_band_has_a_distinct_edge"),
    ("#735", "The Cover subtitle gives the week ending as a long date.",
     "test_excel_cover_brand::Band::test_f_the_subtitle_has_the_long_date"),
    ("#758", "The Remove demo data box opens below the top bar at every width in light and dark.",
     "test_demo_dialog_place::DemoDialogPlace::test_the_dialog_starts_below_the_top_bar_at_every_width_in_light_and_dark"),
    ("#756", "E and V do not move the section being read, at every width in light and dark.",
     "test_e_key_no_shift::Walk::test_e_and_v_move_nothing_at_every_width_in_light_and_dark"),
    ("#725", "The top bar actions look as before after the colours moved to tokens, and a stale answer to the asking switch is ignored.",
     "test_ask_settings::Settings::test_a_change_answered_after_a_newer_read_was_started_does_not_touch_the_switch"),
    ("#719", "START-HERE says to double-click clark.command.",
     "test_package::MacZipTest::test_start_here_says_what_is_in_the_folder_and_how_to_swap_an_old_clark"),
    ("#744", "The usage line of the launcher shows the command the person typed.",
     "test_typed::UsageLine::test_launch_help_in_both_modes"),
    ("#745", "/health says the version clark is running, and no path.",
     "test_server::Health::test_health_says_the_version_it_runs"),
    ("#743", "clark.command tells every run to write no bytecode.",
     "test_launcher::Command::test_every_run_is_told_to_write_no_bytecode_so_no_pycache_folder_appears_in_the_clark_folder"),
    ("#616", "A report that cannot be put back under its name says it is still in the folder under a hidden name.",
     "test_publication_numbers::ThroughThePublisher::test_a_link_that_cannot_be_put_back_is_said_plainly"),
    ("#610", "A live document left out of the published file is logged by its ID only.",
     "test_documents_published::Absent::test_a_live_document_left_out_for_its_link_is_logged_by_id_only_and_the_file_is_unchanged_issue_610"),
    ("#723", "A held workbook with no check goes before a plan waiting for Apply.",
     "test_excel_sheet_followups::Followups::test_a_new_workbook_pushes_out_a_held_file_before_a_plan_waiting_for_apply"),
    ("#737", "A sheet over the row limit is listed as more than 2,000 rows and ticking it is refused in words.",
     "test_excel_sheet_listing::Listing::test_every_sheet_over_2000_rows_is_listed_as_over_the_limit_and_ticking_it_is_refused"),
    ("#759", "Line 1 of START-HERE in a public download no longer says repository.",
     "test_package::DefaultAudienceTest::test_the_public_line_one_is_the_ruled_sentence_and_never_says_repository"),
    ("#754", "In Help the slash goes to the search box, and the ask key leaves Help alone.",
     "test_help_pr_a::SlashInHelp::test_help_says_what_slash_does_in_help_with_its_condition_and_without_the_switch_name"),
    ("#697", "The Settings links are a list down the left above 900 px and a row of chips at 900 px and narrower.",
     "test_settings_head::Head::test_C_the_list_is_at_the_left_at_1400_and_900"),
    ("#742", "The daily log follows --data: it is in the logs folder inside the data folder.",
     "test_log_follows_data::Started::test_data_given_writes_inside_it_and_nothing_under_the_home"),
    ("#760", "A folder of mixed versions is refused with a plain message.",
     "test_mixed_folder::Folder::test_one_older_file_is_refused"),
    ("#763", "A brand's own circle picture no longer stops Preview and Publish.",
     "test_brand_circle::Route::test_publish_and_preview_pass_with_the_circle"),
    ("#763", "An outside address in the brand file shows its own sentence on Publish and Preview.",
     "test_brand_circle::Route::test_an_address_shows_its_own_sentence_on_publish_and_preview"),
    ("#763", "A picture in another form shows its own sentence on Publish and Preview.",
     "test_brand_circle::Route::test_another_picture_shows_its_own_sentence_on_publish_and_preview"),
    ("#763", "The two brand refusal sentences are the approved words.",
     "test_page_words::Words::test_a_brand_link_refusal_does_not_contradict_itself"),
    ("#761", "The three public meet clark files are the regenerated ones, pinned by hash and size.",
     "test_ci_scan::PinnedPublicFiles::test_the_next_pins_are_well_formed_and_each_real_file_is_its_current_or_its_next_pin"),
    ("#761", "The public zip carries the meet clark folder at the top under its own name.",
     "test_extra_folder::Build::test_each_folder_is_at_the_top_under_its_own_name"),
]

# Not on main yet: (item, check, pull request, a file under the top folder and the text that is in it once the pull request has
# landed; marker None means there is no pull request to look for yet).
WAITING = []

# (item, check, kind, why, what the person does)
WALK_THROUGH = [
    ("#729", "A real answer from a connected AI proposes a change to a use case (live only).",
     "live only", "it needs a connected Claude or ChatGPT and a real answer",
     "in Edit ask clark to set a use case's status and headline, and see the change card, Apply and Undo"),
]

# "apply" is not banned here: the card's button is called Apply, and the notes must name it.
BANNED_WORDS = ("applied", "staged", "proposal", "sweep", "tracker", "vault", "extract", "refused")

DRAFT = re.compile(r"(?m)^<!-- DRAFT: waits for (.+?) -->$")


def names_in(path):
    """{class name: {test method names}} in a test file, read without importing it."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {c.name: {f.name for f in c.body if isinstance(f, ast.FunctionDef)} for c in tree.body if isinstance(c, ast.ClassDef)}


def version():
    found = re.search(r'__version__\s*=\s*"([^"]+)"', (ROOT / "src" / "clark" / "__init__.py").read_text(encoding="utf-8"))
    return found.group(1) if found else None


def schema_version():
    found = re.search(r"(?m)^SCHEMA_VERSION\s*=\s*(\d+)", (ROOT / "src" / "clark" / "store.py").read_text(encoding="utf-8"))
    return int(found.group(1)) if found else None


def landed(path, marker):
    """True when the file exists and holds the marker; None for a row with no marker (no pull request yet)."""
    if marker is None:
        return None
    p = ROOT / path
    return p.is_file() and marker.encode("utf-8") in p.read_bytes()


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
        checks = [c for _, c, _ in COVERED] + [c for _, c, *_ in WAITING] + [c for _, c, _, _, _ in WALK_THROUGH]
        self.assertEqual(sorted(c for c in set(checks) if checks.count(c) > 1), [])
        for item, check, kind, why, does in WALK_THROUGH:
            self.assertIn(kind, ("judgement", "live only"), check)
            self.assertTrue(why.strip() and does.strip(), check)

    def test_each_waiting_check_names_its_pull_request_or_says_there_is_none(self):
        for item, check, pr, path, marker in WAITING:
            self.assertRegex(pr, r"^(PR \d+|no pull request yet \((issue \d+|branch [\w-]+)\))$", check)
            self.assertEqual(marker is None, pr.startswith("no pull request"), check)

    def test_the_sheet_has_a_row_for_every_waiting_pull_request_and_every_covered_item(self):
        sheet = (ROOT / "dev" / "handchecks" / (VERSION + "-sheet.md")).read_text(encoding="utf-8")
        for item, check, pr, path, marker in WAITING:
            self.assertIn("WAITING " + pr, sheet, check)
            self.assertIn(item, sheet, check)
        for item in {i for i, _, _ in COVERED}:
            self.assertIn(item, sheet, f"{item} has no row on the hand-check sheet")


class Notes(unittest.TestCase):
    """The notes' own rules, read from the tree now (the same for every release): a title that says Beta, the Beta line, plain words,
    no lower-case 'ask clark' in a heading, no date in year-first form, and one DRAFT comment for each WAITING row."""

    def setUp(self):
        self.text = (ROOT / "dev" / "release-notes" / (VERSION + "-plain.md")).read_text(encoding="utf-8")

    def test_the_title_the_beta_line_and_the_update_sentence(self):
        self.assertEqual(self.text.splitlines()[0], f"# clark {VERSION} (Beta), Mac")
        self.assertIn("Beta", self.text)
        self.assertIn("This is the 1.0 build. It is still marked Beta because updating from inside clark is not switched on yet.", self.text)
        self.assertIn("Updating from inside clark is not switched on yet: install a new version by downloading it and replacing the old one.", self.text)

    def test_no_banned_word_and_no_lower_case_ask_clark_in_a_heading(self):
        for word in BANNED_WORDS:
            self.assertIsNone(re.search(r"(?i)\b%s\b" % word, self.text), word)
        for line in self.text.splitlines():
            if line.startswith("#"):
                self.assertNotIn("ask clark", line)

    def test_the_notes_say_the_data_layout_is_unchanged_and_carry_no_layout_step(self):
        self.assertIn("This version does not change how clark stores your data.", self.text)
        self.assertNotIn("Read this first", self.text)
        self.assertNotIn("Step 17", self.text)

    def test_the_known_limits_carry_the_by_hand_install_and_the_demo_limit(self):
        self.assertIn("## Known limits", self.text)
        self.assertIn("rename the old clark folder first", self.text)
        self.assertIn("Editing a demo project keeps it", self.text)

    def test_a_date_in_the_notes_is_day_first_and_no_one_is_named(self):
        self.assertIsNone(re.search(r"\b\d{4}-\d\d-\d\d\b", self.text), "a date in the notes is DD-MM-YYYY")
        self.assertNotRegex(self.text, r"team-[a-z]+-\d+", "a branch name is in the notes")

    def test_each_waiting_row_has_one_draft_comment_and_nothing_else_does(self):
        found = sorted(DRAFT.findall(self.text))
        self.assertEqual(found, sorted(pr for _, _, pr, _, _ in WAITING))
        self.assertEqual(self.text.count("<!-- DRAFT: "), len(WAITING), "a DRAFT comment not on a line of its own")


class Cut(unittest.TestCase):
    """Release-cut checks that could be read from the tree. They are RETIRED: 1.0.2 is published (tag v1.0.2), and main moves on to
    1.0.3 (a new data layout may land on main before the 1.0.3 cut commit sets its version), so a check of the live tree against
    1.0.2 would fail for a reason that is not a 1.0.2 fault. The published 1.0.2 files are fixed by the tag; the notes' own rules
    (class Notes) and the COVERED rows (class Tables) still run."""

    def cut_made(self):
        self.skipTest("1.0.2 is published (tag v1.0.2): the cut checks are retired; the tag holds the 1.0.2 tree")

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

    def test_the_data_layout_is_still_the_one_the_notes_say(self):
        self.cut_made()
        self.assertEqual(schema_version(), SCHEMA, "the notes say the data layout is unchanged")

    def test_a_waiting_row_whose_pull_request_has_landed_has_been_moved_to_covered(self):
        self.cut_made()
        out = [f"{item} {pr}: it is in main now; give it a covering test in COVERED, a line in the notes and a row in the sheet"
               for item, check, pr, path, marker in WAITING if landed(path, marker)]
        self.assertEqual(out, [])


def _skips():
    for i, (item, check, kind, why, does) in enumerate(WALK_THROUGH):
        def t(self, _m=f"needs a person ({kind}): {why}. Do this: {does}"):
            self.skipTest(_m)
        t.__name__ = "test_%s_%d_needs_a_person" % (re.sub(r"\W", "_", item), i)
        t.__doc__ = check
        setattr(Walk, t.__name__, t)
    for i, (item, check, pr, path, marker) in enumerate(WAITING):
        def w(self, _m=f"PENDING = '{pr}': not merged yet; this row runs once it lands and the cut commit is made"):
            self.skipTest(_m)
        w.__name__ = "test_%s_%d_waiting" % (re.sub(r"\W", "_", item), i)
        w.__doc__ = check
        setattr(Walk, w.__name__, w)


class Walk(unittest.TestCase):
    """One skipped test per walk-through or waiting check, so the run lists them by name with the reason."""


_skips()

if __name__ == "__main__":
    unittest.main()
