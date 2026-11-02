"""#409: no release note, SECURITY.md or Help may say the selected text is sent or screened while the ask panel sends no selection.

The v0.3 note said a key "inside the text you selected" is refused, but the real panel sends only the typed question and earlier
turns (the AI menu uses a stub client and no /api/ai route exists). So the words "you selected" may not appear in a release note,
SECURITY.md or Help unless the ask panel's own code sends a selection.

Run: python3 dev/run_tests.py test_docs_selection_claim
"""
import re
import tempfile
import unittest
from pathlib import Path

from _paths import SRC  # noqa: F401  (puts src/ on the path)

ROOT = Path(__file__).resolve().parent.parent
PANEL_CODE = [ROOT / "src/clark/page/src/edit/AskPanel.jsx", ROOT / "src/clark/page/src/edit/AskChange.jsx",
              ROOT / "src/clark/ask_service.py"]
DOCS = sorted((ROOT / "dev/release-notes").glob("*.md")) + [ROOT / "SECURITY.md",
                                                           ROOT / "src/clark/page/src/help/helpContent.json"]
CLAIM = re.compile(r"you selected|selected text (?:is|are) (?:sent|checked|refused|screened)", re.I)
SENDS = re.compile(r"\b(?:getSelection|selectedText|selection)\b")


def panel_sends_selection(paths=PANEL_CODE):
    return any(SENDS.search(p.read_text(encoding="utf-8")) for p in paths)


def claims(paths=DOCS):
    return [p.name for p in paths if CLAIM.search(p.read_text(encoding="utf-8"))]


class SelectionClaim(unittest.TestCase):
    def test_the_files_exist(self):
        for p in PANEL_CODE + DOCS:
            self.assertTrue(p.is_file(), p.name)
        self.assertGreaterEqual(len(DOCS), 3)

    def test_no_doc_claims_a_selection_the_panel_does_not_send(self):
        if not panel_sends_selection():
            self.assertEqual(claims(), [])

    def test_the_check_notices_a_claim_and_a_selection(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "n.md"
            f.write_text("inside the text you selected, is refused", encoding="utf-8")
            self.assertEqual(claims([f]), ["n.md"])
            g = Path(d) / "p.jsx"
            g.write_text("send(selection)", encoding="utf-8")
            self.assertTrue(panel_sends_selection([g]))


if __name__ == "__main__":
    unittest.main()
