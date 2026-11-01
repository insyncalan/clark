"""#272: the empty-state words follow the prototype ("Nothing recorded."), source check only."""
import unittest

import _paths  # noqa: F401
from _paths import ROOT


class EmptyStateWordsTest(unittest.TestCase):
    def test_use_case_pages_use_the_prototype_words(self):
        for name in ("UseCaseDetail.jsx", "UseCases.jsx"):
            text = (ROOT / "src/clark/page/src/components" / name).read_text(encoding="utf-8")
            self.assertIn("Nothing recorded", text, name)
            self.assertNotIn("Nothing written yet", text, name)

    def test_prototype_still_says_nothing_recorded(self):
        text = (ROOT / "system/prototype/views.js").read_text(encoding="utf-8")
        self.assertIn("Nothing recorded.", text)


if __name__ == "__main__":
    unittest.main()
