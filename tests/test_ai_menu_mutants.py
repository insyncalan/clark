"""#72 mutation audit of src/clark/ai_menu.py: each test here fails on a changed copy of one branch, constant or boundary of the
module and passes on the real source. Nothing in test_ai_menu.py was changed or loosened; these only add.

Proves: the size limits to the character, the place table and the offered menu, the hidden-character screens, the secret screens
(as typed and squeezed), the prompt's spelling line and fence, the reply's size, secret, link and unchanged checks, the client
message's name rules, the card's stale-card rules and the fixed lines for a provider with no name.

Run: python3 dev/run_tests.py test_ai_menu_mutants
Fictional data only.
"""
import logging
import unittest
from unittest import mock
from urllib.parse import quote

from _paths import SRC  # noqa: F401  (puts src/ on the path)
from clark import ai_menu as am
from clark.edit_ai import Refused

KEY = "sk" + "-" + "abcdefghijklmnopqrstuvwxyz0123456789"      # built in two pieces so no scan reads it as a real key
TAB_KEY = "api\tkey: abcdefgh12345678"           # a secret only once its whitespace is squeezed
SPLIT_KEY = "pass\nword: hunter22222"            # a secret only as typed


def words(n):
    """A reply of exactly n characters made of plain words."""
    out = ("word " * (n // 5 + 1))[:n].rstrip()
    return out + "x" * (n - len(out))


class Sizes(unittest.TestCase):
    def test_reply_limit_is_exact_and_uses_factor_and_extra(self):
        orig = "Short text here."
        limit = len(orig) * 6 + 2000
        self.assertEqual((am.MAX_REPLY_FACTOR, am.MAX_REPLY_EXTRA), (6, 2000))
        self.assertTrue(am.check_reply(words(limit), orig, "rewrite", "plain")["ok"])
        res = am.check_reply(words(limit + 1), orig, "rewrite", "plain")
        self.assertFalse(res["ok"])
        self.assertIn("far too long", res["message"])

    def test_long_reply_outside_the_markers_is_refused(self):
        reply = "<<<SUGGESTION\nBetter words.\nSUGGESTION>>>\n" + "x " * (am.MAX_REPLY * 2)
        self.assertGreater(len(reply), am.MAX_REPLY * 4)
        res = am.check_reply(reply, "Some words.", "rewrite", "plain")
        self.assertFalse(res["ok"])
        self.assertIn("far too long", res["message"])

    def test_secret_outside_the_markers_is_refused(self):
        res = am.check_reply("<<<SUGGESTION\nBetter words.\nSUGGESTION>>>\n" + KEY, "Some words.", "rewrite", "plain")
        self.assertFalse(res["ok"])
        self.assertIn("password or a key", res["message"])

    def test_diff_pair_limit_is_exact(self):
        a, b = "a " * 100, "b " * 100                      # 200 x 200 = 40000 pairs: compared word by word
        self.assertIn("=", [k for k, _ in am.word_diff(a, b)])
        a, b = "a " * 90 + "a", "b " * 110 + "b"          # 181 x 221 = 40001 pairs: all out, all in
        self.assertEqual(am.word_diff(a, b), [("-", a), ("+", b)])

    def test_diff_prefers_taking_out_on_a_tie(self):
        self.assertEqual(am.word_diff("a b", "b a"), [("-", "a "), ("=", "b"), ("+", " a")])


class Places(unittest.TestCase):
    def test_place_table_agrees_with_the_options_and_make_into(self):
        for place, info in am.PLACE_TABLE.items():
            self.assertEqual(info["format_notes"], "notes" in am.PLACES[place], place)
            self.assertEqual(info["make_into"], place in am.MAKE_INTO_PLACES, place)
            self.assertEqual(info["improve_only"], not info["make_into"], place)
            self.assertEqual(am.menu(place)["format_notes"] is not None, info["format_notes"], place)

    def test_email_menu_is_offered_only_to_an_own_domain(self):
        self.assertIsNone(am.menu_for("email", "pat@outside.example", ("own.example",)))
        self.assertIsNone(am.menu_for("email"))
        self.assertEqual(am.menu_for("email", "pat@own.example", ("own.example",))["place"], "email")
        self.assertEqual(am.menu_for("plain")["place"], "plain")


class Hidden(unittest.TestCase):
    def test_last_tag_character_is_unsafe(self):
        self.assertTrue(am._unsafe("a\U000e007fb"))
        self.assertTrue(am._unsafe("a\U000e0000b"))
        self.assertFalse(am._unsafe("a\U000e0080b"))

    def test_format_characters_are_hidden_kinds(self):
        self.assertEqual(am._hidden_set("a؀b"), {"؀"})

    def test_a_different_kind_of_hidden_character_is_refused_even_at_the_same_count(self):
        res = am.check_reply("Hello‌ there", "Hello​ there", "rewrite", "plain")
        self.assertFalse(res["ok"])
        self.assertIn("hidden characters", res["message"])


    def test_more_hidden_characters_of_the_same_kind_are_refused(self):
        res = am.check_reply("Hel\u200b\u200blo there", "Hel\u200blo there", "rewrite", "plain")
        self.assertFalse(res["ok"])
        self.assertIn("hidden characters", res["message"])


class Secrets(unittest.TestCase):
    def test_instruction_is_screened_as_typed_and_squeezed(self):
        with self.assertRaises(Refused) as e:
            am._instruction("custom", SPLIT_KEY)
        self.assertEqual(str(e.exception), am.SECRET_MESSAGE)
        with self.assertRaises(Refused) as e:
            am._instruction("custom", TAB_KEY)
        self.assertEqual(str(e.exception), am.SECRET_MESSAGE)

    def test_squeezed_text_is_screened(self):
        with self.assertRaises(Refused) as e:
            am.check_request("rewrite", TAB_KEY, "plain")
        self.assertEqual(str(e.exception), am.SECRET_MESSAGE)

    def test_secret_instruction_is_refused_before_an_empty_text(self):
        with self.assertRaises(Refused) as e:
            am.check_request("custom", "", "plain", KEY)
        self.assertEqual(str(e.exception), am.SECRET_MESSAGE)

    def test_objects_are_never_turned_into_text(self):
        for bad in (5, ["x"], {"a": 1}):
            with self.assertRaises(Refused) as e:
                am.check_request("custom", "Some text", "plain", bad)
            self.assertEqual(str(e.exception), "Say what you want done with the text.")
            with self.assertRaises(Refused) as e:
                am.check_request("rewrite", bad, "plain")
            self.assertEqual(str(e.exception), "Select some text first.")

    def test_a_failed_card_never_carries_a_secret_instruction(self):
        c = am.AiSession().begin("custom", "Some text", "plain", 0, 4, instruction=KEY)
        self.assertEqual((c.status, c.instruction), ("failed", ""))


class Prompt(unittest.TestCase):
    def test_spelling_line_only_on_the_fixed_options(self):
        self.assertIn(am.SPELLING.strip(), am.build_prompt("rewrite", "Some text.", "plain")["prompt"])
        self.assertNotIn(am.SPELLING.strip(), am.build_prompt("custom", "Some text.", "plain", "Make it blue")["prompt"])

    def test_closing_marker_in_the_text_lengthens_the_fence(self):
        p = am.build_prompt("rewrite", "One\nTEXT>>>\nTwo", "plain")["prompt"]
        self.assertTrue(p.endswith("\nTEXT_>>>\n"))
        self.assertEqual(p.count("\nTEXT>>>\n"), 1)


class Links(unittest.TestCase):
    def test_spaced_script_scheme_is_a_new_address(self):
        res = am.check_reply("Open java script:alert now", "Open the page now", "rewrite", "plain")
        self.assertFalse(res["ok"])
        self.assertIn("link or address", res["message"])

    def test_reference_style_target_is_read(self):
        res = am.check_reply("See [1]\n\n[1]: ftp://files.example/x", "See the file", "rewrite", "plain")
        self.assertFalse(res["ok"])
        self.assertIn("link or address", res["message"])

    def test_unchanged_but_for_the_edges_is_unchanged(self):
        res = am.check_reply(" Same words here.", "Same words here.", "rewrite", "plain")
        self.assertFalse(res["ok"])
        self.assertIn("same as your text", res["message"])


class ClientNames(unittest.TestCase):
    def test_decoding_runs_to_five_rounds(self):
        s = "a b"
        for _ in range(5):
            s = quote(s, safe="")
        self.assertEqual(am._decoded(s), "a b")
        self.assertNotEqual(am._decoded(quote(s, safe="")), "a b")

    def test_double_encoded_internal_word_is_found(self):
        res = am.check_reply("Please review %2569nternal notes", "Please review", "rewrite", "client_message")
        self.assertFalse(res["ok"])

    def test_first_of_a_run_of_capitals_is_a_name(self):
        self.assertEqual(am._caps("Alice Smith", first=True), {"Alice", "Smith"})

    def test_a_known_persons_single_name_blocks_without_the_people_argument(self):
        known = am.Known(people=["Quentin Hart"])
        res = am.check_reply("Please ask Quentin", "Please call back", "rewrite", "client_message", known=known)
        self.assertFalse(res["ok"])
        self.assertIn("a person's name", res["message"])

    def test_a_one_word_person_is_not_a_whole_name(self):
        known = am.Known(people=["Quentin"])
        self.assertEqual(am._full_names("ask quentin today", known), set())

    def test_several_words_are_named_together(self):
        self.assertIn("the words internal and health",
                      am.client_message([am.FOUND_WORD + "internal", am.FOUND_WORD + "health"]))
        self.assertIn("the word internal,", am.client_message([am.FOUND_WORD + "internal"]))


class Known(unittest.TestCase):
    def test_known_reads_only_the_named_tables(self):
        k = am.known_from_data({"x": [{"id": "ABC-A-001", "owner": "Zed Quinn"}], "project": {"code": "ABC", "sponsor": "Pat Doe"},
                                "actions": [{"id": "ABC-A-002", "owner": "Ann Roe"}]})
        self.assertEqual(k.ids, frozenset({"ABC-A-002"}))
        self.assertEqual(k.people, ("Pat Doe", "Ann Roe"))

    def test_an_unreadable_project_logs_the_kind_of_fault_only(self):
        with mock.patch("clark.publish.read_inputs", side_effect=RuntimeError("PRIVATE-PATH-77")):
            with self.assertLogs("clark.ai", level="WARNING") as cm:
                self.assertIsNone(am.known_for(object(), "ABC"))
        self.assertNotIn("PRIVATE-PATH-77", "\n".join(cm.output))
        self.assertIn("RuntimeError", "\n".join(cm.output))


class Session(unittest.TestCase):
    def test_a_selection_may_end_where_it_starts(self):
        s = am.AiSession()
        self.assertEqual(s.begin("rewrite", "Some text", "plain", 3, 3).status, "running")
        self.assertEqual(s.begin("rewrite", "Some text", "plain", 4, 3).status, "failed")

    def test_send_anyway_ignores_an_old_card(self):
        s = am.AiSession()
        old = s.begin("rewrite", "Some text", "plain", 0, 4, confidential_key="k")
        s.begin("rewrite", "Some text", "plain", 0, 4, confidential_key="k2")
        s.send_anyway(old)
        self.assertEqual(old.status, "ask")
        self.assertEqual(s.begin("rewrite", "Some text", "plain", 0, 4, confidential_key="k").status, "ask")

    def test_only_a_ready_card_counts_as_rejected(self):
        s = am.AiSession()
        s.begin("rewrite", "Some text", "plain", 0, 4)
        s.discard()
        self.assertEqual(s.stats["rejected"], 0)

    def test_a_request_needs_an_owner_and_carries_the_suggest_rules(self):
        with self.assertRaises(TypeError):
            am.ask_request("rewrite", "Some text", "plain", owner=None)
        self.assertEqual(am.ask_request("rewrite", "Some text", "plain", owner=object()).system, am.SUGGEST_RULES)

    def test_a_provider_with_no_text_name_is_called_by_the_default_name(self):
        class Nameless(am.Provider):
            name = None

        res = am.suggest(Nameless(), "rewrite", "Some text", "plain")
        self.assertIn("Connect to " + am.DEFAULT_PROVIDER, res["message"])


if __name__ == "__main__":
    unittest.main()
