"""Row 1189, slice 1 (Current state, ticket 1188): what the library template does and does not do yet, pinned so a change is seen.

The new project's Current state is the library template (a text section, "Header and Text" in the box). Pinned here:
 - the default section and the library template are the same section (type, width choices, empty body); the card's title in the library is Current state like the default section's (Header only when it is added in Classic, row 1251);
 - the template DOES draw its words in the published file, the Word report and the Excel cover once it has words;
 - the built-in type "current" (an existing report) is still NOT drawn in the published file: Dashboard.jsx has no branch for it.
So an existing report's built-in is not switched: the template cannot yet leave Current state out of the published file.

Run: python3 dev/run_tests.py test_current_state_template
"""
import re
import unittest

from _demo import USER, DemoStore
from _paths import ROOT
from clark import default_sections, publish

SRC = ROOT / "src" / "clark" / "page" / "src"
SAID = "<p>Scanning is two thirds done.</p>"


class CurrentStateTemplate(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store

    def first(self):
        return next(s for s in self.store.data_for("ABC")["report_sections"] if s["id"] == "ABC-S-001")

    def test_the_default_section_is_the_library_template(self):
        tpl = re.search(r'\{ id: "current-state", name: "([^"]+)", kind: "text", fit: \[([^\]]*)\], type: "([^"]+)", title: "([^"]+)", body: "([^"]*)"',
                        (SRC / "logic" / "templates.js").read_text(encoding="utf-8"))
        self.assertIsNotNone(tpl, "the library card is in templates.js")
        name, fit, typ, title, body = tpl.groups()
        d = default_sections.DEFAULT_SECTIONS[0] if hasattr(default_sections, "DEFAULT_SECTIONS") else self.first()
        self.assertEqual((typ, body), (d["type"], d.get("body", "")))
        self.assertEqual(name, "Header and Text")
        self.assertEqual((title, d["title"]), ("Header", "Header"), "row 1262: the starting title of the template and the Dashboard default is Header")
        self.assertIn('"half"', fit)

    def test_the_template_words_reach_the_published_file(self):
        with self.store.step("dashboard", USER) as st:
            st.update("report_sections", "ABC-S-001", {"body": SAID})
        sec = next(s for s in publish.build(self.store, "ABC", now="2030-01-15")["published"]["sections"] if s["id"] == "ABC-S-001")
        self.assertIn("Scanning is two thirds done.", sec["body"])

    def test_the_built_in_current_type_is_not_drawn_in_a_file(self):
        dash = (SRC / "components" / "Dashboard.jsx").read_text(encoding="utf-8")
        fd = next(l for l in dash.splitlines() if "const fileDraws" in l)
        self.assertNotIn('"current"', fd, "no branch draws type current in a file")
        self.assertIn("!!KINDS[s.type]", fd)
        kinds = (SRC / "logic" / "sectionRows.js").read_text(encoding="utf-8")
        self.assertNotRegex(kinds, r'\bcurrent\s*:')


if __name__ == "__main__":
    unittest.main()
