"""Row 1293 line 10: a dry run or an offer that could not be made or saved is not used up (ask_service.py, ask_apply.py; guarded).

Run: python3 dev/run_tests.py test_ask_retry_1293
A busy or unusable database (status 503) or a fault saves nothing, so the reply may be shown again and the offer may be applied again.
A refusal that reads the data (a changed item, a wrong title) still uses the offer. Fictional data only.
"""
import unittest
from unittest import mock

from test_ask_change_route import Base, change_line
from clark import ask_apply, ask_service


class Retry(Base):
    def setUp(self):
        super().setUp()
        self.real = self.service.applier.ask_change
        self.down = {"dry": False, "save": False, "boom": False, "refuse": False}
        self.dry_queue = []                       # one entry for each dry run asked for: None reads the data, else the code that run is refused with
        self.service.applier.ask_change = self.flaky

    def flaky(self, request, dry=True, expect=None):
        busy = (503, {"ok": False, "code": "busy", "message": "clark's data is in use"})
        if dry is not False and self.dry_queue:
            code = self.dry_queue.pop(0)
            if code is not None:
                return (400 if code == "refused" else 503), {"ok": False, "code": code, "message": "Nothing was changed."}
        if dry is not False and self.down["dry"]:
            return busy
        if dry is False and self.down["save"]:
            return busy
        if dry is False and self.down["boom"]:
            raise RuntimeError("a fault")
        if dry is False and self.down["refuse"]:
            return 409, {"ok": False, "code": "changed", "message": "It changed since it was shown."}
        return self.real(request, dry=dry, expect=expect)

    def reply(self):
        return self.answer(change_line(op="change", id=self.action, current_title="Draft the cut-over plan",
                                       current_owner="Sam Lee", status="Closed"), "CITE: P1")["reply"]

    def test_a_dry_run_that_found_the_data_busy_leaves_the_reply_usable(self):
        reply = self.reply()
        self.down["dry"] = True
        status, body = self.dry(reply)
        self.assertEqual((status, body["plans"][0]["code"]), (200, "busy"))
        self.down["dry"] = False
        status, body = self.dry(reply)
        self.assertEqual((status, body["ok"]), (200, True), body)
        self.assertEqual(self.dry(reply)[1]["code"], "shown_already", "a dry run that worked is still made once")

    def two_new(self):
        return self.answer(*[change_line(op="new", kind="action", title=f"Task {i}", owner="Sam Lee") for i in range(2)])["reply"]

    def test_one_plan_of_several_that_found_the_data_busy_leaves_the_reply_usable(self):
        reply = self.two_new()
        self.dry_queue = [None, "busy"]
        status, body = self.dry(reply)
        self.assertEqual((status, [p["ok"] for p in body["plans"]]), (200, [True, False]))
        self.assertEqual(self.dry(reply)[0], 200)

    def test_a_dry_run_that_found_the_data_unusable_leaves_the_reply_usable(self):
        reply = self.two_new()
        self.dry_queue = ["no_data", "no_data"]
        self.assertEqual(self.dry(reply)[1]["plans"][0]["code"], "no_data")
        self.assertEqual(self.dry(reply)[0], 200)

    def test_a_dry_run_with_a_plain_refusal_in_it_still_uses_the_reply_up(self):
        reply = self.two_new()
        self.dry_queue = ["refused", None]
        self.assertEqual(self.dry(reply)[1]["plans"][0]["code"], "refused")
        self.assertEqual((self.dry(reply)[0], self.dry(reply)[1]["code"]), (409, "shown_already"))

    def test_a_dry_run_that_worked_still_uses_the_reply_up(self):
        reply = self.reply()
        self.assertEqual(self.dry(reply)[0], 200)
        self.assertEqual((self.dry(reply)[0], self.dry(reply)[1]["code"]), (409, "shown_already"))

    def test_a_refused_dry_run_of_too_many_changes_leaves_the_reply_usable(self):
        many = [change_line(op="new", kind="action", title=f"Task {i}", owner="Sam Lee") for i in range(2)]
        reply = self.answer(*many)["reply"]          # the reply reader now cuts at the limit, so the limit is lowered for this run
        with mock.patch.object(ask_apply, "MAX_AT_ONCE", 1):
            self.assertEqual((self.dry(reply)[0], self.dry(reply)[1]["code"]), (400, "too_many"))

    def offer(self):
        status, dry = self.dry(self.reply())
        self.assertEqual(status, 200, dry)
        return dry["plans"][0]["offer"]

    def test_a_busy_save_keeps_the_offer_and_it_saves_the_next_time(self):
        offer = self.offer()
        self.down["save"] = True
        status, body = self.apply(offer, confirm=True)
        self.assertEqual((status, body["code"]), (503, "busy"))
        self.assertEqual(self.status_of(self.action), "Open")
        self.down["save"] = False
        status, body = self.apply(offer, confirm=True)
        self.assertEqual((status, body["ok"]), (200, True), body)
        self.assertEqual(self.status_of(self.action), "Closed")
        self.assertEqual(self.apply(offer, confirm=True)[1]["code"], "no_offer", "saved once, used once")

    def test_a_fault_while_saving_keeps_the_offer(self):
        offer = self.offer()
        self.down["boom"] = True
        with self.assertRaises(RuntimeError):
            self.service.applier.apply(offer, "ABC", confirm=True)
        self.down["boom"] = False
        self.assertEqual(self.apply(offer, confirm=True)[0], 200)

    def test_a_fault_after_the_save_was_committed_does_not_restore_the_offer(self):
        reply = self.answer(change_line(op="new", kind="action", title="Task once", owner="Sam Lee"))["reply"]
        status, dry = self.dry(reply)
        self.assertEqual(status, 200, dry)
        offer = dry["plans"][0]["offer"]
        before = self.counts()[0]
        with mock.patch("clark.backup.finish", side_effect=RuntimeError("after the commit")):
            with self.assertRaises(RuntimeError):
                self.service.applier.apply(offer, "ABC", confirm=True)
        self.assertEqual(self.counts()[0], before + 1, "the save happened")
        self.assertEqual(self.apply(offer, confirm=True)[1]["code"], "no_offer", "the offer is used up: a second Apply saves nothing")
        self.assertEqual(self.counts()[0], before + 1, "saved once")

    def test_a_fault_before_the_commit_restores_the_offer_and_nothing_is_saved(self):
        offer = self.offer()
        with mock.patch("clark.store.Store.ask_enabled", side_effect=RuntimeError("before the commit")):
            with self.assertRaises(RuntimeError):
                self.service.applier.apply(offer, "ABC", confirm=True)
        self.assertEqual(self.status_of(self.action), "Open")
        self.assertEqual(self.apply(offer, confirm=True)[0], 200)
        self.assertEqual(self.status_of(self.action), "Closed")

    def new_offer(self):
        reply = self.answer(change_line(op="new", kind="action", title="Task once", owner="Sam Lee"))["reply"]
        status, dry = self.dry(reply)
        self.assertEqual(status, 200, dry)
        return dry["plans"][0]["offer"]

    def test_a_busy_answer_after_the_save_was_committed_does_not_restore_the_offer(self):
        self.service.applier.ask_change = self.real                       # the real save: its own busy answer
        offer = self.new_offer()
        before = self.counts()[0]
        busy = ask_apply.changes.Invalid("clark's data is in use by another window")
        with mock.patch("clark.backup.finish", side_effect=busy):
            status, body = self.service.applier.apply(offer, "ABC", confirm=True)
        self.assertEqual((status, body["code"]), (503, "busy"))
        self.assertEqual(self.counts()[0], before + 1, "the save happened")
        self.assertEqual(self.apply(offer, confirm=True)[1]["code"], "no_offer")
        self.assertEqual(self.counts()[0], before + 1, "saved once")

    def test_a_busy_answer_before_the_save_keeps_the_offer_through_the_real_save(self):
        self.service.applier.ask_change = self.real
        offer = self.new_offer()
        before = self.counts()[0]
        busy = ask_apply.changes.Invalid("clark's data is in use by another window")
        with mock.patch("clark.store.Store.step", side_effect=busy):
            status, body = self.service.applier.apply(offer, "ABC", confirm=True)
        self.assertEqual((status, body["code"]), (503, "busy"))
        self.assertEqual(self.counts()[0], before)
        self.assertEqual(self.apply(offer, confirm=True)[0], 200, "kept for the next Apply")
        self.assertEqual(self.counts()[0], before + 1)

    def test_a_fault_inside_the_step_before_the_commit_restores_the_offer(self):
        self.service.applier.ask_change = self.real
        offer = self.new_offer()
        before = self.counts()[0]
        with mock.patch("clark.changes._AskStore.shown", side_effect=RuntimeError("inside the step")):
            with self.assertRaises(RuntimeError):
                self.service.applier.apply(offer, "ABC", confirm=True)
        self.assertEqual(self.counts()[0], before)
        self.assertEqual(self.apply(offer, confirm=True)[0], 200)
        self.assertEqual(self.counts()[0], before + 1)

    def test_a_commit_that_fails_restores_the_offer(self):
        self.service.applier.ask_change = self.real
        offer = self.new_offer()
        before = self.counts()[0]
        real_open = ask_apply.changes.clark_store.open_store

        class Con:
            def __init__(self, con):
                self.con = con

            def execute(self, sql, *a):
                if sql == "COMMIT":
                    raise RuntimeError("the commit failed")
                return self.con.execute(sql, *a)

            def __getattr__(self, name):
                return getattr(self.con, name)

        def open_store(*a, **kw):
            store = real_open(*a, **kw)
            store.con = Con(store.con)
            return store
        with mock.patch.object(ask_apply.changes.clark_store, "open_store", open_store):
            with self.assertRaises(RuntimeError):
                self.service.applier.apply(offer, "ABC", confirm=True)
        self.assertEqual(self.counts()[0], before)
        self.assertEqual(self.apply(offer, confirm=True)[0], 200, "nothing was committed, so the offer was kept")

    def test_a_fault_in_a_dry_run_is_not_a_committed_save(self):
        offer_request = self.service.applier.offers[self.new_offer()].request
        with mock.patch("clark.backup.finish", side_effect=RuntimeError("after the rollback")):
            with self.assertRaises(RuntimeError) as got:
                self.real(offer_request, dry=True)
        self.assertFalse(getattr(got.exception, "committed", False))

    def test_an_empty_dry_step_is_not_committed_and_an_empty_real_one_is(self):
        who = dict(actor=ask_apply.changes.ASK_ACTOR)
        with self.store.step(ask_apply.changes.ASSISTANT, "Sam Lee", dry=True, **who) as st:
            pass
        self.assertIs(st.committed, False)
        with self.store.step(ask_apply.changes.ASSISTANT, "Sam Lee", dry=False, **who) as st:
            pass
        self.assertIs(st.committed, True)

    def test_a_fault_that_is_not_an_exception_still_keeps_the_offer(self):
        offer = self.offer()
        with mock.patch.object(self.service.applier, "ask_change", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.service.applier.apply(offer, "ABC", confirm=True)
        self.assertEqual(self.apply(offer, confirm=True)[0], 200)

    def test_a_kept_offer_still_expires_when_it_would_have(self):
        now = [1000.0]
        self.service.applier.clock = lambda: now[0]
        offer = self.offer()
        now[0] += 10 * 60
        self.down["save"] = True
        self.assertEqual(self.apply(offer, confirm=True)[0], 503)
        self.down["save"] = False
        now[0] += 21 * 60                         # 31 minutes after it was made, 21 after the busy save
        self.assertEqual((self.apply(offer)[0], self.apply(offer)[1]["code"]), (409, "no_offer"))
        self.assertEqual(self.status_of(self.action), "Open")

    def test_a_busy_save_of_an_offer_from_your_files_keeps_it_needing_confirm(self):
        offer = self.offer()
        self.service.applier.offers[offer].from_source = True
        self.down["save"] = True
        self.assertEqual(self.apply(offer, confirm=True)[0], 503)
        self.down["save"] = False
        status, body = self.apply(offer)
        self.assertEqual((status, body["code"]), (409, "needs_confirm"))
        self.assertEqual(self.apply(offer, confirm=True)[0], 200)
        self.assertEqual(self.status_of(self.action), "Closed")

    def test_a_refusal_from_the_data_still_uses_the_offer(self):
        offer = self.offer()
        self.down["refuse"] = True
        self.assertEqual(self.apply(offer)[0], 409)
        self.down["refuse"] = False
        self.assertEqual(self.apply(offer)[1]["code"], "no_offer")
        self.assertEqual(self.status_of(self.action), "Open")

    def test_two_applies_at_the_same_moment_save_once(self):
        offer = self.offer()
        seen = []
        real = self.service.applier.ask_change

        def second_press(request, dry=True, expect=None):
            if dry is False and not seen:
                seen.append(self.service.applier.apply(offer, "ABC"))      # the press that arrives while the first is saving
            return real(request, dry=dry, expect=expect)
        self.service.applier.ask_change = second_press
        self.assertEqual(self.apply(offer)[0], 200)
        self.assertEqual((seen[0][0], seen[0][1]["code"]), (409, "no_offer"))


if __name__ == "__main__":
    unittest.main()
