"""#47b: src/clark/edit_ai.py (the text-cleaning core copied from creaite's edit_ai.py, v2.6.9) and src/clark/confusables.py.

creaite has no stand-alone unit test of unseen/unmarked/normal: its suites reach them through the client gate
(test_client_gate_late.py 126, 186, 395; test_client_output_step1.py 329). These test the functions directly, one row each:
every default-ignorable range, controls, noncharacters, lone surrogates, the braille blank, look-alike letters, other scripts'
digits, an ID hidden by a tag character, loose_ids with codes and an `exists` callable, and that hidden_count counts what
normal() would drop, so a passage can be shown unchanged with a count beside it.

Run: python3 dev/run_tests.py test_edit_ai
Fictional data only.
"""
import ast
import unittest

from _paths import SRC
from clark import confusables, edit_ai
from clark.store import ID_PREFIX

CODES = ["ABC", "XYZ"]


def holds(*refs):
    return lambda ref: ref in refs


class Unseen(unittest.TestCase):
    def test_every_default_ignorable_range_its_ends_and_its_middle_are_dropped(self):
        self.assertEqual(len(edit_ai.DEFAULT_IGNORABLE), 17)
        for first, last in edit_ai.DEFAULT_IGNORABLE:
            for cp in {first, (first + last) // 2, last}:
                self.assertEqual(edit_ai.unseen(f"AB{chr(cp)}C"), "ABC", hex(cp))
                self.assertEqual(edit_ai.unseen(f"\u00e9{chr(cp)}"), "\u00e9", hex(cp))        # also in non-ASCII text

    def test_every_format_character_is_dropped(self):
        import unicodedata
        for cp in range(0x110000):
            if unicodedata.category(chr(cp)) == "Cf":
                self.assertEqual(edit_ai.unseen(f"A{chr(cp)}B"), "AB", hex(cp))

    def test_controls_noncharacters_and_lone_surrogates_are_dropped_and_line_breaks_kept(self):
        for cp in list(range(0, 9)) + [0x0e, 0x1f, 0x7f, 0x80, 0x9f, 0xfdd0, 0xfdef, 0xd800, 0xdbff, 0xdc00, 0xdfff]:
            self.assertEqual(edit_ai.unseen(f"A{chr(cp)}B"), "AB", hex(cp))
        for plane in range(17):
            for low in (0xFFFE, 0xFFFF):
                self.assertEqual(edit_ai.unseen(f"A{chr(plane * 0x10000 + low)}B"), "AB", hex(plane * 0x10000 + low))
        self.assertEqual(edit_ai.unseen("a\tb\nc\rd"), "a\tb\nc\rd")                           # tab, line feed and carriage return stay
        for c in edit_ai.LINE_LIKE:
            self.assertEqual(edit_ai.unseen(f"A{c}B"), "A\nB", repr(c))                       # where Word breaks the line

    def test_the_braille_blank_is_a_space(self):
        self.assertEqual(edit_ai.unseen("a\u2800b"), "a b")

    def test_plain_text_is_returned_as_it_is(self):
        text = "ABC-A-004 is due 2026-11-02."
        self.assertEqual(edit_ai.unseen(text), text)
        self.assertEqual(edit_ai.unseen(""), "")
        self.assertEqual(edit_ai.unseen(None), "")


class Normal(unittest.TestCase):
    def test_look_alike_letters_read_as_the_letters_they_resemble(self):
        cases = {"\u0410\u0412\u0421": "ABC",             # Cyrillic capitals
                 "\u0430\u0435\u043e\u0440\u0441": "aeoPc",   # Cyrillic small letters (creaite maps its \u0440 to a capital P: IDs are compared in capitals)
                 "\u0391\u0392\u0395": "ABE",               # Greek capitals
                 "\u03bf\u03c1": "oP",                      # Greek small letters
                 "\u0585": "o",                             # Armenian
                 "\u13aa\u13df": "AC",                      # Cherokee
                 "\u1d00\u1d04": "AC",                      # small capitals
                 "\u2010\u2011\u2013\u2014\u2212\uff0d": "------"}
        for text, want in cases.items():
            self.assertEqual(edit_ai.normal(text), want, text)

    def test_an_id_written_with_look_alikes_reads_as_the_id(self):
        self.assertEqual(edit_ai.normal("\u0410\u0412\u0421-\u0410-004"), "ABC-A-004")
        self.assertEqual(edit_ai.normal("ABC\u2011A\u2011004"), "ABC-A-004")
        self.assertEqual(set(edit_ai.ID_RE.findall(edit_ai.normal("see \u0410\u0412\u0421-\u0410-004."))), {"ABC-A-004"})

    def test_fullwidth_and_other_scripts_digits_read_as_0_to_9(self):
        self.assertEqual(edit_ai.normal("\uff21\uff22\uff23\uff0d\uff21\uff0d\uff10\uff10\uff14"), "ABC-A-004")
        self.assertEqual(edit_ai.normal("\u0661\u0662\u0663"), "123")                         # Arabic-Indic
        self.assertEqual(edit_ai.normal("\u06f1\u06f2\u06f3"), "123")                         # Persian
        self.assertEqual(edit_ai.normal("\u0967\u0968"), "12")                                # Devanagari

    def test_combining_marks_hide_nothing(self):
        self.assertEqual(edit_ai.unmarked("ABC-A-00\u0301" + "4"), "ABC-A-004")
        self.assertEqual(edit_ai.normal("ABC-A-00\u0301" + "4"), "ABC-A-004")
        self.assertEqual(edit_ai.unmarked("plain"), "plain")

    def test_normal_is_for_comparing_it_drops_the_joiners_that_persian_writing_uses(self):
        """The reason a passage is never rewritten with normal(): U+200C separates letters in Persian words (ruling on #47b)."""
        persian = "\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645"
        self.assertIn("\u200c", persian)
        self.assertNotIn("\u200c", edit_ai.normal(persian))
        self.assertNotEqual(edit_ai.normal(persian), persian)
        self.assertEqual(edit_ai.hidden_count(persian), 1)                                    # shown as a count; the text is left alone
        self.assertEqual(persian, "\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645")


class HiddenCount(unittest.TestCase):
    def test_counts_what_a_reader_cannot_see(self):
        self.assertEqual(edit_ai.hidden_count("plain text"), 0)
        self.assertEqual(edit_ai.hidden_count(""), 0)
        self.assertEqual(edit_ai.hidden_count(None), 0)
        self.assertEqual(edit_ai.hidden_count("a\u200bb\u200dc"), 2)
        self.assertEqual(edit_ai.hidden_count("A" + chr(0xE0041) + chr(0xE0042) + "C"), 2)   # Unicode tag characters
        self.assertEqual(edit_ai.hidden_count("a\x00b\x07c"), 2)
        self.assertEqual(edit_ai.hidden_count("a\ufdd0b\ud800"), 2)
        self.assertEqual(edit_ai.hidden_count("a\u2800"), 1)
        self.assertEqual(edit_ai.hidden_count("tab\tnew\nline\r"), 0)

    def test_it_agrees_with_unseen_about_what_is_dropped(self):
        for cp in (0x00AD, 0x200B, 0x202E, 0x2066, 0xFEFF, 0xE0041, 0x0007, 0xFDD0):
            text = f"a{chr(cp)}b"
            self.assertEqual(edit_ai.hidden_count(text), 1, hex(cp))
            self.assertEqual(len(edit_ai.unseen(text)), 2, hex(cp))


class LooseIds(unittest.TestCase):
    def test_every_id_form_the_store_makes_matches_the_strict_pattern(self):
        for table, prefix in ID_PREFIX.items():
            ref = f"ABC{prefix}001"
            self.assertEqual(edit_ai.ID_RE.findall(f"see {ref}."), [ref], table)
        self.assertEqual(sorted(ID_PREFIX.values()), sorted(["-A-", "-D-", "-", "-M-", "-W-", "-U-", "-S-"]))     # #65 adds -S- (a report section)
        for ref in ("ABC-A-001", "ABC-001", "ABC-D-001", "ABC-M-001", "ABC-W-001", "ABC-U-001", "ABC-S-001"):
            self.assertTrue(edit_ai.ID_RE.fullmatch(ref), ref)
        self.assertFalse(edit_ai.ID_RE.search("abc-a-001"))
        self.assertFalse(edit_ai.ID_RE.search("ABC-A-0001"))

    def test_the_strict_form_is_found_anywhere_without_asking_exists(self):
        def never_asked(ref):
            raise AssertionError("asked")
        self.assertEqual(edit_ai.loose_ids([], never_asked, "Due: ABC-A-004 and ABC-007"), {"ABC-A-004", "ABC-007"})

    def test_the_loose_forms_of_creaites_docstring(self):
        ref = "ABC-A-004"
        for text in ("abc a 004", "ABC (A) 004", "ABC.A.004", "ABC_A_004", "ABC/A/004", "ABC:A:004", "ABC\\-A\\-004",
                     "seeABC-A-004", "ABC-A-4", "ABC-A-OO4", "ABC - A - 004", "[ABC-A-004]", "ABC A\n004"):
            self.assertEqual(edit_ai.loose_ids(CODES, holds(ref), text), {ref}, text)
        self.assertEqual(edit_ai.loose_ids(CODES, holds("ABC-004"), "abc 004, ABC-004"), {"ABC-004"})
        self.assertEqual(edit_ai.loose_ids(CODES, holds("ABC-D-012"), "xyz and abc d 12"), {"ABC-D-012"})

    def test_a_number_is_a_whole_number(self):
        self.assertEqual(edit_ai.loose_ids(CODES, holds("ABC-A-040", "ABC-A-004"), "ABC-A-40"), {"ABC-A-040"})
        self.assertEqual(edit_ai.loose_ids(CODES, lambda r: True, "ABC A 10/09"), set())      # a date, not an ID
        self.assertEqual(edit_ai.loose_ids(CODES, lambda r: True, "ABC A 10:30"), set())
        self.assertEqual(edit_ai.loose_ids(CODES, lambda r: True, "ABC A 10.5"), set())

    def test_a_loose_match_counts_only_when_exists_says_it_is_real(self):
        self.assertEqual(edit_ai.loose_ids(CODES, lambda r: False, "ABC 100 users and abc a 4"), set())
        self.assertEqual(edit_ai.loose_ids(CODES, holds("ABC-100"), "ABC 100 users"), {"ABC-100"})
        asked = []
        edit_ai.loose_ids(CODES, lambda r: asked.append(r) or True, "abc a 4")
        self.assertEqual(asked, ["ABC-A-004"])

    def test_an_exists_that_raises_counts_the_id(self):
        def broken(ref):
            raise RuntimeError("the store can't be read")
        self.assertEqual(edit_ai.loose_ids(CODES, broken, "abc a 4"), {"ABC-A-004"})

    def test_an_id_with_a_hidden_tag_character_is_still_found(self):
        hidden = "ABC-A-0" + chr(0xE0041) + "04"
        self.assertNotIn("ABC-A-004", hidden)
        self.assertEqual(edit_ai.loose_ids(CODES, lambda r: True, hidden), {"ABC-A-004"})
        for hide in ("\u200b", "\u2060", "\ufeff", "\u00ad", "\u202e", "\u0301", "\x00"):
            self.assertEqual(edit_ai.loose_ids(CODES, lambda r: True, "A" + hide + "BC-A-0" + hide + "04"), {"ABC-A-004"}, repr(hide))
        self.assertEqual(edit_ai.loose_ids(CODES, lambda r: True, "\u0410\u0412\u0421-\u0410-004"), {"ABC-A-004"})

    def test_only_this_projects_codes_are_looked_for_and_odd_codes_are_ignored(self):
        self.assertEqual(edit_ai.loose_ids(["XYZ"], lambda r: True, "abc a 4"), set())
        self.assertEqual(edit_ai.loose_ids(["ab", None, 5, "A.C", "ABC"], lambda r: True, "abc a 4"), {"ABC-A-004"})
        self.assertEqual(edit_ai.loose_ids(None, lambda r: True, "nothing here"), set())
        self.assertEqual(edit_ai.loose_ids(CODES, lambda r: True, ""), set())
        self.assertEqual(edit_ai.loose_ids(CODES, lambda r: True, None), set())

    def test_the_letter_o_is_not_a_milestone_letter(self):
        self.assertEqual(edit_ai.loose_ids(CODES, lambda r: True, "ABC O 4"), set())          # A-N and P-Z only: "O" is a zero


class Confusables(unittest.TestCase):
    def test_skeleton_reads_look_alikes_and_hidden_characters_as_plain_letters(self):
        self.assertEqual(confusables.skeleton("\u0410\u0412\u0421\u200b-\u0410-004"), "ABC-A-004")
        self.assertEqual(confusables.skeleton("\uff21\uff22\uff23\u2013A\u2013004"), "ABC-A-004")
        self.assertEqual(confusables.skeleton(None), "")
        self.assertEqual(confusables.skeleton(5), "5")
        self.assertTrue(confusables.TABLE)
        self.assertEqual(confusables.TABLE[0x0410], "A")

    def test_the_table_pairs_one_letter_for_one(self):
        for chars, latin in confusables._PAIRS:
            self.assertEqual(len(chars), len(latin))


class Source(unittest.TestCase):
    def test_no_tracker_store_database_or_other_creaite_module_is_imported(self):
        banned = {"tracker", "store", "paths", "sqlite3", "subprocess", "socket", "urllib", "status_checks", "client_leak",
                  "client_output", "drafts", "report", "log", "permissions", "notes", "reach"}
        for name in ("edit_ai.py", "confusables.py"):
            tree = ast.parse((SRC / "clark" / name).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                mods = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                    [node.module or ""] + [f"{node.module}.{a.name}" for a in node.names] if isinstance(node, ast.ImportFrom) else [])
                for m in mods:
                    self.assertFalse(set(m.split(".")) & banned, f"{name}: imports {m}")

    def test_what_is_cut_is_not_there(self):
        for name in ("OPTIONS", "PLACES", "request", "context", "parse", "check", "result", "relevel", "options", "client_problems",
                     "VIP_LOOSE", "project_facts", "in_tracker"):
            self.assertFalse(hasattr(edit_ai, name), name)
        for name in ("ID_RE", "CODE_RE", "Refused", "LOOK_ALIKE", "CONTROLS", "unseen", "unmarked", "normal", "loose_ids", "hidden_count"):
            self.assertTrue(hasattr(edit_ai, name), name)

    def test_the_rule_for_a_passage_is_written_in_the_module(self):
        doc = edit_ai.__doc__
        self.assertIn("COMPARE AND DETECT", doc)
        self.assertIn("U+200C", doc)


if __name__ == "__main__":
    unittest.main()
