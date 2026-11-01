"""#72 slice 7: the client check knows the project. A reply for a client message is blocked when it adds one of the project's real item
codes or people's names (or a loose code in any spelling); what the user's own text already held may stay; the line names the kind of
thing found and never repeats it. The email place is offered only for an address on the user's own domains. Fictional names.
Run: cd tests && PYTHONPATH=../src python3 -m unittest test_ai_client_known"""
import json
import unittest
from pathlib import Path

import _paths  # noqa: F401
from _demo import DemoStore, USER
from clark import ai_menu as am

CORPUS = json.loads((Path(__file__).parent / "fixtures" / "ai-client-parity.json").read_text(encoding="utf-8"))

DATA = {
    "project": {"code": "ABC", "sponsor": "Priya Nair"},
    "milestones": [{"id": "ABC-M-001", "owner": "Tomas Ruiz"}],
    "actions": [{"id": "ABC-A-004", "owner": "Mia Hale"}, {"id": "ABC-A-040", "owner": ""}],
    "raid": [{"id": "ABC-001", "owner": "Omar Reid"}],
    "decisions": [{"id": "ABC-D-001", "made_by": "Lena Voss"}],
    "use_cases": [{"id": "ABC-U-001"}],
}
KNOWN = am.known_from_data(DATA)
WROTE = "We will send the plan on Friday and confirm the date with you."


def reply(text):
    return "<<<SUGGESTION\n" + text + "\nSUGGESTION>>>"


def check(text, original=WROTE, known=KNOWN, people=()):
    return am.check_reply(reply(text), original, "rewrite", "client_message", people, known)


class TheKnownSet(unittest.TestCase):
    def test_codes_item_codes_and_people_come_from_the_rows(self):
        self.assertEqual(KNOWN.codes, ("ABC",))
        self.assertEqual(KNOWN.ids, {"ABC-M-001", "ABC-A-004", "ABC-A-040", "ABC-001", "ABC-D-001", "ABC-U-001"})
        self.assertEqual(set(KNOWN.people), {"Priya Nair", "Tomas Ruiz", "Mia Hale", "Omar Reid", "Lena Voss"})

    def test_nothing_in_gives_an_empty_set(self):
        k = am.known_from_data(None)
        self.assertEqual((k.codes, tuple(k.ids), k.people), ((), (), ()))

    def test_it_is_built_from_the_real_store(self):
        with DemoStore() as store:
            with store.step("dashboard", USER) as st:
                a = st.create("actions", {"project": "ABC", "description": "Check the cut-over", "owner": "Mia Hale",
                                          "raised": "2026-10-01", "source": "demo"})
            k = am.known_for(store, "ABC")
            self.assertIn(a, k.ids)
            self.assertIn("ABC-M-001", k.ids)
            self.assertIn("ABC-U-001", k.ids)
            self.assertIn("Mia Hale", k.people)
            self.assertEqual(k.codes, ("ABC",))
            self.assertIsNone(am.known_for(store, "ZZZ"))          # no such project: the shape rules stay in force


class RealCodesAndNames(unittest.TestCase):
    def test_a_real_item_code_in_any_spelling_is_blocked(self):
        for added in ("See ABC-A-004.", "See abc a 004.", "See ABC (A) 004.", "See ABC-A-4.", "See ABC\\-A\\-OO4.", "See seeABC-001.",
                      "See ABC 001."):
            r = check(WROTE + " " + added)
            self.assertFalse(r["ok"], added)
            self.assertIn("an item code", r["message"], added)

    def test_a_made_up_strict_code_is_blocked_too_but_ordinary_words_are_not(self):
        self.assertFalse(check(WROTE + " See ABC-A-999.")["ok"])
        for fine in ("It needs ABC 100 users.", "Phase B 12 starts in week 3.", "Version 2 of the plan."):
            r = check(WROTE + " " + fine)
            self.assertTrue(r["ok"], (fine, r["message"]))

    def test_a_loose_code_that_is_no_real_item_is_not_blocked(self):
        self.assertTrue(check(WROTE + " The ABC a 5 route is open.")["ok"])
        self.assertFalse(check(WROTE + " The ABC a 4 route is open.")["ok"])

    def test_a_known_persons_name_is_blocked_in_any_case(self):
        for added in ("Mia Hale will call you.", "mia hale will call you.", "Please ask Lena  Voss.", "Thanks to Priya."):
            r = check(WROTE + " " + added)
            self.assertFalse(r["ok"], added)
            self.assertIn("a person's name", r["message"], added)

    def test_a_word_that_is_only_part_of_a_name_is_not_a_name_when_it_is_in_lower_case(self):
        self.assertTrue(check(WROTE + " We will be there on time.")["ok"])
        self.assertTrue(check(WROTE + " The nair of the plan is clear.")["ok"])

    def test_without_a_known_set_the_shape_rules_stand(self):
        self.assertFalse(check(WROTE + " See ABC-A-004.", known=None)["ok"])
        self.assertFalse(check(WROTE + " See abc a 5.", known=None)["ok"])
        self.assertTrue(check(WROTE + " See abc a 5.")["ok"])           # with the set, ABC-A-005 is no real item


class WhatTheUserHad(unittest.TestCase):
    def test_a_code_the_user_wrote_may_stay(self):
        original = "ABC-A-004 is done and ABC-A-040 is next."
        self.assertTrue(check("ABC-A-004 is finished, and ABC-A-040 comes next.", original)["ok"])

    def test_a_code_the_user_wrote_does_not_let_another_through(self):
        r = check("ABC-A-004 is finished, and ABC-001 comes next.", "ABC-A-004 is done and we will tell you what is next.")
        self.assertFalse(r["ok"])

    def test_a_loose_code_the_user_wrote_in_a_different_spelling_may_stay(self):
        self.assertTrue(check("ABC-A-004 is finished.", "abc a 4 is done.")["ok"])

    def test_a_name_the_user_wrote_may_stay(self):
        original = "Mia Hale will send the plan on Friday."
        self.assertTrue(check("Mia Hale sends the plan on Friday.", original)["ok"])
        self.assertFalse(check("Mia Hale sends the plan on Friday; Omar Reid will confirm.", original)["ok"])

    def test_a_word_the_user_wrote_may_stay(self):
        original = "The health of the build is good."
        self.assertTrue(check("The build is in good health.", original)["ok"])


class TheMessageNamesTheKind(unittest.TestCase):
    def test_each_kind_is_named_without_the_thing(self):
        cases = (("See ABC-A-004.", "an item code", "ABC-A-004"),
                 ("Mia Hale will call.", "a person's name", "Mia"),
                 ("It is VIP work.", "an internal marker", "VIP"))
        for added, kind, leak in cases:
            m = check(WROTE + " " + added)["message"]
            self.assertIn(kind, m)
            self.assertNotIn(leak, m)
            self.assertNotIn("A-004", m)

    def test_a_word_from_the_fixed_list_is_named(self):
        m = check(WROTE + " The health is poor.")["message"]
        self.assertIn("the word health", m)
        m = check(WROTE + " The health is poor and the status is amber.")["message"]
        self.assertIn("the words amber and health", m)

    def test_several_kinds_are_named_together(self):
        m = check(WROTE + " Mia Hale says ABC-A-004 is red.")["message"]
        self.assertIn("an item code, a person's name and the word red", m)

    def test_the_line_is_plain_and_says_what_to_do(self):
        m = check(WROTE + " See ABC-A-004.")["message"]
        self.assertEqual(m, "The suggestion added an item code, which a client should not see, so it was not shown. Try again.")

    def test_an_odd_word_form_is_not_echoed(self):
        m = check(WROTE + " This is internalised wording.")["message"]
        self.assertIn("the word internal", m)
        m = check(WROTE + " Not for the client.")["message"]
        self.assertIn("wording meant for the team", m)
        self.assertNotIn("not for", m.lower())


class TheListsStillHold(unittest.TestCase):
    """The parity lists, run with a known set as well: the hostile ones stay blocked and the ordinary ones stay shown."""

    def verdict(self, item, known):
        return am.check_reply(reply(item["reply"]), item["original"], "rewrite", "client_message", CORPUS["people"], known)

    def test_the_hostile_list_is_all_blocked(self):
        k = am.Known(codes=["ABC"], ids=["ABC-A-004", "ABC-R-017", "ABC-A-003"], people=CORPUS["people"])
        for item in CORPUS["hostile"]:
            self.assertFalse(self.verdict(item, k)["ok"], item["id"])

    def test_the_ordinary_list_is_all_shown(self):
        k = am.Known(codes=["ABC"], ids=["ABC-A-004", "ABC-R-017"], people=CORPUS["people"])
        for item in CORPUS["ordinary"]:
            r = self.verdict(item, k)
            self.assertTrue(r["ok"], (item["id"], r["message"]))

    def test_every_hostile_message_names_a_kind(self):
        for item in CORPUS["hostile"]:
            m = self.verdict(item, None)["message"]
            self.assertTrue(m.startswith("The suggestion added "), (item["id"], m))


class SessionPassesTheSet(unittest.TestCase):
    def test_a_card_is_failed_by_the_projects_own_code(self):
        s = am.AiSession(known=KNOWN)
        card = s.begin("rewrite", WROTE, "client_message", 0, len(WROTE))
        s.deliver(card, reply(WROTE + " See abc a 004."))
        self.assertEqual(card.status, "failed")
        self.assertIn("an item code", card.message)


class TheEmailPlace(unittest.TestCase):
    OWN = ["example.test"]

    def test_offered_for_an_own_domain_only(self):
        self.assertTrue(am.place_offered("email", "sam@example.test", self.OWN))
        self.assertTrue(am.place_offered("email", "Sam@Example.Test", self.OWN))
        self.assertFalse(am.place_offered("email", "dana@partner.test", self.OWN))
        self.assertFalse(am.place_offered("email", "sam@mail.example.test", self.OWN))

    def test_no_address_or_no_own_domain_counts_as_outside(self):
        self.assertFalse(am.place_offered("email", "", self.OWN))
        self.assertFalse(am.place_offered("email", "sam@example.test", []))
        self.assertFalse(am.place_offered("email"))

    def test_every_other_place_is_always_offered(self):
        for place in ("notes", "current", "plain", "client_message"):
            self.assertTrue(am.place_offered(place, "dana@partner.test", self.OWN), place)

    def test_the_menu_is_absent_for_an_outside_address(self):
        self.assertIsNone(am.menu_for("email", "dana@partner.test", self.OWN))
        self.assertEqual(am.menu_for("email", "sam@example.test", self.OWN), am.menu("email"))
        self.assertEqual(am.menu_for("plain"), am.menu("plain"))

    def test_the_rule_is_the_draft_email_rule(self):
        from clark import draft_email as de
        for address in ("sam@example.test", "dana@partner.test", "", "nobody", "a@b@example.test"):
            self.assertEqual(am.place_offered("email", address, self.OWN), not de.is_outside(address, self.OWN), address)

    def test_an_unknown_place_is_refused(self):
        with self.assertRaises(am.Refused):
            am.place_offered("minutes")


if __name__ == "__main__":
    unittest.main()
