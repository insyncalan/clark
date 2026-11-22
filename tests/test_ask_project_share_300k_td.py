"""Row 1508: the project's own data may take up to half of the 300,000-token request (PROJECT_SHARE = BUDGET // 2).

Run: python3 dev/run_tests.py test_ask_project_share_300k_td
Fictional data only.
"""
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401

from clark import ask, ask_data, ask_service, store as st
from test_ask_route import Base, CODE


class ProjectShare(Base):
    def fill_big(self, n, size):
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            with store.step("dashboard", "tester", place="menu") as s:
                for i in range(n):
                    s.create("actions", {"project": CODE, "description": f"ZQ-SHARE-{i:03d} " + "lorem ipsum " * (size // 12), "raised": "2026-10-01", "source": "demo", "status": "Open"})
        finally:
            store.close()

    def spy(self):
        seen = {}
        real = ask_data.project_data

        def project(*a, **k):
            seen["budget"] = a[3]
            out = real(*a, **k)
            seen["chars"] = sum(len(x.text) for x in out.passages)
            seen["left"] = out.left_out
            return out

        return seen, mock.patch.object(ask_data, "project_data", project)

    def test_project_share_is_half_the_budget(self):
        self.assertEqual(ask_service.PROJECT_SHARE, ask.BUDGET // 2)
        self.assertEqual(ask_service.PROJECT_SHARE, 600000)
        with mock.patch.object(ask, "BUDGET", 400000):      # written as the expression, so it follows the budget
            import importlib
            try:
                importlib.reload(ask_service)
                self.assertEqual(ask_service.PROJECT_SHARE, 200000)
            finally:
                importlib.reload(ask_service)

    def test_the_whole_request_stays_300000_tokens(self):
        self.assertEqual(ask.BUDGET, 1200000)
        self.assertEqual(ask.BUDGET // 4, 300000)
        self.assertEqual(ask.MAX_REQUEST, 1230000)

    def test_a_project_of_100000_characters_is_sent_whole(self):
        self.fill_big(28, 3600)                       # about 100,000 characters, under the 60-passage limit; 25,000 would have cut it
        seen, p = self.spy()
        with p:
            status, got = self.question("What is open?")
        self.assertEqual(status, 200, got)
        self.assertEqual(seen["budget"], 600000)      # the budget left after the project data and the file room (none here)
        self.assertGreater(seen["chars"], 100000)
        self.assertEqual(seen["left"], 0)
        self.assertFalse([n for n in got["notes"] if "left out" in n], got["notes"])

    def test_over_the_share_is_cut_and_the_note_is_true(self):
        many = [ask.Passage("p", "x" * 1000) for _ in range(700)]        # 700,000 characters
        kept, left = ask_data.choose(many, "q", ask_service.PROJECT_SHARE)
        self.assertEqual((len(kept), left), (600, 100))
        self.assertEqual(sum(len(p.text) for p in kept), 600000)
        self.assertEqual(ask_data.left_out_lines([("actions", len(kept), len(many))]),
                         ["Sent 600 of 700 actions (the closest to your question); 100 were left out."])
        self.fill_big(28, 3600)
        with mock.patch.object(ask_service, "PROJECT_SHARE", 50000):     # the route says the same through its notes
            status, got = self.question("What is open?")
        self.assertEqual(status, 200, got)
        lines = [n for n in got["notes"] if n.startswith("Sent ") and "left out." in n]
        self.assertTrue(lines, got["notes"])
        kinds = [n.split(" of ")[1].split(" ")[1] for n in lines]
        self.assertEqual(len(kinds), len(set(kinds)), "one line per cut kind")
        self.assertTrue(any(" actions " in n for n in lines), got["notes"])


if __name__ == "__main__":
    unittest.main()
