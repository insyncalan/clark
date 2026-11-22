"""Row 1282: the Work items list's Priority drop-down of a risk or an issue is the peek's own Impact x Likelihood matrix, one shared component.

Run: python3 dev/run_tests.py test_priority_one_control_1282
These checks read the page's source, so they run without Chrome. The browser run of the same behaviour is in test_priority_rating_cell.
"""
import re
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "clark" / "page" / "src" / "edit"


class OneControl(unittest.TestCase):
    def test_the_list_picker_for_a_risk_or_an_issue_is_the_peeks_matrix(self):
        text = (SRC / "cells" / "PriorityPick.jsx").read_text(encoding="utf-8")
        self.assertRegex(text, r'import \{ Matrix \} from "\.\./PeekRating\.jsx"')
        self.assertRegex(text, r'row\.kind !== "action"\) return <Matrix ')

    def test_the_peek_uses_the_same_component(self):
        self.assertIn("<Matrix ", (SRC / "PeekProps.jsx").read_text(encoding="utf-8"))

    def test_there_is_no_second_copy_of_the_two_stacked_lists(self):
        self.assertFalse((SRC / "cells" / "RatingPick.jsx").exists(), "the old two-list picker is gone")
        for path in SRC.rglob("*.jsx"):
            self.assertNotIn("RatingPick.jsx", path.read_text(encoding="utf-8"), path.name)

    def test_the_change_says_where_it_was_made(self):
        text = (SRC / "PeekRating.jsx").read_text(encoding="utf-8")
        self.assertRegex(text, r'function Matrix\(\{[^}]*place = "peek"')
        self.assertIsNone(re.search(r'place: "peek"', text), "the place is the one the caller gave, not fixed to the peek")

    def test_the_list_passes_the_cell_place_and_an_action_keeps_its_plain_list(self):
        text = (SRC / "cells" / "PriorityPick.jsx").read_text(encoding="utf-8")
        self.assertIn('place={place || "cell"}', text, "a list change is logged as made in the cell, not the peek")
        self.assertIn("<MenuPick ", text, "an action keeps the plain list of priorities")
        self.assertLess(text.index("<Matrix "), text.index("<MenuPick "), "the matrix is for the non-action branch")
        self.assertIn("place={place}", (SRC / "cells" / "Cell.jsx").read_text(encoding="utf-8"), "the cell hands its place to the picker")

    def test_the_peek_keeps_the_default_place(self):
        text = (SRC / "PeekProps.jsx").read_text(encoding="utf-8")
        line = next(ln for ln in text.splitlines() if "<Matrix " in ln)
        self.assertNotIn("place=", line, "the peek's own use says nothing, so the change is made in the peek")

    def test_the_matrix_sets_both_fields_in_one_change_and_does_nothing_when_unchanged(self):
        text = (SRC / "PeekRating.jsx").read_text(encoding="utf-8")
        self.assertRegex(text, r"changeRating\(tableOf\(row\), row\.id, \{ impact, likelihood \}")
        self.assertRegex(text, r"if \(impact === row\.impact && likelihood === row\.likelihood\) return;")
        self.assertRegex(text, r"onClose\(true\);\s*\n\s*if \(impact === row\.impact")

    def test_the_old_picker_styles_are_gone(self):
        css = (SRC.parents[1] / "shell.css").read_text(encoding="utf-8")
        for name in ("rpick", "rp-head"):
            self.assertNotIn(name, css)
        for path in SRC.parent.rglob("*"):
            if path.suffix in (".jsx", ".js", ".css"):
                self.assertNotIn("rp-head", path.read_text(encoding="utf-8"), path.name)


if __name__ == "__main__":
    unittest.main()
