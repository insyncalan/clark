"""Help against the prototype (v0.9, "Help: entries still missing"): every Help entry of the prototype is shown, held for a
reason, replaced by an entry of the build, or waiting for a feature that is not on the page; and what is shown names only what the page has.

Run: python3 dev/run_tests.py test_help_parity
Quick tier: reads files, starts no browser.

HOW TO USE THIS WHEN A FEATURE ARRIVES. WAITS lists, for each prototype entry the build does not have, the feature it needs and a marker
that must NOT be on the page yet. When the feature's PR merges, the marker matches and the test names the entry to write: write it
from the prototype's words, changed to what the page does, then take its line out of WAITS.
"""
import json
import re
import unittest

from _help_shown import LATER, RAW, shown_content
from _paths import ROOT
from test_help_shown import page_code, strip_comments, strings

PROTO_HELP = (ROOT / "system" / "prototype" / "help.js").read_text(encoding="utf-8")
SRC = ROOT / "src" / "clark"
SHOWN = shown_content()
PAGE = page_code()                      # the page's own code, Help's words left out


def read(*parts):
    return (SRC.joinpath(*parts)).read_text(encoding="utf-8")


# prototype entry id (howto- or ref-) -> (the feature it needs, a pattern that must NOT yet match the page's code, and the one file to look in when it is not all of it)
WAITS = {
    "howto-check-before-you-publish": ("the stale and incomplete notes with Show them in the Publish box", r"Show them"),
    "howto-find-a-past-publication": ("the Published reports list (numbered publications)", r"Published reports"),
    "ref-published-reports": ("the Published reports list (numbered publications)", r"Published reports"),
    "howto-start-from-last-report": ("Start from last week's report", r"Start from last"),
    "ref-since-last-report": ("the Since the last report panel", r"Since the last report"),
    "howto-save-as-a-pdf": ("the PDF option in the Publish box", r"PDF", ("page", "src", "edit", "Publish.jsx")),
    "howto-add-people-details": ("the People card in Settings", r"[\"'>]People[\"'<]"),
    "ref-people": ("the People card in Settings", r"[\"'>]People[\"'<]"),
}
# prototype entries the build has under another id, written for what the page does
REPLACED = {
    "howto-work-the-use-cases": "howto-find-a-use-case",
    "howto-ask-the-client-for-something": "howto-ask-for-what-you-need",
}


def prototype_ids():
    """The ids of the prototype's How do I entries and Reference sections, in its order, as howto-/ref- places."""
    how_at = PROTO_HELP.index("const TASKS")
    ref_at = PROTO_HELP.index("const REF_GROUPS")
    out = []
    for kind, lo, hi in (("howto", how_at, ref_at), ("ref", ref_at, len(PROTO_HELP))):
        out += [f"{kind}-{m}" for m in re.findall(r"^\s*\{ id: '([^']+)', g: '", PROTO_HELP[lo:hi], re.M)]
    return out


def shown_ids():
    return {"howto-" + t["id"] for t in SHOWN["howto"]["tasks"]} | {"ref-" + t["id"] for t in SHOWN["reference"]["sections"]}


def held_ids():
    return {"howto-" + k for k in LATER["howto"]} | {"ref-" + k for k in LATER["reference"]}


class EveryPrototypeEntryIsAccountedFor(unittest.TestCase):
    def test_the_prototype_has_the_entries_this_test_expects(self):
        ids = prototype_ids()
        self.assertEqual((len([i for i in ids if i.startswith("howto-")]), len([i for i in ids if i.startswith("ref-")])), (33, 36))

    def test_each_one_is_shown_held_replaced_or_waiting(self):
        known = shown_ids() | held_ids() | set(WAITS) | set(REPLACED)
        self.assertEqual([i for i in prototype_ids() if i not in known], [], "a prototype Help entry the build neither shows, holds nor waits for")

    def test_a_waiting_entry_is_not_in_the_source_and_its_feature_is_not_on_the_page(self):
        source = {"howto-" + t["id"] for t in RAW["howto"]["tasks"]} | {"ref-" + t["id"] for t in RAW["reference"]["sections"]}
        for place, (feature, marker, *where) in WAITS.items():
            self.assertNotIn(place, source, f"{place} is written: take it out of WAITS and hold or show it")
            code = read(*where[0]) if where else PAGE          # one file, or all the page's code
            self.assertNotRegex(code, marker, f"{feature} is on the page now: write {place} from the prototype's words, for what the page does")

    def test_a_replaced_entry_is_shown(self):
        for old, new in REPLACED.items():
            self.assertIn(new, shown_ids(), f"{new} replaces the prototype's {old}")

    def test_the_prototype_entries_released_here_are_shown(self):
        want = {"howto-set-the-health", "howto-handle-a-slipped-milestone", "ref-sections", "ref-needs-from-you", "ref-freshness", "ref-milestones-page", "ref-diagnostics"}
        self.assertEqual(sorted(want - shown_ids()), [])
        self.assertEqual(sorted(want & held_ids()), [])


class WhatIsShownIsOnThePage(unittest.TestCase):
    """Every control or label a shown entry names (its bold names, its quoted words, the first cell of a table row) is a word the page holds
    in its own source: the page's code, Help's own code, the tile titles and the default section titles."""
    SOURCES = [page_code(include_help=True), strip_comments(read("glance.py")), read("default_sections.py")]
    CORPUS = re.sub(r"[‘’]", "'", "\n".join(SOURCES))

    @staticmethod
    def labels_of(entry):
        out = set()
        for t in strings(entry):
            out |= set(re.findall(r"\*\*(.+?)\*\*", t)) | set(re.findall(r"“(.+?)”", t))
        for b in entry.get("b", []):
            if b[0] == "tbl":
                for row in b[2]:
                    out |= set(row[0].split(", "))
        return {re.sub(r"\s*\(.*?\)\s*$", "", x).strip(" .,:;…") for x in out}

    def on_page(self, label):
        label = re.sub(r"[‘’]", "'", label)
        return bool(re.search(r"(?<![\w])" + re.escape(label) + r"(?![\w])", self.CORPUS))

    def missing(self, entries):
        return sorted({f"{e['id']}: {x}" for e in entries for x in self.labels_of(e) if not self.on_page(x)})

    def test_every_label_in_a_shown_entry_is_on_the_page(self):
        self.assertEqual(self.missing(SHOWN["howto"]["tasks"] + SHOWN["reference"]["sections"]), [])

    def test_the_check_fails_on_a_made_up_label(self):
        bad = {"id": "x", "b": [["p", "Press **Frobnicate** or see “Widget zone”."], ["tbl", ["A", "B"], [["Gizmo row", "c"]]]]}
        self.assertEqual(self.missing([bad]), ["x: Frobnicate", "x: Gizmo row", "x: Widget zone"])


def entry(kind, id_):
    rows = SHOWN["howto"]["tasks"] if kind == "howto" else SHOWN["reference"]["sections"]
    return next(x for x in rows if x["id"] == id_)


class ReportSectionsHasNeedsFromYou(unittest.TestCase):
    """Row 63: Report sections has a Needs from you row, and the whole table says only what the page draws."""
    TABLE = next(b for b in entry("ref", "sections")["b"] if b[0] == "tbl")

    def test_the_row_is_there_and_names_the_section_as_the_page_does(self):
        row = next(r for r in self.TABLE[2] if r[0] == "Needs from you")
        self.assertIn("what you need from the client", row[1])
        self.assertIn("[Needs from you](#ref-needs-from-you)", row[1])
        self.assertEqual(self.TABLE[2][-1][0], "Needs from you", "the prototype puts it last")
        self.assertIn("title: \"Needs from you\"", read("page", "src", "logic", "needs.js").replace("  title:", "title:"))

    def test_what_the_row_says_is_what_the_page_does(self):
        row = next(r for r in self.TABLE[2] if r[0] == "Needs from you")[1]
        words = read("page", "src", "logic", "needs.js")
        self.assertIn("rows you add yourself", row)
        self.assertIn('addRow: "Add a row"', words)                      # the rows are added by hand
        self.assertIn("Left out of the published page when no row is shown", row)
        self.assertRegex(read("page", "src", "components", "Dashboard.jsx"), r's\.type === "needs" && !hasNeeds\(s\)')       # left out when no row is shown
        self.assertNotRegex(row, r"(?i)pending decision|Needed from the client|straight after|Word file")     # what the page does not do (yet)

    def test_the_table_has_no_row_for_a_section_the_page_does_not_draw(self):
        """Risks and issues, Open actions, Decisions and Supporting documents show 'Not shown on this page yet.' (Section.jsx), as does Current state in Edit."""
        names = [r[0] for r in self.TABLE[2]]
        self.assertEqual(names, ["At a glance", "Use case summary", "Milestones", "Summary, This week, Next week", "Needs from you"])
        section = read("page", "src", "components", "Section.jsx")
        self.assertIn("Not shown on this page yet.", section)
        for t in ("raid", "actions", "decisions", "docs"):
            self.assertNotRegex(section, rf'section\.type === "{t}"')

    def test_the_needs_entry_links_to_the_task_and_the_task_is_shown(self):
        self.assertIn("(#howto-ask-for-what-you-need)", json.dumps(entry("ref", "needs-from-you"), ensure_ascii=False))
        entry("howto", "ask-for-what-you-need")


class TheWeekEndsOnAFriday(unittest.TestCase):
    """Row 64 (needs the owner): the prototype says 'The week ends on a Friday.' The page has no such rule, so the line stays out of Help."""
    def test_help_does_not_say_it(self):
        every = json.dumps(SHOWN, ensure_ascii=False)
        self.assertNotIn("The week ends on a Friday", every)

    def test_the_page_has_no_friday_week_end(self):
        """The 'this week' of the Work items filters ends on a Sunday (client_filters.week_end, logic/board.js), and the week ending of a
        report is typed in: no default to a Friday. When the owner decides, either the page changes or Help says what it does."""
        from clark import client_filters
        self.assertEqual(client_filters.week_end("2026-11-02", 0), "2026-11-08")          # a Monday: the Sunday after
        self.assertIn("the week ends on Sunday", read("page", "src", "logic", "board.js"))
        self.assertNotRegex(read("publish_flow.py") + read("store.py"), r"(?i)friday")


class MovementEntries(unittest.TestCase):
    """Row 65: a search for movement finds Help, and what it says is what the Movement block has."""
    WORDS = read("page", "src", "edit", "movementWords.js")
    BLOCK = read("page", "src", "edit", "Movement.jsx")

    def test_the_two_entries_name_only_buttons_and_fields_the_block_has(self):
        text = " ".join(strings(entry("howto", "handle-a-slipped-milestone")))
        for name in re.findall(r"\*\*(.+?)\*\*", text):
            base = re.sub(r"\s*\(.*?\)\s*$", "", name)
            if base not in ("Milestones", "Undo"):
                self.assertIn(base, self.WORDS + self.BLOCK, name)
        for gone in ("Rebaseline", "Add a recovery action", "Escalate to steering", "Internal note", "diamond", "red line"):
            self.assertNotIn(gone, text, f"the page has no {gone}")

    def test_the_block_is_edit_only_and_never_published(self):
        self.assertIn("data-edit-only", self.BLOCK)
        self.assertIn("never published", self.WORDS)
        ref = json.dumps(entry("ref", "milestones-page"), ensure_ascii=False)
        self.assertIn("In Edit, **Movement** is under the list", ref)
        self.assertNotIn("Plan", " ".join(strings(entry("ref", "milestones-page"))))        # the page has no tab called Plan

    def test_the_rows_keys_are_the_arrows(self):
        self.assertIn("ArrowDown", self.BLOCK)
        self.assertIn("move between rows with [[Up]] and [[Down]] and press [[Enter]], to choose it.", " ".join(strings(entry("howto", "handle-a-slipped-milestone"))))

    def test_a_move_is_only_open_when_it_has_slipped(self):
        self.assertIn("can_move", self.BLOCK)
        self.assertIn("A milestone that has not slipped cannot be moved.", " ".join(strings(entry("howto", "handle-a-slipped-milestone"))))


class DiagnosticsEntry(unittest.TestCase):
    """Row 65: a search for diagnostics finds Help, and what it says is what Settings and the log do."""
    TEXT = " ".join(strings(entry("ref", "diagnostics")))
    PAGE = read("page", "src", "edit", "Diagnostics.jsx")

    def test_it_names_the_controls_the_card_has(self):
        for name in ("Normal", "Debug", "Open folder", "Copy diagnostics", "Errors in the last 7 days"):
            self.assertIn(f"**{name}**", self.TEXT)
            self.assertIn(name, self.PAGE)
        self.assertNotIn("Open the folder", self.TEXT)
        self.assertNotIn("**Log level**", self.TEXT)
        self.assertEqual(entry("ref", "diagnostics")["w"], "Settings › Logs and diagnostics")
        self.assertIn("<h2>Logs and diagnostics</h2>", self.PAGE)

    def test_the_numbers_are_the_log_s(self):
        log, diag = read("log.py"), read("diagnostics.py")
        self.assertIn("MAX_BYTES = 5 * 1024 * 1024", log)           # 5 MB a day
        self.assertIn("KEEP_DAYS = 7", log)                         # today and the six days before
        self.assertIn("DEBUG_NOTICE_AFTER_DAYS = 7", log)           # Settings' note after a week of Debug
        self.assertIn("LAST_LINES = 200", diag)                     # the last 200 log lines in the copy
        self.assertIn("5 MB at most", self.TEXT)
        self.assertIn("today and the six days before it are kept", self.TEXT)
        self.assertIn("last 200 log lines", self.TEXT)
        self.assertNotIn("last 20 log lines", self.TEXT)

    def test_the_report_holds_no_browser_and_says_only_what_it_holds(self):
        self.assertNotIn("browser", self.TEXT)
        diag = read("diagnostics.py")
        self.assertIn('f"Version:', diag)
        self.assertIn('f"System:', diag)
        self.assertIn('f"Logging:', diag)


class FreshnessEntry(unittest.TestCase):
    TEXT = " ".join(strings(entry("ref", "freshness")))

    def test_it_names_what_the_peek_and_the_filter_have(self):
        peek = read("page", "src", "components", "Peek.jsx")
        for name in ("Raised", "Last reviewed"):
            self.assertIn(f'name="{name}"', peek)
            self.assertIn(f"**{name}**", self.TEXT)
        self.assertIn("staleWords", peek)
        filters = read("page", "src", "filters.js")
        self.assertIn('reviewed: "Freshness"', filters)
        self.assertIn("REVIEW_DAYS = 14", filters)
        self.assertIn("Not reviewed in 14 days", self.TEXT)
        self.assertIn("No owner or no date", filters)
        self.assertIn("No owner or no date", self.TEXT)
        self.assertIn('["incomplete", "No owner or no date"]', filters)

    def test_it_does_not_say_what_the_rule_leaves_out(self):
        rule = read("freshness.py")
        self.assertRegex(rule, r"an import\s+\(route excel")                    # an import is not a review, but the page has no import: Help does not mention one
        self.assertNotIn("Excel", self.TEXT)
        self.assertNotIn("ask clark", self.TEXT)                        # the page does not call its panel that
        self.assertIn("Closed, cancelled, made and withdrawn items and archived items are never flagged", rule)
        self.assertIn("open action, risk, issue or decision", self.TEXT)


class HealthStepsSayWhatThePageDoes(unittest.TestCase):
    TEXT = " ".join(strings(entry("howto", "set-the-health")))

    def test_the_keys_and_words_are_the_tile_s(self):
        tile = read("page", "src", "edit", "GlanceEdit.jsx")
        self.assertIn('e.key === "Escape"', tile)                          # Esc puts the old words back
        self.assertNotIn("Enter", tile.split("function Reason")[1].split("export const GLANCE")[0])      # so there is no Mod+Enter to keep it
        self.assertNotIn("Mod+Enter", self.TEXT)
        self.assertIn("A health change needs a reason", tile)
        for name in ("On track", "At risk", "Off track", "Project health"):
            self.assertIn(f"**{name}**", self.TEXT)

    def test_no_check_that_ask_clark_does_not_make(self):
        self.assertNotIn("ask clark", self.TEXT)
        self.assertNotIn("warns you", self.TEXT)


if __name__ == "__main__":
    unittest.main()
