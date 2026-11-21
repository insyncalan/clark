"""Row 1411: the At a glance card is gone from the box; the Dashboard's At a glance section stays.
The card is the template; the section it makes is the built-in's own type (glance), so what a new project starts with, what the
Add a section box makes, and what View, Word, Excel and the published file draw are one thing. These tests pin that the card, the
default section and every reader agree, so the template does everything the built-in does.

Run: python3 dev/run_tests.py test_glance_from_template
No Chrome: the page's catalogue (logic/templates.js) runs in node. Fictional data only.
"""
import json
import shutil
import subprocess
import unittest

from _paths import SRC
from clark import changes, default_sections, excel_cover, glance, publish, store as store_module

PAGE = SRC / "clark" / "page" / "src"
LOGIC = PAGE / "logic" / "templates.js"
NODE = shutil.which("node")


def run(expr):
    script = f'import * as T from {json.dumps(LOGIC.as_uri())}; console.log(JSON.stringify({expr}));'
    got = subprocess.run([NODE, "--input-type=module", "-e", script], capture_output=True, text=True, timeout=60)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


class GlanceFromTemplate(unittest.TestCase):
    def default(self):
        return [d for d in default_sections.DEFAULT_SECTIONS if d["type"] == "glance"]

    def test_the_new_project_has_one_glance_section(self):
        self.assertEqual(len(self.default()), 1)
        self.assertEqual(self.default()[0]["title"], "At a glance")

    def test_the_tiles_the_section_draws_are_in_the_page(self):
        tiles_js = (PAGE / "glanceTiles.js").read_text(encoding="utf-8")
        for k in glance.TILES:
            self.assertIn(f'"{glance.TILE_TITLES[k]}"', tiles_js)

    def test_view_word_excel_and_the_published_file_all_draw_the_type(self):
        self.assertIn("glance", publish.BUILT_IN_SECTIONS)
        self.assertIn('section.type === "glance" ? <Glance', (PAGE / "components" / "Section.jsx").read_text(encoding="utf-8"))
        self.assertIn('t == "glance"', (SRC / "clark" / "docx_build.py").read_text(encoding="utf-8"))
        self.assertIn('kind == "glance"', (SRC / "clark" / "excel_cover.py").read_text(encoding="utf-8"))
        self.assertTrue(excel_cover)


if __name__ == "__main__":
    unittest.main()
