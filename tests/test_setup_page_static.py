"""The first-run setup page (row 836, step 5), checks that need no browser: its words, its labels and where it is reached from.
Run: python3 dev/run_tests.py test_setup_page_static
"""
import re
import unittest

from _paths import SRC

from clark import doctor

PAGE_SRC = SRC / "clark" / "page" / "src"
LOGIC = (PAGE_SRC / "logic" / "setup.js").read_text(encoding="utf-8")
VIEW = (PAGE_SRC / "edit" / "SetupPage.jsx").read_text(encoding="utf-8")
SHELL = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")


class Words(unittest.TestCase):
    def test_the_status_labels_are_the_doctors(self):
        block = LOGIC.split("export const LABELS = {", 1)[1].split("}", 1)[0]
        pairs = {(a or b): c for a, b, c in re.findall(r'(?:"([a-z ]+)"|([a-z]+)): "([^"]+)"', block)}
        self.assertEqual(dict(doctor.LABELS), pairs)

    def test_no_doctor_sentence_is_copied_into_the_page(self):
        doctor_text = (SRC / "clark" / "doctor.py").read_text(encoding="utf-8")
        for name, text in re.findall(r'export const ([A-Z_]+) = "([^"]+)"', LOGIC):
            self.assertNotIn(text, doctor_text, name)

    def test_new_words_are_plain_and_none_starts_with_the_product_name(self):
        for name, text in re.findall(r'export const ([A-Z_]+) = "([^"]+)"', LOGIC):
            self.assertFalse(text.startswith(("clark", "Clark")), name)
            self.assertIsNone(re.search(r"(?i)\b(json|token|database|api|route|server)\b", text), name)


class Reach(unittest.TestCase):
    def test_every_class_the_page_uses_is_already_in_the_shell(self):
        for attr in re.findall(r"class=(\{[^}]*\}|\"[^\"]*\")", VIEW):
            for words in re.findall(r'"([^"]*)"', attr):
                for word in words.split():
                    self.assertIn("." + word, SHELL, word)

    def test_the_error_class_the_logic_names_is_in_the_shell(self):
        self.assertIn('"error"', LOGIC)
        self.assertIn("p.error", SHELL)

    def test_the_page_is_not_yet_in_either_built_page(self):
        for name in ("page.html", "page-view.html"):
            built = (SRC / "clark" / "page" / name).read_text(encoding="utf-8")
            self.assertNotIn("Setting up clark", built, name)
            self.assertNotIn("setup-lines", built, name)

    def test_no_entry_imports_it(self):
        for entry in ("main.jsx", "view.jsx", "main-test.jsx", "boot.jsx"):
            self.assertNotIn("SetupPage", (PAGE_SRC / entry).read_text(encoding="utf-8"), entry)


if __name__ == "__main__":
    unittest.main()
