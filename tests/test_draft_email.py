"""#50: Draft email's wording and rules, plain code with no model. Fixed clock, fictional names."""
import re
from pathlib import Path
import unittest

import _paths  # noqa: F401
from clark import draft_email as de
from clark import look

NOW = "2026-10-13 09:00"                     # a Tuesday
TODAY = "2026-10-13"
OWN = ["example.test"]
INSIDE, OUTSIDE = "sam@example.test", "dana@partner.test"


def item(id_, text, due=None, **kw):
    base = {"id": id_, "project": "ABC", "kind": "actions", "text": text, "due": due, "priority": "Medium",
            "owner": "Dana Hart", "status": "Open", "client_visible": True}
    base.update(kw)
    return base


LATE = item("ABC-A-001", "Share the UAT plan", "2026-10-09", priority="High", update="Plan in draft")
SOON = item("ABC-A-002", "Confirm the test dates", "2026-10-15")
LATE2 = item("ABC-A-006", "Send the access list", "2026-10-08")
FAR = item("ABC-A-003", "Order the licences", "2026-11-30")
NODATE = item("ABC-A-004", "Tidy the wiki")
INTERNAL = item("ABC-A-005", "Check the vendor margin", "2026-10-20", client_visible=False)
RISK = item("ABC-R-001", "Test environment may slip", "2026-10-16", kind="raid", type="Issue", response="")
DEC = item("ABC-D-001", "Which use cases go into Phase 2", "2026-10-15", kind="decisions", owner="Chris Dunn")
NAMES = {"ABC": "Example Programme"}


def both(n, last="2026-10-12", ids=("ABC-A-001", "ABC-A-006")):
    """The same chase history for each of the items."""
    return {i: {"n": n, "last": last} for i in ids}


def build(**kw):
    o = {"mode": "update_request", "items": [LATE, SOON], "name": "Dana Hart", "email": INSIDE, "own_domains": OWN, "from": "Sam",
         "now": NOW, "project_names": NAMES}
    o.update(kw)
    return de.build(o)


class Greeting(unittest.TestCase):
    def test_by_the_time_of_day(self):
        self.assertEqual(de.greeting(9, "Dana"), "Good morning, Dana,")
        self.assertEqual(de.greeting(11, ""), "Good morning,")
        self.assertEqual(de.greeting(12, "Dana"), "Good afternoon, Dana,")
        self.assertEqual(de.greeting(13, "Dana"), "Good afternoon, Dana,")
        self.assertEqual(de.greeting(17, "Dana"), "Good afternoon, Dana,")
        self.assertEqual(de.greeting(18, "Dana"), "Good evening, Dana,")
        self.assertEqual(de.greeting(19, "Dana"), "Good evening, Dana,")

    def test_the_email_uses_the_clock_and_the_first_name(self):
        for now, word in (("2026-10-13 09:00", "morning"), ("2026-10-13 13:00", "afternoon"), ("2026-10-13 19:00", "evening")):
            self.assertTrue(build(now=now)["text"].startswith(f"Good {word}, Dana,\n"), now)


class Subject(unittest.TestCase):
    def test_starts_with_the_project_name(self):
        self.assertEqual(build(items=[LATE])["subject"], "Example Programme · ABC-A-001 · Update request: Share the UAT plan")
        self.assertEqual(build()["subject"], "Example Programme · Update request: 2 open items (1 overdue)")
        self.assertEqual(build(items=[SOON, FAR])["subject"], "Example Programme · Update request: 2 open items")

    def test_chase_and_decision_subjects_step_up(self):
        self.assertEqual(build(mode="chase", items=[LATE])["subject"],
                         "Example Programme · ABC-A-001 · Reminder: Share the UAT plan")
        two = {"ABC-A-001": {"n": 2, "last": "2026-10-08"}}
        self.assertEqual(build(mode="chase", items=[LATE], chased=two)["subject"],
                         "Example Programme · ABC-A-001 · Reply needed: Share the UAT plan")
        self.assertEqual(build(mode="decision", items=[DEC])["subject"],
                         "Example Programme · Decision needed: Which use cases go into Phase 2")

    def test_nothing_ticked_has_no_count(self):
        self.assertEqual(build(mode="chase", items=[LATE], picked=[])["subject"], "Reminder")


class Wording(unittest.TestCase):
    def test_update_request(self):
        t = build(reply_by="2026-10-15")["text"]
        self.assertIn(de.OPEN, t)
        self.assertIn("Could you let me know where each one stands", t)
        self.assertIn("It would be helpful to hear back by Thursday 15-10-2026.", t)
        self.assertTrue(t.endswith("Kind regards,\nSam"))
        self.assertNotIn("decision we need", t)
        self.assertIn(de.DECIDE, build(items=[LATE, DEC])["text"])

    def test_chase_steps_up_with_the_count(self):
        first = build(mode="chase", items=[LATE, LATE2])["text"]
        self.assertIn("A quick reminder about the items below, which are now past their due dates.", first)
        c = both(1, "2026-10-08")
        self.assertIn("I'm following up on my earlier note of 08-10-2026 about the items below, which are still overdue.",
                      build(mode="chase", items=[LATE, LATE2], chased=c)["text"])
        c = both(3, "2026-10-08")
        d = build(mode="chase", items=[LATE, LATE2], chased=c)
        self.assertEqual(d["tone"], 2)
        self.assertIn("I have chased them 3 times, most recently on 08-10-2026.", d["text"])
        self.assertNotIn("holding up", d["text"])
        self.assertIn("Please reply with a firm date for each", d["text"])

    def test_a_chase_of_one_item_is_in_the_singular(self):
        t = build(mode="chase", items=[LATE])["text"]
        self.assertIn("about the item below, which is now past its due date.", t)
        self.assertIn("where it stands", t)

    def test_decision_request(self):
        d = build(mode="decision", items=[DEC], name="Chris Dunn", reply_by="2026-10-15", unblocks="the Phase 2 proposal")
        self.assertIn("A quick note on the decision below, which is needed for the Phase 2 proposal.", d["text"])
        self.assertIn("by Thursday 15-10-2026?", d["text"])
        self.assertTrue(d["text"].endswith("Thank you,\nSam"))
        c = {"ABC-D-001": {"n": 2, "last": "2026-10-08"}}
        f = build(mode="decision", items=[DEC], chased=c, unblocks="the Phase 2 proposal")
        self.assertIn("I have asked for this decision twice, most recently on 08-10-2026. It is holding up the Phase 2 proposal.", f["text"])
        self.assertIn("as soon as you can?", f["text"])

    def test_the_opening_can_be_the_users_own(self):
        self.assertIn("Quick one.", build(cover="Quick one.")["text"])
        self.assertNotIn(de.OPEN, build(cover="Quick one.")["text"])

    def test_no_model_words_or_internal_jargon(self):
        for mode, items in (("update_request", [LATE, RISK]), ("chase", [LATE]), ("decision", [DEC])):
            t = build(mode=mode, items=items)["text"].lower()
            for w in ("tracker", "sweep", "proposal", "vault", "apply"):
                self.assertNotIn(w, t.replace("the phase 2 proposal", ""))


class PlainWordsHigh(unittest.TestCase):
    """The plain-words review: the two high-priority rows."""

    def test_the_firmer_decision_subject_does_not_invent_a_deadline(self):
        c = {"ABC-D-001": {"n": 2, "last": "2026-10-08"}}
        dated = build(mode="decision", items=[DEC], chased=c, reply_by="2026-10-15")["subject"]
        self.assertEqual(dated, "Example Programme · Decision needed: reply by Thursday 15-10-2026")
        undated = build(mode="decision", items=[DEC], chased=c)["subject"]
        self.assertEqual(undated, "Example Programme · Decision still needed")
        self.assertNotIn("this week", dated + undated)

    def test_the_firmer_chase_states_only_what_the_data_says(self):
        c = both(2)
        many = build(mode="chase", items=[LATE, LATE2], chased=c)["text"]
        self.assertIn("These items are now well overdue, the longest by 5 days. I have chased them twice, most recently on 12-10-2026.", many)
        one = build(mode="chase", items=[LATE], chased=c)["text"]
        self.assertIn("This item is now 4 days overdue. I have chased it twice, most recently on 12-10-2026.", one)
        for t in (many, one):
            self.assertNotIn("holding up", t)
            self.assertNotIn("other work", t)

    def test_a_reason_appears_only_when_the_sender_types_one(self):
        c = {"ABC-A-001": {"n": 2, "last": "2026-10-12"}}
        t = build(mode="chase", items=[LATE], chased=c, unblocks="the UAT start")["text"]
        self.assertIn("It is holding up the UAT start.", t)
        d = {"ABC-D-001": {"n": 2, "last": "2026-10-08"}}
        none = build(mode="decision", items=[DEC], chased=d)["text"]
        self.assertIn("I have asked for this decision twice, most recently on 08-10-2026.", none)
        self.assertNotIn("holding up", none)
        self.assertIn("It is holding up the Phase 2 proposal.",
                      build(mode="decision", items=[DEC], chased=d, unblocks="the Phase 2 proposal")["text"])


class PlainWordsMedium(unittest.TestCase):
    """The plain-words review: the ten medium-priority rows."""

    def test_no_filler_and_no_moment_that_clashes_with_the_reply_by_date(self):
        t = build(reply_by="2026-10-15")["text"]
        self.assertIn("I'm pulling together where things stand on the items below.", t)
        self.assertNotIn("hope you're well", t)
        self.assertNotIn("when you have a moment", t)
        for mode in ("chase", "decision"):
            self.assertNotIn("hope you're well", build(mode=mode, items=[LATE if mode == "chase" else DEC])["text"])

    def test_the_firmer_subject_says_reply_needed_once(self):
        s = build(mode="chase", items=[LATE, LATE2], chased=both(2))["subject"]
        self.assertEqual(s, "Example Programme · Reply needed: 2 overdue items")
        self.assertEqual(s.lower().count("overdue"), 1)

    def test_a_single_item_subject_carries_its_title(self):
        self.assertEqual(build(mode="chase", items=[SOON])["subject"], "Example Programme · ABC-A-002 · Reminder: Confirm the test dates")
        self.assertEqual(build(items=[FAR])["subject"], "Example Programme · ABC-A-003 · Update request: Order the licences")

    def test_a_decision_without_a_reason_has_no_soon_or_next_steps(self):
        t = build(mode="decision", items=[DEC], reply_by="2026-10-15")["text"]
        self.assertIn("A quick note on the decision below.", t)
        self.assertIn("Could you let me have the decision, or tell me what you need to make it, by Thursday 15-10-2026?", t)
        for w in ("soon", "next steps"):
            self.assertNotIn(w, t)
        second = build(mode="decision", items=[DEC], chased={"ABC-D-001": {"n": 1, "last": "2026-10-08"}})["text"]
        self.assertIn("I'm following up on my earlier note of 08-10-2026 about the decision below.", second)
        self.assertNotIn("next steps", second)

    def test_no_reply_by_date_says_as_soon_as_you_can(self):
        t = build(mode="decision", items=[DEC])["text"]
        self.assertIn("what you need to make it, as soon as you can?", t)
        self.assertNotIn("needed-by", t)

    def test_unknown_kinds_say_what_to_choose(self):
        msg = "That kind of email isn't available. Choose Update request, Chase or Decision."
        with self.assertRaises(ValueError) as a:
            build(mode="polish")
        self.assertEqual(str(a.exception), msg)
        with self.assertRaises(ValueError) as b:
            de.sent_entry(["ABC-A-001"], "polish", TODAY)
        self.assertEqual(str(b.exception), msg)

    def test_nothing_ticked_on_i_sent_it_says_what_to_do(self):
        with self.assertRaises(ValueError) as a:
            de.sent_entry([], "chase", TODAY)
        self.assertEqual(str(a.exception), "Tick at least one item before you press I sent it.")

    def test_an_empty_selection_blocks_copying(self):
        d = build(picked=[])
        msg = "No items are ticked. Tick at least one to draft the email."
        self.assertFalse(d["ready"])
        self.assertEqual(d["problems"], [msg])
        with self.assertRaises(ValueError) as a:
            de.clipboard(d)
        self.assertEqual(str(a.exception), msg)
        self.assertFalse(de.mailto_offered(d))
        self.assertTrue(build()["ready"])
        self.assertEqual(build()["problems"], [])

    def test_a_missing_sender_name_asks_for_it(self):
        msg = "Add your name in Settings › Profile so it signs the email."
        for blank in ("", "   "):
            d = build(**{"from": blank})
            self.assertEqual(d["problems"], [msg])
            self.assertFalse(d["ready"])
            with self.assertRaises(ValueError):
                de.clipboard(d)


class PerItem(unittest.TestCase):
    """The second review: what a chase says is true of each ticked item, not of the highest count or latest date."""

    def test_different_counts_say_only_that_some_were_chased(self):
        c = {"ABC-A-001": {"n": 2, "last": "2026-10-12"}}                      # the other item was never chased
        t = build(mode="chase", items=[LATE, LATE2], chased=c)["text"]
        self.assertIn("I have chased some of them before, most recently on 12-10-2026.", t)
        self.assertNotIn("twice", t)
        self.assertNotIn("chased them", t)
        c = {"ABC-A-001": {"n": 1, "last": "2026-10-08"}, "ABC-A-006": {"n": 1, "last": "2026-10-10"}}   # same count, other days
        t = build(mode="chase", items=[LATE, LATE2], chased=c)["text"]
        self.assertIn("I'm following up on the items below, which are still overdue. I have chased some of them before, most recently on 10-10-2026.", t)
        self.assertNotIn("earlier note of", t)

    def test_the_same_history_is_stated_as_it_is(self):
        t = build(mode="chase", items=[LATE, LATE2], chased=both(3))["text"]
        self.assertIn("I have chased them 3 times, most recently on 12-10-2026.", t)

    def test_an_item_not_yet_due_is_never_called_overdue(self):
        for tone, c in ((0, None), (1, both(1, "2026-10-08", ("ABC-A-002",))), (2, both(2, "2026-10-08", ("ABC-A-002",)))):
            t = build(mode="chase", items=[SOON], chased=c)["text"]
            opening = t.split("\n\n")[1]
            for bad in ("overdue", "0 days", "past its due", "past their due"):
                self.assertNotIn(bad, opening, (tone, opening))
        self.assertIn("A quick reminder about the item below, which is due on 15-10-2026.", build(mode="chase", items=[SOON])["text"])
        self.assertIn("This item is due on 15-10-2026. I have chased it twice, most recently on 08-10-2026.",
                      build(mode="chase", items=[SOON], chased=both(2, "2026-10-08", ("ABC-A-002",)))["text"])
        self.assertIn("I'm writing again about the items below.",
                      build(mode="chase", items=[SOON, FAR], chased=both(2, "2026-10-08", ("ABC-A-002", "ABC-A-003")))["text"])

    def test_a_mix_of_overdue_and_not_yet_due_says_some(self):
        self.assertIn("A quick reminder about the items below, some of which are past their due dates.",
                      build(mode="chase", items=[LATE, SOON])["text"])
        t = build(mode="chase", items=[LATE, SOON], chased=both(2, "2026-10-12", ("ABC-A-001", "ABC-A-002")))["text"]
        self.assertIn("Some of these items are now well overdue, the longest by 4 days. I have chased them twice, most recently on 12-10-2026.", t)
        self.assertNotIn("These items are now well overdue", t)
        t = build(mode="chase", items=[LATE, SOON], chased=both(1, "2026-10-08", ("ABC-A-001", "ABC-A-002")))["text"]
        self.assertIn("about the items below, some of which are still overdue.", t)

    def test_the_subject_counts_only_the_overdue_ones(self):
        self.assertEqual(build(mode="chase", items=[LATE, SOON])["subject"], "Example Programme · Reminder: 2 items (1 overdue)")
        self.assertEqual(build(mode="chase", items=[SOON, FAR])["subject"], "Example Programme · Reminder: 2 items")
        self.assertEqual(build(mode="chase", items=[LATE, LATE2])["subject"], "Example Programme · Reminder: 2 overdue items")

    def test_several_decisions_with_different_histories(self):
        dec2 = item("ABC-D-002", "Pick the vendor", "2026-10-15", kind="decisions", owner="Chris Dunn")
        c = {"ABC-D-001": {"n": 2, "last": "2026-10-08"}}
        t = build(mode="decision", items=[DEC, dec2], chased=c)["text"]
        self.assertIn("I have asked for some of these decisions before, most recently on 08-10-2026.", t)
        self.assertNotIn("twice", t)
        c = {"ABC-D-001": {"n": 1, "last": "2026-10-08"}}
        t = build(mode="decision", items=[DEC, dec2], chased=c)["text"]
        self.assertIn("I'm following up on the decision below. I have asked for some of these decisions before, most recently on 08-10-2026.", t)

    def test_the_second_decision_subject_has_one_colon(self):
        c = {"ABC-D-001": {"n": 1, "last": "2026-10-08"}}
        self.assertEqual(build(mode="decision", items=[DEC], chased=c)["subject"],
                         "Example Programme · Decision needed (second reminder): Which use cases go into Phase 2")
        dec2 = item("ABC-D-002", "Pick the vendor", "2026-10-15", kind="decisions")
        self.assertEqual(build(mode="decision", items=[DEC, dec2], chased=c)["subject"],
                         "Example Programme · Decision needed (second reminder)")
        for sub in (build(mode="decision", items=[DEC], chased=c)["subject"],):
            self.assertEqual(sub.split(" · ", 1)[1].count(":"), 1)

    def test_the_sender_signs_with_the_first_word_of_the_name(self):
        t = build(**{"from": "Sam Rowan"})["text"]
        self.assertTrue(t.endswith("Kind regards,\nSam"))
        self.assertNotIn("Rowan", t)


class HeldWords(unittest.TestCase):
    """Look-alike held words, and the empty states."""
    SPELLINGS = ("confi\u00addential", "con\u200bfidential", "re\u2060stricted", "CONFIDENTIAL", "\u0441onfidential",
                 "confid\u0435ntial", "restr\u0456cted", "\uff43onfidential", "con\u200dfi\ufeffdential")

    def test_a_hidden_or_look_alike_spelling_is_still_held_back(self):
        for word in self.SPELLINGS:
            self.assertTrue(de.barred(item("X-1", f"Budget notes ({word})")), word)
            self.assertTrue(de.barred(item("X-1", "Fine", response=f"see {word}")), word)
            self.assertTrue(de.barred(item("X-1", "Fine", **{de.LATEST: f"this is {word}"})), word)
        self.assertFalse(de.barred(item("X-1", "Share the plan")))

    def test_the_items_handed_back_carry_only_the_words_the_module_reads(self):
        rich = dict(LATE, internal_note="Do not tell the client", source="mail 12-10", reasoning="because", extra=1)
        d = build(items=[rich], mode="chase")
        self.assertEqual(sorted(d["items"][0]), sorted(k for k in LATE if k in de.ITEM_KEYS))
        for key in ("internal_note", "source", "reasoning", "extra"):
            self.assertNotIn(key, d["items"][0])
        self.assertNotIn("Do not tell", repr(d))

    def test_no_open_items_is_its_own_message(self):
        d = build(items=[])
        self.assertEqual(d["problems"], ["There are no open items to put in an email."])
        held = build(items=[item("X-1", "Budget (confidential)")])
        self.assertEqual(held["problems"], ["There are no open items to put in an email."])
        self.assertEqual(build(picked=[])["problems"], ["No items are ticked. Tick at least one to draft the email."])


class PlainWordsLow(unittest.TestCase):
    """The plain-words review: the five low-priority rows."""

    def test_thank_you_is_the_same_in_every_tone(self):
        for c in (None, {"ABC-A-001": {"n": 1, "last": "2026-10-08"}}, {"ABC-A-001": {"n": 3, "last": "2026-10-08"}}):
            t = build(mode="chase", items=[LATE, SOON], chased=c)["text"]
            self.assertIn(" Thank you.\n", t)
            self.assertNotIn("very much", t)

    def test_the_firmer_ask_for_several_items_says_any_of_them(self):
        c = {"ABC-A-001": {"n": 3, "last": "2026-10-08"}}
        many = build(mode="chase", items=[LATE, SOON], chased=c)["text"]
        self.assertIn("tell me what is blocking any of them, so that we can resolve it together.", many)
        one = build(mode="chase", items=[LATE], chased=c)["text"]
        self.assertIn("tell me what is blocking it, so that we can resolve it together.", one)

    def test_a_long_subject_is_cut_at_a_word_about_60_characters(self):
        long_text = "Agree which of the nine regional use cases go into the second phase of the programme"
        d = item("ABC-D-009", long_text, "2026-10-15", kind="decisions")
        sub = build(mode="decision", items=[d])["subject"]
        self.assertEqual(sub, "Example Programme · Decision needed: Agree which of the nine regional use cases go into the…")
        self.assertLessEqual(len(sub.split(": ", 1)[1]), 61)
        act = item("ABC-A-009", long_text, "2026-10-09")
        self.assertTrue(build(mode="chase", items=[act])["subject"].endswith("regional use cases go into the…"))
        self.assertEqual(de.short("Short title"), "Short title")
        self.assertEqual(de.short("x" * 70), "x" * 59 + "…")

    def test_the_table_headings_are_id_item_due_priority(self):
        h = build()["html"]
        self.assertEqual(re.findall(r"<th [^>]*>([^<]*)</th>", h)[:4], ["ID", "Item", "Due", "Priority"])


class ToneNames(unittest.TestCase):
    def test_the_tone_steps_read_first_chase_second_chase_firmer_chase(self):
        """#208(c): a person sees First chase, Second chase, Firmer chase; the prototype's tone buttons say the same."""
        self.assertEqual(de.TONE_NAMES, ("First chase", "Second chase", "Firmer chase"))
        proto = (Path(de.__file__).resolve().parents[2] / "system" / "prototype" / "peek.js").read_text(encoding="utf-8")
        for name in de.TONE_NAMES:
            self.assertIn(name, proto)
        self.assertNotIn("'First']", proto)


class Dates(unittest.TestCase):
    def test_dates_read_one_shape_only(self):
        self.assertEqual(de.shown("2026-10-29"), "29-10-2026")
        self.assertEqual(de.weekday_date("2026-10-29"), "Thursday 29-10-2026")
        self.assertEqual(de.shown("0999-01-02"), "02-01-0999")
        for text in ("20261029", "2026-W44-3", "2026-10-29T10:00", "2026-10-29 ", "2026-10-29\n", "2026-13-01", "2026-02-30",
                     "\u0662\u0660\u0662\u0666-\u0661\u0660-\u0662\u0669", "", "12345"):
            with self.subTest(text=text):
                self.assertEqual(de.shown(text), text)
                self.assertEqual(de.weekday_date(text), "")
        self.assertEqual(de.shown(None), "")
        self.assertEqual(de.weekday_date(None), "")
        self.assertEqual(de.shown(12345), "12345")

    def test_overdue_and_due_soon_in_words_and_colour(self):
        d = de.due_info("2026-10-09", TODAY)
        self.assertEqual((d["date"], d["words"], d["level"]), ("09-10-2026", "4 days overdue", "over"))
        self.assertEqual(de.due_info("2026-10-12", TODAY)["words"], "1 day overdue")
        self.assertEqual(de.due_info(TODAY, TODAY)["words"], "due today")
        self.assertEqual(de.due_info("2026-10-14", TODAY)["words"], "due tomorrow")
        self.assertEqual(de.due_info("2026-10-19", TODAY)["words"], "due in 6 days")
        self.assertEqual(de.due_info("2026-10-20", TODAY)["words"], "due in 7 days")
        self.assertEqual(de.due_info("2026-10-21", TODAY), {"date": "21-10-2026", "words": "", "level": ""})
        self.assertEqual(de.due_info("2026-10-15", TODAY, "decisions")["words"], "needed in 2 days")
        self.assertEqual(de.due_info(None, TODAY)["date"], "No date")

    def test_the_email_shows_dates_as_dd_mm_yyyy(self):
        d = build(items=[LATE, SOON, FAR])
        self.assertIn("09-10-2026 (4 days overdue)", d["text"])
        self.assertIn("15-10-2026 (due in 2 days)", d["text"])
        self.assertIn("30-11-2026", d["text"])
        self.assertNotRegex(d["text"] + d["html"], r"\d{4}-\d{2}-\d{2}")

    def test_html_colours_follow_the_state(self):
        h = build(items=[LATE, SOON, FAR])["html"]
        self.assertIn(f'color:{de.COLOURS["red"]};', h)
        self.assertIn(f'color:{de.COLOURS["amber"]};', h)
        self.assertIn("4 days overdue", h)
        self.assertIn("font-weight:bold;", h)

    def test_overdue_sorts_first_then_soonest_then_undated(self):
        d = build(items=[NODATE, FAR, SOON, LATE])
        self.assertEqual(d["ids"], ["ABC-A-001", "ABC-A-002", "ABC-A-003", "ABC-A-004"])

    def test_reply_by_skips_the_weekend(self):
        self.assertEqual(de.working_days_ahead("2026-10-16", 2), "2026-10-20")      # Friday + 2 = Tuesday
        self.assertEqual(de.working_days_ahead("2026-10-13", 2), "2026-10-15")


class InlineStyles(unittest.TestCase):
    def test_every_element_is_styled_and_nothing_else_is_used(self):
        h = build(mode="update_request", items=[LATE, RISK, DEC, INTERNAL], email=OUTSIDE, include_update=True)["html"]
        for banned in ("class=", "<style", "<span", "<script", "var(", "<img", "id=", "data-", "<!--", "@import", "<font",
                       "display:flex"):
            self.assertNotIn(banned, h)
        tags = re.findall(r"<(p|div|b|i|br|table|tr|th|td)\b([^>]*)>", h)
        self.assertTrue(tags)
        for name, attrs in tags:
            if name not in ("br",):
                self.assertIn("style=", attrs, name)
        self.assertIn('cellpadding="6"', h)
        self.assertIn("border-bottom:1px solid", h)
        self.assertIn(f"font-family:{look.email_font_family()};font-size:11pt;", h)
        self.assertEqual(look.email_font_family(), "Calibri,Arial,sans-serif", "Outlook's Word engine: Calibri, then Arial")
        self.assertEqual(de.COLOURS["ink"], "#" + look.colour("text"), "the ink is the look's text colour")
        self.assertIn(f"color:{de.COLOURS['ink']};", h)
        self.assertIn(f"background:{de.COLOURS['white']}", h)

    def test_text_is_escaped(self):
        h = build(items=[item("ABC-A-009", "Fix <b>this</b> & that", "2026-10-20")])["html"]
        self.assertIn("Fix &lt;b&gt;this&lt;/b&gt; &amp; that", h)

    def test_the_text_colours_pass_4_5_to_1_on_white(self):
        def lum(hexcol):
            c = [int(hexcol[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
            return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
        for name in ("red", "amber", "ink", "muted"):
            ratio = 1.05 / (lum(de.COLOURS[name]) + 0.05)
            self.assertGreaterEqual(ratio, 4.5, name)

    def test_risks_decisions_updates_and_rows_in_both_bodies(self):
        d = build(items=[LATE, RISK, DEC], include_update=True)
        self.assertIn("Latest update: Plan in draft", d["text"])
        self.assertIn("Issue: Test environment may slip", d["text"])
        self.assertIn("Response: none recorded yet", d["text"])
        self.assertIn("Decision needed: Which use cases go into Phase 2", d["text"])
        self.assertIn("Decision needed:</b> Which use cases", d["html"])
        self.assertNotIn("Latest update", build(items=[LATE])["text"])


class Outside(unittest.TestCase):
    def test_own_domain_or_not(self):
        self.assertFalse(de.is_outside("Sam@Example.test", OWN))
        self.assertTrue(de.is_outside(OUTSIDE, OWN))
        self.assertTrue(de.is_outside("", OWN))
        self.assertTrue(de.is_outside("not-an-address", OWN))

    def test_internal_items_start_unticked_for_an_outside_address(self):
        items = [LATE, INTERNAL]
        self.assertEqual(de.default_picked(items, OUTSIDE, OWN), ["ABC-A-001"])
        self.assertEqual(de.default_picked(items, "", OWN), ["ABC-A-001"])
        self.assertEqual(de.default_picked(items, INSIDE, OWN), ["ABC-A-001", "ABC-A-005"])

    def test_an_internal_item_that_is_ticked_is_tagged(self):
        d = build(items=[LATE, INTERNAL], email=OUTSIDE)
        self.assertEqual(d["internal_ids"], ["ABC-A-005"])
        self.assertEqual(build(items=[LATE, INTERNAL], email=INSIDE)["internal_ids"], [])
        self.assertEqual(build(items=[LATE], email=OUTSIDE)["internal_ids"], [])

    def test_the_internal_tag_is_never_in_the_copied_email(self):
        for email in (OUTSIDE, INSIDE, ""):
            d = build(items=[LATE, INTERNAL], email=email)
            self.assertNotIn("(internal)", d["text"] + d["html"] + de.clipboard(d)["text/plain"])

    def test_picked_decides_what_is_in(self):
        d = build(items=[LATE, SOON], picked=["ABC-A-002"])
        self.assertEqual(d["ids"], ["ABC-A-002"])
        self.assertNotIn("ABC-A-001", d["text"] + d["html"])

    def test_barred_items_never_appear_even_if_picked(self):
        held = item("ABC-A-010", "Review the confidential pricing", "2026-10-20")
        hidden = item("ABC-A-011", "Hidden row", "2026-10-20", hidden=True)
        sens = item("ABC-A-012", "Sensitive matter", "2026-10-20", sensitive=True)
        d = build(items=[LATE, held, hidden, sens], email=OUTSIDE)
        self.assertEqual(d["ids"], ["ABC-A-001"])
        self.assertEqual(build(items=[sens], email=INSIDE)["ids"], ["ABC-A-012"])           # kept for an own address
        ok, left = de.offered([LATE, held, hidden, sens], OUTSIDE, OWN)
        self.assertEqual(([i["id"] for i in ok], left), (["ABC-A-001"], 3))

    def test_internal_notes_and_sources_are_never_read(self):
        secret = item("ABC-A-013", "Plain task", "2026-10-20", internal_note="NOTE-TEXT-X", source="mail from Zed",
                      notes="NOTES-Y", movement="MOVE-Z")
        d = build(items=[secret], include_update=True)
        for word in ("NOTE-TEXT-X", "Zed", "NOTES-Y", "MOVE-Z"):
            self.assertNotIn(word, d["text"] + d["html"])

    def test_closed_items_are_not_offered(self):
        done = item("ABC-A-014", "Old", "2026-10-01", status="Closed")
        self.assertEqual(de.offered([LATE, done], INSIDE, OWN)[0], [LATE])


class Selection(unittest.TestCase):
    ALL = [LATE, SOON, FAR, NODATE, INTERNAL, DEC, item("ABC-A-020", "Someone else's", "2026-10-09", owner="Pat Lee"),
           item("ABC-A-021", "Done", "2026-10-09", status="Done")]

    def test_one_item_from_the_peek(self):
        self.assertEqual([i["id"] for i in de.item_for_peek(self.ALL, "ABC-A-001", INSIDE, OWN)], ["ABC-A-001"])
        self.assertEqual(de.item_for_peek(self.ALL, "ABC-A-021", INSIDE, OWN), [])
        self.assertEqual(de.item_for_peek(self.ALL, "NOPE-A-001", INSIDE, OWN), [])

    def test_all_of_an_owners_open_items(self):
        got = [i["id"] for i in de.items_for_owner(self.ALL, "dana hart", INSIDE, OWN, "update_request", TODAY)]
        self.assertEqual(got, ["ABC-A-001", "ABC-A-002", "ABC-A-005", "ABC-A-003", "ABC-A-004"])

    def test_a_chase_offers_only_the_overdue_ones(self):
        got = [i["id"] for i in de.items_for_owner(self.ALL, "Dana Hart", INSIDE, OWN, "chase", TODAY)]
        self.assertEqual(got, ["ABC-A-001"])

    def test_the_mode_the_peek_opens_in(self):
        self.assertEqual(de.mode_for(DEC, TODAY), "decision")
        self.assertEqual(de.mode_for(LATE, TODAY), "chase")
        self.assertEqual(de.mode_for(SOON, TODAY), "update_request")
        self.assertEqual(de.mode_for(NODATE, TODAY), "update_request")


class CopyingAndSent(unittest.TestCase):
    def test_both_clipboard_types(self):
        d = build()
        c = de.clipboard(d)
        self.assertEqual(c, {"text/html": d["html"], "text/plain": d["text"]})
        self.assertTrue(c["text/html"].startswith("<div ") and "<" not in c["text/plain"])

    def test_a_refused_clipboard_says_what_to_press(self):
        self.assertEqual(de.copy_result(True), "Copied")
        self.assertEqual(de.copy_result(False), "The browser did not copy it. Press ⌘C to copy the selected text.")

    def test_mail_link_only_when_the_finished_link_is_short(self):
        # The limit is on the encoded link, not the text: a space is 3 characters in a link and a line break 6.
        self.assertEqual(de.MAILTO_LIMIT, 2000)
        fits = {"to": "a@b.test", "subject": "S", "text": "x" * 1900}
        self.assertTrue(len(fits["text"]) < de.MAILTO_LIMIT and de.mailto_offered(fits))
        edge = len(de.mailto_link(dict(fits, text="")))
        self.assertTrue(de.mailto_offered(dict(fits, text="x" * (de.MAILTO_LIMIT - edge))))
        self.assertFalse(de.mailto_offered(dict(fits, text="x" * (de.MAILTO_LIMIT - edge + 1))))
        spaced = dict(fits, text="word " * 340)             # 1,700 characters of text, about 2,700 as a link
        self.assertEqual(len(spaced["text"]), 1700)
        self.assertGreater(len(de.mailto_link(spaced)), 2400)
        self.assertFalse(de.mailto_offered(spaced))
        self.assertFalse(de.mailto_offered(dict(fits, text="line\n" * 400)))


class HeaderInjection(unittest.TestCase):
    """The security review: nothing that enters the Subject or To can start a second header in the mail link."""
    EVIL = "Prog\r\nBcc: evil@x.example"

    def test_a_project_name_with_a_line_break_is_one_line_in_the_subject(self):
        for name in (self.EVIL, "Prog\nBcc: e@x.test", "Prog\rBcc: e@x.test", "Prog\u2028Bcc: e@x.test", "Prog\u0085Bcc: e@x.test",
                     "Prog\x00\x0bBcc: e@x.test"):
            d = build(project_names={"ABC": name}, items=[LATE])
            for ch in "\r\n\u2028\u2029\u0085\x00\x0b":
                self.assertNotIn(ch, d["subject"], repr(name))
            link = de.mailto_link(d)
            for bad in ("%0D", "%0A", "%E2%80%A8", "%00"):
                self.assertNotIn(bad, link.split("&body=")[0], repr(name))
            self.assertTrue(d["subject"].startswith("Prog Bcc: "), d["subject"])

    def test_a_project_name_with_a_line_break_in_a_many_item_subject_too(self):
        d = build(mode="chase", items=[LATE, SOON], project_names={"ABC": self.EVIL})
        self.assertNotIn("\n", d["subject"])
        self.assertNotIn("\r", d["subject"])

    def test_the_recipient_is_one_line(self):
        d = build(email="dana@partner.test\r\nBcc: evil@x.example")
        self.assertNotIn("\n", d["to"])
        self.assertNotIn("\r", d["to"])
        self.assertNotIn("%0A", de.mailto_link(d).split("?subject=")[0])
        # a draft handed in by someone else is flattened too, by the link builder
        raw = {"to": "a@b.test\r\nBcc: e@x.test", "subject": "S\r\nBcc: e@x.test", "text": "hi"}
        head = de.mailto_link(raw).split("&body=")[0]
        self.assertNotIn("%0D", head)
        self.assertNotIn("%0A", head)

    def test_one_line_collapses_every_break_and_control_character(self):
        self.assertEqual(de.one_line("a\r\nb\u2028c\u2029d\u0085e\x00f\t g"), "a b c d e f g")
        self.assertEqual(de.one_line(None), "")

    def test_the_sent_entry_is_ids_date_and_mode_only(self):
        e = de.sent_entry(["ABC-A-001", "ABC-A-001", "ABC-A-002"], "chase", "2026-10-13")
        self.assertEqual(e, {"kind": "email_sent", "ids": ["ABC-A-001", "ABC-A-002"], "date": "2026-10-13", "mode": "chase"})
        for bad in (([], "chase", TODAY), (["ABC-A-001"], "polish", TODAY), (["ABC-A-001"], "chase", "13-10-2026")):
            with self.assertRaises(ValueError):
                de.sent_entry(*bad)

    def test_recorded_chases_step_the_tone_up(self):
        log = [de.sent_entry(["ABC-A-001"], "chase", "2026-10-06"), de.sent_entry(["ABC-A-001", "ABC-A-002"], "chase", "2026-10-08"),
               de.sent_entry(["ABC-A-003"], "update_request", "2026-10-08"), {"kind": "other", "ids": ["ABC-A-004"], "mode": "chase"}]
        counts = de.chase_counts(log)
        self.assertEqual(counts, {"ABC-A-001": {"n": 2, "last": "2026-10-08"}, "ABC-A-002": {"n": 1, "last": "2026-10-08"}})
        self.assertEqual(de.tone_for(["ABC-A-002"], counts), 1)
        self.assertEqual(de.tone_for(["ABC-A-001", "ABC-A-002"], counts), 2)
        self.assertEqual(de.tone_for(["ABC-A-009"], counts), 0)


class NeverSends(unittest.TestCase):
    def test_the_module_has_no_way_to_send_or_reach_out(self):
        with open(de.__file__, encoding="utf-8") as fh:
            src = fh.read()
        for word in ("import smtplib", "import socket", "import urllib", "import subprocess", "import requests", "sendmail"):
            self.assertNotIn(word, src)


if __name__ == "__main__":
    unittest.main()
