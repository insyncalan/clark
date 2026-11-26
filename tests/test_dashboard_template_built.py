"""Row 1189 (epic): the Dashboard is built from the template library. A ratchet, with no browser (quick tier).

Every default section (default_sections.py) is either a library template (a `type` in logic/templates.js TEMPLATES) or sits in
PENDING, the built-ins still waiting for their template, each with the row that replaces it. And components/Section.jsx may
draw only the built-in types in PENDING plus the older ones it still reads: a new hand-coded branch fails here. When a row lands,
its type leaves PENDING (and the branch leaves Section.jsx); a type cannot be added to PENDING without changing this file.

Run: python3 dev/run_tests.py test_dashboard_template_built
"""
import re
import unittest

from _paths import SRC
from clark import default_sections

PENDING = {      # built-in type -> the row whose template replaces it
    "usecases": 1191, "milestones": 1192,      # row 1266: the default At a glance is the glance template and the default Documents is the Files and links template, so glance and docs left PENDING
}
OLDER = {"current", "tracker"}       # still read and drawn, no longer a default: "current" (row 1188) and the Progress tracker (#189)
OLD_REPORTS = {"raid", "actions", "decisions", "glance", "docs"}      # no longer a default (rows 8 to 10 of 1193), still drawn for a report that has them
PAGE = SRC / "clark" / "page" / "src"


def library_types():
    text = (PAGE / "logic" / "templates.js").read_text(encoding="utf-8")
    block = text[text.index("export const TEMPLATES"):text.index("export const LATER")]
    return set(re.findall(r'\btype: "([a-z0-9]+)"', block))


def section_branches():
    text = (PAGE / "components" / "Section.jsx").read_text(encoding="utf-8")
    return set(re.findall(r'section\.type === "([a-z0-9]+)"', text))


class DashboardFromLibrary(unittest.TestCase):
    def test_every_default_section_is_a_template_or_waiting_for_its_row(self):
        lib = library_types()
        self.assertIn("text", lib)
        for s in default_sections.DEFAULT_SECTIONS:
            self.assertTrue(s["type"] in lib or s["type"] in PENDING, "%s (%s) is neither a library template nor pending" % (s["title"], s["type"]))

    def test_nothing_pending_is_already_a_template_or_missing_from_the_defaults(self):
        lib = library_types()
        defaults = {s["type"] for s in default_sections.DEFAULT_SECTIONS}
        for t in PENDING:
            self.assertNotIn(t, lib, "%s is a template now: take it out of PENDING and out of Section.jsx" % t)
            self.assertIn(t, defaults, "%s is no longer a default: take it out of PENDING" % t)

    def test_section_draws_no_hand_coded_branch_beyond_the_pending_ones(self):
        extra = section_branches() - set(PENDING) - OLDER - OLD_REPORTS - {"text"}
        self.assertEqual(extra, set(), "Section.jsx has a hand-coded branch for %s: use a library template" % sorted(extra))
        self.assertTrue(set(PENDING) <= section_branches() | {"docs"})


if __name__ == "__main__":
    unittest.main()
