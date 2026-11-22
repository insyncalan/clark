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
const editor = { id: "editor" }, title = { id: "title" }, body = { id: "body" }, bub = { id: "bubble" }, slash = { id: "slash" };
const N = { editor, title, body, bubble: bub, slash, none: null };
const inRoot = new Set([editor]);
const root = { current: scenario.rootNull ? null : { contains: (n) => inRoot.has(n) } };
const timers = [];
globalThis.setTimeout = (fn, ms) => { timers.push([fn, ms || 0]); return timers.length; };
const doc = { hasFocus: () => scenario.hasFocus === undefined ? true : scenario.hasFocus, body, activeElement: N[scenario.activeAtEvent === undefined ? "title" : scenario.activeAtEvent] };
globalThis.document = doc;
let finished = 0;
const finishRef = { current: (v) => { if (v !== false) throw new Error("finish called with " + v); finished++; } };
const bubble = { current: scenario.bubble ? { contains: (n) => n === bub } : null }, slashBox = { current: scenario.slash ? { contains: (n) => n === slash } : null };
const keep = { current: !!scenario.keep }, aiOpen = { current: !!scenario.aiAtEvent };
const run = new Function("root", "bubble", "slashBox", "keep", "aiOpen", "finishRef", "document", "setTimeout", "return " + away.replace(/^const away = /, ""))
  (root, bubble, slashBox, keep, aiOpen, finishRef, doc, globalThis.setTimeout);
run({ relatedTarget: scenario.to === undefined || scenario.to === null ? null : N[scenario.to] });
if (scenario.aiAtTimer) aiOpen.current = true;
if (scenario.aiClearAtTimer) aiOpen.current = false;
if (scenario.activeAtTimer) doc.activeElement = N[scenario.activeAtTimer];
while (timers.some((t) => t[1] === 0)) timers.splice(timers.findIndex((t) => t[1] === 0), 1)[0][0]();   // the 0 ms timers first
if (scenario.activeLater) doc.activeElement = N[scenario.activeLater];     // the focus lands after them
while (timers.length) timers.shift()[0]();                // then the later ones (a re-look)
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
        done = subprocess.run([node, str(js)], capture_output=True, text=True, timeout=10)   # a look that keeps re-arming itself never ends: the timeout fails it
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

    # Row 1277 mutation sweep: every branch of away() has a test that fails when it is changed.
    def test_target_inside_the_field_or_its_boxes_never_saves(self):
        for to in ("editor", "bubble", "slash"):
            self.assertEqual(saves(to=to, bubble=True, slash=True, activeAtEvent="title"), 0, to)

    def test_target_in_a_box_that_is_not_there_is_outside(self):
        self.assertEqual(saves(to="bubble", activeAtEvent="title"), 1)
        self.assertEqual(saves(to="slash", activeAtEvent="title"), 1)

    def test_no_field_root_does_not_throw_and_saves(self):
        self.assertEqual(saves(to="title", rootNull=True), 1)

    def test_no_focus_no_target_stays_open_while_the_active_element_is_the_editor_a_box_the_body_or_nothing(self):
        for at in ("editor", "bubble", "slash", "body", "none"):
            self.assertEqual(saves(to=None, hasFocus=False, activeAtEvent=at, bubble=True, slash=True), 0, at)

    def test_no_focus_no_target_saves_when_the_focus_is_on_the_title(self):
        self.assertEqual(saves(to=None, hasFocus=False, activeAtEvent="title", bubble=True, slash=True), 1)

    def test_no_target_with_the_page_focused_saves_wherever_the_focus_was(self):
        # hasFocus true (or the guard is not about a window leaving): the 0 ms look decides.
        self.assertEqual(saves(to=None, hasFocus=True, activeAtEvent="editor", activeAtTimer="title"), 1)
        self.assertEqual(saves(to=None, hasFocus=True, activeAtEvent="title"), 1)

    def test_a_target_outside_saves_even_when_the_page_reports_no_focus(self):
        # the window guard is only for a focusout without a target.
        self.assertEqual(saves(to="title", hasFocus=False, activeAtEvent="editor", activeAtTimer="title"), 1)

    def test_no_focus_no_target_with_the_focus_in_the_field_returns_at_once_without_a_look(self):
        # the early return is the decision: a focus that lands outside a moment later is not acted on.
        self.assertEqual(saves(to=None, hasFocus=False, activeAtEvent="editor", activeAtTimer="title"), 0)
        self.assertEqual(saves(to=None, hasFocus=False, activeAtEvent="body", activeAtTimer="title"), 0)

    def test_an_ai_menu_open_at_the_event_keeps_the_box_open_even_if_it_is_closed_by_the_look(self):
        self.assertEqual(saves(to="title", aiAtEvent=True, aiClearAtTimer=True), 0)

    def test_an_open_ai_menu_keeps_the_box_open_at_the_event_and_at_the_look(self):
        self.assertEqual(saves(to="title", aiAtEvent=True), 0)
        self.assertEqual(saves(to="title", aiAtTimer=True), 0)
        self.assertEqual(saves(to="title", activeAtEvent="editor", activeAtTimer="editor", activeLater="title", aiAtTimer=True), 0)

    def test_the_look_keeps_the_box_open_when_the_focus_is_inside_the_field_or_a_box_and_saves_on_the_body_or_nothing(self):
        for at in ("editor", "bubble", "slash"):
            self.assertEqual(saves(to="title", activeAtEvent="title", activeAtTimer=at, bubble=True, slash=True), 0, at)
        for at in ("body", "none", "title"):
            self.assertEqual(saves(to="title", activeAtEvent="editor", activeAtTimer=at, bubble=True, slash=True), 1, at)

    def test_a_relook_happens_once_only_and_only_with_a_target(self):
        # still in the editor at the second look: saves nothing more, and no third look.
        self.assertEqual(saves(to="title", activeAtEvent="editor", activeAtTimer="editor"), 0)
        # no target: no re-look, so a late focus move is not acted on (the hasFocus guard already decided).
        self.assertEqual(saves(to=None, hasFocus=True, activeAtEvent="editor", activeAtTimer="editor", activeLater="title"), 0)

    def test_the_relook_sees_a_box_as_inside_and_the_body_as_outside(self):
        for at in ("bubble", "slash", "editor"):
            self.assertEqual(saves(to="title", activeAtEvent="editor", activeAtTimer="editor", activeLater=at, bubble=True, slash=True), 0, at)
        self.assertEqual(saves(to="title", activeAtEvent="editor", activeAtTimer="editor", activeLater="body"), 1)
        self.assertEqual(saves(to="title", activeAtEvent="editor", activeAtTimer="editor", activeLater="none"), 1)

    def test_the_relook_does_not_run_with_the_first_look(self):
        # the second look waits: the move that lands after the 0 ms timers is what it sees (and saves exactly once).
        self.assertEqual(saves(to="title", activeAtEvent="editor", activeAtTimer="editor", activeLater="title"), 1)


if __name__ == "__main__":
    unittest.main()
