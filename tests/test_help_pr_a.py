"""Help PR A: the words about the top bar and palette, the typed filter, Settings, ask clark when asking is off, bash clark.command and the
Excel columns, each pinned against the code that makes it true. Reads files only; starts no browser.

Run: python3 dev/run_tests.py test_help_pr_a
"""
import json
import re
import unittest

from _paths import ROOT

SRC = ROOT / "src" / "clark"
PAGE = SRC / "page" / "src"
RAW = json.loads((PAGE / "help" / "helpContent.json").read_text(encoding="utf-8"))
TASKS = {t["id"]: t for t in RAW["howto"]["tasks"]}
SECS = {s["id"]: s for s in RAW["reference"]["sections"]}


def code(*parts):
    return (PAGE.joinpath(*parts)).read_text(encoding="utf-8")


def flat(o):
    if isinstance(o, str):
        return o
    if isinstance(o, list):
        return " ".join(flat(x) for x in o)
    if isinstance(o, dict):
        return " ".join(flat(v) for k, v in o.items() if k not in ("id", "g", "go"))
    return ""


class TopBar(unittest.TestCase):
    def test_the_help_has_no_logo_bullet_the_logo_has_no_help_line_of_its_own(self):      # row 854: the logo is now a Home button; Help gained no new sentence
        self.assertNotIn("back to the Dashboard", flat(SECS["top-bar"]))
        self.assertNotIn("The logo", flat(SECS["top-bar"]))

    def test_ctrl_or_cmd_j_is_handled_and_the_ask_tooltip_names_it(self):
        """Row 855: askPanelState.js handles Ctrl or Cmd + J and the ask button's tooltip names it (Help's keys row waits for approved words)."""
        self.assertRegex(code("edit", "askPanelState.js"), r'"j"[^\n]*metaKey \|\| e\.ctrlKey')
        self.assertIn("Open ask clark (/ or Ctrl or Cmd + J)", code("edit", "AskButton.jsx"))

    def test_the_search_button_and_palette_sentence(self):
        text = flat(SECS["top-bar"])
        self.assertIn("The magnifying glass opens **Go to or do**, the same box as [[Mod+K]].", text)
        self.assertIn('aria-label="Go to or do"', code("edit", "SearchButton.jsx"))
        self.assertIn("<circle", code("edit", "SearchButton.jsx"))
        self.assertIn("tools.SearchButton && !fromFile.value", code("components", "TopBar.jsx"))       # none in a published file
        self.assertIn("A published file has no such button.", text)
        pal = code("edit", "palette.js")
        for label in ("Publish…", "Preview the page in a new tab", "Export to Excel", '"Settings"', "PANEL_TITLE", '"Help"', '"Appearance: "'):
            self.assertIn(label, pal)
        self.assertIn('PANEL_TITLE = "ask clark"', code("edit", "askWords.js"))
        for word in ("Publish", "Preview the page in a new tab", "Export to Excel", "Settings", "ask clark", "Help", "Appearance", "a page, a project, a work item or a milestone", "then press [[Enter]]"):
            self.assertIn(word, text)
        self.assertIn("kind: \"Page\"", pal)
        self.assertIn("kind: \"Project\"", pal)
        self.assertIn("openPeek(r.id, \"item\")", pal)
        self.assertIn("\"milestone\"", pal)


class TypedFilter(unittest.TestCase):
    FIND = flat(TASKS["find-work-items"]["s"])
    REF = flat(SECS["work-items"])

    def test_the_fields_are_the_lines_fields(self):
        line = code("logic", "filterLine.js")
        body = line[line.index("export const LINE_FIELDS"):line.index("export const NAMES")]
        keys = re.findall(r"^  (\w+): \{ name:", body, re.M)
        self.assertEqual(keys, ["type", "status", "owner", "priority", "due", "workstream", "usecase", "milestone", "client", "is"])
        self.assertIn("The fields are " + ", ".join(keys[:-1]) + " and is.", self.FIND)

    def test_the_syntax_is_the_parsers(self):
        parse = code("logic", "filterQueryParse.js")
        for hint in ("comma is OR within the field", "space is AND across tokens", "-field:value         excludes", "has:field  no:field", "@me is the signed-in person"):
            self.assertIn(hint, parse)
        self.assertIn("free text            matches the title", parse)
        ev = code("logic", "filterQueryEval.js")
        self.assertIn("`${row.title || \"\"} ${row.id || \"\"}`", ev)        # a plain word: title and ID only
        for s in ("A plain word finds the items with it in the title or the ID.", "A comma means or, a space between two parts means and, and a - in front means not",
                  "no:owner finds the items with no owner, has:owner the items with one, and owner:@me means you"):
            self.assertIn(s, self.FIND)

    def test_the_messages_and_empty_words_are_the_codes(self):
        ui = code("logic", "filterQueryUi.js")
        self.assertIn("`Unknown field '${e.name}'. Did you mean ${first.name}?`", ui)
        self.assertIn("`Add a value after '${e.name}:'.`", ui)
        self.assertIn('EMPTY = { none: "No work items match.", clear: "Clear filter" }', ui)
        self.assertIn('NO_ME = "Set your name in Settings to see your actions."', code("logic", "filterLine.js"))
        for s in ("There is no “x” filter.", "Add a value after 'x:'.", "Set your name in Settings to see your actions.", "**Clear search**", "No open items match"):
            self.assertIn(s, self.FIND)
        self.assertIn("text-decoration: underline wavy var(--status-red)", (PAGE.parent / "shell.css").read_text(encoding="utf-8"))
        self.assertIn('PLACEHOLDER = "Filter by keyword or by field"', code("logic", "filterLine.js"))
        self.assertIn("**Filter by keyword or by field**", self.FIND)

    def test_the_count_and_clear(self):
        fl = code("components", "FilterLine.jsx")
        self.assertIn("`${matches} of ${rows.length}`", fl)
        self.assertIn('aria-label="Clear filter"', fl)
        self.assertIn("The count at the right reads, for example, 12 of 40.", self.FIND)

    def test_the_app_draws_the_line_and_the_file_draws_the_old_bar(self):
        wi = code("components", "WorkItems.jsx")
        self.assertIn("const L = fromFile.value ? null : lineApi.current", wi)
        self.assertIn("<SearchBox />", wi)
        self.assertIn("<FilterBar />", wi)
        self.assertIn('placeholder="Search work items"', wi)
        self.assertIn(">Clear all<", wi)
        wf = code("components", "WorkFilters.jsx")
        for b in (">is any of<", ">is not<", ">Select all<", ">Clear<", "Filter by</span>"):
            self.assertIn(b, wf)
        flt = code("filters.js")
        self.assertIn('FIELDS.filter((f) => f !== "client" && f !== "reviewed")', flt)
        self.assertIn("a **Filter by** row with Workstream, Status, Due, Owner, Priority, Use case and Milestone.", self.FIND)
        self.assertIn("map[r.id] = [r.id, words, who, richWords(r.latest_update), r.client_message, r.use_case]", code("clientView.js"))
        self.assertIn("finds words in the ID, the description, the owner, the latest update, the client wording and the use case", self.FIND)
        self.assertIn("a published file keeps the type and Open / Closed / All", wi)
        self.assertIn("**Clear all** removes the filters and the search but keeps the type and Open, Closed or All.", self.FIND)

    def test_the_old_sentences_are_gone(self):
        every = flat(RAW)
        for gone in ("Every filter can be **is** or **is not**", "A line under the filters shows how many items match", "**Clear all** puts it back", "Select all** and **Clear** are at the top. A dot marks",
                     "In the app it goes back to the open items", "The search box finds words in the ID, title, owner"):
            self.assertNotIn(gone, every)
        self.assertIn("The filter line takes a plain word", self.REF)
        self.assertIn("A published file has a **Search work items** box and a **Filter by** row instead", self.REF)
        ctx = flat([c for c in RAW["context"] if c["page"] == "work"])
        self.assertIn("Narrow the list by typing in the filter line", ctx)


class SettingsChips(unittest.TestCase):
    TEXT = flat(SECS["settings"])

    def test_the_chip_names_and_order_are_the_pages(self):
        views = code("components", "Views.jsx")
        cards = re.search(r"const CARDS = \[(.*?)\];", views, re.S).group(1)
        names = [n for n in re.findall(r'\["\w+", "([^"]*)", "[\w-]+"\]', cards)]
        self.assertEqual(names, ["Profile", "Publishing", "Personal", "Freshness", "Gantt", "Logs and diagnostics", "Projects", "Data", "Backups", "", "", "People", "Asking", ""])
        self.assertIn('Update.chip = L.TITLE', code("edit", "Update.jsx"))
        self.assertIn('TITLE = "Version and updates"', code("logic", "update.js"))
        self.assertIn("Profile, Publishing, Personal, Freshness, Gantt, Logs and diagnostics, Projects, Data, Backups, Version and updates, Brands, People, Asking and Quit, in the order the cards are drawn.", self.TEXT)
        self.assertIn('<nav class="set-bar"', views)
        self.assertIn('aria-current={here === headId ? "location" : undefined}', views)
        self.assertIn('NEEDS_PROJECT = ["ClientFolder", "PublishedReports", "ReviewDays", "GanttSetting"]', views)
        self.assertIn("Publishing, Freshness and Gantt need an open project. Published reports also needs one and has a card but no link.", self.TEXT)
        self.assertIn("A list of links down the left of the cards takes you to a card (in a window narrower than 900 px it is a row of chips under the title)", self.TEXT)
        self.assertIn("The link of the card you are reading is marked.", self.TEXT)

    def test_published_reports_has_no_chip(self):
        views = code("components", "Views.jsx")
        self.assertNotIn('"PublishedReports", "', re.search(r"const CARDS = \[(.*?)\];", views, re.S).group(1))
        self.assertIn("{PublishedReports ? <PublishedReports /> : null}", views)

    def test_ai_is_drawn_straight_after_asking_and_has_no_chip(self):
        ask = code("edit", "AskSettings.jsx")
        self.assertLess(ask.index("</section>"), ask.index("<AiSettings />"))
        ai = code("edit", "AiSettings.jsx")
        self.assertIn('<section class="frame setting" id="ai-settings">', ai)
        self.assertIn("A card of its own, drawn straight after the Asking card and without a link.", self.TEXT)
        self.assertIn("AI (under Asking)", self.TEXT)

    def test_personal_holds_the_appearance_about_you_and_keys(self):
        per = code("edit", "Personal.jsx")
        self.assertIn("<legend>About you</legend>", per)
        for field in ('box("name"', 'box("alias"', 'box("email"'):
            self.assertIn(field, per)
        self.assertNotIn('box("phone"', per)
        self.assertIn("<h2 id=\"profile-h\" tabIndex={-1}>Profile</h2>\n      <AboutYou />", per)      # row 950: About you is the Profile card, not part of Personal
        self.assertNotIn("<AboutYou />\n      <fieldset class=\"styles keys\">", per)
        self.assertIn("<legend>Keys</legend>", per)
        self.assertIn('aria-label="Single-key shortcuts"', per)
        self.assertIn("<legend>Appearance</legend>", per)
        self.assertLess(per.index('["system", "System"'), per.index('["light", "Light"'))
        self.assertIn("Appearance (System, Light or Dark) and Keys (Single-key shortcuts)", self.TEXT)
        self.assertIn("About you (your name, Alias and Email).", self.TEXT)
        self.assertNotIn("Phone number", self.TEXT)

    def test_published_reports_row(self):
        self.assertIn('data-pubopen={r.number}', code("edit", "PublishedReports.jsx"))
        self.assertIn('open: "Open"', code("logic", "pastReports.js"))
        self.assertIn("The numbered copies you have published, each with **Open** to see it as it was.", self.TEXT)


class AskOff(unittest.TestCase):
    def test_the_button_hides_and_the_slash_still_opens(self):
        text = flat(SECS["ask-clark"])
        self.assertIn("if (!askOn.value) return null;", code("edit", "AskButton.jsx"))
        keys = code("edit", "askPanelState.js")
        self.assertIn('e.key === "/"', keys)
        self.assertNotIn("askOn", keys[keys.index("export function installAskKeys"):keys.index("document.addEventListener(\"mousedown\"")])
        words = code("edit", "askWords.js")
        self.assertIn('OFF_LINE = "Asking is off. Turn it on in Settings."', words)
        self.assertIn('OFF_LINK = "Open Settings"', words)
        self.assertIn("{W.OFF_LINE} <a href=\"#settings\"", code("edit", "AskPanel.jsx"))
        self.assertIn("The **ask clark** button shows only while asking is on. With asking off, [[/]] still opens the panel, except while Help is open, and the panel says “Asking is off. Turn it on in Settings.” and has an **Open Settings** link.", text)
        self.assertIn("!helpOpen.value", keys)       # #754: the ask key leaves Help alone, so the sentence says 'except while Help is open'


class SlashInHelp(unittest.TestCase):
    def test_help_says_what_slash_does_in_help_with_its_condition_and_without_the_switch_name(self):
        store = code("help", "helpStore.js")
        self.assertIn('e.key === "/" && helpOpen.value && singleKeys.value', store)       # only while the switch is on
        line = flat(SECS["using-help"])
        self.assertIn("[[?]] opens Help from any page. In Help, [[/]] goes to the search box, unless the letter keys are turned off in Settings › Personal › Keys.", line)
        self.assertNotIn("Single-key", line)       # the switch's own name stays in the V and E key rows only (test_single_keys)
        every = flat(RAW)
        self.assertNotIn("In Help, it goes to the search box instead", every)


class Terminal(unittest.TestCase):
    TEXT = flat(TASKS["start-check-and-restore-in-terminal"]["s"])

    def test_the_zip_unzips_into_one_folder_called_clark(self):
        self.assertIn('TOP = "clark"', (SRC / "release_files.py").read_text(encoding="utf-8"))
        self.assertIn("The download unzips into one folder called clark, whatever its version.", self.TEXT)

    def test_the_commands(self):
        cmd = (ROOT / "clark.command").read_text(encoding="utf-8")
        self.assertIn('export CLARK_TYPED="bash clark.command"', cmd)
        self.assertIn("--check) shift; python3 -m clark.doctor", cmd)
        self.assertIn("restore) python3 -m clark", cmd)
        main = (SRC / "__main__.py").read_text(encoding="utf-8")
        self.assertIn("Close clark first: stop every running copy. With no NAME it only lists the copies.", main)
        self.assertIn("clark-20261028T143005Z-undo.db", main)
        doc = (SRC / "doctor.py").read_text(encoding="utf-8")
        self.assertIn("Everything clark needs is ready.", doc)
        self.assertIn("It changes nothing", doc)
        for s in ("`bash clark.command`", "`bash clark.command --check`", "`bash clark.command restore`", "close clark first", "With no name after restore it only lists them.",
                  "`bash clark.command restore clark-20261028T143005Z-undo.db`", "It changes nothing."):
            self.assertIn(s, self.TEXT)

    def test_no_sentence_starts_with_the_product_name(self):
        for s in TASKS["start-check-and-restore-in-terminal"]["s"]:
            self.assertFalse(re.match(r"\s*clark\b", s, re.I), s)


class ExcelColumns(unittest.TestCase):
    def test_the_table_is_the_import_list(self):
        js = code("logic", "dataCard.js")
        block = js[js.index("export const IMPORT_COLUMNS"):js.index("export const PROJECT")]
        want = [(name, ", ".join(re.findall(r'"([^"]+)"', cols))) for name, cols in re.findall(r'\["([^"]+)", \[(.*?)\]\]', block)]
        table = next(b for b in SECS["excel"]["b"] if b[0] == "tbl")
        self.assertEqual(table[1], ["Sheet", "Columns the import reads"])
        self.assertEqual([(r[0], r[1]) for r in table[2]], want)
        heads = flat(table)
        for real in ("Achieved on", "% complete"):
            self.assertIn(real, heads)
        for wrong in ("Rating", "Progress", "Title", "Open work items"):
            self.assertNotIn(wrong, heads)
        py = (SRC / "excel.py").read_text(encoding="utf-8")
        for label in ('("Achieved on", "actual_date")', '("% complete", "percent_complete")'):
            self.assertIn(label, py)

    def test_the_table_is_what_the_importer_applies(self):
        """Per sheet: ID, then every export column except the ones excel.DERIVED skips and excel_import.LOCKED / LOCKED_IN never apply
        (excel_import.py:135-136 and :661). Those are named in the paragraph under the table."""
        from clark import excel, excel_import as ei
        table = next(b for b in SECS["excel"]["b"] if b[0] == "tbl")
        rows = {r[0]: r[1] for r in table[2]}
        left_out = set()
        for name, tbl, cols, _ in excel.SHEETS:
            applied = [l for l, f in cols if f == "id" or (f not in excel.DERIVED and f not in ei.LOCKED and f not in ei.LOCKED_IN.get(tbl, ()))]
            self.assertEqual(rows[name].split(", "), applied, name)
            left_out |= {l for l, f in cols if l not in applied}
        left_out.discard("ID")
        note = flat(SECS["excel"]["b"][-1])
        for label in sorted(left_out):
            self.assertIn(label, note)
        self.assertIn("an import never changes anything from them", note)


if __name__ == "__main__":
    unittest.main()
