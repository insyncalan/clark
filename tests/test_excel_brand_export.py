"""Item 711 (4b): the workbook is drawn in the local brand's LIGHT values at export (excel_palette threaded through excel.py).

Run: python3 dev/run_tests.py test_excel_brand_export
Every brand here is invented in a temporary folder (light and dark blocks, same names, different values); nothing is read from system/branding.
"""
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

import _paths  # noqa: F401
import _publish_fixture as fx
from _demo import DemoStore
from openpyxl import load_workbook

from clark import excel, excel_colours as base, excel_palette as palette, publish_flow
from test_excel_picture import make_png

BRAND_ONE = """/* an invented teal look */
:root {
  --brand-navy: #0B2545; --brand-blue: #0A7C74; --brand-ink: #101820; --grey-300: #B8C4D0;
  --status-green-tint: #DDF5F0; --status-green-text: #046B5F; --tone-green-tint: #DDF5F0; --tone-green-text: #046B5F;
  --font-office: 'Segoe UI', sans-serif;
}
:root[data-theme=dark] { --brand-navy: #FFEEDD; --brand-blue: #AB1234; --font-office: Verdana; --status-green-tint: #123456; }
@media (prefers-color-scheme: dark) { :root { --brand-navy: #EEDDCC; --font-office: Tahoma; } }
"""
BRAND_TWO = """:root[data-theme=dark] { --brand-navy: #ABCDEF; --font-office: Tahoma; }
:root { --brand-navy: #1B1F3B; --brand-blue: #7A1FA2; --grey-50: #F4F4FA; --font-office: Georgia; }
"""
DARK_ONLY_VALUES = {"FFEEDD", "AB1234", "EEDDCC", "123456", "ABCDEF"}
DATA_SHEETS = ("Actions", "Risks & Issues", "Decisions", "Milestones", "Use cases")


def rgb(colour):
    v = getattr(colour, "rgb", None)
    return v[-6:].upper() if isinstance(v, str) else None


def harvest(path):
    """Every cell's fill colour, font colour and font name, by sheet and address: what a person sees."""
    wb = load_workbook(path)
    out = {}
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                out[(ws.title, c.coordinate)] = (rgb(c.fill.fgColor) if c.fill.fill_type else None, rgb(c.font.color), (c.font.name if c.value is not None else None),
                                                 rgb(c.border.left.color) if c.border.left and c.border.left.style else None)
    return wb, out


class Rig(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.dir = Path(tempfile.mkdtemp(prefix="clark-brandx-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.n = 0

    def brand(self, text=None, logo=False):
        d = self.dir / f"brand{self.n}"
        d.mkdir()
        if text is not None:
            (d / "tokens.css").write_text(text, encoding="utf-8")
        if logo:
            (d / "logo.png").write_bytes(make_png(60, 20))
        return d

    def export(self, branding):
        self.n += 1
        path = self.dir / f"w{self.n}.xlsx"
        w = []
        excel.export_project(self.demo.store, "ABC", path, self.dir / f"s{self.n}.json", on="2030-06-01", exported_by="Sam Example",
                             branding=branding, warnings=w)
        return path, w


class WithABrand(Rig):
    def check(self, text, navy, blue, font):
        path, w = self.export(self.brand(text))
        wb, cells = harvest(path)
        self.assertEqual(w, [])
        self.assertEqual(wb.sheetnames[0], "Cover")
        for name in DATA_SHEETS:
            head = wb[name]["A1"]
            self.assertEqual((rgb(head.fill.fgColor), head.font.name), (navy, font), name)
        hist, lists = wb["History"]["A2"], wb["Lists"]["A1"]
        self.assertEqual((rgb(hist.fill.fgColor), hist.font.name, rgb(lists.fill.fgColor), lists.font.name), (navy, font, navy, font))
        band = wb["Cover"]["A1"]
        self.assertEqual((rgb(band.fill.fgColor), band.font.name), (navy, font))
        self.assertEqual({c[2] for c in cells.values() if c[2]}, {font})                # every cell, every sheet, one font
        self.assertTrue(DARK_ONLY_VALUES.isdisjoint({v for c in cells.values() for v in c[:2] + c[3:] if v}))
        return wb, cells

    def test_brand_one_like(self):
        wb, cells = self.check(BRAND_ONE, "0B2545", "0A7C74", "Segoe UI")
        bars = {c[3] for (sheet, _), c in cells.items() if sheet == "Cover" and c[3]}
        self.assertTrue(bars)
        self.assertTrue(bars <= {base.TOKENS["status-red"], base.TOKENS["status-amber-text"], "046B5F", "B8C4D0"}, bars)                                       # the tile bars: the status tokens, or this brand's grey-300

    def test_a_branded_workbook_is_still_protected(self):
        path, _ = self.export(self.brand(BRAND_ONE, logo=True))
        wb = load_workbook(str(path))
        self.assertTrue(all(ws.protection.sheet for ws in wb.worksheets))
        self.assertTrue(wb["Cover"]["A1"].protection.locked)

    def test_brand_two_like(self):
        self.check(BRAND_TWO, "1B1F3B", "7A1FA2", "Georgia")

    def test_the_cover_headings_use_the_brand_blue(self):
        path, _ = self.export(self.brand(BRAND_TWO))
        with zipfile.ZipFile(path) as z:
            text = "".join(z.read(n).decode() for n in z.namelist() if n.startswith("xl/") and n.endswith(".xml"))
        self.assertIn("7A1FA2", text)

    def test_a_status_colour_reaches_the_conditional_formats(self):
        path, _ = self.export(self.brand(BRAND_ONE))
        with zipfile.ZipFile(path) as z:
            styles = z.read("xl/styles.xml").decode()
        self.assertIn("DDF5F0", styles)
        self.assertIn("046B5F", styles)

    def test_the_brand_logo_still_appears(self):
        path, _ = self.export(self.brand(BRAND_ONE, logo=True))
        with zipfile.ZipFile(path) as z:
            self.assertIn("xl/media/image1.png", z.namelist())
        self.assertEqual(rgb(load_workbook(path)["Cover"]["A1"].fill.fgColor), "0B2545")

    def test_a_bad_colour_falls_back_for_that_token_with_a_warning(self):
        d = self.brand(":root { --brand-navy: rgb(1, 2, 3); --grey-100: #E0EEFF; }")
        path, shown = self.export(d)
        w = palette.palette(branding=d).warnings          # the palette's own notes; none reach the person's warnings yet
        self.assertEqual(shown, [])
        wb, _ = harvest(path)
        self.assertEqual(rgb(wb["Actions"]["A1"].fill.fgColor), base.HEADER_FILL)
        self.assertEqual(rgb(wb["Lists"]["A1"].fill.fgColor), base.HEADER_FILL)
        self.assertEqual(len(w), 1)
        self.assertIn("brand-navy", w[0])

    def test_a_failing_pair_reverts(self):
        d = self.brand(":root { --brand-navy: #E0E0E0; --white: #FFFFFF; }")
        path, shown = self.export(d)
        w = palette.palette(branding=d).warnings
        self.assertEqual(shown, [])
        wb, _ = harvest(path)
        self.assertEqual((rgb(wb["Actions"]["A1"].fill.fgColor), rgb(wb["Actions"]["A1"].font.color)), (base.HEADER_FILL, base.HEADER_TEXT))
        self.assertEqual(len(w), 1)


class WithNoBrand(Rig):
    def test_no_brand_is_the_committed_look(self):
        for branding in (self.brand(None), self.dir / "absent"):
            path, w = self.export(branding)
            wb, cells = harvest(path)
            self.assertEqual(w, [])
            self.assertEqual(wb["Actions"]["A1"].font.name, excel.OFFICE_FONT)
            self.assertEqual((rgb(wb["Actions"]["A1"].fill.fgColor), rgb(wb["Actions"]["A1"].font.color)), (base.HEADER_FILL, base.HEADER_TEXT))
            self.assertEqual(rgb(wb["Cover"]["A1"].fill.fgColor), base.TOKENS["brand-navy"])
            self.assertEqual({c[2] for c in cells.values() if c[2]}, {excel.OFFICE_FONT})

    def test_a_brand_free_workbook_equals_one_made_with_the_module_defaults(self):
        path, _ = self.export(self.brand(None))
        default = self.dir / "default.xlsx"
        wb = excel.workbook("ABC", {}, "2030-06-01")                    # no palette: the module's own
        wb.save(default)
        a, b = harvest(path)[1], harvest(default)[1]
        for key in set(a) & set(b) & {k for k in b if k[0] in DATA_SHEETS + ("Lists",) and k[1].endswith("1")}:
            self.assertEqual(a[key], b[key], key)


class ThroughThePublisher(unittest.TestCase):
    """GET /api/export reaches the palette: Publisher passes its own branding to excel.export_project."""

    def test_the_publishers_branding_colours_the_download(self):
        tmp = Path(tempfile.mkdtemp(prefix="clark-brandx-pub-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        db = tmp / "clark.db"
        fx.build_db(db, fx.load())
        results = {}
        for name, css in (("none", None), ("one", BRAND_ONE), ("two", BRAND_TWO)):
            brand = tmp / name
            brand.mkdir()
            if css:
                (brand / "tokens.css").write_text(css, encoding="utf-8")
            pub = publish_flow.Publisher(db, [], today=lambda: "2026-10-28", by_user=lambda: "Sam Example", data_dir=tmp, branding=brand)
            status, body = pub.export("PUB")
            self.assertEqual(status, 200, body)
            out = tmp / f"{name}.xlsx"
            out.write_bytes(body["data"])
            ws = load_workbook(out)["Actions"]["A1"]
            results[name] = (rgb(ws.fill.fgColor), ws.font.name, body["warnings"])
        self.assertEqual(results["none"], (base.HEADER_FILL, excel.OFFICE_FONT, []))
        self.assertEqual(results["one"], ("0B2545", "Segoe UI", []))
        self.assertEqual(results["two"], ("1B1F3B", "Georgia", []))


class Polish(Rig):
    def test_the_palette_notes_are_logged_and_never_shown(self):
        brand = self.brand(":root { --brand-navy: rgb(1, 2, 3); }")
        with self.assertLogs("clark.excel", "WARNING") as logs:
            path, shown = self.export(brand)
        self.assertEqual(shown, [])                         # the list the person sees stays empty
        ours = [r for r in logs.records if "brand-navy" in r.getMessage()]
        self.assertEqual(len(ours), 1)
        self.assertEqual(ours[0].levelname, "WARNING")
        self.assertTrue(ours[0].getMessage().startswith("Brand colour brand-navy not used"))

    def test_a_brand_file_that_is_not_utf8_does_not_block_the_export(self):
        d = self.brand(None)
        (d / "tokens.css").write_bytes(b"\xff\xfe\x00")
        with self.assertLogs("clark.excel", "WARNING"):
            path, shown = self.export(d)
        self.assertEqual(shown, [])
        self.assertEqual(rgb(load_workbook(path)["Actions"]["A1"].fill.fgColor), base.HEADER_FILL)

    def test_no_note_is_logged_for_a_good_or_missing_brand(self):
        import logging
        with self.assertLogs("clark.excel", logging.WARNING) as logs:       # (assertNoLogs is Python 3.10+): only the sentinel may be logged
            logging.getLogger("clark.excel").warning("sentinel")
            self.export(self.brand(None))
        self.assertEqual([r.getMessage() for r in logs.records], ["sentinel"])

    def test_the_id_name_columns_wrap_and_the_rest_are_unchanged(self):
        rows = {"milestones": [{"id": "M1", "name": "Go live"}], "use_cases": [{"id": "U1", "title": "Pay"}],
                "actions": [{"id": "A1", "description": "d", "milestone": "M1", "use_case": "U1", "owner": "Kim"}],
                "raid": [{"id": "R1", "description": "d", "milestone": "M1", "use_case": "U1", "response_action": "r"}],
                "decisions": [{"id": "D1", "decision": "d", "milestone": "M1", "use_case": "U1"}]}
        wb = excel.workbook("ABC", rows, "2030-06-01")
        for sheet in ("Actions", "Risks & Issues", "Decisions"):
            ws = wb[sheet]
            heads = {c.value: c.column_letter for c in ws[1]}
            for name in [n for n in ("Milestone", "Use case") if n in heads]:
                cell = ws[f"{heads[name]}2"]
                self.assertTrue(cell.alignment.wrap_text, (sheet, name))
                self.assertEqual(cell.alignment.vertical, "top")
                self.assertEqual(ws.column_dimensions[heads[name]].width, 40)
            self.assertEqual(ws[f"{heads['Use case']}2"].value, "U1: Pay")
            for name in ("ID", "Owner", "Labels"):
                if name in heads:
                    self.assertFalse(ws[f"{heads[name]}2"].alignment.wrap_text, (sheet, name))
            self.assertEqual(ws.auto_filter.ref[:2], "A1")
            self.assertEqual(len([r for r in ws.row_dimensions.values() if r.height]), 0)     # no fixed row height: Excel fits wrapped rows
        raid = wb["Risks & Issues"]
        heads = {c.value: c.column_letter for c in raid[1]}
        self.assertTrue(raid[f"{heads['Response action']}2"].alignment.wrap_text)
        self.assertEqual(raid.column_dimensions[heads["Response action"]].width, 48)


class CoverGutter(unittest.TestCase):
    def test_this_week_and_next_week_have_a_two_column_gutter_with_no_rule_across_it(self):
        from openpyxl import Workbook
        wb = Workbook()
        excel.write_cover(wb, [{"kind": "pair", "text": "", "left": {"title": "This week", "text": "A"}, "right": {"title": "Next week", "text": "B"}}])
        ws = wb["Cover"]
        spans = sorted((r.min_col, r.max_col) for r in ws.merged_cells.ranges)
        self.assertEqual(spans, [(1, 5), (1, 5), (8, 12), (8, 12)])
        for col in (6, 7):
            self.assertIsNone(ws.cell(row=2, column=col).border.bottom.style)
        self.assertEqual(ws.cell(row=2, column=1).border.bottom.style, "thin")
        self.assertEqual(ws.cell(row=2, column=8).border.bottom.style, "thin")


if __name__ == "__main__":
    unittest.main()
