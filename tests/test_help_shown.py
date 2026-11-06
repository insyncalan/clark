"""#82 (the lead): Help shows only what is on the page, says Archive for records, and spells "ask clark" in lower case.

Run: python3 dev/run_tests.py test_help_shown
Quick tier: reads files, starts no browser.

THE HELD LIST. helpContent.json is the whole Help (the prototype's, in plain words). src/clark/page/src/help/helpLater.json lists
the entries held back because the part of clark they describe is not on the page yet: they are hidden from the three tabs, the
search, the contents lists and "open at a place". HOW TO RELEASE ONE when its item merges: remove its line in helpLater.json,
then run this file. The tests below read the page's own source (every file under src/clark/page/src except Help's own words)
and fail with the names that the page does not have yet: a bold button name, a screen, or a feature word (peek, board, ask
clark, Publish ...). Fix the wording or hold the entry again. If the item adds the feature word for the first time, add its
proof to FEATURES below.
"""
import json
import re
import unittest

from _help_shown import HELP, LATER, RAW, shown_content
from _paths import ROOT

PAGE_SRC = ROOT / "src" / "clark" / "page" / "src"
SKIP = {"helpContent.json", "helpLater.json", "helpHeld.json"}
SHOWN = shown_content()
# The one place a record is really deleted today: a text section's menu (edit/Gutter.jsx). The owner has not ruled on it, so Help
# describes the button exactly as the page labels it. FOR THE RULING (the owner / the review): archive it too, or keep Delete.
SECTION_DELETE = "Delete section"
# Signed by the owner on 04-11-2026, build notes: the Start here job and its entry are named this on the signed mockups. Exact strings only.
SIGNED_DELETE = {"Move, hide and delete sections"}
# A feature word in shown text needs proof that the page has it: a pattern that must match the page's own code (outside Help).
FEATURES = [
    ("the peek", r"\bpeek\b", r"<Peek\b"),
    ("Sneak peek", r"Sneak peek", r"Sneak peek|Change an item with words"),      # the page names it by its button (edit/SneakPeek.jsx); "Sneak peek" itself is only in comments
    ("the board", r"\bboard\b", r'"Board"|>Board<'),
    ("ask clark", r"ask clark", r"ask clark"),
    ("Import and Export", r"\b(Import|Export|Excel)\b", r"\b(Import|Export)\b|Excel"),
    ("Publish", r"\b(Publish|Preview|Word document)\b", r'"Publish|>Publish|"Preview|>Preview'),
    ("the profile circle", r"profile circle", r"profile"),
    ("the AI menu", r"\bAI\b", r"\bAI\b"),
    ("use cases", r"\buse cases?\b", r"[Uu]se case"),
    ("filters and grouping", r"\b(Filter by|Group by)\b", r"Filter by|Group by"),
]


def strip_comments(code):
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    return re.sub(r"(?m)(^|\s)//.*$", r"\1", code)


def page_code(include_help=False):
    out = []
    for f in sorted(PAGE_SRC.rglob("*")):
        if not f.is_file() or f.suffix not in (".js", ".jsx") or f.name in SKIP:
            continue
        if f.parent == HELP and not include_help:
            continue
        out.append(strip_comments(f.read_text(encoding="utf-8")))
    return "\n".join(out)


def strings(o):
    """Every word a person reads in a piece of the source (ids, groups, addresses and the lists' bookkeeping are not words)."""
    if isinstance(o, str):
        yield o
    elif isinstance(o, list):
        for x in o:
            yield from strings(x)
    elif isinstance(o, dict):
        for k, v in o.items():
            if k not in ("id", "g", "go", "parts", "ic", "tabs", "groups"):
                yield from strings(v)


def shown_texts():
    s = SHOWN
    out = list(strings(s["start"]) if s["start"]["parts"] else [])
    out += list(strings(s["howto"]["tasks"])) + list(strings(s["reference"]["sections"]))
    out += [x for g in s["guides"] for x in strings({k: v for k, v in g.items() if k != "next"})]       # the guides' words (next is a list of places)
    return out


class Held(unittest.TestCase):
    def test_every_held_id_is_a_real_entry_and_nothing_else_is(self):
        self.assertEqual(sorted(set(LATER["howto"]) - {t["id"] for t in RAW["howto"]["tasks"]}), [])
        self.assertEqual(sorted(set(LATER["reference"]) - {t["id"] for t in RAW["reference"]["sections"]}), [])
        self.assertEqual(sorted(set(LATER["start"]) - {"top", "loop", "first", "jobs", "where", "rules", "foot"}), [])
        for k in LATER["keys"]:
            self.assertEqual(RAW["reference"]["keys"][k["at"]][0], k["keys"], "a held key row moved: fix its position")
        for part in ("start", "howto", "reference"):
            for why in LATER[part].values():
                self.assertTrue(why.strip())

    def test_the_ai_card_help_is_shown_and_quotes_the_card_verbatim(self):
        """#446: the Connect Claude or ChatGPT task is shown (the card has merged), and quotes the card's own words."""
        task = next(t for t in RAW["howto"]["tasks"] if t["id"] == "connect-claude-or-chatgpt")
        self.assertNotIn("connect-claude-or-chatgpt", LATER["howto"])
        self.assertIn("connect-claude-or-chatgpt", [x["id"] for x in SHOWN["howto"]["tasks"]])
        src = (ROOT / "src" / "clark" / "ai_connect.py").read_text(encoding="utf-8")
        intro = "Connect Claude or ChatGPT for ask clark: the passages it sends leave this computer, go to the one you choose and count against that plan. No password or key is kept."
        self.assertEqual(task["s"][2], intro)
        self.assertIn("No password or key is kept.", src)
        self.assertIn("Connect Claude or ChatGPT for ask clark: the passages it sends leave this computer, go to the one you choose and count against that plan. ", src)
        self.assertEqual(task["s"][1][:len("Press **Connect** under the one you use if it says **Not connected**.")], "Press **Connect** under the one you use if it says **Not connected**.")
        self.assertEqual(task["s"][4], "To stop, press **Disconnect**. The card then says: Disconnected. You're still signed in to Claude or ChatGPT on this computer, but clark won't use it.")
        self.assertIn("Disconnected. You're still signed in to {name} on this computer, but clark won't use it.", src)
        self.assertIn("settings", LATER["reference"])
        self.assertIn("No password or key is kept: the sign-in already on this computer is used.", json.dumps(RAW["reference"]["sections"]))

    def test_the_held_list_is_indented_evenly(self):
        """Every held id sits two spaces in, like its neighbours (a stray space once crept onto one line)."""
        text = (HELP / "helpLater.json").read_text(encoding="utf-8")
        ids = set(LATER["howto"]) | set(LATER["reference"])
        for n, line in enumerate(text.splitlines(), 1):
            m = re.match(r'^( *)"([^"]+)": "', line)
            if m and m.group(2) in ids:
                self.assertEqual(len(m.group(1)), 2, f"helpLater.json line {n}: {m.group(2)} is not indented by two spaces")

    def test_the_shown_help_is_what_is_left(self):
        s = SHOWN
        self.assertEqual([x["id"] for x in s["howto"]["tasks"]], ["write-the-weekly-report", "set-the-health", "check-the-report", "publish-the-report", "word-in-and-out", "find-a-past-publication", "save-as-a-pdf", "add-a-work-item", "use-the-board", "change-an-item-in-words", "arrange-the-report", "add-a-section-from-a-template", "ask-for-what-you-need", "find-a-use-case", "handle-a-slipped-milestone", "connect-claude-or-chatgpt", "undo-a-mistake", "start-check-and-restore-in-terminal", "run-clark-with-docker"])
        self.assertEqual([x["id"] for x in s["reference"]["sections"]], ["profile-circle", "sections", "section-templates", "needs-from-you", "freshness", "archive-restore", "at-a-glance", "layouts", "work-items", "milestones-page", "ask-clark", "status-words", "sneak-peek",
                          "milestone-states", "published-reports", "diagnostics", "dates-and-ids", "using-help", "keys"])
        self.assertEqual(s["start"]["parts"], ["top", "loop", "jobs", "where", "rules"])      # the hero and the loop (row 903) above the jobs; first and foot wait for their parts of clark
        self.assertEqual(len(s["reference"]["keys"]), 37 - len(LATER["keys"]))
        self.assertEqual(s["howto"]["groups"], ["Every week", "Work items", "The report", "Milestones", "Settings and safety", "Advanced"])
        self.assertEqual(s["reference"]["groups"], ["Screens", "Working with items", "Milestones", "Publishing", "Settings and data", "Keys and icons"])
        self.assertEqual(len(LATER["howto"]) + len(s["howto"]["tasks"]), len(RAW["howto"]["tasks"]))
        self.assertEqual(len(LATER["reference"]) + len(s["reference"]["sections"]), len(RAW["reference"]["sections"]))

    def test_every_link_inside_the_shown_help_goes_to_a_shown_place(self):
        """A link in a shown entry never points at an entry that is still held (it would go nowhere)."""
        places = {"ref-" + x["id"] for x in SHOWN["reference"]["sections"]} | {"howto-" + x["id"] for x in SHOWN["howto"]["tasks"]}
        places |= {"start-" + p for p in SHOWN["start"]["parts"]}
        links = set(re.findall(r"\]\(#([a-z0-9-]+)\)", json.dumps(SHOWN)))
        self.assertEqual(sorted(links - places), [])

    def test_the_source_itself_is_whole(self):
        self.assertEqual((len(RAW["howto"]["tasks"]), len(RAW["reference"]["sections"]), len(RAW["reference"]["keys"])), (37, 35, 37))   # 37 and 35 with the People entries (#454), the Word entry written and Run clark with Docker and the AI card task (#446); the People entries held


class AgainstThePage(unittest.TestCase):
    """HIGH 1: what Help shows must exist on the page as it is today."""
    CODE = page_code()
    HELPCODE = page_code(include_help=True)

    def test_every_bold_name_shown_is_on_the_page(self):
        norm = lambda t: re.sub(r"[‘’]", "'", t)
        code = norm(self.HELPCODE)
        missing = sorted({b for t in shown_texts() for b in re.findall(r"\*\*(.+?)\*\*", t) if norm(b).strip(" .,:;…") not in code})
        self.assertEqual(missing, [], "Help names buttons the page does not have: hold the entry in helpLater.json, or reword it")

    def test_the_held_use_case_entry_names_only_what_the_page_has(self):
        """#421: the held keep-the-use-cases entry is checked now, while it is held, so releasing it cannot show a button the page lacks."""
        norm = lambda t: re.sub(r"[‘’]", "'", t)
        code = norm(self.HELPCODE)
        entry = next(x for x in RAW["howto"]["tasks"] if x["id"] == "keep-the-use-cases")
        self.assertIn("keep-the-use-cases", LATER["howto"])
        names = sorted({b for t in strings(entry["s"]) for b in re.findall(r"\*\*(.+?)\*\*", t) if norm(b).strip(" .,:;…") not in code})
        self.assertEqual(names, [])

    def test_every_screen_shown_is_a_tab_of_the_page(self):
        screens = set(re.findall(r'(\w+): "[A-Z]\w+"', re.search(r"export const TITLES = \{(.*?)\}", (PAGE_SRC / "stores" / "report.js").read_text(encoding="utf-8")).group(1)))
        text = " ".join(shown_texts())
        gos = {m.split("#")[0].split("+")[0] for m in re.findall(r"\]\(go:([^)]+)\)", text)}
        self.assertEqual(sorted(gos - screens), [])

    def test_no_feature_word_is_shown_before_the_page_has_the_feature(self):
        text = "\n".join(shown_texts())
        for name, shown, proof in FEATURES:
            if re.search(shown, text):
                self.assertRegex(self.CODE, proof, f"Help talks about {name}, which the page does not have yet")

    def test_the_check_has_teeth_on_the_whole_source(self):
        """On the whole source (nothing held) the same checks fail: ask clark is not on the page (the board is, from #68). Publish left this list when its button and box reached the page (#43), Import and Export when Export did (#147), and the peek when Sneak peek did (#42); a feature that has arrived can no longer be absent, and the entries still listed prove the check bites."""
        everything = " ".join(list(strings(RAW["howto"]["tasks"])) + list(strings(RAW["start"])))
        absent = [n for n, shown, proof in FEATURES if re.search(shown, everything) and not re.search(proof, self.CODE)]
        self.assertEqual(absent, [])            # every feature word has arrived: "ask clark" (#47a), the peek (#42), Publish (#43) and Sneak peek (#721); the bold-name floor below is what still bites
        names = {b for b in re.findall(r"\*\*(.+?)\*\*", everything) if b not in self.HELPCODE}
        # the count falls as features reach the page: 190 bold names, 99 still absent at #147's merge with main, 83 with the section
        # gutter (#101), whose words Help names (Add a section, the grip ...), 76 with the AI menu and card (Accept, Discard, Show changes, Improve, Format notes ...), 73 with the peek's Activity tab (#42: Help now names Activity and no longer All, Updates and Source); lower this only when a feature lands, never to hide a missing one
        # 72 with Appearance (Light, Dark, System and Dark mode name something on the page now)
        # 68 with the section templates (#96) as well (their words in the Add a section box and in Help name things the page does now: measured on the merged tree)
        # 66 with all eighteen templates built (#96 G1 to G7, measured once on the integrated tree): three more of Help’s bold words are on the page (the RAID cards’ Client wording and Latest update, the pictures’ Description): 69 on the base, 66 now
        # 66 with the section templates (#96) and the peek's Activity tab and Appearance name features as well (measured on the merged tree)
        # 66 again on the merge with the command palette (#198), which adds no bold Help name (measured on the merged tree)
        # 66 again on the merge with ask clark's panel (#47a) and the palette's command for it (measured on the merged tree)
        # 63 on main with the ask panel's suggestion pills (Check this report, Summarise this week, Which risks are red?); the section templates (#96) add no further bold Help name beyond ones main already counts. Measured at this merge: 60 (the merged tree counts three fewer than main)
        # 60 measured after merging main (floor 63 there): the section templates (#96) put three bold Help names on the page, so they are no longer absent: Client wording and Latest update (the RAID cards) and Description (the pictures' caption box)
        # 59 measured on this branch's merge with main: the bar above the page names one bold Help entry that was not on the page before (measured on the merged tree)
        # 59 with Show archived on Milestones (C-M4): its button, now on the page, is one more Help bold name no longer absent (measured: 59, was 60)
        # 58 on the merge with Show archived on Milestones (59 on main): the Supporting documents section (#74) is one more of Help's bold names on the page (measured on the merged tree)
        # 58 measured on the merged tree (main is 59), names printed: one name left the absent list, Week ending, which this branch's report bar (A-D2) puts on the page
        # 55 measured on the merged tree (main is 57): this change moved two Help names onto the page, 'Last update' and 'Move to Friday'
        # 57 measured on the merge of main into the supporting documents branch (#74)
        # 49 measured on the merge of #421, #443 and #124 onto Train 03 (the PDF entry adds no bold name absent from the page)
        # 49 measured on the merge of #421 onto Train 03 (held use-case entry no longer bolds '+ Add use case', '+ Link an existing work item', 'Archive use case', 'Show archived', 'Draft from the project'; 50 fails)
        # 48 measured on the merged tree with the parity batch (#214) and main: one more name left the absent list than on Train 03 (49 fails)
        # 46 measured on the merged tree (main is 48): Latest update and Move to Friday are on the page with this change (names no longer absent)
        # 47 measured on the merge of main into the #527 branch (main is 48): Help no longer names New project, so that bold name left the count
        # 46 measured on the take-over of PR 209 (#271) merged with main (47 there): the held use-case entry now bolds only 'See all' and quotes the button's full name, and 'See all' is on the page, so one more name left the absent list (47 fails)
        # 45 measured on the merge of main into the #436 milestones finish (main is 46): the bold Help name "Linked work items" is on the page now, as a row of the archived milestone's read-only peek
        # 44 with the first-run welcome (#174): its Not now button and its words put two more of Help's bold names on the page (46 fails)
        # 43 measured on the merge of main into the #436 milestones finish (main is 44): both of the above together
        # 44 measured on the merge of main into this branch (main is 46): Latest update and Move to Friday together with main's Help changes left two more names off the absent list (45 fails)
        # 44 with the first-run welcome (#174): its Not now button and its words put two more of Help's bold names on the page (46 fails)
        # 42 measured on the merge of main into this branch (44 on each side alone): the first-run welcome (#174) and Latest update with Move to Friday together put two more names on the page (43 fails)
        # 41 measured on the merge of main (42) into the #436 milestones finish (43): both sides' names on the page together (42 fails)
        # 44 measured on the merge of the Version and updates card (#282, PR 288) into main (46 there): Updates, Choose zip… and Undo update name things the page now draws
        # 39 measured on the refresh of the Version and updates card onto main (41 there): both sides' names on the page together (40 fails)
        # 41 measured on the take-over of PR 457 (#454) merged with main (42 there): the People card's Organisation column takes one more name off the absent list (42 fails)
        # 40 measured on the rebuild of item 454 on main (main is 41): the People card's Organisation column takes one more name off the absent list (41 fails)
        # 39 measured on the rebuild of item 434 on main (main is 40): the report rows' Edit parts put Help's bold Add from your project record on the page (40 fails)
        # 39 measured on the merge of main (40) into the project switcher's menu (item 439, 40): Project settings and the People card's Organisation column together (40 fails)
        # 38 measured on the merge of main (39) into item 434 (39): both sides' names on the page together (39 fails)
        # 37 measured on the merge of main (39) into the Word screens branch: the Word how-to (written, shown) bolds names that are on the page now, and the absent list is shorter (38 fails)
        # 33 measured on the merge of main (37) into the Settings Data card and Projects table (item 444, 34 on the earlier main): both sides' names on the page together (34 fails)
        # 36 measured on the merge of main (37) into item 434 (38): both sides' names on the page together (37 fails)
        # 32 measured on the merge of main (36) into the Settings Data card and Projects table (item 444, 33): both sides' names on the page together (33 fails)
        # 38 measured on the merge of main (40 there, the People card) into the refreshed Version and updates card: both sides' names on the page together (39 fails)
        # 40 measured with the project switcher's menu (item 439) on main: Project settings is on the page, so that bold name left the absent list (41 fails)
        # 37 measured on the merge of main (39 there, the project switcher's menu) into the refreshed Version and updates card (38): both sides' names on the page together (38 fails)
        # 35 measured on the merge of main (37 there, the Word screens) into the refreshed Version and updates card (37): both sides' names on the page together (36 fails)
        # 30 measured on the merge of main (32 there, the Settings Data card and Projects table) into the refreshed Version and updates card (35): both sides' names on the page together (31 fails)
        # 26 measured with item 445 (the Update card now draws the names Choose zip, Review, Show the files and the others; 30 before): the two
        # update Help entries are held (helpLater.json) until the release key is pinned, but the floor counts the whole source (27 fails)
        # 23 measured on the merge of main (26 there, the update card of item 445) into the Help overhaul branch: both sides' names on the page together (24 fails)
        # 16 measured with ask clark and Sneak peek released (#721): their corrected bold names are on the page (ask clark, Check this report, Apply, Confirm and apply, New chat, Close ...), 23 before
        # 15 measured with row 828 (the milestone peek's own fields: State, Progress, Visible to client and Client wording are on the page now, 16 before)
        self.assertGreaterEqual(len(names), 15)

        # 52 measured on the merge with main's supporting documents (#74), which puts one more Help name on the page; earlier, 53 on the merged tree with the Milestones page (#458) puts five more bold Help names on the page than main does, so they left the absent list (main is 58; measured on trial merges): Add a recovery action, Add milestone, Escalate to steering, Internal note, Rebaseline
        # 57 measured on the merged tree (main is 58), names printed: Show milestone details also left the absent list, which the remembered Hide or Show toggle for the milestone details (C-M6) puts on the page
        # 56 measured on the merged tree after the next main merge (names printed): the milestone details toggle (C-M6) leaves the list on top of the Supporting documents section
        # 51 measured on the merge with train-03 (names printed): its Milestones page (#458) and this branch's parity batch 1 each take Help names off the absent list

    def test_the_shown_keys_are_ones_the_page_answers(self):
        rows = [r[0] for r in SHOWN["reference"]["keys"]]
        self.assertEqual(rows, ["[[?]]", "[[/]]", "[[/]] [[/]]", "[[Esc]]", "[[Enter]]", "[[Shift+Enter]]", "[[Up]] [[Down]] [[Enter]]", "[[V]]", "[[E]]", "[[Alt+Up]] [[Alt+Down]]", "[[Home]] [[End]]",
                                "Click", "[[Mod]]+click", "[[Shift]]+click", "[[Mod+Shift]]+click", "[[Shift+Up]] [[Shift+Down]]",
                                "[[Space]]", "[[Mod+A]]", "The tick box on a group", "[[Esc]] with a selection", "[[O]] [[S]] [[P]] [[T]] [[C]]", "[[Shift+F10]]", "[[Mod+K]]",
                                "[[Up]] [[Down]] [[Home]] [[End]]", "[[Up]] [[Down]] [[Left]] [[Right]]", "[[Enter]]",
                                "[[Mod+J]]", "[[Up]] [[Down]]", "[[Left]] [[Right]] [[Home]]"])


GLANCE_PY = ROOT / "src" / "clark" / "glance.py"
SECTIONS_PY = ROOT / "src" / "clark" / "default_sections.py"      # the titles of the sections a new report starts with
# Words a shown Reference entry quotes that the page builds from data, so no source file holds them whole (each with the reason).
COMPUTED = {
    "3 days late": "Due, built from the date (workItems.js dueCell)",
    "In 5 days": "Due, built from the date (workItems.js dueCell)",
    "of n open actions": "the Overdue actions tile's detail, built from the count (glance.py)",
    "DPP-report-2026-10-30.html": "a worked example of the file name Publish builds from the project's code and the week ending (its form is checked by test_help_content.PublishFileName)",
    "this week\u2019s actions": "an example of what a card might be called, not a label",
    "decisions needed": "an example of what a card might be called, not a label",
    "3 of 12 selected": "the Hand over bar's count, built from the numbers (logic/handOver.js)",
    "api key": "the words the secret screen reads before a question is sent (ask_secret words, secret_screen.py)",
    "access key": "the words the secret screen reads before a question is sent (secret_screen.py)",
    "move to Friday, owner Jo, high priority": "a worked example of words typed in Sneak peek (its own placeholder is the same kind of line, SneakPeek.jsx)",
    "due Friday \u00b7 move to tomorrow \u00b7 by Friday": "words typed in Sneak peek, read by sneak.py (#721)",
    "owner Jo \u00b7 assign to Sam \u00b7 give it to Priya": "words typed in Sneak peek, read by sneak.py (#721)",
    "done \u00b7 closed \u00b7 reopen \u00b7 delayed \u00b7 cancelled": "words typed in Sneak peek, read by sneak.py (#721)",
    "made \u00b7 decided \u00b7 withdrawn \u00b7 pending": "words typed in Sneak peek, read by sneak.py (#721)",
    "forecast Friday \u00b7 achieved yesterday \u00b7 done \u00b7 reopen": "words typed in Sneak peek, read by sneak.py (row 728)",
    "flag \u00b7 high risk \u00b7 on track \u00b7 done \u00b7 committed \u00b7 candidate \u00b7 planned 2027 \u00b7 no flag \u00b7 headline": "words typed in Sneak peek, read by sneak.py (row 728)",
    "urgent priority \u00b7 high priority \u00b7 medium priority \u00b7 low priority": "words typed in Sneak peek, read by sneak.py (#721)",
    "Hand over 30 items to Priya?": "the Hand over question, built from the count and the name (logic/handOver.js)",
    "Put back the backup from DD-MM-YYYY 09:30? What you have now is kept first": "the Restore question, built from the backup's date and time (a worked example)",
}


def labels_of(entry):
    """Every control or label a shown entry names: its bold names, its quoted words, and the first cell of each table row."""
    out = set()
    for t in strings(entry):
        out |= set(re.findall(r"\*\*(.+?)\*\*", t)) | set(re.findall(r"\u201c(.+?)\u201d", t))
    for b in entry["b"] if "b" in entry else []:
        if b[0] == "tbl":
            for row in b[2]:
                out |= set(row[0].split(", "))
    return {re.sub(r"\s*\(.*?\)\s*$", "", x).strip(" .,:;\u2026") for x in out}


class ReleasedLabels(unittest.TestCase):
    """The check on #82: every label a RELEASED Help entry (How do I, Reference) names must be a word the page itself holds in its source (whole words,
    in the code of the page and of Help, and the tile titles in glance.py). Held entries are exempt: they are not shown."""
    PAGE = page_code(include_help=True) + "\n" + strip_comments(GLANCE_PY.read_text(encoding="utf-8")) + "\n" + strip_comments(SECTIONS_PY.read_text(encoding="utf-8"))

    @classmethod
    def on_page(cls, label):
        norm = lambda t: re.sub(r"[\u2018\u2019]", "'", t)
        pat = r"(?<![\w])" + re.escape(norm(label)) + r"(?![\w])"
        return bool(re.search(pat, norm(cls.PAGE))) or label in COMPUTED

    def missing(self, entries):
        return sorted({f"{e['id']}: {x}" for e in entries for x in labels_of(e) if not self.on_page(x)})

    def test_every_label_in_a_released_entry_is_on_the_page(self):
        entries = SHOWN["howto"]["tasks"] + SHOWN["reference"]["sections"]
        self.assertEqual(self.missing(entries), [], "a released Help entry names something the page does not have: reword it or hold the entry")

    def test_every_label_in_a_shown_guide_is_on_the_page(self):
        """#642: the control names in a guide's steps and result line are strings of the page, so a renamed button fails here."""
        self.assertTrue(SHOWN["guides"])
        self.assertEqual(self.missing(SHOWN["guides"]), [], "a guide names something the page does not have: reword it or hold the guide")
        named = {x for g in SHOWN["guides"] for x in labels_of(g)}
        for want in ("Edit", "Add a section", "Add section", "Move up", "Leave out of the published page", "Include in the published page", "Delete section"):
            self.assertIn(want, named)

    def test_the_check_fails_on_a_made_up_label(self):
        """Mutation check: a label the page does not have, as a bold name, a quoted word and a table row, is each reported."""
        bad = {"id": "x", "b": [["p", "Press **Frobnicate** or see \u201cWidget zone\u201d."], ["tbl", ["A", "B"], [["Gizmo row", "c"]]]]}
        self.assertEqual(self.missing([bad]), ["x: Frobnicate", "x: Gizmo row", "x: Widget zone"])

    def test_the_computed_words_are_still_in_shown_entries(self):
        """A word excused as computed must still be quoted by a released entry, or it is stale."""
        every = " ".join(shown_texts())
        for w in COMPUTED:
            self.assertIn(w, every)


class NeverDelete(unittest.TestCase):
    """HIGH 2 (the owner: we never delete, we archive): a record is archived, never deleted, in everything a person reads."""
    def user_text(self):
        return [s for s in strings(RAW)] + [s for s in strings(LATER)]

    def test_no_delete_in_the_words_except_the_section_button_as_the_page_labels_it(self):
        """Signed by the owner on 04-11-2026, build notes (the signed mockups): the string in SIGNED_DELETE is allowed, exactly, and no other
        Help word may say "delete" except the Delete section button's own name."""
        found = []
        for s in self.user_text():
            if s in SIGNED_DELETE:
                continue
            rest = s.replace(SECTION_DELETE, "")
            found += re.findall(r"(?i)\b(delet\w*)\b", rest)
        self.assertEqual(found, [])

    def test_the_section_button_is_named_as_the_page_names_it(self):
        self.assertIn(f"**{SECTION_DELETE}**", json.dumps(RAW, ensure_ascii=False))
        self.assertIn(f'text: "{SECTION_DELETE}"', (PAGE_SRC / "edit" / "Gutter.jsx").read_text(encoding="utf-8"))
        self.assertEqual(sum(s.count(SECTION_DELETE) for s in self.user_text()), 2)      # the how-to entry and the Move, hide and delete sections guide (#642)

    def test_archive_says_what_it_does(self):
        text = " ".join(self.user_text())
        for part in ("Archive hides the project and everything in it from the usual lists, the counts and the published page",
                     "**Show archived** finds it", "**Restore** and **Undo** bring it back"):
            self.assertIn(part, text)
        self.assertIn("Archive this use case", text)       # the button as the page labels it (#421: the held entry once said "Archive use case")
        self.assertIn("Archive milestone", text)


class AskClark(unittest.TestCase):
    """MEDIUM: ask clark is written in lower case, wherever it is, at the start of a sentence too."""
    def test_every_spelling_in_the_help_source_is_lower_case(self):
        bad = []
        for f in sorted(HELP.iterdir()):
            if f.suffix in (".json", ".js", ".jsx"):
                bad += [(f.name, m) for m in re.findall(r"(?i)\bask clark\b", f.read_text(encoding="utf-8")) if m != "ask clark"]
        self.assertEqual(bad, [])

    def test_the_whole_page_source_too(self):
        bad = []
        for f in PAGE_SRC.rglob("*"):
            if f.is_file() and f.suffix in (".js", ".jsx", ".json"):
                bad += [(f.name, m) for m in re.findall(r"(?i)\bask clark\b", f.read_text(encoding="utf-8")) if m != "ask clark"]
        self.assertEqual(bad, [])

    def test_the_first_step_no_longer_starts_with_it(self):
        self.assertNotIn("Ask clark", json.dumps(RAW, ensure_ascii=False))
        self.assertIn("Use ask clark to **Check this report**", json.dumps(RAW, ensure_ascii=False))


class Wording(unittest.TestCase):
    """The page test stays strict (team names, dd-mm-20yy dates). Help's real example dates and the template name Headline band are in
    held entries, and a held entry is left out of the built page, so the page test passes without an exception."""
    def test_the_page_test_has_no_exception_for_help(self):
        page_test = (ROOT / "tests" / "test_page.py").read_text(encoding="utf-8")
        self.assertNotIn("Help (#82) may carry", page_test)
        self.assertNotRegex(page_test, r"for allowed in")

    def test_a_held_entry_is_not_in_the_built_page(self):
        import sys
        sys.path.insert(0, str(ROOT / "dev" / "tools"))
        import build_page
        html = build_page.build()
        self.assertNotIn("Open the report with a message", html)
        self.assertNotIn("click another item anywhere on the page and the peek moves to it", html)      # a held entry (the peek) is not in the page


if __name__ == "__main__":
    unittest.main()
