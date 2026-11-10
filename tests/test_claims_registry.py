"""#233: Help, the product page and the published text may only claim what a proof backs (tests/_claims.py).

Run: python3 dev/run_tests.py test_claims_registry
Quick tier: reads files, starts no browser.

Part one is the worked example: the six claims PR 58 (#82) shipped that the page did not back, as a fixture. Each must be flagged,
by name and file, and the same claim must pass the moment the fixture page really has the thing (so the flag is not just "always red").
Part two is the real registry: each claim listed in CLAIMS is in its file as written and is backed by the page today. To cover a new
claim, add a Claim with its proof; to drop one, delete the words from the file and the line here.
"""
import unittest

from _claims import Claim, component, selector, test as proof_test, unbacked
from _paths import ROOT, TESTS

PAGE_SRC = ROOT / "src" / "clark" / "page" / "src"
HELP_FILE = "helpContent.json"

# The six findings of PR 58, each as the words Help used and the proof that was missing. Page fixture: what that page had.
PR58 = [
    Claim("search", "the search", HELP_FILE, selector(r'type="search"')),
    Claim("import-export-icons", "the import and export icons and +", HELP_FILE, selector(r'aria-label="(Import|Export)"')),
    Claim("eye-column", "The eye: Client-visible", HELP_FILE, selector(r'<th class="c-eye"')),
    Claim("picker", "Add from your project record", HELP_FILE, component("Picker")),
    Claim("done-grey", "Done (grey)", HELP_FILE, selector(r'"Done"')),
    Claim("cover", "the cover", HELP_FILE, selector(r'class="cover"')),
]
PR58_TEXT = {HELP_FILE: "the search; the import and export icons and +; The eye: Client-visible; Add from your project record; Done (grey); the cover"}
PR58_PAGE = {                      # what the page of that day had: no search box, no icons, six columns, an unmounted Picker, and no cover
    "components/WorkItems.jsx": '<th class="c-type">Type</th><th class="c-item">Item</th><th>Owner</th><th>Due</th><th>Priority</th><th>Status</th>',
    "components/Picker.jsx": "export function Picker() { return <input/> }",
    "components/UseCases.jsx": 'const STATUS = ["On track", "Flag", "High risk"]',
    "logic/filterLine.js": "export const parse = () => []",       # imported only by a test fixture, so not by any page file
}
FOUND_LATER = {                    # for each claim, a page that really has the thing
    "search": {"components/WorkItems.jsx": '<input type="search">'},
    "import-export-icons": {"components/Bar.jsx": '<button aria-label="Export">'},
    "eye-column": {"components/WorkItems.jsx": '<th class="c-eye">'},
    "picker": {"edit/Bulk.jsx": "import { Picker } from '../components/Picker'"},
    "done-grey": {"components/UseCases.jsx": 'const S = ["Done"]'},
    "cover": {"components/Report.jsx": '<div class="cover">'},
}


class PR58Fixture(unittest.TestCase):
    def test_each_of_the_six_unbacked_claims_is_flagged_with_its_claim_and_file(self):
        for c in PR58:
            with self.subTest(c.id):
                got = unbacked([c], PR58_TEXT, PR58_PAGE, {})
                self.assertEqual(len(got), 1, f"{c.id}: the check let an unbacked claim through")
                self.assertIn(c.text, got[0])
                self.assertIn(HELP_FILE, got[0])
                self.assertIn(c.id, got[0])

    def test_the_six_together_report_six(self):
        self.assertEqual(len(unbacked(PR58, PR58_TEXT, PR58_PAGE, {})), 6)

    def test_a_claim_passes_when_the_page_really_has_the_thing(self):
        for c in PR58:
            with self.subTest(c.id):
                page = dict(PR58_PAGE, **FOUND_LATER[c.id])
                self.assertEqual(unbacked([c], PR58_TEXT, page, {}), [])

    def test_a_word_somewhere_in_the_source_is_not_a_proof(self):
        """The old check passed on 'the search' because the word was in the code. A comment or a test-only module does not back the claim."""
        page = dict(PR58_PAGE, **{"logic/other.js": "// the search is not built; type=\"search\" is for later"})
        self.assertEqual(len(unbacked([PR58[3]], PR58_TEXT, page, {})), 1)           # the Picker is still mounted nowhere
        self.assertEqual(len(unbacked([PR58[0]], PR58_TEXT, {"logic/filterLine.js": "const q = 1"}, {})), 1)

    def test_a_test_proof_needs_the_test_to_exist(self):
        c = Claim("x", "the thing", HELP_FILE, proof_test("test_thing.py", "test_the_thing_works"))
        text = {HELP_FILE: "the thing"}
        self.assertEqual(len(unbacked([c], text, {}, {})), 1)
        self.assertEqual(len(unbacked([c], text, {}, {"test_thing.py": "def test_other(self):"})), 1)
        self.assertEqual(unbacked([c], text, {}, {"test_thing.py": "def test_the_thing_works(self):"}), [])

    def test_a_claim_gone_from_its_file_is_reported_stale(self):
        got = unbacked([PR58[0]], {HELP_FILE: "nothing here"}, PR58_PAGE, {})
        self.assertEqual(len(got), 1)
        self.assertIn("is not in", got[0])


def page_without_help():
    out = {}
    for f in sorted(PAGE_SRC.rglob("*")):
        if f.is_file() and f.suffix in (".js", ".jsx") and f.parent.name != "help":
            out[str(f.relative_to(PAGE_SRC))] = f.read_text(encoding="utf-8")
    return out


# What Help says today, each with the thing that proves it. Every line was checked against the page when it was added.
CLAIMS = [
    Claim("published-search", "**Search work items** box", HELP_FILE, selector(r'<input id="q" type="search"')),
    Claim("show-archived-button", "**Show archived**", HELP_FILE, selector(r"Show archived")),
    Claim("settings-logs-card", "Settings › Logs and diagnostics", HELP_FILE, component("Diagnostics")),
    Claim("settings-publishing-card", "Settings › Folder", HELP_FILE, component("ClientFolder")),
    Claim("settings-personal-card", "Settings › Appearance", HELP_FILE, component("Personal")),
]


class RealRegistry(unittest.TestCase):
    TEXTS = {HELP_FILE: (PAGE_SRC / "help" / HELP_FILE).read_text(encoding="utf-8")}
    PAGE = page_without_help()
    TESTS = {p.name: p.read_text(encoding="utf-8") for p in TESTS.glob("test_*.py")}

    def test_every_registered_claim_is_in_its_file_and_backed_by_the_page(self):
        self.assertEqual(unbacked(CLAIMS, self.TEXTS, self.PAGE, self.TESTS), [])

    def test_the_registry_has_claims_and_unique_ids(self):
        ids = [c.id for c in CLAIMS]
        self.assertGreaterEqual(len(ids), 5)
        self.assertEqual(len(ids), len(set(ids)))

    def test_the_check_bites_on_the_real_tree(self):
        """A made-up claim about a component the real page does not have is flagged."""
        c = Claim("made-up", "Search work items", HELP_FILE, component("NoSuchComponent"))
        self.assertEqual(len(unbacked([c], self.TEXTS, self.PAGE, self.TESTS)), 1)


if __name__ == "__main__":
    unittest.main()
