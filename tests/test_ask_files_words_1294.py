"""Row 1294, second push: the picker, the Files line, ask_files.py and the approved words agree (words logged NEW-WORDS 20-11)."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EDIT = ROOT / "src/clark/page/src/edit"


def _ext_set(s):
    return {e.lower() for e in re.findall(r"\.?([A-Za-z0-9]+)", s)}


class FilesWords(unittest.TestCase):
    def test_picker_accept_is_exactly_the_line_and_the_server(self):
        panel = (EDIT / "AskPanel.jsx").read_text(encoding="utf-8")
        m = re.search(r'id="ask-file-input"[^>]*accept="([^"]*)"', panel)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), ".txt,.md,.csv")
        accepted = {a.lstrip(".") for a in m.group(1).split(",")}
        line = re.search(r'FILES_LINE = "([^"]*)"', (EDIT / "FilesSettings.jsx").read_text(encoding="utf-8")).group(1)
        self.assertTrue(line.startswith("Files: text, Markdown and CSV"))
        named = {"txt", "md", "csv"}  # text, Markdown, CSV as the line names them
        self.assertEqual(accepted, named)
        srv = (ROOT / "src/clark/ask_files.py").read_text(encoding="utf-8")
        kinds = re.search(r"TEXT_KINDS = re\.compile\(r\"[^(]*\(([^)]*)\)", srv).group(1)
        self.assertEqual(accepted, set(kinds.split("|")))
        not_yet = set(re.search(r"NOT_YET = re\.compile\(r\"[^(]*\(([^)]*)\)", srv).group(1).replace("e?", "e").split("|"))
        self.assertFalse(accepted & not_yet)

    def test_approved_words(self):
        fs = (EDIT / "FilesSettings.jsx").read_text(encoding="utf-8")
        self.assertIn('"Off for all projects."', fs)
        self.assertIn("<h2>Files</h2>", fs)
        self.assertIn('aria-label="Files"', fs)
        self.assertIn("<h2>{`Files in ${code}`}</h2>", fs)
        self.assertIn("aria-label={`Files in ${code}`}", fs)
        self.assertIn('ATTACH_LABEL = "Add a file";', (EDIT / "askFiles.js").read_text(encoding="utf-8"))
        line = "Files cannot be checked just now. They are checked again when you ask, and none are sent if they are off."
        self.assertEqual(fs.count(line), 2, "the approved failing-check line, in the All tab and the project tab")
        self.assertNotIn("None can be added", "".join(p.read_text(encoding="utf-8") for p in EDIT.glob("*.js*")))
        self.assertNotIn("Add a file or picture", "".join(p.read_text(encoding="utf-8") for p in EDIT.glob("*.js*")))


    def test_the_panel_stays_fail_open_and_the_server_is_the_gate(self):
        panel = (EDIT / "AskPanel.jsx").read_text(encoding="utf-8")
        self.assertIn("useState(true)", panel.split("filesOk")[1], "filesOk starts true: the paperclip shows until the server says no")
        self.assertIn('title={F.ATTACH_LABEL} aria-label={F.ATTACH_LABEL}', panel)


if __name__ == "__main__":
    unittest.main()
