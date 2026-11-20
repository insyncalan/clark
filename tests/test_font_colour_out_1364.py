"""Row 1364: a font colour survives save, the published file and the exports; the Classic CSS block draws it from tokens only.

Run: python3 dev/run_tests.py test_font_colour_out_1364
Real change route and store (the server cleans on every save), the real publish.build, the real Word build. Excel makes plain words of
rich text, so a colour (like bold) is not carried there: the test says so and pins it.
"""
import re
import unittest

import _publish_fixture as fx
from _demo import USER, DemoStore
from _paths import ROOT

from clark import changes, docx_build, excel_client, excel_cover, publish, sanitise
from test_docx_build import every_text, parts

TOKEN_OF = {"grey": "text-muted", "brand": "brand-blue", "red": "tone-red-text", "amber": "tone-amber-text", "green": "tone-green-text", "blue": "tone-blue-text"}
WORD_HEX = {"grey": "475577", "brand": "5B47D8", "red": "B3392F", "amber": "8A5A12", "green": "2F6E57", "blue": "2456A8"}
RULES = (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")
HTML = '<p>Plain <span class="rt-c-red"><strong>ZQ-red words</strong></span> and <span class="rt-c-green">ZQ-green</span>.</p>'


class SaveAndPublish(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.ms = self.demo.milestone
        with self.s.step("dashboard", USER) as st:
            st.update("milestones", self.ms, {"client_message": "A note for the client"})
        self.send = changes.make_change(self.s.path, [], USER)

    def save(self, value):
        return self.send({"project": "ABC", "kind": "milestones", "op": "update", "id": self.ms, "changes": {"description": value}, "place": "peek"})

    def stored(self):
        return self.s.read("milestones", ref=self.ms)["description"]

    def test_saved_text_keeps_the_colour_classes_and_reads_back_the_same(self):
        self.save(HTML)
        self.assertEqual(self.stored(), HTML)
        self.assertEqual(sanitise.clean_html(self.stored()), HTML)

    def test_a_pasted_hex_or_style_is_dropped_on_save(self):
        self.save('<p><span style="color:#ff0000">ZQ-hex</span><span class="rt-c-blue" style="color:#00f">ZQ-two</span></p>')
        self.assertEqual(self.stored(), '<p>ZQ-hex<span class="rt-c-blue">ZQ-two</span></p>')

    def test_the_published_file_carries_the_span_and_its_stylesheet_defines_the_six_classes_from_tokens(self):
        self.save(HTML)
        body = publish.build(self.s, "ABC", now="2026-10-29")["body"].decode("utf-8")
        self.assertRegex(body, r'rt-c-red\\?">(?:<strong>)?ZQ-red words|rt-c-red')
        self.assertIn("ZQ-green", body)
        self.assertRegex(body, r'class=\\?"rt-c-green')
        style = "".join(re.findall(r'<style id="theme">(.*?)</style>', body, re.S))
        self.assertTrue(style, "the published file layers the Classic theme's stylesheet")
        for name, token in TOKEN_OF.items():
            with self.subTest(name):
                self.assertRegex(style, r"\.rt-c-%s\s*\{\s*color:\s*var\(--%s\)\s*;?\s*\}" % (name, token))
        self.assertNotIn("style=\\\"color", body)

    def test_the_published_cleaner_is_the_one_that_ran(self):
        self.assertEqual(publish.clean_html(HTML), HTML)


class Exports(unittest.TestCase):
    def test_word_writes_the_tokens_value_for_each_colour_and_none_for_plain_text(self):
        for name, hexv in WORD_HEX.items():
            with self.subTest(name):
                p = publish.select(fx.inputs())
                p["data"]["use_cases"][0]["standing"] = f'<p>ZQ-plain <span class="rt-c-{name}">ZQ-coloured</span></p>'
                xml = parts(docx_build.build(p))["word/document.xml"].decode()
                coloured = re.search(r'<w:r><w:rPr>(?:(?!</w:rPr>).)*<w:color w:val="%s"/>(?:(?!</w:rPr>).)*</w:rPr><w:t[^>]*>ZQ-coloured' % hexv, xml)
                self.assertIsNotNone(coloured, "the coloured run has the token's colour")
                self.assertRegex(xml, r'<w:r><w:t xml:space="preserve">ZQ-plain </w:t></w:r>')
                self.assertNotIn("rt-c-", every_text(docx_build.build(p)))

    def test_word_colour_follows_a_brand_override_of_the_token(self):
        p = publish.select(fx.inputs())
        p["data"]["use_cases"][0]["standing"] = '<p><span class="rt-c-red">ZQ-b</span></p>'
        xml = parts(docx_build.build(p, {"tone-red-text": "112233"}))["word/document.xml"].decode()
        self.assertIn('<w:color w:val="112233"/>', xml)

    def test_word_bold_inside_a_colour_keeps_both_and_the_colour_ends_with_its_span(self):
        ctx = docx_build._Ctx(docx_build.palette(), "2026-10-28")
        out = docx_build.rich('<p><span class="rt-c-blue"><strong>a</strong></span> b</p>', ctx)
        self.assertIn('<w:b/><w:color w:val="2456A8"/></w:rPr><w:t xml:space="preserve">a</w:t>', out)
        self.assertRegex(out, r'<w:r><w:t xml:space="preserve"> b</w:t></w:r>')

    def test_excel_carries_the_words_only_so_the_colour_is_dropped_as_bold_is(self):
        for fn in (excel_client.plain, excel_cover.plain):
            self.assertEqual(fn(HTML), "Plain ZQ-red words and ZQ-green.")


class ClassicCss(unittest.TestCase):
    def block(self):
        i = RULES.index("/* Row 1364")
        return RULES[i:RULES.index("/* Row 1314")]

    def test_the_block_sits_below_row_1318_and_before_row_1314(self):
        self.assertLess(RULES.index("/* Row 1318"), RULES.index("/* Row 1364"))
        self.assertLess(RULES.index("/* Row 1364"), RULES.index("/* Row 1314"))

    def test_each_class_is_one_colour_token_and_no_hex_is_written_but_the_specified_shadow(self):
        b = self.block()
        for name, token in TOKEN_OF.items():
            self.assertIn(".rt-c-%s { color: var(--%s); }" % (name, token), b)
        self.assertEqual(re.findall(r"#[0-9A-Fa-f]{3,8}\b", b.split("*/", 1)[1]), [])
        self.assertEqual(re.findall(r"rgba?\([^)]*\)", b), ["rgba(14, 36, 48, .12)"])

    def test_the_palette_measures_are_the_specified_ones(self):
        b = self.block()
        pal = re.search(r"\.rt-fc-pal \{([^}]*)\}", b).group(1)
        for part in ("width: 208px", "padding: 8px", "border: 1px solid var(--grey-200)", "border-radius: 8px", "box-shadow: 0 6px 18px rgba(14, 36, 48, .12)"):
            self.assertIn(part, pal)
        sw = re.search(r"\.rt-fc-sw \{([^}]*)\}", b).group(1)
        for part in ("width: 32px", "height: 32px", "border: 1px solid var(--grey-200)", "border-radius: 6px"):
            self.assertIn(part, sw)
        self.assertIn("grid-template-columns: repeat(4, 32px); gap: 6px", b)
        self.assertIn(".rt-fc-sw.on { outline: 2px solid var(--brand-blue); outline-offset: 1px; }", b)
        self.assertRegex(b, r"\.rt-fc-auto \{[^}]*height: 32px")
        self.assertRegex(b, r"\.rt-btn\.rt-fc-btn \{ width: 32px; padding: 0; \}")
        self.assertRegex(b, r"\.rt-fc-bar \{[^}]*width: 14px; height: 3px")

    def test_cards_files_are_not_touched(self):
        for f in ("shell.css", "edit/edit.css"):
            text = (ROOT / "src" / "clark" / "page" / f if f == "shell.css" else ROOT / "src" / "clark" / "page" / "src" / f).read_text(encoding="utf-8")
            self.assertNotIn("rt-c-", text)
            self.assertNotIn("rt-fc", text)


if __name__ == "__main__":
    unittest.main()
