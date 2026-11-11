"""Keyboard focus rings the stylesheet owes: the peek's buttons and width handle and the milestone labels.

Run: python3 dev/run_tests.py test_focus_rings_sweep
Reads src/clark/page/shell.css (the rules, not a page): each ring is drawn in a colour that holds 3:1 on the surface it sits on in both themes.
"""
import re
import unittest

from _paths import SRC

CSS = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")


def rule(selector):
    """The declarations of the rule whose selector list is exactly `selector`."""
    m = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
    return m.group(1) if m else None


class FocusRings(unittest.TestCase):
    def test_the_peek_buttons_ring_is_the_focus_colour(self):
        body = rule(".pkp-btn:focus-visible")
        self.assertIsNotNone(body)
        self.assertIn("var(--focus)", body)
        self.assertNotIn("--brand-cyan", body)

    def test_the_milestone_label_buttons_have_a_ring(self):
        body = rule(".mv-lab:focus-visible")
        self.assertIsNotNone(body, "a .mv-lab button reached by Tab shows a ring")
        self.assertIn("outline: 2px solid", body)

    def test_the_peek_width_handle_shows_focus_with_an_outline_not_only_a_faint_fill(self):
        body = rule(".pk-edge:focus-visible")
        self.assertIsNotNone(body, "focus has its own rule, apart from hover")
        self.assertIn("outline: 2px solid var(--focus)", body)
        self.assertIn("opacity: 1", body)
        self.assertEqual(rule(".pk-edge:hover"), " background: var(--brand-cyan); opacity: .5; ")

    def test_try_again_ring_is_the_focus_colour(self):
        self.assertIn("var(--focus)", rule(".again:focus-visible"))

    def test_menu_items_show_a_two_pixel_ring_when_focused(self):
        m = re.search(r'(?m)^\.ddmenu \[role="menuitem"\]:focus-visible, \.ddmenu \[role="menuitemradio"\]:focus-visible\s*\{([^}]*)\}', CSS)
        self.assertIsNotNone(m, "menu items have a ring rule of their own")
        self.assertIn("outline: 2px solid var(--focus)", m.group(1))

    def test_the_filter_box_shows_a_two_pixel_ring_while_the_input_has_focus(self):
        body = rule(".fline:focus-within")
        self.assertIsNotNone(body)
        self.assertIn("outline: 2px solid var(--focus)", body)


if __name__ == "__main__":
    unittest.main()
