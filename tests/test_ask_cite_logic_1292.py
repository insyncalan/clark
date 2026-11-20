"""Row 1292 (reopened): where the numbered citations go (src/clark/page/src/edit/askCite.js), and the read line's words (askWords.js READ_LINE).

Run: python3 dev/run_tests.py test_ask_cite_logic_1292
Quick tier: no browser. The modules are bundled by the pinned esbuild and run in node (skips without node). Fictional IDs only.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import SRC

import esbuild  # noqa: E402  (dev/tools)

EDIT = SRC / "clark" / "page" / "src" / "edit"


def run_node(entry, name, probe):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "m.js"
        done = esbuild.run(["--bundle", "--format=iife", f"--global-name={name}", str(EDIT / entry), f"--outfile={out}"], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        script = Path(tmp) / "probe.js"
        script.write_text(out.read_text(encoding="utf-8") + f";\nconsole.log(JSON.stringify({probe}));", encoding="utf-8")
        got = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert got.returncode == 0, got.stderr
        return json.loads(got.stdout)


def cite(call):
    return run_node("askCite.js", "C", call)


def words(call):
    return run_node("askWords.js", "W", call)


class Sources(unittest.TestCase):
    def test_the_kind_of_an_id(self):
        self.assertEqual(cite('[C.kindOf("ABC-A-001"), C.kindOf("ABC-M-002"), C.kindOf("ABC-U-003"), C.kindOf("ABC-001")]'), ["item", "milestone", "usecase", "item"])

    def test_sources_are_numbered_in_the_order_given_each_once_and_a_use_case_has_none(self):
        got = cite('C.sourcesOf([{id:"ABC-A-002"},{id:"ABC-M-001"},{id:"ABC-A-002"},{id:"ABC-U-001"},{id:""},null,{id:5}])')
        self.assertEqual(got, [{"n": 1, "id": "ABC-A-002", "kind": "item"}, {"n": 2, "id": "ABC-M-001", "kind": "milestone"}])

    def test_no_items_no_sources(self):
        self.assertEqual(cite("[C.sourcesOf(undefined), C.sourcesOf([]), C.sourcesOf('x')]"), [[], [], []])

    def test_a_number_follows_each_whole_mention_and_nothing_else_changes(self):
        got = cite('C.pieces("ABC-A-001 is late; ABC-A-0011 and XABC-A-001 are not it, ABC-A-001 again.", [{n:1,id:"ABC-A-001",kind:"item"}])')
        self.assertEqual([p for p in got if p["t"] == "cite"], [{"t": "cite", "id": "ABC-A-001", "n": 1}] * 2)
        self.assertEqual("".join(p["v"] for p in got if p["t"] == "text"), "ABC-A-001 is late; ABC-A-0011 and XABC-A-001 are not it, ABC-A-001 again.", "the words are kept whole")

    def test_the_longer_id_wins_and_two_sources_get_their_own_numbers(self):
        got = cite('C.pieces("ABC-A-001 then ABC-A-0010.", [{n:1,id:"ABC-A-001"},{n:2,id:"ABC-A-0010"}])')
        self.assertEqual([p["n"] for p in got if p["t"] == "cite"], [1, 2])

    def test_with_no_sources_the_text_is_whole(self):
        self.assertEqual(cite('C.pieces("ABC-A-001 is late", [])'), [{"t": "text", "v": "ABC-A-001 is late"}])

    def test_an_id_with_regex_marks_is_not_read_as_a_pattern(self):
        self.assertEqual(cite('C.pieces("a.c and abc", [{n:1,id:"a.c"}])'), [{"t": "text", "v": "a.c"}, {"t": "cite", "id": "a.c", "n": 1}, {"t": "text", "v": " and abc"}])


class ReadLine(unittest.TestCase):
    def test_the_ticket_line(self):
        self.assertEqual(words('W.READ_LINE({work_items:17,milestones:6,use_cases:8,as_at:"17-11-2026"})'), "17 work items, 6 milestones and 8 use cases read · as at 17-11-2026")

    def test_one_is_singular_and_a_kind_with_none_is_left_out(self):
        self.assertEqual(words('W.READ_LINE({work_items:1,milestones:0,use_cases:1,as_at:"17-11-2026"})'), "1 work item and 1 use case read · as at 17-11-2026")
        self.assertEqual(words('W.READ_LINE({work_items:3,milestones:0,use_cases:0,as_at:""})'), "3 work items read")

    def test_nothing_read_or_a_bad_reply_says_nothing(self):
        self.assertEqual(words('[W.READ_LINE({work_items:0,milestones:0,use_cases:0,as_at:"17-11-2026"}), W.READ_LINE(null), W.READ_LINE("x"), W.READ_LINE({work_items:"9"})]'), ["", "", "", ""])


if __name__ == "__main__":
    unittest.main()
