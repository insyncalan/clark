"""Item 1194: the Documents and links row rules are scoped to the doc-links list (class tpl-dl-links), so the editor's other lists and the
One document file row keep their old geometry; and the published file's plain badge (a box of words, no svg) keeps its rules.
Reads the sources (shell.css, the two DocLinks.jsx, docIcons.jsx); no browser."""
import re
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "clark" / "page"
SCOPE = ".tpl-dl-links"

# What only the approved mockup's rows carry: any rule holding one of these must be scoped, and the shared base rules must not hold them.
MOCKUP = ("padding: 8px 10px 8px 14px", "border-radius: 12px", "font-size: 16px", "font-weight: 500", "line-height: 1.3", "height: 41px")
SCOPED = (".tpl-dl-links .tpl-badge", ".tpl-dl-links .tpl-dl-i", ".tpl-dl-links .tpl-dl-i .tpl-name", ".tpl-dl-links .tpl-dl-i .tpl-rename",
          ".tpl-dl-links .tpl-dl-i .tpl-main")
PLAIN_FILL = {"PDF": ("#C93608", "#fff"), "DOC": ("#1F5FBF", "#fff"), "XLS": ("#1E9B4B", "#111"), "PPT": ("#E8601C", "#111"),
              "JPG": ("#6B46C1", "#fff"), "PNG": ("#C72A7A", "#fff"), "TXT": ("#F2A400", "#111"), "URL": ("#5B47D8", "#fff"),
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

    def test_the_mockup_row_rules_exist_and_every_selector_of_them_is_scoped(self):
        for selector in SCOPED:
            self.assertTrue(declarations(self.sheet, selector), selector)
        for sels, body in self.sheet:
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


class PlainBadge(unittest.TestCase):
    sheet = rules((SRC / "shell.css").read_text(encoding="utf-8"))

    def test_the_plain_badge_rule_and_each_kind_s_fill_and_text_are_pinned(self):
        plain = declarations(self.sheet, ".tpl-badge.tpl-plain")
        self.assertEqual({k: plain[k] for k in ("width", "padding", "color", "font-size", "font-weight", "letter-spacing")},
                         {"width": "41px", "padding": "0", "color": "var(--white)", "font-size": "var(--size-caption)", "font-weight": "800", "letter-spacing": "0"})
        tok = dict(re.findall(r"(--[a-z-]+):\s*(#[0-9A-Fa-f]{3,6})", (SRC.parent / "brand" / "tokens.css").read_text(encoding="utf-8")))
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
