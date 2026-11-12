"""#82 (BRD 5.13, FR-120 to FR-124): Help's source, src/clark/page/src/help/helpContent.json, is complete and in plain words.

Run: python3 dev/run_tests.py test_help_content
Quick tier: reads the JSON and the prototype's files, starts no browser. The logic that works on the source (tab lists, search,
places) is tested in test_help_logic.py. Counts are the prototype's, which has grown past the issue's first numbers (27 tasks
and 30 sections, not 24 and 28, after the section templates and the Needs from you task were added). Text taken out because it describes the prototype
or names creaite is in helpHeld.json, which the page never loads, and none of it may be in the shipped source.
"""
import json
import re
import pathlib
import unittest

from _paths import ROOT

HELP = ROOT / "src" / "clark" / "page" / "src" / "help"
SRC = json.loads((HELP / "helpContent.json").read_text(encoding="utf-8"))
HELD = json.loads((HELP / "helpHeld.json").read_text(encoding="utf-8"))
LOGIC = (HELP / "helpLogic.js").read_text(encoding="utf-8")
PROTO = ROOT / "system" / "prototype"
BASE = {"start": "start-", "howto": "howto-", "reference": "ref-"}
UI_NAMES = {"Version and updates", "clark version and updates"}     # the name of a Settings section (BRD FR-8a), shown as a name, not as the start of a sentence
# 'Archive', 'Archive use case' and 'Show archived' are the owner's rule (we archive, never delete) and are not in the prototype, which still
# says Delete; 'Delete section' is the label the page has today (edit/Gutter.jsx), kept as it is for the ruling.
# 'ask clark', 'Confirm and apply', 'Folders asking may read', 'Turn off asking' (#721) and the two long pills are the page's own words (edit/askWords.js, AskSettings.jsx, SneakPeek.jsx); the prototype words them differently.
# 'Add a row' is no longer listed here: the prototype now draws that button (the Excel layout window, files.js), so it is found there like any other.
# 'Outline colour' (the tile's right-click menu, edit/GlanceEdit.jsx) is read on the page itself; the prototype words it differently. 'Shown to client' left this list with the tag on a work item row (#456: the eye column says it, and Help no longer bolds it)
# 'New agreed date (DD-MM-YYYY)', 'Who agreed it' and 'Keep the date' are the words of the Movement block (edit/movementWords.js); 'Open folder' is the button of Settings > Logs and diagnostics (edit/Diagnostics.jsx). The prototype words these differently, so they are read against the page.
# 'Keep the model I have' and 'Use it anyway' are the buttons of the Settings AI card (edit/AiSettings.jsx, #446); the prototype has no AI card. Claude and ChatGPT are named only as the two providers the card connects.
# 'Show the files' and 'Put back the app and settings only' are the update card's own buttons (logic/update.js LABELS, item 445); the prototype has neither.
# 'Set commitment' and 'No flag' (#692) are read on the page itself (edit/CommitMenu.jsx SET_WORDS, NO_FLAG); the prototype has no commitment flag.
# 'Report menu' and 'Export to PDF' are the published file's own menu words (components/ClientMenu.jsx WORDS, #713); the prototype has no such menu.
# 'Ask clark to update for you' is the words box's heading (edit/SneakPeek.jsx, row 1077, the owner's words of 09-11-2026); the prototype still says Change an item with words.
CHECKED_BY_HAND = set(['Close this panel', 'Make this panel fill the screen', 'Comfortable', 'Add a group', 'How do I…', 'Keep the date', 'Keep the model I have', 'New agreed date (DD-MM-YYYY)', 'Open folder', 'Outline colour', 'Progress tracker', 'Put back the app and settings only', 'Remove group', 'Show the files', 'Clear filter', 'Open Settings', 'Search work items', 'is any of', 'Confirm and apply', 'Folders asking may read', 'Turn off asking', 'What is the next milestone?', 'Which use cases need attention?', 'Use it anyway', 'Start here', 'Who agreed it', 'What to import', 'Set commitment', 'No flag', 'Report menu', 'Export to PDF', '⋯', 'Template settings', 'Use the automatic words', 'Show history', 'Hide history', 'Show the Gantt to me', 'Show the Gantt to the client', 'Tab name', 'Your email', 'Open in your mail app', 'Ask clark to update for you'])  # merged with main: the four main-only words ('Personal › Spacing', 'Personal › Appearance', 'Review X.Y.Z', 'The line above the title') are now found in the prototype, so they are out; 'Open in your mail app' (Feedback card) is kept  # the last four: the Gantt and Profile cards' own labels (edit/GanttSetting.jsx, edit/Personal.jsx)
STEPS = SRC["howto"]["tasks"]
SECTIONS = SRC["reference"]["sections"]
START = SRC["start"]


def texts(o, path=""):
    """Every string a person reads, with where it is: ids, groups, links' targets and icon names are addresses, not words."""
    skip = {"id", "g", "go"}
    if isinstance(o, str):
        yield path, o
    elif isinstance(o, list):
        for i, x in enumerate(o):
            yield from texts(x, f"{path}[{i}]")
    elif isinstance(o, dict):
        for k, v in o.items():
            if k not in skip and k != "about":
                yield from texts(v, f"{path}.{k}")


# The Docker entry (Advanced) is for the Terminal: it names addresses, a command and what Terminal and Docker print, so the rules
# about addresses, file names and plain words are not applied to its own paragraphs (every other rule still is).
DOCKER = {s for t in SRC["howto"]["tasks"] if t["id"] == "run-clark-with-docker" for s in t["s"]}


def words():
    """The strings to read as words. A job's first item is its id and its last its screen; an icon's first is its picture's name."""
    out = list(texts({"howto": SRC["howto"], "start": {k: v for k, v in START.items() if k not in ("jobs", "where")}}))
    out += [(f"job {j[0]}", s) for j in START["jobs"] for s in j[1:3]]
    out += [(f"where {w[0]}", s) for w in START["where"] for s in w[:2]]
    out += list(texts({"groups": SRC["reference"]["groups"], "sections": [{k: v for k, v in s.items() if k != "b"} for s in SECTIONS]}))
    for s in SECTIONS:
        for n, b in enumerate(s["b"]):
            out += list(texts(b[1:], f"ref {s['id']} block {n}"))
    out += [("key", s) for r in SRC["reference"]["keys"] for s in r]
    out += [("icon", s) for r in SRC["reference"]["icons"] for s in r[1:]]
    out += [("mark", s) for r in SRC["reference"]["milestone_states"] + SRC["reference"]["milestone_extra"] for s in r]
    return out


class Shape(unittest.TestCase):
    def test_the_docker_entry_says_the_shared_data_default_and_keeps_the_two_routes_warning_after_start(self):
        """issue 694: Docker keeps its data where clark.command does, outside the clark folder. The warning is a step of its own right
        after Start, and the old 'each keep their own data' wording is gone."""
        steps = [t["s"] for t in SRC["howto"]["tasks"] if t["id"] == "run-clark-with-docker"][0]
        at = [i for i, s in enumerate(steps) if s.startswith("Start. ")][0]
        self.assertTrue(steps[at + 1].startswith("Never use two routes on the same data at once. "), steps[at + 1][:60])
        self.assertTrue(steps[at + 2].startswith("Use another data folder. "), steps[at + 2][:60])
        text = " ".join(steps)
        self.assertIn("This start keeps its data in ~/Library/Application Support/clark, the same place clark.command uses, so you see "
                      "the projects you already have, or an empty set on a first start.", steps[at])
        self.assertIn("Your data is not in the clark folder, so you can swap that folder for a newer download.", steps[at])
        self.assertIn("If you already have a folder called clark, rename or move it before you unzip a newer download, so the two do not clash.", steps[at])
        self.assertIn('CLARK_DATA_DIR="/full/path" docker compose -f docker/compose.yaml up -d', steps[at + 2])
        self.assertIn("stop clark, move that folder out of it, and name it this way.", steps[at + 2])
        self.assertIn("Docker and clark.command use the same data unless you name another folder with CLARK_DATA_DIR. "
                      "If clark.command looks empty, you started Docker with another folder.", text)
        for gone in ("beside the clark files", "each keep their own data", "Use the projects you already have"):
            self.assertNotIn(gone, text)

    def test_three_tabs_from_one_source(self):
        self.assertEqual(SRC["tabs"], [["start", "Start here"], ["howto", "How do I…"], ["reference", "Reference"]])

    def test_the_counts(self):
        """Start here: five loop steps, five first-ten-minutes steps, five jobs (the owner's five, 04-11-2026; the prototype had twelve), seven places (Dashboard, Work items, Milestones, Use cases, ask clark, the profile circle, Settings), four rules."""
        self.assertEqual((len(START["loop"]), len(START["first"]), len(START["jobs"]), len(START["where"]), len(START["rules"])),
                         (5, 5, 5, 7, 4))
        self.assertEqual([j[0] for j in START["jobs"]], ["add-a-work-item", "write-the-weekly-report", "add-a-section-from-a-template", "arrange-the-report", "publish-the-report"],
                         "the owner's order; bringing in an Excel workbook is not one of them")
        self.assertIn(START["undo"], [t["id"] for t in STEPS])
        self.assertEqual((len(STEPS), len(SECTIONS)), (38, 36))   # with the People entries (#454), held, and the Word entry, Run clark with Docker, and the AI card task (#446), and Excel file layout (#951), and the Feedback entry (#1069)
        self.assertEqual((len(SRC["reference"]["keys"]), len(SRC["reference"]["icons"])), (33, 29))   # the peek chip's icon is gone (#1077)

    def test_ids_are_unique_plain_and_listed_in_a_group(self):
        for kind, rows, groups in (("task", STEPS, SRC["howto"]["groups"]), ("section", SECTIONS, SRC["reference"]["groups"])):
            ids = [r["id"] for r in rows]
            self.assertEqual(len(ids), len(set(ids)), kind)
            for r in rows:
                self.assertRegex(r["id"], r"^[a-z0-9]+(-[a-z0-9]+)*$", r["id"])
                self.assertIn(r["g"], groups, r["id"])
            for g in groups:
                self.assertTrue([r for r in rows if r["g"] == g], f"the {kind} group {g} is empty")

    def test_every_entry_has_a_title_and_a_body(self):
        for t in STEPS:
            self.assertTrue(t["t"].strip() and t["w"].strip(), t["id"])
            self.assertTrue(t["s"] and all(s.strip() for s in t["s"]), t["id"])
        for s in SECTIONS:
            self.assertTrue(s["t"].strip(), s["id"])
            self.assertTrue(s["b"], s["id"])
            for kind, *rest in s["b"]:
                self.assertIn(kind, {"p", "ul", "tbl", "keys", "icons", "marks", "types", "ai"}, s["id"])
                if kind in ("p", "ul", "tbl"):
                    self.assertTrue(rest[0] and (rest[1] if kind == "tbl" else True), s["id"])
        for j in START["jobs"]:
            self.assertTrue(all(str(x).strip() for x in j), j)
        for x in START["loop"] + START["first"]:
            self.assertTrue(x["t"].strip() and x["d"].strip())
        for r in START["rules"] + START["where"]:
            self.assertTrue(r[0].strip() and r[1].strip())

    def test_every_job_is_a_task_and_every_task_goes_somewhere_real(self):
        ids = {t["id"] for t in STEPS}
        for j in START["jobs"]:
            self.assertIn(j[0], ids)
        screens = set(re.search(r"export const SCREENS = \[(.*?)\]", LOGIC).group(1).replace('"', "").replace(" ", "").split(","))
        for t in STEPS:
            if t["id"] not in ("run-clark-with-docker", "start-check-and-restore-in-terminal"):      # these entries are run in Terminal: they open no screen
                self.assertIn(t["go"].split("#")[0], screens, t["id"])


class KeysVE(unittest.TestCase):
    def rows(self):
        return {r[0]: r[1] for r in SRC["reference"]["keys"]}

    def test_v_and_e_are_one_row_each_in_plain_words(self):
        rows = self.rows()
        self.assertEqual(len([r for r in SRC["reference"]["keys"] if r[0] in ("[[V]]", "[[E]]")]), 2)
        self.assertNotIn("[[V]] [[E]]", rows)
        self.assertIn("Switches to View", rows["[[V]]"])
        self.assertIn("Switches to Edit", rows["[[E]]"])
        for key in ("[[V]]", "[[E]]"):
            self.assertIn("Dashboard", rows[key])
            self.assertIn("only", rows[key])
            self.assertIn("typing in a box", rows[key])


class Places(unittest.TestCase):
    ids = {"start-" + p for p in ("top", "loop", "first", "jobs", "where", "rules", "foot")} | \
          {"howto-" + t["id"] for t in STEPS} | {"ref-" + s["id"] for s in SECTIONS}

    def all_strings(self):
        return [s for _, s in texts({"s": START, "h": SRC["howto"], "r": SRC["reference"]})]

    def test_every_link_inside_help_finds_its_place(self):
        links = {m for s in self.all_strings() for m in re.findall(r"\]\(#([^)]+)\)", s)}
        links |= {"howto-" + j[0] for j in START["jobs"]} | {"ref-keys"}
        self.assertGreater(len(links), 16)   # measured 17 on this tree (18 before the four entries were released and the jobs list gained none); it was 24 with the prototype's twelve jobs. The floor is the measured count less one.
        self.assertEqual(sorted(links - self.ids), [])

    def test_every_screen_help_sends_you_to_exists(self):
        screens = set(re.search(r"export const SCREENS = \[(.*?)\]", LOGIC).group(1).replace('"', "").replace(" ", "").split(","))
        protos = (PROTO / "views.js").read_text(encoding="utf-8")
        gos = {m for s in self.all_strings() for m in re.findall(r"\]\(go:([^)]+)\)", s)} | {j[3] for j in START["jobs"]} | \
              {w[2] for w in START["where"] if w[2]}
        self.assertGreater(len(gos), 3)
        for g in gos:
            view, _, anchor = g.partition("#")
            self.assertIn(view, screens, g)
            if anchor:
                self.assertIn(f'id="{anchor}"', protos, g)

    def test_every_place_the_prototype_opens_help_at_exists(self):
        """C.help.open('x') anywhere in the prototype or the page: x is a place or a tab."""
        used = set()
        for f in list(PROTO.glob("*.js")) + list((ROOT / "src" / "clark" / "page" / "src").rglob("*.js*")):
            used |= set(re.findall(r"help\.open\('([^']+)'\)", f.read_text(encoding="utf-8")))
        self.assertGreaterEqual(len(used), 4)
        self.assertEqual(sorted(u for u in used if u not in self.ids and u not in BASE), [])


class Words(unittest.TestCase):
    JARGON = re.compile(r"\b(sweeps?|proposals?|stag(?:e|ed|ing)|vault|live server|extract(?:s|ed|ion)?|refus(?:e|ed|al)|valid|invalid|"
                        r"(?<!Progress )tracker|prototype|demo|creaite|Claude(?! (?:or|and) ChatGPT)|Tiptap|schema|database|SQLite|JSON|token|hook|script|payload)\b", re.I)
    # "close the list to apply it" is ordinary English for a filter; nothing here means creaite's apply
    PATH = re.compile(r"(?:\w+/){2,}|\.py\b|\.js\b|\.json\b|\.md\b|~/|\\")
    AMERICAN = re.compile(r"\b(color|colors|colored|organize|organized|center|behavior|favorite|gray|customize|license|canceled)\b", re.I)

    def test_no_internal_jargon_or_paths_or_creaite(self):
        found = [(p, s) for p, s in words() if s not in DOCKER and (self.JARGON.search(s) or self.PATH.search(s))]
        self.assertEqual(found, [])

    def test_no_line_starts_with_the_product_name_and_the_name_is_lower_case(self):
        starts = [(p, s) for p, s in words() if re.match(r"\s*(\*\*)?clark\b", s, re.I) and s not in UI_NAMES]
        self.assertEqual(starts, [])
        self.assertEqual([(p, s) for p, s in words() if re.search(r"\bClark\b", s)], [])

    def test_british_english_and_dates(self):
        self.assertEqual([(p, s) for p, s in words() if self.AMERICAN.search(s)], [])
        self.assertEqual([(p, s) for p, s in words() if re.search(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", s)], [])
        # a date shown to a person is DD-MM-YYYY or written out; YYYY-MM-DD is allowed only inside a file name
        shown = [s for _, s in words() if re.search(r"\b\d{4}-\d{2}-\d{2}\b", s) and ".html" not in s]
        self.assertEqual(shown, [])

    def test_no_real_looking_email_or_address(self):
        self.assertEqual([(p, s) for p, s in words() if s not in DOCKER and re.search(r"[\w.]+@[\w.]+|https?://", s)], [])

    def test_nothing_is_named_that_clark_does_not_have(self):
        """creaite's mail, calendar and meeting features are not clark's, nor are the report layouts that are only in the backlog (FR-4)."""
        absent = re.compile(r"\b(Outlook|transcripts?|VIP|steerco|Steerco|people register|Teams chat|sweep|meeting minutes|Cover-led|Health spine|health spine)\b")
        found = [(p, s) for p, s in words() if absent.search(s) and not s.startswith("**Open in your mail app** opens a new email")]   # Feedback (#1069): says clark cannot choose Outlook for you
        self.assertEqual(found, [])

    def test_every_button_and_label_in_bold_is_in_the_prototype(self):
        """A **bold** name is a button or label on a screen. It must be written in the prototype's other files (or be a word Help
        itself defines), so Help never names something the product does not have."""
        corpus = "\n".join(p.read_text(encoding="utf-8") for p in list(PROTO.glob("*.js")) + [PROTO / "index.html"] if p.name != "help.js")
        corpus = re.sub(r"[‘’]", "'", corpus).lower()
        missing = set()
        for p, s in words():
            for b in re.findall(r"\*\*(.+?)\*\*", s):
                name = re.sub(r"[‘’]", "'", b).strip(" .,:;…").lower()
                if name and name not in corpus:
                    missing.add(b)
        self.maxDiff = None
        # a ratchet: these were read by hand (a path through Settings, a button made of words and a number, a part of a screen
        # described in words); a NEW bold name that the prototype lacks fails here, and the review or the builder checks it
        self.assertEqual(sorted(missing - CHECKED_BY_HAND), [], "bold names that the prototype does not have: add them there, or reword Help")
        self.assertEqual(sorted(CHECKED_BY_HAND - missing), [], "no longer needed in the hand-checked list: take it out")

    def test_help_names_new_project_only_if_the_page_builds_it(self):
        """#527: Help may not send a reader to a "New project" menu item that the page does not have."""
        src = HELP.parent
        built = any("New project" in f.read_text(encoding="utf-8", errors="ignore")
                    for f in src.rglob("*") if f.is_file() and f.suffix in (".js", ".jsx", ".ts", ".tsx") and HELP not in f.parents)
        help_text = "\n".join(f.read_text(encoding="utf-8") for f in HELP.glob("*.json"))
        if not built:
            self.assertNotIn("New project", help_text, "Help names New project but no code under src/clark/page/src builds it")


class Held(unittest.TestCase):
    def test_taken_out_text_is_not_in_the_shipped_source(self):
        shipped = json.dumps(SRC, ensure_ascii=False)
        self.assertGreaterEqual(len(HELD["held"]), 15)
        for h in HELD["held"]:
            self.assertTrue(h["where"] and h["text"] and h["why"])
            if len(h["text"]) > 40:
                self.assertNotIn(h["text"], shipped, h["where"])

    def test_the_page_never_loads_the_held_file(self):
        for f in (ROOT / "src" / "clark" / "page" / "src").rglob("*.js*"):
            self.assertNotIn("helpHeld", f.read_text(encoding="utf-8"), f.name)



class WordingRound(unittest.TestCase):
    """The plain-words review of the Help: each fix is pinned here so the old wording cannot come back."""
    ALL = " \n".join(s for _, s in words())

    def test_the_template_list_has_only_what_the_box_offers_and_no_old_names(self):   # HIGH (the table is shown once the page has the box)
        self.assertNotIn('"Headline band"', json.dumps(SRC["reference"]["sections"]), "a template the box does not offer is not in the table")
        self.assertNotIn("Headline message", json.dumps(SRC))
        self.assertNotIn("Notice bar", json.dumps(SRC))

    def test_the_panel_header_does_not_say_question_mark_comes_back_from_help(self):       # HIGH
        jsx = (HELP / "Help.jsx").read_text(encoding="utf-8")
        self.assertNotIn("to come back", jsx)
        self.assertRegex(jsx, r"to open Help; Esc takes you where you were")

    def test_the_help_does_not_offer_import_from_word_in_the_profile_menu(self):            # row 1063 (replaces the #432 wording test: the menu entry is gone)
        self.assertNotIn("Import from Word", self.ALL)
        self.assertNotIn("bring items in from a Word file", self.ALL)
        self.assertIn("**Export to Word**", self.ALL, "Export to Word stays in Help")
        raw = (HELP / "helpContent.json").read_text(encoding="utf-8")      # the whole source, including the context lines that ALL does not read
        self.assertNotIn("Import from Word", raw, "no help line, in any section, names the removed menu entry")

    def test_examples_are_real_dates(self):                                                  # MEDIUM
        self.assertIn("due Friday · move to tomorrow · by Friday", self.ALL)      # a date-free example: no made-up date reaches the built page
        self.assertNotRegex(self.ALL, r"\b\d\d-\d\d-20\d\d\b")
        self.assertNotRegex(self.ALL, r"such as DD-MM-YYYY|forecast DD-MM-YYYY")

    def test_no_report_layout_choice_is_mentioned(self):                                     # MEDIUM
        self.assertNotRegex(self.ALL, r"(?i)report layout|layout and section style|Cover-led|Editing the layout|one layout")
        self.assertIn("the report in the Spacing you chose", self.ALL)

    def test_no_leftover_from_the_prototype(self):                                           # MEDIUM
        self.assertNotIn("The real clark", self.ALL)
        self.assertIn("Each day has its own file, 5 MB at most", self.ALL)      # the log's own rule (log.py MAX_BYTES, KEEP_DAYS)

    def test_published_line_is_plainer(self):                                                # LOW
        self.assertIn("“Published” on its date, to the client (or locally)", self.ALL)

    def test_no_results_does_not_offer_ask_clark_yet(self):                                  # MEDIUM
        self.assertNotRegex(re.search(r"export const noResults.*?\}\);", LOGIC, re.S).group(0), r'hint: "[^"]*ask clark')


class UseCaseStatuses(unittest.TestCase):
    """#412: Help names the four use case statuses the store allows, in its order, in both places it lists them."""

    def test_help_names_the_stores_four_statuses(self):
        from clark import store
        allowed = list(store.ALLOWED[("use_cases", "status")])
        self.assertEqual(allowed, ["On track", "Flag", "High risk", "Done"])
        lines = [t for _, t in texts(SRC) if "click the status word to choose" in t or t.startswith("Use case statuses:")]
        self.assertEqual(len(lines), 2, lines)
        for line in lines:
            with self.subTest(line=line):
                self.assertEqual(re.findall(r"\*\*([^*]+)\*\*", line.split("choose", 1)[-1]), allowed)

    def test_the_colours_help_names_are_the_pages(self):
        (line,) = [t for _, t in texts(SRC) if t.startswith("Use case statuses:")]
        self.assertEqual(re.findall(r"\*\*[^*]+\*\* \(([a-z]+)\)", line), ["green", "amber", "red", "grey"])


class PublishFileName(unittest.TestCase):
    def test_example_file_name_is_what_publish_really_names_the_file(self):
        from clark import publish
        task = next(t for t in STEPS if t["id"] == "publish-the-report")
        example = re.search(r"for example “([^”]+)”", task["n"]).group(1)
        code, week = re.fullmatch(r"([A-Z0-9]+)-report-(\d{4}-\d{2}-\d{2})\.html", example).groups()
        self.assertEqual(publish.file_name(code, week, "2026-11-02"), example)


class LowWordsRound(unittest.TestCase):
    """The five low-priority fixes from the review."""
    ALL = " \n".join(s for _, s in words())

    def test_nothing_here_yet_is_plainer(self):
        jsx = (HELP / "Help.jsx").read_text(encoding="utf-8")
        self.assertIn("Nothing here yet. This appears when the part of clark it describes is ready.", jsx)
        self.assertNotIn("This part of Help appears", jsx)

    def test_usual_lists_not_default_views(self):
        self.assertNotIn("default views", self.ALL)
        self.assertEqual(self.ALL.count("the usual lists, the counts and the published page"), 2)

    def test_editing_line_says_what_it_does(self):
        self.assertIn("while you edit, that each change saves on its own", self.ALL)
        self.assertNotIn("“Editing", self.ALL)       # the page has no such label to quote

    def test_the_report_has_no_look_to_choose(self):
        self.assertNotIn("one look", self.ALL)
        self.assertIn("The report is the cover, then the sections, with the contents at the right edge", self.ALL)
        self.assertNotIn("sections in cards", self.ALL)       # Compact is not cards

    def test_no_line_starts_with_ask_clark(self):
        self.assertNotIn("The check in ask clark warns you when", self.ALL)       # ask clark has no such check on the page: the line was taken out of the health steps
        self.assertFalse([s for _, s in words() if re.match(r"(?i)ask clark[’']s\b", s.strip())])

    def test_the_section_style_lines_are_the_ones_settings_shows(self):
        """Help and Settings › Personal give the same two lines for Compact and Comfortable (item 1025). The prototype predates the Spacing
        setting, so these lines are checked against Settings only."""
        table = next(b for sec in SECTIONS if sec["id"] == "layouts" for b in sec["b"] if b[0] == "tbl")
        card = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "Personal.jsx").read_text(encoding="utf-8")
        self.assertEqual([n for n, _ in table[2]], ["Compact", "Comfortable"])
        for name, line in table[2]:
            self.assertIn(line, card, f"{name}: Help's line is the one Settings shows")

    def test_use_case_help_says_what_the_page_says(self):
        """The page's button reads "See all N work items for <ref>" (every linked item, as the prototype's views.js) and a use case has four statuses, Done included (UseCases.jsx; #412)."""
        page = (ROOT / "src" / "clark" / "page" / "src" / "components" / "UseCases.jsx").read_text(encoding="utf-8")
        self.assertIn('`See all ${n} work ${n === 1 ? "item" : "items"} for ${u.ref}`', page)
        self.assertEqual(self.ALL.count("it reads “See all N work items” and the use case's reference") + self.ALL.count("which reads “See all N work items” and the use case's reference"), 2)
        self.assertNotIn("See all work items", self.ALL)
        self.assertIn('export const STATUSES = [["On track", "g"], ["Flag", "a"], ["High risk", "r"], ["Done", "n"]];', page)
        self.assertIn("Use case statuses: **On track** (green), **Flag** (amber), **High risk** (red) and **Done** (grey).", self.ALL)


    def test_the_prototype_help_gives_the_section_style_lines_its_own_settings_gives(self):
        """#294: the prototype's help.js and its Settings card (views.js) say the same thing for each of the four section styles."""
        help_js = (PROTO / "help.js").read_text(encoding="utf-8")
        proto = (PROTO / "views.js").read_text(encoding="utf-8")
        card = re.search(r"\[\['slim'.*?\]\]\.map", proto, re.S).group(0)
        lines = re.findall(r"\['\w+', '([^']+)', '([^']+)'\]", card)
        self.assertEqual([n for n, _ in lines], ["Slim gaps", "Roomy gaps", "Grey headers", "One card"])
        for name, line in lines:
            self.assertIn(f"'{line}'", help_js, f"{name}: the prototype's Help line is its Settings line")


    def test_work_items_names_the_chips_and_clear_all_the_page_draws(self):
        # the app draws only the filter line (WorkItems.jsx, the L branch); the chips and Clear all are the published file's (PublishedList)
        self.assertIn("**Clear filter** (the **×**) empties the line", self.ALL)
        self.assertIn("A published file has a **Search work items** box and a **Filter by** row instead", self.ALL)
        self.assertIn("**Clear all** removes the filters and the search but keeps the type and Open, Closed or All", self.ALL)

    def test_milestone_at_risk_uses_the_pages_own_legend_words(self):
        """The page has no control that sets a state; its legend says 'Marked at risk by the project team.'"""
        self.assertIn("Marked at risk by the project team.", self.ALL)
        self.assertNotIn("Marked at risk by hand", self.ALL)

    def test_ids_line_says_everything_numbered_code_001_shares_the_numbering(self):
        """Assumptions and dependencies are stored with risks and issues (one CODE-001 series)."""
        self.assertIn("Actions, decisions, and everything numbered CODE-001 share one numbering", self.ALL)
        self.assertNotIn("Actions, risks, issues and decisions share one numbering", self.ALL)


class HelpMatchesThePage(unittest.TestCase):
    """Three places where Help said less, or something other, than the page does (Tech Debt #401, #402, #403)."""
    ALL = " ".join(s for _, s in words())
    SRC = ROOT / "src" / "clark" / "page" / "src"

    def test_the_work_items_filters_name_freshness_as_the_page_does(self):
        names = (self.SRC / "filters.js").read_text(encoding="utf-8")
        self.assertIn('reviewed: "Freshness"', names)
        find = next(t for t in STEPS if t["id"] == "find-work-items")
        self.assertIn("a **Filter by** row with Workstream, Status, Due, Owner, Priority, Use case and Milestone", " ".join(find["s"]))     # the published file's row: no Client, no Freshness (filters.js fieldList)
        table = next(b for sec in SECTIONS if sec["id"] == "work-items" for b in sec["b"] if b[0] == "tbl" and b[1] == ["Filter", "Values"])
        self.assertEqual(table[2][-1][0], "Freshness")
        self.assertIn("Not reviewed in 14 days", table[2][-1][1])
        self.assertIn("No owner or no date", table[2][-1][1])
        self.assertIn("REVIEW_DAYS = 14", names)

    def test_a_use_case_names_the_ways_back_the_page_has(self):
        detail = (self.SRC / "components" / "UseCaseDetail.jsx").read_text(encoding="utf-8")
        self.assertIn("data-uc-back", detail)
        self.assertIn('"Escape"', detail)
        find = next(t for t in STEPS if t["id"] == "find-a-use-case")
        line = find["s"][-1]
        self.assertIn("**Use cases** link at the top, [[Esc]] or the Back button of your browser", line)
        self.assertNotIn("Back returns", line)
        self.assertNotIn("**Back**", line)       # the page has no button called Back

    def test_every_line_that_lists_milestone_states_lists_fr50s(self):
        """#453: FR-50's states are Achieved, On track, At risk, Slipped, Overdue and Forecast; no Help line may leave one out."""
        brd = (ROOT / "docs" / "BRD.md").read_text(encoding="utf-8")
        self.assertIn("(Achieved, On track, At risk, Slipped, Overdue) plus Forecast", brd)
        fr50 = {"Achieved", "On track", "At risk", "Slipped", "Overdue", "Forecast"}
        self.assertEqual({r[0] for r in SRC["reference"]["milestone_states"]}, fr50, "the legend")
        states = next(sec for sec in SECTIONS if sec["id"] == "milestone-states")
        follow = next(b[1] for b in states["b"] if b[0] == "p" and b[1].startswith("A state follows the dates"))
        edit = next(s for _, s in words() if s.startswith("**State**: "))
        for name, line in (("Milestone states and marks", follow), ("the State chip", edit)):
            for st in fr50:
                self.assertIn(st, line, f"{name} names {st}")

    def test_help_names_the_tile_menu_as_the_page_does(self):
        """#453: the tile's right-click menu is headed 'Outline colour' (edit/GlanceEdit.jsx); Help calls it that everywhere."""
        glance = (self.SRC / "edit" / "GlanceEdit.jsx").read_text(encoding="utf-8")
        self.assertIn('<div class="lab" role="presentation">Outline colour</div>', glance)
        self.assertNotIn("**Tile colour**", self.ALL)
        self.assertGreaterEqual(self.ALL.count("right-click for **Outline colour**") + self.ALL.count("Right-click a tile in Edit for **Outline colour**"), 2)

    def test_delete_section_is_said_for_both_kinds_that_have_it(self):      # the name is kept (test_v070 lists it); row 906: now every kind
        """Row 906: the menu offers Delete section for every section type (no type list gates it), and Help says so."""
        gutter = (self.SRC / "edit" / "Gutter.jsx").read_text(encoding="utf-8")
        self.assertNotIn("DELETABLE", gutter)
        self.assertNotIn("canDelete", gutter)
        self.assertIn('text: "Delete section"', gutter)
        arrange = " ".join(next(t for t in STEPS if t["id"] == "arrange-the-report")["s"])
        self.assertRegex(arrange, r"and\s+\*\*Delete section\*\*")
        self.assertNotIn("for a text section or the Needs from you section", arrange)


class CalendarKeysHelp(unittest.TestCase):
    """#481: the Milestones entry names the calendar's keys, and each one is a key the calendar handles (so Help says only what the page does)."""

    def test_the_calendar_line_names_the_keys_the_page_handles(self):
        ROOT = pathlib.Path(__file__).resolve().parent.parent
        code = (ROOT / "src" / "clark" / "page" / "src" / "components" / "MsCalendar.jsx").read_text(encoding="utf-8")
        task = next(t for t in STEPS if t["t"] == "Read the timeline and calendar")
        line = next(x for x in task["s"] if x.startswith("With the keyboard, [[Tab]] reaches the calendar"))
        for key, handled in (("[[Left]]", "ArrowLeft"), ("[[Right]]", "ArrowRight"), ("[[Up]]", "ArrowUp"), ("[[Down]]", "ArrowDown"),
                             ("[[Enter]]", "Enter"), ("[[Esc]]", "Escape"), ("[[Shift+Tab]]", "shiftKey")):
            self.assertIn(key, line)
            self.assertIn(handled, code, f"Help names {key} but the calendar does not handle {handled}")


class PublicationNumberWords(unittest.TestCase):
    def test_help_says_a_publication_number_is_never_reused_and_undo_does_not_take_it_back(self):
        """item 515: the store never reuses a number and Undo never meets a publication; the publish task in Help says both."""
        text = json.dumps(SRC, ensure_ascii=False)
        self.assertIn("A number is never used again, and **Undo** does not take it back.", text)


class NeededFromTheClientWords(unittest.TestCase):
    def test_help_says_the_flag_lists_the_item_only_when_the_report_has_a_needs_from_you_section(self):
        """Row 1066: publish adds no 'Needs from you' section the editor lacks, so Help must not promise the item is listed without one."""
        text = json.dumps(SRC, ensure_ascii=False)
        self.assertIn("**Needed from the client**: switch it on in Edit and, when the report has a “Needs from you” section, the item is listed there.", text)
        self.assertNotIn("switch it on in Edit and the item is listed under “Needs from you”", text)
        peek = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "PeekLatest.jsx").read_text(encoding="utf-8")
        self.assertIn("Lists it under “Needs from you” when the report has that section", peek, "the peek's own sub-line makes the same condition")


class ProfileCircleWords(unittest.TestCase):
    def test_help_says_the_profile_circle_is_a_person_icon_that_opens_the_menu_not_initials(self):
        """1.0.6: the editor's profile circle is a person icon that opens the menu; only the published report's own button shows initials."""
        text = json.dumps(SRC, ensure_ascii=False)
        for claim in ("your initials go in the circle", "initials fill the circle", "your initials (a person icon"):
            self.assertNotIn(claim, text.lower(), f"Help must not say the editor's profile circle shows initials: {claim}")
        self.assertIn("a person icon at the top right that opens the menu", json.dumps(SRC["reference"], ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
