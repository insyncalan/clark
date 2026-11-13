"""Item 711 (4a): the Excel palette reads the local brand over the committed look (clark.excel_palette), pure and uncached.

Run: python3 dev/run_tests.py test_excel_palette
Every brand here is invented in a temporary folder; nothing is read from or written to branding.
"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
from clark import excel_colours as base
from clark import excel_palette as ep

BRAND_ONE = """/* an invented teal look */
:root {
  --brand-navy: #0B2545; --brand-blue: #0A7C74; --brand-ink: #101820;
  --tone-green-tint: #DDF5F0; --tone-green-text: #046B5F;
  --teal: #13A89E; --status-blue-text: var(--teal-dark); --teal-dark: #0A6F68;
  --font-office: 'Segoe UI', sans-serif;
}
"""
BRAND_TWO = """:root { --brand-navy: #1B1F3B; --white: #FFF; --brand-blue: #7A1FA2; --grey-100: #EEE; --grey-700: #444;
  --font-office: Georgia; }
"""
NOWHERE = Path("/nonexistent-brand-folder")


def contrast_ok(p):
    return all(ep.contrast_ratio(p.tokens[f], p.tokens[t]) >= 4.5 for f, t, _ in ep._pairs(p.colours))


class Committed(unittest.TestCase):
    def check_default(self, p):
        self.assertEqual(p.tokens, base.TOKENS)
        self.assertEqual(p.colours, base.COLOURS)
        self.assertEqual((p.header_fill, p.header_text, p.late_text), (base.HEADER_FILL, base.HEADER_TEXT, base.LATE_TEXT))
        self.assertEqual(p.font, ep.look.office_font())
        self.assertEqual(p.warnings, [])
        for name in base.COLOURS:
            self.assertEqual(p.hexes(name), base.hexes(name))
        self.assertEqual(len(p.tokens), len(base.TOKEN_NAMES))

    def test_no_brand_is_the_module_constants(self):
        self.check_default(ep.palette(branding=NOWHERE))

    def test_empty_branding_dir(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        self.check_default(ep.palette(branding=d))

    def test_committed_pairs_pass(self):
        self.assertTrue(contrast_ok(ep.palette(branding=NOWHERE)))

    def test_contrast_ratio(self):
        self.assertAlmostEqual(ep.contrast_ratio("#000", "#FFFFFF"), 21.0)
        self.assertAlmostEqual(ep.contrast_ratio("FFFFFF", "ffffff"), 1.0)


class Brands(unittest.TestCase):
    def brand(self, text):
        d = Path(tempfile.mkdtemp(prefix="clark-pal-"))
        self.addCleanup(shutil.rmtree, d, True)
        (d / "tokens.css").write_text(text, encoding="utf-8")
        return d

    def test_brand_one_like_brand_from_a_folder(self):
        w = []
        p = ep.palette(branding=self.brand(BRAND_ONE), warnings=w)
        self.assertEqual(p.header_fill, "0B2545")
        self.assertEqual(p.tokens["brand-blue"], "0A7C74")
        self.assertEqual(p.hexes("green"), ("DDF5F0", "046B5F"))
        self.assertEqual(p.tokens["status-blue-text"], "0A6F68")        # a var() chain through a brand-only name
        self.assertEqual(p.tokens["grey-100"], base.TOKENS["grey-100"])  # untouched names stay committed
        self.assertEqual(p.font, "Segoe UI")
        self.assertEqual(p.warnings, w)
        self.assertTrue(contrast_ok(p))

    def test_brand_two_like_brand_three_digit_hex(self):
        p = ep.palette(branding=self.brand(BRAND_TWO))
        self.assertEqual(p.header_text, "FFFFFF")
        self.assertEqual(p.header_fill, "1B1F3B")
        self.assertEqual(p.tokens["grey-100"], "EEEEEE")
        self.assertEqual(p.tokens["grey-700"], "444444")
        self.assertEqual(p.font, "Georgia")
        self.assertEqual(p.warnings, [])
        self.assertTrue(contrast_ok(p))

    def test_only_some_tokens(self):
        p = ep.palette(css=":root { --brand-navy: #123456; }")
        self.assertEqual(p.header_fill, "123456")
        self.assertEqual({k: v for k, v in p.tokens.items() if k != "brand-navy"},
                         {k: v for k, v in base.TOKENS.items() if k != "brand-navy"})
        self.assertEqual(p.font, ep.look.office_font())

    def test_function_colours_fall_back_per_token_with_a_warning(self):
        for bad in ("rgb(10, 20, 30)", "hsl(200, 50%, 20%)", "color-mix(in srgb, #000, #fff 20%)"):
            w = []
            p = ep.palette(css=":root { --brand-navy: %s; --grey-100: #DDEEFF; }" % bad, warnings=w)
            self.assertEqual(p.header_fill, base.HEADER_FILL, bad)
            self.assertEqual(p.tokens["grey-100"], "DDEEFF", bad)         # the other token is kept
            self.assertEqual(len(w), 1, bad)
            self.assertIn("brand-navy", w[0])
            self.assertEqual(p.warnings, w)

    def test_a_failing_status_pair_reverts_as_a_pair(self):
        w = []
        p = ep.palette(css=":root { --tone-amber-tint: #FFFF00; --tone-amber-text: #FFFF99; --tone-red-tint: #FFEEEE; }", warnings=w)
        self.assertEqual(p.hexes("amber"), base.hexes("amber"))      # both reverted, not only the text
        self.assertEqual(p.tokens["tone-red-tint"], "FFEEEE")      # a passing pair elsewhere is kept
        self.assertEqual(len(w), 1)
        self.assertIn("tone-amber-tint", w[0])

    def test_a_failing_header_pair_reverts_both(self):
        p = ep.palette(css=":root { --brand-navy: #DDDDDD; --white: #FFFFFF; }")
        self.assertEqual((p.header_fill, p.header_text), (base.HEADER_FILL, base.HEADER_TEXT))
        self.assertTrue(p.warnings)

    def test_a_failing_cover_pair_reverts(self):
        p = ep.palette(css=":root { --status-red: #FF9999; }")        # the white-on-red INTERNAL tag
        self.assertEqual(p.tokens["status-red"], base.TOKENS["status-red"])

    def test_the_cover_subtitle_pair_reverts_as_a_pair(self):
        w = []
        p = ep.palette(css=":root { --grey-100: #1F4050; --brand-navy: #0B2545; }", warnings=w)      # light text gone dark on the band
        self.assertEqual(p.tokens["grey-100"], base.TOKENS["grey-100"])
        self.assertEqual(p.tokens["brand-navy"], base.TOKENS["brand-navy"])
        self.assertTrue(any("subtitle" in x for x in w), w)       # the grey status pair fails too, with its own note

    def test_the_cover_tile_pair_reverts_as_a_pair(self):
        w = []
        p = ep.palette(css=":root { --brand-ink: #CCCCCC; --grey-50: #F4F4FA; }", warnings=w)
        self.assertEqual((p.tokens["brand-ink"], p.tokens["grey-50"]), (base.TOKENS["brand-ink"], base.TOKENS["grey-50"]))
        self.assertEqual(len(w), 1)
        self.assertIn("tiles", w[0])

    def test_passing_cover_pairs_keep_the_brand_values(self):
        w = []
        p = ep.palette(css=":root { --brand-navy: #0B2545; --grey-100: #EEEEEE; --brand-ink: #101820; --grey-50: #F4F4FA; }", warnings=w)
        self.assertEqual((p.tokens["grey-100"], p.tokens["brand-ink"], p.tokens["grey-50"]), ("EEEEEE", "101820", "F4F4FA"))
        self.assertEqual(w, [])

    def test_a_generic_or_bad_font(self):
        self.assertEqual(ep.palette(css=":root { --font-office: sans-serif, Calibri; }").font, "Calibri")
        w = []
        p = ep.palette(css=":root { --font-office: serif; }", warnings=w)
        self.assertEqual(p.font, ep.look.office_font())
        self.assertEqual(len(w), 1)
        self.assertEqual(ep.palette(css=":root { --font-office: 'Bad<Name', Verdana; }").font, "Verdana")

    def test_a_font_name_over_excels_31_characters_is_refused(self):
        w = []
        long = "A" * 32
        p = ep.palette(css=":root { --font-office: %s; }" % long, warnings=w)
        self.assertEqual(p.font, ep.look.office_font())
        self.assertEqual(len(w), 1)
        self.assertEqual(ep.palette(css=":root { --font-office: %s; }" % ("B" * 31)).font, "B" * 31)

    def test_a_brand_file_that_cannot_be_read_gives_the_committed_look_and_a_note(self):
        for data in (b"\xff\xfe\x00", b":root { --brand-navy: #123456; }" + b" " * ep.MAX_BRAND_BYTES):
            d = Path(tempfile.mkdtemp())
            self.addCleanup(shutil.rmtree, d, True)
            (d / "tokens.css").write_bytes(data)
            p = ep.palette(branding=d)
            self.assertEqual(p.tokens, base.TOKENS)
            self.assertEqual(len(p.warnings), 1)
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        (d / "tokens.css").write_text(":root { --brand-navy: #123456; }", encoding="utf-8")
        real = Path.read_text

        def read(self, *a, **k):
            if self.parent == d:
                raise OSError("denied")
            return real(self, *a, **k)
        with mock.patch.object(Path, "read_text", read):
            p = ep.palette(branding=d)
        self.assertEqual((p.tokens, len(p.warnings)), (base.TOKENS, 1))

    def test_unreadable_brand_text(self):
        p = ep.palette(css="nothing here")
        self.assertEqual(p.tokens, base.TOKENS)
        self.assertEqual(len(p.warnings), 1)

    def test_no_cache_between_calls(self):
        a = ep.palette(css=":root { --brand-navy: #0B2545; }")
        b = ep.palette(css=":root { --brand-navy: #1B1F3B; }")
        c = ep.palette(branding=NOWHERE)
        self.assertEqual((a.header_fill, b.header_fill, c.header_fill), ("0B2545", "1B1F3B", base.HEADER_FILL))
        self.assertEqual(base.TOKENS["brand-navy"], base.HEADER_FILL)        # the module constants are not touched

    def test_never_writes_to_disk(self):
        d = self.brand(BRAND_ONE)
        before = sorted(p.name for p in d.iterdir())
        real_open = open

        def guarded(f, mode="r", *a, **k):
            self.assertFalse(set(mode) & set("wax+"), f"{f} opened for writing")
            return real_open(f, mode, *a, **k)
        with mock.patch("builtins.open", guarded), mock.patch.object(Path, "write_text", side_effect=AssertionError), \
                mock.patch.object(Path, "write_bytes", side_effect=AssertionError), mock.patch.object(Path, "mkdir", side_effect=AssertionError):
            ep.palette(branding=d)
            ep.palette(css=BRAND_TWO)
        self.assertEqual(sorted(p.name for p in d.iterdir()), before)


class LightOnly(unittest.TestCase):
    LIGHT = ":root { --brand-navy: #0B2545; --grey-100: #DDEEFF; --font-office: Georgia; }"
    DARK = ":root[data-theme=dark] { --brand-navy: #FFEEDD; --grey-100: #101010; --font-office: Verdana; }"
    MEDIA = "@media (prefers-color-scheme: dark) { :root { --brand-navy: #EEDDCC; --grey-100: #202020; --font-office: Tahoma; } }"

    def check_light(self, css):
        w = []
        p = ep.palette(css=css, warnings=w)
        self.assertEqual((p.header_fill, p.tokens["grey-100"], p.font), ("0B2545", "DDEEFF", "Georgia"), css)
        self.assertEqual(w, [], css)

    def test_dark_after_light(self):
        self.check_light(self.LIGHT + "\n" + self.DARK + "\n" + self.MEDIA)

    def test_dark_before_light(self):
        self.check_light(self.MEDIA + "\n" + self.DARK + "\n" + self.LIGHT)

    def test_closing_braces_on_one_line(self):
        self.check_light("/* c */ " + self.LIGHT + " " + self.DARK + " " + self.MEDIA)

    def test_only_a_dark_block_is_the_committed_look(self):
        for css in (self.DARK, self.MEDIA, self.DARK + self.MEDIA):
            w = []
            p = ep.palette(css=css, warnings=w)
            self.assertEqual(p.tokens, base.TOKENS)
            self.assertEqual(p.font, ep.look.office_font())
            self.assertEqual(len(w), 1)         # one note that no light block was found, none per dark value


class PlainWarningWording(unittest.TestCase):
    """Warnings reach the page's Excel export unchanged, so they use no file or code words."""

    def test_warnings_use_plain_words(self):
        w = []
        ep.palette(css="body{}", warnings=w)
        w2 = []
        ep.palette(css=":root { --brand-navy: nonsense; }", warnings=w2)
        self.assertTrue(w and w2)
        for text in w + w2:
            for word in ("tokens", "committed", "not used ("):
                self.assertNotIn(word, text)


class LastDeclarationNoSemicolon(unittest.TestCase):
    """A brand's last colour with no closing semicolon is valid CSS: it is read, and an unreadable one still gets its warning."""

    def test_unreadable_last_colour_is_warned_not_dropped(self):
        warnings = []
        ep.palette(css=":root{--brand-navy:#ffffff}", warnings=warnings)
        self.assertTrue(any("brand-navy" in w for w in warnings), warnings)

    def test_last_colour_without_semicolon_is_used(self):
        p = ep.palette(css=":root{--brand-blue:#0A7C74}")
        self.assertEqual(p.tokens["brand-blue"], "0A7C74")


if __name__ == "__main__":
    unittest.main()
