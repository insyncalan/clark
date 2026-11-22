"""Row 1306 slice C4: the connector screen (src/clark/ask_connector_screen.py). Pure functions; nothing is read or sent.

Run: python3 dev/run_tests.py test_ask_connector_screen
"""
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401

from clark import ask_connector_screen as cs

HIDDEN = ["​", "‍", "﻿", "‮", "⁦", "\U000e0041", "\u0007", "\u0000", " ", "­", ""]


class Tools(unittest.TestCase):
    def test_allow_list_has_no_write_word(self):
        bad = ("send", "reply", "delete", "create", "update", "move", "rename", "upload", "forward", "post", "add", "complete",
               "set", "respond", "trash", "copy", "modify")
        for names in cs.ALLOWED_TOOLS.values():
            for n in names:
                words = n.lower().replace("-", "_").split("_")
                self.assertFalse(any(b in words for b in bad), n)

    def test_a_tool_of_another_server_with_an_allowed_name_is_not_allowed(self):
        # Row 1306: only mcp__<the part's own server>__<tool> passes; a prefix of any other server does not.
        self.assertTrue(cs.tool_allowed("mcp__claude_ai_Microsoft_365__outlook_email_search"))
        self.assertTrue(cs.tool_allowed("mcp__claude_ai_Todoist__find-tasks"))
        for t in ("mcp__other_server__outlook_email_search", "mcp__claude_ai_Todoist__outlook_email_search",
                  "mcp__claude_ai_Microsoft_365__find-tasks", "mcp__claude_ai_Microsoft_365_2__outlook_email_search"):
            self.assertFalse(cs.tool_allowed(t), t)
            self.assertIsNone(cs.part_of_tool(t), t)

    def test_writes_refused(self):
        for t in ("outlook_send_mail", "outlook_delete_event", "teams_send_chat_message", "sharepoint_delete_item",
                  "add-tasks", "outlook_create_draft", "Bash", "", None, 5):
            self.assertFalse(cs.tool_allowed(t), t)

    def test_reads_allowed_and_prefix(self):
        self.assertTrue(cs.tool_allowed("outlook_email_search"))
        self.assertTrue(cs.tool_allowed("mcp__claude_ai_Microsoft_365__outlook_email_search"))
        self.assertFalse(cs.tool_allowed("outlook_email_search_and_send"))

    def test_off_part(self):
        self.assertTrue(cs.tool_allowed("outlook_email_search", {"Mail"}))
        self.assertFalse(cs.tool_allowed("outlook_email_search", {"Calendar"}))
        self.assertFalse(cs.tool_allowed("outlook_email_search", set()))


class Screen(unittest.TestCase):
    def test_plain_used(self):
        s = cs.screen("outlook_email_search", "Hello\nthere\tfriend")
        self.assertTrue(s.used)
        self.assertEqual(s.text, "Hello\nthere\tfriend")

    def test_hidden_refused_not_stripped(self):
        for h in HIDDEN:
            s = cs.screen("outlook_email_search", "ab" + h + "cd")
            self.assertFalse(s.used, repr(h))
            self.assertEqual(s.reason, cs.REFUSED_HIDDEN)
            self.assertEqual(s.text, "")

    def test_non_text_refused(self):
        self.assertFalse(cs.screen("outlook_email_search", None).used)
        self.assertFalse(cs.screen("outlook_email_search", b"x").used)

    def test_size_caps(self):
        self.assertTrue(cs.screen("sharepoint_search", "a" * 40000).used)
        s = cs.screen("sharepoint_search", "a" * 40001)
        self.assertFalse(s.used)
        self.assertEqual(s.reason, cs.REFUSED_SIZE)

    def test_the_total_is_the_request_ceiling(self):
        self.assertEqual(cs.MAX_TOTAL, 1_230_000)                      # row 1293: the same as ask.MAX_REQUEST
        self.assertEqual(cs.MAX_RESULT, 40000)
        self.assertTrue(cs.screen("sharepoint_search", "a", 1_229_999).used)
        self.assertFalse(cs.screen("sharepoint_search", "a", 1_230_000).used)

    @mock.patch.object(cs, "MAX_TOTAL", 70000)
    def test_total_cap(self):
        res = [("sharepoint_search", "a" * 40000), ("sharepoint_search", "b" * 30000), ("sharepoint_search", "c")]
        out = cs.screen_all(res)
        self.assertEqual([s.used for s in out], [True, True, False])
        self.assertEqual(out[2].reason, cs.REFUSED_TOTAL)

    def test_refused_does_not_count_to_total(self):
        out = cs.screen_all([("sharepoint_search", "a​" * 30000), ("sharepoint_search", "b" * 40000),
                             ("sharepoint_search", "c" * 30000)])
        self.assertEqual([s.used for s in out], [False, True, True])

    def test_tool_and_off_refused(self):
        self.assertEqual(cs.screen("outlook_send_mail", "x").reason, cs.REFUSED_TOOL)
        self.assertEqual(cs.screen("outlook_email_search", "x", on_parts={"Todoist"}).reason, cs.REFUSED_OFF)


class Line(unittest.TestCase):
    def test_used_and_not(self):
        out = cs.screen_all([("outlook_email_search", "SECRET BODY"), ("teams_list_chats", "x​y"),
                             ("outlook_send_mail", "z")])
        ul = cs.used_line(out)
        self.assertEqual(ul.used, ("Mail",))
        self.assertEqual(ul.text, "Used: Mail. Not used: Teams chats has hidden characters")
        self.assertIn("unknown connector (tool not allowed)", ul.not_used)
        self.assertNotIn("not allowed", ul.text, "a tool on no part has no approved word, so it is data only")
        self.assertNotIn("SECRET", ul.text)

    def test_empty(self):
        self.assertEqual(cs.used_line([]).text, "")

    def line(self, *pairs):
        return cs.used_line(cs.screen_all(list(pairs))).text

    def test_the_used_line_is_the_connector_name_only_never_a_count(self):
        for pair, name in ((("outlook_email_search", '[1, 2, 3]'), "Mail"), (("outlook_email_search", '[]'), "Mail"),
                           (("outlook_calendar_search", '{"value": [1, 2]}'), "Calendar"), (("teams_list_chats", '[1, 2]'), "Teams"),
                           (("sharepoint_search", '[1]'), "SharePoint and OneDrive"), (("find-tasks", '[1, 2]'), "Todoist"),
                           (("outlook_email_search", "Subject: Lunch"), "Mail")):
            self.assertEqual(self.line(pair), f"Used: {name}", pair)

    def test_two_results_of_one_part_name_it_once(self):
        self.assertEqual(self.line(("outlook_email_search", "[1, 2]"), ("outlook_email_search", "[3]")), "Used: Mail")

    @mock.patch.object(cs, "MAX_TOTAL", 70000)
    def test_every_not_used_reason_has_its_approved_words(self):
        self.assertEqual(self.line(("outlook_email_search", "x" * 40001)), "Not used: Mail was too long")
        self.assertEqual(self.line(("outlook_email_search", "a\u200bb")), "Not used: Mail has hidden characters")
        self.assertEqual(self.line(("outlook_email_search", "x" * 35000), ("outlook_calendar_search", "y" * 35000),
                                   ("find-tasks", "z" * 35000)), "Used: Mail, Calendar. Not used: Tasks was over the total")
        self.assertEqual(cs.used_line([cs.screen("sharepoint_search", "x", on_parts={"Mail"})]).text, "Not used: Files is off")
        self.assertEqual(cs.used_line([cs.screen("find-tasks", "x", on_parts={"Mail"})]).text, "Not used: Tasks is off")
        self.assertEqual(cs.used_line([cs.screen("teams_list_chats", "x", on_parts={"Mail"})]).text, "Not used: Teams chats is off")
        self.assertEqual(cs.used_line([cs.screen("outlook_calendar_search", "x", on_parts={"Mail"})]).text, "Not used: Calendar is off")


class Provenance(unittest.TestCase):
    def test_flag(self):
        m = cs.mark("hi", "Mail")
        self.assertTrue(m.from_connector)
        self.assertTrue(cs.is_from_connector(m))
        self.assertFalse(cs.is_from_connector("hi"))


class PlainStaysAccepted(unittest.TestCase):
    def test_plain_text_used(self):
        for t in ("Hello world", "abc 123", "Meeting at 10:30, room B-2. (Bring notes; ok?) \"quoted\" it's 5% - done!",
                  "line one\nline two\ttabbed", "caf\u00e9 na\u00efve \u00fcber", "\u65e5\u672c\u8a9e\u306e\u30c6\u30ad\u30b9\u30c8",
                  "\U0001F600 \U0001F44D \U0001F389 ok", "\u2764 \u2705 done", "\u3042 \u3044"):
            r = cs.screen("outlook_email_search", t)
            self.assertTrue(r.used, repr(t))
            self.assertEqual(cs.hidden_count(t), 0, repr(t))

    def test_invisible_non_format_refused(self):
        for c in ("\ufe0f", "\ufe00", "\U000e0100", "\U000e01ef", "\u034f", "\u3164", "\u115f", "\u1160", "\u2800",
                  "\u180b", "\u180e", "\uffa0"):
            r = cs.screen("outlook_email_search", "a" + c + "b")
            self.assertFalse(r.used, repr(c))
            self.assertEqual(r.reason, cs.REFUSED_HIDDEN)
            self.assertIn("Mail has hidden characters", cs.used_line([r]).text)

    def test_only_mcp_server_prefix(self):
        self.assertFalse(cs.tool_allowed("mcp__srv__find-tasks"), "row 1306: a server that is not the part's own is refused")
        self.assertTrue(cs.tool_allowed("mcp__claude_ai_Todoist__find-tasks", {"Todoist"}))
        for t in ("evil__outlook_email_search", "x__y__outlook_email_search", "a__outlook_email_search",
                  "mcp__outlook_email_search", "mcp____outlook_email_search", "mcp__srv__x__outlook_email_search",
                  "MCP__srv__outlook_email_search", "mcp__s rv__outlook_email_search", "__outlook_email_search",
                  "mcp__srv__outlook_email_search__"):
            self.assertFalse(cs.tool_allowed(t), t)
            self.assertIsNone(cs.part_of_tool(t), t)


if __name__ == "__main__":
    unittest.main()
