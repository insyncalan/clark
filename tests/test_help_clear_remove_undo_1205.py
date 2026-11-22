"""Row 1205 item 15: Help says Clear, Remove and Undo show only when there is something to clear, remove or put back.

Run: python3 dev/run_tests.py test_help_clear_remove_undo_1205
Quick tier: reads helpContent.json and two JSX files, starts no browser.
"""
import unittest

from _paths import SRC

PAGE = SRC / "clark" / "page" / "src"
HELP = (PAGE / "help" / "helpContent.json").read_text(encoding="utf-8")


class HelpClearRemoveConditional(unittest.TestCase):
    def test_clear_remove_undo_lines_say_when_they_show(self):
        for s in ("**Clear**, which shows only once a folder is chosen, takes it away again.",
                  "**Remove** shows only on a brand you added,",
                  "**Undo** shows only when there is a change to put back:",
                  "**Remove** shows only when there is a chat to remove."):
            self.assertEqual(HELP.count(s), 1, s)
        for old in ("and **Clear** takes it away again.", "**Remove** on a brand asks you to confirm"):
            self.assertNotIn(old, HELP, old)
        # The code facts the words rest on: each button is drawn only under its condition.
        cf = (PAGE / "edit" / "ClientFolder.jsx").read_text(encoding="utf-8")
        for cond, attr in (("local", "data-clear-local"), ("saved", "data-clear-folder")):
            self.assertRegex(cf, r"\{" + cond + r" \? <button[^>]*\b" + attr + r"\b", attr)
        br = (PAGE / "edit" / "Brands.jsx").read_text(encoding="utf-8")
        self.assertRegex(br, r"\{b\.own \? <button[^>]*\bdata-remove\b(?!-)", "data-remove")
        self.assertRegex(br, r"\{v\.undo \? <button[^>]*\bdata-undo\b", "data-undo")
        ap = (PAGE / "edit" / "AskPanel.jsx").read_text(encoding="utf-8")
        self.assertRegex(ap, r"\{saved\.length \? \((?s:.*?)ask-hist-del", "chat Remove only per saved chat")


if __name__ == "__main__":
    unittest.main()
