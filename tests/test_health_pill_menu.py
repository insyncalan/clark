"""A-D17: the health pill and its menu, pinned in the source (no browser). The look is filled blocks, in the menu and on the report.

Run: python3 dev/run_tests.py test_health_pill_menu
The text on each fill is computed from the committed tokens, light and dark, and must be at least 4.5:1.
"""
import re
import unittest

from _paths import SRC

PAGE = SRC / "clark" / "page"
CSS = (PAGE / "shell.css").read_text(encoding="utf-8")
TOKENS = (SRC / "clark" / "brand" / "tokens.css").read_text(encoding="utf-8")


def tokens(block):
    return dict(re.findall(r"(--[a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})\b", block))


def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def rule(sel):
    m = re.search(re.escape(sel) + r"\s*\{([^}]*)\}", CSS)
    assert m, sel
    return m.group(1)


def var_of(decl, prop):
    return re.search(prop + r":\s*var\((--[a-z0-9-]+)\)", decl).group(1)


class Contrast(unittest.TestCase):
    def themes(self):
        light = tokens(TOKENS.split(":root[data-theme=dark]")[0])
        dark = dict(light)
        dark.update(tokens(TOKENS.split(":root[data-theme=dark] {")[1].split("}")[0]))
        return {"light": light, "dark": dark}

    def test_text_on_every_fill_is_4_5_to_1_in_both_themes(self):
        for name, tok in self.themes().items():
            for rag in "gar":
                decl = rule(f".hpill.{rag}")
                fill, text = tok[var_of(decl, "background")], tok[var_of(decl, "color")]
                self.assertGreaterEqual(ratio(fill, text), 4.5, f"{rag} in {name}: {fill} with {text}")


class Source(unittest.TestCase):
    def test_the_filled_look_uses_tokens_only(self):
        block = CSS[CSS.index(".hpill {"):CSS.index(".ddmenu .hck")]
        self.assertNotRegex(block, r"#[0-9A-Fa-f]{3,6}\b", "no hard-coded colour")
        self.assertIn("text-transform: uppercase", rule(".hpill"))
        self.assertIn("var(--radius-sm)", rule(".hpill"))
        self.assertIn("font-size: var(--size-small)", rule(".hpill"))

    def test_the_menu_rows_are_pills_with_a_check_mark_shape(self):
        menu = (PAGE / "src" / "components" / "Menu.jsx").read_text(encoding="utf-8")
        self.assertIn('<span class={`hpill ${it.pill}`}>', menu)
        self.assertIn('<Icon name="check" cls="hck" />', menu)
        self.assertIn('"menuitemradio"', menu)
        health = (PAGE / "src" / "edit" / "GlanceEdit.jsx").read_text(encoding="utf-8")
        self.assertIn("pill: r, checked: name === health", health)
        self.assertIn("pickHealth(h, health, reason)", health, "what is saved is unchanged")

    def test_the_report_pill_is_the_same_block(self):
        glance = (PAGE / "src" / "components" / "Glance.jsx").read_text(encoding="utf-8")
        self.assertIn("pill hpill ", glance)


if __name__ == "__main__":
    unittest.main()
