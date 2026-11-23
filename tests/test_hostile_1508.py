"""Hostile tests, row 1508 (PROJECT_SHARE = ask.BUDGET // 2). Logic only, no UI."""
import base64
import unittest
from unittest import mock

import test_ask_route as route
import test_ask_project_share_300k_td as mine
from clark import ask, ask_data, ask_files, ask_passages, ask_service


class Share(unittest.TestCase):
    def test_exact_int_600000_not_float(self):
        self.assertIs(type(ask_service.PROJECT_SHARE), int)
        self.assertEqual(ask_service.PROJECT_SHARE * 2, ask.BUDGET)
        self.assertEqual(ask_service.PROJECT_SHARE // 4, 150000)      # 150,000 tokens at 4 characters

    def test_share_below_max_request_and_leaves_room(self):
        self.assertLess(ask_service.PROJECT_SHARE, ask.MAX_REQUEST)
        self.assertEqual(ask.BUDGET - ask_service.PROJECT_SHARE, 600000)

    def test_exactly_at_share_is_sent_whole_and_one_over_is_cut(self):
        whole = mine.read(10, 4000, 10 ** 9)
        total = mine.size_of(whole)
        again = mine.read(10, 4000, total)
        self.assertEqual((again.left_out, mine.size_of(again)), (0, total))
        less = mine.read(10, 4000, total - 1)
        self.assertGreater(less.left_out, 0)
        self.assertLessEqual(mine.size_of(less), total - 1)

    def test_zero_budget_sends_nothing_and_says_so(self):
        got = mine.read(5, 500, 0)
        self.assertEqual(mine.size_of(got), 0)
        self.assertGreater(got.left_out, 0)


class Through(route.Base):
    def _spy(self, window=None, question="what is late?"):
        seen = {}
        real = ask_passages.folder_data
        real_project = ask_data.project_data

        def project(*a, **k):
            seen["project_used"] = real_project(*a, **k)
            return seen["project_used"]

        def folders(f, d, q, budget, *a, **k):
            seen["folder"] = budget
            return real(f, d, q, budget, *a, **k)
        if window is not None:
            self.provider.most_chars = lambda: window
        with mock.patch.object(ask_data, "project_data", side_effect=project) as spy, \
                mock.patch.object(ask_passages, "folder_data", side_effect=folders), \
                mock.patch.object(ask_service, "folders_for", return_value=["x"], create=True) as _f:
            status, got = self.question(question)
        return status, got, spy, seen

    def test_default_window_project_gets_600000_folders_get_the_rest(self):
        status, got, spy, seen = self._spy()
        self.assertEqual(status, 200, got)
        project = spy.call_args[0][3]
        self.assertEqual(project, 600000)
        self.assertIn("folder", seen)
        used = sum(len(p.text) for p in seen["project_used"].passages)
        self.assertEqual(seen["folder"], ask.budget_for(None) - used)      # the folders get exactly what the project left

    def test_small_window_caps_the_project_below_the_share(self):
        window = 100000
        status, got, spy, seen = self._spy(window)
        self.assertEqual(status, 200, got)
        self.assertEqual(spy.call_args[0][3], min(ask_service.PROJECT_SHARE, ask.budget_for(window)))
        self.assertLess(spy.call_args[0][3], ask_service.PROJECT_SHARE)

    def test_a_large_file_added_shrinks_the_project_share(self):
        big = "fiction " * 10000
        files = [{"name": "a.txt", "data": base64.b64encode(big.encode()).decode()}]
        added = sum(len(x.text) for x in ask_files.passages(files))
        self.assertGreater(added, 0)
        with mock.patch.object(ask_data, "project_data", wraps=ask_data.project_data) as spy:
            status, got = self.question("what is late?", files=files)
        self.assertEqual(status, 200, got)
        self.assertEqual(spy.call_args[0][3], min(ask_service.PROJECT_SHARE, ask.budget_for(None) - added))


if __name__ == "__main__":
    unittest.main()
