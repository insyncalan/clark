"""Row 1277: the leave-save of the rich editor (RichText.jsx away()) under the event orders seen on macOS, modelled in node (no browser).

test_peek_milestone_1184 'description ... leaving saves' fails on macOS only: the focus moved to #peek .pk-title and the save never reached the store.
away() is the only path: onFocusOut -> (relatedTarget / document.hasFocus() guards) -> setTimeout 0 -> activeElement check -> finishRef.current(false).
Nothing retries it. This runs the real away() text (cut out of RichText.jsx) against a fake focus timeline.

Run: python3 dev/run_tests.py test_rich_away_order_node_1277
Quick tier: no browser; skipped when node is not on the machine.
"""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import SRC

SRC_FILE = SRC / "clark" / "page" / "src" / "edit" / "RichText.jsx"

DRIVER = r"""
const away = %(away)s;
const scenario = %(scenario)s;
const editor = { id: "editor" }, title = { id: "title" }, body = { id: "body" };
const inRoot = new Set([editor]);
const root = { current: { contains: (n) => inRoot.has(n) } };
const timers = [];
globalThis.setTimeout = (fn) => { timers.push(fn); return timers.length; };
const doc = { hasFocus: () => scenario.hasFocus, activeElement: scenario.activeAtEvent === "editor" ? editor : title };
globalThis.document = doc;
let finished = 0;
const finishRef = { current: () => { finished++; } };
const bubble = { current: null }, slashBox = { current: null };
const keep = { current: !!scenario.keep }, aiOpen = { current: false };
const run = new Function("root", "bubble", "slashBox", "keep", "aiOpen", "finishRef", "document", "setTimeout", "return " + away.replace(/^const away = /, ""))
  (root, bubble, slashBox, keep, aiOpen, finishRef, doc, globalThis.setTimeout);
run({ relatedTarget: scenario.to === "title" ? title : null });
if (scenario.activeAtTimer) doc.activeElement = scenario.activeAtTimer === "editor" ? editor : title;
while (timers.length) timers.shift()();
if (scenario.activeLater) doc.activeElement = title;     // too late: nothing looks again
console.log(JSON.stringify({ finished }));
"""


def away_text():
    src = SRC_FILE.read_text(encoding="utf-8")
    m = re.search(r"const away = \(e\) => \{.*?\n  \};", src, re.S)
    assert m, "RichText.jsx has no 'const away = (e) => {' block"
    return m.group(0).rstrip(";")


def saves(**scenario):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        js = Path(tmp) / "away.js"
        js.write_text(DRIVER % {"away": json.dumps(away_text()), "scenario": json.dumps(scenario)}, encoding="utf-8")
        done = subprocess.run([node, str(js)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)["finished"]


class AwayOrder(unittest.TestCase):
    def test_linux_order_focus_moves_to_the_title_and_the_field_saves(self):
        # relatedTarget is the title, the page has the focus, the timer sees the title as the active element.
        self.assertEqual(saves(to="title", hasFocus=True, activeAtEvent="title"), 1)

    def test_the_window_really_left_keeps_the_box_open(self):
        # No target, the page has lost the focus, the editor is still the active element: the person left the window, nothing is saved (RichText away()).
        self.assertEqual(saves(to=None, hasFocus=False, activeAtEvent="editor"), 0)

    def test_a_menu_or_link_box_closing_keeps_the_box_open(self):
        self.assertEqual(saves(to="title", hasFocus=True, activeAtEvent="title", keep=True), 0)

    def test_macos_order_no_related_target_and_hasFocus_false_but_the_focus_is_on_the_title(self):
        # HYPOTHESIS (not proven on a Mac): the title took the focus (activeElement is #peek .pk-title) but focusout carries no relatedTarget and
        # document.hasFocus() is false (an unfocused headless window). away() returns on the second guard and nothing retries: the save never happens.
        self.assertEqual(saves(to=None, hasFocus=False, activeAtEvent="title"), 1, "focus is on the title, outside the field: that is leaving")

    def test_macos_order_focusout_arrives_before_activeElement_moves(self):
        # HYPOTHESIS: focusout (the 'blur arriving first') fires while document.activeElement is still the editor; the setTimeout 0 check reads the editor,
        # takes it for 'still inside' and returns; the focus lands on the title a moment later and nothing looks again.
        self.assertEqual(saves(to="title", hasFocus=True, activeAtEvent="editor", activeAtTimer="editor", activeLater="title"), 1)


if __name__ == "__main__":
    unittest.main()
