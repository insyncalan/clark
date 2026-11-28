"""Row 1543 AP4b (review ruling, WO-M22777): one rule, everything the client receives highlights no late days. Two parts here:
(d) the client Excel workbook has no Overdue actions tile (the glance sheet), no Late word on a Gantt line or a passed milestone and no red
late look on a date; the internal Excel export is unchanged; (e) the published Use cases strip never says "N overdue" (the editor's neither:
the strip draws a count of each status only).
Fictional data.

Run: python3 dev/run_tests.py test_published_excel_1543        (the web part needs Chrome; run only while the machine's load is under 70)
"""
import copy
import io
import re

from openpyxl import load_workbook

import test_glance_page as glance
import test_published_header_1543 as base
from clark import excel_client, publish
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

LATE = re.compile(r"(?i)\b(overdue|late|days? late|d late)\b")
RED = {"FFC00000", "FFB91C1C", "FFDC2626"}


def words_of(data):
    """Every sheet name, cell value, cell comment and defined name of the workbook, as a list of (where, text)."""
    wb = load_workbook(io.BytesIO(data))
    out = [("sheet", n) for n in wb.sheetnames] + [("name", n) for n in wb.defined_names]
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if c.value is not None:
                    out.append((f"{ws.title}!{c.coordinate}", str(c.value)))
                if c.comment:
                    out.append((f"{ws.title}!{c.coordinate} comment", c.comment.text))
    return wb, out


class Excel1543(glance.Published):
    def plant_all(self):
        self.plant_gantt = base.Header1543.plant_gantt
        base.Header1543.plant_gantt(self)
        self.demo.action(description="Chase the supplier file", owner="Pat Demo", due_date="2026-10-01")
        base.Header1543.plant_late(self)

    def built(self):
        built = copy.deepcopy(publish.build(self.store, "ABC", now="2026-10-28")["published"])
        if not any(x["type"] == "gantt" for x in built["sections"]):
            built["sections"] = list(built["sections"]) + [{"id": "gantt-1", "type": "gantt", "title": "Gantt", "beside": 0}]
        built["sections"] = list(built["sections"]) + [{"id": "gt-1", "type": "glancetemplate", "title": "At a glance", "beside": 0, "content": {
            "order": ["overdue", "risks"], "health": {"shown": False}, "counts": [
                {"tile": "overdue", "title": "Overdue actions", "value": 2, "detail": "of 3 open actions", "rag": "r"},
                {"tile": "risks", "title": "High risks and issues", "value": 1, "detail": "1 open", "rag": "a"}]}}]
        return built

    def test_client_workbook_has_no_late_word_and_no_red_late_look(self):
        self.plant_all()
        built = self.built()
        wb, said = words_of(excel_client.workbook_bytes(built))
        text = " | ".join(t for _, t in said)
        for control in ("Chase the supplier file", "Passed task", "Passed gate", "Slipped gate", "Expected later", "High risks and issues"):
            self.assertIn(control, text, f"control: {control} is in the workbook")
        self.assertIn("Running task", text, "control: the Gantt sheet has its other line")
        gantt = next(ws for ws in wb.worksheets if any(c.value == "Passed task" for r in ws.iter_rows() for c in r))
        head = {c.value: c.column for c in gantt[4]}
        self.assertIn("Status", head, "control: the Gantt sheet has its Status column")
        passed = next(r for r in range(5, gantt.max_row + 1) if gantt.cell(r, 1).value == "Passed task" or any(c.value == "Passed task" for c in gantt[r]))
        self.assertEqual(gantt.cell(passed, head["Status"]).value, excel_client.NO_LATE_WORD, "a passed Gantt line reads a dash")
        for where, t in said:
            self.assertIsNone(LATE.search(t), f"no late word at {where}: {t!r}")
        for ws in wb.worksheets:
            self.assertEqual(len(ws.conditional_formatting), 0, f"{ws.title}: no conditional (late) format")
            for row in ws.iter_rows():
                for c in row:
                    for colour in (c.font.color, c.fill.fgColor if c.fill and c.fill.fill_type else None):
                        self.assertNotIn(getattr(colour, "rgb", None), RED, f"{ws.title}!{c.coordinate}: no red look")
        glance_sheet = wb["At a glance"]
        labels = [c.value for c in glance_sheet["A"][4:]]
        self.assertIn("High risks and issues", labels, "control: the glance sheet holds the risks tile")
        self.assertNotIn("Overdue actions", labels, "and no Overdue actions tile")

    def test_internal_export_keeps_its_late_rule(self):
        from clark import excel, excel_colours
        self.assertIn(("actions", "due_date"), excel_colours.LATE, "the editor's Excel export still draws a late date")
        self.assertTrue(hasattr(excel, "add_late_rule"))


class Strip1543(glance.Published):
    def test_published_use_case_strip_never_says_overdue(self):
        self.demo.plant_builtin_sections()
        built = publish.build(self.store, "ABC", now="2026-10-28")["published"]
        rows = built["data"]["glance"]["strip"]["rows"]
        self.assertTrue(any(r["overdue"] for r in rows), "control: the file's own strip data counts an overdue item (it is carried, not drawn)")
        path = self.publish()
        probe = """(() => { const u = document.querySelector('[data-uc-section]'); const s = u && u.querySelector('.ucstrip');
          return {strip: s ? s.textContent : null, all: u ? u.textContent : null, n: u ? u.querySelectorAll('.ucrow').length : 0,
                  wide: document.documentElement.scrollWidth <= innerWidth}; })()"""
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.draw(cdp, path, width, dark)
                p.until("!!document.querySelector('[data-uc-section] .ucstrip')", "the use case strip drew")
                got = p.js(probe)
                self.assertGreaterEqual(got["n"], 1, "control: the use case rows are drawn")
                self.assertRegex(got["strip"], r"\d+ use cases?", "control: the strip says its count")
                self.assertRegex(got["strip"], r"\d+ (On track|Flag|High risk|Done)", "control: the strip has its status counts")
                self.assertIsNone(LATE.search(got["strip"]), f"no overdue or late word in the strip: {got['strip']!r}")
                self.assertIsNone(LATE.search(got["all"]), f"nor in the rows: {got['all']!r}")
                self.assertTrue(got["wide"], "no sideways scroll")


for _cls in (Excel1543, Strip1543):
    for _name in dir(glance.Published):      # the base class's own tests are run in its own file
        if _name.startswith("test") and _name not in _cls.__dict__:
            setattr(_cls, _name, None)
