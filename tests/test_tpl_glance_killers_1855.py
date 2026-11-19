"""Row 1264 slice 9 (PR 1855), killer tests for the survivors of the mutation read of b8248fee. Fictional data only. No browser: node and source reads.

K1 a silent per-row change must not leave an Undo that says "Undone: " with nothing after it (edit/templates/GlanceTemplate.jsx perRow sends
   words "" with {silent: true}; stores/changes.js change() stored `Undone: ${done}` for it).
K2 the body's per_row reads the same in the page (templates/glanceBody.js readBody) and in clark (section_kinds/glancetemplate.py upgrade), for
   the text 3.0 too (JSON.parse turns 3.0 into 3, Python reads it as a float and falls back to 4).
K3 the Edit part shows ONE hint paragraph, not the At a glance one and its own after it.
K4 the health wrapper stays a flex box inside a stretching grid, so the health tile is as tall as its neighbours on the line.

Run: python3 dev/run_tests.py test_tpl_glance_killers_1855
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402
import test_tpl_glance_body_node_1264 as B  # noqa: E402

from clark.section_kinds import glancetemplate as G  # noqa: E402

PAGE = SRC / "clark" / "page"
ENTRY = ROOT / "tests" / "fixtures" / "changes_node.js"
_BUNDLE = {}
STUBS = """
globalThis.window = globalThis;
globalThis.location = { pathname: "/", search: "", hash: "", href: "http://x/", origin: "http://x" };
globalThis.history = { replaceState() {}, pushState() {} };
globalThis.addEventListener = () => {}; globalThis.removeEventListener = () => {};
globalThis.document = { querySelector: () => null, addEventListener() {}, removeEventListener() {}, getElementById: () => null,
  createElement: () => ({ style: {}, setAttribute() {} }), documentElement: { dataset: {} }, activeElement: null, body: {} };
globalThis.localStorage = { getItem: () => null, setItem() {}, removeItem() {} };
globalThis.sessionStorage = globalThis.localStorage;
"""
FAKE = """
;(async () => {
  CH.project.value = "ABC"; CH.data.value = { report_sections: [{ id: 1 }], project: {} };
  const again = { ok: true, sections: [{ id: 1 }] };
  globalThis.fetch = async (path) => ({ ok: true, status: 200, json: async () => path.startsWith("/api/data") ? { ok: true, data: { report_sections: [{ id: 1 }], project: {} } } : { ...again, apply_id: 7 } });
  await CH.change({ op: "update", id: 1, changes: { body: "{}" }, place: "report" }, %s, %s);
  await CH.undo(7);
  console.log(JSON.stringify(CH.toast.value));
})().catch((e) => { console.log("ERR " + e.stack); process.exit(1); });
"""


def changes_bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ch.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=CH", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE / 'src'}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    return _BUNDLE["code"]


def undo_toast(words, named):
    """What the toast says after one change made with `words` and `named`, and its Undo."""
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(STUBS + changes_bundle() + FAKE % (json.dumps(words), json.dumps(named)), encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stdout + done.stderr
        return json.loads(done.stdout.strip().splitlines()[-1])


class UndoWords(unittest.TestCase):
    def test_k1_undo_of_a_silent_per_row_change_says_undone_with_nothing_after_the_colon(self):
        t = undo_toast("", {"silent": True})
        self.assertEqual((t["kind"], t["text"]), ("done", "Undone."))

    def test_k1b_undo_of_a_named_change_still_repeats_its_words(self):
        t = undo_toast("Overdue actions hidden from the published report.", {"focus": "[data-x]"})
        self.assertEqual(t["text"], "Undone: Overdue actions hidden from the published report.")

    def test_k1c_no_undo_toast_ever_ends_on_a_bare_colon(self):
        for words, named in (("", {"silent": True}), ("", {"focus": "[data-x]"}), ("", {"quiet": True})):
            with self.subTest(words=words, named=named):
                self.assertFalse(undo_toast(words, named)["text"].rstrip().endswith(":"))

    def test_k1d_the_per_row_buttons_still_send_no_words_and_stay_silent(self):
        src = (PAGE / "src/edit/templates/GlanceTemplate.jsx").read_text(encoding="utf-8")
        self.assertRegex(src, r'perRow: \(n\) => send\(withChange\(u, \{ perRow: n \}\), "", [^\n]*\{ silent: true \}\)')


class PerRowParity(unittest.TestCase):
    TEXTS = ("3", "4", "3.0", "4.0", "3.5", "5", "0", "true", '"3"', "null")

    def js(self, text):
        return B.run_node("G.readBody({body: %s}).per_row" % json.dumps('{"v": 1, "per_row": %s}' % text))

    def py(self, text):
        return G.upgrade(json.loads('{"v": 1, "per_row": %s}' % text))["per_row"]

    def test_k2_the_page_and_clark_read_every_per_row_text_the_same(self):
        for text in self.TEXTS:
            with self.subTest(per_row=text):
                self.assertEqual(self.js(text), self.py(text))

    def test_k2b_3_and_4_as_whole_numbers_are_kept(self):
        self.assertEqual((self.js("3"), self.js("4")), (3, 4))
        self.assertEqual((self.py("3"), self.py("4")), (3, 4))

    def test_k2c_3_point_0_is_refused_by_the_check_as_the_reader_does_not_take_it(self):
        with self.assertRaises(Exception):
            G.check(json.loads('{"v": 1, "per_row": 3.0}'))


def tpl_edit():
    src = (PAGE / "src/edit/templates/GlanceTemplate.jsx").read_text(encoding="utf-8")
    return src[src.index("export function Edit("):]


class OneHint(unittest.TestCase):
    def test_k3_the_edit_part_draws_one_hint_paragraph(self):
        body = tpl_edit()
        paras = re.findall(r"<GLANCE\.Hint\b|<p class=\"glance-hint\"", body)
        self.assertEqual(paras, ["<GLANCE.Hint"], "one paragraph: the At a glance one, with the template's sentences added to it")

    def test_k3b_the_one_hint_carries_the_slice_9_words(self):
        body = tpl_edit()
        self.assertIn("WORDS.hintEye", body)
        self.assertIn("WORDS.hintAdd", body)
        self.assertIn("text: WORDS.hint", body)      # row 1336: Classic says the approved line instead; Cards keeps the two sentences
        self.assertNotIn('<p class="glance-hint"', body)


def rule(css, selector):
    m = re.search(r"^" + re.escape(selector) + r" \{([^}]*)\}", css, re.M)
    assert m, selector
    return dict(p.strip().split(":", 1) for p in m.group(1).split(";") if ":" in p)


class HealthStretch(unittest.TestCase):
    css = (PAGE / "shell.css").read_text(encoding="utf-8")

    def test_k4_the_grid_stretches_and_the_health_wrapper_is_a_flex_box_so_its_tile_fills_the_line(self):
        grid, health = rule(self.css, ".tpl-gt"), rule(self.css, ".tpl-gt-health")
        self.assertEqual(grid["align-items"].strip(), "stretch")
        self.assertEqual(health["display"].strip(), "flex")
        self.assertNotIn("align-items", health, "the wrapper's own align-items would stop the health tile filling it")
        self.assertNotIn("align-self", health)

    def test_k4b_the_wrapper_takes_the_width_of_one_tile_or_the_whole_line(self):
        health = rule(self.css, ".tpl-gt-health")
        self.assertEqual(health["flex"].strip(), rule(self.css, ".tpl-gt-tile")["flex"].strip())
        self.assertEqual(rule(self.css, ".tpl-gt-health.own-row")["flex-basis"].strip(), "100%")


class SavingPerSection(unittest.TestCase):
    src = (PAGE / "src" / "edit" / "templates" / "glanceTileEditor.jsx").read_text(encoding="utf-8")

    def test_n1_a_done_in_flight_is_kept_per_section_not_in_one_flag(self):
        self.assertNotRegex(self.src, r"let saving\b")
        self.assertIn("const saving = new Set()", self.src)
        self.assertIn("saving.has(section.id)", self.src)
        self.assertIn("saving.add(section.id)", self.src)
        self.assertIn("saving.delete(section.id)", self.src)

    def test_n2_remove_waits_while_its_done_is_in_flight_in_that_section(self):
        body = self.src[self.src.index("remove: async"):]
        self.assertLess(body.index("saving.has(section.id)"), body.index("close(e,"), "the guard comes before any close")


class HintParts(unittest.TestCase):
    src = (PAGE / "src" / "edit" / "GlanceEdit.jsx").read_text(encoding="utf-8")

    def test_h1_the_hint_adds_a_template_s_sentences_after_one_space_and_adds_nothing_by_default(self):
        self.assertIn('function Hint({ more = "", text = "" })', self.src)
        self.assertIn('{more ? ` ${more}` : ""}', self.src)


if __name__ == "__main__":
    unittest.main()
