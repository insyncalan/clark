"""Row 1264, the reader's addendum on the glance tile editor: what a Done that is still on its way does, run in node with a held send (no browser).
A stand-in for fetch holds each save until the test lets it go, so the order is exact: a Remove while a Done is on its way waits (S1), a Done in
another section is not stopped and both land (S2), a Done that lands never drops the editor another section has open with its typed draft (S3),
and the Removed toast of a draft with no label says Untitled (S4). Fictional data only.

Run: python3 dev/run_tests.py test_tpl_glance_held_send_1264
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
ENTRY = ('export * from "@src/edit/templates/glanceTileEditor.jsx";\n'
         'export { toast } from "@src/stores/changes.js";\n'
         'export { project, data } from "@src/stores/report.js";\n'
         'export { readBody } from "@src/templates/glanceBody.js";\n')
_BUNDLE = {}

# Two sections, each with two stored tiles; a fetch that records the section of each save and holds it until `let_go()`.
SETUP = """
const T = (id, label) => ({ id, label, figure: '1' });
const body = (tiles) => G.readBody({ body: JSON.stringify({ v: 1, bespoke: tiles }) });
const A = G.tileActions({ id: 'sA' }, body([T('t1', 'Alpha'), T('t2', 'Beta')]));
const B = G.tileActions({ id: 'sB' }, body([T('t1', 'Gamma'), T('t2', 'Delta')]));
G.project.value = 'p1'; G.data.value = { report_sections: [] };
const sent = [], held = [];
globalThis.fetch = (path, opts) => {
  if (String(path).startsWith('/api/data')) return Promise.resolve({ ok: true, status: 200, json: async () => ({ ok: true, data: { report_sections: [] } }) });
  sent.push(JSON.parse(opts.body).id);
  return new Promise((res) => held.push(() => res({ ok: true, status: 200, json: async () => ({ ok: true, sections: [], apply_id: null }) })));
};
const focused = [];
globalThis.document.querySelector = (sel) => ({ focus() { focused.push(sel); } });
const tick = () => new Promise((r) => setTimeout(r, 20));
const let_go = async () => { while (held.length) { held.shift()(); await tick(); } };
const type = (label) => { G.editor.value = { ...G.editor.value, draft: { ...G.editor.value.draft, label } }; };
const ed = () => JSON.parse(JSON.stringify(G.editor.value));
const said = () => G.toast.value && G.toast.value.text;
"""


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            entry, out = Path(tmp) / "e.js", Path(tmp) / "o.js"
            entry.write_text(ENTRY, encoding="utf-8")
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=GE", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(entry), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    return _BUNDLE["code"]


def run_node(probe):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text("globalThis.window = globalThis; globalThis.addEventListener = () => {};"
                          " globalThis.document = { querySelector() { return null; }, addEventListener() {}, documentElement: { dataset: {} } };\n"
                          + bundle() + ";\nconst G = GE;\n" + SETUP + "\n(async () => { " + probe + " })().then((r) => console.log(JSON.stringify(r)));",
                          encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60)
        assert done.returncode == 0, done.stderr[:600]
        return json.loads(done.stdout)


class RemoveWhileDoneIsOnItsWay(unittest.TestCase):
    def test_S1a_remove_on_a_stored_tile_waits_for_its_done_and_sends_nothing_itself(self):
        got = run_node("""
          A.pencil({ key: 't1', label: 'Alpha' }); type('Alpha two');
          const done = A.done(); await tick();
          const during = { sent: sent.slice(), editor: ed() };
          await A.remove(); await tick();
          const after = { sent: sent.slice(), editor: ed(), said: said() };
          await let_go(); await done;
          return { during, after, end: { sent: sent.slice(), editor: ed(), said: said() } };""")
        self.assertEqual(got["during"]["sent"], ["sA"], "the Done is the one save on its way")
        self.assertEqual(got["after"]["sent"], ["sA"], "Remove sent no save of its own")
        self.assertEqual(got["after"]["editor"]["id"], "t1", "Remove did not close the editor")
        self.assertNotEqual(got["after"]["said"], "Removed: Alpha")
        self.assertEqual(got["end"]["sent"], ["sA"])
        self.assertIsNone(got["end"]["editor"], "the Done then closed the editor")

    def test_S1b_remove_on_a_new_draft_waits_for_its_done_and_does_not_drop_it_early(self):
        got = run_node("""
          A.add(); type('Fresh');
          const done = A.done(); await tick();
          await A.remove(); await tick();
          const after = { sent: sent.slice(), editor: ed(), said: said() };
          await let_go(); await done;
          return { after, end: { sent: sent.slice(), editor: ed(), said: said() } };""")
        self.assertEqual(got["after"]["sent"], ["sA"])
        self.assertEqual(got["after"]["editor"]["draft"]["label"], "Fresh", "the draft is still open, not dropped by Remove")
        self.assertNotEqual(got["after"]["said"], "Removed: Fresh")
        self.assertEqual(got["end"]["sent"], ["sA"], "nothing was sent after the Done")
        self.assertIsNone(got["end"]["editor"])

    def test_S1c_once_the_done_has_landed_remove_works_again_on_that_section(self):
        got = run_node("""
          A.pencil({ key: 't1', label: 'Alpha' }); type('Alpha two');
          const done = A.done(); await tick(); await let_go(); await done;
          A.pencil({ key: 't2', label: 'Beta' });
          focused.length = 0; const rm = A.remove(); await tick(); await let_go(); await rm; await tick();
          return { sent: sent.slice(), editor: ed(), said: said(), focused };""")
        self.assertEqual(got["sent"], ["sA", "sA"])
        self.assertEqual(got["said"], None, "no step, so no toast with no step to undo (the stand-in reply has none)")
        self.assertIsNone(got["editor"])
        self.assertEqual(got["focused"], ['[data-id="sA"] .tileadd'], "the focus goes to Add a tile")


class AnotherSectionIsFree(unittest.TestCase):
    def test_S2_a_done_in_section_b_is_not_stopped_by_a_done_on_its_way_in_section_a_and_both_land(self):
        got = run_node("""
          A.pencil({ key: 't1', label: 'Alpha' }); type('Alpha two');
          const doneA = A.done(); await tick();
          B.pencil({ key: 't2', label: 'Delta' }); type('Delta two');
          const doneB = B.done(); await tick();
          const queued = sent.slice();
          await let_go(); await doneA; await doneB;
          return { queued, sent: sent.slice(), editor: ed() };""")
        self.assertEqual(got["queued"], ["sA"], "the saves run in turn: B waits behind A, it is not refused")
        self.assertEqual(got["sent"], ["sA", "sB"], "B's Done was accepted and saved after A's")
        self.assertIsNone(got["editor"], "B's Done closed B's editor")

    def test_S2b_a_second_done_in_the_same_section_sends_nothing(self):
        got = run_node("""
          A.pencil({ key: 't1', label: 'Alpha' }); type('Alpha two');
          const first = A.done(); await tick(); const second = A.done(); await tick();
          await let_go(); await first; await second;
          return sent.slice();""")
        self.assertEqual(got, ["sA"])


class NoDraftDroppedByAnotherSectionsDone(unittest.TestCase):
    def test_S3a_a_done_that_lands_leaves_the_editor_open_in_another_section_with_its_typed_draft_and_the_focus_where_it_is(self):
        got = run_node("""
          A.pencil({ key: 't1', label: 'Alpha' }); type('Alpha two');
          const doneA = A.done(); await tick();
          B.pencil({ key: 't1', label: 'Gamma' }); type('Typed in B');
          await let_go(); await doneA; await tick();
          return { editor: ed(), focused };""")
        self.assertIsNotNone(got["editor"], "B's open editor was dropped by A's Done")
        self.assertEqual((got["editor"]["sid"], got["editor"]["id"], got["editor"]["draft"]["label"]), ("sB", "t1", "Typed in B"), "same tile id, other section")
        self.assertEqual(got["focused"], [], "A's pencil did not take the focus from B's editor")

    def test_S3b_the_same_holds_for_another_tile_of_the_same_section(self):
        got = run_node("""
          A.pencil({ key: 't1', label: 'Alpha' }); type('Alpha two');
          const doneA = A.done(); await tick();
          A.pencil({ key: 't2', label: 'Beta' }); type('Typed on beta');
          await let_go(); await doneA; await tick();
          return ed();""")
        self.assertIsNotNone(got, "the open editor of the other tile was dropped")
        self.assertEqual((got["sid"], got["id"], got["draft"]["label"]), ("sA", "t2", "Typed on beta"))

    def test_S3c_a_done_with_no_other_editor_open_still_closes_its_own(self):
        got = run_node("""
          A.pencil({ key: 't1', label: 'Alpha' }); type('Alpha two');
          const d = A.done(); await tick(); await let_go(); await d; await tick();
          return { editor: ed(), focused };""")
        self.assertIsNone(got["editor"])
        self.assertEqual(got["focused"], ['[data-id="sA"] [data-tile="t1"] [data-tile-pencil]'], "the focus goes back to its pencil")

    def test_S3d_a_remove_that_lands_does_not_drop_another_sections_open_editor_either(self):
        got = run_node("""
          A.pencil({ key: 't1', label: 'Alpha' });
          const rm = A.remove(); await tick();
          B.pencil({ key: 't2', label: 'Delta' }); type('Typed in B');
          await let_go(); await rm; await tick();
          return ed();""")
        self.assertIsNotNone(got, "B's open editor was dropped by A's Remove")
        self.assertEqual((got["sid"], got["draft"]["label"]), ("sB", "Typed in B"))


class RemovedToastNamesAnUnlabelledDraft(unittest.TestCase):
    def test_S4_removing_a_draft_says_removed_with_its_trimmed_label_or_untitled_when_it_has_none(self):
        for label, want in (("   ", "Removed: Untitled"), ("", "Removed: Untitled"), ("  Fresh  ", "Removed: Fresh")):
            with self.subTest(label=label):
                got = run_node("A.add(); type(%s); await A.remove(); return { said: said(), editor: ed(), sent: sent.slice() };" % json.dumps(label))
                self.assertEqual(got["said"], want)
                self.assertIsNone(got["editor"])
                self.assertEqual(got["sent"], [], "a draft was never stored: nothing is sent")


if __name__ == "__main__":
    unittest.main()
