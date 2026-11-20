"""Row 1293 line 10: a dry run or an offer that could not be made or saved is not used up (ask_service.py, ask_apply.py; guarded).

Run: python3 dev/run_tests.py test_ask_retry_1293
A busy or unusable database (status 503) or a fault saves nothing, so the reply may be shown again and the offer may be applied again.
A refusal that reads the data (a changed item, a wrong title) still uses the offer. Fictional data only.
"""
import unittest

from test_ask_change_route import Base, change_line
from clark import ask_service


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
        many = [change_line(op="new", kind="action", title=f"Task {i}", owner="Sam Lee") for i in range(6)]
        reply = self.answer(*many)["reply"]
        self.assertEqual((self.dry(reply)[0], self.dry(reply)[1]["code"]), (400, "too_many"))

    def offer(self):
        status, dry = self.dry(self.reply())
        self.assertEqual(status, 200, dry)
        return dry["plans"][0]["offer"]

    def test_a_busy_save_keeps_the_offer_and_it_saves_the_next_time(self):
        offer = self.offer()
        self.down["save"] = True
        status, body = self.apply(offer)
        self.assertEqual((status, body["code"]), (503, "busy"))
        self.assertEqual(self.status_of(self.action), "Open")
        self.down["save"] = False
        status, body = self.apply(offer)
        self.assertEqual((status, body["ok"]), (200, True), body)
        self.assertEqual(self.status_of(self.action), "Closed")
        self.assertEqual(self.apply(offer)[1]["code"], "no_offer", "saved once, used once")

    def test_a_fault_while_saving_keeps_the_offer(self):
        offer = self.offer()
        self.down["boom"] = True
        with self.assertRaises(RuntimeError):
            self.service.applier.apply(offer, "ABC")
        self.down["boom"] = False
        self.assertEqual(self.apply(offer)[0], 200)

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
