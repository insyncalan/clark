"""Mutation audit of src/clark/glance.py and src/clark/docx_build.py: the tests that kill the mutants the older tests let live.

Run: python3 dev/run_tests.py test_mutation_gl_docx
Each test names the line it pins. Rows are the made-up #39 plant (project PUB) or small made-up rows; no browser, no database.
"""
import copy
import io
import unittest
import zipfile
from unittest import mock

from _paths import ROOT   # noqa: F401  (puts src/ on the path)

import _publish_fixture as fx
from clark import docx_build, docx_read, glance, publish

ON = "2026-10-28"


def published():
    return publish.select(fx.inputs())


def blocks(data):
    return docx_read.read(data, "report.docx").blocks


def table(data, first, second):
    return next(b["rows"] for b in blocks(data) if b["kind"] == "table" and b["rows"][0][:2] == [first, second])


def ctx():
    return docx_build._Ctx(docx_build.palette(), ON)


class GlanceRules(unittest.TestCase):
    def test_a_withdrawn_item_is_not_open(self):                       # CLOSED lists Withdrawn
        self.assertFalse(glance.is_open({"status": "Withdrawn"}))
        self.assertFalse(glance.is_overdue({"kind": "decision", "status": "Withdrawn", "date": "2026-01-01"}, ON))
        for status in ("Open", "Pending", "Delayed"):
            self.assertTrue(glance.is_open({"status": status}), status)

    def test_a_row_with_no_visible_flag_is_visible(self):              # work_rows: client_visible defaults to 1
        rows = glance.work_rows({"actions": [{"id": "A-1", "status": "Open"}, {"id": "A-2", "status": "Open", "client_visible": 0}]})
        self.assertEqual([r["client_visible"] for r in rows], [True, False])

    def test_every_section_deleted_hides_every_built_in_section(self):  # kept_rows: sections_deleted is read from the rows
        rows = {"project": {"code": "ABC", "health": "On track"}, "actions": [], "raid": [], "decisions": [],
                "report_sections": [], "sections_deleted": True}
        kept = glance.kept_rows(rows, ON)
        self.assertEqual(kept["hidden_types"], publish.hidden_types([], True))
        self.assertTrue({"actions", "raid", "decisions"} <= kept["hidden_types"])
        rows["sections_deleted"] = False
        self.assertEqual(glance.kept_rows(rows, ON)["hidden_types"], set(), "no rows and none ever deleted: nothing hidden")

    def test_the_health_reason_on_a_tile_is_words_not_markup(self):    # _health_tile: rich_plain_text
        rows = {"project": {"code": "ABC", "health": "At risk", "health_reason": "<p>Supplier <strong>late</strong></p><script>x()</script>"}}
        for client in (False, True):
            tile = glance.tiles(rows, ON, for_client=client, kept=glance.kept_rows(rows, ON) if client else None)[0]
            self.assertEqual(tile["tile"], "health")
            self.assertNotIn("<", tile["reason"])
            self.assertNotIn("<", tile["label"])
            self.assertIn("Supplier late", tile["reason"])


class WordCells(unittest.TestCase):
    def test_xml_cannot_hold_the_c1_controls(self):                    # NOT_XML covers \x7f to \x9f
        self.assertEqual(docx_build.esc("a\x7fb\x85c\x9fd"), "abcd")
        self.assertEqual(docx_build.esc("e\x9ff"), "ef")
        self.assertEqual(docx_build.esc("\xa0"), "\xa0", "the first character after the range stays")

    def test_an_urgent_cell_is_solid_maroon_with_bold_white_words(self):    # word_cell colour "urgent"
        c = ctx()
        body, fill = docx_build.word_cell("Overdue", c, colour="urgent")
        self.assertEqual(fill, c.tok["tone-urgent"])
        self.assertIn("<w:b/>", body)
        self.assertIn(f'<w:color w:val="{c.tok["white"]}"/>', body)
        plain, no_fill = docx_build.word_cell("Overdue", c, colour="nonsense")
        self.assertIsNone(no_fill)
        self.assertNotIn("<w:b/>", plain)

    def test_an_open_urgent_item_keeps_the_maroon_status_cell(self):   # the action's own status cell
        c = ctx()
        body, fill = docx_build._status_cell({"status": "Open", "priority": "Urgent", "due_date": "2026-01-01"}, "action", c)
        self.assertEqual(fill, c.tok["tone-urgent"])
        self.assertIn("Overdue", body)

    def test_late_text_is_red_and_on_time_text_is_not(self):          # word_cell late=
        c = ctx()
        red = f'<w:color w:val="{c.tok["tone-red-text"]}"/>'
        self.assertIn(red, docx_build.word_cell("01-01-2026 (overdue)", c, late=True)[0])
        self.assertNotIn(red, docx_build.word_cell("01-01-2030", c, late=False)[0])
        self.assertNotIn(red, docx_build.word_cell("01-01-2030", c)[0])


class WordSections(unittest.TestCase):
    def test_a_use_case_with_no_standing_still_lists_its_linked_work_items(self):    # section_usecases: body or linked
        p = published()
        p["data"]["use_cases"][0]["standing"] = ""
        text = "\n".join(str(b.get("text", "")) for b in blocks(docx_build.build(p)))
        self.assertIn("Linked work items: PUB-A-001", text)

    def test_a_use_case_with_no_standing_and_no_links_has_no_detail(self):
        p = published()
        p["data"]["use_cases"][0]["standing"] = ""
        for key in ("actions", "raid", "decisions"):
            for r in p["data"][key]:
                r["use_case"] = None
        text = "\n".join(str(b.get("text", "")) for b in blocks(docx_build.build(p)))
        self.assertNotIn("Linked work items", text)

    def test_slip_is_shown_on_a_planned_milestone_and_not_on_an_achieved_one(self):   # section_milestones: slip and not achieved
        p = published()
        m = p["data"]["milestones"][0]
        m.update(status="Done", actual_date="2026-10-01", slip_days=5)
        p["data"]["milestones"][1].update(slip_days=5)
        rows = {r[0]: r for r in table(docx_build.build(p), "ID", "Milestone")[1:]}
        self.assertEqual(rows["PUB-M-001"][-1], "")
        self.assertEqual(rows["PUB-M-002"][-1], "+5 days")

    def test_zero_percent_complete_is_still_said(self):                # percent_complete is None, not falsy
        p = published()
        p["data"]["milestones"][0]["percent_complete"] = 0
        p["data"]["milestones"][1]["percent_complete"] = None
        rows = {r[0]: r for r in table(docx_build.build(p), "ID", "Milestone")[1:]}
        self.assertIn("0% complete", rows["PUB-M-001"][1])
        self.assertNotIn("% complete", rows["PUB-M-002"][1])

    def test_a_pending_decision_with_no_date_says_so_without_needed_by(self):   # section_decisions label
        p = published()
        d = p["data"]["decisions"][0]
        d.update(status="Pending", needed_by=None)
        p["data"]["decisions"][1].update(status="Pending", needed_by="2030-01-02")
        rows = {r[0]: r for r in table(docx_build.build(p), "ID", "Decision")[1:]}
        self.assertEqual(rows["PUB-D-001"][-1], "No date needed by")
        self.assertEqual(rows["PUB-D-003"][-1], "Needed by 02-01-2030")


class Limit(unittest.TestCase):
    def test_the_limit_is_exact_and_not_a_multiple_of_itself(self):    # build: len(data) > MAX_BYTES
        p = published()
        size = len(docx_build.build(p))
        with mock.patch.object(docx_build, "MAX_BYTES", size):
            self.assertEqual(len(docx_build.build(p)), size)
        with mock.patch.object(docx_build, "MAX_BYTES", size - 1):
            with self.assertRaises(docx_build.WordError):
                docx_build.build(p)


if __name__ == "__main__":
    unittest.main()
