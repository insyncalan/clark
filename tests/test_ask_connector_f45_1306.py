"""Row 1306, security review F4 and F5: a fake connector server proves what the argument list and the screen let through. Nothing here
starts a real connector or the real command; the fake server's handlers count their calls, and a small stand-in for the command's
permission rule (an exact allow, a deny by exact name or by whole server prefix, deny wins, anything neither allowed nor denied is
refused) decides whether a handler is reached.

Run: python3 dev/run_tests.py test_ask_connector_f45_1306
"""
import json
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

from clark import ask, ask_claude as ac, ask_connector_args as ca, ask_connector_screen as scr, ask_connector_stream as cs
from clark import ask_connectors

M365 = "claude.ai Microsoft 365"
P = "mcp__claude_ai_Microsoft_365"
LIST_M365 = f"{M365}: https://example.invalid/m - ✓ Connected"
PARTS = ("mail", "calendar", "teams", "sharepoint")
DISC = [{"connector": c, "label": c, "server": M365} for c in PARTS]
SHARE = "SharePoint and OneDrive"
PATH = Path("/x/claude")
MAIL_ADDRESS = "mail:///messages/AAMkAD-fake-message-id"


class FakeServer:
    """A fake connector server: tools are handlers that count their calls."""
    def __init__(self, name, tools):
        self.name, self.calls = name, []
        self.tools = {t: self._handler(t) for t in tools}

    def _handler(self, tool):
        def run(arguments):
            self.calls.append((tool, arguments))
            return "fake result"
        return run

    @property
    def prefix(self):
        return ca.prefix(self.name)


def permitted(args, full_name):
    """The stand-in for the command's rule: denied when a deny names the tool or its whole server; allowed only by an exact allow."""
    denied = {a[len(ca.FLAG_DENY):] for a in args if a.startswith(ca.FLAG_DENY)}
    allowed = {a[len(ca.FLAG_ALLOW):] for a in args if a.startswith(ca.FLAG_ALLOW)}
    server = full_name.rsplit("__", 1)[0]
    if full_name in denied or server in denied:
        return False
    return full_name in allowed


def model_calls(args, server, tool, arguments=None):
    """The model asks for `tool` of `server`: the handler is reached only when the argument list permits it."""
    if permitted(args, f"{server.prefix}__{tool}"):
        return server.tools[tool](arguments or {})
    return None


def call_for(on, listing):
    ask_connectors.clear_cache()
    return ca.build_call(on, lambda: listing)


class F4ReadResource(unittest.TestCase):
    def setUp(self):
        self.m365 = FakeServer(M365, ("sharepoint_search", "read_resource", "outlook_email_search"))

    def test_the_tables_do_not_list_it(self):
        self.assertNotIn("read_resource", ca.READ_TOOLS[M365]["sharepoint"])
        self.assertNotIn("read_resource", scr.ALLOWED_TOOLS[SHARE])
        for tools in ca.READ_TOOLS[M365].values():
            self.assertNotIn("read_resource", tools)
        for tools in scr.ALLOWED_TOOLS.values():
            self.assertNotIn("read_resource", tools)

    def test_only_sharepoint_on_never_allows_it_and_denies_it_by_name(self):
        args = ca.connector_args(DISC, ["sharepoint"])
        self.assertNotIn(f"--allowedTools={P}__read_resource", args)
        self.assertIn(f"--disallowedTools={P}__read_resource", args)
        self.assertIn(f"--allowedTools={P}__sharepoint_search", args)

    def test_it_is_denied_with_every_part_on_too(self):
        args = ca.connector_args(DISC + [{"connector": "people", "label": "", "server": M365}], list(PARTS) + ["people"])
        self.assertNotIn(f"--allowedTools={P}__read_resource", args)
        self.assertIn(f"--disallowedTools={P}__read_resource", args)

    def test_a_mail_resource_call_never_reaches_the_server(self):
        args = ca.connector_args(DISC, ["sharepoint"])
        self.assertIsNone(model_calls(args, self.m365, "read_resource", {"uri": MAIL_ADDRESS}))
        self.assertEqual(self.m365.calls, [])
        self.assertEqual(model_calls(args, self.m365, "sharepoint_search", {"query": "plan"}), "fake result")
        self.assertEqual([c[0] for c in self.m365.calls], ["sharepoint_search"])

    def test_the_other_sharepoint_read_tools_still_work(self):
        args = ca.connector_args(DISC, ["sharepoint"])
        for tool in ("sharepoint_search", "sharepoint_folder_search"):
            self.assertIn(f"--allowedTools={P}__{tool}", args)
            self.assertTrue(scr.tool_allowed(f"{P}__{tool}", {SHARE}), tool)

    def test_the_screen_refuses_it_with_a_mail_address(self):
        s = scr.screen(f"{P}__read_resource", json.dumps({"uri": MAIL_ADDRESS}), 0, {SHARE})
        self.assertFalse(s.used)
        self.assertEqual(s.reason, scr.REFUSED_TOOL)
        self.assertFalse(scr.tool_allowed("read_resource"))
        self.assertFalse(scr.tool_allowed(f"{P}__read_resource", {SHARE}))

    def test_a_run_that_called_it_is_refused_as_a_whole(self):
        lines = [json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "1", "name": f"{P}__read_resource", "input": {}}]}}),
                 json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "1", "content": "mail body"}]}}),
                 json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "x"})]
        ok, _line, result = cs.checked(("\n".join(lines) + "\n").encode(), {SHARE})
        self.assertFalse(ok)
        self.assertIsNone(result)


class Wired(unittest.TestCase):
    """The same through ClaudeCommand.ask, with the start of the command faked: `self.args` is what would have been started."""
    def setUp(self):
        ask_connectors.clear_cache()
        self.args, self.listing = [], LIST_M365
        self.provider = ac.ClaudeCommand(places=(), env={}, limit=5)
        self.provider.connector_runner = lambda: self.listing
        for p in (mock.patch.object(self.provider, "usable", return_value=(PATH, None)),
                  mock.patch.object(ac, "run", side_effect=self.fake_run)):
            p.start()
            self.addCleanup(p.stop)

    def fake_run(self, args, *_a, **_k):
        self.args = list(args)
        return "ok", json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "ok"}).encode(), 0

    def ask(self, connectors):
        return self.provider.ask(ask.Request(text="Q", question="Q", connectors=tuple(connectors)))

    def test_read_resource_is_not_in_the_args_passed_to_the_command(self):
        self.ask(["sharepoint"])
        self.assertFalse([a for a in self.args if a.startswith(ca.FLAG_ALLOW) and "read_resource" in a])
        self.assertIn(f"--disallowedTools={P}__read_resource", self.args)
        self.assertIn(f"--allowedTools={P}__sharepoint_search", self.args)

    def test_an_unknown_server_is_denied_whole_in_the_args_passed_to_the_command(self):
        self.listing = LIST_M365 + "\nclaude.ai Fake Unlisted: https://example.invalid/u - ✓ Connected"
        self.ask(["mail"])
        self.assertIn("--disallowedTools=mcp__claude_ai_Fake_Unlisted", self.args)
        self.assertFalse([a for a in self.args if a.startswith(ca.FLAG_ALLOW) and "Fake" in a])

    def test_a_server_whose_name_cannot_be_denied_ends_the_connector_run(self):
        self.listing = LIST_M365 + "\nclaude.ai Fake's Tool: https://example.invalid/u - ✓ Connected"
        self.ask(["mail"])
        self.assertEqual(self.args, ac.arguments(PATH, "", ask.RULES))        # today's locked-down command, no connector reached


class F5UnknownServer(unittest.TestCase):
    def setUp(self):
        self.fake = FakeServer("claude.ai Fake Unlisted", ("send_everything", "read_everything"))
        self.listing = LIST_M365 + f"\n{self.fake.name}: https://example.invalid/u - ✓ Connected"

    def test_the_fake_server_is_outside_the_known_list(self):
        self.assertNotIn("Fake_Unlisted", ca.KNOWN_SERVERS)

    def test_the_write_tool_is_refused_before_any_call(self):
        call = call_for(["mail"], self.listing)
        self.assertTrue(call.ok)
        self.assertIn(f"--disallowedTools={self.fake.prefix}", call.args)
        self.assertIsNone(model_calls(call.args, self.fake, "send_everything", {"to": "x"}))
        self.assertIsNone(model_calls(call.args, self.fake, "read_everything"))
        self.assertEqual(self.fake.calls, [])

    def test_it_is_denied_whole_whatever_is_on(self):
        for on in (["mail"], ["sharepoint"], ["mail", "calendar", "teams", "sharepoint"]):
            call = call_for(on, self.listing)
            self.assertIn(f"--disallowedTools={self.fake.prefix}", call.args, on)
            self.assertFalse([a for a in call.args if a.startswith(ca.FLAG_ALLOW) and "Fake" in a], on)
        self.assertEqual(self.fake.calls, [])

    def test_the_on_server_is_still_reached(self):
        call = call_for(["mail"], self.listing)
        m365 = FakeServer(M365, ("outlook_email_search", "outlook_send_mail"))
        self.assertEqual(model_calls(call.args, m365, "outlook_email_search"), "fake result")
        self.assertIsNone(model_calls(call.args, m365, "outlook_send_mail"))
        self.assertEqual([c[0] for c in m365.calls], ["outlook_email_search"])

    def test_a_name_that_cannot_be_denied_refuses_the_run_before_any_call(self):
        for name in ("claude.ai Fake's Tool", "claude.ai Fäke", "claude.ai Fake\x07Tool", "--fake"):
            call = call_for(["mail"], LIST_M365 + f"\n{name}: https://example.invalid/u - ✓ Connected")
            self.assertFalse(call.ok, name)
            self.assertEqual(call.args, (), name)
            self.assertEqual(call.reason, "server name not readable", name)
            self.assertEqual(call.dropped, 1, name)
            with self.assertRaises(ValueError):
                ca.compose(["--strict-mcp-config"], call)

    def test_a_clean_list_is_not_refused(self):
        self.assertTrue(call_for(["mail"], self.listing).ok)
        self.assertEqual(call_for(["mail"], self.listing).dropped, 0)

    def test_a_dropped_name_is_refused_even_when_the_on_connector_is_found(self):
        disc = DISC + [{"connector": "other", "label": "", "server": "bad name\x00"}]
        self.assertEqual(ca.connector_plan(disc, ["mail"])[1], 1)


if __name__ == "__main__":
    unittest.main()
