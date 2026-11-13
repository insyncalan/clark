"""A long folder path is one unbroken word: the Settings copy-folder hint, its refusal, the warning line and the
suggestion buttons must wrap it inside the card (overflow-wrap) rather than push past the edge at 900.

Run: python3 dev/run_tests.py test_long_path_wrap
"""
import re
import unittest
from pathlib import Path

import _paths  # noqa: F401

CSS = Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "shell.css"


def rule(selector):
    for m in re.finditer(r"^" + re.escape(selector) + r" \{([^}]*)\}", CSS.read_text(encoding="utf-8"), re.M):
        return m.group(1)
    raise AssertionError("no rule for " + selector)


class LongPathWrap(unittest.TestCase):
    def test_each_place_a_folder_path_is_shown_wraps_anywhere(self):
        for sel in (".setting p.error", ".fld-bad", ".fld small", ".fld [data-copy-suggestion]"):
            self.assertIn("overflow-wrap: anywhere", rule(sel), sel)

    def test_a_suggestion_button_stays_inside_its_column(self):
        body = rule(".fld [data-copy-suggestion]")
        self.assertIn("max-width: 100%", body)
        self.assertIn("white-space: normal", body)


if __name__ == "__main__":
    unittest.main()
