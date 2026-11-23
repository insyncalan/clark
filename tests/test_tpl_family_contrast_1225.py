"""Row 1225 AP4: every template's text is 4.5 to 1 against what it sits on, in Edit and in View, light and dark, at 1400 and 900 px.

All 24 templates, filled, on the served page. Each visible text is measured in the page (its colour, with alpha and opacity, over the
backgrounds above it). Not measured: text of a disabled control (exempt, WCAG 1.4.3) and a label drawn at opacity 0. A text over a
background image is listed, not passed (none today).
The 900 px half skips while PAUSED_900 is set (test_server.py), as every 900 px case does.
Run: python3 dev/run_tests.py test_tpl_family_contrast_1225
"""
import unittest

import _tpl_family as F
from test_report_editor import tearDownModule  # noqa: F401
from test_server import Running  # noqa: F401

FLOOR = 4.5


class TextContrast(F.Family):
    def check(self, width):
        for dark in (False, True):
            with self.subTest(width=width, theme="dark" if dark else "light"):
                got = self.read(width, dark, F.CONTRAST_JS)
                self.assertEqual(len(got["view"]), 24)
                for mode, by in got.items():
                    for tid, texts in by.items():
                        with self.subTest(mode=mode, template=tid):
                            self.assertTrue(texts, f"{tid} in {mode}: some text was measured")
                            low = [(t["ratio"], t["text"], t["tag"]) for t in texts if t["ratio"] < FLOOR or t["image"]]
                            self.assertEqual(low, [], f"{tid} in {mode}: text under {FLOOR} to 1 or over an image (ratio, text, element)")

    def test_text_is_4_5_to_1_at_1400(self):
        self.check(1400)

    def test_text_is_4_5_to_1_at_900(self):
        self.check(900)


if __name__ == "__main__":
    unittest.main()
