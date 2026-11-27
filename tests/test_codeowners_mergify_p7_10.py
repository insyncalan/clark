"""Bifrost P7-10: the Mergify config is a guarded file. .mergify.yml decides what may merge (the queue conditions), so a change to it
needs the owner's review like the workflows do. It sits at the repository root, outside /.github/, so it needs its own CODEOWNERS line."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def owners():
    out = {}
    for ln in (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8").splitlines():
        if ln.strip() and not ln.lstrip().startswith("#"):
            parts = ln.split()
            out[parts[0]] = parts[1:]
    return out


class MergifyConfigIsGuarded(unittest.TestCase):
    def test_the_mergify_config_exists_at_the_root(self):
        self.assertTrue((ROOT / ".mergify.yml").is_file())

    def test_the_mergify_config_has_an_owner_line_in_codeowners(self):
        self.assertIn("/.mergify.yml", owners(), ".mergify.yml has no line in .github/CODEOWNERS")

    def test_the_owner_of_the_mergify_config_is_the_repository_owner(self):
        o = owners()
        self.assertEqual(o.get("/.mergify.yml"), o.get("/.github/"), "the .mergify.yml line must name the same owner as /.github/")


if __name__ == "__main__":
    unittest.main()
