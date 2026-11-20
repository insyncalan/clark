"""Row 1189, slice 3 (item 1191): the Use case summary section the Dashboard starts with is the section the library's card makes.

The rule of the epic: a section moves to its template only when the template does everything the built-in does today. The card makes
the built-in's own type (usecases), so these tests pin that the two stay one thing: the same type and title in the default layout, the
re-add from the box, and the store; the same page parts for View and Edit (the strip, the rows, the Add control); the same readers
for Word, Excel and the published file.

Run: python3 dev/run_tests.py test_usecases_slice3
No Chrome: the page's catalogue runs in node. Fictional data only.
"""
import json
import shutil
import subprocess
import unittest

from _paths import SRC
from clark import changes, default_sections, docx_build, excel_client, publish

PAGE = SRC / "clark" / "page" / "src"
LOGIC = PAGE / "logic" / "templates.js"
NODE = shutil.which("node")


def run(expr):
    script = f'import * as T from {json.dumps(LOGIC.as_uri())}; console.log(JSON.stringify({expr}));'
    got = subprocess.run([NODE, "--input-type=module", "-e", script], capture_output=True, text=True, timeout=60)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def default_usecases():
    return [s for s in default_sections.DEFAULT_SECTIONS if s["type"] == "usecases"]


class UseCasesSlice3(unittest.TestCase):
    def test_the_dashboard_starts_with_one_use_case_section(self):
        self.assertEqual(len(default_usecases()), 1)

    def test_the_card_and_the_default_make_the_same_section(self):
        card = run('T.BUILT_INS.find(x => x.type === "usecases")')
        start = default_usecases()[0]
        self.assertEqual(card["type"], start["type"])
        self.assertEqual(card["title"], "Use cases", "row 1262: the card's name; the default report's own title is not renamed")
        self.assertEqual(changes.BUILT_IN_TITLES["usecases"], card["title"], "the store re-adds it with the card's title")

    def test_the_card_is_offered_only_when_the_section_was_taken_out(self):
        report = [{"id": "a", "type": "text", "title": "x", "beside": 0}]
        self.assertEqual(run(f'T.list({{sections: {json.dumps(report)}}}).filter(x => x.type === "usecases").length'), 1)
        report.append({"id": "b", "type": "usecases", "title": "Use case summary", "beside": 0})
        self.assertEqual(run(f'T.list({{sections: {json.dumps(report)}}}).filter(x => x.type === "usecases").length'), 0)

    def test_view_and_edit_draw_the_built_in_parts(self):
        src = (PAGE / "components" / "Section.jsx").read_text(encoding="utf-8")
        self.assertIn('section.type === "usecases" ? <UseCases tools={tools} section={section} />', src)
        self.assertIn('section.type === "usecases" && tools.ucEdit ? <tools.ucEdit.Configure section={section} />', src, "the section header keeps its Configure button (the Add tile is gone, row 1234-B)")

    def test_word_excel_and_the_published_file_read_the_section_by_its_type(self):
        self.assertTrue(callable(docx_build.section_usecases))
        self.assertIn("usecases", docx_build.TITLES)
        self.assertEqual(excel_client.SECTION_OF["use_cases"], "usecases")
        self.assertIn("usecases", publish.BUILT_IN_SECTIONS)
        self.assertIn("usecases", publish.SECTION_TYPES)


if __name__ == "__main__":
    unittest.main()
