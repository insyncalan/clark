"""#520: MsBlock builds the set of ids left out of the published page once, and both the Dashboard's filter and the Eye's marks read it."""
import re
import unittest

from _paths import ROOT

SRC = ROOT / "src/clark/page/src/components/MsBlock.jsx"


class HiddenOnce(unittest.TestCase):
    def setUp(self):
        self.jsx = SRC.read_text(encoding="utf-8")

    def test_the_left_out_ids_are_built_in_one_place(self):
        self.assertEqual(len(re.findall(r"leftOutIds\(data\.value\)", self.jsx)), 1, "one call builds the set")
        self.assertEqual(len(re.findall(r"new Set\(", self.jsx)), 1, "one Set")

    def test_the_dashboard_filter_and_the_list_read_the_same_set(self):
        self.assertIn("!left.has(r.id)", self.jsx)
        self.assertIn("left={left}", self.jsx)
        self.assertNotIn("off.has", self.jsx)

    def test_the_set_is_built_only_where_it_is_used(self):
        self.assertRegex(self.jsx, r"const left = dash \|\| Eye \? new Set\(leftOutIds\(data\.value\)\) : null")


if __name__ == "__main__":
    unittest.main()
