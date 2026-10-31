"""The colours and fonts of the Word, Excel and email files are the committed look's own, read from it, and stay so.

Run: python3 dev/run_tests.py test_export_colours
src/clark/look.py reads src/clark/brand/tokens.css when clark starts; excel_colours.TOKENS, the Word file, the workbook's fonts and the
email take their values from it, so no hex or font name is written in those modules. This test reads tokens.css on its own and checks
that what they hold is what the look says, and that none of them writes a value of its own.
"""
import ast
import re
import unittest
from unittest import mock

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
            want = "FFFFFF" if token == "white" else light_values()["--" + token]       # tokens.css writes --white as #fff
            self.assertEqual(c[key], "#" + want, key)

    def test_a_value_from_the_look_is_read_as_the_page_reads_it(self):
        css = ":root { --a: #fff; --b: var(--a); --c: #0e2430; --f: Calibri, 'Segoe UI', \"Arial\", sans-serif; }\n"
        self.assertEqual((look.colour("a", css=css), look.colour("--b", css=css), look.colour("c", css=css)), ("FFFFFF", "FFFFFF", "0E2430"))
        self.assertEqual(look.families("f", css=css), ["Calibri", "Segoe UI", "Arial", "sans-serif"])
        with self.assertRaises(look.LookError):
            look.colour("no-such-token", css=css)
        with self.assertRaises(look.LookError):
            look.colour("f", css=css)

    def test_a_font_with_markup_in_it_is_left_out(self):
        css = ':root { --f: Arial, x"/><w:evil/>, Calibri; }\n'
        self.assertEqual(look.families("f", css=css), ["Arial", "Calibri"])

    def test_a_token_that_refers_to_itself_is_one_plain_error_naming_it(self):
        for css in (":root { --a: var(--b); --b: var(--a); }\n", ":root { --a: var(--a); }\n"):
            with self.assertRaises(look.LookError) as got:
                look.colour("a", css=css)
            self.assertIn("--a refers back to itself", str(got.exception))

    def test_an_empty_font_token_or_one_with_no_usable_name_is_one_plain_error_naming_it(self):
        for value in ("", " ", '"/><w:evil/>', ", ,"):
            css = ":root { --font-office: %s; --font-email: Calibri; }\n" % value
            with self.assertRaises(look.LookError) as got:
                look.office_font(css)
            self.assertIn("--font-office", str(got.exception))
        with self.assertRaises(look.LookError) as got:
            look.office_font(":root { --font-email: Calibri; }\n")
        self.assertIn("no token named --font-office", str(got.exception))

    def test_a_missing_look_file_is_one_plain_error_naming_the_file(self):
        with mock.patch.object(look, "TOKENS_CSS", ROOT / "no-such-folder" / "tokens.css"):
            for call in (lambda: look.colour("brand-navy"), look.office_font, look.email_font_family):
                with self.assertRaises(look.LookError) as got:
                    call()
                self.assertIn("brand/tokens.css", str(got.exception))

    def test_a_css_with_no_block_is_one_plain_error(self):
        with self.assertRaises(look.LookError):
            look.colour("a", css="nothing here")

    def test_the_committed_look_still_reads_as_before(self):
        self.assertEqual((look.colour("brand-navy"), look.colour("white"), look.colour("border"), look.office_font()),
                         ("062F3A", "FFFFFF", "C4CEE3", "Arial"))
        self.assertEqual(look.colour("brand-navy", "dark"), "04202A")

    def test_no_hex_colour_or_font_name_is_written_in_these_modules(self):
        """Every string in the code (not a docstring or a comment) of the modules that make Word, Excel and email files."""
        for name in ("docx_build", "excel_colours", "excel", "excel_cover", "draft_email"):
            found = written_by_hand((ROOT / "src" / "clark" / f"{name}.py").read_text(encoding="utf-8"))
            self.assertEqual(found, [], f"{name} writes a colour or font name of its own")

    def test_the_scan_finds_each_kind_of_hand_written_value(self):
        for code in ("x = '#fff'", "x = '#ffff'", "x = '#A3301F'", "x = '112233ff'", "x = 'A3301F'", "x = 'rgb(1,2,3)'",
                     "x = 'rgba(1, 2, 3, .5)'", "x = 'Arial'", "x = 'calibri'", "x = 'Segoe UI'", "x = 'Tahoma'", "x = 'Times New Roman'",
                     "x = 'font-family:Georgia,serif'", "x = 'Courier New'", "x = f'#{a}A3301F'", "x = f'#A3{a}0F'", "x = f'color:#{a}'.format() + '#abc'",
                     "x = f'font-family:{a},Verdana'", "x = f'{a}#fff{b}'"):
            self.assertTrue(written_by_hand(code), code)

    def test_the_scan_leaves_alone_what_is_not_a_value_written_by_hand(self):
        code = ('"""A docstring may say Arial and #A3301F."""\n# a comment may say Calibri\n'
                'x = "decade"\ny = f"{a}px solid {b}"\nz = "add"\nw = "font-weight:bold;"\n')
        self.assertEqual(written_by_hand(code), [])


HEX_VALUE = re.compile(r"#(?:[0-9A-Fa-f]|\{\}){3,8}(?![0-9A-Za-z])"           # a # then 3 to 8 hex digits, a value spliced in counting as one
                       r"|(?<![0-9A-Za-z#])(?=[0-9A-Fa-f]*\d|[A-F]+(?![0-9A-Za-z]))(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})(?![0-9A-Za-z])")  # or 6 or 8 on their own
FUNCTION_COLOUR = re.compile(r"\b(?:rgba?|hsla?)\s*\(", re.I)
FONT_NAME = re.compile(r"\b(?:Arial|Calibri|Helvetica|Segoe UI|Tahoma|Verdana|Times New Roman|Courier|Georgia|Cambria|Consolas|Menlo|"
                       r"Inter|Montserrat)\b", re.I)


def written_by_hand(source):
    """The strings in `source`'s code (not its docstrings or comments) that hold a hex colour (3, 4, 6 or 8 digits, also when a
    value is spliced into an f-string right after the #), an rgb( or hsl( colour, or a font name in any case. An f-string is read as
    one text with {} where a value is put in, so a colour cut in two by a value is still seen."""
    tree = ast.parse(source)
    docs = {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body and isinstance(n.body[0], ast.Expr)}
    parts, texts = set(), []
    for n in ast.walk(tree):
        if isinstance(n, ast.JoinedStr):
            texts.append("".join(v.value if isinstance(v, ast.Constant) else "{}" for v in n.values))
            parts |= {id(v) for v in n.values}
    texts += [n.value for n in ast.walk(tree)
              if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs and id(n) not in parts]
    return [t for t in texts if HEX_VALUE.search(t) or FUNCTION_COLOUR.search(t) or FONT_NAME.search(t)]

if __name__ == "__main__":
    unittest.main()
