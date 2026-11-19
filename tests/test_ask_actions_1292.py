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


FAKE = """(function () { window.__clip = []; window.ClipboardItem = function (o) { this.o = o; };
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { write: function (l) { var o = l[0].o, r = {}; return Promise.all(Object.keys(o).map(function (k) { return o[k].text().then(function (t) { r[k] = t; }); })).then(function () { window.__clip.push(r); }); }, writeText: function (t) { window.__clip.push({ 'text/plain': t }); return Promise.resolve(); } } }); })()"""


class Page(Classic):
    def ask(self, p, q):
        p.js("document.querySelector('#ask-box').focus()")
        p.type(q)
        p.js("document.querySelector('#ask-send').click()")

    def open(self, p):
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
                self.open(p)
                p.js(FAKE)
                self.ask(p, "How is it going?")
                p.until("document.querySelectorAll('.ask-turn.assistant').length === 1 && !document.querySelector('#ask-work')", f"{w}: answered")
                self.assertEqual(p.js("[...document.querySelectorAll('.ask-turn-acts button')].map(b => b.textContent)"), ["Copy", "Ask again"], f"{w}: the links")
                self.assertEqual(p.js("document.documentElement.scrollWidth <= window.innerWidth"), True, f"{w}: no sideways scroll")
                p.js("document.querySelector('[data-ask-copy]').click()")
                p.until("window.__clip.length === 1", f"{w}: copied")
                self.assertEqual(p.js("window.__clip[0]"), {"text/html": "<p><strong>Health:</strong> steady.</p>", "text/plain": "Health: steady."})
                p.until("document.body.textContent.includes('Copied. It pastes into Word or an email with its formatting.')", f"{w}: the notice")
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
            self.open(p)
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
            self.open(p)
            self.ask(p, "First?")
            p.until("document.querySelectorAll('.ask-turn.assistant').length === 1 && !document.querySelector('#ask-work')", "answered")
            self.assertEqual(p.js("document.querySelectorAll('.ask-turn-acts').length"), 0)

    def test_a_box_with_words_keeps_up_arrow_to_itself(self):
        pass


if __name__ == "__main__":
    unittest.main()
