"""Accessible names for icons. Run: python3 dev/run_tests.py test_icon_labels

A source scan of page/src/**/*.jsx: a button or link whose only child is an icon needs aria-label or aria-labelledby, a bare svg
outside Icon.jsx is hidden from readers unless it is a labelled image, and the text-style menu's name holds its visible words.
"""
import re
import unittest

from _paths import ROOT

SRC = ROOT / "src" / "clark" / "page" / "src"


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", lambda m: " " * len(m.group(0)), text, flags=re.S)
    return re.sub(r"(?<![:\"'`])//[^\n]*", lambda m: " " * len(m.group(0)), text)


def open_tag(text, i):
    """The end index of the opening tag that starts at i, skipping braces and quoted values."""
    depth, quote = 0, None
    j = i
    while j < len(text):
        c = text[j]
        if quote:
            if c == quote:
                quote = None
        elif c in "\"'`" and depth >= 0:
            quote = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif c == ">" and depth == 0:
            return j
        j += 1
    return -1


def named(tag):
    return "aria-label=" in tag or "aria-labelledby=" in tag


def icon_only_unnamed():
    out = []
    for path in sorted(SRC.rglob("*.jsx")):
        text = strip_comments(path.read_text(encoding="utf-8"))
        for m in re.finditer(r"<(button|a)(?=[\s>])", text):
            end = open_tag(text, m.start())
            if end < 0 or text[end - 1] == "/":
                continue
            close = text.find("</%s>" % m.group(1), end)
            if close < 0:
                continue
            kids = text[end + 1:close].strip()
            icon = re.fullmatch(r"<Icon\b[^<]*?/>|<svg\b.*?</svg>", kids, flags=re.S)
            if icon and not named(text[m.start():end]):
                out.append("%s:%d" % (path.relative_to(ROOT), text.count("\n", 0, m.start()) + 1))
    return out


def bare_svgs():
    out = []
    for path in sorted(SRC.rglob("*.jsx")):
        if path.name == "Icon.jsx":
            continue
        text = strip_comments(path.read_text(encoding="utf-8"))
        for m in re.finditer(r"<svg(?=[\s>])", text):
            tag = text[m.start():open_tag(text, m.start())]
            line = text[text.rfind("\n", 0, m.start()) + 1:m.start()]
            if "aria-hidden" in tag or 'aria-hidden="true"' in line or ('role="img"' in tag and named(tag)):
                continue
            out.append("%s:%d" % (path.relative_to(ROOT), text.count("\n", 0, m.start()) + 1))
    return out


class IconLabels(unittest.TestCase):
    def test_icon_only_controls_have_names(self):
        self.assertEqual(icon_only_unnamed(), [])

    def test_bare_svgs_are_hidden_or_labelled(self):
        self.assertEqual(bare_svgs(), [])

    def test_scan_catches_a_missing_name(self):
        text = '<button type="button" onClick={() => go(1)}><Icon name="x" /></button>'
        end = open_tag(text, 0)
        self.assertFalse(named(text[:end]))
        self.assertTrue(named('<button aria-label="Close"'))

    def test_text_style_name_holds_the_visible_label(self):
        text = (SRC / "edit" / "RichText.jsx").read_text(encoding="utf-8")
        m = re.search(r"<Menu label=\{([^}]*)\} ariaLabel=(\"[^\"]*\"|\{`[^`]*`\})", text)
        self.assertIsNotNone(m)
        self.assertIn("Text style: ${", m.group(2))
        self.assertIn(m.group(1), m.group(2))


if __name__ == "__main__":
    unittest.main()
