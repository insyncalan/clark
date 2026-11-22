"""Row 1306 C4 wiring: the read-only connector argument list is the one the real ask call uses, and only when a connector is On.
The command is faked (nothing is started); these tests prove clark's argument list, the store switch reaching the request, and the screen
of what the run did. The real proof is a run on a Mac with the connectors set up. Fictional data only.

Run: python3 dev/run_tests.py test_ask_connector_wiring
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

import _publish_fixture as plant
from clark import ask, ask_claude as ac, ask_connector_args as ca, ask_connector_screen as scr, ask_connector_stream as cs
from clark import ask_connectors, ask_service
from clark.store import open_store

M365, TODOIST = "claude.ai Microsoft 365", "claude.ai Todoist"
P = "mcp__claude_ai_Microsoft_365"
LIST_M365 = f"{M365}: https://example.invalid/m - ✓ Connected"
LIST_TODO = f"{TODOIST}: https://example.invalid/t - ✓ Connected"
LIST_DRIVE = "claude.ai Google Drive: https://example.invalid/d - ✓ Connected"
PATH = Path("/x/claude")
TODOIST_WRITES = ("add-tasks", "update-tasks", "complete-tasks", "uncomplete-tasks", "delete-object", "add-comments", "update-comments",
                  "add-projects", "update-projects", "add-sections", "update-sections", "add-labels", "update-labels", "add-filters",
                  "update-filters", "add-reminders", "update-reminders", "reschedule-tasks", "reorder-objects", "project-move",
                  "project-management", "manage-assignments", "import-project-template", "set-user-status")


def event(kind, *blocks):
    return json.dumps({"type": kind, "message": {"content": list(blocks)}})


def use(i, name):
    return event("assistant", {"type": "tool_use", "id": i, "name": name, "input": {}})


def got(i, content):
    return event("user", {"type": "tool_result", "tool_use_id": i, "content": content})


def found(i, *names, matches=True, content=None, extra=None):
    """A ToolSearch result in the shape a real run wrote (probe on a real machine): one tool_reference block per tool, and tool_use_result with the matches."""
    block = {"type": "tool_result", "tool_use_id": i,
             "content": content if content is not None else [{"type": "tool_reference", "tool_name": n} for n in names]}
    ev = {"type": "user", "message": {"content": [block]}}
    if matches:
        ev["tool_use_result"] = {"matches": list(names), "total_deferred_tools": 9}
    ev.update(extra or {})
    return json.dumps(ev)


def final(text="The plan is on track."):
    return json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": text})


def stream(*lines):
    return ("\n".join(lines) + "\n").encode("utf-8")


class Run(unittest.TestCase):
    """ClaudeCommand.ask with the command's start faked: `self.args` is what would have been started."""
    def setUp(self):
        ask_connectors.clear_cache()
        self.args, self.discoveries = [], 0
        self.out = json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "ok"}).encode()
        self.listing = LIST_M365
        self.provider = ac.ClaudeCommand(places=(), env={}, limit=5)
        self.provider.connector_runner = self.discover
        for p in (mock.patch.object(self.provider, "usable", return_value=(PATH, None)),
                  mock.patch.object(ac, "run", side_effect=self.fake_run)):
            p.start()
            self.addCleanup(p.stop)

    def discover(self):
        self.discoveries += 1
        if isinstance(self.listing, Exception):
            raise self.listing
        return self.listing

    status = "ok"

    def fake_run(self, args, *_a, **_k):
        self.args = list(args)
        return self.status, self.out, 0

    def ask(self, connectors=()):
        return self.provider.ask(ask.Request(text="Q", question="Q", connectors=tuple(connectors)))

    def today(self):
        return ac.arguments(PATH, "", ask.RULES)


class Unchanged(Run):
    def test_no_connector_on_is_byte_identical_to_today_and_discovery_is_never_run(self):
        self.assertEqual(self.ask(), "ok")
        self.assertEqual(self.args, self.today())
        self.assertEqual(self.discoveries, 0)
        self.assertIn("--strict-mcp-config", self.args)
        self.assertEqual(self.args[self.args.index("--tools") + 1], "")
        self.assertEqual(self.args[self.args.index("--max-turns") + 1], "1")
        self.assertEqual(self.args[self.args.index("--output-format") + 1], "json")
        self.assertEqual(self.provider.last_used, "")

    def test_the_request_default_is_none_on(self):
        self.assertEqual(ask.Request(text="a", question="a").connectors, ())

    def test_on_but_not_found_is_exactly_today(self):
        self.listing = LIST_DRIVE
        self.ask(["mail"])
        self.assertEqual(self.args, self.today())
        self.assertEqual(self.discoveries, 1)

    def test_on_but_discovery_fails_is_exactly_today(self):
        self.listing = RuntimeError("no command")
        self.assertEqual(self.ask(["mail"]), "ok")
        self.assertEqual(self.args, self.today())

    def test_todoist_alone_has_no_allow_table_so_it_is_exactly_today(self):
        self.listing = LIST_TODO
        self.ask(["todoist"])
        self.assertEqual(self.args, self.today())


class Killers(Run):
    def test_an_on_list_with_no_usable_id_is_today_and_not_screened(self):
        self.out = stream(use("1", f"{P}__outlook_send_mail"), final("Plain"))
        r = self.ask([None])
        self.assertEqual(self.args, self.today())
        self.assertNotEqual(r, ask.Failure(ac.CONNECTOR_REFUSED))

    def test_a_failed_run_is_read_as_today_not_screened(self):
        self.status = "failed"
        self.out = stream(json.dumps({"type": "rate_limit_event", "rate_limit_info": {"status": "rejected"}}))
        r = self.ask(["mail"])
        self.assertIsInstance(r, ask.Failure)
        self.assertNotEqual(r, ask.Failure(ac.CONNECTOR_REFUSED))

    def test_the_turns_for_a_connector_run_are_six_and_it_is_a_string(self):
        self.ask(["mail"])
        self.assertEqual(self.args[self.args.index("--max-turns") + 1], "6")

    def test_connector_arguments_with_no_connector_in_the_call_is_the_base_unchanged(self):
        base = self.today()
        self.assertEqual(ac.connector_arguments(base, ca.Call(True)), base)

    def test_a_discovered_id_outside_the_five_is_ignored_not_an_error(self):
        self.listing = LIST_M365 + "\n" + LIST_DRIVE
        self.out = stream(use("1", f"{P}__outlook_email_search"), got("1", "m"), final("Fine"))
        self.assertEqual(self.ask(["mail", "other"]), "Fine")

    def test_the_used_line_of_an_earlier_run_does_not_carry_over(self):
        self.out = stream(use("1", f"{P}__outlook_email_search"), got("1", "m"), final("Fine"))
        self.ask(["mail"])
        self.assertEqual(self.provider.last_used, "Used: Mail")
        self.assertEqual(self.provider.last_line.used, ("Mail",))
        self.out = json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "ok"}).encode()
        self.ask()
        self.assertEqual(self.provider.last_used, "")
        self.assertIsNone(self.provider.last_line)

    def test_the_stream_reader_edges(self):
        t = lambda *b: stream(use("1", f"{P}__outlook_email_search"), got("1", list(b)), final())  # noqa: E731
        txt = lambda x: {"type": "text", "text": x}  # noqa: E731
        self.assertFalse(cs.checked(stream(use("1", f"{P}__outlook_email_search"), got("1", []), final()), {"Mail"})[0], "empty list")
        self.assertFalse(cs.checked(t(txt("a"), {"type": "image"}), {"Mail"})[0], "one block that is not text")
        self.assertFalse(cs.checked(t({"text": "a"}), {"Mail"})[0], "no type")
        self.assertFalse(cs.checked(t(txt("x" * 20000), txt("x" * 20000)), {"Mail"})[0], "the newline between blocks counts: 40001")
        self.assertTrue(cs.checked(t(txt("x" * 20000), txt("x" * 19999)), {"Mail"})[0])
        self.assertFalse(cs.checked(stream(use("1", f"{P}__outlook_calendar_search"), final()), {"Mail"})[0], "a part that is off, no result")
        text_block = {"type": "text", "text": "thinking"}
        ok = stream(event("assistant", text_block), event("user", text_block), final())
        self.assertTrue(cs.checked(ok, {"Mail"})[0], "blocks that are not tool calls or results are not tools")


class Wired(Run):
    def test_one_on_one_found_uses_the_builders_list(self):
        self.assertEqual(self.ask(["mail"]), "ok")
        base = self.today()
        want = ac.connector_arguments(base, ca.build_call(["mail"], lambda: LIST_M365))
        self.assertEqual(self.args, want)
        self.assertNotIn("--strict-mcp-config", self.args)
        self.assertIn(f"--allowedTools={P}__outlook_email_search", self.args)
        self.assertEqual(self.discoveries, 2)         # one before the run (the argument list) and one after it (F5: a server that appeared)

    def test_only_the_output_the_turns_and_the_connector_flags_differ_from_today(self):
        self.ask(["mail"])
        today = self.today()
        rest = [a for a in self.args if a not in ("--verbose",) and not a.startswith(("--allowedTools=", "--disallowedTools="))]
        rest = ["json" if a == "stream-json" else "1" if a == ac.CONNECTOR_TURNS else a for a in rest]
        gone = []
        for i, a in enumerate(today):          # what a connector run leaves out (probes on real Macs): --strict-mcp-config, --safe-mode; --tools "" becomes --tools ToolSearch
            if a in ("--strict-mcp-config", "--safe-mode"):
                continue
            gone.append("ToolSearch" if (a == "" and today[i - 1] == "--tools") else a)
        self.assertEqual(rest, gone)
        self.assertEqual(self.args[self.args.index("--output-format") + 1:][:2], ["stream-json", "--verbose"])
        self.assertEqual(self.args[self.args.index("--tools") + 1], "ToolSearch")
        self.assertNotIn("--safe-mode", self.args)
        self.assertEqual(self.args[self.args.index("--max-turns") + 1], ac.CONNECTOR_TURNS)

    # Every built-in tool name known today. The connector run carries none of them: `--tools ToolSearch` is the allow-list.
    BUILT_INS = ("Agent", "AskUserQuestion", "Bash", "BashOutput", "Edit", "Glob", "Grep", "KillShell", "LS", "MultiEdit", "NotebookEdit", "Read", "Task", "TodoWrite",
                 "WebFetch", "WebSearch", "Write", "Skill", "SlashCommand", "Monitor", "Workflow", "CronCreate", "CronDelete", "CronList", "EnterPlanMode",
                 "ExitPlanMode", "EnterWorktree", "ExitWorktree", "ListMcpResourcesTool", "ReadMcpResourceTool", "ReadMcpResourceDirTool", "EndConversation",
                 "Artifact", "ArtifactCheck", "ArtifactComments", "ArtifactData", "DesignSync", "ListAgents", "ReportFindings", "SendFeedback", "StructuredOutput",
                 "SendToProject", "SendToProjectContext", "TaskCreate", "TaskGet", "TaskList", "TaskUpdate", "TaskStop", "TaskOutput", "SendMessage",
                 "ScheduleWakeup", "RemoteTrigger", "PushNotification", "PowerShell", "LSP", "REPL", "Tmux", "Sleep")

    def test_the_built_list_for_mail_on_is_the_allow_list_form_from_the_probes(self):
        # APPEARS: the argument list a Mail-On run sends is the set confirmed on real machines: --tools ToolSearch (an allow-list: init lists only that), no
        # --safe-mode, no empty --tools, the budget BEFORE every tool list (a list swallows what follows it), every other M365 tool and server denied by name or
        # prefix, the one Mail tool allowed, and NO built-in name anywhere.
        self.ask(["mail"])
        a = self.args
        self.assertEqual([a[i + 1] for i, x in enumerate(a) if x == "--tools"], ["ToolSearch"])
        self.assertNotIn("--safe-mode", a)
        self.assertNotIn("--strict-mcp-config", a)
        self.assertEqual(a[a.index("--setting-sources") + 1], "")
        self.assertIn("--no-session-persistence", a)
        self.assertEqual(a[a.index("--max-turns") + 1], "6")
        lists = [i for i, x in enumerate(a) if x.startswith(("--allowedTools", "--disallowedTools"))]
        self.assertNotIn("--max-budget-usd", a)
        named = {x.split("=", 1)[1] for x in a if x.startswith(("--allowedTools=", "--disallowedTools="))}
        self.assertEqual(sorted(named & set(self.BUILT_INS)), [], "no built-in name is allowed or denied: the allow-list is the gate")
        self.assertFalse(hasattr(ca, "BUILT_IN_TOOLS"))
        self.assertEqual([x for x in a if x.startswith("--allowedTools")], [f"--allowedTools={P}__outlook_email_search"])

    def test_no_built_in_and_no_denied_write_tool_passes_the_screen(self):
        # Refused by the run check, not assumed: a tool_use of any built-in, of a denied M365 write tool, fails the run.
        for name in self.BUILT_INS + tuple(f"{P}__{t}" for t in ca.WRITE_TOOLS[ca.M365]):
            ok, _line, result = cs.checked(stream(use("1", name), got("1", "t"), final()), {"Mail"})
            self.assertFalse(ok, name)
            self.assertIsNone(result, name)

    def test_every_other_account_connector_is_denied_whole(self):
        self.listing = LIST_M365 + "\n" + LIST_DRIVE + "\n" + LIST_TODO
        self.ask(["mail"])
        self.assertIn("--disallowedTools=mcp__claude_ai_Google_Drive", self.args)
        self.assertIn("--disallowedTools=mcp__claude_ai_Todoist", self.args)
        self.assertFalse([a for a in self.args if a.startswith("--allowedTools=") and "Todoist" in a])

    def test_every_write_tool_of_the_five_parts_is_denied_and_never_allowed(self):
        self.listing = LIST_M365 + "\n" + LIST_TODO
        self.ask(["mail", "calendar", "teams", "sharepoint", "todoist"])
        allowed = {a[len("--allowedTools="):] for a in self.args if a.startswith("--allowedTools=")}
        denied = {a[len("--disallowedTools="):] for a in self.args if a.startswith("--disallowedTools=")}
        self.assertEqual(len(ca.WRITE_TOOLS[ca.M365]), 36)
        for tool in ca.WRITE_TOOLS[ca.M365]:
            self.assertIn(f"{P}__{tool}", denied, tool)
            self.assertNotIn(f"{P}__{tool}", allowed, tool)
            self.assertIsNone(scr.part_of_tool(f"{P}__{tool}"), "the screen would not allow it either")
        self.assertIn("mcp__claude_ai_Todoist", denied)          # the whole server: so every one of its tools, writes included
        for tool in TODOIST_WRITES:
            self.assertIsNone(scr.part_of_tool(tool), tool)
            self.assertFalse([a for a in allowed if a.endswith(tool)], tool)
        self.assertTrue(allowed and all(scr.tool_allowed(t) for t in allowed))      # everything allowed is on the screen's read list
        self.assertTrue(all(a.startswith(("--allowedTools=", "--disallowedTools=")) or not a.startswith("--allow") for a in self.args))

    def test_an_off_connector_keeps_its_read_tools_denied(self):
        self.ask(["mail"])
        self.assertIn(f"--disallowedTools={P}__outlook_calendar_search", self.args)
        self.assertNotIn(f"--allowedTools={P}__outlook_calendar_search", self.args)

    def test_the_prompt_and_rules_stay_in_one_piece_and_the_question_is_never_an_argument(self):
        self.ask(["mail"])
        self.assertEqual(self.args[self.args.index("--system-prompt") + 1], ask.system_prompt("", ask.RULES))
        self.assertFalse([a for a in self.args if a == "Q"])


class Screened(Run):
    def run_with(self, *lines, on=("mail",)):
        self.out = stream(*lines)
        return self.provider.ask(ask.Request(text="Q", question="Q", connectors=tuple(on)))

    def test_a_clean_read_is_answered_and_named_on_the_used_line(self):
        r = self.run_with(use("1", f"{P}__outlook_email_search"), got("1", "three mails"), final("Answer"))
        self.assertEqual(r, "Answer")
        self.assertEqual(self.provider.last_used, "Used: Mail")

    def test_a_hidden_character_in_a_result_refuses_the_whole_run(self):
        r = self.run_with(use("1", f"{P}__outlook_email_search"), got("1", "ok​hidden"), final())
        self.assertEqual(r, ask.Failure(ac.CONNECTOR_REFUSED))
        self.assertIn("Not used", self.provider.last_used)

    def test_a_too_big_result_refuses(self):
        r = self.run_with(use("1", f"{P}__outlook_email_search"), got("1", "x" * (scr.MAX_RESULT + 1)), final())
        self.assertEqual(r, ask.Failure(ac.CONNECTOR_REFUSED))

    @mock.patch.object(scr, "MAX_TOTAL", 70000)
    def test_the_total_cap_refuses(self):
        r = self.run_with(use("1", f"{P}__outlook_email_search"), got("1", "x" * 40000), use("2", f"{P}__outlook_email_search"),
                          got("2", "y" * 40000), final())
        self.assertEqual(r, ask.Failure(ac.CONNECTOR_REFUSED))

    def test_a_write_tool_called_refuses_even_with_a_clean_result(self):
        r = self.run_with(use("1", f"{P}__outlook_send_mail"), got("1", "sent"), final())
        self.assertEqual(r, ask.Failure(ac.CONNECTOR_REFUSED))

    def test_a_write_tool_called_with_no_result_refuses(self):
        r = self.run_with(use("1", f"{P}__outlook_send_mail"), final())
        self.assertEqual(r, ask.Failure(ac.CONNECTOR_REFUSED))

    def test_a_tool_of_a_part_that_is_off_refuses(self):
        r = self.run_with(use("1", f"{P}__outlook_calendar_search"), got("1", "a meeting"), final())
        self.assertEqual(r, ask.Failure(ac.CONNECTOR_REFUSED))

    def test_a_result_that_is_not_text_refuses_and_a_list_of_text_blocks_is_joined(self):
        r = self.run_with(use("1", f"{P}__outlook_email_search"), got("1", [{"type": "image"}]), final())
        self.assertEqual(r, ask.Failure(ac.CONNECTOR_REFUSED))
        r = self.run_with(use("1", f"{P}__outlook_email_search"), got("1", [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]), final("Fine"))
        self.assertEqual(r, "Fine")

    def test_no_final_result_is_no_answer(self):
        r = self.run_with(use("1", f"{P}__outlook_email_search"), got("1", "x"))
        self.assertIsInstance(r, ask.Failure)

    def test_no_tool_used_is_answered(self):
        self.assertEqual(self.run_with(final("Plain")), "Plain")
        self.assertEqual(self.provider.last_used, "")

    def test_a_run_with_no_connector_is_not_screened(self):
        self.out = stream(use("1", f"{P}__outlook_send_mail"), final("Plain"))
        self.assertIsInstance(self.provider.ask(ask.Request(text="Q", question="Q")), ask.Failure)     # not the stream format: today's reader refuses it

    def test_tool_search_is_strict_about_its_query_its_id_and_its_result(self):
        mail = f"{P}__outlook_email_search"

        def run(query, *rest, ident="0", extra=None):
            inp = {"query": query}
            inp.update(extra or {})
            return cs.checked(stream(event("assistant", {"type": "tool_use", "id": ident, "name": "ToolSearch", "input": inp}), *rest, final()), {"Mail"})[0]
        self.assertTrue(run(mail, found("0", mail)))
        for query in ("outlook_email_search outlook_send_mail", "xoutlook_email_search", "outlook_email_search, send draft delete", "+outlook_email_search delete",
                      "Select:outlook_email_search,outlook_send_mail", "outlook_email_search\u200b", "outlook_email_s\u0435arch", " outlook_email_search",
                      "outlook_email_search" + " " * 400 + "outlook_send_mail", "x\nselect:outlook_send_mail outlook_email_search"):
            self.assertFalse(run(query), query)
        self.assertFalse(run(mail, got("0", "loaded")), "plain text is no longer a search result")
        self.assertFalse(run(mail, got("0", "bad\u202etext")), "a hidden character in a search result")
        self.assertFalse(run(mail, use("0", mail), got("0", "t")), "an id used twice")
        self.assertFalse(run(mail, ident=""), "no id")
        self.assertFalse(run(mail, event("user", {"type": "tool_result", "content": "zzz\u202e"}), ident=None), "a search without an id")

    def test_the_real_search_result_shape_passes_and_every_other_shape_fails(self):
        mail = f"{P}__outlook_email_search"
        cal = f"{P}__outlook_calendar_search"
        send = f"{P}__outlook_send_mail"

        def run(*rest, on=("Mail",)):
            q = event("assistant", {"type": "tool_use", "id": "0", "name": "ToolSearch", "input": {"query": f"select:{mail}"}})
            return cs.checked(stream(q, *rest, use("1", mail), got("1", "three mails"), final()), set(on))
        self.assertTrue(run(found("0", mail))[0], "the shape of a real run")
        self.assertTrue(run(found("0", mail, matches=False))[0], "content alone, exactly the reference")
        self.assertTrue(run(found("0", mail, content=[{"type": "tool_reference", "tool_name": mail}]))[0])
        for label, ev in (("another tool", found("0", send)),
                          ("a tool of a part that is Off", found("0", cal)),
                          ("a bare name", found("0", "outlook_email_search")),
                          ("two references, one not allowed", found("0", mail, send)),
                          ("an extra block", found("0", mail, content=[{"type": "tool_reference", "tool_name": mail}, {"type": "text", "text": "hi"}])),
                          ("an extra key in the block", found("0", mail, content=[{"type": "tool_reference", "tool_name": mail, "note": "x"}])),
                          ("text", found("0", mail, content="outlook_email_search")),
                          ("no content", found("0", mail, content=[])),
                          ("matches differ", found("0", mail, extra={"tool_use_result": {"matches": [send], "total_deferred_tools": 9}})),
                          ("matches with an extra", found("0", mail, extra={"tool_use_result": {"matches": [mail, send], "total_deferred_tools": 9}})),
                          ("an extra key in the result", found("0", mail, extra={"tool_use_result": {"matches": [mail], "total_deferred_tools": 9, "x": 1}})),
                          ("the total is not a number", found("0", mail, extra={"tool_use_result": {"matches": [mail], "total_deferred_tools": "9"}})),
                          ("a result with no matches key", found("0", mail, extra={"tool_use_result": {"total_deferred_tools": 9}}))):
            ok, _l, result = run(ev)
            self.assertFalse(ok, label)
            self.assertIsNone(result, label)
        self.assertFalse(run(found("0", mail), on=("Calendar",))[0], "Mail is Off")

    def test_tool_search_then_the_allowed_tool_passes_and_anything_else_fails(self):
        # The safe set keeps ToolSearch (the Mail tool needs it to load). Only a ToolSearch that asks for an allowed tool is let through.
        def search(i, query):
            return event("assistant", {"type": "tool_use", "id": i, "name": "ToolSearch", "input": {"query": query}})
        mail = f"{P}__outlook_email_search"
        for query in (f"select:{mail}", "select:outlook_email_search", "outlook_email_search"):
            ok, line, result = cs.checked(stream(search("0", query), found("0", mail), use("1", mail), got("1", "t"), final()), {"Mail"})
            self.assertTrue(ok, query)
            self.assertIsNotNone(result, query)
        ok, _l, _r = cs.checked(stream(search("0", f"select:{mail}"), final()), {"Mail"})
        self.assertTrue(ok, "a search alone is fine")
        for query in ("", "mail", "select:", f"select:{mail},{P}__outlook_send_mail", "select:Bash", "select:outlook_calendar_search", "x" * 600,
                      "select:mcp__other__outlook_email_search"):
            ok, _l, result = cs.checked(stream(search("0", query), got("0", "x"), final()), {"Mail"})
            self.assertFalse(ok, query)
            self.assertIsNone(result, query)
        for other in ("Bash", f"{P}__outlook_send_mail", "WebFetch"):
            ok, _l, result = cs.checked(stream(search("0", f"select:{mail}"), found("0", mail), use("1", other), got("1", "t"), final()), {"Mail"})
            self.assertFalse(ok, other)
            self.assertIsNone(result, other)
        ok, _l, _r = cs.checked(stream(event("assistant", {"type": "tool_use", "id": "0", "name": "ToolSearch", "input": "select:x"}), final()), {"Mail"})
        self.assertFalse(ok, "a search with no input object")
        ok, _l, _r = cs.checked(stream(search("0", f"select:{mail}"), final()), {"Calendar"})
        self.assertFalse(ok, "Mail is Off: a search for its tool is refused")

    def test_a_bare_tool_name_in_the_stream_is_refused(self):
        # The real stream names every tool mcp__<server>__<tool>; a bare allowed name (or another server's prefix) is not ours: the run is refused.
        for name in ("outlook_email_search", "mcp__other_server__outlook_email_search"):
            for calls in ((use("1", name), got("1", "t")), (use("1", name),)):
                ok, _line, result = cs.checked(stream(*calls, final()), {"Mail"})
                self.assertFalse(ok, (name, len(calls)))
                self.assertIsNone(result)

    def test_the_stream_reader_alone(self):
        ok, line, result = cs.checked(stream(use("1", f"{P}__outlook_email_search"), got("1", "t"), final()), {"Mail"})
        self.assertTrue(ok)
        self.assertEqual(json.loads(result)["result"], "The plan is on track.")
        self.assertEqual(cs.checked(b"\xff", {"Mail"}), (False, "", None))
        self.assertEqual(cs.checked(stream("not json", "[1]", final()), {"Mail"})[0], True)


class Switch(unittest.TestCase):
    """The service hands the provider the connectors that are On for this install and not Off for the project."""
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.db = plant.build_db(self.d / "clark.db")
        self.seen = []

        class Spy(ask.StubProvider):
            def ask(spy, request):
                self.seen.append(request.connectors)
                return super().ask(request)
        self.service = ask_service.AskService(self.db, Spy(reply="Fine.\nCITE: P1"), [])

    def sql(self, text, *args):
        s = open_store(self.db, onedrive_roots=[])
        try:
            s.con.execute(text, args)
            s.con.commit()
        finally:
            s.close()

    def ask(self):
        status, body = self.service.ask({"project": "PUB", "question": "What is the state of the plan?"})
        self.assertTrue(body["ok"], body)

    def test_a_new_install_has_none_on(self):
        self.ask()
        self.assertEqual(self.seen, [()])

    def test_on_reaches_the_request_in_the_stores_order(self):
        self.sql("UPDATE connector_switches SET is_on = 1 WHERE connector IN ('teams', 'mail')")
        self.ask()
        self.assertEqual(self.seen, [("mail", "teams")])

    def test_off_for_this_project_leaves_it_out_and_the_others_in(self):
        self.sql("UPDATE connector_switches SET is_on = 1 WHERE connector IN ('teams', 'mail')")
        self.sql("INSERT INTO project_connectors (project_id, connector, off) VALUES ('PUB', 'mail', 1)")
        self.ask()
        self.assertEqual(self.seen, [("teams",)])

    def test_off_everywhere_and_off_here_together_leave_none_and_the_call_is_todays(self):
        self.sql("UPDATE connector_switches SET is_on = 1 WHERE connector = 'mail'")
        self.sql("INSERT INTO project_connectors (project_id, connector, off) VALUES ('PUB', 'mail', 1)")
        self.ask()
        self.assertEqual(self.seen, [()])
        ask_connectors.clear_cache()
        p = ac.ClaudeCommand(places=(), env={}, limit=5)
        sent = []
        with mock.patch.object(p, "usable", return_value=(PATH, None)), \
                mock.patch.object(ac, "run", side_effect=lambda a, *_x, **_k: (sent.append(list(a)), ("ok", b"{}", 0))[1]):
            p.ask(ask.Request(text="Q", question="Q", connectors=self.seen[0]))
        self.assertEqual(sent, [ac.arguments(PATH, "", ask.RULES)])

    def test_a_switch_turned_off_again_reads_off(self):
        self.sql("UPDATE connector_switches SET is_on = 1 WHERE connector = 'mail'")
        self.ask()
        self.sql("UPDATE connector_switches SET is_on = 0 WHERE connector = 'mail'")
        self.ask()
        self.assertEqual(self.seen, [("mail",), ()])


if __name__ == "__main__":
    unittest.main()
