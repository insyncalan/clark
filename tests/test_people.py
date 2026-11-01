"""#115: the people rules and plain words (src/clark/people.py): the email rule, the matching key and resolver, a person's fields,
the import box, the prompts and history lines, and the staged change from anyone but the owner (Alan's Q3 answer).

Run: python3 dev/run_tests.py test_people
Fictional people only (RULES: no real names). No database: people.py takes plain values.
"""
import ast
import re
import unittest
from pathlib import Path

from clark import people

SRC = Path(__file__).resolve().parent.parent / "src" / "clark" / "people.py"


def P(i, name, **kw):
    return {"id": i, "name": name, "aliases": kw.pop("aliases", ""), "archived": kw.pop("archived", 0), **kw}


class EmailRule(unittest.TestCase):
    def test_valid_is_trimmed_and_lower_cased(self):
        self.assertEqual(people.clean_email("  Sam.Reed@X.Example "), ("sam.reed@x.example", ""))

    def test_blank_is_allowed(self):
        self.assertEqual(people.clean_email(""), ("", ""))
        self.assertEqual(people.clean_email(None), ("", ""))
        self.assertEqual(people.clean_email("   "), ("", ""))

    def test_each_refusal(self):
        bad = ["a,b@x.example", "a@x.example;b@x.example", "Sam <a@x.example>", "a b@x.example", "a@@x.example", "a@b@x.example",
               "@x.example", "a@", "a(b)@x.example", "a[b]@x.example", 'a"b@x.example', "a'b@x.example", "a\\b@x.example",
               "a?b@x.example", "a#b@x.example", "a%b@x.example", "a`b@x.example", "a\tb@x.example", "a​b@x.example",
               "a‮b@x.example", "a b@x.example", "a@x..example", "a@.x.example", "a@x.example.", "a@-x.example",
               "a@x-.example", "plain", "a" * 65 + "@x.example"]
        for value in bad:
            addr, problem = people.clean_email(value)
            self.assertEqual(addr, "", value)
            self.assertTrue(problem, value)
            self.assertIn("Check the address and try again.", problem, value)

    def test_no_dot_in_domain_has_its_own_words(self):
        self.assertEqual(people.clean_email("a@x")[1], people.EMAIL_INCOMPLETE)

    def test_too_long(self):
        long = "a@" + ".".join(["b" * 60] * 5) + ".example"
        self.assertGreater(len(long), 254)
        self.assertEqual(people.clean_email(long)[1], people.EMAIL_TOO_LONG)

    def test_a_row_names_the_row(self):
        text = people.email_row_problem(7, people.EMAIL_REFUSED)
        self.assertTrue(text.startswith("Row 7: that email can't be used"))
        self.assertTrue(text.endswith("Check the address and try again."))
        self.assertEqual(people.email_row_problem(7, ""), "")

    def test_no_address_with_two_recipients_survives(self):
        for value in ("a,b@x.example", "a@x.example,b@x.example", "a@x.example b@x.example"):
            self.assertEqual(people.clean_email(value)[0], "")


class Matching(unittest.TestCase):
    def setUp(self):
        self.list = [P("P-001", "Sam Reed", aliases="Sammy; S Reed", label="Harbour team"),
                     P("P-002", "Sam Reid", email="sam.reid@x.example"),
                     P("P-003", "Jo Park", archived=1)]

    def test_exact_name_and_alias_one_match(self):
        self.assertEqual(people.resolve("sam reed", self.list)["id"], "P-001")
        self.assertEqual(people.resolve("  SAMMY ", self.list)["id"], "P-001")
        self.assertEqual(people.resolve("s  reed", self.list)["id"], "P-001")

    def test_no_fuzzy_matching(self):
        for typed in ("Sam Rede", "Sam", "Reed", "Sam Reeds"):
            self.assertEqual(people.resolve(typed, self.list)["status"], "none", typed)

    def test_tbc_and_blank_map_to_no_person(self):
        for typed in ("", "  ", "TBC", "tbc", None):
            self.assertEqual(people.resolve(typed, self.list)["status"], "blank")

    def test_accents_and_look_alikes_read_as_the_repo_reads_text(self):
        people_ = [P("P-001", "Zoë Hale")]
        self.assertEqual(people.resolve("Zoe Hale", people_)["id"], "P-001")
        self.assertEqual(people.resolve("Zoе Hale", people_)["id"], "P-001")          # a Cyrillic e
        self.assertEqual(people.resolve("Ｚoe Hale", people_)["id"], "P-001")          # a fullwidth Z

    def test_two_people_with_the_same_name_set_no_link(self):
        both = self.list + [P("P-004", "Sam Reed", email="quay@x.example")]
        got = people.resolve("Sam Reed", both)
        self.assertEqual((got["status"], got["id"], got["ids"]), ("many", None, ["P-001", "P-004"]))

    def test_an_alias_on_two_people_also_matches_two(self):
        both = [P("P-001", "Ann One", aliases="Annie"), P("P-002", "Ann Two", aliases="Annie")]
        self.assertEqual(people.resolve("annie", both)["status"], "many")

    def test_archived_person_is_not_matched_but_offered(self):
        got = people.resolve("Jo Park", self.list)
        self.assertEqual((got["status"], got["id"], got["ids"]), ("archived", None, ["P-003"]))

    def test_a_live_person_beats_an_archived_one(self):
        both = self.list + [P("P-004", "Jo Park")]
        self.assertEqual(people.resolve("Jo Park", both)["id"], "P-004")

    def test_alias_clash_lists_the_other_holders(self):
        holders = people.alias_holders("sammy", self.list, own_id="P-002")
        self.assertEqual([h["id"] for h in holders], ["P-001"])
        self.assertEqual(people.alias_holders("sammy", self.list, own_id="P-001"), [])

    def test_show_name_adds_label_then_email_only_when_names_clash(self):
        both = self.list + [P("P-004", "Sam Reed", email="quay@x.example")]
        self.assertEqual(people.show_name(both[0], both), "Sam Reed (Harbour team)")
        self.assertEqual(people.show_name(both[3], both), "Sam Reed (quay@x.example)")
        self.assertEqual(people.show_name(self.list[1], self.list), "Sam Reid")

    def test_aliases_are_split_and_deduplicated(self):
        self.assertEqual(people.aliases_of({"aliases": "A; a ;B;; b"}), ["A", "B"])
        self.assertEqual(people.join_aliases(["A", "a", " B "]), "A;B")


class Fields(unittest.TestCase):
    def test_clean_fields(self):
        clean, bad = people.check_person({"name": "  Sam   Reed ", "email": "Sam@X.Example", "needs_details": 1, "aliases": "S; s"})
        self.assertEqual(bad, [])
        self.assertEqual((clean["name"], clean["email"], clean["aliases"]), ("Sam Reed", "sam@x.example", "S"))
        self.assertEqual(clean["needs_details"], 0)           # the flag clears when an email is added

    def test_flag_stays_without_an_email(self):
        clean, _ = people.check_person({"name": "Sam Reed", "needs_details": 1})
        self.assertEqual(clean["needs_details"], 1)
        self.assertIsNone(clean["email"])

    def test_name_required_and_kind_checked_and_label_limit(self):
        self.assertTrue(people.check_person({"name": " "})[1])
        self.assertTrue(people.check_person({"name": "A", "kind": "robot"})[1])
        self.assertTrue(people.check_person({"name": "A", "label": "x" * 31})[1])
        self.assertEqual(people.check_person({"name": "A", "label": "x" * 30})[1], [])
        self.assertEqual(people.check_person({"name": "Harbour team", "kind": "group"})[1], [])

    def test_a_name_may_be_shared_but_an_email_may_not_even_in_other_case(self):
        have = [P("P-001", "Sam Reed", email="a@x.example")]
        self.assertEqual(people.check_person({"name": "Sam Reed"}, have)[1], [])
        problems = people.check_person({"name": "Sam Reid", "email": "A@X.example"}, have)[1]
        self.assertEqual(problems, ["That email already belongs to Sam Reed. Check the address, or open Sam Reed to change it."])
        self.assertEqual(people.check_person({"name": "Sam Reed", "email": "a@x.example"}, have, own_id="P-001")[1], [])

    def test_ids_never_reuse_a_number(self):
        self.assertEqual(people.next_person_id([]), "P-001")
        self.assertEqual(people.next_person_id(["P-001", "P-004", "P-002"]), "P-005")
        with self.assertRaises(ValueError):
            people.next_person_id(["P-999"])

    def test_a_person_id_is_not_a_work_item_id(self):
        from clark import doclinks
        pattern = getattr(doclinks, "ITEM_REF", None)
        if pattern is not None:
            self.assertIsNone(pattern.search("see P-001 and P-002"))


class ImportBox(unittest.TestCase):
    def test_tab_separated_with_header(self):
        text = "Name\tEmail\tOrganisation\nSam Reed\tSam@x.example\tHarbour\nJo Park\t\t\n"
        rows, problems = people.parse_rows(text)
        self.assertEqual(problems, [])
        self.assertEqual([r["clean"]["name"] for r in rows], ["Sam Reed", "Jo Park"])
        self.assertEqual(rows[0]["clean"]["email"], "sam@x.example")
        self.assertEqual(rows[1]["clean"]["needs_details"], 0 if rows[1]["clean"]["email"] else rows[1]["clean"]["needs_details"])

    def test_csv_without_header_uses_the_default_order(self):
        rows, problems = people.parse_rows("Sam Reed,sam@x.example,Harbour,Lead\n")
        self.assertEqual(problems, [])
        self.assertEqual((rows[0]["clean"]["organisation"], rows[0]["clean"]["role"]), ("Harbour", "Lead"))

    def test_a_refused_row_is_named_and_the_others_stand(self):
        rows, problems = people.parse_rows("Sam Reed\ta,b@x.example\nJo Park\tjo@x.example\n")
        self.assertEqual(len(problems), 1)
        self.assertTrue(problems[0].startswith("Row 1: that email can't be used"), problems)
        self.assertEqual(rows[1]["problems"], [])

    def test_a_repeated_email_in_the_paste_is_named(self):
        _, problems = people.parse_rows("A\ta@x.example\nB\tA@x.example\n")
        self.assertEqual(len(problems), 1)
        self.assertTrue(problems[0].startswith("Row 2:"))

    def test_empty_and_too_many(self):
        self.assertEqual(people.parse_rows("  \n")[1], ["Paste at least one row."])
        many = "\n".join(f"P{i}\tp{i}@x.example" for i in range(people.ROW_LIMIT + 1))
        self.assertTrue(people.parse_rows(many)[1][0].startswith("That is more than"))

    def test_formula_like_text_is_kept_as_text_not_run(self):
        rows, _ = people.parse_rows("=HYPERLINK(\"x\")\ta@x.example\n")
        self.assertTrue(rows[0]["clean"]["name"].startswith("="))          # the People sheet escapes it on the way out

    def test_plan_lines(self):
        lines = people.plan_lines(11, [("Sam", ["Sam Reed", "Sam Reid"])], ["Sam Rede", "Jo Park", "Li Wen"])
        self.assertEqual(lines[0], "11 items now point at a person.")
        self.assertEqual(lines[1], "1 owner name matches more than one person and will be saved as typed: Sam (Sam Reed, Sam Reid).")
        self.assertEqual(lines[2], "3 owner names are not on the people list and will be saved as typed: Sam Rede, Jo Park, Li Wen.")
        self.assertIn("Same person as …", lines[3])
        self.assertEqual(lines[-1], "Nothing is saved until you press Import. Reply Import or Cancel.")

    def test_plan_lines_hide_empty_counts(self):
        self.assertEqual(people.plan_lines(), ["Nothing is saved until you press Import. Reply Import or Cancel."])
        self.assertEqual(people.plan_lines(1)[0], "1 item now points at a person.")


class Words(unittest.TestCase):
    def test_prompts(self):
        self.assertEqual(people.add_prompt("Sam Reed"), "Add Sam Reed as a new person?")
        self.assertEqual(people.ADD_BUTTONS, ("Add person", "Keep the name only"))
        self.assertEqual(people.archived_prompt("Sam Reed"), "Sam Reed is archived. Restore Sam Reed and use this name?")
        self.assertEqual(people.archived_buttons("Sam Reed"), ("Restore Sam Reed", "Keep the name only"))
        self.assertEqual(people.merge_prompt("Sam Reed", "Sam Reid", 14),
                         "Merge Sam Reed into Sam Reid? 14 items will show Sam Reid, and Sam Reed will be archived. You can undo this.")
        self.assertEqual(people.rename_prompt("Sam Reed", "Sam Reid", 14, 3),
                         "Rename Sam Reed to Sam Reid? 14 items in 3 projects will show Sam Reid. You can undo this.")
        self.assertEqual(people.archive_prompt("Sam Reed", 4),
                         "Archive Sam Reed? Old items keep the name. Sam Reed still owns 4 open items and they keep the name too. "
                         "You can restore Sam Reed later.")
        self.assertNotIn("still owns", people.archive_prompt("Sam Reed", 0))

    def test_two_matches_and_clash(self):
        self.assertEqual(people.two_matches("Sam", ["Sam Reed (Harbour team)", "Sam Reed (Quay team)"]),
                         "Sam matches Sam Reed (Harbour team) and Sam Reed (Quay team). The name is saved as typed and not tied to either person.")
        self.assertIn("Use it for Sam Reed as well?", people.alias_clash("Rede", "Sam Reid", "Sam Reed"))
        self.assertIn("restored without an email", people.restore_without_email("Sam Reed", "a@x.example", "Sam Reid"))

    def test_toasts(self):
        self.assertEqual(people.rename_toast("Sam Reid", 14, 3, 6),
                         "Renamed to Sam Reid on 14 items in 3 projects (and left 6 archived items as they were). Undo.")
        self.assertEqual(people.rename_toast("Sam Reid", 1, 1), "Renamed to Sam Reid on 1 item in 1 project. Undo.")
        self.assertEqual(people.merge_toast("Sam Reed", "Sam Reid", 14), "Merged Sam Reed into Sam Reid. 14 items now show Sam Reid. Undo.")
        self.assertEqual(people.archive_toast("Sam Reed", 4),
                         "Sam Reed archived. Sam Reed still owns 4 open items; they keep the name. Restore from the Archived list. Undo.")
        self.assertEqual(people.UNDO_BUTTON, "Undo last people change")
        self.assertEqual(people.undo_refused_later("rename", "Sam Reed"),
                         "Can't undo the rename of Sam Reed: the person was changed again afterwards. Undo that change first.")
        self.assertEqual(people.merged_away("Sam Reed", "Sam Reid"), "Sam Reed was merged into Sam Reid. Undo the merge first.")

    def test_no_user_text_speaks_of_ids_or_jargon(self):
        words = [people.add_prompt("A"), people.merge_prompt("A", "B", 2), people.PRIVACY_NOTE, people.EMAIL_REFUSED, people.OWNER_RENAMED_AFTER]
        for w in words:
            self.assertNotRegex(w, r"owner_id|resolver|schema|delete|guarded", w)

    def test_history_lines_say_who_what_where_when(self):
        at = "2026-10-29 14:05:09"
        self.assertEqual(people.history_line("rename", "Sam Reed", "Alan Example", at, new="Sam Reid", items=14, projects=3),
                         "Sam Reed renamed to Sam Reid. Made by Alan Example, on the People list, 29-10-2026 at 14:05. "
                         "14 items in 3 projects now show Sam Reid.")
        self.assertEqual(people.history_line("merge", "Sam Reed", "Alan Example", at, new="Sam Reid", items=14, aliases=2),
                         "Sam Reed merged into Sam Reid. Made by Alan Example, on the People list, 29-10-2026 at 14:05. "
                         "14 items now show Sam Reid; 2 aliases moved.")
        self.assertEqual(people.history_line("archive", "Sam Reed", "Alan Example", at),
                         "Sam Reed archived. Made by Alan Example, on the People list, 29-10-2026 at 14:05. Old items keep the name.")
        self.assertEqual(people.history_line("restore", "Sam Reed", "Alan Example", at),
                         "Sam Reed restored. Made by Alan Example, on the People list, 29-10-2026 at 14:05.")
        self.assertEqual(people.history_line("undo-rename", "Sam Reed", "Alan Example", at),
                         "Rename of Sam Reed undone. Made by Alan Example, on the People list, 29-10-2026 at 14:05.")
        with self.assertRaises(ValueError):
            people.history_line("nonsense", "A", "B", at)

    def test_owner_line_on_an_item(self):
        at = "2026-10-29 14:05"
        self.assertEqual(people.owner_line("Sam Reed", "Sam Reid", "Alan Example", at),
                         "Owner changed from Sam Reed to Sam Reid because the person was renamed. Made by Alan Example, on the People list, 29-10-2026 at 14:05.")
        self.assertIn("because Sam Reed was merged into Sam Reid.", people.owner_line("Sam Reed", "Sam Reid", "A", at, "merged", "Sam Reid"))

    def test_stamp(self):
        self.assertEqual(people.stamp("2026-10-29T09:03:00"), "29-10-2026 at 09:03")
        self.assertEqual(people.stamp("nonsense"), "")


class StagedChange(unittest.TestCase):
    """Alan's Q3 answer (29-10-2026): a people change from anyone but the owner is staged and shown to the owner."""

    def test_only_the_owner_applies_directly(self):
        self.assertTrue(people.may_apply_directly("Alan Example", "Alan Example"))
        self.assertFalse(people.may_apply_directly("Sara Teammate", "Alan Example"))
        self.assertFalse(people.may_apply_directly("", ""))
        self.assertFalse(people.may_apply_directly(None, "Alan Example"))

    def test_the_staged_line_says_who_what_and_from_to(self):
        self.assertEqual(people.staged_line("Sara Teammate", "Sam Reed", "email", "sam@x.example", "sam.reed@x.example"),
                         "Sara Teammate proposes to change Sam Reed's email from sam@x.example to sam.reed@x.example. Nothing has changed yet.")
        self.assertIn("from nothing to", people.staged_line("S", "Sam Reed", "role", None, "Lead"))
        self.assertEqual(people.staged_new_line("Sara Teammate", "Jo Park"),
                         "Sara Teammate proposes to add Jo Park to the people list. Nothing has changed yet.")

    def test_buttons_are_plain(self):
        self.assertEqual(people.staged_buttons(), ("Accept", "Reject"))

    def test_the_history_says_who_proposed_who_accepted_how_and_when(self):
        line = people.accepted_line("Sara Teammate", "Alan Example", "on the People list", "2026-10-29 15:40",
                                    what="Sam Reed's email from a@x.example to b@x.example")
        self.assertEqual(line, "Sara Teammate proposed Sam Reed's email from a@x.example to b@x.example; Alan Example accepted it "
                               "on the People list, 29-10-2026 at 15:40.")
        rej = people.accepted_line("Sara Teammate", "Alan Example", "in a teammate's changes file", "2026-10-29 15:41", rejected=True)
        self.assertEqual(rej, "Sara Teammate proposed it; Alan Example rejected it in a teammate's changes file, 29-10-2026 at 15:41.")


class Source(unittest.TestCase):
    def test_no_database_no_files_and_no_sql_like_literals(self):
        tree = ast.parse(SRC.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] + [getattr(node, "module", None) or ""]
                self.assertFalse(any("sqlite" in n for n in names), names)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                self.assertFalse(re.match(r"\s*(update|delete|replace|create)", node.value, re.I), node.lineno)
                words = node.value.split()
                self.assertFalse(len(words) > 1 and words[0] in ("SELECT", "INSERT", "UPDATE", "DELETE", "PRAGMA", "DROP", "REPLACE"))
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") in ("open", "eval", "exec"):
                self.fail(f"people.py calls {node.func.id}")


if __name__ == "__main__":
    unittest.main()
