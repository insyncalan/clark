"""Survivors of a mutation hunt on PR 1331: each test below fails against the mutant named in its docstring.

Run: python3 dev/run_tests.py test_mutation_m1331_survivors
Milestones and releases are fictional demo rows.
"""
import importlib.util
import re
import unittest
from pathlib import Path

import _paths  # noqa: F401
from clark import milestones as ms
from clark import secret_screen

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("check_release_assets", ROOT / "dev" / "tools" / "check_release_assets.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def release(assets):
    return {"tag_name": "v0.5.0", "name": "clark 0.5.0 (Beta), Mac", "prerelease": True, "draft": False,
            "body": "# clark 0.5.0 (Beta), Mac\nclark is Beta until version 1.0.\n" + "a1" * 32,
            "published_at": "2026-11-02T10:00:00Z", "assets": assets}


def zip_at(when, name="clark-0.5.0-mac.zip"):
    return {"name": name, "size": 5, "created_at": when}


class MilestoneStateWord(unittest.TestCase):
    def test_a_stray_word_is_no_state(self):
        """Mutant: milestone_state accepts any text, not only a known state word."""
        row = {"status": "Planned", "baseline_date": "2026-10-01", "forecast_date": None, "state_set": 1}
        for stray in ("Stray", "on track", "At risk ", "__proto__"):
            with self.subTest(state=stray):
                self.assertEqual(ms.milestone_state({**row, "state": stray}, "2026-10-28"), "Overdue")
        self.assertEqual(ms.milestone_state({**row, "state": "At risk"}, "2026-10-28"), "At risk")


class AttachOrder(unittest.TestCase):
    def test_the_latest_of_two_zips_of_that_name_decides(self):
        """Mutant: min instead of max over the zip's attach times."""
        out = mod.problems([release([zip_at("2026-11-02T09:00:00Z"), zip_at("2026-11-02T10:30:00Z")])])
        self.assertEqual(len(out), 1)
        self.assertIn("attached after the release was published", out[0])

    def test_another_file_attached_late_is_not_the_zip(self):
        """Mutant: every asset counts, not only the one named for the zip."""
        out = mod.problems([release([zip_at("2026-11-02T09:00:00Z"), zip_at("2026-11-02T12:00:00Z", "clark-0.5.0-mac.zip.sig")])])
        self.assertFalse([line for line in out if "attached after" in line], out)


class ShortKeyReach(unittest.TestCase):
    def test_a_digit_far_into_a_named_long_form_still_counts(self):
        """Mutant: the digit look-ahead of a named long form reaches 20 characters, not 80."""
        for head in ("\x70k-admin-", "\x53k-ant-", "\x72k-proj-"):
            text = head + "a" * 40 + "1"
            with self.subTest(text=text):
                self.assertTrue(re.search(secret_screen.SHORT_SK, text))


if __name__ == "__main__":
    unittest.main()
