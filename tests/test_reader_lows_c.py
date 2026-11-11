"""Reader LOWs on rows 1277, 1280, 1274 and 1287 (quick tier: starts no Chrome). Run: python3 dev/run_tests.py test_reader_lows_c

A Settings card that is missing may skip only off CI; a card's id must sit inside a section; the menu pick test does not sleep;
the clark.app test file has no run of three blank lines."""
import ast
import os
import re
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def text(name):
    return (HERE / name).read_text(encoding="utf-8")


class ReaderLows(unittest.TestCase):
    def test_a_missing_optional_card_fails_in_ci_and_skips_elsewhere(self):
        tree = ast.parse(text("test_settings_cards_widths_2.py"))        # read, not imported: the import would pull in the browser harness
        keep = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name == "may_skip")
                or (isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "OPTIONAL")]
        t = type("T", (), {})
        scope = {"os": os}
        exec(compile(ast.Module(body=keep, type_ignores=[]), "may_skip", "exec"), scope)
        t.may_skip = staticmethod(scope["may_skip"])
        self.assertTrue(t.may_skip("Update", None, {}))
        self.assertFalse(t.may_skip("Update", None, {"CI": "true"}))
        self.assertFalse(t.may_skip("People", None, {}), "a card that is not optional never skips")
        self.assertFalse(t.may_skip("Update", {"doc_over": 0}, {}), "a card that is there is checked")

    def test_the_first_half_probe_does_not_fall_back_to_the_heading(self):
        self.assertNotRegex(text("test_settings_widths_1.py"), r"closest\('section'\)\s*\|\|")

    def test_the_menu_pick_waits_for_the_menu_not_for_half_a_second(self):
        self.assertNotIn("time.sleep", text("test_menu_icons_mutproof_1074.py"))

    def test_no_three_blank_lines_in_the_app_build_tests(self):
        self.assertIsNone(re.search(r"\n\n\n\n", text("test_package_app.py")))


if __name__ == "__main__":
    unittest.main()
