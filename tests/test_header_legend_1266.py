"""Row 1266 follow-up checks: a section titled Header feeds the published current state, the eleven section ids of a new
project, and the Classic Milestones legend rule in rules-2.css (no Chrome).

Fictional data only (tests/_demo.py). Run: python3 dev/run_tests.py test_header_legend_1266"""
import re
import unittest

from _demo import USER, DemoStore
from _paths import ROOT, SRC  # noqa: F401  (puts src/ on the path)
from clark import default_sections, publish

RULES2 = (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules-2.css").read_text(encoding="utf-8")


def sec(body, title="Header", **kw):
    return {"id": "ABC-S-001", "type": "text", "title": title, "body": body, "sort_order": 1, **kw}


class HeaderFeedsCurrentState(unittest.TestCase):
    def test_a_section_titled_header_is_the_current_state_of_the_file(self):
        """Mutant: publish.py current_state_section_body, drop "header" from titles: red."""
        self.assertEqual(publish.current_state_section_body([sec("<p>On track.</p>")]), "<p>On track.</p>")
        self.assertEqual(publish.current_state_section_body([sec("<p>On track.</p>", title="  HEADER ")]), "<p>On track.</p>")

    def test_an_older_report_titled_current_state_still_feeds_it(self):
        self.assertEqual(publish.current_state_section_body([sec("<p>Old.</p>", title="Current state")]), "<p>Old.</p>")

    def test_a_hidden_header_or_the_editor_hint_alone_gives_nothing(self):
        self.assertEqual(publish.current_state_section_body([sec("<p>Secret.</p>", hidden=1)]), "")
        self.assertEqual(publish.current_state_section_body([sec("<p>%s</p>" % default_sections.CURRENT_STATE_PREFILL)]), "")

    def test_the_built_page_of_a_project_carries_the_header_text_as_its_current_state(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        header = next(s for s in demo.store.data_for("ABC")["report_sections"] if s["title"] == "Header")
        with demo.store.step("dashboard", USER) as st:
            st.update("report_sections", header["id"], {"body": "<p>Header words.</p>"})
        built = publish.build(demo.store, "ABC", now="2030-01-15")
        self.assertIn("Header words.", str(built["published"]["data"]["project"]["current_state"]))


class ElevenIds(unittest.TestCase):
    def test_a_new_project_stores_eleven_sections_with_ids_one_to_eleven_in_order(self):
        """Mutant: default_sections.py, drop one section: red."""
        demo = DemoStore()
        self.addCleanup(demo.close)
        rows = sorted(demo.store.data_for("ABC")["report_sections"], key=lambda r: r["sort_order"])
        self.assertEqual([r["id"] for r in rows], ["ABC-S-%03d" % n for n in range(1, 12)])
        self.assertEqual([r["title"] for r in rows], ["Headline", "At a glance", "Header", "This week", "Next week", "Milestones",
                                                      "Use cases", "Risks and issues", "Open actions", "Decisions", "Documents"])


class MilestonesLegendRule(unittest.TestCase):
    RULE = re.search(r"^\.msl-bar \.mlg-row \{([^}]*)\}", RULES2, re.M)

    def test_the_legend_has_the_surface_behind_it_in_classic(self):
        """Mutant: rules-2.css, drop the background from the .msl-bar .mlg-row rule: red."""
        self.assertIsNotNone(self.RULE)
        self.assertIn("background: var(--surface)", self.RULE.group(1))

    def test_the_rule_is_one_rule_with_no_colour_value_and_sits_outside_the_1592_block(self):
        self.assertEqual(len(re.findall(r"^\.msl-bar \.mlg-row \{", RULES2, re.M)), 1)
        self.assertNotRegex(self.RULE.group(1), r"#[0-9a-fA-F]{3,8}\b|rgb")
        block = RULES2[RULES2.index("/* Row 1592"):RULES2.index("/* Row 1314")]
        self.assertNotIn(".msl-bar", block)
        self.assertLess(self.RULE.start(), RULES2.index("/* Row 1592"))


if __name__ == "__main__":
    unittest.main()
