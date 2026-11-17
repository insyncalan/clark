"""Row 1264, slice 7: the Word report and the client workbook print the glance template as the View draws it: the tiles in the body's
order, only the kept ones, the health row on or off (in its place or on its own row), a bespoke tile with its label, figure, tag and note,
the same counts as the View, a hidden tile absent.

Run: python3 dev/run_tests.py test_glance_word_excel_1264
Uses the #39 plant (fictional data) with one glancetemplate section put in front, through publish.select().
"""
import io
import json
import re
import unittest
import zipfile

from _paths import ROOT   # noqa: F401

import _publish_fixture as fx
from openpyxl import load_workbook
from clark import docx_build, docx_read, excel_client, glance_print, publish

BESPOKE = [{"id": "bud", "label": "ZQ-Budget", "figure": "87%", "tag": "ZQ-Steady", "note": "ZQ-Note one", "tone": "green"},
           {"id": "mor", "label": "ZQ-Morale", "figure": "ZQ-High", "tag": "", "note": "", "tone": "blue"},
           {"id": "sec", "label": "ZQ-Secret", "figure": "ZQ-Hid", "tag": "ZQ-HidTag", "note": "ZQ-HidNote", "hidden": True}]


def body(**kw):
    return {"v": 1, "bespoke": BESPOKE, **kw}


def select(b=None, hidden=0, with_section=True, title=""):
    i = fx.inputs()
    i["sections"] = [x for x in i["sections"] if x["type"] != "glance"]      # the built-in At a glance prints the same words: leave it out so only the template is read
    if with_section:
        i["sections"].insert(0, {"project": "PUB", "id": "s-gt", "type": "glancetemplate", "title": title, "beside": 0, "hidden": hidden,
                                 "sort_order": 0, "body": json.dumps(b if b is not None else body())})
    return publish.select(i)


def lines(pub):
    """Every paragraph of the report, a table cell's paragraphs too, in reading order."""
    out = []
    for b in docx_read.read(docx_build.build(pub), "r.docx").blocks:
        if b["kind"] == "table":
            out += [p for row in b["rows"] for cell in row for p in str(cell).split("\n")]
        else:
            out.append(b.get("text", ""))
    return out


def alltext(pub):
    return "\n".join(lines(pub))


def sheet(pub):
    wb = load_workbook(io.BytesIO(excel_client.workbook_bytes(pub)))
    return wb["At a glance"] if "At a glance" in wb.sheetnames else None


def sheet_rows(pub):
    ws = sheet(pub)
    return [[ws.cell(r, c).value for c in (1, 2, 3, 4)] for r in range(5, ws.max_row + 1)]


def counts(pub):
    s = next(x for x in pub["sections"] if x["type"] == "glancetemplate")
    return {c["tile"]: c for c in s["content"]["counts"]}


class Word(unittest.TestCase):
    def test_the_section_has_its_heading_and_every_kept_bespoke_tile_with_its_four_words(self):
        t = lines(select())
        self.assertIn("At a glance", [b["text"] for b in docx_read.read(docx_build.build(select()), "r.docx").blocks if b["kind"] == "heading"])
        for w in ("ZQ-Budget", "87%", "ZQ-Steady", "ZQ-Note one", "ZQ-Morale", "ZQ-High"):
            self.assertIn(w, t)

    def test_a_title_the_person_gave_is_the_heading(self):
        heads = [b["text"] for b in docx_read.read(docx_build.build(select(title="ZQ-Mine")), "r.docx").blocks if b["kind"] == "heading"]
        self.assertIn("ZQ-Mine", heads)

    def test_a_hidden_tile_is_not_in_the_report(self):
        self.assertNotIn("ZQ-Secret", alltext(select()))
        self.assertNotIn("ZQ-HidNote", alltext(select()))

    def test_a_hidden_counting_tile_is_not_in_the_report_and_the_others_are(self):
        pub = select(body(builtin={"risks": {"hidden": True}}))
        t = alltext(pub)
        self.assertNotIn("High risks and issues", t)
        self.assertIn("Overdue actions", t)
        self.assertIn("Decisions needed", t)

    def test_the_counts_are_the_views(self):
        pub = select()
        c = counts(pub)
        t = lines(pub)
        for key in ("overdue", "risks", "decisions"):
            self.assertIn(c[key]["title"], t)
            self.assertIn(str(c[key]["value"]), t)
            self.assertIn(c[key]["detail"], t)

    def test_the_tiles_are_in_the_bodys_order(self):
        pub = select(body(order=["mor", "decisions", "bud", "health", "risks", "overdue"]))
        t = lines(pub)
        at = [t.index(w) for w in ("ZQ-Morale", "Decisions needed", "ZQ-Budget", "Project health", "High risks and issues", "Overdue actions")]
        self.assertEqual(at, sorted(at))

    def test_the_default_order_is_health_then_the_counts_then_the_bespoke_tiles(self):
        t = lines(select())
        at = [t.index(w) for w in ("Project health", "Overdue actions", "High risks and issues", "Decisions needed", "ZQ-Budget", "ZQ-Morale")]
        self.assertEqual(at, sorted(at))

    def test_health_off_means_no_health_tile(self):
        self.assertNotIn("Project health", alltext(select(body(health={"shown": False}))))
        self.assertIn("Project health", alltext(select()))

    def test_health_shows_the_projects_health_word(self):
        self.assertIn("At risk", lines(select())[lines(select()).index("Project health"):][:3])

    def test_health_on_its_own_row_is_above_the_tiles_and_in_a_paragraph_of_its_own(self):
        pub = select(body(order=["mor", "health", "bud"], health={"own_row": True}))
        data = docx_build.build(pub)
        xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode("utf-8")
        self.assertIn("Project health: </w:t>", xml)
        t = lines(pub)
        self.assertLess(t.index("Project health: At risk"), t.index("ZQ-Morale"))
        self.assertLess(xml.index("Project health: "), xml.index("ZQ-Morale"))

    def test_health_in_its_place_is_not_a_row_of_its_own(self):
        xml = zipfile.ZipFile(io.BytesIO(docx_build.build(select()))).read("word/document.xml").decode("utf-8")
        self.assertNotIn("Project health: </w:t>", xml)

    def test_a_tile_is_shaded_in_its_tone(self):
        xml = zipfile.ZipFile(io.BytesIO(docx_build.build(select(body(bespoke=[BESPOKE[0]]))))).read("word/document.xml").decode("utf-8")
        cell = next(c for c in re.findall(r"<w:tc>.*?</w:tc>", xml, re.S) if "ZQ-Budget" in c)
        self.assertIn(f'w:fill="{docx_build.TOKENS["tone-green-tint"]}"', cell)
        plain = next(c for c in re.findall(r"<w:tc>.*?</w:tc>", zipfile.ZipFile(io.BytesIO(docx_build.build(select(body(bespoke=[BESPOKE[1]]))))).read("word/document.xml").decode("utf-8"), re.S) if "ZQ-Morale" in c)
        self.assertIn(f'w:fill="{docx_build.TOKENS["tone-blue-tint"]}"', plain)

    def test_a_counting_tile_says_the_pages_word(self):
        c = counts(select())
        self.assertEqual(c["risks"]["rag"], "r")
        self.assertIn("High", lines(select()))

    def test_the_tiles_run_four_to_a_line_and_none_is_lost(self):
        many = [{"id": f"t{i}", "label": f"ZQ-T{i}", "figure": str(i)} for i in range(9)]
        pub = select(body(bespoke=many, health={"shown": False}, builtin={n: {"hidden": True} for n in ("overdue", "risks", "decisions")}))
        t = lines(pub)
        for i in range(9):
            self.assertIn(f"ZQ-T{i}", t)
        rows = next(b["rows"] for b in docx_read.read(docx_build.build(pub), "r.docx").blocks if b["kind"] == "table" and "ZQ-T0" in str(b["rows"]))
        self.assertEqual([len(r) for r in rows], [4, 4, 4])

    def test_a_hidden_section_is_not_in_the_report(self):
        self.assertEqual(docx_build.build(select(hidden=1)), docx_build.build(select(with_section=False)))

    def test_nothing_to_show_leaves_the_section_out(self):
        pub = select()
        for s in pub["sections"]:
            if s["type"] == "glancetemplate":
                s["content"] = {"health": {"shown": False}, "order": [], "bespoke": []}
        self.assertEqual(docx_build.build(pub), docx_build.build(select(with_section=False)))

    def test_a_report_with_no_such_section_is_as_before(self):
        self.assertNotIn("ZQ-Budget", alltext(select(with_section=False)))

    def test_the_words_are_escaped(self):
        b = body(bespoke=[{"id": "x", "label": "A<b>&", "figure": "1", "tag": "", "note": ""}])
        self.assertIn("A<b>&", lines(select(b)))

    def test_killer_a_counting_tile_is_shaded_in_its_colour_and_the_health_tile_in_the_projects(self):
        xml = zipfile.ZipFile(io.BytesIO(docx_build.build(select()))).read("word/document.xml").decode("utf-8")
        cells = re.findall(r"<w:tc>.*?</w:tc>", xml, re.S)
        for word, tone in (("Overdue actions", "green"), ("High risks and issues", "red"), ("Project health", "amber")):
            cell = next(c for c in cells if word in c)
            self.assertIn(f'w:fill="{docx_build.TOKENS["tone-" + tone + "-tint"]}"', cell, word)

    def test_killer_the_risk_tile_says_High_in_its_own_line_and_the_health_reason_is_printed(self):
        t = lines(select())
        self.assertEqual(t[t.index("High risks and issues") + 2], "High")
        self.assertIn("ZQ-HEALTH-REASON", t)

    def test_killer_health_on_its_own_row_keeps_its_reason_and_its_colour(self):
        pub = select(body(order=["health", "bud"], health={"own_row": True}))
        self.assertIn("ZQ-HEALTH-REASON", lines(pub))
        xml = zipfile.ZipFile(io.BytesIO(docx_build.build(pub))).read("word/document.xml").decode("utf-8")
        para = next(p for p in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S) if "Project health: " in p)
        self.assertIn(f'w:fill="{docx_build.TOKENS["tone-amber-tint"]}"', para)


class Excel(unittest.TestCase):
    def test_the_sheet_has_a_row_for_each_kept_tile_in_order(self):
        rows = sheet_rows(select())
        self.assertEqual([r[0] for r in rows], ["Project health", "Overdue actions", "High risks and issues", "Decisions needed", "ZQ-Budget", "ZQ-Morale"])

    def test_a_bespoke_row_has_label_figure_tag_note(self):
        rows = {r[0]: r for r in sheet_rows(select())}
        self.assertEqual(rows["ZQ-Budget"], ["ZQ-Budget", "87%", "ZQ-Steady", "ZQ-Note one"])
        self.assertEqual(rows["ZQ-Morale"], ["ZQ-Morale", "ZQ-High", None, None])

    def test_the_counts_are_the_views(self):
        pub = select()
        c = counts(pub)
        rows = {r[0]: r for r in sheet_rows(pub)}
        for key in ("overdue", "risks", "decisions"):
            self.assertEqual(rows[c[key]["title"]][1], str(c[key]["value"]))
            self.assertEqual(rows[c[key]["title"]][3], c[key]["detail"])

    def test_the_order_is_the_bodys(self):
        rows = sheet_rows(select(body(order=["mor", "decisions", "bud", "health", "risks", "overdue"])))
        self.assertEqual([r[0] for r in rows], ["ZQ-Morale", "Decisions needed", "ZQ-Budget", "Project health", "High risks and issues", "Overdue actions"])

    def test_hidden_tiles_are_absent(self):
        rows = sheet_rows(select(body(builtin={"overdue": {"hidden": True}}, health={"shown": False})))
        names = [r[0] for r in rows]
        self.assertNotIn("ZQ-Secret", names)
        self.assertNotIn("Overdue actions", names)
        self.assertNotIn("Project health", names)

    def test_health_on_its_own_row_is_first(self):
        rows = sheet_rows(select(body(order=["mor", "health"], health={"own_row": True})))
        self.assertEqual(rows[0][0], "Project health")
        self.assertEqual(rows[0][1], "At risk")

    def test_no_section_or_a_hidden_one_gives_no_such_sheet(self):
        self.assertIsNone(sheet(select(with_section=False)))
        self.assertIsNone(sheet(select(hidden=1)))

    def test_the_cells_are_locked_text_and_the_workbook_is_the_same_each_time(self):
        pub = select()
        ws = sheet(pub)
        self.assertTrue(ws["A5"].protection.locked)
        self.assertEqual(excel_client.workbook_bytes(pub), excel_client.workbook_bytes(pub))

    def test_the_other_sheets_are_still_there(self):
        wb = load_workbook(io.BytesIO(excel_client.workbook_bytes(select())))
        self.assertIn("Actions", wb.sheetnames)

    def test_killer_the_risk_tile_status_and_a_label_that_starts_with_an_equals_sign_stays_text(self):
        rows = {r[0]: r for r in sheet_rows(select(body(bespoke=[{"id": "f", "label": "=1+1", "figure": "-5", "tag": "@x", "note": "+y"}])))}
        self.assertEqual(rows["High risks and issues"][2], "High")
        ws = sheet(select(body(bespoke=[{"id": "f", "label": "=1+1", "figure": "-5", "tag": "@x", "note": "+y"}])))
        cell = next(c for c in ws["A"] if c.value == "=1+1")
        self.assertEqual(cell.data_type, "s")
        self.assertTrue(cell.quotePrefix)

    def test_killer_nothing_to_show_gives_no_sheet(self):
        pub = select()
        for s in pub["sections"]:
            if s["type"] == "glancetemplate":
                s["content"] = {"health": {"shown": False}, "order": [], "bespoke": []}
        self.assertIsNone(sheet(pub))


class Reader(unittest.TestCase):
    def test_a_content_that_is_not_an_object_is_nothing(self):
        got = glance_print.read(select(), {"type": "glancetemplate", "content": "x"})
        self.assertEqual(got["tiles"][0]["key"], "health")
        self.assertEqual([t["key"] for t in got["tiles"]], ["health"])

    def test_a_tag_word_of_a_count_follows_its_colour(self):
        pub = select()
        sec = {"content": {"order": ["overdue"], "counts": [{"tile": "overdue", "title": "T", "value": 3, "detail": "d", "rag": "r"}], "health": {"shown": False}}}
        self.assertEqual(glance_print.read(pub, sec)["tiles"][0]["tag"], "Overdue")
        sec["content"]["counts"][0]["rag"] = "g"
        self.assertEqual(glance_print.read(pub, sec)["tiles"][0]["tag"], "On track")
        sec["content"]["counts"][0]["rag"] = "n"
        self.assertEqual(glance_print.read(pub, sec)["tiles"][0]["tag"], "")

    def test_killer_every_count_tag_word_of_the_page(self):
        pub = select()
        want = {("overdue", "r"): "Overdue", ("overdue", "a"): "At risk", ("decisions", "a"): "Waiting", ("decisions", "r"): "Off track",
                ("risks", "a"): "Watch", ("risks", "r"): "High", ("risks", "g"): "On track"}
        for (key, rag), word in want.items():
            sec = {"content": {"order": [key], "counts": [{"tile": key, "title": "T", "value": 1, "detail": "d", "rag": rag}], "health": {"shown": False}}}
            self.assertEqual(glance_print.read(pub, sec)["tiles"][0]["tag"], word, (key, rag))

    def test_killer_a_count_tile_carries_its_colour_and_the_health_tile_the_projects(self):
        pub = select()
        sec = {"content": {"order": ["health", "risks"], "counts": [{"tile": "risks", "title": "T", "value": 1, "detail": "d", "rag": "a"}]}}
        got = glance_print.read(pub, sec)["tiles"]
        self.assertEqual([t["colour"] for t in got], ["amber", "amber"])
        sec["content"]["counts"][0]["rag"] = "r"
        self.assertEqual(glance_print.read(pub, sec)["tiles"][1]["colour"], "red")


if __name__ == "__main__":
    unittest.main()
