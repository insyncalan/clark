"""Row 999 (guarded): every output takes the brand of the project it is made for, and no other: the web page, the preview, the Excel
workbook, the client workbook inside the page, the PDF's marker check and the Word file. Run: python3 dev/run_tests.py test_brand_isolation
Two invented brands (ZEBRA teal, QUOKKA plum) are installed in a temporary folder (system/branding/<id>/ with a manifest); nothing is
read from the real system/branding. A project on Generic gets the committed look. The brand's id and name appear in no output.
"""
import base64
import io
import json
import re
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
import _publish_fixture as fx
from _demo import DemoStore, USER
from test_brands_outputs import BRANDS, make_brand
from openpyxl import load_workbook

from clark import brands, changes, docx_build, page, publish, publish_flow, word_route
from clark.store import open_store

IDS = {"generic", "zebra", "quokka"}


def install(root, name):
    d = make_brand(Path(root) / "system" / "branding", name)
    (d / brands.MANIFEST).write_text(json.dumps({"id": name, "name": name.title() + " Co", "version": "1.0.0"}), encoding="utf-8")
    return d


class Rig(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="clark-iso-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.zebra, self.quokka = install(self.root, "zebra"), install(self.root, "quokka")
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store

    def set_brand(self, brand):
        with mock.patch.object(changes, "brand_ids", lambda: IDS):
            status, body = changes.make_change(self.s.path, [], USER)(
                {"project": "ABC", "kind": "projects", "op": "update", "changes": {"brand": brand}})
        self.assertEqual(status, 200, body)

    def publisher(self):
        return publish_flow.Publisher(self.s.path, [], by_user=lambda: USER, data_dir=self.s.path.parent, brand_root=self.root)


class Publisher(Rig):
    def test_the_projects_brand_folder_is_found_at_each_call(self):
        pub = self.publisher()
        self.assertEqual(pub.project_brand(self.s, "ABC"), page.NO_BRAND)          # generic until changed
        self.set_brand("zebra")
        self.assertEqual(pub.project_brand(self.s, "ABC"), self.zebra)
        self.set_brand("quokka")
        self.assertEqual(pub.project_brand(self.s, "ABC"), self.quokka)
        self.set_brand("generic")
        self.assertEqual(pub.project_brand(self.s, "ABC"), page.NO_BRAND)

    def test_a_removed_brand_or_unknown_code_is_the_plain_page(self):
        self.set_brand("zebra")
        shutil.rmtree(self.zebra)
        self.assertEqual(self.publisher().project_brand(self.s, "ABC"), page.NO_BRAND)
        self.assertEqual(self.publisher().project_brand(self.s, "NOPE"), page.NO_BRAND)

    def test_an_explicit_branding_still_wins(self):
        pub = publish_flow.Publisher(self.s.path, [], branding=self.quokka, data_dir=self.s.path.parent, brand_root=self.root)
        self.set_brand("zebra")
        self.assertEqual(pub.project_brand(self.s, "ABC"), self.quokka)

    def test_the_pdf_marker_check_reads_the_projects_own_folder(self):
        from clark import publish_pdf, pdf
        pub = self.publisher()
        real, seen = page.page_html, []

        def spy(branding, *a, **k):
            seen.append(branding)
            return real(branding, *a, **k)
        for brand, folder in (("zebra", self.zebra), ("quokka", self.quokka), ("generic", page.NO_BRAND)):
            self.set_brand(brand)
            built = publish.build(self.s, "ABC")
            seen.clear()
            with mock.patch.object(page, "page_html", spy), mock.patch.object(pdf, "find_chrome", lambda: None):
                got = publish_pdf.Step({}, pub).prepare(pub, self.root / "x.html", built, "2026-10-29", self.s, "ABC", None, None)
            self.assertEqual(got[0], 409, got)          # stops at the Chrome check, after the marker check ran
            self.assertEqual(seen, [folder], brand)

    def test_preview_and_export_are_made_with_the_projects_brand(self):
        from clark import excel
        pub = self.publisher()
        real_build, real_export = publish.build, excel.export_project
        seen = {"build": [], "export": []}

        def build(store, code, now=None, branding=None, *a, **k):
            seen["build"].append(branding)
            return real_build(store, code, now, branding, *a, **k)

        def export(*a, **k):
            seen["export"].append(k.get("branding"))
            return real_export(*a, **k)
        for brand, folder in (("zebra", self.zebra), ("quokka", self.quokka), ("generic", page.NO_BRAND)):
            self.set_brand(brand)
            seen["build"].clear(), seen["export"].clear()
            with mock.patch.object(publish, "build", build), mock.patch.object(excel, "export_project", export):
                pub.preview({"project": "ABC"})
                pub.export("ABC")
            self.assertEqual(seen["build"], [folder], brand)
            self.assertEqual(seen["export"], [folder], brand)

    def test_a_publish_builds_and_checks_markers_with_the_projects_brand(self):
        local = self.root / "Local"
        local.mkdir()
        client = self.root / "Client"
        client.mkdir()
        self.demo.update("projects", "ABC", {"publish_client": str(client)})
        pub = publish_flow.Publisher(self.s.path, [], choose_save_file=lambda prompt, name, start=None: local / name,
                                     today=lambda: "2026-10-29", by_user=lambda: USER, data_dir=self.s.path.parent, brand_root=self.root)
        real_build, real_html = publish.build, page.page_html
        built_with, html_with = [], []

        def build(store, code, now=None, branding=None, *a, **k):
            built_with.append(branding)
            return real_build(store, code, now, branding, *a, **k)

        def html(branding, *a, **k):
            html_with.append(branding)
            return real_html(branding, *a, **k)
        self.set_brand("zebra")
        with mock.patch.object(publish, "build", build), mock.patch.object(page, "page_html", html):
            got = pub.publish({"project": "ABC", "to_client": True})
        self.assertTrue(built_with, got)
        self.assertEqual(set(map(str, built_with)), {str(self.zebra)})
        self.assertEqual(set(map(str, html_with)), {str(self.zebra)})


class Word(Rig):
    def test_each_brand_colours_its_own_word_file_and_not_the_others(self):
        for name in ("zebra", "quokka"):
            self.set_brand(name)
            colours = word_route.brand_colours(self.s, "ABC", self.root)
            got = docx_build.palette(colours)
            self.assertEqual(got["brand-navy"], BRANDS[name]["navy"].upper(), name)
            other = BRANDS["quokka" if name == "zebra" else "zebra"]["navy"].upper()
            z = zipfile.ZipFile(io.BytesIO(docx_build.build(publish.select(fx.inputs()), colours=colours)))
            raw = "".join(z.read(n).decode("utf-8", "replace") for n in z.namelist() if n.endswith(".xml")).upper()
            self.assertIn(BRANDS[name]["navy"].upper(), raw)
            self.assertNotIn(other, raw)
            self.assertNotIn(name.upper() + " CO", raw)

    def test_generic_is_the_committed_colours_after_a_branded_one(self):
        self.set_brand("zebra")
        word_route.brand_colours(self.s, "ABC", self.root)
        self.set_brand("generic")
        self.assertEqual(docx_build.palette(word_route.brand_colours(self.s, "ABC", self.root)), docx_build.palette())

    def test_a_word_export_saves_with_the_projects_brand(self):
        self.set_brand("zebra")
        out = Path(tempfile.mkdtemp(prefix="clark-iso-out-"))
        self.addCleanup(shutil.rmtree, out, True)
        seam = word_route.make_word_export(self.s.path, [], USER, today=lambda: "2026-10-29", choose_folder=lambda prompt: out,
                                           brand_root=self.root)
        status, body = seam({"project": "ABC"})
        self.assertEqual(status, 200, body)
        z = zipfile.ZipFile(next(out.rglob("*.docx")))
        raw = "".join(z.read(n).decode("utf-8", "replace") for n in z.namelist() if n.endswith(".xml")).upper()
        self.assertIn(BRANDS["zebra"]["navy"].upper(), raw)
        self.assertNotIn(BRANDS["quokka"]["navy"].upper(), raw)


class ClientWorkbook(Rig):
    def setUp(self):
        super().setUp()
        self.plant = fx.load()
        self.db = open_store(fx.build_db(self.root / "clark.db", self.plant), onedrive_roots=[])
        self.addCleanup(self.db.close)

    def fill(self, branding):
        built = publish.build(self.db, "PUB", self.plant["as_at"], branding, number=1, workbook=True)
        m = re.search(r'<script type="application/json" id="clark-data">(.*?)</script>', built["body"].decode("utf-8"), re.S)
        data = base64.b64decode(json.loads(m.group(1))["data"]["client_workbook"]["base64"])
        return load_workbook(io.BytesIO(data)).worksheets[0]["A1"].fill.fgColor.rgb[-6:].upper()

    def test_each_brand_colours_its_workbook_and_generic_is_committed_in_the_same_process(self):
        from clark import excel_client
        self.assertEqual(self.fill(self.zebra), BRANDS["zebra"]["navy"])
        self.assertEqual(self.fill(self.quokka), BRANDS["quokka"]["navy"])
        self.assertEqual(self.fill(page.NO_BRAND), excel_client.colours.HEADER_FILL.upper())
        self.assertEqual(self.fill(self.zebra), BRANDS["zebra"]["navy"])

    def test_title_sub_and_header_text_take_the_palette_and_the_gantt_sheet_too(self):
        from clark import excel_client
        pal = {"fill": "112233", "text": "445566"}
        published = publish.select(fx.inputs())
        wb = load_workbook(io.BytesIO(excel_client.workbook_bytes(published, pal)))
        seen = set()
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for c in row:
                    if c.font and c.font.color is not None and c.value not in (None, ""):
                        seen.add(c.font.color.rgb[-6:].upper() if isinstance(c.font.color.rgb, str) else None)
        self.assertIn("445566", seen)
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for c in row:
                    if c.fill.fgColor.rgb and c.fill.fill_type == "solid":
                        self.assertEqual(c.fill.fgColor.rgb[-6:].upper(), "112233", (ws.title, c.coordinate))
                    if c.value not in (None, "") and c.font.bold and c.font.color is not None and isinstance(c.font.color.rgb, str):
                        self.assertEqual(c.font.color.rgb[-6:].upper(), "445566", (ws.title, c.coordinate))
        for ws in wb.worksheets:                       # the title and sub-title lines are in the palette text colour too
            for c in (ws["A1"], ws["A2"]):
                if c.value not in (None, "") and c.font.color is not None and isinstance(c.font.color.rgb, str):
                    self.assertEqual(c.font.color.rgb[-6:].upper(), "445566", (ws.title, c.coordinate))

    def test_the_branded_pair_text_is_the_brands_not_the_committed_one(self):
        from clark import excel_client
        cream = self.root / "cream"
        cream.mkdir()
        (cream / "tokens.css").write_text(":root { --brand-navy: #0B3D3A; --white: #FFFFF0; }\n", encoding="utf-8")
        got = excel_client.palette_of(cream)
        self.assertEqual(got, {"fill": "0B3D3A", "text": "FFFFF0"})

    def test_the_gantt_sheet_takes_the_palette(self):
        from clark import excel_client
        published = publish.select(fx.inputs())
        published["data"]["gantt"] = {"tab_name": "Plan", "columns": ["name", "start", "end", "pct"], "lines": [
            {"id": "G1", "name": "Build", "start": "2026-10-01", "end": "2026-10-20", "pct": 50}]}
        published["tabs"] = [*published["tabs"], "gantt"]      # row 1068: the sheet follows the tab, as a real publish with the switch on lists it
        wb = load_workbook(io.BytesIO(excel_client.workbook_bytes(published, {"fill": "112233", "text": "445566"})))
        ws = wb["Plan"]
        self.assertEqual(ws["A1"].fill.fgColor.rgb[-6:].upper(), "112233")
        self.assertEqual(ws["A4"].fill.fgColor.rgb[-6:].upper(), "112233")
        self.assertEqual(ws["A1"].font.color.rgb[-6:].upper(), "445566")
        self.assertEqual(ws["A4"].font.color.rgb[-6:].upper(), "445566")


class FakeStore:
    def __init__(self, row=None, exc=None):
        self.row, self.exc = row, exc

    def read(self, table, ref=None):
        if self.exc:
            raise self.exc
        return self.row


class Hostile(Rig):
    """Row 999, adversarial: hostile brand ids and codes, an unreadable row, a hostile token file, the client page's own words."""

    def test_hostile_brand_ids_in_the_row_never_leave_the_branding_folder(self):
        for bad in ("../zebra", "zebra/../quokka", "ZEBRA", "zebra\n", " zebra", "zebra\x00", "\u017eebra", "a" * 5000, "assets",
                    "design-system", ".", "..", 5, ["zebra"], {"id": "zebra"}, True):
            got = publish_flow.brand_of(FakeStore({"brand": bad}), "ABC", self.root)
            self.assertIs(got, page.NO_BRAND, repr(bad)[:40])

    def test_hostile_project_codes_give_the_plain_page_and_never_raise(self):
        self.set_brand("zebra")
        for bad in (None, 5, b"ABC", ["ABC"], "", "../../etc", "ABC\x00", "\u00c5BC", "A" * 100000, "abc", "ABC; DROP TABLE projects"):
            self.assertIs(publish_flow.brand_of(self.s, bad, self.root), page.NO_BRAND, repr(bad)[:30])

    def test_an_unreadable_row_is_the_plain_page_not_a_failed_publish(self):
        import sqlite3
        for exc in (sqlite3.OperationalError("database is locked"), sqlite3.DatabaseError("malformed"), KeyError("brand")):
            self.assertIs(publish_flow.brand_of(FakeStore(exc=exc), "ABC", self.root), page.NO_BRAND, type(exc).__name__)
        for row in (None, [], "zebra", {"brand": None}, {"brand": ""}, {}):
            self.assertIs(publish_flow.brand_of(FakeStore(row), "ABC", self.root), page.NO_BRAND, repr(row))

    def test_a_hostile_token_file_gives_a_plain_colour_pair_in_the_client_workbook(self):
        from clark import excel_client
        committed = {"fill": excel_client.colours.HEADER_FILL, "text": excel_client.colours.HEADER_TEXT}
        evil = self.root / "evil"
        (evil / "assets").mkdir(parents=True)
        (evil / "tokens.css").write_text(":root{--brand-navy:red;}</style><script>x</script>;--white:#zzzzzz;--brand-ink:url(x);"
                                         "--brand-navy:#" + "f" * 4000 + ";}", encoding="utf-8")
        for folder in (evil, self.root / "missing", page.NO_BRAND, None):
            pal = excel_client.palette_of(folder)
            for k in ("fill", "text"):
                self.assertRegex(pal[k], r"^[0-9A-Fa-f]{6}$", (str(folder), k))
        self.assertEqual(excel_client.palette_of(page.NO_BRAND), committed)
        from openpyxl import Workbook
        wb = Workbook()
        excel_client.write_sheet(wb, publish.select(fx.inputs()), "actions", excel_client.palette_of(evil))   # must not raise

    def test_the_branded_client_page_names_no_brand_and_carries_no_other_brands_colour(self):
        plant = fx.load()
        db = open_store(fx.build_db(self.root / "h.db", plant), onedrive_roots=[])
        self.addCleanup(db.close)
        for name, other in (("zebra", "quokka"), ("quokka", "zebra")):
            built = publish.build(db, "PUB", plant["as_at"], getattr(self, name), number=1, workbook=True)
            raw = built["body"].decode("utf-8", "replace")
            low = raw.lower()
            self.assertNotIn(other, low)
            self.assertNotIn(name + " co", low)
            self.assertNotIn(str(self.root).lower(), low)           # no path of the branding folder in the client file
            self.assertNotIn("system/branding", low)


if __name__ == "__main__":
    unittest.main()
