"""Item 1191: the Use Cases library template. The Dashboard's use case section is drawn through the template parts (templateFor /
tools.templateEdit) for the store type "usecases", not by a branch in Section.jsx; the card is in the Add a section box with its
Help row; every new visible string lives in logic/useCasesStrings1191.js (UNRULED until ruled); the empty rule keeps View's
"No use cases yet." and leaves a published file without use cases out; Word, Excel and the published file read the same type.

Run: python3 dev/run_tests.py test_use_cases_template_1191
Needs Chrome. Fictional data only. Widths 1400 and 900.
"""
import json
import re
import unittest

from _paths import SRC
from clark import changes, docx_build, publish, store
import test_section_registry as _reg
from test_use_cases_list import Setup
from test_server import chrome

PAGE_SRC = SRC / "clark" / "page" / "src"
STRINGS = PAGE_SRC / "logic" / "useCasesStrings1191.js"


def strings():
    """name -> value of every exported constant in the strings file (plain string and string-list literals only)."""
    text = STRINGS.read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"^export const (\w+) = (.+?);\s*(?://.*)?$", text, re.M):
        out[m.group(1)] = json.loads(m.group(2))
    return out


class Static(unittest.TestCase):
    def test_section_jsx_has_no_branch_for_the_use_case_type(self):
        src = (PAGE_SRC / "components" / "Section.jsx").read_text(encoding="utf-8")
        self.assertNotIn("<UseCases", src, "the summary is drawn by its template parts")
        self.assertNotIn('import { UseCases }', src)
        self.assertNotRegex(src, r'type === "usecases" \? <UseCases')

    def test_strings_file_has_the_unruled_constants_and_nothing_else_hard_coded(self):
        s = strings()
        self.assertEqual(sorted(s), ["USE_CASES_DESCRIPTION", "USE_CASES_FIT_HELP", "USE_CASES_HOLDS", "USE_CASES_NAME", "USE_CASES_START_TITLE"])
        self.assertTrue(STRINGS.read_text(encoding="utf-8").count("UNRULED") >= 1)
        self.assertEqual(s["USE_CASES_NAME"], "Use Cases")
        self.assertEqual(s["USE_CASES_FIT_HELP"], "Full")
        for name in ("USE_CASES_NAME", "USE_CASES_DESCRIPTION"):
            for f in (PAGE_SRC / "logic" / "templates.js",):
                self.assertNotIn(json.dumps(s[name], ensure_ascii=False), f.read_text(encoding="utf-8"), f"{name} only in the strings file")

    def test_help_has_a_row_with_the_card_words(self):
        s = strings()
        help_ = json.loads((PAGE_SRC / "help" / "helpContent.json").read_text(encoding="utf-8"))
        rows = []

        def walk(o):
            if isinstance(o, dict):
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                if len(o) == 3 and all(isinstance(x, str) for x in o):
                    rows.append(tuple(o))
                for v in o:
                    walk(v)
        walk(help_)
        self.assertIn((s["USE_CASES_NAME"], s["USE_CASES_DESCRIPTION"], s["USE_CASES_FIT_HELP"]), rows)

    def test_the_store_the_change_route_word_and_excel_keep_the_type(self):
        self.assertIn("usecases", store.SECTION_TYPES)
        self.assertIn("usecases", changes.NEW_SECTION_TYPES)
        self.assertIn("usecases", publish.BUILT_IN_SECTIONS)
        self.assertEqual(docx_build.TITLES["usecases"], "Use cases")
        from clark import excel_client
        self.assertEqual(excel_client.SECTION_OF["use_cases"], "usecases")


class Parts(_reg.PageSide):
    """Only the tests below are this item's; the base class's own run in test_section_registry."""
    def test_the_type_has_view_and_edit_parts_and_is_ready(self):
        self.assertEqual(self.val('[typeof T.templateFor("usecases").view, typeof T.templateFor("usecases").isEmpty, T.templateFor("usecases").ready]'),
                         ["function", "function", True])
        self.assertEqual(self.val('typeof T.templateEdit("usecases")'), "function")

    def test_one_card_for_the_type_named_and_described_in_the_strings(self):
        s = strings()
        cards = self.val('T.templates.TEMPLATES.filter(x => x.type === "usecases")')
        self.assertEqual(len(cards), 1)
        c = cards[0]
        self.assertEqual((c["id"], c["name"], c["description"], c["fit"], c["kind"], c["ready"]),
                         ("use-cases", s["USE_CASES_NAME"], s["USE_CASES_DESCRIPTION"], ["full"], "work", True))
        self.assertEqual(c["holds"], s["USE_CASES_HOLDS"])
        self.assertEqual(c["title"], s["USE_CASES_START_TITLE"])
        self.assertIs(self.val('T.templates.available(T.templates.find("use-cases"))'), True)
        self.assertIn("use-cases", self.val("Object.keys(T.templates.SKETCHES)"))

    def test_empty_rule_view_keeps_its_message_and_a_file_without_use_cases_leaves_it_out(self):
        sec = '{type: "usecases"}'
        self.val("(T.fromFile.value = false, 0)")
        self.assertIs(self.val(f"T.templateEmpty({sec}, {{use_cases: []}})"), False, "served View says 'No use cases yet.'")
        self.assertIs(self.val(f"T.templateEmpty({sec}, {{use_cases: [{{id: 'u'}}]}})"), False)
        self.val("(T.fromFile.value = true, 0)")
        self.assertIs(self.val(f"T.templateEmpty({sec}, {{use_cases: []}})"), True, "a file with none leaves the section out")
        self.assertIs(self.val(f"T.templateEmpty({sec}, {{}})"), True)
        self.assertIs(self.val(f"T.templateEmpty({sec}, {{use_cases: [{{id: 'u'}}]}})"), False)
        self.val("(T.fromFile.value = false, 0)")


for _name in [n for n in dir(_reg.PageSide) if n.startswith("test_")]:
    setattr(Parts, _name, None)      # the base class's own tests run in test_section_registry, not here
del _name


class InThePage(Setup):
    def test_view_draws_the_summary_through_the_template_at_both_widths(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width, hash_="#dashboard&p=ABC")
                p.until("!!document.querySelector('.sec[data-type=usecases] .uc')", "the summary drew")
                self.assertEqual(p.js("document.querySelector('.sec[data-type=usecases] .uctotal').textContent"), "2 use cases")
                self.assertEqual(p.js("[...document.querySelectorAll('.sec[data-type=usecases] .ucrow .ucref')].map(e => e.textContent)"), ["UC 1.1", "UC 1.2"])
                self.assertEqual(p.js("document.querySelector('.sec[data-type=usecases] [data-uc-more]').textContent"), "2 more on the Use cases page")
                self.assertEqual(p.js("document.querySelectorAll('.sec[data-type=usecases] [data-edit-only]').length"), 0, "View has no editing controls")

    def test_view_with_none_on_the_dashboard_still_says_so(self):
        self.store.con.execute("UPDATE use_cases SET client_visible = 0")
        self.store.con.commit()
        with chrome() as cdp:
            p = self.show(cdp, hash_="#dashboard&p=ABC")
            p.until("!!document.querySelector('.sec[data-type=usecases] [data-nouc]')", "the empty message drew")
            self.assertEqual(p.js("document.querySelector('.sec[data-type=usecases] [data-nouc]').textContent"), "No use cases are on the dashboard.")

    def test_edit_keeps_the_header_add_and_the_rows_editing_controls(self):
        with chrome() as cdp:
            p = self.show(cdp, hash_="#dashboard&p=ABC")
            p.edit()
            p.until("!!document.querySelector('.sec[data-type=usecases] .sec-head .uc-add button') && !!document.querySelector('.sec[data-type=usecases] [data-uc-status]')", "Edit drew the Add and the eyes")
            self.assertGreater(p.js("document.querySelectorAll('.sec[data-type=usecases] .ucrow').length"), 0)


if __name__ == "__main__":
    unittest.main()
