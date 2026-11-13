"""Help PR B3: the words for the client Report menu in a published file (#681, #687) and for the Excel export cells (#672): 'ID: name',
'Open work items', the Cover and the sheet name 'Risks & Issues'. Each sentence is pinned against the code that makes it true.
Reads files only; starts no browser.

Run: python3 dev/run_tests.py test_help_pr_b3
"""
import json
import unittest

from _paths import ROOT

PAGE = ROOT / "src" / "clark" / "page" / "src"
SRC = ROOT / "src" / "clark"
RAW = json.loads((PAGE / "help" / "helpContent.json").read_text(encoding="utf-8"))
LATER = json.loads((PAGE / "help" / "helpLater.json").read_text(encoding="utf-8"))
SECS = {s["id"]: s for s in RAW["reference"]["sections"]}
GUIDES = {g["id"]: g for g in RAW["guides"]}


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


def py(name):
    return (SRC / name).read_text(encoding="utf-8")


class ReportMenu(unittest.TestCase):
    def test_the_bullet_and_the_code_behind_each_sentence(self):
        t = flat(SECS["client-page"])
        for sentence in (
            "The round button at the top right opens the **Report menu**: **Profile**, **Export to Excel** (only when the file holds a workbook; when the report is too large to include one, the row is greyed and a note says so), **Export to PDF** and **Past reports**.",
            "**Profile** keeps the reader’s name in their own browser only, and the button then shows their initials.",
            "**Past reports** lists earlier reports kept in the same folder as this one, newest first, and opens the one you press; with none it says No earlier reports.",
        ):
            self.assertIn(sentence, t)
        self.assertIn("client-page", LATER["reference"], "still held: this PR unholds nothing")
        menu = code("components", "ClientMenu.jsx")
        for w in ('menu: "Report menu"', 'profile: "Profile"', 'excel: "Export to Excel"', 'pdf: "Export to PDF"', 'past: "Past reports"', 'theme: "Switch between light and dark"',
                  'none: "No earlier reports."', "Kept only in this browser",
                  "{book ? item(\"excel\"", "{big ? ", "{ini ?"):
            self.assertIn(w, menu)
        self.assertLess(menu.index("WORDS.profile"), menu.index("WORDS.excel", menu.index("WORDS.profile")))
        self.assertIn("fromFile.value ? <ClientMenu", code("components", "TopBar.jsx"))

    def test_the_workbook_row_depends_on_the_file(self):
        """Keep the condition: the workbook can be left out for size or when it cannot be made (publish.py build, excel_client.embed)."""
        pub, cl = py("publish.py"), py("excel_client.py")
        self.assertIn("client_workbook_too_large", cl)
        self.assertIn("MAX_WORKBOOK_BYTES", cl)
        self.assertIn("The client workbook could not be made", pub)
        self.assertIn("the report is the thing: no spreadsheet is better than no report", pub)
        self.assertIn("if (!isObj(w) || typeof w.base64", code("logic", "clientMenu.js"))

    def test_past_reports_is_the_folder_newest_first(self):
        pf, lg = py("past_files.py"), code("logic", "clientMenu.js")
        self.assertIn("found.sort(key=lambda r: r[0], reverse=True)", pf)
        self.assertIn("-report-", pf)
        self.assertIn("a.iso < b.iso ? 1", lg)
        self.assertIn("href: encodeURIComponent(r.file)", lg)
        self.assertIn("past.length ? WORDS.sameFolder : WORDS.none", code("components", "ClientMenu.jsx"))
        self.assertIn("past = past_files.listing(dest.parent, code, dest.name)", py("publish_flow.py"))

    def test_profile_and_dark_mode_are_kept_in_the_browser(self):
        rd = code("stores", "reader.js")
        self.assertIn("localStorage", rd)
        self.assertIn('v === "system"', rd)
        self.assertIn("lightForPrint", code("stores", "print.js"))


class ExcelCells(unittest.TestCase):
    def test_the_excel_paragraph(self):
        t = flat(SECS["excel"])
        for sentence in (
            "On the Actions, Risks & Issues and Decisions sheets, a Milestone or Use case cell reads “ID: name”; on import only the ID before the first colon counts, so renaming a milestone is not a change.",
            "The Milestones and Use cases sheets have an Open work items column that lists the IDs of the open actions, risks and issues and decisions linked to that row; it is worked out for the sheet and never read back.",
            "and Priority on Risks & Issues.",
        ):
            self.assertIn(sentence, t)
        self.assertNotIn("Risks and issues", t)
        ex, im = py("excel.py"), py("excel_import.py")
        self.assertIn('("Risks & Issues", "raid"', ex)
        self.assertIn('return f"{item_id}: {name}"', ex)
        self.assertIn('("Milestone", "milestone")', ex)
        self.assertIn('if table in ("milestones", "use_cases")', ex)
        self.assertIn("names[f].get(r.get(f), r.get(f)) for f in REF_TABLES", ex)
        self.assertIn('head, sep, _ = text.partition(": ")', im)
        self.assertIn("renamed milestone still resolves", im)
        self.assertIn('DERIVED = {"original_date", "shown_state", "open_items"}', ex)
        self.assertEqual(ex.count('("Open work items", "open_items")'), 2)
        self.assertIn("glance.is_open(r)", ex)
        self.assertIn('OPEN_TABLES = (("actions", "milestone"), ("raid", "milestone"), ("decisions", "milestone")', ex)
        self.assertIn('SHEET_TABLES["risks and issues"] = "raid"', im, "the old name is still read")

    def test_the_cover_step(self):
        step = GUIDES["send-the-workbook-out"]["steps"][4]["d"]
        for sentence in (
            "Open the file. It opens on the Cover: a title band with the project name, tagged INTERNAL, and under it a line with Weekly report, the week ending and who it is for.",
            "Then come the sections the published page shows, in the report’s order: the current state, the At a glance tiles side by side (the health is one of them) and the text sections, with This week and Next week side by side when both have words.",
            "A quiet About this export block comes last: when it was exported and by whom, a caution that it shows the project as it was on that date, who to send changes back to, where to make changes, and a note on IDs.",
        ):
            self.assertIn(sentence, step)
        cv, ex = py("excel_cover.py"), py("excel.py")
        self.assertIn('SUBTITLE_KIND', cv)
        self.assertIn('parts.append(f"Week ending {long_date(week)}")', cv)
        self.assertIn('parts.append(f"for {client}")', cv)
        self.assertIn('title["tag"] = INTERNAL_TAG', cv)
        self.assertIn('== "this week" and nxt.get("type") == "text"', cv)
        self.assertIn('shown = [s for s in sections or [] if not s.get("hidden")]', cv)
        self.assertLess(cv.index('_line("about", ABOUT)'), cv.index('_line("ids", IDS)'))
        self.assertIn("ws = wb.create_sheet(COVER_NAME, 0)", ex)
        self.assertIn("a quiet About this export block", ex)

    def test_the_tab_order_and_the_page_words_already_say_risks_and_issues_with_an_ampersand(self):
        step = GUIDES["send-the-workbook-out"]["steps"][5]["d"]
        self.assertIn("Actions, Risks & Issues, Decisions, Milestones and Use cases", step)
        order = [py("excel.py").index(f'    ("{n}", "{t}"') for n, t in (("Actions", "actions"), ("Risks & Issues", "raid"), ("Decisions", "decisions"), ("Milestones", "milestones"), ("Use cases", "use_cases"))]
        self.assertEqual(order, sorted(order))
        self.assertIn("Sheets called Actions, Risks & Issues, Decisions, Milestones and Use cases", code("logic", "dataCard.js"))
        self.assertIn("sheets called Actions, Risks & Issues (or Risks and issues, or RAID)", flat(GUIDES["bring-in-an-excel-workbook"]))


if __name__ == "__main__":
    unittest.main()
