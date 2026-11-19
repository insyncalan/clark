"""Row 1292 (S7): each answer has Copy (formatted, so it pastes with bold and lists), Ask again, and Up-arrow in an empty box brings back the last question.

Run: python3 dev/run_tests.py test_ask_actions_1292
Quick tier: no browser. The pure parts (askActions.js) are bundled by the pinned esbuild and run in node; the panel is checked as source.
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
PANEL = (EDIT / "AskPanel.jsx").read_text(encoding="utf-8")
WORDS = (EDIT / "askWords.js").read_text(encoding="utf-8")
ACTIONS = (EDIT / "askActions.js").read_text(encoding="utf-8") if (EDIT / "askActions.js").exists() else ""
CSS = (EDIT / "edit.css").read_text(encoding="utf-8")


def run_node(probe):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "aa.js"
        done = esbuild.run(["--bundle", "--format=iife", "--global-name=AA", str(EDIT / "askActions.js"), f"--outfile={out}"], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        script = Path(tmp) / "probe.js"
        script.write_text(out.read_text(encoding="utf-8") + ";\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        got = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert got.returncode == 0, got.stderr
        return json.loads(got.stdout)


def j(x):
    return json.dumps(x)


class Html(unittest.TestCase):
    def test_marks_become_elements_and_text_is_escaped(self):
        h = run_node("AA.answerHtml(" + j("**Late** items:\n- a <b>x</b> & y\n- `z`\n\n1. one\n2. two") + ")")
        self.assertIn("<strong>Late</strong>", h)
        self.assertIn("<ul><li>a &lt;b&gt;x&lt;/b&gt; &amp; y</li><li><code>z</code></li></ul>", h)
        self.assertIn("<ol><li>one</li><li>two</li></ol>", h)

    def test_heading_italic_pre_and_a_numbered_list_start(self):
        h = run_node("AA.answerHtml(" + j("## Plan\n*soft*\n\n```\nl1\n<l2>\n```\n\n3. three") + ")")
        self.assertIn("<h4>Plan</h4>", h)
        self.assertIn("<p><em>soft</em></p>", h)
        self.assertIn("<pre><code>l1\n&lt;l2&gt;</code></pre>", h)
        self.assertIn('<ol start="3"><li>three</li></ol>', h)

    def test_a_line_break_inside_a_paragraph_is_kept(self):
        self.assertIn("<p>a<br>b</p>", run_node("AA.answerHtml(" + j("a\nb") + ")"))

    def test_quotes_are_escaped_too(self):
        self.assertIn("&quot;q&quot;", run_node("AA.answerHtml(" + j('say "q"') + ")"))


class Plain(unittest.TestCase):
    def test_marks_are_dropped_and_lists_keep_their_markers(self):
        p = run_node("AA.answerPlain(" + j("## Plan\n**Late** and *soft* `z`\n\n- a\n- b\n\n2. two\n3. three\n\n```\ncode\n```") + ")")
        self.assertEqual(p, "Plan\n\nLate and soft z\n\n- a\n- b\n\n2. two\n3. three\n\ncode")

    def test_empty_text_is_empty(self):
        self.assertEqual(run_node("[AA.answerPlain(''), AA.answerPlain(null), AA.answerHtml('')]"), ["", "", ""])


class Turns(unittest.TestCase):
    T = [
        {"role": "user", "text": "first"},
        {"role": "assistant", "text": "a1"},
        {"role": "assistant", "kind": "problem", "text": "oops"},
        {"role": "user", "text": "second"},
        {"role": "assistant", "text": "a2"},
    ]

    def test_last_question_is_the_latest_user_turn(self):
        self.assertEqual(run_node("AA.lastQuestion(" + j(self.T) + ")"), "second")
        self.assertEqual(run_node("AA.lastQuestion([])"), "")
        self.assertEqual(run_node("AA.lastQuestion([{role:'assistant',text:'x'}])"), "")

    def test_last_question_ignores_a_user_turn_with_a_kind_keeps_its_spaces_and_sees_the_final_turn(self):
        self.assertEqual(run_node("AA.lastQuestion([{role:'user',text:'q'},{role:'user',kind:'note',text:'n'}])"), "q")
        self.assertEqual(run_node("AA.lastQuestion([{role:'user',text:' q '}])"), " q ")
        self.assertEqual(run_node("AA.lastQuestion([{role:'assistant',text:'a'},{role:'user',text:'last'}])"), "last")
        self.assertEqual(run_node("AA.questionFor([{role:'user',kind:'note',text:'n'},{role:'assistant',text:'a'}],1)"), "")

    def test_question_for_an_answer_is_the_user_turn_before_it(self):
        t = j(self.T)
        self.assertEqual(run_node("[AA.questionFor(" + t + ",1), AA.questionFor(" + t + ",4), AA.questionFor(" + t + ",0), AA.questionFor(" + t + ",9)]"), ["first", "second", "", ""])

    def test_only_a_plain_answer_has_the_buttons(self):
        r = run_node("[AA.hasActions({role:'assistant',text:'x'}), AA.hasActions({role:'assistant',text:'x',kind:'problem'}), AA.hasActions({role:'assistant',text:'',kind:'changes'}), AA.hasActions({role:'user',text:'x'}), AA.hasActions({role:'assistant',text:'  '})]")
        self.assertEqual(r, [True, False, False, False, False])


class Panel(unittest.TestCase):
    def test_words(self):
        for w in ('COPY = "Copy"', 'ASK_AGAIN = "Ask again"', "COPIED", "COPY_FAILED"):
            self.assertIn(w, WORDS)

    def test_copy_writes_html_and_plain_text_to_the_clipboard(self):
        self.assertIn("ClipboardItem", ACTIONS)
        self.assertIn('"text/html": new Blob([answerHtml(text)]', ACTIONS)
        self.assertIn('"text/plain": new Blob([answerPlain(text)]', ACTIONS)

    def test_buttons_are_in_the_panel_and_named(self):
        self.assertIn("data-ask-copy", PANEL)
        self.assertIn("data-ask-again", PANEL)
        self.assertIn("W.COPY", PANEL)
        self.assertIn("W.ASK_AGAIN", PANEL)
        self.assertIn(".ask-actions-row", CSS)

    def test_ask_again_is_not_offered_while_working_and_sends_the_question_again(self):
        self.assertIn('disabled={busy || state !== "ready"}', PANEL)
        self.assertIn("send(null, questionFor(list, list.indexOf(t)))", PANEL)

    def test_up_arrow_in_an_empty_box_recalls_the_last_question_and_only_there(self):
        self.assertIn('e.key === "ArrowUp"', PANEL)
        self.assertIn("!text &&", PANEL)
        self.assertIn("lastQuestion(turns.value)", PANEL)
        self.assertIn("!e.isComposing && !e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey)", PANEL)

    def test_the_result_of_a_copy_is_told_to_screen_readers(self):
        self.assertIn("setSaid(", PANEL)
        self.assertIn("setSaid(ok ? W.COPIED : W.COPY_FAILED)", PANEL)
        self.assertIn("if (!ok) setNote(W.COPY_FAILED)", PANEL)


if __name__ == "__main__":
    unittest.main()
