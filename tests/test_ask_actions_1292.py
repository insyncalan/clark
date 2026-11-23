"""Row 1292, feature 9: Copy, Ask again and Up-arrow recall in ask clark (askActions.js, AskPanel.jsx).

Run: python3 dev/run_tests.py test_ask_actions_1292
Part 1 (quick, node): what Copy puts on the clipboard (formatted and plain), the question Ask again sends, the Up-arrow walk.
Part 2 (real browser, 1400 and 900 px, Classic): the two links under an answer, Copy writes both forms, Ask again sends the same
question again, Up-arrow in an empty box brings back the last question and then the one before. Cards shows no links.
Fictional text only.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import SRC

import esbuild  # noqa: E402  (dev/tools)
from test_ask_first_run_classic_1352 import Classic
from test_server import chrome

EDIT = SRC / "clark" / "page" / "src" / "edit"
ANSWER = "**Health:** steady.\n\n## Concerns\n- Supplier <b>late</b>\n- Kit late\n\n1. First\n2. Second"


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


def run_node_async(expr):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "aa.js"
        done = esbuild.run(["--bundle", "--format=iife", "--global-name=AA", str(EDIT / "askActions.js"), f"--outfile={out}"], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        script = Path(tmp) / "probe.js"
        script.write_text(out.read_text(encoding="utf-8") + ";\n(" + expr + ").then((v) => console.log(JSON.stringify(v)));", encoding="utf-8")
        got = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert got.returncode == 0, got.stderr
        return json.loads(got.stdout)


class Logic(unittest.TestCase):
    def test_html_is_formatted_and_every_word_is_escaped(self):
        h = run_node("AA.answerHtml(" + json.dumps(ANSWER) + ")")
        self.assertEqual(h, "<p><strong>Health:</strong> steady.</p><h4>Concerns</h4><ul><li>Supplier &lt;b&gt;late&lt;/b&gt;</li><li>Kit late</li></ul><ol><li>First</li><li>Second</li></ol>")

    def test_plain_has_no_marks_and_keeps_lists(self):
        t = run_node("AA.answerPlain(" + json.dumps(ANSWER) + ")")
        self.assertEqual(t, "Health: steady.\n\nConcerns\n\n- Supplier <b>late</b>\n- Kit late\n\n1. First\n2. Second")

    def test_both_forms_go_to_the_clipboard_and_a_refusal_is_false(self):
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("no node")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "aa.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=AA", str(EDIT / "askActions.js"), f"--outfile={out}"], capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = Path(tmp) / "probe.js"
            script.write_text(out.read_text(encoding="utf-8") + """;
(async () => {
  const w = []; class Item { constructor(o) { this.o = o; } }
  const ok = await AA.copyAnswer("Hi **there**", { clipboard: { write: async (l) => { w.push(Object.keys(l[0].o)); } } }, Item);
  const no = await AA.copyAnswer("Hi", { clipboard: { write: async () => { throw new Error("x"); } } }, Item);
  const plain = []; await AA.copyAnswer("Hi **there**", { clipboard: { writeText: async (t) => { plain.push(t); } } }, null);
  console.log(JSON.stringify({ ok, no, w, plain }));
})();""", encoding="utf-8")
            got = subprocess.run([node, str(script)], capture_output=True, text=True)
            assert got.returncode == 0, got.stderr
        self.assertEqual(json.loads(got.stdout), {"ok": True, "no": False, "w": [["text/html", "text/plain"]], "plain": ["Hi there"]})

    def test_ask_again_names_the_question_before_the_answer(self):
        t = [{"role": "user", "text": "a"}, {"role": "assistant", "text": "x"}, {"role": "user", "text": "b"}, {"role": "assistant", "text": "y"}]
        self.assertEqual(run_node("[AA.questionBefore(" + json.dumps(t) + ", 1), AA.questionBefore(" + json.dumps(t) + ", 3), AA.questionBefore([], 0)]"), ["a", "b", ""])

    def test_up_arrow_walks_back_and_stops_at_the_oldest(self):
        t = [{"role": "user", "text": "a"}, {"role": "assistant", "text": "x"}, {"role": "user", "text": "b"}, {"role": "assistant", "text": "y", "kind": "note"}]
        got = run_node("(() => { const t = " + json.dumps(t) + "; const s1 = AA.recallStep(t, 0), s2 = AA.recallStep(t, s1.at), s3 = AA.recallStep(t, s2.at); return [s1, s2, s3, AA.recallStep([], 0)]; })()")
        self.assertEqual(got, [{"text": "b", "at": 1}, {"text": "a", "at": 2}, {"text": "a", "at": 2}, None])

    def test_blank_and_kind_turns_are_not_questions(self):
        t = [{"role": "user", "text": "a"}, {"role": "user", "text": "  "}, {"role": "user", "text": "k", "kind": "note"}, {"role": "assistant", "text": "x"}]
        j = json.dumps(t)
        self.assertEqual(run_node("[AA.questionBefore(" + j + ", 3), AA.recallStep(" + j + ", 0), AA.recallStep(" + j + ", 5)]"), ["a", {"text": "a", "at": 1}, {"text": "a", "at": 1}])
        self.assertEqual(run_node("[AA.questionBefore([{role: 'user', text: ''}, {role: 'assistant', text: 'x'}], 1), AA.recallStep([{role: 'user', text: ' '}], 0)]"), ["", None])

    def test_actions_only_under_an_answer_in_words(self):
        got = run_node("[{role:'assistant',text:'Hi'}, {role:'assistant',text:''}, {role:'assistant',text:'  '}, {role:'assistant',text:'x',kind:'changes'}, {role:'user',text:'q'}, {role:'assistant'}].map(AA.hasActions)")
        self.assertEqual(got, [True, False, False, False, False, False])

    def test_copy_without_a_clipboard_is_false_and_write_missing_falls_back(self):
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("no node")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "aa.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=AA", str(EDIT / "askActions.js"), f"--outfile={out}"], capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = Path(tmp) / "probe.js"
            script.write_text(out.read_text(encoding="utf-8") + """;
(async () => {
  class Item { constructor(o) { this.o = o; } }
  const plain = [];
  const none = await AA.copyAnswer("Hi", {}, Item);
  const nonav = await AA.copyAnswer("Hi");
  const fb = await AA.copyAnswer("Hi **x**", { clipboard: { writeText: async (t) => { plain.push(t); } } }, Item);
  console.log(JSON.stringify({ none, nonav, fb, plain }));
})();""", encoding="utf-8")
            got = subprocess.run([node, str(script)], capture_output=True, text=True)
            assert got.returncode == 0, got.stderr
        self.assertEqual(json.loads(got.stdout), {"none": False, "nonav": False, "fb": True, "plain": ["Hi x"]})

    def test_missing_clipboard_item_with_write_present_uses_plain_text(self):
        got = run_node_async("""(async () => {
  const plain = [], wrote = [];
  const ok = await AA.copyAnswer("Hi **x**", { clipboard: { write: async () => { wrote.push(1); }, writeText: async (t) => { plain.push(t); } } }, null);
  return { ok, plain, wrote };
})()""")
        self.assertEqual(got, {"ok": True, "plain": ["Hi x"], "wrote": []})

    def test_blocks_the_copy_must_keep(self):
        a = "### Third\n\n#### Fourth\n\n###### Sixth\n\n3. Three\n4. Four\n\n```\na <b>\n  c\n```\n\nOne *soft* and `a<b` here\nnext line"
        h = run_node_async("(async () => AA.answerHtml(" + json.dumps(a) + "))()")
        t = run_node_async("(async () => AA.answerPlain(" + json.dumps(a) + "))()")
        self.assertEqual(h, "<h5>Third</h5><h5>Fourth</h5><h5>Sixth</h5><ol start=\"3\"><li>Three</li><li>Four</li></ol><pre><code>a &lt;b&gt;\n  c</code></pre><p>One <em>soft</em> and <code>a&lt;b</code> here<br>next line</p>")
        self.assertEqual(t, "Third\n\nFourth\n\nSixth\n\n3. Three\n4. Four\n\na <b>\n  c\n\nOne soft and a<b here\nnext line")

    def test_heading_levels_one_and_two(self):
        h = run_node_async("(async () => AA.answerHtml(" + json.dumps("# One\n\n## Two") + "))()")
        self.assertEqual(h, "<h3>One</h3><h4>Two</h4>")


FAKE = """(function () { window.__clip = []; window.ClipboardItem = function (o) { this.o = o; };
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { write: function (l) { var o = l[0].o, r = {}; return Promise.all(Object.keys(o).map(function (k) { return o[k].text().then(function (t) { r[k] = t; }); })).then(function () { window.__clip.push(r); }); }, writeText: function (t) { window.__clip.push({ 'text/plain': t }); return Promise.resolve(); } } }); })()"""

FAKE_FAIL = "(function () { Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: function () { return Promise.reject(new Error('no')); } } }); window.ClipboardItem = undefined; })()"
UP = "document.querySelector('#ask-box').value"


class Page(Classic):
    def ask(self, p, q):
        p.js("document.querySelector('#ask-box').focus()")
        p.type(q)
        p.js("document.querySelector('#ask-send').click()")

    def open_ask(self, p):
        p.key("/", code="Slash", vk=191)
        p.until("!!document.querySelector('#ask-panel')", "opened")
        p.until("!document.querySelector('#ask-send').disabled", "ready")

    def test_copy_ask_again_and_up_arrow_at_1400_and_900(self):
        self.stub.answer = "**Health:** steady."
        for w in (1400, 900):
            self.stub.calls.clear()
            with chrome() as cdp:
                p = self.visit(cdp)
                self.at(p, w)
                self.open_ask(p)
                p.js(FAKE)
                self.ask(p, "How is it going?")
                p.until("document.querySelectorAll('.ask-turn.assistant').length === 1 && !document.querySelector('#ask-work')", f"{w}: answered")
                self.assertEqual(p.js("[...document.querySelectorAll('.ask-turn-acts button')].map(b => b.textContent)"), ["Copy", "Ask again"], f"{w}: the links")
                self.assertEqual(p.js("document.documentElement.scrollWidth <= window.innerWidth"), True, f"{w}: no sideways scroll")
                p.js("document.querySelector('[data-ask-copy]').click()")
                p.until("window.__clip.length === 1", f"{w}: copied")
                self.assertEqual(p.js("window.__clip[0]"), {"text/html": "<p><strong>Health:</strong> steady.</p>", "text/plain": "Health: steady."})
                self.assertEqual(p.js("[...document.querySelectorAll('.ask-turn-acts button')].map(b => b.getAttribute('aria-label'))"), ["Copy this answer", "Ask this question again"], f"{w}: the screen-reader names")
                p.until("document.querySelector('#ask-note').textContent === 'Copied'", f"{w}: the notice is just Copied")
                p.until("document.querySelector('#ask-note').textContent === ''", f"{w}: Copied goes after 2 s")
                p.js("document.querySelector('[data-ask-again]').click()")
                p.until("document.querySelectorAll('.ask-turn.assistant').length === 2 && !document.querySelector('#ask-work')", f"{w}: asked again")
                asks = [c[1]["question"] for c in self.stub.calls if c[0] == "ask"]
                self.assertEqual(asks, ["How is it going?", "How is it going?"], f"{w}: the same question twice")
                self.ask(p, "And the budget?")
                p.until("document.querySelectorAll('.ask-turn.assistant').length === 3 && !document.querySelector('#ask-work')", f"{w}: third answer")
                p.js("document.querySelector('#ask-box').focus()")
                p.key("ArrowUp", code="ArrowUp", vk=38)
                p.until("document.querySelector('#ask-box').value === 'And the budget?'", f"{w}: last question back")
                p.key("ArrowUp", code="ArrowUp", vk=38)
                p.until("document.querySelector('#ask-box').value === 'How is it going?'", f"{w}: the one before")

    def test_a_box_with_words_keeps_up_arrow_to_itself(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.open_ask(p)
            self.ask(p, "First?")
            p.until("document.querySelectorAll('.ask-turn.assistant').length === 1 && !document.querySelector('#ask-work')", "answered")
            p.js("document.querySelector('#ask-box').focus()")
            p.type("typed")
            p.key("ArrowUp", code="ArrowUp", vk=38)
            self.assertEqual(p.js("document.querySelector('#ask-box').value"), "typed")


class Cards(Page):
    THEME = None

    def test_copy_ask_again_and_up_arrow_at_1400_and_900(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.open_ask(p)
            self.ask(p, "First?")
            p.until("document.querySelectorAll('.ask-turn.assistant').length === 1 && !document.querySelector('#ask-work')", "answered")
            self.assertEqual(p.js("document.querySelectorAll('.ask-turn-acts').length"), 0)

    def test_a_box_with_words_keeps_up_arrow_to_itself(self):
        pass

    def test_up_arrow_in_an_empty_box_recalls_nothing_under_cards_at_1400_and_900(self):
        for w in (1400, 900):
            with chrome() as cdp:
                p = self.visit(cdp)
                self.at(p, w)
                self.open_ask(p)
                self.ask(p, "First?")
                p.until("document.querySelectorAll('.ask-turn.assistant').length === 1 && !document.querySelector('#ask-work')", f"{w}: answered")
                p.js("document.querySelector('#ask-box').focus()")
                p.key("ArrowUp", code="ArrowUp", vk=38)
                p.key("ArrowUp", code="ArrowUp", vk=38)
                self.assertEqual(p.js(UP), "", f"{w}: nothing brought back under Cards")


class More(Classic):
    ask = Page.ask
    open_ask = Page.open_ask

    def answered(self, p, n, what):
        p.until(f"document.querySelectorAll('.ask-turn.assistant').length === {n} && !document.querySelector('#ask-work')", what)

    def test_modifiers_and_composing_leave_the_box_alone_at_1400_and_900(self):
        for w in (1400, 900):
            with chrome() as cdp:
                p = self.visit(cdp)
                self.at(p, w)
                self.open_ask(p)
                self.ask(p, "First?")
                self.answered(p, 1, f"{w}: answered")
                p.js("document.querySelector('#ask-box').focus()")
                for mod, name in ((8, "shift"), (1, "alt"), (2, "ctrl"), (4, "meta")):
                    p.key("ArrowUp", modifiers=mod, code="ArrowUp", vk=38)
                    self.assertEqual(p.js(UP), "", f"{w}: {name} leaves it empty")
                p.js("document.querySelector('#ask-box').dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', isComposing: true, bubbles: true, cancelable: true }))")
                self.assertEqual(p.js(UP), "", f"{w}: composing leaves it empty")
                p.key("ArrowUp", code="ArrowUp", vk=38)
                self.assertEqual(p.js(UP), "First?", f"{w}: a plain Up-arrow brings it back")

    def test_typing_and_sending_start_the_walk_again_at_1400_and_900(self):
        for w in (1400, 900):
            with chrome() as cdp:
                p = self.visit(cdp)
                self.at(p, w)
                self.open_ask(p)
                self.ask(p, "One?")
                self.answered(p, 1, f"{w}: first")
                self.ask(p, "Two?")
                self.answered(p, 2, f"{w}: second")
                p.js("document.querySelector('#ask-box').focus()")
                p.key("ArrowUp", code="ArrowUp", vk=38)
                p.key("ArrowUp", code="ArrowUp", vk=38)
                self.assertEqual(p.js(UP), "One?", f"{w}: two back")
                p.js("document.querySelector('#ask-box').select()")
                p.key("Backspace", code="Backspace", vk=8)
                self.assertEqual(p.js(UP), "", f"{w}: cleared")
                p.key("ArrowUp", code="ArrowUp", vk=38)
                self.assertEqual(p.js(UP), "Two?", f"{w}: typing started the walk again")
                p.js("document.querySelector('#ask-send').click()")
                self.answered(p, 3, f"{w}: third")
                p.js("document.querySelector('#ask-box').focus()")
                p.key("ArrowUp", code="ArrowUp", vk=38)
                self.assertEqual(p.js(UP), "Two?", f"{w}: a send started the walk again")

    def test_a_send_starts_the_walk_again_even_through_the_duplicate_at_1400_and_900(self):
        """After a recalled question is sent it is in the list twice: the next two Up-arrows must give it twice, not walk on to the one before."""
        for w in (1400, 900):
            with chrome() as cdp:
                p = self.visit(cdp)
                self.at(p, w)
                self.open_ask(p)
                self.ask(p, "One?")
                self.answered(p, 1, f"{w}: first")
                self.ask(p, "Two?")
                self.answered(p, 2, f"{w}: second")
                p.js("document.querySelector('#ask-box').focus()")
                p.key("ArrowUp", code="ArrowUp", vk=38)
                self.assertEqual(p.js(UP), "Two?", f"{w}: brought back")
                p.js("document.querySelector('#ask-send').click()")
                self.answered(p, 3, f"{w}: sent again")
                p.js("document.querySelector('#ask-box').focus()")
                p.key("ArrowUp", code="ArrowUp", vk=38)
                self.assertEqual(p.js(UP), "Two?", f"{w}: the walk began again")
                p.key("ArrowUp", code="ArrowUp", vk=38)
                self.assertEqual(p.js(UP), "Two?", f"{w}: the second step is the sent copy, not the one before")

    def test_words_put_in_the_box_by_the_quick_bar_are_not_walked_over_at_1400_and_900(self):
        """A question recalled with Up-arrow, then the box filled by the quick bar: Up-arrow leaves those words alone."""
        for w in (1400, 900):
            with chrome() as cdp:
                p = self.visit(cdp)
                self.at(p, w)
                self.open_ask(p)
                self.ask(p, "One?")
                self.answered(p, 1, f"{w}: first")
                p.js("document.querySelector('#ask-box').focus()")
                p.key("ArrowUp", code="ArrowUp", vk=38)
                self.assertEqual(p.js(UP), "One?", f"{w}: brought back")
                p.key("k", 2, "KeyK", 75)
                p.until("!!document.querySelector('#palette[open]')", f"{w}: quick bar open")
                p.js("document.querySelector('#palette-q').focus()")
                p.type("Handed words?")
                p.key("Enter", 0, "Enter", 13)
                p.until("!document.querySelector('#palette')", f"{w}: quick bar closed")
                p.until(f"document.querySelector('#ask-box').value === 'Handed words?'", f"{w}: the words are in the box")
                p.js("document.querySelector('#ask-box').focus()")
                p.key("ArrowUp", code="ArrowUp", vk=38)
                self.assertEqual(p.js(UP), "Handed words?", f"{w}: Up-arrow left them alone")

    def test_ask_again_waits_while_a_question_is_being_answered_at_1400_and_900(self):
        for w in (1400, 900):
            self.stub.hold.set()
            with chrome() as cdp:
                p = self.visit(cdp)
                self.at(p, w)
                self.open_ask(p)
                self.ask(p, "Slow?")
                self.answered(p, 1, f"{w}: answered")
                self.stub.hold.clear()
                self.ask(p, "Next?")
                p.until("!!document.querySelector('#ask-work')", f"{w}: working")
                self.assertEqual(p.js("document.querySelector('[data-ask-again]').disabled"), True, f"{w}: disabled while working")
                n = len(self.stub.calls)
                p.js("document.querySelector('[data-ask-again]').click()")
                self.assertEqual(len(self.stub.calls), n, f"{w}: a click sends nothing")
                self.stub.hold.set()
                self.answered(p, 2, f"{w}: done")
                self.assertEqual(p.js("document.querySelector('[data-ask-again]').disabled"), False, f"{w}: enabled again")

    def test_the_failure_notice_is_shown_at_1400_and_900(self):
        for w in (1400, 900):
            with chrome() as cdp:
                p = self.visit(cdp)
                self.at(p, w)
                self.open_ask(p)
                p.js(FAKE_FAIL)
                self.ask(p, "Q?")
                self.answered(p, 1, f"{w}: answered")
                p.js("document.querySelector('[data-ask-copy]').click()")
                p.until("document.body.textContent.includes('Could not copy. Select the text and copy it yourself.')", f"{w}: the failure notice")

    def test_copied_going_away_does_not_wipe_a_newer_line_at_1400_and_900(self):
        for w in (1400, 900):
            with chrome() as cdp:
                p = self.visit(cdp)
                self.at(p, w)
                self.open_ask(p)
                p.js(FAKE)
                self.ask(p, "Q?")
                self.answered(p, 1, f"{w}: answered")
                p.js("document.querySelector('[data-ask-copy]').click()")
                p.until("document.querySelector('#ask-note').textContent === 'Copied'", f"{w}: copied")
                p.js("document.querySelector('#ask-send').click()")
                p.until("document.querySelector('#ask-note').textContent === 'Type a question first, then press Ask.'", f"{w}: a newer line replaced Copied")
                p.js("window.__t = Date.now()")
                p.until("Date.now() - window.__t > 2600", f"{w}: past the 2 s")
                self.assertEqual(p.js("document.querySelector('#ask-note').textContent"), "Type a question first, then press Ask.", f"{w}: the newer line stays")

    def test_the_copied_timer_is_cleared_when_the_panel_goes_away(self):
        # The panel stays mounted while the page is open (App.jsx), so closing it never runs the cleanup; the cleanup is pinned in the source.
        src = (EDIT / "AskPanel.jsx").read_text(encoding="utf-8")
        self.assertIn("useEffect(() => () => clearTimeout(copiedTimer.current), []);", src)
        self.assertIn("clearTimeout(copiedTimer.current);\n    setNote(ok ?", src, "a second copy cancels the first timer")

    def test_ask_again_is_off_when_asking_is_off_though_nothing_is_running_at_1400_and_900(self):
        for w in (1400, 900):
            self.stub.__dict__.pop("ask", None)
            with chrome() as cdp:
                p = self.visit(cdp)
                self.at(p, w)
                self.open_ask(p)
                self.ask(p, "Q?")
                self.answered(p, 1, f"{w}: answered")
                self.assertEqual(p.js("document.querySelector('[data-ask-again]').disabled"), False, f"{w}: on while ready")
                self.stub.ask = lambda body: (409, {"ok": False, "code": "asking_off", "message": "Asking is off."})
                self.ask(p, "Next?")
                p.until("!document.querySelector('#ask-work') && !!document.querySelector('[data-ask-again]') && document.querySelector('#ask-panel').textContent.length > 0", f"{w}: settled")
                p.until("document.querySelector('[data-ask-again]').disabled === true", f"{w}: Ask again is off with asking off")


if __name__ == "__main__":
    unittest.main()
