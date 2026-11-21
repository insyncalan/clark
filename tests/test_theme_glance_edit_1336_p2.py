"""Row 1336 part 2: the At a glance template in Edit under the Classic Theme, the controls and the words, as Chrome computes them at 1400 and 900 px
(light). Pinned from the ruled values: the bin on a built-in tile deletes it (24x24, top 4, right 4, icon 16, aria-label 'Delete <tile>', title
'Delete this tile') with an Undo toast, and Add a tile brings it back; grip right 56, eye right 30 on a built-in tile (Project health keeps 30 and 4 and
has no bin); the label keeps 84px on its right on a built-in tile and 110px on a typed tile; the tiles keep a fixed fraction of the row (3 tiles in 4
places leave the 4th blank); a hidden Project health is one full-width 'Show project health here' line; the help text is the approved line, 14px, two
lines at most. Fictional data only.

Run: TZ=UTC python3 dev/run_tests.py test_theme_glance_edit_1336_p2
"""
import json
import unittest

from test_server import chrome, wait
from test_theme_glance_edit_1336 import ClassicEdit, tearDownModule  # noqa: F401

HINT = ("Drag a tile to move it, or hold Alt and press an arrow key. The eye hides a tile from the published page; the bin deletes it. "
        "Add a tile brings it back.")
OWN = {"id": "t1", "label": "Fictional own tile", "figure": "7", "tag": "Fine", "note": "Fictional note", "tone": "green"}
PROBE = """(function(sel){ function rel(el, cell){ var r = el.getBoundingClientRect(), c = cell.getBoundingClientRect();
    return { top: Math.round((r.top - c.top) * 10) / 10, right: Math.round((c.right - r.right) * 10) / 10, w: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10 }; }
  var out = {}, g = document.querySelector(sel + ' [data-glance-template]'), gr = g.getBoundingClientRect();
  out.glance = { w: gr.width, left: gr.left };
  out.tiles = {};
  g.querySelectorAll('.tcell').forEach(function(cell){
    var k = cell.dataset.tile, grip = cell.querySelector('.tgrip'), eye = cell.querySelector('.teye'), bin = cell.querySelector('[data-tile-bin]'),
      lab = cell.querySelector('.k, .tpl-gt-k'), tile = cell.querySelector('.fig, .tpl-gt-tile'), tr = tile.getBoundingClientRect(), icon = bin ? bin.querySelector('svg') : null, cr = cell.getBoundingClientRect();
    out.tiles[k] = { fx: Math.round((tr.left - gr.left) * 10) / 10, fw: Math.round(tr.width * 10) / 10, w: Math.round(cr.width * 10) / 10, x: Math.round((cr.left - gr.left) * 10) / 10, grip: grip ? rel(grip, cell) : null, eye: eye ? rel(eye, cell) : null,
      bin: bin ? Object.assign(rel(bin, cell), { icon: icon ? [Math.round(icon.getBoundingClientRect().width), Math.round(icon.getBoundingClientRect().height)] : null,
        label: bin.getAttribute('aria-label'), title: bin.getAttribute('title') }) : null,
      padR: lab ? getComputedStyle(lab).paddingRight : null }; });
  var sh = g.querySelector('[data-gt-showhealth]'); if (sh) { var s = sh.getBoundingClientRect(); out.show = { w: Math.round(s.width * 10) / 10, text: sh.textContent.trim() }; }
  var h = document.querySelector(sel + ' [data-glance-hint]'), cs = getComputedStyle(h);
  out.hint = { text: h.textContent, size: cs.fontSize, margin: cs.margin, lines: Math.round(h.getBoundingClientRect().height / parseFloat(cs.lineHeight)) };
  return out; })"""


class Controls(ClassicEdit):
    def seed_body(self, body):
        status, got = self.real_change({"project": "ABC", "kind": "report_sections", "op": "update", "id": self.ref, "changes": {"body": json.dumps(body)}})
        assert status == 200, got

    def look2(self, width, body=None, cdp_p=None):
        if body is not None:
            self.seed_body(body)
        with chrome() as cdp:
            p = self.page(cdp, width, False)
            return p.js(f"({PROBE})({json.dumps(self.sel())})")

    def test_P1_bin_and_controls_on_built_in_tiles(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.look2(width, {"v": 1})
                for k in ("overdue", "risks", "decisions"):
                    t = got["tiles"][k]
                    self.assertEqual({x: t["bin"][x] for x in ("top", "right", "w", "h")}, {"top": 4, "right": 4, "w": 24, "h": 24}, t)
                    self.assertEqual(t["bin"]["icon"], [16, 16], t)
                    self.assertEqual((t["bin"]["label"], t["bin"]["title"]), ({"overdue": "Delete Overdue actions", "risks": "Delete High risks and issues", "decisions": "Delete Decisions needed"}[k], "Delete this tile"))
                    self.assertEqual((t["grip"]["right"], t["grip"]["top"], t["grip"]["w"], t["grip"]["h"]), (56, 4, 24, 24), t)
                    self.assertEqual((t["eye"]["right"], t["eye"]["top"], t["eye"]["w"], t["eye"]["h"]), (30, 4, 24, 24), t)
                    self.assertEqual(t["padR"], "84px", t)

    def test_P2_project_health_has_no_bin_and_keeps_grip_30_eye_4(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.look2(width, {"v": 1, "health": {"shown": True}})
                h = got["tiles"]["health"]
                self.assertIsNone(h["bin"])
                self.assertEqual((h["grip"]["right"], h["eye"]["right"]), (30, 4), h)

    def test_P3_a_typed_tile_label_keeps_110(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.look2(width, {"v": 1, "bespoke": [OWN]})
                t = got["tiles"]["t1"]
                self.assertEqual(t["padR"], "110px", t)
                self.assertEqual((t["bin"]["right"], t["grip"]["right"], t["eye"]["right"]), (4, 56, 30), t)

    def test_P4_fixed_fraction_and_the_show_project_health_line(self):
        # Ruling 4: each tile is (100% - (cols - 1) x 12px) / cols wide, 12px between tiles. The tile is the drawn box (.fig), measured in Chrome;
        # the expected values are worked from the measured row width and the ruled 12 and 4 or 3, never read back from a CSS rule.
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.look2(width, {"v": 1, "health": {"shown": False}})
                g = got["glance"]["w"]
                names = list(got["tiles"])
                self.assertEqual(names, ["overdue", "risks", "decisions"], names)
                t = [got["tiles"][k] for k in names]
                want = (g - 3 * 12) / 4
                for i in range(3):
                    self.assertAlmostEqual(t[i]["fw"], want, delta=0.6, msg=f"tile {i} width {t[i]['fw']} want {want} (row {g}): {got}")
                    self.assertAlmostEqual(t[i]["fx"], i * (want + 12), delta=0.6, msg=f"tile {i} left {t[i]['fx']}: {got}")
                for i in range(2):
                    self.assertAlmostEqual(t[i + 1]["fx"] - (t[i]["fx"] + t[i]["fw"]), 12, delta=0.6, msg=f"gap between tiles: {got}")
                self.assertLess(t[2]["fx"] + t[2]["fw"], g - want / 2, f"the 4th place stays blank: {got}")
                self.assertEqual(got["show"]["text"], "Show project health here")
                self.assertAlmostEqual(got["show"]["w"], g, delta=0.6)
        with self.subTest(per_row=3):
            got = self.look2(1400, {"v": 1, "per_row": 3, "health": {"shown": False}})
            g = got["glance"]["w"]
            a, b = got["tiles"]["overdue"], got["tiles"]["risks"]
            self.assertAlmostEqual(a["fw"], (g - 2 * 12) / 3, delta=0.6, msg=str(got))
            self.assertAlmostEqual(b["fx"] - (a["fx"] + a["fw"]), 12, delta=0.6, msg=str(got))

    def test_P4b_bin_rests_in_body_colour_and_the_show_line_gap_is_14(self):
        probe = """(function(sel){ var g = document.querySelector(sel + ' [data-glance-template]'), e = document.createElement('i'), o = {};
          function res(v){ e.style.color = v; document.body.appendChild(e); var c = getComputedStyle(e).color; e.remove(); return c; }
          var bin = g.querySelector('[data-tile-bin]'), sh = g.querySelector('[data-gt-showhealth]');
          o.text = res('var(--text)'); o.muted = res('var(--text-muted)'); o.bin = bin ? getComputedStyle(bin).color : null;
          o.gap = sh ? getComputedStyle(sh).columnGap : null; return o; })"""
        for width in (1400, 900):
            with self.subTest(width=width):
                self.seed_body({"v": 1, "health": {"shown": False}})
                with chrome() as cdp:
                    got = self.page(cdp, width, False).js(f"({probe})({json.dumps(self.sel())})")
                self.assertEqual(got["bin"], got["text"], got)
                self.assertNotEqual(got["bin"], got["muted"], got)
                self.assertEqual(got["gap"], "14px", got)

    def test_P5_the_help_text_is_the_approved_line(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                h = self.look2(width, {"v": 1})["hint"]
                self.assertEqual(h["text"], HINT)
                self.assertEqual((h["size"], h["margin"]), ("14px", "8px 2px 0px"), h)
                self.assertLessEqual(h["lines"], 2, h)

    def test_P6_the_bin_deletes_with_undo_and_add_a_tile_brings_it_back(self):
        self.seed_body({"v": 1})
        with chrome() as cdp:
            p = self.page(cdp, 1400, False)
            p.js(f"document.querySelector({self.q('[data-tile=overdue] [data-tile-bin]')}).click()")
            p.until(f"!document.querySelector({self.q('[data-tile=overdue]')})", "the tile left the strip")
            self.assertTrue(wait(lambda: self.body().get("builtin", {}).get("overdue", {}).get("hidden") is True, 10), self.body())
            self.assertEqual(self.toast(p).split("Undo")[0].strip(), "Removed: Overdue actions")
            self.undo(p)
            p.until(f"!!document.querySelector({self.q('[data-tile=overdue]')})", "undone: the tile is back")
            self.assertTrue(wait(lambda: not self.body().get("builtin"), 10), self.body())
            p.js(f"document.querySelector({self.q('[data-tile=overdue] [data-tile-bin]')}).click()")
            p.until(f"!document.querySelector({self.q('[data-tile=overdue]')})", "deleted again")
            p.js(f"document.querySelector({self.q('.tileadd')}).click()")
            p.until("!!document.querySelector('.ddmenu[role=menu] [role=menuitem]')", "the Add a tile menu")
            self.assertIn("Overdue actions", p.js("[...document.querySelectorAll('.ddmenu[role=menu] [role=menuitem]')].map(b => b.textContent).join('|')"))
            p.js("document.querySelector('.ddmenu[role=menu] [role=menuitem]').click()")
            p.until(f"!!document.querySelector({self.q('[data-tile=overdue]')})", "added back")


if __name__ == "__main__":
    unittest.main()


class HintAndToastSource(unittest.TestCase):
    """The hint closing words and the bin toast, read from the source so they are pinned without a browser."""

    SRC = (__import__("pathlib").Path(__file__).resolve().parent.parent / "src/clark/page/src/edit/templates/GlanceTemplate.jsx").read_text(encoding="utf-8")

    def test_the_hint_line_in_the_source_is_the_approved_one(self):
        self.assertIn('hint: "' + HINT + '"', self.SRC)

    def test_the_bin_says_it_deletes_and_never_removes_it_from_the_strip(self):
        self.assertIn("the bin deletes it. Add a tile brings it back.", self.SRC)
        self.assertNotIn("from the strip", self.SRC.split("hint:")[1].split("\n")[0])

    def test_the_bin_toast_is_removed_colon_and_the_tile_name(self):
        line = [l for l in self.SRC.splitlines() if l.lstrip().startswith("const del = ")][0]
        self.assertIn("`Removed: ${titleOf(key)}`", line)
        self.assertNotIn("Deleted", line)
