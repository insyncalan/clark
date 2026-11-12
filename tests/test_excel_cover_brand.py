"""Issue 735: the Excel Cover's logo, cover picture (wave), dark band, larger title and long date.

Run: python3 dev/run_tests.py test_excel_cover_brand
Every brand here is invented in a temporary folder with generated PNGs; nothing is read from branding.
A logo and a cover picture load ONLY from the branding folder; with no folder clark's own icon is the logo; a folder with no
logo gives a Cover with no logo; there is never a default wave.
"""
import os
import re
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
from openpyxl import load_workbook

from clark import excel, excel_cover as cover, excel_picture as pic, page
from test_excel_picture import make_png, PROJECT, STAMP

SRC = Path(__file__).resolve().parent.parent / "src" / "clark"
OWN = SRC / "page" / "assets" / "clark-icon-512.png"
LOGO = make_png(60, 20)
WAVE = make_png(90, 30)
OTHER = make_png(10, 10)         # a picture that is neither: for outside the folder


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-cvb-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.brand = self.dir / "branding"
        self.brand.mkdir()
        self.state = self.dir / "state.json"

    def export(self, branding, name="w.xlsx", warnings=None):
        self.path = self.dir / name
        lines = cover.lines(project=dict(PROJECT, week_ending="2026-10-30", client_name="Sample Client"), sections=[], tiles=[],
                            exported=STAMP, by="Sam Example", internal="")
        excel.export(self.path, "DEMO", {}, self.state, on="2030-06-01", cover=lines, branding=branding, warnings=warnings)
        return zipfile.ZipFile(self.path)

    def images(self, z):
        return {n: z.read(n) for n in z.namelist() if n.startswith("xl/media/")}

    def cover_sheet(self, branding):
        self.export(branding)
        return load_workbook(self.path)["Cover"]

    def put_wave(self, data=WAVE):
        (self.brand / "assets").mkdir(exist_ok=True)
        (self.brand / "assets" / "cover-wave.png").write_bytes(data)


class LogoRule(Base):
    def test_a_no_folder_shows_clarks_own_logo(self):
        missing = self.dir / "nothing-here"
        z = self.export(missing)
        self.assertEqual(list(self.images(z).values()), [OWN.read_bytes()])
        self.assertEqual(pic.load(missing)[0], OWN.read_bytes())

    def test_a_no_folder_at_all_by_default_is_clarks_own_logo(self):
        with mock.patch.object(page, "BRANDING", self.dir / "absent"):
            self.assertEqual(pic.load()[0], OWN.read_bytes())

    def test_b_a_folder_with_a_logo_shows_that_logo(self):
        (self.brand / "logo.png").write_bytes(LOGO)
        self.assertEqual(list(self.images(self.export(self.brand)).values()), [LOGO])

    def test_b_the_assets_logo_is_found(self):
        (self.brand / "assets").mkdir()
        (self.brand / "assets" / "logo-mark.png").write_bytes(LOGO)
        self.assertEqual(list(self.images(self.export(self.brand)).values()), [LOGO])

    def test_c_a_folder_without_a_logo_has_no_logo_and_not_clarks_mark(self):
        z = self.export(self.brand)
        self.assertEqual(self.images(z), {})
        self.assertNotIn("<drawing ", z.read("xl/worksheets/sheet1.xml").decode())
        self.assertIsNone(pic.load(self.brand))

    def test_c_a_folder_with_a_refused_logo_has_no_logo_and_not_clarks_mark(self):
        (self.brand / "logo.png").write_bytes(b"not a picture")
        said = []
        with self.assertLogs("clark.excel", "WARNING"):
            z = self.export(self.brand, warnings=said)
        self.assertEqual(self.images(z), {})
        self.assertEqual(len(said), 1)
        self.assertTrue(said[0].startswith("The brand logo was not used"))

    def test_d_a_symlink_to_a_logo_outside_the_folder_is_never_read(self):
        outside = self.dir / "outside.png"
        outside.write_bytes(OTHER)
        (self.brand / "assets").mkdir()
        try:
            os.symlink(outside, self.brand / "logo.png")
        except (OSError, NotImplementedError):
            self.skipTest("no symlinks here")
        os.symlink(outside, self.brand / "assets" / "logo-x.png")
        os.symlink(outside, self.brand / "assets" / "cover-x.png")
        self.assertIsNone(pic.local_logo(self.brand))
        self.assertIsNone(pic.local_wave(self.brand))
        self.assertEqual(self.images(self.export(self.brand)), {})

    def test_d_a_symlinked_folder_pointing_out_is_never_read(self):
        outside = self.dir / "elsewhere"
        outside.mkdir()
        (outside / "logo-a.png").write_bytes(OTHER)
        (outside / "cover-a.png").write_bytes(OTHER)
        try:
            os.symlink(outside, self.brand / "assets")
        except (OSError, NotImplementedError):
            self.skipTest("no symlinks here")
        self.assertIsNone(pic.local_logo(self.brand))
        self.assertIsNone(pic.local_wave(self.brand))

    def test_d_a_file_beside_the_folder_or_reached_with_dotdot_is_not_a_way_in(self):
        (self.dir / "logo.png").write_bytes(OTHER)          # beside the brand folder, not in it
        self.assertIsNone(pic.local_logo(self.brand))
        self.assertEqual(self.images(self.export(self.brand)), {})

    def test_the_own_logo_goes_through_the_same_safe_loader(self):
        with mock.patch.object(pic, "read_size", wraps=pic.read_size) as rs:
            got = pic.load(self.dir / "absent")
        rs.assert_called_once()
        self.assertEqual(got[1:], (512, 512))
        self.assertTrue(pic.own_logo().is_relative_to(page.HERE))


class Wave(Base):
    def test_e_a_cover_picture_is_drawn_below_the_subtitle(self):
        (self.brand / "logo.png").write_bytes(LOGO)
        self.put_wave()
        z = self.export(self.brand)
        self.assertEqual(sorted(self.images(z).values()), sorted([LOGO, WAVE]))
        drawing = z.read("xl/drawings/drawing1.xml").decode()
        self.assertEqual(drawing.count("<xdr:pic>"), 2)
        self.assertIn("<xdr:row>2</xdr:row>", drawing, "the picture row is under the title and the subtitle")
        self.assertEqual(z.read("xl/drawings/_rels/drawing1.xml.rels").decode().count("<Relationship "), 2)
        ws = load_workbook(self.path)["Cover"]
        self.assertEqual(ws.row_dimensions[3].height, pic.WAVE_ROW_POINTS)
        self.assertEqual(ws.freeze_panes, "A4")

    def test_e_a_cover_picture_without_a_logo_is_drawn_alone(self):
        self.put_wave()
        self.assertEqual(list(self.images(self.export(self.brand)).values()), [WAVE])

    def test_e_no_cover_picture_means_none_and_never_a_default(self):
        (self.brand / "logo.png").write_bytes(LOGO)
        z = self.export(self.brand)
        self.assertEqual(list(self.images(z).values()), [LOGO])
        self.assertEqual(z.read("xl/drawings/drawing1.xml").decode().count("<xdr:pic>"), 1)
        self.assertEqual(load_workbook(self.path).worksheets[0].freeze_panes, "A3")
        z = self.export(self.dir / "absent", "x.xlsx")
        self.assertEqual(list(self.images(z).values()), [OWN.read_bytes()], "no folder: clark's icon, still no wave")
        self.assertEqual(z.read("xl/drawings/drawing1.xml").decode().count("<xdr:pic>"), 1)
        self.assertIsNone(pic.local_wave(self.dir / "absent"))
        with mock.patch.object(page, "BRANDING", self.dir / "absent"):
            self.assertIsNone(pic.local_wave())

    def test_e_a_non_png_cover_picture_is_refused_in_words_and_the_export_goes_on(self):
        self.put_wave(b"<svg></svg>")
        said = []
        with self.assertLogs("clark.excel", "WARNING") as logs:
            z = self.export(self.brand, warnings=said)
        self.assertIn("The brand cover picture was not used, so the Cover has no picture: cover-wave.png is not a PNG picture.",
                      logs.output[0])
        self.assertEqual(len(said), 1)
        self.assertEqual(self.images(z), {})
        self.assertTrue(self.path.exists())

    def test_e_an_oversized_cover_picture_is_refused_in_words(self):
        self.put_wave(make_png(3000, 10))
        with self.assertLogs("clark.excel", "WARNING") as logs:
            z = self.export(self.brand)
        self.assertIn("3000 by 10 pixels", logs.output[0])
        self.assertEqual(self.images(z), {})
        self.put_wave(WAVE + b"\0" * pic.MAX_BYTES)
        with self.assertLogs("clark.excel", "WARNING") as logs:
            self.export(self.brand, "y.xlsx")
        self.assertIn("too big", logs.output[0])


class Band(Base):
    def test_f_the_title_is_larger_and_the_band_has_a_distinct_edge(self):
        ws = self.cover_sheet(self.brand)
        self.assertEqual(ws["A1"].font.size, excel.COVER_TITLE_SIZE)
        self.assertGreater(excel.COVER_TITLE_SIZE, 16)
        self.assertEqual(ws["A2"].font.size, excel.COVER_SUBTITLE_SIZE)
        self.assertGreater(excel.COVER_SUBTITLE_SIZE, excel.COVER_SIZE)
        navy = excel.colours.TOKENS["brand-navy"]
        for ref in ("A1", "A2"):
            self.assertEqual(ws[ref].fill.fgColor.rgb[-6:], navy, ref)
        self.assertEqual(ws["A2"].border.bottom.style, "thick")
        self.assertEqual(ws["A2"].border.bottom.color.rgb[-6:], excel.colours.TOKENS["brand-blue"], "a palette token")
        self.assertIsNone(getattr(ws["A1"].border.bottom, "style", None))

    def test_f_with_a_cover_picture_the_edge_is_under_the_picture_row(self):
        self.put_wave()
        ws = self.cover_sheet(self.brand)
        self.assertIsNone(getattr(ws["A2"].border.bottom, "style", None))
        self.assertEqual(ws["A3"].border.bottom.style, "thick")
        self.assertEqual(ws["A3"].fill.fgColor.rgb[-6:], excel.colours.TOKENS["brand-navy"])

    def test_f_the_subtitle_has_the_long_date(self):
        got = cover.subtitle({"week_ending": "2026-10-30", "client_name": "Sample Client"})
        self.assertEqual(got, "Weekly report · Week ending Friday 30 October 2026 · for Sample Client")
        self.assertEqual(cover.long_date("2026-01-05"), "Monday 5 January 2026")
        self.assertEqual(cover.long_date("not a day"), "not a day")
        self.assertEqual(cover.long_date(""), "")
        self.assertEqual(cover.subtitle({}), "Weekly report")

    def test_f_the_workbook_cell_says_it(self):
        ws = self.cover_sheet(self.brand)
        self.assertEqual(ws["A2"].value, "Weekly report · Week ending Friday 30 October 2026 · for Sample Client")


class NotOnThePublishedPage(unittest.TestCase):
    """g: the logo and the cover picture are for the local workbook only."""

    def test_only_the_local_export_reads_the_brand_pictures(self):
        users = [p.name for p in sorted(SRC.rglob("*.py"))
                 if re.search(r"excel_picture|local_logo|local_wave|load_wave|own_logo", p.read_text(encoding="utf-8"))]
        self.assertEqual(users, ["brands.py", "excel.py", "excel_picture.py"])      # #944: brands.py only checks a brand picture's size when installing

    def test_the_client_workbook_the_publisher_and_the_word_file_draw_no_picture(self):
        for name in ("excel_client.py", "publish.py", "publish_flow.py", "publish_pdf.py", "published_copies.py", "docx_build.py"):
            text = (SRC / name).read_text(encoding="utf-8")
            self.assertNotRegex(text, r"excel_picture|local_logo|local_wave|load_wave|own_logo|xl/media", name)

    def test_the_public_copy_holds_no_brand_picture(self):
        names = [p.name for p in SRC.rglob("*") if p.is_file()]
        self.assertFalse([n for n in names if re.match(r"(logo|cover)-.*\.png$", n)])


if __name__ == "__main__":
    unittest.main()
