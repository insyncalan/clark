"""Row 1293, the rulings (a) to (d) and the Low words, server side: the second change after the first is saved, the duplicate "new item"
warning, and the notes under the answer that say only what happened. Every new sentence is in
src/clark/ask_words.py. Real ask_apply and ask_service on a real store; the provider is a stub (nothing calls a model).

Run: python3 dev/run_tests.py test_ask_rulings_1293
Fictional data only.
"""
import json
import unittest
from unittest import mock

from _demo import USER
from test_ask_apply import Base as ApplyBase
import test_ask_route as route_base
from clark import app_settings, ask, ask_apply, ask_data, ask_words, platform, store as st

TITLE = "Draft the cut-over plan"


class SecondChange(ApplyBase):
    """(a) Two changes to one item built from the same "before": once the first is saved the second is refused, with the ruling's words."""

    def two(self, first, second):
        a = self.planned({"op": "change", "id": self.action, "current_title": TITLE, **first})
        b = self.planned({"op": "change", "id": self.action, "current_title": TITLE, **second})
        return a, b

    def test_apply_the_first_and_the_second_is_marked_stale_with_the_exact_words(self):
        a, b = self.two({"status": "Closed"}, {"status": "Delayed"})
        done = self.applied(a["offer"])
        self.assertEqual(done["stale"], [{"offer": b["offer"], "message": "This one was not saved: status changed when the first change was saved. Ask again to change it."}])

    def test_pressing_apply_on_the_second_writes_nothing_and_says_it_in_the_same_words(self):
        a, b = self.two({"status": "Closed"}, {"status": "Delayed"})
        self.applied(a["offer"])
        before = self.counts()
        status, body = self.ask.apply(b["offer"], "ABC")
        self.assertEqual((status, body["ok"], body["code"]), (409, False, "changed"))
        self.assertEqual(body["message"], ask_words.stale("status"))
        self.assertEqual(self.counts(), before, "nothing was written for the second")
        self.assertEqual(self.s.read("actions", ref=self.action)["status"], "Closed", "the first stays saved")
        self.assertEqual(self.ask.apply(b["offer"], "ABC")[1]["code"], "no_offer", "and it is not offered again")

    def test_the_field_named_is_the_one_the_second_change_was_about_when_the_first_moved_it(self):
        a, b = self.two({"status": "Closed", "priority": "High"}, {"priority": "Low"})
        self.assertEqual(self.applied(a["offer"])["stale"][0]["message"], ask_words.stale("priority"))

    def test_the_field_named_is_from_the_second_changes_own_fields_when_the_first_moved_more(self):
        a, b = self.two({"status": "Closed", "priority": "High"}, {"priority": "Low"})
        self.assertEqual(self.applied(a["offer"])["stale"][0]["message"], ask_words.stale("priority"))
        other = self.demo.action(owner="Kit Moss", description="Order the lanyards")
        c = self.planned({"op": "change", "id": other, "current_title": "Order the lanyards", "priority": "High", "status": "Closed"})
        d = self.planned({"op": "change", "id": other, "current_title": "Order the lanyards", "status": "Delayed"})
        self.assertEqual(self.applied(c["offer"])["stale"][0]["message"], ask_words.stale("status"))

    def test_the_field_named_is_a_plain_word_not_a_column(self):
        self.assertEqual(ask_words.stale("due_date"), "This one was not saved: due date changed when the first change was saved. Ask again to change it.")
        self.assertEqual(ask_words.stale("description"), "This one was not saved: title changed when the first change was saved. Ask again to change it.")
        self.assertEqual(ask_words.field_name("some_field"), "some field")

    def test_a_change_to_another_item_is_not_stale(self):
        other = self.demo.action(owner="Kit Moss", description="Order the lanyards")
        a = self.planned({"op": "change", "id": self.action, "current_title": TITLE, "status": "Closed"})
        b = self.planned({"op": "change", "id": other, "current_title": "Order the lanyards", "status": "Closed"})
        self.assertEqual(self.applied(a["offer"])["stale"], [])
        self.assertEqual(self.applied(b["offer"])["kind"], "actions")

    def test_a_first_change_that_is_not_applied_makes_nothing_stale(self):
        a, b = self.two({"status": "Closed"}, {"status": "Delayed"})
        self.assertEqual(self.applied(b["offer"])["stale"][0]["offer"], a["offer"])      # the other way round: whichever is saved first wins
        self.assertEqual(self.s.read("actions", ref=self.action)["status"], "Delayed")

    def test_a_new_item_has_no_stale_offers(self):
        a = self.planned({"op": "new", "kind": "action", "title": "Book the room"})
        b = self.planned({"op": "new", "kind": "action", "title": "Book the hall"})
        self.assertEqual(self.applied(a["offer"])["stale"], [])
        self.assertEqual(self.applied(b["offer"])["after"]["description"], "Book the hall")


class Duplicate(ApplyBase):
    """(b) A new item with the same kind, project and title (capitals and extra spaces ignored), and the same owner (blank matches any)."""

    def said(self, change):
        return self.planned(change).get("duplicate")

    def test_the_same_title_in_other_capitals_and_spaces_warns_with_the_exact_words(self):
        got = self.said({"op": "new", "kind": "action", "title": "  DRAFT  the Cut-Over   plan ", "owner": "Sam Lee"})
        self.assertEqual(got, 'There is already an action called "DRAFT the Cut-Over plan". Apply to add another.')

    def test_a_blank_owner_on_either_side_matches_any_owner(self):
        self.assertIsNotNone(self.said({"op": "new", "kind": "action", "title": TITLE}))                       # new item with no owner, existing has one
        self.demo.action(owner="", description="Ring the supplier")
        self.assertIsNotNone(self.said({"op": "new", "kind": "action", "title": "Ring the supplier", "owner": "Kit Moss"}))

    def test_two_different_owners_are_not_a_duplicate(self):
        self.assertIsNone(self.said({"op": "new", "kind": "action", "title": TITLE, "owner": "Kit Moss"}))

    def test_the_same_owner_in_other_capitals_is_a_duplicate(self):
        self.assertIsNotNone(self.said({"op": "new", "kind": "action", "title": TITLE, "owner": "sam  lee"}))

    def test_another_title_or_another_kind_or_another_project_is_not_a_duplicate(self):
        self.assertIsNone(self.said({"op": "new", "kind": "action", "title": "Draft the cut-over plans"}))
        self.assertIsNone(self.said({"op": "new", "kind": "decision", "title": TITLE}))
        self.assertIsNone(self.said({"op": "new", "kind": "risk", "title": TITLE}))
        self.assertIsNone(self.said({"op": "new", "kind": "action", "title": "Order the badges"}), "that title is in another project")

    def test_an_archived_item_is_not_a_duplicate(self):
        with self.s.step("dashboard", USER) as st:
            st.archive("actions", self.action)
        self.assertIsNone(self.said({"op": "new", "kind": "action", "title": TITLE}))

    def test_the_warning_never_blocks_and_apply_adds_another(self):
        plan = self.planned({"op": "new", "kind": "action", "title": TITLE, "owner": "Sam Lee"})
        self.assertTrue(plan["ok"] and plan["duplicate"] and plan["offer"])
        self.assertEqual(self.applied(plan["offer"])["after"]["description"], TITLE)
        self.assertEqual(len([r for r in self.s.read("actions", "ABC") if r["description"] == TITLE]), 2)

    def test_a_card_that_is_not_a_duplicate_has_no_duplicate_key(self):
        self.assertNotIn("duplicate", self.planned({"op": "new", "kind": "action", "title": "A brand new thing"}))
        self.assertNotIn("duplicate", self.planned({"op": "change", "id": self.action, "current_title": TITLE, "status": "Closed"}))

    def test_a_new_item_the_same_reply_already_offered_is_warned_on_the_second_only(self):
        new = {"op": "new", "kind": "risk", "title": "Supplier may slip", "owner": "Kit Moss"}
        again = {"op": "new", "kind": "risk", "title": "supplier  MAY slip"}
        status, body = self.ask.plan_all("ABC", [new, again, dict(new, kind="issue")])
        first, second, third = body["plans"]
        self.assertNotIn("duplicate", first)
        self.assertEqual(second["duplicate"], 'There is already a risk called "supplier MAY slip". Apply to add another.')
        self.assertNotIn("duplicate", third, "an issue is not a risk")

    def test_a_stored_risk_is_not_a_duplicate_of_an_issue_with_the_same_title(self):
        with self.s.step("dashboard", USER) as st:
            st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier may slip", "raised": "2026-10-01", "source": "demo"})
        self.assertIsNone(self.said({"op": "new", "kind": "issue", "title": "Supplier may slip"}))
        self.assertIsNotNone(self.said({"op": "new", "kind": "risk", "title": "Supplier may slip"}))

    def test_two_new_items_of_one_reply_with_different_titles_are_not_duplicates(self):
        one = {"op": "new", "kind": "action", "title": "Book the room"}
        two = {"op": "new", "kind": "action", "title": "Book the hall"}
        self.assertNotIn("duplicate", self.ask.plan_all("ABC", [one, two])[1]["plans"][1])

    def test_a_change_earlier_in_the_reply_is_not_a_new_item_to_match(self):
        change = {"op": "change", "id": self.action, "current_title": TITLE, "title": "Brand new name"}
        new = {"op": "new", "kind": "action", "title": "Brand new name"}
        plans = self.ask.plan_all("ABC", [change, new])[1]["plans"]
        self.assertTrue(plans[0]["ok"], plans[0])
        self.assertNotIn("duplicate", plans[1])

    def test_the_kind_word_takes_a_or_an(self):
        for kind, article in (("action", "an"), ("issue", "an"), ("assumption", "an"), ("risk", "a"), ("dependency", "a"), ("decision", "a"), ("milestone", "a")):
            self.assertEqual(ask_words.duplicate(kind, "T"), f'There is already {article} {kind} called "T". Apply to add another.')

    def test_a_refused_item_has_no_warning(self):
        body = self.ask.plan("ABC", {"op": "new", "kind": "action", "title": TITLE, "owner": "Sam Lee", "bogus": "x"})[1]
        self.assertFalse(body["ok"])
        self.assertNotIn("duplicate", body)


class UsedLine(route_base.Base):
    """The Low words: in the notes under the answer, only when it happened."""

    def notes(self, **kw):
        status, got = self.question(**kw)
        self.assertEqual((status, got["ok"]), (200, True), got)
        return got["notes"]

    def planted(self, passages, cut=0):
        store = st.open_store(self.db, onedrive_roots=[])
        self.addCleanup(store.close)
        real = ask_data.project_data(store, route_base.CODE, "How is the plan?", 40000)
        data = ask_data.ProjectData(tuple(passages), real.facts, 0, cut=cut)
        return mock.patch.object(ask_data, "project_data", return_value=data)

    def test_a_plain_answer_has_none_of_the_new_lines(self):
        new = {ask_words.LONG_ROWS, ask_words.REPLY_CUT, ask_words.SECRET_LEFT_OUT}
        self.assertFalse(new & set(self.notes()))
        self.assertFalse([n for n in self.notes() if n.startswith("Sent about")])

    def test_a_cut_row_says_so(self):
        with self.planted([ask.Passage("Plan", "A short line.")], cut=2):
            self.assertIn("Some long rows were cut at 4,000 characters.", self.notes())

    def test_a_long_row_is_counted_by_project_data_only_when_it_is_cut_and_not_a_secret(self):
        self.assertEqual(ask_data.long_rows(["x" * 4000, "y" * 4001, "z" * 9000]), 2)
        self.assertEqual(ask_data.long_rows(["short"]), 0)
        self.assertEqual(ask_data.long_rows(["password: " + "hunter22 " + "x" * 5000]), 0)

    def test_project_data_counts_a_long_row_of_a_kind_and_a_long_project_line(self):
        store = st.open_store(self.db, onedrive_roots=[])
        self.addCleanup(store.close)
        self.assertEqual(ask_data.project_data(store, route_base.CODE, "plan", 40000).cut, 0)
        with store.step("dashboard", USER) as step:
            step.create("actions", {"project": route_base.CODE, "description": "Long " + "x" * 5000, "raised": "2026-10-01", "source": "demo"})
        self.assertEqual(ask_data.project_data(store, route_base.CODE, "plan", 40000).cut, 1)

    def test_a_long_project_line_is_counted(self):
        with mock.patch.object(ask_data, "project_lines", return_value=["Summary: " + "y" * 5000]):
            store = st.open_store(self.db, onedrive_roots=[])
            self.addCleanup(store.close)
            self.assertEqual(ask_data.project_data(store, route_base.CODE, "plan", 40000).cut, 1)

    def test_a_reply_of_sixty_thousand_and_one_is_cut(self):
        self.provider.reply = "a" * 60001
        self.assertIn(ask_words.REPLY_CUT, self.notes())

    def test_a_reply_over_sixty_thousand_is_cut_and_says_so(self):
        self.provider.reply = "a " * 31000 + "\nCITE: P1"
        self.assertIn("The answer was cut at 60,000 characters.", self.notes())

    def test_a_reply_of_exactly_sixty_thousand_is_not(self):
        self.provider.reply = "a" * 60000
        self.assertNotIn(ask_words.REPLY_CUT, self.notes())

    def test_size_sent_is_said_above_twenty_thousand_rounded_to_the_thousand(self):
        big = [ask.Passage(f"Part {i}", f"line {i} " * 480) for i in range(6)]
        with self.planted(big):
            notes = self.notes()
        (sent,) = self.provider.sent
        said = [n for n in notes if n.startswith("Sent about")]
        self.assertGreater(len(sent), 20000)
        self.assertEqual(said, [f"Sent about {(len(sent) + 500) // 1000 * 1000:,} characters."])
        self.assertRegex(said[0], r"^Sent about \d{2},000 characters\.$")

    def test_a_small_request_says_nothing_about_size(self):
        self.assertEqual([n for n in self.notes() if n.startswith("Sent")], [])

    def test_the_size_line_by_the_numbers(self):
        for n, want in ((0, ""), (20000, ""), (20001, "Sent about 20,000 characters."), (20499, "Sent about 20,000 characters."),
                        (20500, "Sent about 21,000 characters."), (45123, "Sent about 45,000 characters."), (70000, "Sent about 70,000 characters.")):
            self.assertEqual(ask_words.sent_about(n), want, n)
        for bad in (None, "30000", True, -5, 20000.5):
            self.assertEqual(ask_words.sent_about(bad), "")

    def test_a_passage_left_out_as_a_key_says_one_line_and_never_what_matched(self):
        key = "sk-" + "ant-api03-" + "A1b2C3d4E5f6G7h8I9j0" + "-xyz"
        with self.planted([ask.Passage("Planted", "Use " + key + " for the feed"), ask.Passage("Plan", "A clean line.")]):
            notes = self.notes()
        self.assertIn("One passage was left out because it looked like a password or key.", notes)
        self.assertNotIn(key, repr(notes))
        self.assertEqual(ask.secret_note(0), "")


class Docker(route_base.Base):
    """Docker: ask is refused in the ruling's words, in the status (panel) and in Settings' switch answer."""

    def in_docker(self):
        patch = mock.patch.object(platform, "container_mode", return_value=True)
        patch.start()
        self.addCleanup(patch.stop)

    def test_outside_docker_nothing_says_docker(self):
        status, got = self.s.api("GET", "/api/ask/status")
        self.assertNotIn("docker", got)
        self.assertNotIn("docker", app_settings.AppSettings(self.db, [], by_user=lambda: "tester").read_ask()[1])

    def test_the_status_says_it_in_the_exact_words(self):
        self.in_docker()
        status, got = self.s.api("GET", "/api/ask/status")
        self.assertEqual((status, got["connected"], got["docker"], got["why"]), (200, False, True, "Ask clark is not available in the Docker version of clark."))

    def test_a_question_is_refused_and_nothing_is_read_or_sent(self):
        self.in_docker()
        status, got = self.question()
        self.assertEqual((status, got["ok"], got["code"], got["message"]), (409, False, "docker", "Ask clark is not available in the Docker version of clark."))
        self.assertEqual(self.provider.sent, [])

    def test_settings_gets_the_line_with_the_switch_answer(self):
        self.in_docker()
        status, got = app_settings.AppSettings(self.db, [], by_user=lambda: "tester").read_ask()
        self.assertEqual((status, got["docker"], got["docker_line"]), (200, True, ask_words.DOCKER))


if __name__ == "__main__":
    unittest.main()
