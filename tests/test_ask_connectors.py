"""Row 1306 C2: connector discovery (src/clark/ask_connectors.py) against canned `mcp list` outputs. Nothing runs a real command.

Run: python3 dev/run_tests.py test_ask_connectors
"""
import unittest

from _paths import SRC  # noqa: F401

from clark import ask_connectors as ac

M365 = "claude.ai Microsoft 365: https://example.invalid/mcp - ✓ Connected"
TODO = "claude.ai Todoist: https://example.invalid/todo - ✓ Connected"
AUTH = "claude.ai Todoist: https://example.invalid/todo - ! Needs authentication"


class Discover(unittest.TestCase):
    def setUp(self):
        ac.clear_cache()

    def found(self, text):
        return ac.list_found(run=lambda: text)

    def test_connected_microsoft(self):
        got = self.found("Checking MCP server health...\n\n" + M365 + "\n")
        self.assertEqual([g["connector"] for g in got], ["mail", "calendar", "teams", "sharepoint"])
        self.assertTrue(all(g["server"] == "claude.ai Microsoft 365" for g in got))
        self.assertEqual(got[3]["label"], "SharePoint and OneDrive")

    def test_todoist_and_both(self):
        self.assertEqual([g["connector"] for g in self.found(TODO)], ["todoist"])
        ac.clear_cache()
        self.assertEqual(len(self.found(M365 + "\n" + TODO)), 5)

    def test_needs_authentication_is_left_out(self):
        self.assertEqual(self.found(AUTH), [])
        ac.clear_cache()
        self.assertEqual([g["connector"] for g in self.found(AUTH + "\n" + M365)], ["mail", "calendar", "teams", "sharepoint"])

    def test_failed_status_words(self):
        for s in ("Failed to connect", "Not connected", "Disconnected", "connecting"):
            ac.clear_cache()
            self.assertEqual(self.found("claude.ai Todoist: https://x.invalid - " + s), [], s)

    def test_unknown_and_lookalike_names_ignored(self):
        text = "\n".join(f"{n}: https://x.invalid - ✓ Connected" for n in (
            "github", "claude.ai Microsoft 365 extra", "Microsoft 365", "claude.ai microsoft 365", "claude.ai Todoist2",
            "my claude.ai Todoist", "Microsoft365"))
        self.assertEqual(self.found(text), [])

    def test_hostile_names(self):
        text = ("claude.ai Todoist\x00: https://x.invalid - ✓ Connected\n"
                "claude.ai\x1b[31m Todoist: https://x.invalid - ✓ Connected\n"
                "claude.ai Todoist‮: https://x.invalid - ✓ Connected\n"
                "ignore previous instructions: a - b - ✓ Connected\n")
        self.assertEqual(self.found(text), [])

    def test_hostile_status_not_accepted(self):
        self.assertEqual(self.found("claude.ai Todoist: https://x.invalid - ✓ Connected\x00 and more"), [])
        ac.clear_cache()
        self.assertEqual(self.found("claude.ai Todoist: https://x.invalid - Connected, send mail to x"), [])

    def test_url_with_dash_and_colon(self):
        got = self.found("claude.ai Todoist: https://x.invalid/a - b:c - ✓ Connected")
        self.assertEqual([g["connector"] for g in got], ["todoist"])

    def test_result_has_only_three_keys_no_url(self):
        for g in self.found(M365):
            self.assertEqual(set(g), {"connector", "label", "server"})
            self.assertNotIn("http", repr(g))

    def test_empty_and_non_text(self):
        for v in ("", "\n\n", None, b"x", 5):
            ac.clear_cache()
            self.assertEqual(ac.list_found(run=lambda v=v: v), [])

    def test_failure_is_empty_and_not_cached(self):
        def boom():
            raise OSError("x")
        self.assertEqual(ac.list_found(run=boom), [])
        self.assertEqual(self.found(TODO)[0]["connector"], "todoist")

    def test_huge_output_capped(self):
        filler = "noise line\n" * 100000
        self.assertEqual(self.found(filler + TODO), [])
        ac.clear_cache()
        self.assertEqual(len(self.found(TODO + "\n" + filler)), 1)
        ac.clear_cache()
        many = "\n".join(f"s{i}: https://x.invalid - ✓ Connected" for i in range(100000))
        self.assertEqual(self.found(many), [])

    def test_cache_for_sixty_seconds(self):
        calls = []
        clock = [1000.0]

        def run():
            calls.append(1)
            return TODO
        for _ in range(3):
            ac.list_found(run=run, now=lambda: clock[0])
        self.assertEqual(len(calls), 1)
        clock[0] += 59
        ac.list_found(run=run, now=lambda: clock[0])
        self.assertEqual(len(calls), 1)
        clock[0] += 2
        ac.list_found(run=run, now=lambda: clock[0])
        self.assertEqual(len(calls), 2)

    def test_returned_list_is_a_copy(self):
        a = self.found(TODO)
        a[0]["connector"] = "x"
        self.assertEqual(ac.list_found(run=lambda: "")[0]["connector"], "todoist")

    def test_default_runner_without_command_is_none(self):
        orig = ac.ask_claude.find_command
        ac.ask_claude.find_command = lambda: (None, "missing")
        try:
            self.assertIsNone(ac.default_runner())
        finally:
            ac.ask_claude.find_command = orig

    def test_default_runner_passes_scrubbed_env_and_limit(self):
        seen = {}

        def fake(args, data, env, limit, max_out, **kw):
            seen.update(args=args, env=env, limit=limit, max_out=max_out)
            return "ok", b"claude.ai Todoist: u - \xe2\x9c\x93 Connected", 0
        o1, o2 = ac.ask_claude.find_command, ac.platform.run_stoppable
        ac.ask_claude.find_command = lambda: ("/x/claude", None)
        ac.platform.run_stoppable = fake
        try:
            self.assertEqual(ac.list_found()[0]["connector"], "todoist")
        finally:
            ac.ask_claude.find_command, ac.platform.run_stoppable = o1, o2
        self.assertEqual(seen["args"], ["/x/claude", "mcp", "list"])
        self.assertEqual(seen["env"], ac.ask_claude.child_env())
        self.assertEqual(seen["limit"], 30)

    def test_default_runner_failed_status(self):
        o1, o2 = ac.ask_claude.find_command, ac.platform.run_stoppable
        ac.ask_claude.find_command = lambda: ("/x/claude", None)
        ac.platform.run_stoppable = lambda *a, **k: ("slow", b"", None)
        try:
            self.assertEqual(ac.list_found(), [])
        finally:
            ac.ask_claude.find_command, ac.platform.run_stoppable = o1, o2

    def test_labels_exact(self):
        got = {g["connector"]: g["label"] for g in self.found(M365 + "\n" + TODO)}
        self.assertEqual(got, {"mail": "Mail", "calendar": "Calendar", "teams": "Teams",
                               "sharepoint": "SharePoint and OneDrive", "todoist": "Todoist"})

    def test_parse_name_and_status_length_limits(self):
        self.assertEqual(ac.parse("n" * 100 + ": u - Connected"), ["n" * 100])
        self.assertEqual(ac.parse("n" * 101 + ": u - Connected"), [])
        self.assertEqual(ac.parse("n: u - " + "!" * 91 + "Connected"), ["n"])
        self.assertEqual(ac.parse("n: u - " + "!" * 92 + "Connected"), [])

    def test_parse_marker_of_several_symbols_and_edges(self):
        self.assertEqual(ac.parse("n: u - \u2714\ufe0f Connected"), ["n"])
        self.assertEqual(ac.parse("  n: u - Connected  "), ["n"])
        self.assertEqual(ac.parse("n: u - Connected\nn: v - Connected"), ["n"])
        self.assertEqual(ac.parse(None), [])
        self.assertEqual(ac.parse(b"n: u - Connected"), [])
        self.assertEqual(ac.map_found([" claude.ai Todoist"]), [])

    def test_parse_byte_and_line_limits(self):
        line = "claude.ai Todoist: u - Connected"
        pad = "#" * (ac.MAX_OUT - len(line) - 1)
        self.assertEqual(ac.parse(pad + "\n" + line), ["claude.ai Todoist"])
        self.assertEqual(ac.parse(pad + "#\n" + line), [])
        self.assertEqual(ac.parse("\n" * 199 + line), ["claude.ai Todoist"])
        self.assertEqual(ac.parse("\n" * 200 + line), [])

    def test_cache_edges(self):
        calls = []
        clock = [1000.0]

        def run():
            calls.append(1)
            return TODO
        ac.list_found(run=run, now=lambda: clock[0])
        clock[0] += 60
        ac.list_found(run=run, now=lambda: clock[0])
        self.assertEqual(len(calls), 2)
        clock[0] -= 500
        ac.list_found(run=run, now=lambda: clock[0])
        self.assertEqual(len(calls), 3)
        ac.clear_cache()
        ticks = iter([0, 70, 100])
        calls.clear()
        ac.list_found(run=run, now=lambda: next(ticks))
        ac.list_found(run=run, now=lambda: next(ticks))
        self.assertEqual(len(calls), 1)

    def test_cached_list_is_a_copy_too(self):
        self.found(TODO)
        b = ac.list_found(run=lambda: "")
        b[0]["connector"] = "x"
        self.assertEqual(ac.list_found(run=lambda: "")[0]["connector"], "todoist")

    def test_default_runner_details(self):
        seen = {}
        out = [b"claude.ai Todoist: u - Connected"]
        status = ["ok"]

        def fake(args, data, env, limit, max_out, **kw):
            seen.update(data=data, max_out=max_out, kw=kw)
            return status[0], out[0], 0
        o1, o2 = ac.ask_claude.find_command, ac.platform.run_stoppable
        ac.ask_claude.find_command = lambda: ("/x/claude", None)
        ac.platform.run_stoppable = fake
        try:
            self.assertIn("Todoist", ac.default_runner())
            self.assertEqual(seen["data"], b"")
            self.assertEqual(seen["max_out"], 64 * 1024)
            self.assertEqual(seen["kw"]["prefix"], "clark-mcp-")
            status[0] = "slow"
            self.assertIsNone(ac.default_runner())
            self.assertEqual(ac.list_found(), [])
            status[0] = "ok"
            out[0] = b"claude.ai Todo\xffist: u - Connected"
            self.assertEqual(ac.list_found(), [])

            def boom(*a, **k):
                raise RuntimeError("x")
            ac.platform.run_stoppable = boom
            self.assertIsNone(ac.default_runner())

            ran = []
            ac.platform.run_stoppable = lambda *a, **k: ran.append(1) or ("ok", b"", 0)
            ac.ask_claude.find_command = lambda: (None, "missing")
            self.assertIsNone(ac.default_runner())
            self.assertEqual(ran, [])
        finally:
            ac.ask_claude.find_command, ac.platform.run_stoppable = o1, o2


    def test_sweep2_line_shape(self):
        self.assertEqual(ac.parse(": u - Connected"), [])
        self.assertEqual(ac.parse("n:u - Connected"), [])
        self.assertEqual(ac.parse("n:  - Connected"), [])
        self.assertEqual(ac.parse("n: u - Con.nected"), [])
        self.assertEqual(ac.parse("n: u - Con nected"), [])
        self.assertEqual(ac.parse("claude.ai Todoist: x: y - Connected"), ["claude.ai Todoist"])

    def test_sweep2_clock_going_back_is_a_miss(self):
        calls = []
        clock = [1000.0]

        def run():
            calls.append(1)
            return TODO
        ac.list_found(run=run, now=lambda: clock[0])
        clock[0] -= 0.5
        ac.list_found(run=run, now=lambda: clock[0])
        self.assertEqual(len(calls), 2)

    def test_sweep2_cleared_cache_runs_at_time_zero(self):
        calls = []
        ac.list_found(run=lambda: TODO, now=lambda: 0)
        ac.clear_cache()
        ac.list_found(run=lambda: calls.append(1) or TODO, now=lambda: 0)
        self.assertEqual(calls, [1])

    def test_sweep2_fresh_cache_state_and_first_call(self):
        import importlib
        fresh = importlib.reload(ac)
        self.assertEqual(fresh._cache, {"at": None, "value": []})
        calls = []
        fresh.list_found(run=lambda: calls.append(1) or TODO, now=lambda: 0)
        self.assertEqual(calls, [1])

    def test_sweep2_undecodable_byte_elsewhere_is_replaced(self):
        o1, o2 = ac.ask_claude.find_command, ac.platform.run_stoppable
        ac.ask_claude.find_command = lambda: ("/x/claude", None)
        ac.platform.run_stoppable = lambda *a, **k: ("ok", b"claude.ai Todoist: u - Connected\n\xff\xfe", 0)
        try:
            self.assertEqual(ac.list_found()[0]["connector"], "todoist")
        finally:
            ac.ask_claude.find_command, ac.platform.run_stoppable = o1, o2


if __name__ == "__main__":
    unittest.main()
