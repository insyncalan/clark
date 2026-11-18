"""Row 1264 slice 6: more tests for the tile editor (glanceTileEditor.jsx): the pure parts run in node (bundled by the pinned esbuild, no browser):
the words and colour table, the shape of each colour, what an own tile draws and its aria-label, and the tile actions' state changes; one browser
test pins the words of a refused change. Fictional data only.

Run: python3 dev/run_tests.py test_tpl_glance_editor_1264_more
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

from test_report_editor import tearDownModule  # noqa: F401, E402
from test_server import chrome  # noqa: E402
from test_tpl_glance_editor_1264 import OWN, Editor  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
ENTRY = ('export * from "@src/edit/templates/glanceTileEditor.jsx";\n'
         'export { toast } from "@src/stores/changes.js";\n'
         'export { readBody } from "@src/templates/glanceBody.js";\n')
# A plain-object view of a vnode: tag, class, the attributes the tests read, and the children.
HELPERS = """
const kids = (v) => (v == null || v === false ? [] : Array.isArray(v) ? v.flatMap(kids) : [v]);
const flat = (v) => typeof v === "object" && v ? { tag: v.type, cls: v.props.class || "", attrs: Object.fromEntries(Object.entries(v.props).filter(([k]) => k !== "children" && k !== "class")), kids: kids(v.props.children).map(flat) } : v;
"""
_BUNDLE = {}


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
                          + bundle() + ";\nconst G = GE;\n" + HELPERS + "\nPromise.resolve(" + probe + ").then((r) => console.log(JSON.stringify(r)));",
                          encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60)
        assert done.returncode == 0, done.stderr[:400]
        return json.loads(done.stdout)


class Words(unittest.TestCase):
    def test_M1_the_limit_sentence_names_the_twelve_tiles(self):
        self.assertEqual(run_node("G.limitWords()"), "You can have up to 12 tiles.")

    def test_M2_the_ruled_words_are_these_and_no_others_were_added(self):
        got = run_node("G.WORDS")
        self.assertEqual({k: got[k] for k in ("notSaved", "untitled", "newTile", "zero", "saved", "cancelled", "noLabel", "done", "cancel")},
                         {"notSaved": "The tile was not saved. Give it a label, then try again.", "untitled": "Untitled", "newTile": "New tile", "zero": "0",
                          "saved": "Tile saved", "cancelled": "Changes to the tile cancelled", "noLabel": "Give the tile a label.", "done": "Done", "cancel": "Cancel"})

    def test_M3_the_picker_gives_each_colour_its_tag_word_and_neutral_none(self):
        self.assertEqual(run_node("G.COLOURS"), [["green", "Green", "On track"], ["amber", "Amber", "At risk"], ["red", "Red", "Off track"],
                                                 ["blue", "Blue", "Info"], ["neutral", "Neutral", ""]])

    def test_M4_each_colour_has_its_own_class_letter(self):
        self.assertEqual(run_node("G.TONE_CLASS"), {"green": "g", "amber": "a", "red": "r", "blue": "b", "neutral": "n"})


class Shapes(unittest.TestCase):
    def shapes(self):
        return run_node("Object.fromEntries(['green', 'amber', 'red', 'blue', 'neutral', 'purple'].map((t) => [t, flat(G.Shape({ tone: t }))]))")

    def test_M5_each_colour_has_its_own_shape_and_none_is_swapped(self):
        s = self.shapes()
        self.assertEqual((s["green"]["kids"][0]["tag"], s["green"]["kids"][0]["attrs"]["r"]), ("circle", "5.5"), "green is a filled circle")
        self.assertEqual((s["amber"]["kids"][0]["tag"], s["amber"]["kids"][0]["attrs"]["d"]), ("path", "M6 .5 11.7 11H.3z"), "amber is a triangle")
        self.assertEqual((s["red"]["kids"][0]["tag"], s["red"]["kids"][0]["attrs"]["d"]), ("path", "M6 .2 11.8 6 6 11.8.2 6z"), "red is a diamond")
        self.assertEqual((s["blue"]["kids"][0]["tag"], s["blue"]["kids"][0]["attrs"]["rx"]), ("rect", "2"), "blue is a rounded square")
        n = s["neutral"]["kids"][0]
        self.assertEqual((n["tag"], n["attrs"]["fill"], n["attrs"]["stroke"]), ("circle", "none", "currentColor"), "neutral is a ring")
        self.assertEqual(len({json.dumps(s[t]["kids"][0], sort_keys=True) for t in ("green", "amber", "red", "blue", "neutral")}), 5)

    def test_M6_a_shape_carries_its_tone_class_is_hidden_from_readers_and_an_unknown_tone_is_neutral(self):
        s = self.shapes()
        for tone, letter in (("green", "g"), ("amber", "a"), ("red", "r"), ("blue", "b"), ("neutral", "n")):
            self.assertEqual(s[tone]["cls"], f"tpl-shp tone-{letter}")
        self.assertEqual(s["green"]["attrs"]["aria-hidden"], "true")
        self.assertEqual(s["purple"]["kids"][0], s["neutral"]["kids"][0], "an unknown tone draws the neutral ring")


class OwnTileDraw(unittest.TestCase):
    def tile(self, t):
        return run_node("flat(G.OwnTile({ t: %s }))" % json.dumps(t))

    def parts(self, got):
        return {k["cls"]: k for k in got["kids"]}

    def test_M7_an_own_tile_draws_dot_label_figure_tag_and_note_with_its_aria_label(self):
        got = self.tile({"label": "Fictional own", "figure": "7", "tag": "Fine", "note": "Fictional note", "tone": "red"})
        self.assertEqual(got["cls"], "fig tpl-gt-tile tone-r")
        self.assertEqual((got["attrs"]["role"], got["attrs"]["aria-label"]), ("group", "Fictional own: 7"))
        p = self.parts(got)
        self.assertEqual(list(p), ["tpl-gt-dot", "tpl-gt-k", "tpl-gt-v num", "tpl-gt-tag", "tpl-gt-note"])
        self.assertEqual([p[c]["kids"] for c in ("tpl-gt-k", "tpl-gt-v num", "tpl-gt-tag", "tpl-gt-note")], [["Fictional own"], ["7"], ["Fine"], ["Fictional note"]])
        self.assertEqual((p["tpl-gt-k"]["attrs"]["title"], p["tpl-gt-note"]["attrs"]["title"]), ("Fictional own", "Fictional note"))
        self.assertEqual(p["tpl-gt-dot"]["attrs"]["aria-hidden"], "true")

    def test_M8_a_tag_a_note_or_a_figure_that_is_empty_draws_no_part(self):
        for gone, tile in (("tpl-gt-tag", {"label": "A", "figure": "1", "note": "n"}), ("tpl-gt-note", {"label": "A", "figure": "1", "tag": "t"}),
                           ("tpl-gt-v num", {"label": "A", "tag": "t", "note": "n"})):
            with self.subTest(gone=gone):
                p = self.parts(self.tile(tile))
                self.assertNotIn(gone, p)
                self.assertEqual(len(p), 4)

    def test_M9_a_blank_label_reads_untitled_and_no_tone_is_neutral(self):
        for label in ("", "   ", None):
            with self.subTest(label=label):
                got = self.tile({"label": label, "figure": "3"})
                self.assertEqual(got["attrs"]["aria-label"], "Untitled: 3")
                self.assertEqual(self.parts(got)["tpl-gt-k"]["kids"], ["Untitled"])
                self.assertTrue(got["cls"].endswith("tone-n"))

    def test_M10_the_aria_label_of_a_tile_with_no_figure_has_an_empty_figure(self):
        self.assertEqual(self.tile({"label": "A"})["attrs"]["aria-label"], "A: ")


class Actions(unittest.TestCase):
    """tileActions: the state each action leaves in the editor signal and the toast (no request is made)."""

    def run_actions(self, body, steps):
        return run_node("""(async () => {
          const u = G.readBody({ body: JSON.stringify({ v: 1, bespoke: %s }) }); const a = G.tileActions({ id: 's1' }, u); const log = [];
          for (const s of %s) { if (s[0] === 'typed') { G.editor.value = { ...G.editor.value, draft: { ...G.editor.value.draft, label: 'Typed draft' } }; } else await a[s[0]](...s.slice(1)); log.push([JSON.parse(JSON.stringify(G.editor.value)), G.toast.value && G.toast.value.text]); }
          return log; })()""" % (json.dumps(body), json.dumps(steps)))

    def test_M11_add_opens_a_new_draft_with_the_ruled_words_and_the_next_id(self):
        got = self.run_actions([{"id": "t1", "label": "A"}], [["add"]])
        e = got[0][0]
        self.assertEqual((e["sid"], e["id"], e["isNew"], e["pop"], e["tried"]), ("s1", "t2", True, False, False))
        self.assertEqual(e["draft"], {"label": "New tile", "figure": "0", "tag": "", "note": "", "tone": "neutral"})

    def test_M12_add_at_twelve_tiles_says_the_limit_and_opens_nothing(self):
        got = self.run_actions([{"id": f"t{i}", "label": "A"} for i in range(1, 13)], [["add"]])
        self.assertEqual(got[0], [None, "You can have up to 12 tiles."])

    def test_M13_the_pencil_opens_the_stored_tile_and_a_second_press_closes_it_with_the_cancel_note(self):
        tile = {"id": "t1", "label": "A", "figure": "7", "tag": "x", "tone": "blue"}
        got = self.run_actions([tile], [["pencil", {"key": "t1", "label": "A"}], ["pencil", {"key": "t1", "label": "A"}]])
        e = got[0][0]
        self.assertEqual((e["id"], e["isNew"]), ("t1", False))
        self.assertEqual(e["draft"], {"label": "A", "figure": "7", "tag": "x", "note": "", "tone": "blue"})
        self.assertEqual(got[1], [None, "Changes to the tile cancelled"])

    def test_M14_done_with_a_blank_label_says_it_was_not_saved_marks_tried_and_keeps_the_editor(self):
        for label in ("", "   "):
            with self.subTest(label=label):
                got = run_node("""(async () => { const a = G.tileActions({ id: 's1' }, { bespoke: [] }); a.add();
                  G.editor.value = { ...G.editor.value, draft: { ...G.editor.value.draft, label: %s } }; await a.done();
                  return [JSON.parse(JSON.stringify(G.editor.value)), G.toast.value.text]; })()""" % json.dumps(label))
                self.assertTrue(got[0]["tried"])
                self.assertEqual(got[1], "The tile was not saved. Give it a label, then try again.")
                self.assertEqual(got[0]["draft"]["label"], label)

    def test_M15_done_with_nothing_changed_makes_no_request_closes_silently_and_toasts_nothing(self):
        tile = {"id": "t1", "label": "A", "figure": "7"}
        got = self.run_actions([tile], [["pencil", {"key": "t1", "label": "A"}], ["done"]])
        self.assertEqual(got[1], [None, None])

    def test_M15b_the_pencil_on_another_tile_drops_the_open_draft_by_design_and_stores_nothing(self):
        tiles = [{"id": "t1", "label": "A", "figure": "7"}, {"id": "t2", "label": "B", "figure": "8"}]
        got = self.run_actions(tiles, [["pencil", {"key": "t1", "label": "A"}], ["typed"], ["pencil", {"key": "t2", "label": "B"}]])
        self.assertEqual(got[1][0]["draft"]["label"], "Typed draft")
        self.assertEqual((got[2][0]["id"], got[2][0]["draft"]["label"]), ("t2", "B"))
        self.assertEqual(got[2][1], None, "nothing was stored, so no toast")

    def test_M16_done_and_remove_with_no_editor_open_do_nothing(self):
        self.assertEqual(self.run_actions([{"id": "t1", "label": "A"}], [["done"], ["remove"]]), [[None, None], [None, None]])


class Refused(Editor):
    def test_M17_when_the_change_is_refused_the_toast_says_clark_is_not_answering_in_the_ruled_words(self):
        self.seed([OWN])
        with chrome() as cdp:
            p = self.page(cdp)
            self.click(p, "[data-tile=t1] [data-tile-pencil]")
            self.editor_open(p)
            self.fill(p, "label", "Fictional typed")
            p.js("window.fetch = function () { return Promise.reject(new Error('down')); };")
            self.click(p, "[data-tile-editor] [data-done]")
            p.until("!!document.querySelector('.toast-text')", "a note")
            self.assertEqual(self.toast(p), "Nothing is running behind this page. After a while with nothing open, clark stops by itself. Start it again from clark.command.")
            self.assertEqual(p.js("document.querySelector('[data-tile-editor] [data-f=label]').value"), "Fictional typed", "the editor stays open with what was typed")


if __name__ == "__main__":
    unittest.main()
