"""The release-asset check (dev/tools/check_release_assets.py) and the checklist line that names it."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_release_assets", ROOT / "dev" / "tools" / "check_release_assets.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class Check(unittest.TestCase):
    def test_a_release_without_its_zip_fails(self):
        out = mod.problems([{"tag_name": "v0.4.0", "assets": []}])
        self.assertEqual(len(out), 1)
        self.assertIn("clark-0.4.0-mac.zip", out[0])

    def test_a_release_with_its_zip_passes(self):
        rel = {"tag_name": "v0.2.1", "assets": [{"name": "clark-0.2.1-mac.zip", "size": 5}]}
        self.assertEqual(mod.problems([rel]), [])

    def test_an_empty_or_wrongly_named_asset_fails(self):
        self.assertTrue(mod.problems([{"tag_name": "v0.3.0", "assets": [{"name": "clark-0.3.0-mac.zip", "size": 0}]}]))
        self.assertTrue(mod.problems([{"tag_name": "v0.3.0", "assets": [{"name": "clark-0.3.0.zip", "size": 9}]}]))

    def test_drafts_and_other_tags_are_left_alone(self):
        rels = [{"tag_name": "v0.5.0", "draft": True, "assets": []}, {"tag_name": "v0.4.0", "assets": []}]
        self.assertEqual(mod.problems(rels, {"v0.3.0"}), [])
        self.assertEqual(len(mod.problems(rels)), 1)

    def test_the_checklist_names_the_attach_step_and_the_check(self):
        text = (ROOT / "dev" / "RELEASING.md").read_text(encoding="utf-8")
        self.assertIn("Attach `clark-X.Y.Z-mac.zip` and its SHA-256", text)
        self.assertIn("dev/tools/check_release_assets.py", text)


if __name__ == "__main__":
    unittest.main()
