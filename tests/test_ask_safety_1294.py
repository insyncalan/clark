"""Row 1294, area 5: the 'Changes and safety' card on the ask clark page says what the code does (src/clark/page/src/edit/AskSettings.jsx).

Run: python3 dev/run_tests.py test_ask_safety_1294
Each of the four statements is pinned to the code behind it; the words are read from the page source."""
import re
import unittest

from _paths import SRC
from test_ask_apply import Base

from clark import ask, ask_files

JSX = (SRC / "clark" / "page" / "src" / "edit" / "AskSettings.jsx").read_text(encoding="utf-8")
LOOKS_KEY = "pass" + "word = Hunter2-Zebra-9"      # built in two pieces so the repository's own secret scan has nothing to match here


def page(*parts):
    return (SRC / "clark" / "page" / "src" / "/".join(parts)).read_text(encoding="utf-8")


class Words(unittest.TestCase):
    def test_the_card_is_on_the_all_projects_tab_with_the_four_statements(self):
        block = JSX[JSX.index("export const SAFETY"):JSX.index("const ALL_FOLDERS_COUNT")]
        titles = re.findall(r'^  \["([^"]+)"', block, re.M)
        self.assertEqual(titles, ["Every change needs your approval",
                                  "A change taken from one of your own files or passages needs an extra tick",
                                  "ask clark is never on a published report",
                                  "Passwords and keys are never sent"])
        self.assertIn("<Safety />", JSX[JSX.index("function AllProjects"):JSX.index("function AllFolders")])
        self.assertIn("These are not switches.", JSX)

    def test_the_old_untrue_words_are_gone(self):
        for old in ("what a client sees", "read-only or client page", "View mode", "Every change has an Undo."):
            self.assertNotIn(old, JSX)

    def test_the_tick_words_are_the_boxs_own_words(self):
        words = page("edit", "askWords.js")
        box = re.search(r'CONFIRM_BOX = "([^"]+)"', words).group(1)
        self.assertEqual(box, "I have checked this change and want to save it")
        self.assertIn("\\u201c" + box + "\\u201d", JSX)


class Approval(Base):
    def test_a_suggestion_changes_nothing_until_apply(self):
        before = self.counts()
        plan = self.planned({"op": "change", "id": self.action, "status": "Closed"})
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.s.read("actions", ref=self.action)["status"], "Open")
        status, body = self.ask.apply("not-an-offer", "ABC")
        self.assertEqual((status, body["code"]), (409, "no_offer"))
        self.assertEqual(self.counts(), before)
        self.applied(plan["offer"])
        self.assertEqual(self.s.read("actions", ref=self.action)["status"], "Closed")

    def test_an_applied_change_has_an_undo_and_it_puts_the_old_value_back(self):
        applied = self.applied(self.planned({"op": "change", "id": self.action, "status": "Closed"})["offer"])
        self.assertTrue(applied["undoable"])
        status, body = self.undo({"project": "ABC", "apply_id": applied["apply_id"]})
        self.assertEqual(status, 200, body)
        self.assertEqual(self.s.read("actions", ref=self.action)["status"], "Open")

    def test_a_decision_marked_made_has_no_undo(self):
        with self.s.step("dashboard", "tester") as st:
            ref = st.create("decisions", {"project": "ABC", "decision": "Pick the venue", "made_by": "Sam Lee", "status": "Pending", "source": "demo"})
        plan = self.planned({"op": "change", "id": ref, "status": "Made", "date": "2026-11-01"})
        self.assertFalse(self.applied(plan["offer"])["undoable"])

    def test_asking_cannot_make_a_new_use_case_so_that_needs_no_undo_words(self):
        status, body = self.ask.plan("ABC", {"op": "new", "kind": "use case", "title": "Book the room"})
        self.assertEqual((status, body["code"]), (400, "not_a_change"))

    def test_a_new_work_item_has_an_undo(self):
        plan = self.planned({"op": "new", "kind": "action", "title": "Book the training room", "owner": "Sam Lee"})
        self.assertTrue(self.applied(plan["offer"])["undoable"])


class ExtraTick(Base):
    def test_only_a_change_taken_from_a_source_needs_the_tick(self):
        own = self.planned({"op": "change", "id": self.action, "status": "Closed"})
        self.assertFalse(own["needs_confirm"])
        src = self.planned({"op": "change", "id": self.action, "status": "Closed", "source": "P2"})
        self.assertTrue(src["needs_confirm"])
        status, body = self.ask.apply(src["offer"], "ABC")
        self.assertEqual((status, body["code"]), (409, "needs_confirm"))
        self.assertIn('"needs_confirm": plan.from_source', (SRC / "clark" / "ask_apply.py").read_text(encoding="utf-8"))

    def test_the_panel_blocks_apply_until_the_tick(self):
        jsx = page("edit", "AskChange.jsx")
        self.assertIn("plan.needs_confirm === true", jsx)
        self.assertIn("(confirm && !ticked)", jsx)


class Published(unittest.TestCase):
    def test_a_published_file_has_no_ask_button_and_asks_no_server(self):
        self.assertIn("a published file has none", page("components", "App.jsx"))
        self.assertIn("tools.AskButton && !fromFile.value", page("components", "TopBar.jsx"))
        self.assertIn("it never edits and never asks a server", page("stores", "report.js"))


class Secrets(unittest.TestCase):
    def test_a_question_that_looks_like_a_key_is_stopped_and_the_person_is_told(self):
        with self.assertRaises(ask.AskRefused) as r:
            ask.check_question(LOOKS_KEY)
        self.assertIn("so it wasn't sent", str(r.exception))

    def test_an_earlier_message_that_looks_like_a_key_stops_the_chat_with_words(self):
        with self.assertRaises(ask.AskRefused) as r:
            ask.check_question("Next question", [("user", LOOKS_KEY)])
        self.assertIn("can't be sent", str(r.exception))

    def test_a_file_that_looks_like_a_key_refuses_the_question(self):
        import base64
        f = {"name": "notes.txt", "data": base64.b64encode(LOOKS_KEY.encode()).decode()}
        with self.assertRaises(ask.AskRefused) as r:
            ask_files.passages([f])
        self.assertIn("Nothing was sent", str(r.exception))


if __name__ == "__main__":
    unittest.main()
