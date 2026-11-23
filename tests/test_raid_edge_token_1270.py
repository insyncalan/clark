"""Row 1270: the RAID card's rating edge is drawn with the spacing token, not a bare pixel width (the drawn edge stays 4 px, measured in test_raid_cards_view_1270)."""
import re
import unittest

from _paths import SRC


class EdgeToken(unittest.TestCase):
    def test_the_card_edge_is_a_token_not_a_bare_px(self):
        css = (SRC / "clark" / "themes" / "prototype-2.0" / "rules-2.css").read_text(encoding="utf-8")      # the card look is the Classic layer (Cards keeps shell.css)
        rule = next(l for l in css.splitlines() if l.startswith(".raid-card {"))
        edge = re.search(r"border-top:\s*([^;]+);", rule)
        self.assertIsNotNone(edge, "the card has a top edge")
        self.assertEqual(edge.group(1), "var(--space-1) solid var(--rc-edge)")


if __name__ == "__main__":
    unittest.main()
