"""Row 1205 item 15: Help says Clear, Remove and Undo show only when there is something to clear, remove or put back.

Run: python3 dev/run_tests.py test_help_1205_i15
Quick tier: reads helpContent.json and two JSX files, starts no browser.
"""
import unittest

from _paths import SRC

PAGE = SRC / "clark" / "page" / "src"
HELP = (PAGE / "help" / "helpContent.json").read_text(encoding="utf-8")


class HelpClearRemoveConditional(unittest.TestCase):
    def test_help_words(self):
        for s in ("**Clear**, which shows only once a folder is chosen, takes it away again.",
                  "**Remove** shows only on a brand you added,",
                  "**Undo** shows only when there is a change to put back:"):
            self.assertEqual(HELP.count(s), 1, s)
        for old in ("and **Clear** takes it away again.", "**Remove** on a brand asks you to confirm"):
            self.assertNotIn(old, HELP, old)

    def test_code_fact(self):
        cf = (PAGE / "edit" / "ClientFolder.jsx").read_text(encoding="utf-8")
        self.assertIn("{local ? <button", cf)
        self.assertIn("{saved ? <button", cf)
        br = (PAGE / "edit" / "Brands.jsx").read_text(encoding="utf-8")
        self.assertIn("{b.own ? <button", br)
        self.assertIn("{v.undo ? <button", br)


if __name__ == "__main__":
    unittest.main()
