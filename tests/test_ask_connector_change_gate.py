"""Row 1306 review finding: a change suggested by an answer that read a connector (mail, calendar, Teams, files) is held like one that read
the person's saved folders: Apply needs confirm: true, which no field from the page can clear. Connector content is text anyone can write,
so it must never reach a change by itself. With no connector in the run nothing changes (an answer from the report alone needs no Confirm).

The provider is a stub that reports a Used line the way the real command does (`last_line`). Fictional data only.
Run: python3 dev/run_tests.py test_ask_connector_change_gate
"""
import threading
import unittest

import test_ask_change_route as route
from clark import ask
from clark import ask_connector_screen as scr
from test_ask_change_route import change_line
from clark import ai_providers


class ConnectorStub(ask.StubProvider):
    """A stub that, like ClaudeCommand, keeps the UsedLine of the run it just made (None when no connector was in the run)."""
    last_line = None


class Gate(route.Base):
    def setUp(self):
        super().setUp()
        self.provider = ConnectorStub(reply="")
        self.service.provider = self.provider

    def closed(self, line):
        self.provider.last_line = line
        got = self.answer(change_line(op="change", id=self.action, current_title="Draft the cut-over plan", status="Closed"))
        return self.dry(got["reply"])[1]

    def test_a_change_after_a_connector_was_read_needs_confirm(self):
        line = scr.used_line(scr.screen_all([("mcp__claude_ai_Microsoft_365__outlook_email_search", '[{"s": 1}]')]))
        dry = self.closed(line)
        self.assertTrue(dry["from_source"])
        plan = dry["plans"][0]
        self.assertTrue(plan["needs_confirm"])
        before = self.counts()
        for extra in ({}, {"confirm": False}, {"confirm": "true"}, {"confirm": 1}):
            status, body = self.apply(plan["offer"], **extra)
            self.assertIn(status, (400, 409), extra)
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.status_of(self.action), "Open")
        self.assertEqual(self.apply(plan["offer"], confirm=True)[0], 200)
        self.assertEqual(self.status_of(self.action), "Closed")

    def test_no_connector_in_the_run_needs_no_confirm(self):
        dry = self.closed(None)
        self.assertFalse(dry["from_source"])
        self.assertFalse(dry["plans"][0]["needs_confirm"])

    def turn_on(self, name="mail"):
        self.store.con.execute("UPDATE connector_switches SET is_on = 1 WHERE connector = ?", (name,))
        self.store.con.commit()

    def test_a_connector_on_but_no_used_line_still_needs_confirm(self):
        """The Used line of the run can be gone by the time the answer reads it (a second run reset it): with a connector On that is not 'no connector read'."""
        self.turn_on()
        dry = self.closed(None)
        self.assertTrue(dry["from_source"])
        plan = dry["plans"][0]
        self.assertTrue(plan["needs_confirm"])
        before = self.counts()
        for extra in ({}, {"confirm": False}, {"confirm": "true"}):
            self.assertIn(self.apply(plan["offer"], **extra)[0], (400, 409), extra)
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.apply(plan["offer"], confirm=True)[0], 200)

    def test_every_connector_that_is_on_counts(self):
        for name in ("calendar", "teams", "sharepoint"):
            self.store.con.execute("UPDATE connector_switches SET is_on = 0")
            self.turn_on(name)
            self.assertTrue(self.closed(None)["from_source"], name)

    def test_a_connector_off_everywhere_needs_no_confirm_without_a_used_line(self):
        self.assertFalse(self.closed(None)["from_source"])

    def test_a_connector_turned_off_for_the_project_needs_no_confirm_without_a_used_line(self):
        self.turn_on()
        self.store.con.execute("INSERT INTO project_connectors (project_id, connector, off) SELECT code, 'mail', 1 FROM projects")
        self.store.con.commit()
        self.assertFalse(self.closed(None)["from_source"])


class RacingCommand:
    """A stand-in for one provider's command inside a real Chosen. A question sets the Used line; while the command is busy (the lock is held) a
    question gets the busy words and runs nothing."""
    name = "fake"
    label = "Fake"

    def __init__(self, line):
        self.line, self.reply = line, ""
        self.command = self
        self.last_line = None
        self.lock = threading.Lock()

    def status(self):
        return {"connected": True, "why": ""}

    def ask(self, request, model=None, prefer=False):
        if not self.lock.acquire(blocking=False):
            return ask.Failure("busy")
        try:
            self.last_line = self.line
            return self.reply
        finally:
            self.lock.release()


class Racing(ask.Provider):
    """What the service is given: a real Chosen. The first question finishes (its answer is back, the Used line set), and a second question on the same
    Chosen comes in BEFORE the service reads the line, finds the command busy, and gets the busy words (Chosen.ask clears the line on the way in)."""
    name = "racing"

    def __init__(self, chosen, command):
        self.chosen, self.command = chosen, command

    @property
    def last_line(self):
        return self.chosen.last_line

    def status(self):
        return self.chosen.status()

    def ask(self, request):
        got = self.chosen.ask(request)
        self.command.lock.acquire()                       # the command is busy with some other run
        try:
            self.second = self.chosen.ask(request)
        finally:
            self.command.lock.release()
        return got


class RaceGate(route.Base):
    def setUp(self):
        super().setUp()
        self.command = RacingCommand(scr.used_line(scr.screen_all([("mcp__claude_ai_Microsoft_365__outlook_email_search", '[{"s": 1}]')])))
        self.chosen = ai_providers.Chosen((), lambda: (self.command, None, False), "off")
        self.racing = Racing(self.chosen, self.command)
        self.service.provider = self.racing

    turn_on = Gate.turn_on

    def first_question(self):
        self.command.reply = change_line(op="change", id=self.action, current_title="Draft the cut-over plan", status="Closed")
        got = self.answer(self.command.reply)
        return self.dry(got["reply"])[1]

    def test_the_second_question_wipes_the_line_the_first_one_set(self):
        self.first_question()
        self.assertEqual(self.racing.second.message, "busy")
        self.assertIsNone(self.chosen.last_line)         # the repro: the first question's line is gone before its reader has it

    def test_a_connector_on_and_the_line_wiped_still_needs_confirm(self):
        self.turn_on()
        dry = self.first_question()
        self.assertTrue(dry["from_source"])
        plan = dry["plans"][0]
        self.assertTrue(plan["needs_confirm"])
        self.assertEqual(self.apply(plan["offer"])[0], 409)
        self.assertEqual(self.apply(plan["offer"], confirm=True)[0], 200)

    def test_no_connector_on_and_the_line_wiped_needs_no_extra_confirm(self):
        dry = self.first_question()
        self.assertFalse(dry["from_source"])
        self.assertFalse(dry["plans"][0]["needs_confirm"])


if __name__ == "__main__":
    unittest.main()
