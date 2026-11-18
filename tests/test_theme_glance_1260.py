"""Row 1260 gap G6: what the At a glance strip takes in the Classic Theme beyond the Row 1313 block (the flat cells, the divider and the
no-box look are pinned in test_theme_dashboard_1313). Read from the source, no browser. Run: python3 dev/run_tests.py test_theme_glance_1260"""
import unittest

from _paths import SRC

THEME = SRC / "clark" / "themes" / "prototype-2.0"
RULES = (THEME / "rules.css").read_text(encoding="utf-8")
SHELL = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
START = "/* Row 1260 gap G6"

BLOCK = [
    ".glance { margin-top: var(--space-2); }",
    ".glance .tcell + .tcell { padding-left: var(--space-4); }",
    ".glance .fig { padding: 0; box-shadow: none; }",
    ".glance .fig .ragdot { display: none; }",
    ".glance .fig .k { font-size: 13px; color: var(--text-muted); }",
    ".glance .fig .v { font-size: 20px; font-weight: 700; }",
    ".glance .fig .dd { font-size: 14px; }",
    ".glance .fig.rag-a .v { color: var(--status-amber-text); } .glance .fig.rag-r .v { color: var(--status-red-text); }",
    ".glance .fig.go:hover { box-shadow: none; }",
    ".glance .fig.go:hover .v { text-decoration: underline; }",
    "@media (max-width: 1180px) { .glance .tcell.health { flex-basis: 100%; } .glance .tcell.health + .tcell { padding-left: 0; } }",
]


class GlanceG6(unittest.TestCase):
    def block(self):
        """The G6 block: its comment, then the lines up to the next row's comment or the end (rows stack after it)."""
        lines = RULES.split("\n")
        i = next(n for n, l in enumerate(lines) if l.startswith(START))
        out = []
        for l in lines[i + 1:]:
            if l.startswith("/* Row "):
                break
            if l.strip():
                out.append(l)
        return out

    def test_the_rules_are_exactly_these_in_order(self):
        self.assertEqual(self.block(), BLOCK)

    def test_none_of_it_is_in_the_shared_stylesheet_so_cards_is_untouched(self):
        for line in BLOCK:
            self.assertNotIn(line, SHELL)
        self.assertNotIn(".glance .fig .v { font-size: 20px", SHELL)

    def test_the_status_is_shown_by_colour_from_the_status_tokens_not_literals(self):
        for l in BLOCK:
            self.assertNotRegex(l, r"#[0-9a-fA-F]{3,8}\b")
        self.assertIn("var(--status-red-text)", " ".join(BLOCK))


if __name__ == "__main__":
    unittest.main()
