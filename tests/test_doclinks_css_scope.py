"""Item 1194: the Documents and links row rules are scoped to the doc-links list (class tpl-dl-links), so the editor's other lists and the
One document file row keep their old geometry; and the published file's plain badge (a box of words, no svg) keeps its rules.
The look is Classic's: its rules are in the theme's rules-2.css (themes/prototype-2.0), and shell.css, edit.css and tokens.css carry none of
them, so the Cards page is what main serves. Reads the sources (shell.css, edit.css, rules-2.css, the two DocLinks.jsx, docIcons.jsx); no browser."""
import re
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "clark" / "page"
THEME = Path(__file__).resolve().parent.parent / "src" / "clark" / "themes" / "prototype-2.0" / "rules-2.css"
SCOPE = ".tpl-dl-links"

# What only the approved mockup's rows carry: any rule holding one of these must be scoped, and the shared base rules must not hold them.
MOCKUP = ("padding: 8px 10px 8px 14px", "border-radius: 12px", "font-size: 16px", "font-weight: 500", "line-height: 1.3", "height: 41px")
SCOPED = (".tpl-dl-links .tpl-badge", ".tpl-dl-links .tpl-dl-i", ".tpl-dl-links .tpl-dl-i .tpl-name", ".tpl-dl-links .tpl-dl-i .tpl-rename",
          ".tpl-dl-links .tpl-dl-i .tpl-main")
# The approved mock-up's tiles (.t-pdf, .t-word, .t-excel, .t-ppt, .t-img, .t-link, .t-mail, .t-file), text white on all. JPG and PNG are the mock's one image tile.
# Row 1194 round 3: the page-icon colours are the mock's (approved 18-11): PDF E8410C, XLS 1E9B4B, PPT E8601C, JPG 6B46C1, PNG E0358B, TXT F2A400.
PLAIN_FILL = {"PDF": ("#E8410C", "#fff"), "DOC": ("#1F5FBF", "#fff"), "XLS": ("#1E9B4B", "#fff"), "PPT": ("#E8601C", "#fff"),
              "JPG": ("#6B46C1", "#fff"), "PNG": ("#E0358B", "#fff"), "TXT": ("#F2A400", "#fff"), "URL": ("#5B47D8", "#fff"),
              "MAIL": ("#0E7C86", "#fff"), "FILE": ("#5A6B77", "#fff")}


def rules(css):
    """[(selector list, declaration text)] of the plain (not @media) rules of the sheet, comments dropped."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return [([s.strip() for s in sel.split(",")], " ".join(body.split()))
            for sel, body in re.findall(r"([^{}@]+)\{([^{}]*)\}", css)]


def declarations(sheet, selector):
    """The declarations of the one rule whose selector list holds exactly `selector`, as a dict."""
    found = [body for sels, body in sheet if selector in sels]
    if len(found) != 1:
        raise AssertionError("%s: %d rules" % (selector, len(found)))
    return {k.strip(): v.strip() for k, v in (d.split(":", 1) for d in found[0].split(";") if ":" in d)}


class Scope(unittest.TestCase):
    sheet = rules((SRC / "shell.css").read_text(encoding="utf-8"))
    classic = rules(THEME.read_text(encoding="utf-8"))

    def test_the_mockup_row_rules_exist_and_every_selector_of_them_is_scoped(self):
        for selector in SCOPED:
            self.assertTrue(declarations(self.classic, selector), selector)
        for sels, body in self.sheet + self.classic:
            if any(m in body for m in MOCKUP) and not any(s.startswith((".tpl-ic", ".tpl-badge.tpl-plain")) for s in sels):
                for s in sels:
                    if s.startswith((".tpl-dl", ".tpl-badge", ".tpl-od", ".tpl-name", ".tpl-main", ".tpl-rename")):
                        self.assertTrue(s.startswith(SCOPE + " "), "%s holds the mockup geometry without the scope class" % s)

    def test_the_shared_rules_keep_their_old_geometry(self):
        for selector in (".tpl-dl-i", ".tpl-badge", ".tpl-name"):
            sels = [s for s, _ in self.sheet if selector in s]
            self.assertTrue(sels, selector)
            body = declarations(self.sheet, selector)
            for key in ("padding", "border-radius", "font-size", "line-height", "height"):
                if key in body:
                    self.assertFalse(any(m == "%s: %s" % (key, body[key]) for m in MOCKUP), "%s: %s" % (selector, key))
        self.assertEqual(declarations(self.sheet, ".tpl-dl-i")["padding"], "var(--space-2) var(--space-3)")
        self.assertEqual(declarations(self.sheet, ".tpl-dl-i")["border-radius"], "var(--radius)")
        self.assertEqual(declarations(self.sheet, ".tpl-badge")["padding"], "2px var(--space-2)")
        self.assertNotIn("height", declarations(self.sheet, ".tpl-badge"))

    def test_both_doc_links_lists_carry_the_scope_class(self):
        for path in ("src/edit/templates/DocLinks.jsx", "src/templates/DocLinks.jsx"):
            self.assertIn('<ul class="tpl-dl tpl-dl-links">', (SRC / path).read_text(encoding="utf-8"), path)


class ClassicOnly(unittest.TestCase):
    """The rules of item 1194 are the Classic theme's: shell.css, edit.css and tokens.css hold none of them (Cards is what main serves)."""
    NAMES = (".tpl-dl-links", "tpl-ic-", ".tpl-page", ".tpl-plain", "tpl-act-", ".tpl-allowed", ".tpl-icon", ".tpl-icons", ".tpl-rename", ".tpl-files-edit .tpl-hint",
             "a.tpl-act", ":has(.tpl-files-edit)", ".tpl-files-edit .tpl-dl-i")

    def test_the_cards_sheets_carry_none_of_the_rules(self):
        for path in ("shell.css", "src/edit/edit.css"):
            text = (SRC / path).read_text(encoding="utf-8")
            for sels, _ in rules(text):
                for s in sels:
                    self.assertFalse(any(n in s for n in self.NAMES), "%s holds %s" % (path, s))
        self.assertNotIn("--badge-", (SRC.parent / "brand" / "tokens.css").read_text(encoding="utf-8"))
        shell = rules((SRC / "shell.css").read_text(encoding="utf-8"))
        self.assertEqual(declarations(shell, ".tpl-acts")["display"], "flex", "the Cards row of buttons is main's")
        self.assertIn("button.tpl-act", [s for sels, _ in shell for s in sels])

    def test_the_classic_rules_are_in_rules_2_css_above_the_last_block(self):
        text = THEME.read_text(encoding="utf-8")
        mine, last = text.index("/* Row 1194 (Documents and links; Classic only"), text.index("/* Row 1314:")
        self.assertGreater(mine, text.index("/* Row 1336 part 3"))
        self.assertLess(mine, last)
        self.assertEqual(text.count("/* Row 1314:"), 1)
        self.assertNotIn("/* Row 1", text[last + 5:], "the Row 1314 block stays the last")
        self.assertLess(len(text.encode("utf-8")), 128 * 1024, "theme.LIMIT")
        self.assertLess(len((THEME.parent / "rules.css").read_bytes()), 128 * 1024, "theme.LIMIT: rules.css is read whole, or no Theme is layered")
        sheet = rules(text)
        for selector in (".tpl-files-edit .tpl-icons", ".tpl-files-edit .tpl-rename", ".tpl-files-edit .tpl-allowed", ".tpl-badge.tpl-page",
                         ".tpl-dl-links .tpl-acts", ".tpl-dl-links button.tpl-act", ".sec:has(.tpl-files-edit) .sec-head"):
            self.assertTrue(declarations(sheet, selector), selector)

    def test_both_jsx_parts_draw_the_new_markup_only_when_a_theme_is_layered(self):
        for path in ("src/templates/DocLinks.jsx", "src/edit/templates/DocLinks.jsx"):
            text = (SRC / path).read_text(encoding="utf-8")
            self.assertIn("classicTheme() ?", text, path)
            self.assertIn("Cards", text, path)


class PlainBadge(unittest.TestCase):
    sheet = rules(THEME.read_text(encoding="utf-8"))

    def test_the_plain_badge_rule_and_each_kind_s_fill_and_text_are_pinned(self):
        plain = declarations(self.sheet, ".tpl-badge.tpl-plain")
        self.assertEqual({k: plain[k] for k in ("width", "padding", "color", "font-size", "font-weight", "letter-spacing")},
                         {"width": "41px", "padding": "0", "color": "var(--white)", "font-size": "11px", "font-weight": "700", "letter-spacing": ".04em"})      # the mock's .fi: 11px, 700, .04em
        tok = dict(re.findall(r"(--[a-z-]+):\s*(#[0-9A-Fa-f]{3,6})", (SRC.parent / "brand" / "tokens.css").read_text(encoding="utf-8") + THEME.read_text(encoding="utf-8")))
        val = lambda v: (tok[re.fullmatch(r"var\((--[a-z-]+)\)", v).group(1)] if v.startswith("var(") else v).replace("#ffffff", "#fff")
        for kind, (fill, text) in PLAIN_FILL.items():
            with self.subTest(kind=kind):
                rule = declarations(self.sheet, ".tpl-badge.tpl-ic-%s" % kind)
                self.assertEqual(val(rule["background"]), fill)
                self.assertEqual(val(rule.get("color", "var(--white)")), text)

    def test_the_action_marks_are_drawn_in_css_only(self):
        self.assertEqual(declarations(self.sheet, ".tpl-act-open::before")["content"], '"\\2197"')
        self.assertEqual(declarations(self.sheet, ".tpl-act-download::before")["content"], '"\\2193"')

    def test_the_published_icon_is_a_plain_span_with_no_svg_and_the_editor_one_is_the_drawn_page(self):
        src = (SRC / "src" / "templates" / "docIcons.jsx").read_text(encoding="utf-8")
        plain = next(l for l in src.splitlines() if l.strip().startswith("if (fromFile.value) return"))
        self.assertIn("tpl-badge tpl-plain tpl-ic-", plain)
        self.assertNotIn("<svg", plain)
        self.assertNotIn("<img", plain)
        act = next(l for l in src.splitlines() if l.startswith("export const ActIcon"))
        self.assertIn("fromFile.value ? <span", act)
        self.assertNotIn("<svg", act.split(" : <svg")[0])
        self.assertIn('<span class="tpl-badge tpl-page">', src)


if __name__ == "__main__":
    unittest.main()
