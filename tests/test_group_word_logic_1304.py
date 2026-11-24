"""Row 1304: the pure rules of Group by in the Work items filter field (src/clark/page/src/logic/groupWord.js).

Run: python3 dev/run_tests.py test_group_word_logic_1304
Quick tier: no browser. The module is bundled by the pinned esbuild and run in node (skipped when node is not on the machine).
The page rules (the list, the tick, the icon label, the chip) are in test_group_in_filter_field.py, in a browser.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import SRC

import esbuild  # noqa: E402  (dev/tools)

LOGIC = SRC / "clark" / "page" / "src" / "logic"
ALL = ["workstream", "status", "due", "owner", "priority", "milestone", "type", "nothing"]


def run_node(probe):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "gw.js"
        done = esbuild.run(["--bundle", "--format=iife", "--global-name=GW", str(LOGIC / "groupWord.js"), f"--outfile={out}"], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        script = Path(tmp) / "probe.js"
        script.write_text(out.read_text(encoding="utf-8") + ";\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        got = subprocess.run([node, str(script)], capture_output=True, text=True, stdin=subprocess.DEVNULL)
        assert got.returncode == 0, got.stderr
        return json.loads(got.stdout)


class Rows(unittest.TestCase):
    def test_the_group_row_is_offered_for_an_empty_word_and_for_a_start_of_group(self):
        for word in ("", "g", "gro", "GROUP"):
            rows = run_node(f"GW.groupRows({json.dumps(word)}, 'workstream', false)")
            self.assertEqual([r["ins"] for r in rows], ["group:"], word)
            self.assertEqual(rows[0]["note"], "How the list is grouped")
        self.assertEqual(run_node("GW.groupRows('status', 'workstream', false)"), [])

    def test_after_group_the_eight_choices_with_exactly_the_current_one_ticked(self):
        rows = run_node("GW.groupRows('group:', 'status', false)")
        self.assertEqual([r["ins"] for r in rows], [f"group:{g}" for g in ALL])
        self.assertEqual([r["group"] for r in rows if r.get("checked")], ["status"])

    def test_on_the_board_seven_choices_and_nothing_is_ticked_as_status(self):
        rows = run_node("GW.groupRows('group:', GW.currentGroup('nothing', true), true)")
        self.assertEqual([r["group"] for r in rows], ALL[:7])
        self.assertEqual([r["group"] for r in rows if r.get("checked")], ["status"])

    def test_a_typed_start_narrows_the_choices(self):
        self.assertEqual([r["group"] for r in run_node("GW.groupRows('group:s', 'workstream', false)")], ["status"])


class Words(unittest.TestCase):
    def test_a_finished_word_is_taken_out_and_is_the_pick(self):
        got = run_node("GW.takeGroup('is:open group:owner x', 20, false)")
        self.assertEqual((got["id"], got["text"], got["board"]), ("owner", "is:open x", False))

    def test_an_unfinished_word_under_the_caret_is_not_taken(self):
        self.assertIsNone(run_node("GW.takeGroup('group:owner', 12, false)"))

    def test_nothing_on_the_board_is_refused_with_the_board_flag(self):
        got = run_node("GW.takeGroup('group:nothing ', 14, true)")
        self.assertTrue(got["board"])
        self.assertEqual(run_node("GW.BOARD_NOTHING"), "A board is always grouped, so choose one of its seven groupings.")

    def test_an_unfinished_word_is_stripped_from_the_applied_line(self):
        self.assertEqual(run_node("GW.strip('is:open group:sta', false)"), "is:open")
        self.assertEqual(run_node("GW.strip('is:open group:zzz', false)"), "is:open group:zzz")

    def test_mask_keeps_the_length_so_the_typed_letters_can_be_put_back(self):
        masked = run_node("GW.mask('group:sta x', false)")
        self.assertEqual(len(masked), len("group:sta x"))
        self.assertNotIn("group", masked)


class Chip(unittest.TestCase):
    def test_no_chip_at_the_start_grouping(self):
        self.assertIsNone(run_node("GW.groupChip('workstream', false)"))

    def test_chip_text_and_cross(self):
        self.assertEqual(run_node("GW.groupChip('status', false)"), {"text": "Group by: Status", "cross": True})
        self.assertEqual(run_node("GW.groupChip('owner', true)"), {"text": "Group by: Owner", "cross": False})


if __name__ == "__main__":
    unittest.main()
