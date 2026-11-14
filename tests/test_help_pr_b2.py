"""Help PR B2: the words for the Commitment flag on the page (#692), the week ending calendar button (#684) and the pencil on Edit (#683),
each pinned against the page code. Reads files only; starts no browser.

Run: python3 dev/run_tests.py test_help_pr_b2
"""
import json
import unittest

from _paths import ROOT

PAGE = ROOT / "src" / "clark" / "page" / "src"
RAW = json.loads((PAGE / "help" / "helpContent.json").read_text(encoding="utf-8"))
LATER = json.loads((PAGE / "help" / "helpLater.json").read_text(encoding="utf-8"))
TASKS = {t["id"]: t for t in RAW["howto"]["tasks"]}
SECS = {s["id"]: s for s in RAW["reference"]["sections"]}


def flat(o):
    if isinstance(o, str):
        return o
    if isinstance(o, list):
        return " ".join(flat(x) for x in o)
    if isinstance(o, dict):
        return " ".join(flat(v) for k, v in o.items() if k not in ("id", "g", "go"))
    return ""


def code(*parts):
    return (PAGE.joinpath(*parts)).read_text(encoding="utf-8")


class Commitment(unittest.TestCase):
    def test_keep_the_use_cases_sentences(self):
        t = flat(TASKS["keep-the-use-cases"])
        for sentence in (
            "A use case can carry a commitment: Planned 2026, Committed or Planned 2027. It shows as a small chip beside the status on the Dashboard, on the Use cases page and on the published page, and nothing shows when there is none.",
            "In Edit, a small menu beside the status reads **Set commitment** when there is none: choose a word, or **No flag** to clear it. Each choice is one change, with one Undo and one line in History.",
            "A published file shows the chip but never the menu. A use case taken off the page with the eye is left out of the published file whole, chip and all.",
        ):
            self.assertIn(sentence, t)
        self.assertNotIn("The client sees it beside the status", t)
        self.assertIn("keep-the-use-cases", LATER["howto"], "still held: this PR unholds nothing")

    def test_find_a_use_case_sentences_are_shown(self):
        t = flat(TASKS["find-a-use-case"])
        self.assertIn("A use case with a commitment shows it as a small chip beside the status.", t)
        self.assertIn("The small menu beside the status there reads **Set commitment**: choose a word, or **No flag**. Each choice is one change, with one Undo and one line in History.", t)
        self.assertNotIn("find-a-use-case", LATER["howto"])

    def test_words_and_places_in_the_code(self):
        menu = code("edit", "CommitMenu.jsx")
        self.assertIn('SET_WORDS = "Set commitment"', menu)
        self.assertIn('NO_FLAG = "No flag"', menu)
        self.assertIn("data-edit-only", menu)
        self.assertIn("kind: \"use_cases\", op: \"update\"", menu)           # one change (so one Undo and one History line)
        self.assertIn("commitment set to", menu)
        chip = code("components", "CommitChip.jsx")
        self.assertIn("return w ? <span", chip)                              # nothing is drawn with no flag
        self.assertIn(": null;", chip)
        self.assertIn("<CommitChip", code("components", "UseCases.jsx"))     # Dashboard rows
        self.assertIn("<ed.Commit", code("components", "UseCases.jsx"))      # the menu only where Edit is
        self.assertIn("<CommitChip", code("components", "UseCasesTab.jsx"))  # the published Use cases tab
        self.assertIn("<CommitChip", code("edit", "UseCasesPage.jsx"))       # the Use cases page
        detail = code("components", "UseCaseDetail.jsx")
        self.assertIn("ro ? <CommitChip u={u} /> : <CommitMenu u={u} left />", detail)
        self.assertIn("Commit: CommitMenu", code("edit", "UseCasesEdit.jsx"))

    def test_the_three_words_and_the_published_file(self):
        store = (ROOT / "src" / "clark" / "store.py").read_text(encoding="utf-8")
        self.assertIn('COMMITMENTS = ("Planned 2026", "Committed", "Planned 2027")', store)
        pub = (ROOT / "src" / "clark" / "publish.py").read_text(encoding="utf-8")
        self.assertIn('"use_cases": ("client_visible", "archived")', pub)   # the eye: a use case that is off is not in the file at all
        self.assertIn('"sort_order", "commitment")', pub)
        tests = (ROOT / "tests" / "test_commitment_page.py").read_text(encoding="utf-8")
        self.assertIn('for edit_only in ("Set commitment", "No flag"', tests)  # that test pins: no menu in the published bytes


class WeekEnding(unittest.TestCase):
    def test_step_two(self):
        s = TASKS["write-the-weekly-report"]["s"][1]
        self.assertEqual(s, "Set **Week ending** to the Friday the report covers: type it as DD-MM-YYYY, press [[Enter]] in the box to use the Friday shown (only while no week is kept yet), or press the calendar button beside the box and pick the day. In the calendar, **Friday** takes the next Friday (today, if it is one). Any other day is not accepted.")
        self.assertNotIn("write-the-weekly-report", LATER["howto"])

    def test_code(self):
        bar = code("edit", "HeaderDate.jsx")      # item 1177: the week box and its calendar button became the header date (HeaderDate.jsx)
        self.assertIn('id="week-ending-pick"', bar)
        self.assertIn('title="Click to change date"', bar)
        self.assertIn("quick={[weekEndingQuick(todayIso())]}", bar)
        self.assertIn('return ["Friday", addDays(today, (5 - wd + 7) % 7)]', code("edit", "itemEdit.js"))   # 0 days on a Friday
        self.assertIn("isFriday", bar)                                          # a picked day goes through the same Friday check


class Pencil(unittest.TestCase):
    def test_icons_row(self):
        row = ["pencil", "Edit", "Switch the Dashboard to Edit. It is on the **Edit** half of the **View** and **Edit** switch, the floating pill just under the header at the right.", "Dashboard"]
        self.assertIn(json.dumps(row, ensure_ascii=False), json.dumps(RAW, ensure_ascii=False))
        self.assertEqual(json.dumps(RAW).count("Switch the Dashboard to Edit"), 1)
        self.assertIn("icons", LATER["reference"], "still held: this PR unholds nothing")

    def test_code(self):
        tg = code("edit", "ModePill.jsx")      # item 1177: the pill is icon-only and floats under the header
        self.assertIn('<svg class="tb-ico"', tg)
        self.assertIn('M13.5 3.5l3 3L7 16H4v-3z', tg)
        self.assertIn('data-mode="edit"', tg)
        self.assertIn("<ModePill />", code("edit", "ReportBar.jsx"))


class Style(unittest.TestCase):
    def test_new_sentences_are_plain(self):
        import re
        t = flat(TASKS["keep-the-use-cases"]) + flat(TASKS["find-a-use-case"]) + flat(TASKS["write-the-weekly-report"])
        self.assertNotRegex(t.replace("DD-MM-YYYY", ""), r"\b\d{2}-\d{2}-\d{4}\b")
        self.assertIn("Planned 2027", t)


if __name__ == "__main__":
    unittest.main()
