"""#1295: the files of ask clark slash commands (ask_commands.py): read, write, validate, remove, reset. No browser.

Run: python3 dev/run_tests.py test_ask_commands
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT  # noqa: F401  (puts src/ on the path)
from clark import ask_commands as ac

GOOD = {"name": "check", "menu": "Check it", "text": "Look at {item}", "scope": "item", "result": "answer"}
BI = ("history", "new", "who")


class AskCommandsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.s = ac.AskCommands(self.root, BI)

    def test_write_then_read_round_trip(self):
        self.s.write(GOOD)
        self.assertEqual(self.s.read(), ([GOOD], []))
        self.assertTrue((self.root / "ask-commands" / "check.json").is_file())

    def test_read_with_no_folder_is_empty(self):
        self.assertEqual(self.s.read(), ([], []))

    def test_name_rules_say_why(self):
        for bad, word in (("a", "at least"), ("x" * 25, "at most"), ("Check", "lower case"), ("a b", "spaces"),
                          ("1ab", "start with a letter"), ("a_b", "only lower case"), ("who", "built-in")):
            with self.assertRaises(ac.Refused, msg=bad) as cm:
                self.s.write({**GOOD, "name": bad})
            self.assertIn(word, str(cm.exception))
        self.assertEqual(list(self.root.rglob("*.json")), [])

    def test_path_like_names_cannot_escape(self):
        for bad in ("../x", "a/b", "..", "a.json"):
            with self.assertRaises(ac.Refused):
                self.s.write({**GOOD, "name": bad})
        self.assertEqual([p for p in self.root.rglob("*") if p.is_file()], [])

    def test_field_limits(self):
        for field, val, word in (("menu", "m" * 71, "70"), ("menu", " ", "menu"), ("text", "t" * 1001, "1,000"), ("text", "", "plain words"),
                                 ("scope", "all", "where"), ("result", "x", "what you get")):
            with self.assertRaises(ac.Refused) as cm:
                self.s.write({**GOOD, field: val})
            self.assertIn(word, str(cm.exception))
        self.s.write({**GOOD, "menu": "m" * 70, "text": "t" * 1000})

    def test_twenty_is_the_limit_but_an_edit_is_not_blocked(self):
        for i in range(20):
            self.s.write({**GOOD, "name": "cmd-%02d" % i})
        with self.assertRaises(ac.Refused) as cm:
            self.s.write({**GOOD, "name": "one-more"})
        self.assertIn("20", str(cm.exception))
        self.s.write({**GOOD, "name": "cmd-03", "menu": "Changed"})
        self.assertEqual(len(self.s.read()[0]), 20)

    def test_duplicate_name_refused_and_rename_moves_the_file(self):
        self.s.write(GOOD)
        self.s.write({**GOOD, "name": "other"})
        with self.assertRaises(ac.Refused):
            self.s.write({**GOOD, "name": "other"}, was="check")
        self.s.write({**GOOD, "name": "renamed"}, was="check")
        self.assertEqual([r["name"] for r in self.s.read()[0]], ["other", "renamed"])

    def test_builtin_is_saved_as_own_version_and_reset(self):
        rec = {"replaces": "who", "menu": "Mine", "text": "Who has {item}?", "scope": "item", "result": "answer"}
        self.assertEqual(self.s.write(rec)["name"], "who")
        self.assertEqual(self.s.read()[0][0]["replaces"], "who")
        self.s.reset("who")
        self.assertEqual(self.s.read()[0], [])

    def test_locked_and_unknown_builtins_cannot_be_saved(self):
        for rep, word in (("history", "action"), ("new", "action"), ("nope", "No built-in")):
            with self.assertRaises(ac.Refused) as cm:
                self.s.write({**GOOD, "replaces": rep})
            self.assertIn(word, str(cm.exception))

    def test_remove_is_for_your_own_only(self):
        self.s.write(GOOD)
        self.s.write({**GOOD, "replaces": "who"})
        self.s.remove("check")
        with self.assertRaises(ac.Refused):
            self.s.remove("who")
        with self.assertRaises(ac.Refused):
            self.s.remove("check")
        self.assertEqual([r["name"] for r in self.s.read()[0]], ["who"])

    def test_damaged_files_are_skipped_and_listed(self):
        self.s.write(GOOD)
        d = self.root / "ask-commands"
        (d / "broken.json").write_text("{not json", encoding="utf-8")
        (d / "wrongname.json").write_text('{"name":"other","menu":"m","text":"t","scope":"item","result":"answer"}', encoding="utf-8")
        (d / "big.json").write_text(" " * 9000, encoding="utf-8")
        (d / "list.json").write_text("[1]", encoding="utf-8")
        (d / "history.json").write_text('{"name":"history","replaces":"history","menu":"m","text":"t","scope":"item","result":"answer"}', encoding="utf-8")
        good, damaged = self.s.read()
        self.assertEqual([r["name"] for r in good], ["check"])
        self.assertEqual(sorted(damaged), ["big.json", "broken.json", "history.json", "list.json", "wrongname.json"])

    def test_unknown_fields_are_not_kept(self):
        self.s.write({**GOOD, "evil": "x"})
        self.assertNotIn("evil", (self.root / "ask-commands" / "check.json").read_text(encoding="utf-8"))

    def test_ai_flag_kept_only_when_true(self):
        self.s.write({**GOOD, "ai": True})
        self.assertTrue(self.s.read()[0][0]["ai"])
        self.s.write({**GOOD, "ai": False})
        self.assertNotIn("ai", self.s.read()[0][0])

    def test_no_side_file_left_after_a_save(self):
        self.s.write(GOOD)
        self.assertEqual([p.name for p in (self.root / "ask-commands").iterdir()], ["check.json"])


class AskCommandsKillersTest(unittest.TestCase):
    """Row 1295 mutation sweep of ask_commands.py: each test pins a rule a one-edit change of the file used to get past."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.s = ac.AskCommands(self.root, BI)
        self.d = self.root / "ask-commands"

    def test_name_length_edges(self):
        self.assertEqual(ac.name_problem("ab"), "")
        self.assertEqual(ac.name_problem("a" * 24), "")
        self.assertIn("at least 2", ac.name_problem("a"))
        self.assertIn("at most 24", ac.name_problem("a" * 25))
        self.s.write({**GOOD, "name": "ab"})
        self.s.write({**GOOD, "name": "a" * 24})
        self.assertEqual([r["name"] for r in self.s.read()[0]], ["a" * 24, "ab"])

    def test_name_problem_returns_empty_text_not_none(self):
        self.assertEqual(ac.name_problem("good-name", ["other"], "", BI), "")
        self.assertEqual(ac.name_problem("who", (), "who", BI), "")            # its own name is never "used"
        self.assertEqual(ac.name_problem("check", ["check"], "check"), "")
        self.assertIn("built-in", ac.name_problem("who", (), "", BI))
        self.assertIn("already", ac.name_problem("check", ["check"], "", BI))

    def test_hyphen_and_digit_names(self):
        self.assertIn("start with a letter", ac.name_problem("-ab"))
        self.assertIn("start with a letter", ac.name_problem("9ab"))
        self.assertEqual(ac.name_problem("a-1"), "")
        self.assertIn("only lower case", ac.name_problem("ab!"))
        self.assertIn("only lower case", ac.name_problem("ab\u00e9"))

    def test_problems_lists_all_in_order_and_survives_odd_values(self):
        self.assertEqual(ac.problems("x"), ["That slash command could not be read."])
        self.assertEqual(ac.problems(None), ["That slash command could not be read."])
        odd = ac.problems({"name": "check", "menu": 5, "text": ["x"], "scope": "item", "result": "answer"})
        self.assertEqual(len(odd), 2)
        self.assertIn("menu", odd[0])
        self.assertIn("plain words", odd[1])
        self.assertEqual(len(ac.problems({"name": "A", "menu": "", "text": "  \n ", "scope": "x", "result": "y"})), 5)
        self.assertTrue(ac.problems({"name": "check", "menu": "m", "text": "   ", "scope": "item", "result": "answer"}))
        self.assertTrue(ac.problems({"name": "check", "menu": "m", "text": "t", "scope": None, "result": "answer"}))
        self.assertEqual(ac.problems({"name": "check", "menu": "m", "text": "t", "scope": "usecase", "result": "draft"}), [])

    def test_a_built_in_version_is_not_checked_for_its_name(self):
        self.assertEqual(ac.problems({"replaces": "who", "name": "BAD NAME", "menu": "m", "text": "t", "scope": "item", "result": "answer"}), [])

    def test_first_problem_is_the_one_shown(self):
        with self.assertRaises(ac.Refused) as cm:
            self.s.write({**GOOD, "name": "Bad", "text": ""})
        self.assertIn("lower case", str(cm.exception))

    def test_file_path_refuses_other_names(self):
        for bad in ("../x", "a/b", "", "A", "a.json", "-a"):
            with self.assertRaises(ac.Refused, msg=bad) as cm:
                self.s._file(bad)
            self.assertIn("That is not a name a slash command can have.", str(cm.exception))
        self.assertEqual(self.s._file("who"), self.d / "who.json")

    def test_write_of_a_non_record_says_it_could_not_be_read(self):
        for bad in ("x", ["name"], None, 5):
            with self.assertRaises(ac.Refused, msg=repr(bad)) as cm:
                self.s.write(bad)
            self.assertIn("could not be read", str(cm.exception))

    def test_the_file_text_is_exact_and_keeps_letters_as_they_are(self):
        self.s.write({**GOOD, "menu": "Caf\u00e9 check", "ai": True})
        txt = (self.d / "check.json").read_text(encoding="utf-8")
        self.assertIn("Caf\u00e9 check", txt)
        self.assertTrue(txt.startswith('{\n "name": "check",\n'))
        self.assertTrue(txt.endswith('"ai": true\n}\n'))
        self.assertEqual(self.s.read()[0][0]["menu"], "Caf\u00e9 check")

    def test_a_built_in_version_drops_the_ai_flag_and_takes_the_built_in_name(self):
        out = self.s.write({**GOOD, "name": "ignored", "replaces": "who", "ai": True})
        self.assertEqual(out["name"], "who")
        self.assertNotIn("ai", out)
        self.assertNotIn("ai", (self.d / "who.json").read_text(encoding="utf-8"))

    def test_built_in_versions_do_not_count_toward_twenty_or_names(self):
        self.s.write({**GOOD, "replaces": "who"})
        for i in range(20):
            self.s.write({**GOOD, "name": "cmd-%02d" % i})
        self.assertEqual(len(self.s.read()[0]), 21)

    def test_renaming_at_twenty_is_allowed_and_adding_is_not(self):
        for i in range(20):
            self.s.write({**GOOD, "name": "cmd-%02d" % i})
        self.s.write({**GOOD, "name": "cmd-99"}, was="cmd-03")
        names = [r["name"] for r in self.s.read()[0]]
        self.assertEqual((len(names), "cmd-99" in names, "cmd-03" in names), (20, True, False))
        with self.assertRaises(ac.Refused):
            self.s.write({**GOOD, "name": "cmd-98"})

    def test_saving_under_the_name_it_was_opened_with_keeps_the_file(self):
        self.s.write(GOOD)
        self.s.write({**GOOD, "menu": "Again"}, was="check")
        self.assertEqual(self.s.read()[0][0]["menu"], "Again")
        self.assertTrue((self.d / "check.json").is_file())

    def test_rename_when_the_old_file_is_already_gone_still_saves(self):
        self.s.write({**GOOD, "name": "fresh"}, was="ghost")
        self.assertEqual([r["name"] for r in self.s.read()[0]], ["fresh"])

    def test_a_built_in_save_does_not_delete_a_file_named_by_was(self):
        self.s.write(GOOD)
        self.s.write({**GOOD, "replaces": "who"}, was="check")
        self.assertEqual(sorted(r["name"] for r in self.s.read()[0]), ["check", "who"])

    def test_the_folder_is_made_with_its_parents(self):
        s = ac.AskCommands(self.root / "data" / "project", BI)
        s.write(GOOD)
        self.assertTrue((self.root / "data" / "project" / "ask-commands" / "check.json").is_file())

    def test_a_failed_rename_leaves_the_old_file_whole_and_no_side_file(self):
        self.s.write(GOOD)
        before = (self.d / "check.json").read_text(encoding="utf-8")
        with mock.patch.object(ac.os, "replace", side_effect=OSError("disk")):
            with self.assertRaises(ac.Refused) as cm:
                self.s.write({**GOOD, "menu": "New words"})
        self.assertIn("could not be saved", str(cm.exception))
        self.assertIn("Nothing was changed", str(cm.exception))
        self.assertEqual((self.d / "check.json").read_text(encoding="utf-8"), before)
        self.assertEqual([p.name for p in self.d.iterdir()], ["check.json"])

    def test_only_json_files_are_read(self):
        self.s.write(GOOD)
        (self.d / "notes.txt").write_text("hello", encoding="utf-8")
        (self.d / "other.json.part").write_text("{", encoding="utf-8")
        self.assertEqual(self.s.read(), ([GOOD], []))

    def _padded(self, size, **over):
        body = json.dumps({**GOOD, **over})
        return body + " " * (size - len(body))

    def test_file_size_limit_is_eight_kilobytes_exactly(self):
        self.s.write(GOOD)
        (self.d / "edge.json").write_text(self._padded(8192, name="edge"), encoding="utf-8")
        (self.d / "over.json").write_text(self._padded(8193, name="over"), encoding="utf-8")
        good, damaged = self.s.read()
        self.assertEqual([r["name"] for r in good], ["check", "edge"])
        self.assertEqual(damaged, ["over.json"])

    def test_a_link_is_skipped_even_when_what_it_points_to_is_good(self):
        self.s.write(GOOD)
        elsewhere = self.root / "elsewhere.txt"
        elsewhere.write_text(json.dumps({**GOOD, "name": "linked"}), encoding="utf-8")
        try:
            (self.d / "linked.json").symlink_to(elsewhere)
        except OSError:
            self.skipTest("no symlinks here")
        good, damaged = self.s.read()
        self.assertEqual(([r["name"] for r in good], damaged), (["check"], ["linked.json"]))

    def test_a_file_with_a_broken_rule_is_damaged_not_good(self):
        self.s.write(GOOD)
        for stem, extra in (("badscope", {"scope": "everywhere"}), ("badtext", {"text": ""}), ("badreplace", {"replaces": "other"}),
                            ("nolocked", {"replaces": "history", "name": "history"})):
            rec = {**GOOD, "name": extra.get("name", stem), **{k: v for k, v in extra.items() if k != "name"}}
            (self.d / (extra.get("name", stem) + ".json")).write_text(json.dumps(rec), encoding="utf-8")
        good, damaged = self.s.read()
        self.assertEqual([r["name"] for r in good], ["check"])
        self.assertEqual(sorted(damaged), ["badreplace.json", "badscope.json", "badtext.json", "history.json"])

    def test_a_good_file_with_extra_fields_is_read_without_them(self):
        (self.d).mkdir()
        (self.d / "check.json").write_text(json.dumps({**GOOD, "evil": 1, "replaces": None}), encoding="utf-8")
        self.assertEqual(self.s.read(), ([GOOD | {"replaces": None}], []))

    def test_a_file_that_is_not_utf8_is_damaged(self):
        self.d.mkdir()
        (self.d / "check.json").write_bytes(b'{"name": "check", "menu": "\xe9"}')
        self.assertEqual(self.s.read(), ([], ["check.json"]))

    def test_reset_leaves_your_own_shortcut_and_a_missing_name_alone(self):
        self.s.write(GOOD)
        self.s.reset("check")
        self.s.reset("who")
        self.assertEqual([r["name"] for r in self.s.read()[0]], ["check"])
        self.s.write({**GOOD, "replaces": "who"})
        self.s.reset("who")
        self.assertEqual([r["name"] for r in self.s.read()[0]], ["check"])

    def test_remove_deletes_the_file_and_keeps_the_others(self):
        self.s.write(GOOD)
        self.s.write({**GOOD, "name": "other"})
        self.s.remove("check")
        self.assertEqual(sorted(p.name for p in self.d.iterdir()), ["other.json"])

    def test_remove_and_reset_refuse_names_that_could_leave_the_folder(self):
        with self.assertRaises(ac.Refused):
            self.s.remove("../x")
        self.s.reset("../x")
        self.assertEqual(self.s.read(), ([], []))


class AskCommandsKillersRound2Test(unittest.TestCase):
    """Row 1295, second independent sweep (~/ag/1883-killers.md): the sentences are pinned whole, and a side file that was never made is no error."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.s = ac.AskCommands(self.root, BI)

    def test_every_sentence_is_exact(self):
        self.assertEqual(ac.name_problem("Check"), "Use lower case letters only in the name.")
        self.assertEqual(ac.name_problem("a_b"), "The name can have only lower case letters, numbers and hyphens.")
        self.assertEqual(ac.name_problem("a b"), "The name cannot have spaces. Use a hyphen instead.")
        self.assertEqual(ac.name_problem("a"), "The name needs at least 2 characters.")
        self.assertEqual(ac.name_problem("a" * 25), "The name can be at most 24 characters.")
        self.assertEqual(ac.name_problem("1ab"), "The name must start with a letter.")
        self.assertEqual(ac.problems({**GOOD, "menu": "m" * 71}), ["The line in the menu can be at most 70 characters."])
        self.assertEqual(ac.problems({**GOOD, "menu": ""}), ["Say what it does in the menu, in a few words."])
        self.assertEqual(ac.problems({**GOOD, "text": "t" * 1001}), ["The instructions can be at most 1,000 characters."])
        self.assertEqual(ac.problems({**GOOD, "text": ""}), ["Say what it should do, in plain words."])
        self.assertEqual(ac.problems({**GOOD, "scope": "x"}), ["Choose where it appears."])
        self.assertEqual(ac.problems({**GOOD, "result": "x"}), ["Choose what you get."])

    def test_the_refusals_of_write_are_exact(self):
        with self.assertRaises(ac.Refused) as cm:
            self.s.write({**GOOD, "replaces": "history"})
        self.assertEqual(str(cm.exception), "/history is an action, not a question, so it cannot be edited.")
        for i in range(20):
            self.s.write({**GOOD, "name": "cmd-%02d" % i})
        with self.assertRaises(ac.Refused) as cm:
            self.s.write({**GOOD, "name": "one-more"})
        self.assertEqual(str(cm.exception), "You can keep 20 slash commands in a project. Remove one to add another.")

    def test_a_save_that_fails_before_the_side_file_exists_is_refused_not_crashed(self):
        with mock.patch.object(Path, "write_text", side_effect=OSError("full")):
            with self.assertRaises(ac.Refused) as cm:
                self.s.write(GOOD)
        self.assertEqual(str(cm.exception), "That slash command could not be saved. Nothing was changed.")
        self.assertEqual(list(self.root.rglob("*.json*")), [])


if __name__ == "__main__":
    unittest.main()
