"""Item 1189, row 2 (ticket 1190): the Dashboard's At a glance section comes from the At a glance library template.
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
    def card(self):
        return run('T.list({sections: []}).find(x => x.type === "glance")')

    def default(self):
        return [d for d in default_sections.DEFAULT_SECTIONS if d["type"] == "glance"]

    def test_the_new_project_has_one_glance_section_and_it_is_the_cards_type_and_title(self):
        card, have = self.card(), self.default()
        self.assertEqual(len(have), 1)
        self.assertEqual((have[0]["type"], have[0]["title"]), (card["type"], card["title"]))

    def test_placing_the_card_asks_for_the_section_a_new_project_starts_with(self):
        got = run('T.plan([{id: "a", type: "text", title: "Summary", beside: 0}], "built-in-glance", "a")')
        values = got["requests"][0]["values"]
        self.assertEqual(values, {k: self.default()[0][k] for k in ("type", "title")})
        self.assertIn(values["type"], changes.NEW_SECTION_TYPES)
        self.assertIn(values["type"], store_module.SECTION_TYPES)

    def test_the_cards_parts_are_the_tiles_the_section_draws_in_order(self):
        parts = self.card()["holds"]
        self.assertEqual(parts[0], "Heading")
        self.assertEqual(parts[1:], [glance.TILE_TITLES[k] for k in glance.TILES])
        tiles_js = (PAGE / "glanceTiles.js").read_text(encoding="utf-8")
        for title in parts[1:]:
            self.assertIn(f'"{title}"', tiles_js, "the page draws the tile the card promises")

    def test_view_word_excel_and_the_published_file_all_draw_the_type(self):
        self.assertIn("glance", publish.BUILT_IN_SECTIONS)
        self.assertIn('section.type === "glance" ? <Glance', (PAGE / "components" / "Section.jsx").read_text(encoding="utf-8"))
        self.assertIn('t == "glance"', (SRC / "clark" / "docx_build.py").read_text(encoding="utf-8"))
        self.assertIn('kind == "glance"', (SRC / "clark" / "excel_cover.py").read_text(encoding="utf-8"))
        self.assertTrue(excel_cover)

    def test_the_card_makes_no_second_kind_of_section(self):
        """The template adds no type of its own: a report built from it reads, edits and publishes as any report has."""
        self.assertEqual(self.card()["kind"], "figures")
        self.assertNotIn("glance-template", store_module.SECTION_TYPES)


if __name__ == "__main__":
    unittest.main()
