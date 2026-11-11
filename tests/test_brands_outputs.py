"""#944 track T4 (FIXTURES): each output takes the brand of the project it is made for, and no other.

Run: python3 dev/run_tests.py test_brands_outputs
Two invented brands (ZEBRA teal, QUOKKA plum) and Generic (no brand folder) are made in a temporary folder with generated PNGs; nothing is
read from system/branding. A test that passes today pins what already works per call (Excel takes a `branding` folder; Word takes
`colours=`; page_html and brand_picture take a folder). A test marked expectedFailure is the NEW wiring the design note has not yet
shaped: it flips to "unexpected success" when built, and that is the signal to remove the mark. A test skipped for a missing seam names
the seam. No assertion here weakens another file.
Guarded files the real wiring touches: excel*, docx_build, word_route, publish*, server.py (csp, picture route), page/__init__.py.
"""
import base64
import inspect
import io
import json
import re
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

import _paths  # noqa: F401
import _publish_fixture as fx
from openpyxl import load_workbook

from clark import changes, docx_build, publish_flow, excel, excel_client, excel_cover as cover, excel_palette, page, publish
from clark import server as sv
from clark.store import open_store
from _demo import USER, DemoStore
from test_excel_picture import make_png, PROJECT, STAMP

SRC = Path(__file__).resolve().parent.parent / "src" / "clark"
OWN_ICON = (SRC / "page" / "assets" / "clark-icon-512.png").read_bytes()

# Distinct colours that are in no committed token, and pass the 4.5:1 pair rule against white (so the palette keeps them).
BRANDS = {
    "zebra": {"navy": "0B3D3A", "blue": "127A72", "font": "Georgia", "logo": make_png(60, 20), "wave": make_png(90, 30),
              "cover": make_png(31, 17)},
    "quokka": {"navy": "3B1048", "blue": "8A2FA0", "font": "Verdana", "logo": make_png(64, 24), "wave": make_png(96, 32),
               "cover": make_png(37, 19)},
}
CSS = ":root {{ --brand-navy: #{navy}; --brand-blue: #{blue}; --font-office: '{font}', sans-serif; }}\n"


def make_brand(root, name):
    """system/branding/<name>/ as T2 will lay it out: tokens.css, both picture conventions (the Excel logo and wave, the served cover)."""
    b = BRANDS[name]
    d = Path(root) / name
    (d / "assets").mkdir(parents=True)
    (d / "tokens.css").write_text(CSS.format(**b), encoding="utf-8")
    (d / "logo.png").write_bytes(b["logo"])
    (d / "assets" / "cover-wave.png").write_bytes(b["wave"])
    (d / "assets" / "cover.png").write_bytes(b["cover"])
    return d


class Rig(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-t4-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.zebra, self.quokka = make_brand(self.dir, "zebra"), make_brand(self.dir, "quokka")
        self.generic = self.dir / "generic-has-no-folder"          # Generic = no folder at all (branding_base -> None -> clark's icon)
        self.n = 0

    def other(self, name):
        return BRANDS["quokka" if name == "zebra" else "zebra"]


class ExcelCover(Rig):
    """Output 1: the Excel Cover's icon (excel_picture.load / load_wave, excel.export)."""

    def cover_zip(self, branding):
        self.n += 1
        path = self.dir / f"w{self.n}.xlsx"
        lines = cover.lines(project=dict(PROJECT, week_ending="2026-10-30", client_name="Sample Client"), sections=[], tiles=[],
                            exported=STAMP, by="Sam Example", internal="")
        excel.export(path, "DEMO", {}, self.dir / f"s{self.n}.json", on="2030-06-01", cover=lines, branding=branding)
        z = zipfile.ZipFile(path)
        return path, {n: z.read(n) for n in z.namelist() if n.startswith("xl/media/")}

    def test_each_brand_draws_its_own_logo_and_wave_and_never_the_others(self):
        for name, folder in (("zebra", self.zebra), ("quokka", self.quokka)):
            _, media = self.cover_zip(folder)
            got = set(media.values())
            self.assertEqual(got, {BRANDS[name]["logo"], BRANDS[name]["wave"]}, name)
            self.assertTrue(got.isdisjoint({self.other(name)["logo"], self.other(name)["wave"], OWN_ICON}), name)

    def test_generic_shows_clarks_own_icon_and_no_brand_picture(self):
        _, media = self.cover_zip(self.generic)
        self.assertEqual(list(media.values()), [OWN_ICON])

    def test_the_cover_band_is_the_brands_navy_and_the_other_brands_is_absent(self):
        for name, folder in (("zebra", self.zebra), ("quokka", self.quokka)):
            path, _ = self.cover_zip(folder)
            fill = load_workbook(path)["Cover"]["A1"].fill.fgColor.rgb[-6:].upper()
            self.assertEqual(fill, BRANDS[name]["navy"], name)
            raw = "".join(zipfile.ZipFile(path).read(n).decode("utf-8", "replace") for n in ("xl/styles.xml",))
            self.assertNotIn(self.other(name)["navy"], raw.upper(), name)

    def test_branding_none_is_the_local_folder_so_generic_must_be_passed_as_a_missing_folder(self):
        # Pins the leak the note must close: branding=None means page.BRANDING (the person's own folder), NOT Generic.
        from unittest import mock
        with mock.patch.object(page, "BRANDING", self.zebra):
            _, media = self.cover_zip(None)
        self.assertIn(BRANDS["zebra"]["logo"], media.values())


class WorkbookPalette(Rig):
    """Output 3, the local work-items workbook: excel_palette per call (already per brand)."""

    def test_each_brand_has_its_own_header_fill_and_font_and_generic_the_committed_one(self):
        for name, folder in (("zebra", self.zebra), ("quokka", self.quokka)):
            pal = excel_palette.palette(branding=folder)
            self.assertEqual((pal.header_fill, pal.font), (BRANDS[name]["navy"], BRANDS[name]["font"]), name)
        pal = excel_palette.palette(branding=self.generic)
        self.assertEqual(pal.header_fill, excel_client.colours.HEADER_FILL)
        self.assertNotIn(pal.header_fill, (BRANDS["zebra"]["navy"], BRANDS["quokka"]["navy"]))

    def test_a_second_call_with_another_brand_leaks_nothing_from_the_first(self):
        a = excel_palette.palette(branding=self.zebra)
        b = excel_palette.palette(branding=self.quokka)
        self.assertNotEqual(a.tokens["brand-navy"], b.tokens["brand-navy"])
        self.assertEqual(excel_palette.palette(branding=self.zebra).tokens, a.tokens)


class Word(Rig):
    """Output 2: Word colours. docx_build.build(colours=) exists and nobody passes it (word_route.py:544)."""

    def published(self):
        return publish.select(fx.inputs())

    def styles(self, colours):
        z = zipfile.ZipFile(io.BytesIO(docx_build.build(self.published(), colours=colours)))
        return z.read("word/styles.xml").decode() + z.read("word/footer1.xml").decode()

    def test_the_brand_palette_reaches_the_word_styles_and_the_other_brand_does_not(self):
        for name, folder in (("zebra", self.zebra), ("quokka", self.quokka)):
            text = self.styles(excel_palette.palette(branding=folder).tokens).upper()
            self.assertIn(BRANDS[name]["navy"], text, name)
            self.assertNotIn(self.other(name)["navy"], text, name)

    def test_generic_word_has_neither_brand_colour(self):
        text = self.styles(excel_palette.palette(branding=self.generic).tokens).upper()
        for b in BRANDS.values():
            self.assertNotIn(b["navy"], text)

    def test_word_carries_no_picture_and_no_brand_name_or_id(self):
        data = docx_build.build(self.published(), colours=excel_palette.palette(branding=self.zebra).tokens)
        z = zipfile.ZipFile(io.BytesIO(data))
        names = z.namelist()
        # The report draws two pictures of its own data (the Gantt and a progress bar, docx_build `images`), not a brand picture.
        self.assertEqual([n for n in names if n.startswith("word/media")], ["word/media/image1.png", "word/media/image2.png"], names)
        brand_pictures = {b[k] for b in BRANDS.values() for k in ("logo", "wave", "cover")} | {OWN_ICON}
        self.assertTrue(brand_pictures.isdisjoint({z.read(n) for n in names if n.startswith("word/media")}))
        self.assertNotIn(b"zebra", b"".join(zipfile.ZipFile(io.BytesIO(data)).read(n) for n in names).lower())

    def test_NEW_word_route_builds_with_the_projects_brand(self):
        # word_route.py:544 is docx_build.build(published) with no colours. Needs a seam from project -> brand folder in _do_export
        # (name unknown until the design note settles it); this checks the file only, through the existing build() signature.
        self.assertIn("branding", inspect.signature(__import__("clark.word_route", fromlist=["x"])._do_export).parameters)


class ClientWorkbook(Rig):
    """Output 3b: the workbook embedded in the published page (excel_client; PALETTE fixed at import, excel_client.py:37)."""

    def setUp(self):
        super().setUp()
        self.plant = fx.load()
        self.store = open_store(fx.build_db(self.dir / "clark.db", self.plant), onedrive_roots=[])
        self.addCleanup(self.store.close)

    def header_fill(self, branding):
        built = publish.build(self.store, "PUB", self.plant["as_at"], branding, number=1, workbook=True)
        m = re.search(r'<script type="application/json" id="clark-data">(.*?)</script>', built["body"].decode("utf-8"), re.S)
        data = base64.b64decode(json.loads(m.group(1))["data"]["client_workbook"]["base64"])
        wb = load_workbook(io.BytesIO(data))
        return wb.worksheets[0]["A1"].fill.fgColor.rgb[-6:].upper(), data

    def test_NEW_each_brand_colours_its_own_client_workbook_and_no_logo(self):
        for name, folder in (("zebra", self.zebra), ("quokka", self.quokka)):
            fill, data = self.header_fill(folder)
            self.assertEqual(fill, BRANDS[name]["navy"], name)
            self.assertFalse([n for n in zipfile.ZipFile(io.BytesIO(data)).namelist() if n.startswith("xl/media")])
            self.assertNotIn(self.other(name)["navy"].encode(), zipfile.ZipFile(io.BytesIO(data)).read("xl/styles.xml").upper())

    def test_NEW_generic_client_workbook_is_committed_after_a_branded_one_in_the_same_process(self):
        self.header_fill(self.zebra)
        fill, _ = self.header_fill(self.generic)
        self.assertEqual(fill, excel_client.colours.HEADER_FILL.upper())
        self.assertNotEqual(fill, BRANDS["zebra"]["navy"])
        self.assertIn("palette", " ".join(inspect.signature(excel_client.workbook_bytes).parameters))     # the note's seam: per call


class PageAndPictures(Rig):
    """Output 4 and 5: the published page's brand block, the picture per brand, the csp."""

    def test_the_published_page_carries_the_brands_look_and_never_the_other_or_the_id(self):
        for name, folder in (("zebra", self.zebra), ("quokka", self.quokka)):
            html = page.page_html(folder, view=True)
            self.assertIn(BRANDS[name]["navy"], html.upper(), name)
            self.assertEqual(html.count('id="brand-local"'), 1)
            self.assertNotIn(self.other(name)["navy"], html.upper(), name)
            self.assertNotIn(f"/{name}/", html)
            self.assertNotIn(name + "/", html)       # the brand id is not a published field (owner answer Q3)

    def test_generic_page_has_no_brand_block(self):
        html = page.page_html(self.generic, view=True)
        self.assertNotIn('id="brand-local"', html)
        for b in BRANDS.values():
            self.assertNotIn(b["navy"], html.upper())

    def test_the_picture_seam_serves_each_brands_cover_and_a_missing_folder_serves_none(self):
        for name, folder in (("zebra", self.zebra), ("quokka", self.quokka)):
            self.assertEqual(page.brand_picture("cover.png", folder), (BRANDS[name]["cover"], "image/png"), name)
        self.assertIsNone(page.brand_picture("cover.png", self.generic))

    def test_csp_img_src_already_admits_any_path_under_assets_so_an_id_segment_needs_no_csp_change(self):
        # Pins the premise check: img-src is the prefix http://<host>/assets/ (server.py:364), which covers /assets/<id>/cover.png.
        # test_server.py:710 pins the exact list; if the note keeps the prefix, csp_policy and that pin stay as they are.
        policy = sv.csp_policy("<html></html>", "127.0.0.1:8766")
        img = re.search(r"img-src ([^;]*)", policy).group(1).split()
        self.assertIn("http://127.0.0.1:8766" + sv.BRAND_PREFIX, img)
        self.assertTrue(("/assets/zebra/cover.png").startswith(sv.BRAND_PREFIX))

    def test_NEW_the_route_dispatches_a_brand_id_segment_only_for_an_installed_brand(self):
        # Built (server.py dispatcher, two parts only; test_brand_route.py runs the route). Pins the shape: brand_picture_route takes the id.
        self.assertIn("brand_id", inspect.signature(sv.brand_picture_route).parameters)


class ProjectBrandT1(Rig):
    """What #944 T1 (merged, layout 20) now gives: projects.brand, written only by changes.py, never published. Real API, no seam."""

    def setUp(self):
        super().setUp()
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store

    def test_a_project_has_a_brand_id_that_is_generic_until_changed(self):
        self.assertEqual(self.s.read("projects", ref="ABC")["brand"], "generic")
        self.assertIn("generic", changes.brand_ids())

    def test_the_brand_id_is_stored_per_project_through_the_one_writer_and_is_not_published(self):
        from unittest import mock
        with mock.patch.object(changes, "brand_ids", lambda: {"generic", "zebra"}):
            status, body = changes.make_change(self.s.path, [], USER)(
                {"project": "ABC", "kind": "projects", "op": "update", "changes": {"brand": "zebra"}})
        self.assertEqual(status, 200, body)
        self.assertEqual(self.s.read("projects", ref="ABC")["brand"], "zebra")
        self.assertNotIn(b"zebra", json.dumps(publish.select(fx.inputs()), default=str).lower().encode())

    def test_NEW_publisher_resolves_the_projects_brand_folder_instead_of_one_fixed_branding(self):
        # publish_flow.Publisher passes self.branding (one folder, set at launch) to publish.build and excel.export_project for every
        # project (publish_flow.py:263/620). T4 must pass the folder of the project's brand id; the resolver (T2's library) is not built.
        self.assertRegex(inspect.getsource(publish_flow.Publisher), r"\[.brand.\]|project_brand|\.brand\b")
