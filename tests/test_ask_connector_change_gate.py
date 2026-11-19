"""Row 1306 review finding: a change suggested by an answer that read a connector (mail, calendar, Teams, files) is held like one that read
the person's saved folders: Apply needs confirm: true, which no field from the page can clear. Connector content is text anyone can write,
so it must never reach a change by itself. With no connector in the run nothing changes (an answer from the report alone needs no Confirm).

The provider is a stub that reports a Used line the way the real command does (`last_line`). Fictional data only.
Run: python3 dev/run_tests.py test_ask_connector_change_gate
"""
import unittest

import test_ask_change_route as route
from clark import ask
from clark import ask_connector_screen as scr
from test_ask_change_route import change_line


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
        got = self.answer(change_line(op="change", id=self.action, status="Closed"))
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


if __name__ == "__main__":
    unittest.main()
