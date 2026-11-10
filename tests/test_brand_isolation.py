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

    def test_the_pdf_marker_check_reads_the_same_folder_as_the_build(self):
        import inspect
        from clark import publish_pdf
        src = inspect.getsource(publish_pdf.Step.prepare)
        self.assertNotIn("page_html(pub.branding", src)
        self.assertIn("project_brand", src)


class Word(Rig):
    def test_the_signature_takes_a_branding_folder(self):
        import inspect
        self.assertIn("branding", inspect.signature(word_route._do_export).parameters)
        self.assertIn("brand_root", inspect.signature(word_route.make_word_export).parameters)

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


if __name__ == "__main__":
    unittest.main()
