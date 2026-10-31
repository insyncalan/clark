"""The colours of the Excel and Word files are the committed look's own colours, and stay so.

Run: python3 dev/run_tests.py test_export_colours
excel_colours.TOKENS is a fixed table (a workbook cannot read a stylesheet), copied from the light values of
src/clark/brand/tokens.css. When the look changes, this test names the token whose hex to copy. The Word file takes its colours from
the same table, so it follows.
"""
import re
import unittest

from _paths import ROOT

from clark import docx_build, excel_colours

TOKENS_CSS = ROOT / "src" / "clark" / "brand" / "tokens.css"


def light_values():
    """{name: 'RRGGBB'} from the first :root block of tokens.css (the light look); only plain #rrggbb values."""
    css = TOKENS_CSS.read_text(encoding="utf-8")
    block = re.search(r":root\s*\{(.*?)\n\}", css, re.S).group(1)
    return {n: v.upper() for n, v in re.findall(r"(--[\w-]+):\s*#([0-9A-Fa-f]{6})\b", block)}


class ExportColours(unittest.TestCase):
    def test_every_colour_in_the_export_table_is_the_looks_light_value(self):
        css = light_values()
        css["--white"] = "FFFFFF"                     # tokens.css writes it as #fff
        wrong = {}
        for name, hexa in excel_colours.TOKENS.items():
            have = css.get(f"--{name}")
            if have is None:
                wrong[name] = "not in tokens.css"
            elif have != hexa:
                wrong[name] = f"table {hexa}, tokens.css {have}"
        self.assertEqual(wrong, {}, "the export table has drifted from tokens.css: copy the light value")

    def test_the_word_file_uses_the_same_table(self):
        self.assertEqual(docx_build.TOKENS, excel_colours.TOKENS)

    def test_the_old_demo_palette_is_gone_from_the_code(self):
        text = (ROOT / "src" / "clark" / "excel_colours.py").read_text(encoding="utf-8") + (ROOT / "src" / "clark" / "docx_build.py").read_text(encoding="utf-8")
        for old in ("14233A", "3B5BDB", "EDF1FF", "2A4FE0", "18232B", "D3D5D8"):
            self.assertNotIn(old, text)


if __name__ == "__main__":
    unittest.main()
