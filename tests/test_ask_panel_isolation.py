"""The ask form backdrop sits at z-index -1; it only stays inside the panel
while .ask-panel creates its own stacking context (isolation: isolate)."""
import re
import unittest
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "src/clark/page/src/edit/edit.css"


def rule(sel):
    text = CSS.read_text()
    m = re.search(r"(?m)^" + re.escape(sel) + r"\s*\{([^}]*)\}", text)
    return m.group(1) if m else ""


class AskPanelIsolation(unittest.TestCase):
    def test_backdrop_is_behind(self):
        body = rule(".ask-form::before")
        self.assertRegex(body, r"z-index:\s*-1")

    def test_panel_isolates(self):
        body = rule(".ask-panel")
        self.assertRegex(body, r"isolation:\s*isolate")
        self.assertIn("position: fixed", body)


if __name__ == "__main__":
    unittest.main()
