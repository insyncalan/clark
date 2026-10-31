"""The colours and fonts of the Word, Excel and email files are the committed look's own, read from it, and stay so.

Run: python3 dev/run_tests.py test_export_colours
src/clark/look.py reads src/clark/brand/tokens.css when clark starts; excel_colours.TOKENS, the Word file, the workbook's fonts and the
email take their values from it, so no hex or font name is written in those modules. This test reads tokens.css on its own and checks
that what they hold is what the look says, and that none of them writes a value of its own.
"""
import ast
import re
import unittest

from _paths import ROOT

from clark import docx_build, draft_email, excel, excel_colours, look

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
        self.assertEqual(wrong, {}, "the export table is not what tokens.css says")

    def test_the_word_file_uses_the_same_table(self):
        self.assertEqual(docx_build.TOKENS, excel_colours.TOKENS)

    def test_the_old_demo_palette_is_gone_from_the_code(self):
        text = (ROOT / "src" / "clark" / "excel_colours.py").read_text(encoding="utf-8") + (ROOT / "src" / "clark" / "docx_build.py").read_text(encoding="utf-8")
        for old in ("14233A", "3B5BDB", "EDF1FF", "2A4FE0", "18232B", "D3D5D8"):
            self.assertNotIn(old, text)


class FontsAndNothingWrittenByHand(unittest.TestCase):
    def test_the_office_font_and_the_email_families_are_what_the_look_says(self):
        css = TOKENS_CSS.read_text(encoding="utf-8")
        office = re.search(r"--font-office:\s*([^;]+);", css).group(1).strip()
        email = [f.strip() for f in re.search(r"--font-email:\s*([^;]+);", css).group(1).split(",")]
        self.assertEqual((docx_build.FONT, excel.COVER_FONT, excel.HISTORY_FONT), (office,) * 3)
        self.assertEqual(draft_email.FONT, f"font-family:{','.join(email)};font-size:11pt;")

    def test_the_email_is_drawn_in_the_looks_light_colours(self):
        c = draft_email.COLOURS
        for key, token in (("red", "status-red-text"), ("amber", "status-amber-text"), ("ink", "text"), ("muted", "text-muted"),
                           ("head", "grey-50"), ("rule", "grey-300"), ("white", "white")):
            self.assertEqual(c[key], "#" + light_values().get("--" + token, "FFFFFF"), key)

    def test_a_value_from_the_look_is_read_as_the_page_reads_it(self):
        css = ":root { --a: #fff; --b: var(--a); --c: #0e2430; --f: Calibri, 'Segoe UI', \"Arial\", sans-serif; }\n"
        self.assertEqual((look.colour("a", css=css), look.colour("--b", css=css), look.colour("c", css=css)), ("FFFFFF", "FFFFFF", "0E2430"))
        self.assertEqual(look.families("f", css=css), ["Calibri", "Segoe UI", "Arial", "sans-serif"])
        with self.assertRaises(KeyError):
            look.colour("no-such-token", css=css)
        with self.assertRaises(ValueError):
            look.colour("f", css=css)

    def test_a_font_with_markup_in_it_is_left_out(self):
        css = ':root { --f: Arial, x"/><w:evil/>, Calibri; }\n'
        self.assertEqual(look.families("f", css=css), ["Arial", "Calibri"])

    def test_no_hex_colour_or_font_name_is_written_in_these_modules(self):
        """Every string in the code (not a docstring or a comment) of the modules that make Word, Excel and email files."""
        hexa, font = re.compile(r"#[0-9A-Fa-f]{6}\b|(?:^|[\"'])[0-9A-Fa-f]{6}(?:$|[\"'])"), re.compile(r"\b(Arial|Calibri|Helvetica|Inter|Montserrat|Verdana)\b")
        for name in ("docx_build", "excel_colours", "excel", "excel_cover", "draft_email"):
            tree = ast.parse((ROOT / "src" / "clark" / f"{name}.py").read_text(encoding="utf-8"))
            docs = {id(n.body[0].value) for n in ast.walk(tree)
                    if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body and isinstance(n.body[0], ast.Expr)}
            strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]
            self.assertEqual([t for t in strings if hexa.search(t)], [], f"{name} writes a hex colour of its own")
            self.assertEqual([t for t in strings if font.search(t)], [], f"{name} writes a font name of its own")


if __name__ == "__main__":
    unittest.main()
