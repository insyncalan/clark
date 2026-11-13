"""Excel palette edges: the exact byte limit of a brand file and the exact 4.5:1 contrast boundary.

Run: python3 dev/run_tests.py test_excel_palette_edges
Every brand here is invented in a temporary folder.
"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
from clark import excel_palette as ep

HEAD = b":root { --brand-navy: #123456; }"


class BrandFileSize(unittest.TestCase):
    def folder(self, size):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        (d / "tokens.css").write_bytes(HEAD + b" " * (size - len(HEAD)))
        return d

    def test_a_file_of_exactly_the_limit_is_read(self):
        w = []
        p = ep.palette(branding=self.folder(256 * 1024), warnings=w)
        self.assertEqual(p.tokens["brand-navy"], "123456")
        self.assertEqual(w, [])

    def test_one_byte_over_the_limit_is_not_read(self):
        w = []
        p = ep.palette(branding=self.folder(256 * 1024 + 1), warnings=w)
        self.assertNotEqual(p.tokens["brand-navy"], "123456")
        self.assertEqual(len(w), 1)


class ContrastBoundary(unittest.TestCase):
    CSS = ":root { --brand-navy: #123456; --tone-urgent: #AA0000; }"

    def test_exactly_4_5_passes(self):
        w = []
        with mock.patch.object(ep, "contrast_ratio", return_value=ep.MIN_CONTRAST):
            p = ep.palette(css=self.CSS, warnings=w)
        self.assertEqual((p.tokens["brand-navy"], p.tokens["tone-urgent"]), ("123456", "AA0000"))
        self.assertEqual(w, [])

    def test_just_under_4_5_reverts_the_pair(self):
        w = []
        with mock.patch.object(ep, "contrast_ratio", return_value=ep.MIN_CONTRAST - 0.001):
            p = ep.palette(css=self.CSS, warnings=w)
        self.assertNotEqual(p.tokens["brand-navy"], "123456")
        self.assertTrue(w)


class Luminance(unittest.TestCase):
    def test_a_very_dark_channel_uses_the_linear_branch(self):
        self.assertAlmostEqual(ep.luminance("0A0A0A"), (10 / 255) / 12.92, places=9)
        self.assertAlmostEqual(ep.luminance("#000"), 0.0, places=9)
        self.assertAlmostEqual(ep.contrast_ratio("000000", "0A0A0A"), ((10 / 255) / 12.92 + 0.05) / 0.05, places=9)

    def test_a_light_channel_uses_the_power_branch(self):
        self.assertAlmostEqual(ep.luminance("808080"), ((128 / 255 + 0.055) / 1.055) ** 2.4, places=9)


class EmptyRoot(unittest.TestCase):
    def test_an_empty_light_block_is_readable_and_silent(self):
        w = []
        p = ep.palette(css=":root { }", warnings=w)
        self.assertEqual(w, [])
        self.assertEqual(p.tokens, ep.committed().tokens)

    def test_no_light_block_warns(self):
        w = []
        ep.palette(css=":root[data-theme=dark] { --brand-navy: #123456; }", warnings=w)
        self.assertEqual(len(w), 1)


class Cascade(unittest.TestCase):
    def test_a_revert_that_breaks_another_pair_is_followed_through(self):
        css = ":root { --brand-navy: #000000; --white: #202020; --brand-blue: #CCCCCC; }"
        w = []
        p = ep.palette(css=css, warnings=w)
        for f, t, _ in ep._pairs(p.colours):
            self.assertGreaterEqual(ep.contrast_ratio(p.tokens[f], p.tokens[t]), ep.MIN_CONTRAST, (f, t))
        self.assertEqual(p.tokens["white"], ep.committed().tokens["white"])
        self.assertEqual(p.tokens["brand-blue"], ep.committed().tokens["brand-blue"])
        self.assertGreaterEqual(len(w), 2)


class GenericFontCase(unittest.TestCase):
    def test_a_capitalised_generic_is_skipped(self):
        self.assertEqual(ep.palette(css=":root { --font-office: Sans-Serif, Verdana; }").font, "Verdana")
        self.assertEqual(ep.palette(css=":root { --font-office: SERIF, Verdana; }").font, "Verdana")


class NoteRules(unittest.TestCase):
    def test_no_font_declared_is_silent(self):
        w = []
        p = ep.palette(css=":root { --brand-navy: #123456; }", warnings=w)
        self.assertEqual((p.font, w), (ep.committed().font, []))

    def test_a_value_error_finding_the_brand_file_gives_the_committed_look(self):
        from clark import page
        w = []
        with mock.patch.object(page, "local_tokens_file", side_effect=ValueError("bad path")):
            p = ep.palette(branding=Path("/x"), warnings=w)
        self.assertEqual(p.tokens, ep.committed().tokens)
        self.assertEqual(len(w), 1)


class ExplicitEmptyCss(unittest.TestCase):
    def test_empty_css_does_not_read_the_local_brand(self):
        w = []
        with mock.patch.object(ep, "_brand_css", side_effect=AssertionError("read the local brand")):
            p = ep.palette(css="", warnings=w)
        self.assertEqual(p.tokens, ep.committed().tokens)
        self.assertEqual(len(w), 1)


class SeveralLightBlocks(unittest.TestCase):
    def test_every_light_block_counts_and_the_later_one_wins(self):
        p = ep.palette(css=":root { --brand-navy: #123456; --brand-blue: #0A7C74; } :root { --brand-blue: #0B5D8F; }")
        self.assertEqual((p.tokens["brand-navy"], p.tokens["brand-blue"]), ("123456", "0B5D8F"))


class WarningsOnPalette(unittest.TestCase):
    def test_the_palette_carries_every_note(self):
        w = []
        p = ep.palette(css=":root { --brand-navy: rgb(1,2,3); --brand-blue: hsl(1,2%,3%); --font-office: serif; }", warnings=w)
        self.assertGreaterEqual(len(w), 3)
        self.assertEqual(p.warnings, w)


class Frozen(unittest.TestCase):
    def test_a_palette_cannot_be_changed(self):
        import dataclasses
        with self.assertRaises(dataclasses.FrozenInstanceError):
            ep.committed().font = "Comic Sans"


if __name__ == "__main__":
    unittest.main()
