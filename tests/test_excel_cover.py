"""#85b, the pure part: the lines of the workbook's Cover sheet (clark.excel_cover). Fictional data only.

Run: python3 dev/run_tests.py test_excel_cover
"""
import os
import shutil
import sqlite3
import tempfile
import time
import unittest
import zipfile
from unittest import mock
from pathlib import Path

import _paths  # noqa: F401  (puts src/ and vendor/ on the path)
from _demo import USER, DemoStore
from openpyxl import Workbook, load_workbook

from clark import excel
from clark import excel_colours as colours
from clark import excel_cover as cover
from clark import excel_import as xi
from clark import look
from clark import page

FIXED_ID = "0123456789ab4def8123456789abcdef"     # an export id held still, so two exports can be compared byte for byte


_NO_BRAND = tempfile.mkdtemp(prefix="clark-no-brand-")    # a brand logo on this computer never changes a test (#133)


def setUpModule():
    global _OLD_BRANDING
    _OLD_BRANDING, page.BRANDING = page.BRANDING, Path(_NO_BRAND)


def tearDownModule():
    page.BRANDING = _OLD_BRANDING
    shutil.rmtree(_NO_BRAND, ignore_errors=True)


PROJECT = {"code": "DEMO", "name": "Harbour Lights upgrade", "current_state": "<p>Phase two is under way.</p><ul><li>Cabling done</li><li>Testing next</li></ul>",
           "internal_notes": "CANARY-INTERNAL-NOTE", "health_reason": "CANARY-PROJECT-FIELD"}
SECTIONS = [
    {"id": "s1", "type": "current", "title": "Current state", "body": "", "hidden": 0},
    {"id": "s2", "type": "glance", "title": "At a glance", "body": "", "hidden": 0},
    {"id": "s3", "type": "text", "title": "Summary", "body": "<p>On course for the spring opening.</p>", "hidden": 0},
    {"id": "s4", "type": "text", "title": "This week", "body": "<p>Lights tested on the east pier.</p>", "hidden": 0},
    {"id": "s5", "type": "text", "title": "Hidden section", "body": "<p>CANARY-HIDDEN-SECTION</p>", "hidden": 1},
    {"id": "s6", "type": "raid", "title": "Risks and issues", "body": "", "hidden": 0},
]
TILES = [
    {"tile": "health", "title": "Project health", "value": "On track", "detail": "", "reason": "Dates hold.", "hidden": False,
     "pill": {"colour": "green"}},
    {"tile": "overdue", "title": "Overdue actions", "value": 3, "detail": "", "hidden": False},
    {"tile": "risks", "title": "High risks and issues", "value": 1, "detail": "of 4 open", "hidden": False},
    {"tile": "decisions", "title": "CANARY-HIDDEN-TILE", "value": 9, "detail": "", "hidden": True},
]
STAMP = "01-06-2030 20:30 (UTC+04:00)"


def build(**kw):
    args = dict(project=PROJECT, sections=SECTIONS, tiles=TILES, exported=STAMP, by="Sam Example", owner="Kim Example",
                email="kim.example@example.com", internal="INTERNAL: never share this with a client.")
    args.update(kw)
    return cover.lines(**args)


def pin_timezone(case, zone="Asia/Dubai"):
    """Pin the local zone for the test (the exported time is local), and put it back afterwards."""
    old = os.environ.get("TZ")

    def restore():
        if old is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old
        time.tzset()
    os.environ["TZ"] = zone
    time.tzset()
    case.addCleanup(restore)


def texts(lines):
    return [x["text"] for x in lines]


class TheLines(unittest.TestCase):
    def test_order_title_then_the_sections_then_the_about_block(self):
        got = build()
        self.assertEqual(got[0], {"kind": "title", "text": "Harbour Lights upgrade", "tag": "INTERNAL"})
        headings = [x["text"] for x in got if x["kind"] == "heading"]
        self.assertEqual(headings, ["Current state", "At a glance", "Summary", "This week"])      # the sections' own order
        i = [x["kind"] for x in got].index("about")
        self.assertEqual([x["kind"] for x in got][i:], ["about", "exported", "caution", "return", "where", "ids", "locked"])
        self.assertEqual(got[i]["text"], "About this export")
        self.assertEqual(got[i + 1]["text"], "01-06-2030 20:30 (UTC+04:00) by Sam Example")
        self.assertEqual(got[-1]["kind"], "locked", "the red Internal line is gone from the bottom: the title tag says it")
        self.assertNotIn("never share this with a client", "\n".join(texts(got)))

    def test_the_tag_is_just_internal_and_no_note_means_no_tag(self):
        self.assertEqual(build()[0]["tag"], "INTERNAL")
        got = build(internal="")
        self.assertNotIn("tag", got[0])
        self.assertNotIn("internal", [x["kind"] for x in got])

    def test_the_subtitle_has_the_week_and_the_client_as_the_page_band_shows_them(self):
        project = {**PROJECT, "week_ending": "2026-10-23", "client_name": "Example Client"}
        self.assertEqual(build(project=project)[1], {"kind": "subtitle", "text": "Weekly report · Week ending Friday 23 October 2026 · for Example Client"})

    def test_the_subtitle_leaves_out_a_part_with_no_data(self):
        self.assertEqual(build(project={**PROJECT, "week_ending": "2026-10-23"})[1]["text"], "Weekly report · Week ending Friday 23 October 2026")
        self.assertEqual(build(project={**PROJECT, "client_name": " Example Client "})[1]["text"], "Weekly report · for Example Client")
        self.assertEqual(build()[1]["text"], "Weekly report")
        self.assertEqual(build(project={**PROJECT, "week_ending": "", "client_name": None})[1]["text"], "Weekly report")

    def test_this_week_and_next_week_are_one_side_by_side_pair_when_both_have_words(self):
        secs = SECTIONS[:4] + [{"id": "s7", "type": "text", "title": "Next week", "body": "<p>Hand over.</p>", "hidden": 0}]
        got = build(sections=secs)
        pair = [x for x in got if x["kind"] == "pair"]
        self.assertEqual(len(pair), 1)
        self.assertEqual((pair[0]["left"]["title"], pair[0]["left"]["text"]), ("This week", "Lights tested on the east pier."))
        self.assertEqual((pair[0]["right"]["title"], pair[0]["right"]["text"]), ("Next week", "Hand over."))
        self.assertNotIn("Next week", [x["text"] for x in got if x["kind"] == "heading"])

    def test_a_next_week_with_no_words_leaves_this_week_as_an_ordinary_section(self):
        secs = [{"type": "text", "title": "This week", "body": "<p>Done.</p>"}, {"type": "text", "title": "Next week", "body": "<p> </p>"}]
        got = build(sections=secs)
        self.assertEqual([x["kind"] for x in got if x["kind"] in ("pair", "heading")], ["heading"])

    def test_empty_sections_are_left_off_heading_and_all(self):
        secs = [{"type": "current", "title": "Current state"}, {"type": "glance", "title": "At a glance"},
                {"type": "text", "title": "Summary", "body": "<p> </p>"}, {"type": "text", "title": "Next week", "body": "<p>Hand over.</p>"}]
        got = build(project={**PROJECT, "current_state": ""}, sections=secs, tiles=[dict(t, hidden=True) for t in TILES])
        self.assertEqual([x["text"] for x in got if x["kind"] == "heading"], ["Next week"])
        got = build(project={**PROJECT, "current_state": ""}, sections=secs[:2], tiles=[])
        self.assertEqual([x["kind"] for x in got if x["kind"] == "heading"], [])

    def test_the_health_tile_carries_the_pills_colour(self):
        (tiles,) = [x["tiles"] for x in build() if x["kind"] == "tiles"]
        self.assertEqual(tiles[0]["colour"], "green")
        no_colour = [dict(t, pill={"colour": None}) if t["tile"] == "health" else t for t in TILES]
        (tiles,) = [x["tiles"] for x in build(tiles=no_colour) if x["kind"] == "tiles"]
        self.assertIsNone(tiles[0]["colour"], "health not set: no colour, words only")

    def test_current_state_is_plain_words_with_breaks(self):
        got = texts(build())
        self.assertIn("Phase two is under way.\nCabling done\nTesting next", got)

    def test_the_tiles_each_have_a_title_a_big_number_and_a_sub_line(self):
        (tiles,) = [x["tiles"] for x in build() if x["kind"] == "tiles"]
        self.assertEqual([(t["title"], t["value"], t["detail"]) for t in tiles],
                         [("Project health", "On track", "Dates hold."), ("Overdue actions", "3", ""),
                          ("High risks and issues", "1", "of 4 open")], "the hidden tile is not there")
        self.assertEqual(texts(build()).count("Project health: On track"), 0, "no one-line tile text any more")

    def test_every_text_section_is_there(self):
        got = texts(build())
        self.assertIn("On course for the spring opening.", got)
        self.assertIn("Lights tested on the east pier.", got)

    def test_nothing_hidden_or_internal_reaches_the_cover(self):
        everything = "\n".join(texts(build()))
        for canary in ("CANARY-HIDDEN-SECTION", "CANARY-HIDDEN-TILE", "CANARY-INTERNAL-NOTE", "CANARY-PROJECT-FIELD", "Hidden section"):
            self.assertNotIn(canary, everything)

    def test_a_section_kind_the_cover_does_not_carry_is_left_out(self):
        self.assertNotIn("Risks and issues", [x["text"] for x in build() if x["kind"] == "heading"])

    def test_no_exporter_name_means_just_the_date(self):
        for by in (None, "  "):
            self.assertEqual([x["text"] for x in build(by=by) if x["kind"] == "exported"], [STAMP])


class TheReturnNote(unittest.TestCase):
    def test_with_an_owner_and_an_address(self):
        self.assertIn("send the file back to Kim Example (kim.example@example.com).", cover.return_note("Kim Example", "kim.example@example.com"))

    def test_with_no_address_the_brackets_go(self):
        note = cover.return_note("Kim Example", "")
        self.assertIn("send the file back to Kim Example.", note)
        self.assertNotIn("(", note)

    def test_with_no_name_it_goes_back_to_whoever_sent_it(self):
        self.assertIn("send the file back to the person who sent it to you.", cover.return_note(None, "kim.example@example.com"))
        self.assertNotIn("kim.example", cover.return_note("", "kim.example@example.com"))


class HostileText(unittest.TestCase):
    def test_tags_and_scripts_never_arrive(self):
        project = {**PROJECT, "current_state": "<p>Fine</p><script>alert('x')</script><img src=x onerror=alert(1)><p>=HYPERLINK(\"http://x\")</p>"}
        everything = "\n".join(texts(build(project=project)))
        self.assertNotIn("<", everything)
        self.assertNotIn("alert", everything)
        self.assertIn("Fine", everything)

    def test_a_very_long_body_is_cut_under_excels_limit_with_a_mark(self):
        project = {**PROJECT, "current_state": "<p>" + "word " * 20000 + "</p>"}
        for line in build(project=project):
            self.assertLess(len(line["text"]), 32767)
        longest = max(texts(build(project=project)), key=len)
        self.assertTrue(longest.endswith(cover.MORE))

    def test_a_body_the_cleaner_refuses_is_cut_not_fatal(self):
        project = {**PROJECT, "current_state": "<p>" + "a" * 400000 + "</p>"}
        got = build(project=project)                       # does not raise
        for line in got:
            self.assertLess(len(line["text"]), 32767)

    def test_empty_everything_still_gives_a_cover(self):
        got = cover.lines({}, [], [], STAMP)
        self.assertEqual([x["kind"] for x in got], ["title", "subtitle", "about", "exported", "caution", "return", "where", "ids", "locked"])


class PlainWords(unittest.TestCase):
    def test_no_wording_line_starts_with_the_product_name(self):
        for text in (cover.CAUTION, cover.RETURN_WITH, cover.RETURN_ANYONE, cover.WHERE_TO_EDIT, cover.IDS, cover.ABOUT, cover.MORE.strip()):
            self.assertFalse(text.lower().startswith("clark"), text)

    def test_the_wording_says_the_cover_is_not_read_back(self):
        self.assertEqual(cover.WHERE_TO_EDIT, "Make your changes on the Actions, Risks & Issues, Decisions, Milestones and Use cases "
                                              "sheets. Changes made on this Cover are ignored.")
        self.assertEqual(cover.IDS, "Please don't change or move IDs. Each ID stays with its own row: if you change one, or sort "
                                    "only the ID column, the details go to another item when the file is imported. Leave the ID "
                                    "empty for a new item.")       # #128 done-when 5, in words true of the import (#129)
        self.assertNotIn("refused", cover.IDS, "#128: a swapped or sorted ID is not refused, so the words must not say it is")


class Escaping(unittest.TestCase):
    """A name, a section title or a tile title that starts like a formula is text on the Cover, never a formula."""
    def setUp(self):
        pin_timezone(self)
        self.dir = Path(tempfile.mkdtemp(prefix="clark-cover-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_leading_formula_characters_show_as_typed_and_are_never_formulas(self):
        for lead in ("=", "+", "@", "\t"):
            with self.subTest(lead=repr(lead)):
                project = {"name": lead + "Name", "current_state": "<p>Now.</p>"}
                sections = [{"type": "current", "title": lead + "Section"}, {"type": "glance", "title": lead + "Glance"},
                            {"type": "text", "title": lead + "Words", "body": "<p>Body.</p>"}]
                tiles = [{"tile": "overdue", "title": lead + "Tile", "value": 2, "detail": "", "hidden": False}]
                wb = Workbook()
                ws = excel.write_cover(wb, cover.lines(project, sections, tiles, STAMP))
                values = [str(c.value) for row in ws.iter_rows() for c in row if c.value]
                self.assertIn("Name" if lead == "\t" else lead + "Name", values)      # the name is trimmed, so a tab goes
                for want in ("Section", "Glance", "Words"):        # headings follow the blue square, so can't start a formula
                    self.assertIn("■  " + lead + want, values)
                self.assertIn(lead + "Tile", values)                        # shown as typed: no apostrophe
                for row in ws.iter_rows():
                    for c in row:
                        self.assertNotEqual(c.data_type, "f", c.coordinate)
                for c in ws[1]:
                    if c.value and c.value.startswith(lead):
                        self.assertEqual((c.data_type, c.quotePrefix), ("s", True), "text that starts like a formula is a string")


class InTheWorkbook(unittest.TestCase):
    """The Cover sheet through the real export of a demo store: where it sits, what it holds, what it must not, and that the
    import never reads it."""
    ON = "2030-06-01"

    def setUp(self):
        pin_timezone(self)
        self.demo = DemoStore()
        self.s = self.demo.store
        self.dir = Path(tempfile.mkdtemp(prefix="clark-cover-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.addCleanup(self.demo.close)
        self.path, self.state = self.dir / "ABC work items.xlsx", self.dir / "state.json"
        self.demo.action(description="Visible overdue action", due_date="2030-01-01")
        self.demo.update("milestones", self.demo.milestone, {"internal_note": "CANARY-INTERNAL-NOTE"})
        self.demo.action(description="CANARY-SENSITIVE-ROW", due_date="2030-01-01", labels="Sensitive")
        self.demo.action(description="CANARY-NOT-FOR-CLIENT", due_date="2030-01-01", client_visible=0)
        con = sqlite3.connect(self.s.path)
        con.execute("UPDATE projects SET current_state = ? WHERE code = 'ABC'",
                    ("<p>=HYPERLINK(\"http://x\")</p><script>alert(1)</script><p>Phase two is under way.</p>",))
        con.execute("UPDATE projects SET client_name = 'Example Client', week_ending = '2030-05-31' WHERE code = 'ABC'")
        con.execute("DELETE FROM report_sections WHERE project = 'ABC'")      # the default sections a new project gets (#65): only these four
        con.execute("INSERT INTO report_sections (project, id, type, title, body, beside, hidden, sort_order) VALUES "
                    "('ABC','a','current','Current state','',0,0,1), ('ABC','b','glance','At a glance','',0,0,2), "
                    "('ABC','c','text','Summary','<p>On course.</p>',0,0,3), "
                    "('ABC','d','text','Secret plans','<p>CANARY-HIDDEN-SECTION</p>',0,1,4)")
        con.commit()
        con.close()
        self.make()

    def make(self):
        return excel.export_project(self.s, "ABC", self.path, self.state, on=self.ON, exported_by="Sam Example", owner="Kim Example",
                                    owner_email="kim.example@example.com")

    def cover_cells(self):
        ws = load_workbook(self.path)["Cover"]
        return [c.value for row in ws.iter_rows() for c in row if c.value is not None]

    def test_cover_is_first_and_open_with_gridlines_off_and_the_band_frozen(self):
        wb = load_workbook(self.path)
        self.assertEqual(wb.sheetnames, ["Cover", "Actions", "Risks & Issues", "Decisions", "Milestones", "Use cases", "History", "Lists"])
        self.assertEqual(wb.active.title, "Cover")
        self.assertFalse(wb["Cover"].sheet_view.showGridLines)
        self.assertEqual(wb["Cover"].freeze_panes, "A3")      # below the title band (the title and the subtitle)

    def test_merged_cells_stay_inside_a_12_column_grid_and_a_row_is_never_merged_across_rows(self):
        ws = self.cover_sheet()
        self.assertTrue(ws.merged_cells.ranges)
        for r in ws.merged_cells.ranges:
            self.assertGreaterEqual(r.min_col, 1)
            self.assertLessEqual(r.max_col, 12, str(r))
            self.assertEqual(r.min_row, r.max_row, str(r))
        widths = {k: v.width for k, v in ws.column_dimensions.items()}
        self.assertEqual(sorted(widths), list("ABCDEFGHIJKL"))
        self.assertEqual(len(set(widths.values())), 1, "twelve equal columns")
        self.assertEqual([c.column for c in ws[1]][-1], 12)

    def cover_sheet(self):
        return load_workbook(self.path)["Cover"]

    def find(self, value):
        (cell,) = [c for row in self.cover_sheet().iter_rows() for c in row if c.value == value]
        return cell

    def find_like(self, text):
        (cell,) = [c for row in self.cover_sheet().iter_rows() for c in row if isinstance(c.value, str) and c.value.endswith(text)
                   and c.value.startswith("■")]
        return cell

    def test_the_title_band_is_navy_with_white_bold_title_the_subtitle_and_the_internal_tag_at_the_right(self):
        ws = self.cover_sheet()
        title, tag, sub = ws["A1"], ws["K1"], ws["A2"]
        self.assertEqual((title.value, tag.value), ("Example Programme", "INTERNAL"))
        self.assertEqual(sub.value, "Weekly report · Week ending Friday 31 May 2030 · for Example Client")
        self.assertEqual(tag.fill.fgColor.rgb[-6:], colours.TOKENS["status-red"], "the INTERNAL tag is red")
        for c in (title, sub):
            self.assertEqual(c.fill.fgColor.rgb[-6:], colours.TOKENS["brand-navy"])
        for c in (title, tag):
            self.assertEqual(c.font.color.rgb[-6:], "FFFFFF")
            self.assertTrue(c.font.b)
        self.assertIn("A1:J1", [str(r) for r in ws.merged_cells.ranges])
        self.assertIn("K1:L1", [str(r) for r in ws.merged_cells.ranges])

    def test_the_red_internal_line_is_gone_but_the_tag_stays_just_internal(self):
        cells = self.cover_cells()
        self.assertEqual([c for c in cells if "INTERNAL" in str(c).upper() or "never share" in str(c).lower()], ["INTERNAL"])
        self.assertNotIn("Internal", [self.cover_sheet().cell(row=r, column=1).value for r in range(1, self.cover_sheet().max_row + 1)])
        self.assertNotIn("Internal", excel.COVER_LABELS.values())

    def test_section_headings_have_the_blue_square_and_a_grey_rule_and_tiles_are_quiet_grey(self):
        h = self.find_like("Summary")
        self.assertEqual(h.value, "■  Summary")
        self.assertTrue(h.font.b)
        self.assertEqual(h.border.bottom.color.rgb[-6:], colours.TOKENS["grey-300"])
        with zipfile.ZipFile(self.path) as z:
            sheet = z.read("xl/worksheets/sheet1.xml").decode()
        self.assertIn(colours.TOKENS["brand-blue"], sheet[sheet.index("Summary") - 300:sheet.index("Summary")], "the square is brand blue")
        tile = self.find("Overdue actions")
        self.assertEqual(tile.fill.fgColor.rgb[-6:], colours.TOKENS["grey-50"])

    def test_the_cover_reads_in_the_dashboards_order_and_ends_with_the_about_block(self):
        ws = self.cover_sheet()
        col = [c.value for c in ws["A"] if c.value]
        self.assertEqual(col[:3], ["Example Programme", "Weekly report · Week ending Friday 31 May 2030 · for Example Client", "■  Current state"])
        self.assertEqual([v for v in col if str(v).startswith("■")], ["■  Current state", "■  At a glance", "■  Summary"])
        tail = [c.value for c in ws["A"] if c.value][-7:]
        self.assertEqual(tail, ["About this export", "Exported", "Caution", "Sending changes back", "Where to make changes", "IDs",
                                "Locked cells"])

    def test_the_tiles_sit_side_by_side_with_a_label_a_big_number_and_a_sub_line(self):
        ws = self.cover_sheet()
        label = self.find("Overdue actions")
        row = label.row
        self.assertEqual([ws.cell(row=row, column=c).value for c in (1, 7, 10)], ["Project health", "Overdue actions", "High risks and issues"])
        self.assertEqual([ws.cell(row=row + 1, column=c).value for c in (1, 7, 10)], ["On track", "1", "0"])
        self.assertEqual([ws.cell(row=row + 2, column=c).value for c in (1, 7, 10)],
                         [None, "of 1 open action", "None open"])
        big = ws.cell(row=row + 1, column=7)
        self.assertGreaterEqual(big.font.size, 20)
        self.assertTrue(big.font.b)
        for first, last in (("A", "F"), ("G", "I"), ("J", "L")):
            self.assertIn(f"{first}{row}:{last}{row}", [str(r) for r in ws.merged_cells.ranges])

    def test_this_week_and_next_week_are_beside_each_other_when_the_page_has_both(self):
        con = sqlite3.connect(self.s.path)
        con.execute("INSERT INTO report_sections (project, id, type, title, body, beside, hidden, sort_order) VALUES "
                    "('ABC','e','text','This week','<p>Book the rooms.</p>',0,0,5), ('ABC','f','text','Next week','<p>Open the office.</p>',0,0,6)")
        con.commit()
        con.close()
        self.make()
        ws = self.cover_sheet()
        this, nxt = self.find_like("This week"), self.find_like("Next week")
        self.assertEqual((this.row, this.column, nxt.row, nxt.column), (this.row, 1, this.row, 8))
        self.assertEqual((ws.cell(row=this.row + 1, column=1).value, ws.cell(row=this.row + 1, column=8).value),
                         ("Book the rooms.", "Open the office."))

    def test_the_stamp_row_is_labelled_exported(self):
        ws = self.cover_sheet()
        (cell,) = [c for row in ws.iter_rows() for c in row if c.value == "Exported"]
        self.assertTrue(ws.cell(row=cell.row, column=4).value.endswith(" by Sam Example"))

    def test_a_long_text_gets_a_taller_row_than_a_short_one(self):
        con = sqlite3.connect(self.s.path)
        con.execute("UPDATE projects SET current_state = ? WHERE code = 'ABC'", ("<p>" + "A long sentence about the work. " * 40 + "</p>",))
        con.commit()
        con.close()
        self.make()
        ws = self.cover_sheet()
        long_row = self.find_like("Current state").row + 1
        short_row = self.find_like("Summary").row + 1
        self.assertGreater(ws.row_dimensions[long_row].height, 5 * ws.row_dimensions[short_row].height / 1.5)
        self.assertGreater(ws.row_dimensions[long_row].height, 100)
        self.assertLessEqual(ws.row_dimensions[long_row].height, 409)

    def test_the_about_block_is_quiet_grey_and_the_where_to_edit_words_are_the_approved_ones(self):
        head = self.find("About this export")
        self.assertEqual(head.fill.fgColor.rgb[-6:], colours.TOKENS["grey-50"])
        self.assertIn(cover.WHERE_TO_EDIT, self.cover_cells())
        ws = self.cover_sheet()
        self.assertEqual(ws.cell(row=head.row + 4, column=1).fill.fgColor.rgb[-6:], colours.TOKENS["grey-50"])

    def test_the_word_provenance_is_nowhere(self):
        ws = self.cover_sheet()
        self.assertNotIn("provenance", "\n".join(str(c.value) for row in ws.iter_rows() for c in row).lower())
        self.assertNotIn("Provenance", repr(excel.COVER_LABELS))

    def test_everything_on_the_cover_is_the_looks_office_font_text_and_no_line_starts_with_the_product_name(self):
        ws = self.cover_sheet()
        for row in ws.iter_rows():
            for c in row:
                if c.value is None:                          # a covered cell of a merge, or a blank spacer row: nothing to read
                    continue
                self.assertEqual(c.font.name, look.office_font(), c.coordinate)
                self.assertIn(c.data_type, ("s", "inlineStr"), c.coordinate)
                self.assertFalse(str(c.value or "").lower().startswith("clark"), c.coordinate)

    def test_what_it_says(self):
        text = self.cover_cells()
        self.assertIn("Example Programme", text)
        self.assertFalse(any(c.startswith("INTERNAL:") for c in text))
        stamp = [c for c in text if c.endswith(" by Sam Example")]
        self.assertEqual(len(stamp), 1)
        self.assertRegex(stamp[0], r"^\d{2}-\d{2}-\d{4} ([01]\d|2[0-3]):[0-5]\d \(UTC[+-]\d{2}:\d{2}\) by Sam Example$")
        self.assertIn(cover.CAUTION, text)
        self.assertTrue(any("Kim Example (kim.example@example.com)" in c for c in text))
        self.assertIn("On course.", text)
        self.assertIn("On track", text)

    def test_counts_are_the_pages_counts_so_hidden_and_sensitive_rows_are_not_in_them(self):
        ws = self.cover_sheet()
        self.assertIn("of 1 open action", self.cover_cells())
        self.assertEqual(ws.cell(row=self.find("Overdue actions").row + 1, column=7).value, "1")

    def test_no_canary_reaches_the_cover(self):
        everything = "\n".join(self.cover_cells())
        for canary in ("CANARY-INTERNAL-NOTE", "CANARY-SENSITIVE-ROW", "CANARY-NOT-FOR-CLIENT", "CANARY-HIDDEN-SECTION", "Secret plans"):
            self.assertNotIn(canary, everything)
        data = "\n".join(str(c.value) for sheet in ("Milestones", "Actions") for row in load_workbook(self.path)[sheet].iter_rows() for c in row)
        for canary in ("CANARY-INTERNAL-NOTE", "CANARY-SENSITIVE-ROW", "CANARY-NOT-FOR-CLIENT"):
            self.assertIn(canary, data, "the data sheets still hold them: only the Cover is clean")

    def test_a_hostile_current_state_makes_no_tag_and_no_formula(self):
        wb = load_workbook(self.path)
        for row in wb["Cover"].iter_rows():
            for c in row:
                self.assertNotEqual(c.data_type, "f", c.coordinate)
        everything = "\n".join(self.cover_cells())
        self.assertNotIn("<script", everything)
        self.assertNotIn("alert", everything)
        self.assertIn("=HYPERLINK(\"http://x\")\nPhase two is under way.", self.cover_cells(),
                      "a cell that starts with = shows as typed, as a text cell; a later line in it can't start a formula")

    def test_the_health_pill_is_a_coloured_cell_and_its_words_name_the_health(self):
        ws = load_workbook(self.path)["Cover"]
        (cell,) = [c for row in ws.iter_rows() for c in row if c.value == "On track"]
        fill, ink = colours.hexes("green")
        self.assertEqual(cell.fill.fgColor.rgb[-6:], fill)
        self.assertEqual(cell.font.color.rgb[-6:], ink)
        others = [c for row in ws.iter_rows() for c in row if c.value and str(c.value) in ("Overdue actions", "1", "of 1 open action")]
        self.assertTrue(others and all(c.fill.fgColor.rgb[-6:] == colours.TOKENS["grey-50"] for c in others),
                        "the other tiles are quiet grey; only the pill has a status colour")
        bar = ws.cell(row=cell.row, column=7).border.left.color.rgb[-6:]
        self.assertEqual(bar, colours.TOKENS["status-red"], "the overdue tile's bar is red (one action is overdue)")

    def test_the_import_never_reads_the_cover(self):
        plan = xi.read_workbook(self.s, self.path, "ABC", state_path=self.state)
        self.assertEqual((plan.changes, plan.problems), ([], []))
        wb = load_workbook(self.path)
        for row in wb["Cover"].iter_rows():
            for c in row:
                if c.value is not None:
                    c.value = "edited " + str(c.value)
        wb.save(self.path)
        plan = xi.read_workbook(self.s, self.path, "ABC", state_path=self.state)
        self.assertEqual((plan.changes, plan.problems), ([], []), "a Cover with every cell edited changes nothing")
        self.assertEqual([n for n in plan.notes if "ignored" in n], [])

    def test_every_sheet_prints_on_one_landscape_page_width(self):
        wb = load_workbook(self.path)
        for ws in wb.worksheets:
            with self.subTest(sheet=ws.title):
                self.assertEqual(ws.page_setup.orientation, "landscape")
                self.assertEqual(ws.page_setup.paperSize, 9)
                self.assertEqual(ws.page_setup.fitToWidth, 1)
                self.assertEqual(ws.page_setup.fitToHeight, 0)
                self.assertTrue(ws.sheet_properties.pageSetUpPr.fitToPage)
                self.assertEqual(ws.print_title_rows, None if ws.title == "Cover" else "$1:$1")
        with zipfile.ZipFile(self.path) as z:
            for name in z.namelist():
                if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"):
                    xml = z.read(name).decode("utf-8")
                    self.assertIn('orientation="landscape"', xml)
                    self.assertIn('fitToPage="1"', xml)

    def test_the_tile_values_are_inset_from_the_coloured_edge(self):
        ws = load_workbook(self.path)["Cover"]
        big = [c for row in ws.iter_rows() for c in row if c.value is not None and c.font.sz == 22 and c.alignment.horizontal == "left"]
        self.assertTrue(big)
        for c in big:
            self.assertEqual(c.alignment.indent, 1)

    def test_the_same_data_and_clock_give_the_same_bytes(self):
        with mock.patch.object(excel, "new_export_id", lambda: FIXED_ID):       # the id is random: held still, as the clock is
            self.state.unlink()
            self.path.unlink()
            self.make()
            first = self.path.read_bytes()
            self.state.unlink()
            self.path.unlink()
            self.make()
        self.assertEqual(self.path.read_bytes(), first)


if __name__ == "__main__":
    unittest.main()
