"""Row 1306 slice C4: the connector screen (src/clark/ask_connector_screen.py). Pure functions; nothing is read or sent.

Run: python3 dev/run_tests.py test_ask_connector_screen
"""
import unittest

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
        self.assertEqual(ul.text, "Used: Read your mail. Not used: Teams chats has hidden characters")
        self.assertIn("unknown connector (tool not allowed)", ul.not_used)
        self.assertNotIn("not allowed", ul.text, "a tool on no part has no approved word, so it is data only")
        self.assertNotIn("SECRET", ul.text)

    def test_empty(self):
        self.assertEqual(cs.used_line([]).text, "")

    def line(self, *pairs):
        return cs.used_line(cs.screen_all(list(pairs))).text

    def test_a_countable_list_shows_its_count_with_the_right_noun(self):
        self.assertEqual(self.line(("outlook_email_search", '[1, 2, 3]')), "Used: Read your mail (3 messages)")
        self.assertEqual(self.line(("outlook_email_search", '[1]')), "Used: Read your mail (1 message)")
        self.assertEqual(self.line(("outlook_calendar_search", '{"value": [1, 2]}')), "Used: Read your calendar (2 events)")
        self.assertEqual(self.line(("outlook_calendar_search", '[1]')), "Used: Read your calendar (1 event)")
        self.assertEqual(self.line(("teams_list_chats", '[1, 2]')), "Used: Read your Teams chats (2 messages)")
        self.assertEqual(self.line(("sharepoint_search", '[1, 2]')), "Used: Read your files (2 files)")
        self.assertEqual(self.line(("sharepoint_search", '[1]')), "Used: Read your files (1 file)")
        self.assertEqual(self.line(("find-tasks", '[1, 2]')), "Used: Read your tasks (2 tasks)")
        self.assertEqual(self.line(("find-tasks", '[1]')), "Used: Read your tasks (1 task)")
        self.assertEqual(self.line(("outlook_email_search", '[]')), "Used: Read your mail (0 messages)")

    def test_an_answer_that_is_not_a_countable_list_shows_no_count(self):
        for text in ("Subject: Lunch", '{"a": 1}', '{"a": [1], "b": [2]}', '"x"', "3", "null"):
            self.assertEqual(self.line(("outlook_email_search", text)), "Used: Read your mail", text)

    def test_two_results_of_one_part_add_up_and_one_uncountable_drops_the_count(self):
        self.assertEqual(self.line(("outlook_email_search", "[1, 2]"), ("outlook_email_search", "[3]")),
                         "Used: Read your mail (3 messages)")
        self.assertEqual(self.line(("outlook_email_search", "[1, 2]"), ("outlook_email_search", "text")), "Used: Read your mail")

    def test_every_not_used_reason_has_its_approved_words(self):
        self.assertEqual(self.line(("outlook_email_search", "x" * 40001)), "Not used: Mail was too long")
        self.assertEqual(self.line(("outlook_email_search", "a\u200bb")), "Not used: Mail has hidden characters")
        self.assertEqual(self.line(("outlook_email_search", "x" * 35000), ("outlook_calendar_search", "y" * 35000),
                                   ("find-tasks", "z" * 35000)), "Used: Read your mail, Read your calendar. Not used: Tasks was over the total")
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


if __name__ == "__main__":
    unittest.main()
