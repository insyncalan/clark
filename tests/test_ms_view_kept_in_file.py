"""Row 1132: a published file's Milestones block keeps the Timeline or Calendar choice in the address (mv=cal), so a reload brings it back."""
import re
import unittest

from _paths import ROOT

SRC = ROOT / "src/clark/page/src"


class MsViewKept(unittest.TestCase):
    def setUp(self):
        self.jsx = (SRC / "components/MsBlock.jsx").read_text(encoding="utf-8")
        self.store = (SRC / "stores/report.js").read_text(encoding="utf-8")

    def test_a_file_reads_its_view_from_the_address_signal(self):
        self.assertRegex(self.jsx, r'const view = client \? \(mv\.value === "cal" \? "cal" : "line"\) : kept')

    def test_a_file_choice_goes_to_the_address_and_not_to_storage(self):
        self.assertRegex(self.jsx, r"if \(client\) setMsView\(v\); else \{ remember\(")

    def test_the_store_writes_it_by_replacing_the_entry(self):
        self.assertRegex(self.store, r"export function setMsView\(v\) \{[^}]*route\.navigate\(where\(\), \{ replace: true \}\)")
        self.assertIn("mv: mv.value", self.store)
        self.assertIn("mv.value = s.mv", self.store)


if __name__ == "__main__":
    unittest.main()
