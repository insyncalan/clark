"""Row 1543 part 2 (AP11): the keys of the published report search as pure rules (logic/reportSearch.js stepAt, isShortcut, boxKey), no browser.

Run: python3 dev/run_tests.py test_report_search_keys_1543_node
Quick tier: the same esbuild bundle and node as test_report_search_1543_node.py (skipped when node is not on the machine). The box and the real keys are in
test_published_header_1543.py (test_published_search_keyboard).
"""
import json
import unittest

from test_report_search_1543_node import run


def ev(key, **o):
    return {"key": key, **o}


class Keys1543(unittest.TestCase):
    def test_step_wraps_at_both_ends(self):
        cases = [[0, -1, 1], [0, -1, -1], [3, -1, 1], [3, -1, -1], [3, 0, 1], [3, 2, 1], [3, 0, -1], [3, 1, 1], [3, 1, -1], [1, 0, 1], [1, 0, -1]]
        got = run(f"{json.dumps(cases)}.map(([n, at, d]) => RS.stepAt(n, at, d))", {})
        self.assertEqual(got, [-1, -1, 0, 2, 1, 0, 2, 2, 0, 0, 0], "none gives -1; none then Down is the first, Up the last; both ends wrap")

    def test_shortcut_is_ctrl_or_cmd_k_only(self):
        evs = [ev("k", ctrlKey=True), ev("K", metaKey=True), ev("k"), ev("k", ctrlKey=True, altKey=True), ev("k", ctrlKey=True, shiftKey=True),
               ev("k", ctrlKey=True, isComposing=True), ev("j", ctrlKey=True), ev("k", ctrlKey=True, metaKey=True), ev("k", metaKey=True), {}]
        got = run(f"{json.dumps(evs)}.map(RS.isShortcut)", {})
        self.assertEqual(got, [True, True, False, False, False, False, False, True, True, False], "Ctrl or Cmd with K, either case; a plain k, Alt, Shift, composing, another letter: no")

    def test_what_each_key_does_in_the_box(self):
        evs = [(ev("ArrowDown"), 3, -1), (ev("ArrowDown"), 3, 2), (ev("ArrowUp"), 3, -1), (ev("ArrowUp"), 3, 0), (ev("ArrowDown"), 0, -1),
               (ev("ArrowDown", altKey=True), 3, 0), (ev("ArrowDown", ctrlKey=True), 3, 0), (ev("ArrowUp", metaKey=True), 3, 1), (ev("ArrowUp", shiftKey=True), 3, 1),
               (ev("Enter"), 3, 1), (ev("Enter"), 3, -1), (ev("Enter"), 0, -1), (ev("Enter"), 3, 3), (ev("Enter"), 3, 0), (ev("Enter"), 3, 2),
               (ev("a"), 3, 1), (ev("Tab"), 3, 1), (ev("Enter", isComposing=True), 3, 1), (ev("ArrowDown", isComposing=True), 3, 1)]
        got = run(f"{json.dumps(evs)}.map(([e, n, at]) => RS.boxKey(e, n, at))", {})
        mv = lambda at: {"do": "move", "at": at}
        ch = lambda at: {"do": "choose", "at": at}
        self.assertEqual(got, [mv(0), mv(0), mv(2), mv(2), None, None, None, None, None, ch(1), None, None, None, ch(0), ch(2), None, None, None, None])

    def test_text_goes_back_to_an_earlier_value_first_result_chosen(self):
        got = run("""(() => {
          const n = 4; let q = "ZQ", pick = {q: "", at: 0};
          const first = RS.chosenAt(pick, q, n);
          pick = {q, at: n - 1};      // Down to the last result
          const last = RS.chosenAt(pick, q, n);
          pick = RS.pickOnType(pick); q = "ZQx";      // a character is added
          pick = RS.pickOnType(pick); q = "ZQ";      // and deleted again: the words are the old ones
          return [first, last, RS.chosenAt(pick, q, n)];
        })()""", {})
        self.assertEqual(got, [0, 3, 0], "Enter after the words went back to an earlier value picks the FIRST result, not the old pick")


if __name__ == "__main__":
    unittest.main()
