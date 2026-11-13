"""Failed-state messages in Update, Brands and AI settings are announced (role alert)."""
import re
import unittest
from pathlib import Path

EDIT = Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "src" / "edit"


class FailedStateAlerts(unittest.TestCase):
    def test_update_and_brands_failed_paragraph_is_alert(self):
        for name in ("Update.jsx", "Brands.jsx"):
            src = (EDIT / name).read_text(encoding="utf-8")
            m = re.search(r'<p class="error"[^>]*>\{state\.message\}', src)
            self.assertIsNotNone(m, name)
            self.assertIn('role="alert"', m.group(0), name)

    def test_ai_error_message_is_alert(self):
        src = (EDIT / "AiSettings.jsx").read_text(encoding="utf-8")
        m = re.search(r'<p class=\{`ai-msg[^\n]*data-ai-msg>', src)
        self.assertIsNotNone(m)
        self.assertIn('"alert"', m.group(0))
        self.assertNotIn('role="status"', m.group(0))


if __name__ == "__main__":
    unittest.main()
