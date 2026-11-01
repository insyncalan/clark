"""The narrow contents button: the parts that need no browser: the contents rail becomes an "On this page" button at 900 px and
narrower. These pin the source (the component and the shared stylesheet) and the built pages, so a change that drops the button, the
focus rules or the tokens is seen without Chrome. The behaviour in a real window is in test_toc_button.py.

Run: python3 dev/run_tests.py test_toc_button_source
"""
import re
import unittest

from _paths import SRC

PAGE = SRC / "clark" / "page"
CSS = (PAGE / "shell.css").read_text(encoding="utf-8")
JSX = (PAGE / "src" / "components" / "Minimap.jsx").read_text(encoding="utf-8")


def narrow_block():
    """The text of the first shell.css rule group that starts at 900 px and holds the contents button."""
    start = CSS.index("@media (max-width: 900px) {\n  .toc {")
    return CSS[start:CSS.index("\n}\n", start)]


class Button(unittest.TestCase):
    def test_the_rail_is_one_real_button_with_the_words_On_this_page(self):
        self.assertRegex(JSX, r'<button type="button" class="toc-lines"[^>]*aria-expanded=\{open \? "true" : "false"\}[^>]*aria-controls="toc-card"[^>]*aria-label="On this page"')
        self.assertIn('<span class="toc-lbl" aria-hidden="true">On this page</span>', JSX)
        self.assertIn('class="toc-ico"', JSX)

    def test_only_a_click_or_a_key_opens_it_at_900_not_hover_or_plain_focus(self):
        self.assertIn('const NARROW = "(max-width: 900px)"', JSX)
        self.assertIn("onMouseEnter={() => { if (!narrow()) setOpen(true); }}", JSX)
        self.assertIn("else if (!narrow()) setOpen(true);", JSX)
        self.assertIn("setOpen(narrow() ? !open : true)", JSX)

    def test_a_click_outside_closes_it_and_escape_still_returns_to_the_button(self):
        self.assertIn('document.addEventListener("pointerdown", outside)', JSX)
        self.assertIn('document.removeEventListener("pointerdown", outside)', JSX)
        self.assertIn("button.current.focus()", JSX)              # Escape: back on the button, shut
        self.assertIn("inert={!open}", JSX)                         # a shut list cannot be tabbed into

    def test_a_choice_still_goes_to_the_section_and_its_heading_takes_focus(self):
        self.assertIn("jump(e)", JSX)
        dash = (PAGE / "src" / "components" / "Dashboard.jsx").read_text(encoding="utf-8")
        self.assertIn("el.focus({ preventScroll: true })", dash)


class Look(unittest.TestCase):
    def test_the_button_is_bottom_right_from_900_down_and_the_lines_are_hidden(self):
        b = narrow_block()
        self.assertRegex(b, r"\.toc \{ right: var\(--space-4\); bottom: var\(--space-4\); top: auto; transform: none; \}")
        self.assertIn(".toc-lines i { display: none; }", b)
        self.assertIn(".toc-ico, .toc-lbl { display: inline-block; }", b)
        self.assertIn("bottom: calc(100% + var(--space-2))", b)             # the list opens above the button

    def test_the_label_is_13px_and_the_target_is_at_least_24px(self):
        b = narrow_block()
        self.assertIn("font-size: var(--size-small)", b)
        height = int(re.search(r"\.toc-lines \{[^}]*min-height: (\d+)px", b).group(1))
        self.assertGreaterEqual(height, 24)
        item = int(re.search(r"\.toc li button \{ min-height: (\d+)px", b).group(1))
        self.assertGreaterEqual(item, 24)

    def test_tokens_only_no_hard_coded_colour_in_the_new_rules(self):
        b = narrow_block()
        self.assertNotRegex(b, r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(")
        for token in ("--grey-700", "--surface", "--text", "--grey-100", "--shadow"):
            self.assertIn(f"var({token})", b)

    def test_the_rail_at_1400_is_untouched_by_the_narrow_rules(self):
        self.assertIn(".toc { position: fixed; right: 6px; top: 50%; transform: translateY(-50%); z-index: 25; }", CSS)
        self.assertIn(".toc-ico, .toc-lbl { display: none; }", CSS)          # the words and the icon only show in the narrow block

    def test_reduced_motion_drops_the_slide_at_900(self):
        self.assertRegex(CSS, r"@media \(max-width: 900px\) and \(prefers-reduced-motion: reduce\) \{ \.toc-card, \.toc\.open \.toc-card \{ transition: none; transform: none; \}")

    def test_both_built_pages_carry_it(self):
        for name in ("page.html", "page-view.html"):
            built = (PAGE / name).read_text(encoding="utf-8")
            self.assertIn(".toc-lbl", built, name)
            self.assertIn("On this page", built, name)


if __name__ == "__main__":
    unittest.main()
