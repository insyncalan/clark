"""Row 1306 slice C4b: the connector argument list (src/clark/ask_connector_args.py). These tests prove the argument list and the
fresh discovery, not claude's behaviour; the real proof is the probe run on a Mac with the connectors set up.

Run: python3 dev/run_tests.py test_ask_connector_args
"""
import unittest

from _paths import SRC  # noqa: F401

from clark import ask_connector_args as ca
from clark import ask_connectors as ac

M365 = "claude.ai Microsoft 365"
P = "mcp__claude_ai_Microsoft_365"
PARTS = ("mail", "calendar", "teams", "sharepoint")
DISC = [{"connector": c, "label": c, "server": M365} for c in PARTS]
DRIVE = {"connector": "other", "label": "", "server": "claude.ai Google Drive"}
TODO = {"connector": "todoist", "label": "Todoist", "server": "claude.ai Todoist"}

LIST_M365 = f"{M365}: https://example.invalid/m - ✓ Connected"
LIST_DRIVE = "claude.ai Google Drive: https://example.invalid/d - ✓ Connected"


class Args(unittest.TestCase):
    def test_one_on_one_off(self):
        a = ca.connector_args(DISC + [DRIVE], ["mail"])
        self.assertIn("--disallowedTools=mcp__claude_ai_Google_Drive", a)       # a known server is denied whole (the pinned list), found or not
        self.assertEqual(a[a.index(f"--allowedTools={P}__outlook_email_search") - 1], a[[i for i, x in enumerate(a) if x.count("__") == 1][-1]])
        self.assertIn(f"--disallowedTools={P}__outlook_send_mail", a)
        self.assertIn(f"--disallowedTools={P}__outlook_calendar_search", a)   # Off connector of the On server: read tools denied too

    def test_second_connector_denied_never_allowed(self):
        a = ca.connector_args(DISC + [DRIVE, TODO], ["mail", "todoist"])
        self.assertIn("--disallowedTools=mcp__claude_ai_Google_Drive", a)
        self.assertIn("--disallowedTools=mcp__claude_ai_Todoist", a)          # asked On, still no allow table
        allows = [x for x in a if x.startswith("--allowedTools=")]
        self.assertEqual(allows, [f"--allowedTools={P}__outlook_email_search"])
        for x in allows:
            self.assertNotIn("Todoist", x)
            self.assertNotIn("Google", x)

    def test_nothing_on_denies_everything(self):
        a = ca.connector_args(DISC + [DRIVE], [])
        self.assertEqual(a, ["--disallowedTools=mcp__claude_ai_Google_Drive", f"--disallowedTools={P}"])

    def test_no_strict_and_equals_form(self):
        a = ca.connector_args(DISC + [DRIVE], ["mail", "teams", "sharepoint", "calendar"])
        self.assertNotIn("--strict-mcp-config", a)
        for x in a:
            self.assertRegex(x, r"^--(allowedTools|disallowedTools)=mcp__[A-Za-z0-9_]+$")

    def test_writes_denied_by_name_and_never_allowed(self):
        a = ca.connector_args(DISC, list(PARTS) + ["people"])
        for t in ca.WRITE_TOOLS[M365]:
            self.assertIn(f"--disallowedTools={P}__{t}", a)
            self.assertNotIn(f"--allowedTools={P}__{t}", a)
        for t in ("outlook_send_mail", "teams_send_chat_message", "sharepoint_delete_item", "outlook_forward_mail",
                  "outlook_respond_to_event", "outlook_set_vacation", "sharepoint_upload_file", "outlook_create_event"):
            self.assertIn(f"--disallowedTools={P}__{t}", a)

    def test_allow_list_is_exact(self):
        a = ca.connector_args(DISC + [{"connector": "people", "label": "", "server": M365}], list(PARTS) + ["people"])
        got = {x.split("__", 3)[-1] for x in a if x.startswith("--allowedTools=")}
        self.assertEqual(got, {"outlook_email_search", "outlook_calendar_search", "outlook_find_available_time",
                               "find_meeting_availability", "chat_message_search", "teams_list_teams", "teams_list_channels",
                               "teams_list_chats", "teams_list_channel_messages", "sharepoint_search",
                               "sharepoint_folder_search", "search_people", "get_me"})
        for t in got:
            self.assertNotIn(f"--disallowedTools={P}__{t}", a)

    def test_write_word_in_table_names(self):
        bad = ("send", "reply", "delete", "create", "update", "move", "rename", "upload", "forward", "respond", "set", "copy",
               "modify", "trash")
        for tools in ca.READ_TOOLS[M365].values():
            for t in tools:
                self.assertFalse(set(t.split("_")) & set(bad), t)

    def test_deterministic_and_ordered(self):
        a = ca.connector_args(DISC + [DRIVE, TODO], ["mail", "calendar"])
        b = ca.connector_args(list(reversed(DISC + [DRIVE, TODO])), ("calendar", "mail"))
        self.assertEqual(a, b)
        a = a
        kinds = [x.startswith("--allowedTools=") for x in a]
        first_allow = kinds.index(True)
        self.assertTrue(all(x.count("__") == 1 and x.startswith("--disallowedTools=mcp__claude") for x in a[:first_allow]))
        self.assertEqual(a[first_allow:first_allow + 3][0], f"--allowedTools={P}__outlook_email_search")
        self.assertEqual(len(a), len(set(a)))

    def test_hostile_names_dropped_and_counted(self):
        hostile = ["--x", "a b\x07", "ev=il", " lead", "trail ", "two  spaces", "tab\tx", "zero​width", "é", "", "x" * 101,
                   "-lead", None, 5]
        disc = DISC + [{"connector": "other", "label": "", "server": h} for h in hostile]
        disc.append({"connector": "--bad", "label": "", "server": "claude.ai Fine"})
        disc.append("not a dict")
        a, dropped = ca.connector_plan(disc, ["mail"])
        a = a
        self.assertEqual(dropped, len(hostile) + 2)
        for x in a:
            self.assertRegex(x, r"^--(allowedTools|disallowedTools)=mcp__[A-Za-z0-9_]+$")
        self.assertEqual(a, ca.connector_plan(DISC, ["mail"])[0])

    def test_on_ids_must_be_clean(self):
        a = ca.connector_args(DISC, ["--mail", "mail=", 7, None])
        self.assertEqual(a, [f"--disallowedTools={P}"])

    def test_on_connector_not_discovered_gets_no_allow(self):
        a = ca.connector_args([DRIVE], ["mail"])
        self.assertEqual(a, ["--disallowedTools=mcp__claude_ai_Google_Drive"])

    def test_nothing_stored(self):
        before = (dict(vars(ca)), dict(ac._cache))
        ca.connector_args(DISC + [DRIVE], ["mail"])
        ca.build_call(["mail"], lambda: LIST_M365)
        self.assertEqual(len(ac._cache), len(before[1]))
        self.assertEqual(ac._cache, before[1])
        for k, v in before[0].items():
            self.assertIs(vars(ca)[k], v)

    def test_prefix(self):
        self.assertEqual(ca.prefix(M365), P)


class Fresh(unittest.TestCase):
    def setUp(self):
        ac.clear_cache()

    def test_new_connector_after_load_is_denied_on_second_call(self):
        outs = [LIST_M365, LIST_M365 + "\n" + LIST_DRIVE]
        run = lambda: outs.pop(0)  # noqa: E731
        first = ca.build_call(["mail"], run)
        second = ca.build_call(["mail"], run)
        self.assertTrue(first.ok and second.ok)
        self.assertIn("--disallowedTools=mcp__claude_ai_Google_Drive", first.args)       # a known server is denied whole even before it is found
        self.assertIn("--disallowedTools=mcp__claude_ai_Google_Drive", second.args)

    def test_stale_cache_not_used_and_not_refreshed(self):
        ac.list_found(lambda: LIST_M365)                       # fills the cache with M365 only
        cached = [dict(x) for x in ac._cache["value"]]
        at = ac._cache["at"]
        call = ca.build_call(["mail"], lambda: LIST_M365 + "\n" + LIST_DRIVE)
        self.assertIn("--disallowedTools=mcp__claude_ai_Google_Drive", call.args)
        self.assertEqual(ac._cache["value"], cached)
        self.assertEqual(ac._cache["at"], at)

    def test_every_call_runs_discovery(self):
        n = []
        run = lambda: n.append(1) or LIST_M365  # noqa: E731
        for _ in range(3):
            ca.build_call(["mail"], run)
        self.assertEqual(len(n), 3)

    def test_failure_refuses(self):
        def boom():
            raise RuntimeError("x")
        for run in (lambda: None, boom, lambda: "", lambda: "   \n", lambda: "garbage without the shape", lambda: b"bytes"):
            c = ca.build_call(["mail"], run)
            self.assertFalse(c.ok)
            self.assertEqual(c.args, ())
            with self.assertRaises(ValueError):
                ca.compose(["claude", "--strict-mcp-config"], c)

    def test_real_empty_differs_from_failure(self):
        self.assertEqual(ac.list_fresh(lambda: "No MCP servers configured."), (True, []))
        self.assertEqual(ac.list_fresh(lambda: None), (False, []))
        c = ca.build_call(["mail"], lambda: "No MCP servers configured.")
        self.assertFalse(c.ok)                                  # On but not found: refused too
        self.assertEqual(c.reason, "connector not found")

    def test_not_connected_server_is_still_denied(self):
        run = lambda: LIST_M365 + "\nclaude.ai Google Drive: https://example.invalid/d - ! Needs authentication"  # noqa: E731
        self.assertIn("--disallowedTools=mcp__claude_ai_Google_Drive", ca.build_call(["mail"], run).args)

    def test_nothing_on_skips_discovery(self):
        def never():
            raise AssertionError("ran")
        c = ca.build_call([], never)
        self.assertTrue(c.ok)
        self.assertFalse(c.connectors)
        base = ["claude", "--strict-mcp-config"]
        self.assertEqual(ca.compose(base, c), base)

    def test_compose_drops_strict_keeps_rest(self):
        c = ca.build_call(["mail"], lambda: LIST_M365 + "\n" + LIST_DRIVE)
        base = ["claude", "--print", "--tools", "", "--strict-mcp-config", "--system-prompt", "x"]
        out = ca.compose(base, c)
        self.assertNotIn("--strict-mcp-config", out)
        self.assertEqual(out[:4], ["claude", "--print", "--tools", ""])
        self.assertEqual(out[-len(c.args):], list(c.args))
        self.assertEqual(base[4], "--strict-mcp-config")        # input unchanged

    def test_fresh_keeps_only_names(self):
        ok, found = ac.list_fresh(lambda: LIST_M365 + "\n" + LIST_DRIVE.replace("example.invalid/d", "example.invalid/secret?t=TOK"))
        self.assertTrue(ok)
        self.assertNotIn("TOK", repr(found))
        self.assertIn({"connector": "other", "label": "", "server": "claude.ai Google Drive"}, found)


if __name__ == "__main__":
    unittest.main()
