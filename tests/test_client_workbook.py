"""Item 713: the client-view workbook, made at publish time and embedded in the one published file.

Run: python3 dev/run_tests.py test_client_workbook
The workbook is made from publish.select()'s own output, so it holds exactly the rows and fields the published page holds. These
tests plant internal text, hidden rows and secrets in the plant (tests/fixtures/publish-plant.json plus more added here) and
look for every one of them in every part of the finished .xlsx: each cell, the shared strings, the zip's file list, the
properties, defined names, comments and hidden sheets.
"""
import base64
import io
import json
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from _paths import ROOT, SRC, TOOLS  # noqa: F401

import _publish_fixture as fx  # noqa: E402
from _growth import assert_growth  # noqa: E402
from openpyxl import load_workbook  # noqa: E402
from clark import excel, excel_client, publish, publish_flow, secret_screen  # noqa: E402
from clark.store import open_store  # noqa: E402

EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")
PARTS = {"[Content_Types].xml", "_rels/.rels", "docProps/app.xml", "docProps/core.xml", "xl/workbook.xml", "xl/_rels/workbook.xml.rels",
         "xl/styles.xml", "xl/theme/theme1.xml", "xl/sharedStrings.xml"}
PLANT_C = "ZQ-PLANTED-PLANT_C-MARKER-7F3A9C"
FORMULA = '=HYPERLINK("https://x.invalid","click")'


def tearDownModule():
    Path(EMPTY_BRANDING).rmdir()


def rich_plant():
    """The plant with more that must stay out: an Internal status-like word, a secret-like string in an internal note, an
    off-flag row in every table, and a visible action whose text starts like a formula."""
    plant = fx.load()
    d = plant["data"]
    d["actions"].append({**d["actions"][0], "id": "PUB-A-020", "description": FORMULA, "client_message": "",
                         "source": "Internal only " + PLANT_C + "/plan.xlsx"})   # row 1077: a source is published by name, so the marker is the folder, the name is not it
    for table in ("milestones", "actions", "raid", "decisions", "use_cases"):
        for row in d[table]:
            if row["id"] in plant["kept"]:
                row["source"] = "ZQ-INTERNAL-ONLY " + PLANT_C + "/plan.xlsx"      # row 1077: the folder is the marker; the file name is published
                if table == "milestones":
                    row["internal_note"] = "ZQ-INTERNAL-ONLY " + PLANT_C
    plant["markers"]["secret"] = PLANT_C
    plant["markers"]["internal_only"] = "ZQ-INTERNAL-ONLY"
    return plant


def selected(plant):
    return publish.select(fx.inputs(plant))


def parts_of(data):
    """Every part of the .xlsx as text, and the cell texts read back, hidden sheets included."""
    zf = zipfile.ZipFile(io.BytesIO(data))
    raw = {n: zf.read(n).decode("utf-8", "replace") for n in zf.namelist()}
    wb = load_workbook(io.BytesIO(data))
    cells = [str(c.value) for ws in wb.worksheets for row in ws.iter_rows() for c in row if c.value is not None]
    return zf.namelist(), raw, wb, cells


class Workbook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plant = rich_plant()
        cls.pub = selected(cls.plant)
        cls.data = excel_client.workbook_bytes(cls.pub)
        cls.names, cls.raw, cls.wb, cls.cells = parts_of(cls.data)
        cls.everything = "\n".join(list(cls.raw.values()) + cls.cells + cls.names + [str(cls.wb.properties.__dict__)])

    def test_no_internal_string_anywhere(self):
        dropped = [self.plant["markers"][k] for k in self.plant["dropped"] if k in self.plant["markers"]]
        for key, marker in list(self.plant["markers"].items()) + [(k, k) for k in self.plant["dropped"]]:
            if marker in ("x.invalid", "window.zq"):
                continue
            for spelling in fx.spellings(marker) + [marker.split()[0]]:
                self.assertNotIn(spelling, self.everything, f"{key}: {spelling!r} is in the workbook")
        self.assertTrue(dropped)
        for word in ("window.zq", "internal", "Internal", "INTERNAL", "Sensitive", "client_visible", "Client-visible", "internal_note",
                     "About this export", "Sending changes back", "History", "Lists", "clark_export_id", "State set by you",
                     "Open work items", "Source", "Updated"):
            self.assertNotIn(word.lower(), self.everything.lower(), word)

    def test_every_client_visible_row_appears(self):
        for key in self.plant["kept"]:
            if key == "PUB-W-001":
                continue                           # a workstream is a name, not a row
            self.assertIn(key, "\n".join(self.cells), key)
        for key, marker in self.plant["kept_markers"].items():
            if key in ("current", "text_section", "health_reason", "PUB-A-001"):
                continue            # prose on the page's own sections; and an action's own text, which its client wording replaces
            self.assertIn(marker, "\n".join(self.cells), key)

    def test_rows_are_the_published_rows_and_no_others(self):
        expect = {t: {r["id"] for r in self.pub["data"][t]} for t in excel_client.COLUMNS}
        for table, ids in expect.items():
            ws = self.wb[excel.SHEET_OF[table]]
            got = {str(r[0].value) for r in ws.iter_rows(min_row=5) if r[0].value}
            want = {i for i in ids if not (table == "milestones" and any(m["id"] == i and m["status"] == "Cancelled" for m in self.pub["data"][table]))}
            self.assertEqual(got, want, table)

    def test_client_wording_stands_in_for_the_text(self):
        ws = self.wb[excel.SHEET_OF["actions"]]
        row = next(r for r in ws.iter_rows(min_row=5) if r[0].value == "PUB-A-001")
        self.assertEqual(row[1].value, "ZQ-KEEP-MESSAGE-1")
        self.assertNotIn("Agree the cut-over plan", "\n".join(self.cells), "the row's own text is not beside the client wording")

    def test_only_the_data_sheets_the_page_shows(self):
        self.assertEqual(self.wb.sheetnames, [excel.SHEET_OF[t] for t in excel.SHEET_OF if t in excel_client.COLUMNS])
        for ws in self.wb.worksheets:
            self.assertEqual(ws.sheet_state, "visible")
        self.assertEqual(len(self.wb.defined_names), 0)

    def test_zip_holds_only_plain_parts(self):
        self.assertTrue(set(self.names) <= PARTS | {f"xl/worksheets/sheet{i}.xml" for i in range(1, 8)}, self.names)
        for bad in ("comment", "vml", "custom", "drawing", "hyperlink", "externalLink", "vbaProject"):
            self.assertFalse([n for n in self.names if bad in n.lower()], bad)
        for xml in self.raw.values():
            for tag in ("<f>", "<f ", "<hyperlink", "<dataValidation", "<legacyDrawing", "<conditionalFormatting"):
                self.assertNotIn(tag, xml)

    def test_properties_carry_nothing_internal(self):
        props = self.wb.properties
        self.assertEqual((props.creator, props.lastModifiedBy), (excel.FIXED_NAME, excel.FIXED_NAME))
        self.assertIsNone(props.description)

    def test_not_importable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "client.xlsx"
            path.write_bytes(self.data)
            self.assertIsNone(excel.export_id_of(path), "no export id the import trusts")
        self.assertNotIn("clark_export_id", self.everything)

    def test_text_that_looks_like_a_formula_is_text(self):
        ws = self.wb[excel.SHEET_OF["actions"]]
        row = next(r for r in ws.iter_rows(min_row=5) if r[0].value == "PUB-A-020")
        self.assertEqual(row[1].value, FORMULA)
        self.assertEqual(row[1].data_type, "s")
        self.assertTrue(row[1].quotePrefix)

    def test_the_workbook_text_passes_the_scans_the_page_does(self):
        text = "\n".join(self.cells)
        self.assertEqual(publish.outside_addresses(text.replace(FORMULA, "")), [])
        self.assertFalse(secret_screen.looks_like_secret(text), "no key shape in the workbook")

    def test_same_content_same_bytes(self):
        import time
        time.sleep(1.1)                       # openpyxl stamps the save time; the file must not
        self.assertEqual(self.data, excel_client.workbook_bytes(selected(self.plant)))

    def test_title_band_names_project_and_week(self):
        ws = self.wb["Actions"]
        self.assertEqual(ws["A1"].value, self.pub["data"]["project"]["name"])
        self.assertEqual(ws["A2"].value, "Week ending 23-10-2026")


# Real commitment words: publish drops any other word (store.COMMITMENTS), so a planted stray word would never reach the file and
# the "gone" assertions below would pass for the wrong reason. The kept use case carries one word, every hidden one another, and the
# base use case a third; no other cell of the planted project holds either of these two.
VISIBLE_FLAG, HIDDEN_FLAG = "Planned 2027", "Planned 2026"


class Flag(unittest.TestCase):
    """A use case's Commitment flag: present only for a kept use case."""

    def made(self, mutate=None):
        plant = fx.load()
        base = plant["data"]["use_cases"][0]
        extra = [("PUB-U-901", "ZQ-FLAG-EYEOFF", {"client_visible": 0}), ("PUB-U-902", "ZQ-FLAG-SENSITIVE", {}),
                 ("PUB-U-903", "ZQ-FLAG-ARCHIVED", {"archived": 1}), ("PUB-U-904", "ZQ-FLAG-VISIBLE", {})]
        for uid, title, over in extra:
            plant["data"]["use_cases"].append({**base, "id": uid, "title": title, "commitment": VISIBLE_FLAG if uid.endswith("904") else HIDDEN_FLAG, **over})
        plant["data"]["labels"]["PUB-U-902"] = ["Sensitive"]
        base["commitment"] = "Committed"
        if mutate:
            mutate(plant)
        fields = {**publish.PUBLISH_FIELDS, "use_cases": publish.PUBLISH_FIELDS["use_cases"] + ("commitment",)}
        with mock.patch.object(publish, "PUBLISH_FIELDS", fields):
            return parts_of(excel_client.workbook_bytes(selected(plant)))

    def test_flag_only_for_kept_use_cases(self):
        names, raw, wb, cells = self.made()
        everything = "\n".join(list(raw.values()) + cells + names)
        for gone in ("ZQ-FLAG-EYEOFF", "ZQ-FLAG-SENSITIVE", "ZQ-FLAG-ARCHIVED", "PUB-U-901", "PUB-U-902", "PUB-U-903", HIDDEN_FLAG):
            self.assertNotIn(gone, everything, gone)
        self.assertIn("ZQ-FLAG-VISIBLE", everything)
        self.assertIn(VISIBLE_FLAG, everything, "a visible use case's flag is published on purpose")
        self.assertIn("Commitment", [c.value for c in wb["Use cases"][4]])

    def test_archiving_it_removes_the_flag(self):
        def archive(plant):
            for u in plant["data"]["use_cases"]:
                if u["id"] == "PUB-U-904":
                    u["archived"] = 1
        names, raw, wb, cells = self.made(archive)
        self.assertNotIn(VISIBLE_FLAG, "\n".join(list(raw.values()) + cells))
        self.assertNotIn("ZQ-FLAG-VISIBLE", "\n".join(cells))

    def test_the_column_follows_the_whitelist(self):
        pub = selected(fx.load())
        _, _, wb, _ = parts_of(excel_client.workbook_bytes(pub))
        head = [c.value for c in wb["Use cases"][4]]
        self.assertEqual("Commitment" in head, "commitment" in publish.PUBLISH_FIELDS["use_cases"])
        for bad in ("Open work items", "Client-visible"):
            self.assertNotIn(bad, head)


class Growth(unittest.TestCase):
    """Making the workbook costs about the same per row at any size (the repo's growth check: t(4n) / t(n) at most GROWTH_LIMIT)."""

    @staticmethod
    def rows(n):
        plant = fx.load()
        base = plant["data"]["actions"][0]
        plant["data"]["actions"] = [{**base, "id": "PUB-A-%05d" % i, "description": "Action %d" % i, "client_message": "Client wording %d" % i,
                                     "milestone": None, "use_case": None} for i in range(n)]
        return fx.inputs(plant)

    def test_the_workbook_grows_in_step_with_the_rows(self):
        def work(n):
            inputs = self.rows(n)
            excel_client.embed(publish.add_glance(publish.select(inputs), inputs))
        assert_growth(self, work, 200, "client workbook")

    def test_the_embedded_size_grows_in_step_with_the_rows(self):
        def size(n):
            inputs = self.rows(n)
            return len(excel_client.embed(publish.add_glance(publish.select(inputs), inputs))["client_workbook"]["base64"])
        small, big = size(200), size(800)
        self.assertLess(big / small, 4.5, (small, big))


class Edges(unittest.TestCase):
    def test_no_client_visible_rows(self):
        plant = fx.load()
        for table in ("milestones", "actions", "raid", "decisions", "use_cases"):
            for row in plant["data"][table]:
                row["client_visible"] = 0
        pub = selected(plant)
        data = excel_client.workbook_bytes(pub)
        _, _, wb, cells = parts_of(data)
        self.assertEqual(wb["Actions"].max_row, 4, "the title band and the headings only")
        self.assertFalse([c for c in cells if c.startswith("PUB-")])

    def test_every_section_hidden(self):
        plant = fx.load()
        for s in plant["sections"]:
            s["hidden"] = 1
        data = excel_client.workbook_bytes(selected(plant))
        _, _, wb, cells = parts_of(data)
        self.assertEqual(len(wb.sheetnames), 1)
        self.assertFalse([c for c in cells if "ZQ-" in c])

    def test_a_hidden_section_has_no_sheet(self):
        plant = fx.load()
        for s in plant["sections"]:
            if s["type"] == "decisions":
                s["hidden"] = 1
        _, _, wb, cells = parts_of(excel_client.workbook_bytes(selected(plant)))
        self.assertNotIn("Decisions", wb.sheetnames)
        self.assertNotIn("ZQ-KEEP-DECISION-1", "\n".join(cells))

    def test_over_the_cap_the_note_is_carried_and_no_workbook(self):
        pub = selected(fx.load())
        with mock.patch.object(excel_client, "MAX_WORKBOOK_BYTES", 100):
            got = excel_client.embed(pub)
        self.assertEqual(got, {"client_workbook_too_large": True})
        self.assertIs(got["client_workbook_too_large"], True)

    def test_under_the_cap_the_shape(self):
        got = excel_client.embed(selected(fx.load()))
        self.assertEqual(set(got), {"client_workbook"})
        self.assertEqual(set(got["client_workbook"]), {"name", "base64"})
        self.assertTrue(got["client_workbook"]["name"].endswith(".xlsx"))
        self.assertTrue(re.fullmatch(r"[A-Za-z0-9+/=]+", got["client_workbook"]["base64"]))
        self.assertLess(excel_client.MAX_WORKBOOK_BYTES, publish.MAX_BYTES)


class Published(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.plant = rich_plant()
        self.store = open_store(fx.build_db(Path(tmp.name) / "clark.db", self.plant), onedrive_roots=[])
        self.addCleanup(self.store.close)
        self.day = self.plant["as_at"]

    def block(self, built):
        m = re.search(r'<script type="application/json" id="clark-data">(.*?)</script>', built["body"].decode("utf-8"), re.S)
        return json.loads(m.group(1))

    def test_off_is_the_bytes_of_today(self):
        a = publish.build(self.store, "PUB", self.day, EMPTY_BRANDING, number=1)
        b = publish.build(self.store, "PUB", self.day, EMPTY_BRANDING, number=1, workbook=False)
        self.assertEqual(a["body"], b["body"])
        self.assertFalse({"client_workbook", "client_workbook_too_large", "past_reports"} & set(self.block(a)["data"]))

    def test_on_embeds_a_workbook_equal_to_the_stand_alone_one(self):
        built = publish.build(self.store, "PUB", self.day, EMPTY_BRANDING, number=1, workbook=True)
        got = self.block(built)["data"]["client_workbook"]
        data = base64.b64decode(got["base64"], validate=True)
        self.assertEqual(data, excel_client.workbook_bytes(built["published"]))
        zipfile.ZipFile(io.BytesIO(data)).testzip()
        load_workbook(io.BytesIO(data))
        text = built["body"].decode("utf-8")
        self.assertEqual(publish.outside_addresses(text), [])
        for key, marker in self.plant["markers"].items():
            if key in ("outside_image", "script_in_text"):
                continue
            self.assertNotIn(marker, text, key)

    def test_page_without_workbook_text_is_the_same_page(self):
        a = publish.build(self.store, "PUB", self.day, EMPTY_BRANDING, number=1)
        b = publish.build(self.store, "PUB", self.day, EMPTY_BRANDING, number=1, workbook=True)
        cut = lambda built: re.sub(r'<script type="application/json" id="clark-data">.*?</script>', "", built["body"].decode("utf-8"), flags=re.S)
        self.assertEqual(cut(a), cut(b))

    def test_over_the_cap_the_publish_still_succeeds_with_the_note(self):
        with mock.patch.object(excel_client, "MAX_WORKBOOK_BYTES", 100):
            built = publish.build(self.store, "PUB", self.day, EMPTY_BRANDING, number=1, workbook=True)
        block = self.block(built)
        self.assertIs(block["data"]["client_workbook_too_large"], True)
        self.assertNotIn("client_workbook", block["data"])

    def test_a_workbook_that_cannot_be_made_does_not_stop_the_publish(self):
        with self.assertLogs("clark.publish", level="WARNING") as logged:
            with mock.patch.object(excel_client, "workbook_bytes", side_effect=ValueError("ZQ-ROW-TEXT")):
                built = publish.build(self.store, "PUB", self.day, EMPTY_BRANDING, number=1, workbook=True)
        self.assertEqual(len(logged.records), 1)
        self.assertIn("ValueError", logged.output[0])
        self.assertNotIn("ZQ-ROW-TEXT", logged.output[0], "the class name only, never the message")
        block = self.block(built)
        self.assertFalse({"client_workbook", "client_workbook_too_large"} & set(block["data"]))
        self.assertFalse({"workbook", "workbook_note"} & set(block))

    def test_the_flow_turns_it_on(self):
        self.assertIs(publish_flow.CLIENT_WORKBOOK, True)


if __name__ == "__main__":
    unittest.main()
