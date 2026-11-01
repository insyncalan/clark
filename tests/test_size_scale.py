"""#428: every font size in the page's own CSS comes from the scale in brand/tokens.css, never a bare pixel size.

After #87 (PR 240) moved the small size from 13 px to 14 px, a bare 13px or an off-scale heading (15, 17, 18, 22 px) would
quietly undo it. The few sizes that are not text on the scale are listed here with the reason. The places that must stay at
13 px to fit their box at 900 px (#428's look at the nine places flagged on PR 240) are pinned to the caption size."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = {"shell.css": ROOT / "src/clark/page/shell.css", "edit.css": ROOT / "src/clark/page/src/edit/edit.css"}

# Not text on the type scale: big figures in the At a glance tiles, and the calendar's month arrows (a glyph sized to its button).
NOT_TEXT = {(".tile .n", "22px"), (".fig .v", "22px"), (".cp-m", "18px")}

# Fixed boxes that a 14 px label overfills at 900 px: the "As at" date in the top bar, the avatars (initials in a 26 or 24 px
# circle), the Type badge (102 px column), the template tick box (18 px).
CAPTION = [".asat", ".av", ".cp-name .av", ".type", ".tpl-check-box", ".sb-a"]

# Headings sit on the heading sizes, so none is smaller than the body text around it.
HEADINGS = {".logo .wm": "--size-h3", ".hp-sec > h2, .hp-sh h2": "--size-h2", ".hp-col .hp-sh h2": "--size-h2",
            ".hp-big": "--size-h2", ".hp-task h3, .hp-ref h3": "--size-h3", ".ucp-body h2": "--size-h3",
            ".ask-head h2": "--size-h3", ".pk-title": "--size-h2"}


def rules(text):
    """(selector, body) for each rule, one level of @media flattened, comments removed."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"@media[^{]+\{((?:[^{}]*\{[^{}]*\})*)\s*\}", lambda m: m.group(1), text)
    return [(" ".join(s.split()), b) for s, b in re.findall(r"([^{}@]+)\{([^{}]*)\}", text)]


def size_of(body):
    """The font size a rule sets, as written: from font-size, or from the size in a font shorthand."""
    m = re.search(r"(?:^|;)\s*font-size:\s*([^;]+)", body)
    if m:
        return m.group(1).strip()
    m = re.search(r"(?:^|;)\s*font:\s*[^;]*?(\d+(?:\.\d+)?px|var\(--size-[\w-]+[^)]*\))", body)
    return m.group(1).strip() if m else None


def all_sizes():
    return [(name, sel, size_of(b)) for name, path in CSS.items() for sel, b in rules(path.read_text(encoding="utf-8")) if size_of(b)]


class Scale(unittest.TestCase):
    def test_the_parser_sees_the_sizes(self):
        self.assertGreater(len(all_sizes()), 100)

    def test_no_bare_pixel_font_size_except_the_listed_ones(self):
        bare = [(name, sel, v) for name, sel, v in all_sizes() if re.fullmatch(r"\d+(?:\.\d+)?px", v) and (sel, v) not in NOT_TEXT]
        self.assertEqual(bare, [], "use a --size-* token from brand/tokens.css")

    def test_no_token_carries_a_pixel_fallback(self):
        stale = [(name, sel, v) for name, sel, v in all_sizes() if re.search(r"var\(--size-[\w-]+\s*,", v)]
        self.assertEqual(stale, [], "a fallback goes stale when the scale moves (it did for --size-h2 in #87)")

    def test_the_tight_boxes_keep_the_caption_size(self):
        found = {sel: v for _, sel, v in all_sizes()}
        for sel in CAPTION:
            self.assertEqual(found.get(sel), "var(--size-caption)", sel)

    def test_headings_sit_on_the_heading_sizes(self):
        found = {sel: v for _, sel, v in all_sizes()}
        for sel, token in HEADINGS.items():
            self.assertEqual(found.get(sel), f"var({token})", sel)

    def test_the_check_catches_a_bare_13px_coming_back(self):
        self.assertEqual(size_of(" padding: 2px; font-size: 13px; "), "13px")
        self.assertEqual(size_of(" font: 500 13px var(--font); "), "13px")
        self.assertEqual([s for s, _ in rules("@media (max-width: 900px) { .x { font-size: 13px; } }")], [".x"])


if __name__ == "__main__":
    unittest.main()
