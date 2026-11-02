"""#48: the new items a Word file would add, staged for the person to accept (src/clark/word_import.py). Design: docs/handoff/design-48-word.md.

Run: python3 dev/run_tests.py test_word_import
Every file is made in the test from made-up text. What is asserted: only NEW actions, risks and issues, and decisions are staged;
nothing is accepted for the person; text from the file stays plain text; every row starts hidden from the client; an existing item
(a line with an ID) is never changed; the same content twice makes the rows once; a bad line names itself and is not staged; the
text is read through docx_read, so a hostile file stages nothing; every message is plain; the module touches no disk, network or
process. The guarded step that writes accepted rows (one step, one Undo, the history row) is not here.
"""
import re
import time
import unittest

from _paths import ROOT   # noqa: F401  (puts src/ on the path)

from clark import docx_build, docx_read, publish, word_import
from clark.word_import import WordImportError, stage
from test_docx_read import P, TBL, TR, docx
import _publish_fixture as fx

NAME = "week 43 notes.docx"
ON = "2026-10-29"
JARGON = r"(?i)\bzip\b|\bxml\b|\bentity\b|\bdtd\b|\brelationship|traceback|exception|errno|\bsql\b|\bjson\b|\bschema\b|fingerprint"


def H(text, level=1):
    return {"kind": "heading", "level": level, "text": text}


def para(text):
    return {"kind": "paragraph", "text": text}


def item(text):
    return {"kind": "list_item", "level": 0, "ordered": False, "text": text}


def table(*rows):
    return {"kind": "table", "rows": [list(r) for r in rows]}


def plan(blocks, seen=()):
    return stage(blocks, NAME, ON, seen)


class WhatIsStaged(unittest.TestCase):
    def test_new_actions_risks_issues_and_decisions_from_their_headings(self):
        p = plan([H("Weekly notes"), para("Intro that is not read."), H("Next steps"), item("Send the plan to Dana"),
                  para("Book the review room"), H("Risks"), item("Supplier may slip"), H("Issues"), item("Test rig is down"),
                  H("Decisions"), item("Use the shared drive")])
        self.assertEqual([(i.table, i.values.get("type")) for i in p.items],
                         [("actions", None), ("actions", None), ("raid", "Risk"), ("raid", "Issue"), ("decisions", None)])
        self.assertEqual([i.n for i in p.items], [1, 2, 3, 4, 5])
        self.assertEqual(p.items[0].values["description"], "Send the plan to Dana")
        self.assertEqual(p.items[4].values["decision"], "Use the shared drive")
        self.assertTrue(all(i.kind == "new" for i in p.items))

    def test_text_under_any_other_heading_is_noted_and_not_staged(self):
        p = plan([H("Background"), para("We met."), item("A point"), H("Actions"), item("Do it")])
        self.assertEqual(len(p.items), 1)
        self.assertTrue(any("2 paragraphs or list items are not under a heading" in n and "they were not read" in n for n in p.notes))

    def test_a_deeper_heading_stays_in_its_section_and_a_same_level_one_ends_it(self):
        p = plan([H("Actions"), H("Platform team", 2), item("Patch the host"), H("Notes"), item("Not an action")])
        self.assertEqual([i.values["description"] for i in p.items], ["Patch the host"])

    def test_a_risks_and_issues_heading_needs_each_line_to_say_which(self):
        p = plan([H("Risks and issues"), item("Risk: budget"), item("Issue - the vendor is late"), item("Something unmarked")])
        self.assertEqual([(i.values["type"], i.values["description"]) for i in p.items],
                         [("Risk", "budget"), ("Issue", "the vendor is late")])
        self.assertEqual(len(p.problems), 1)
        self.assertIn('Start it with "Risk:" or "Issue:"', p.problems[0].message)

    def test_an_empty_file_says_what_to_do(self):
        p = plan([H("Hello"), para("Nothing here.")])
        self.assertEqual(p.items, [])
        self.assertEqual((p.problems, p.already_created), ([], 0), "the box says it, once, from these counts")

    def test_a_table_is_read_by_its_headings(self):
        t = table(["Action", "Owner", "Priority", "Due", "Status", "Weight"],
                  ["Order the licences", "Sam Okafor", "high", "05-11-2026", "open", "3"],
                  ["Check the invoice", "", "", "2026-11-12", "", ""])
        p = plan([H("Actions"), t])
        a, b = p.items
        self.assertEqual((a.values["owner"], a.values["priority"], a.values["due_date"], a.values["status"]),
                         ("Sam Okafor", "High", "2026-11-05", "Open"))
        self.assertEqual(b.values["due_date"], "2026-11-12")
        self.assertNotIn("owner", b.values)
        self.assertTrue(any("Weight" in n for n in p.notes))
        self.assertIn("table 1, line 1", a.where)

    def test_a_risk_table_and_a_decision_table(self):
        p = plan([H("Risks"), table(["Item", "Impact", "Likelihood"], ["Late delivery", "High", "medium"]),
                  H("Decisions"), table(["Decision", "Status", "Made by", "Date"],
                                        ["Go with option B", "Made", "The board", "01-10-2026"],
                                        ["Pick a vendor", "", "", ""])])
        r, d1, d2 = p.items
        self.assertEqual((r.values["type"], r.values["impact"], r.values["likelihood"]), ("Risk", "High", "Medium"))
        self.assertEqual((d1.values["status"], d1.values["date"]), ("Made", "2026-10-01"))
        self.assertEqual(d2.values["status"], "Pending")

    def test_a_table_with_no_description_column_or_no_lines_is_noted(self):
        p = plan([H("Actions"), table(["Owner", "Due"], ["Sam", "05-11-2026"]), table(["Action"])])
        self.assertEqual(p.items, [])
        self.assertEqual(len(p.notes), 2)       # two tables (nothing found is said by the box, from the counts)

    def test_the_numbers_stay_in_order_across_tables_and_text(self):
        p = plan([H("Actions"), table(["Action"], ["One"], ["Two"]), item("Three")])
        self.assertEqual([(i.n, i.values["description"]) for i in p.items], [(1, "One"), (2, "Two"), (3, "Three")])


class NothingChangesAnExistingItem(unittest.TestCase):
    def test_a_line_with_an_id_is_left_alone(self):
        t = table(["ID", "Action", "Status"], ["PUB-A-001", "Changed words", "Closed"], ["", "A new one", "Open"])
        p = plan([H("Actions"), t])
        self.assertEqual([i.values["description"] for i in p.items], ["A new one"])
        self.assertTrue(any("are existing items" not in n and "it is an existing item" in n and "An import never changes an existing item" in n for n in p.notes))

    def test_no_row_is_changed_or_removed_and_nothing_is_closed(self):
        p = plan([H("Actions"), table(["Action", "Status"], ["Done thing", "Closed"], ["Dropped thing", "Cancelled"])])
        self.assertEqual(p.items, [])
        self.assertEqual(len(p.problems), 2)
        self.assertIn("Status \"Closed\" is not one of Open or Delayed", p.problems[0].message)

    def test_the_words_of_a_report_clark_wrote_come_back_as_nothing_new(self):
        pub = publish.select(fx.inputs(fx.load()))
        read = docx_read.read(docx_build.build(pub), "report.docx")
        p = stage(read, "report.docx", ON)
        self.assertEqual(p.items, [])
        self.assertTrue(any("existing items" in n for n in p.notes))


class NothingIsDecidedForThePerson(unittest.TestCase):
    def test_nothing_is_accepted_until_the_person_says(self):
        p = plan([H("Actions"), item("One"), item("Two"), item("Three")])
        self.assertEqual(p.accepted(), [])
        p.accept(2)
        self.assertEqual([i.n for i in p.accepted()], [2])
        p.accept_all()
        self.assertEqual(len(p.accepted()), 3)
        p.reject(1)
        self.assertEqual([i.n for i in p.accepted()], [2, 3])
        p.reject_all()
        self.assertEqual(p.accepted(), [])

    def test_an_unknown_number_is_said_in_words(self):
        with self.assertRaises(WordImportError) as c:
            plan([H("Actions"), item("One")]).accept(9)
        self.assertEqual(str(c.exception), "There is no item 9 in this list.")

    def test_every_row_starts_hidden_from_the_client_and_says_so(self):
        p = plan([H("Actions"), item("One"), H("Risks"), item("Two"), H("Decisions"), item("Three")])
        for i in p.items:
            self.assertEqual(i.values["client_visible"], 0)
            self.assertIn("Not shown to the client until you turn it on.", i.describe())
        self.assertIn("Not shown to the client until you turn it on.", p.report())

    def test_the_source_names_the_file_the_day_and_the_heading(self):
        p = plan([H("Next steps"), item("One")])
        self.assertEqual(p.items[0].values["source"], 'Word import, 29-10-2026, week 43 notes.docx, under "Next steps"')

    def test_a_file_name_with_a_path_or_odd_characters_is_cleaned(self):
        p = stage([H("Actions"), item("x")], "C:\\Users\\me\\a\u202etxt\x00.docx", ON)
        self.assertEqual(p.file, "atxt.docx")
        self.assertNotIn("\\", p.items[0].values["source"])
        self.assertEqual(stage([H("Actions"), item("x")], "", ON).file, "a Word file")

    def test_a_new_action_gets_the_day_it_was_raised_and_a_decision_does_not(self):
        p = plan([H("Actions"), item("A"), H("Decisions"), item("B")])
        self.assertEqual(p.items[0].values["raised"], ON)
        self.assertNotIn("raised", p.items[1].values)

    def test_a_day_that_is_not_a_day_stops_in_words(self):
        for bad in ("29-10-2026", "2026-13-40", None, ""):
            with self.assertRaises(WordImportError) as c:
                stage([], NAME, bad)
            self.assertNotRegex(str(c.exception), JARGON)


class TheSameFileTwice(unittest.TestCase):
    def test_the_same_content_makes_the_rows_once(self):
        blocks = [H("Actions"), item("Send the plan"), H("Risks"), item("Supplier may slip")]
        first = plan(blocks)
        again = plan(blocks, seen={i.fp for i in first.items})
        self.assertEqual(again.items, [])
        self.assertEqual(again.already_created, 2)
        self.assertIn("2 left out because they were added before or repeat another line", again.report())

    def test_the_fingerprint_ignores_the_file_the_day_and_the_client_flag(self):
        a = stage([H("Actions"), item("Send the plan")], "one.docx", "2026-10-01")
        b = stage([H("Actions"), item("Send the plan")], "two.docx", "2026-11-01")
        self.assertEqual(a.items[0].fp, b.items[0].fp)
        self.assertEqual(len(a.items[0].fp), 64)

    def test_two_different_rows_have_different_fingerprints(self):
        p = plan([H("Actions"), item("One"), H("Risks"), item("One")])
        self.assertNotEqual(p.items[0].fp, p.items[1].fp)

    def test_a_line_repeated_in_one_file_is_staged_once(self):
        p = plan([H("Actions"), item("Same"), item("Same"), item("same")])
        self.assertEqual([i.values["description"] for i in p.items], ["Same", "same"])
        self.assertEqual(p.already_created, 1)


class ABadLineNamesItself(unittest.TestCase):
    def test_a_bad_date_priority_and_status_each_say_where_and_what(self):
        t = table(["Action", "Due", "Priority"], ["Good one", "05-11-2026", "High"], ["Bad date", "31-02-2026", ""],
                  ["Bad priority", "", "Soon"])
        p = plan([H("Actions"), t])
        self.assertEqual([i.values["description"] for i in p.items], ["Good one"])
        self.assertEqual(len(p.problems), 2)
        self.assertIn("table 1, line 2 under \"Actions\"", p.problems[0].message)
        self.assertIn('Due "31-02-2026" is not a date. Write it as DD-MM-YYYY.', p.problems[0].message)
        self.assertIn('Priority "Soon" is not one of Urgent, High, Medium or Low.', p.problems[1].message)
        self.assertIn("Nothing was added from this line.", p.problems[1].message)

    def test_a_line_with_no_words_for_the_item(self):
        p = plan([H("Actions"), table(["Action", "Owner"], ["", "Sam"])])
        self.assertEqual(p.items, [])
        self.assertIn("there is no description to add", p.problems[0].message)
        p2 = plan([H("Decisions"), table(["Decision", "Status", "Date"], ["Choose", "Made", ""])])
        self.assertIn("it says Made but has no date", p2.problems[0].message)

    def test_every_refusal_and_note_that_blocks_a_line_ends_with_a_next_step(self):
        p = plan([H("Actions"), table(["Action", "Owner"], ["", "Sam"])])
        self.assertTrue(p.problems[0].message.endswith("Add a description and import again."))
        p = plan([H("Decisions"), table(["Decision", "Status", "Date"], ["Choose", "Made", ""])])
        self.assertTrue(p.problems[0].message.endswith("so this one cannot be added. Add the date in the Word file and choose the file again."))
        p = plan([H("Actions"), item("x" * (word_import.MAX_VALUE + 1))])
        self.assertTrue(p.problems[0].message.endswith("Shorten it and import again."))
        p = plan([H("Actions"), table(["Action", "Owner"])])
        self.assertTrue(any(n.endswith("Add the lines under the headings and import again.") for n in p.notes))
        p = plan([H("Actions"), table(["Owner", "Due"], ["Sam", "2026-11-01"])])
        self.assertTrue(any(n.endswith("Add a Description column and import again.") for n in p.notes))
        p = plan([H("Actions")] + [item(f"Row {i}") for i in range(word_import.MAX_ITEMS + 5)])
        self.assertTrue(any(n.endswith("Put the rest in a second file.") for n in p.notes))
        with self.assertRaises(WordImportError) as c:
            stage([], "a.docx", "2026-13-45")
        self.assertTrue(str(c.exception).endswith("Choose a real date and try again."))

    def test_a_risk_line_with_no_type_under_a_mixed_heading(self):
        p = plan([H("RAID"), table(["Item", "Owner"], ["Something", "Sam"])])
        self.assertEqual(p.items, [])
        self.assertIn("whether this is a risk or an issue", p.problems[0].message)

    def test_an_over_long_value_is_refused_not_cut(self):
        p = plan([H("Actions"), item("x" * (word_import.MAX_VALUE + 1)), item("y" * word_import.MAX_VALUE)])
        self.assertEqual(len(p.items), 1)
        self.assertIn("longer than 2,000 characters", p.problems[0].message)

    def test_a_flood_of_rows_is_cut_and_said(self):
        p = plan([H("Actions")] + [item(f"Row {i}") for i in range(word_import.MAX_ITEMS + 5)])
        self.assertEqual(len(p.items), word_import.MAX_ITEMS)
        self.assertTrue(any("5 more were not read" in n for n in p.notes))


class TextFromAFileIsOnlyText(unittest.TestCase):
    HOSTILE = '<script>alert(1)</script> <img src=x onerror=alert(1)> javascript:alert(1) {{PROJECT_NAME}} \x07\u202e'

    def test_markup_stays_inert_text_and_control_characters_go(self):
        p = plan([H("Actions"), item(self.HOSTILE)])
        text = p.items[0].values["description"]
        self.assertIn("<script>alert(1)</script>", text)       # kept as the words typed, never run: it is plain text in a plain field
        self.assertNotIn("\x07", text)
        self.assertNotIn("\u202e", text)

    def test_no_rich_field_is_seeded_and_nothing_else_than_the_known_fields_is_written(self):
        p = plan([H("Actions"), table(["Action", "Owner", "Labels", "Client messaging", "Source", "Client-visible", "Project"],
                                      ["Do it", "Sam", "x", "to the client", "elsewhere", "Yes", "ZZZ"]),
                  H("Decisions"), table(["Decision", "Reasoning", "Client messaging"], ["Go", "Because", "msg"])])
        self.assertEqual(word_import.RICH_FIELDS, frozenset())
        allowed = {"description", "decision", "owner", "priority", "due_date", "status", "latest_update", "type", "response_action",
                   "impact", "likelihood", "made_by", "needed_by", "date", "reasoning", "revisit", "raised", "client_visible",
                   "source"}
        for i in p.items:
            self.assertLessEqual(set(i.values), allowed)
            self.assertEqual(i.values["client_visible"], 0)
            self.assertNotIn("client_message", i.values)
            self.assertTrue(i.values["source"].startswith("Word import,"))

    def test_blanks_and_line_breaks_are_tidied_to_one_line(self):
        p = plan([H("Actions"), item("  Send   the\n plan\t now ")])
        self.assertEqual(p.items[0].values["description"], "Send the plan now")


class AHostileHeadingCannotFreezeOrFlood(unittest.TestCase):
    """"""
    def timed(self, blocks):
        started = time.time()
        p = plan(blocks)
        return p, time.time() - started

    def test_a_100000_dot_heading_stages_in_under_a_second(self):
        for text in ("a" + "." * 100_000 + "b", "." * 100_000 + "x", "Actions" + "." * 100_000 + "x", "-" * 100_000 + "x",
                     ":" * 100_000 + "x", "\u2013" * 100_000 + "x"):
            p, took = self.timed([H(text), item("Do it")])
            self.assertLess(took, 1, text[:12])
            self.assertEqual(p.items, [])

    def test_a_matching_heading_with_190000_dots_is_not_a_heading_and_nothing_long_is_copied(self):
        p, took = self.timed([H("Actions" + "." * 190_000), item("Send the plan"), table(["Action"], ["Another"])])
        self.assertLess(took, 1)
        self.assertEqual(p.items, [])
        self.assertLess(len(p.report()), 1000)
        self.assertTrue(any("1 paragraph or list item is not under a heading" in n and "it was not read" in n for n in p.notes))

    def test_what_is_kept_of_a_heading_is_short(self):
        p = plan([H("Actions" + " " * 50 + "." * 20), item("Send the plan")])      # 77 characters once tidied: still a heading
        self.assertEqual(len(p.items), 1)
        self.assertLessEqual(len(p.items[0].values["source"]), 200)
        self.assertEqual(word_import._heading_text("x" * 500), "x" * 79 + "\u2026")

    def test_the_longest_heading_that_can_match_still_matches(self):
        self.assertEqual(word_import._heading_kind("Actions" + "." * 60), "actions")
        self.assertEqual(word_import._heading_kind("3.  Next   steps :-"), "actions")
        self.assertIsNone(word_import._heading_kind("Actions" + "." * word_import.MAX_HEADING))

    def test_many_long_headings_stay_quick(self):
        p, took = self.timed([b for _ in range(200) for b in (H("Risks" + "." * 5_000 + "b"), item("x"))])
        self.assertLess(took, 2)

    def test_a_level_that_is_not_a_whole_number_is_taken_as_one(self):
        for level in ("2", None, "x", 2.9, [], float("inf")):
            blocks = [{"kind": "heading", "level": level, "text": "Actions"}, item("Do it")]
            self.assertEqual(len(plan(blocks).items), 1, repr(level))


class PlainWordsOfThePlan(unittest.TestCase):
    """"""
    BAD = re.compile(r"(?i)\bclean\b|\bstaged\b|\(s\)|\bparts?\b|\bword never\b")

    def test_the_report_says_waiting_then_accepted_or_rejected_and_never_clean(self):
        p = plan([H("Actions"), item("One"), item("Two"), item("Three")])
        self.assertEqual(p.items[0].state, "waiting")
        lines = p.report().splitlines()
        self.assertTrue(lines[1].startswith("  1. waiting: New action"), lines[1])
        p.accept(1)
        p.reject(2)
        lines = p.report().splitlines()
        self.assertTrue(lines[1].startswith("  1. accepted: New action"), lines[1])
        self.assertTrue(lines[2].startswith("  2. rejected: New action"), lines[2])
        self.assertTrue(lines[3].startswith("  3. waiting: New action"), lines[3])
        self.assertNotRegex(p.report(), self.BAD)

    def test_the_first_line_has_proper_plurals(self):
        one = plan([H("Actions"), item("One")]).report().splitlines()[0]
        self.assertIn("week 43 notes.docx: 1 new item found (1 action, 0 risks or issues, 0 decisions), 0 not added.", one)
        many = plan([H("Actions"), item("One"), item("Two"), H("Risks"), item("R"), item("S"), H("Decisions"), item("D")])
        self.assertIn(": 5 new items found (2 actions, 2 risks or issues, 1 decision), 0 not added.", many.report())
        self.assertNotRegex(many.report(), self.BAD)

    def test_the_notes_agree_in_number(self):
        one = plan([para("Loose"), H("Actions"), table(["ID", "Action"], ["PUB-A-001", "x"], ["", "new"])])
        self.assertIn("1 paragraph or list item is not under a heading for actions, risks, issues or decisions, so it was not read.",
                      one.notes)
        self.assertIn("1 table line carries an ID, so it is an existing item. An import never changes an existing item, so it was "
                      "left alone.", one.notes)
        two = plan([para("a"), para("b"), H("Actions"), table(["ID", "Action"], ["PUB-A-001", "x"], ["PUB-A-002", "y"])])
        self.assertIn("2 paragraphs or list items are not under a heading for actions, risks, issues or decisions, so they were "
                      "not read.", two.notes)
        self.assertIn("2 table lines carry an ID, so they are existing items. An import never changes an existing item, so they "
                      "were left alone.", two.notes)
        for n in one.notes + two.notes:
            self.assertNotRegex(n, self.BAD)

    def test_a_table_line_that_is_neither_risk_nor_issue_says_what_to_do(self):
        p = plan([H("Risks and issues"), table(["Item"], ["Supplier may slip"])])
        self.assertEqual(p.problems[0].message,
                         "table 1, line 1 under \"Risks and issues\": it does not say whether this is a risk or an issue. Add a Type "
                         "column or start the line with Risk or Issue. Nothing was added from this line.")

    def test_a_text_line_that_is_neither_says_what_to_do(self):
        p = plan([H("Risks and issues"), item("Supplier may slip")])
        self.assertIn("Start it with \"Risk:\" or \"Issue:\".", p.problems[0].message)

    def test_an_unknown_item_number_is_said_plainly(self):
        with self.assertRaises(WordImportError) as c:
            plan([H("Actions"), item("x")]).accept(7)
        self.assertEqual(str(c.exception), "There is no item 7 in this list.")

    def test_repeats_in_one_file_are_counted_in_the_report(self):
        p = plan([H("Actions"), item("Same"), item("Same")])
        self.assertIn("1 left out because they were added before or repeat another line", p.report())


class ReadFromARealFile(unittest.TestCase):
    def body(self):
        return (P("Weekly notes", style="Heading1") + P("Actions", style="Heading1") + P("Chase the supplier", style="ListBullet")
                + TBL(TR("Action", "Owner", "Due"), TR("Draft the brief", "Sam Okafor", "12-11-2026"))
                + P("Decisions", style="Heading1") + P("Move go-live to December") + P("Deleted words", hidden=True))

    def test_a_file_made_by_hand_stages_through_the_reader(self):
        read = docx_read.read(docx(self.body()), NAME)
        p = stage(read, NAME, ON)
        self.assertEqual([(i.table, i.values["description" if i.table == "actions" else "decision"]) for i in p.items],
                         [("actions", "Chase the supplier"), ("actions", "Draft the brief"),
                          ("decisions", "Move go-live to December")])
        self.assertEqual(p.items[1].values["owner"], "Sam Okafor")
        self.assertTrue(any("not read" in n or "hidden" in n.lower() for n in p.notes))   # the reader's own note comes through

    def test_a_hostile_file_never_reaches_staging(self):
        with self.assertRaises(docx_read.WordRefused):
            docx_read.read(docx(self.body(), parts={"word/vbaProject.bin": b"x"}), NAME)


class Plain(unittest.TestCase):
    def test_every_message_is_plain(self):
        p = plan([H("Actions"), table(["Action", "Due", "Priority", "Mystery"], ["A", "99", ""], ["B", "", "Soon"], ["C", "", ""]),
                  H("Risks and issues"), item("No type"), H("Decisions"), table(["Decision", "Status"], ["D", "Made"]),
                  para("x"), item("y"), H("Other"), item("z")])
        text = p.report() + "\n".join(str(x) for x in p.problems)
        self.assertNotRegex(text, JARGON)
        for line in text.splitlines():
            self.assertFalse(line.strip().lower().startswith("clark"))
        self.assertGreater(len(p.problems), 3)

    def test_the_module_touches_neither_disk_nor_network_nor_a_process(self):
        src = (ROOT / "src" / "clark" / "word_import.py").read_text(encoding="utf-8")
        for word in (r"(?<![.\w])open\(", r"\bsocket\b", r"\burllib\b", r"\bsubprocess\b", r"os\.system", r"\bpathlib\b", r"\bos\.",
                     r"\bsys\.", r"\bdatetime\.now", r"\bdate\.today", r"\btime\.time\b", r"\brandom\b", r"\bsqlite3\b",
                     r"\bopenpyxl\b", r"\bimport clark\.store\b", r"\bfrom clark import .*\bstore\b"):
            self.assertFalse(re.search(word, src), word)
        for module in re.findall(r"^(?:import|from) (\w+)", src, re.M):
            self.assertIn(module, ("hashlib", "json", "re", "unicodedata", "dataclasses", "datetime"), module)


if __name__ == "__main__":
    unittest.main()
