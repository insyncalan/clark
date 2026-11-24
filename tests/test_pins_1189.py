"""Row 1189, follow-up: the gaps a second mutation pass found, pinned.

Behaviour where a test can reach it (publish.build on a demo store), a source pin where it cannot (the page's JSX and templates.js):
 (a) a text section with an empty body is not drawn in a file (Dashboard.jsx fileDraws uses emptyBody);
 (b) the Use Cases card stays full width;
 (c) a hidden At a glance section leaves its figures out of the published file, a visible one carries them;
 (d) a hidden Use Cases section leaves the strip out, a visible one carries it;
 (e) Section.jsx draws the Use Cases Add control only when editing, and gives Glance the clean flag.

Run: python3 dev/run_tests.py test_pins_1189
"""
import re
import unittest

from _demo import USER, DemoStore, builtin_glance
from _paths import ROOT
from clark import publish
from test_glance import ON, RULES, data, sections, use_case

SRC = ROOT / "src" / "clark" / "page" / "src"


def read(*parts):
    return (SRC.joinpath(*parts)).read_text(encoding="utf-8")


class SourcePins(unittest.TestCase):
    def test_a_file_text_branch_uses_emptyBody(self):
        fd = next(l for l in read("components", "Dashboard.jsx").splitlines() if "const fileDraws" in l)
        self.assertIn('s.type === "text" ? !emptyBody(s.body)', fd)

    def test_b_the_use_cases_card_stays_full_width(self):
        js = read("logic", "templates.js")
        for card in ("USECASES_CARD",):
            m = re.search(r"const %s = \{ fit: \[([^\]]*)\]" % card, js)
            self.assertIsNotNone(m, card)
            self.assertEqual(m.group(1).replace(" ", ""), '"full"', card)

    def test_e_add_control_only_when_editing_and_glance_gets_clean(self):
        jsx = read("components", "Section.jsx")
        self.assertIn('editing && section.type === "usecases" && tools.ucEdit ? <tools.ucEdit.Configure section={section} /> : null', jsx)
        self.assertIn('<Glance tools={tools} clean={clean} />', jsx)


class PublishedSections(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        builtin_glance(self.store, ["ABC"])      # row 1266: a new project has the At a glance template; these tests are the built-in one's

    def set_hidden(self, typ, hidden):
        with self.store.step("dashboard", USER) as st:
            for s in self.store.data_for("ABC")["report_sections"]:
                if s["type"] == typ:
                    st.update("report_sections", s["id"], {"hidden": hidden})

    def glance(self):
        return publish.build(self.store, "ABC", now="2030-01-15")["published"]["data"]["glance"]

    def test_c_a_hidden_glance_leaves_its_tiles_out_and_a_visible_one_carries_them(self):
        self.set_hidden("glance", 0)
        self.assertTrue(self.glance()["tiles"], "visible: the figures are in")
        self.set_hidden("glance", 1)
        self.assertEqual(self.glance()["tiles"], [], "hidden: none")

    def test_d_a_hidden_use_cases_section_does_not_publish_the_strip(self):
        def strip(*hide):
            i = {"data": data(use_cases=[use_case(1)]), "hidden": [], "sections": sections(*hide), "label_rules": RULES,
                 "as_at": ON, "glance_tiles": []}
            pub = publish.select(i)
            pub["data"]["use_cases"] = [use_case(1)]      # select already empties them for a hidden section; add_glance must not rely on that
            return publish.add_glance(pub, i)["data"]["glance"]
        self.assertEqual(strip()["strip"]["total"], 1, "visible: the strip is in")
        self.assertNotIn("strip", strip("usecases"), "hidden: no strip")


if __name__ == "__main__":
    unittest.main()
