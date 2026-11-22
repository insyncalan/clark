"""Row 1303 part 1: a tile hidden with the eye leaves Edit view; Add a tile lists it and shows it again. No Chrome.

Run: python3 dev/run_tests.py test_glance_hidden_1303
`Logic` runs glanceHidden.js in node (a copy named .mjs, so it loads as a module). `Wiring` reads the sources: each test names the operand it kills.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import SRC  # noqa: F401

PAGE = SRC / "clark" / "page" / "src"
NODE = shutil.which("node")


def read(*parts):
    return PAGE.joinpath(*parts).read_text(encoding="utf-8")


def run_node(expr):
    with tempfile.TemporaryDirectory() as d:
        mod = Path(d) / "hidden.mjs"
        mod.write_text(read("glanceHidden.js"), encoding="utf-8")
        out = subprocess.run([NODE, "--input-type=module", "-e", f"import * as H from {json.dumps(mod.as_uri())}; console.log(JSON.stringify({expr}));"],
                             capture_output=True, text=True, timeout=60, check=True)
    return json.loads(out.stdout)


TILES = "[{key:'health'},{key:'overdue',hidden:true},{key:'risks'},{key:'decisions',hidden:true},{key:'t1',hidden:true},{key:'t2'}]"


@unittest.skipUnless(NODE, "node is needed for the logic test")
class Logic(unittest.TestCase):
    def test_drawn_tiles_leave_out_the_hidden_ones_and_keep_the_order(self):         # kills: filter not negated, order changed
        self.assertEqual(run_node(f"H.drawnTiles({TILES}).map(t => t.key)"), ["health", "risks", "t2"])

    def test_hidden_tiles_are_the_hidden_ones_in_order(self):                          # kills: filter negated, order changed
        self.assertEqual(run_node(f"H.hiddenTiles({TILES}).map(t => t.key)"), ["overdue", "decisions", "t1"])

    def test_project_health_is_never_offered_in_add_a_tile(self):                     # kills: the health exclusion removed
        self.assertEqual(run_node("H.hiddenTiles([{key:'health',hidden:true},{key:'risks',hidden:true}]).map(t => t.key)"), ["risks"])

    def test_nothing_hidden_offers_nothing_and_draws_everything(self):                # kills: the two lists not being complements
        self.assertEqual(run_node("[H.hiddenTiles([{key:'a'},{key:'b'}]).length, H.drawnTiles([{key:'a'},{key:'b'}]).length]"), [0, 2])

    def test_every_tile_is_in_exactly_one_list_except_hidden_health(self):            # kills: a tile lost or listed twice
        got = run_node(f"[H.drawnTiles({TILES}).length, H.hiddenTiles({TILES}).length]")
        self.assertEqual(sum(got), 6)


class Wiring(unittest.TestCase):
    def test_the_live_page_draws_no_hidden_tile_in_edit_and_lists_it_in_add_a_tile(self):   # kills: `editing ||` filter back, list not from drawnTiles
        s = read("components", "Glance.jsx")
        self.assertIn("const list = drawnTiles(every)", s)
        self.assertNotIn("editing || !t.hidden", s)
        self.assertIn("hidden = editing ? hiddenTiles(every) : []", s)
        self.assertIn("editing && hidden.length ? <tools.glance.AddTile", s)                 # kills: the menu drawn in View, or with nothing to show

    def test_the_health_share_counts_only_visible_other_tiles_and_only_without_a_hidden_one_drawn(self):   # kills: the others / share operands and the data-others attribute
        s = read("components", "Glance.jsx")
        self.assertIn('const others = list.filter((t) => t.key !== "health" && !t.hidden).length;', s)
        self.assertIn('const share = list.some((t) => t.key === "health" && !t.hidden) && !list.some((t) => t.hidden) && (others === 1 || others === 2) ? String(others) : undefined;', s)
        self.assertIn('<div class="glance" data-glance data-others={share}>', s)

    def test_the_live_pick_shows_the_tile_again_through_the_one_hide_change(self):          # kills: show asking hidden = true, or a change of its own
        s = read("edit", "GlanceEdit.jsx")
        self.assertIn("show: (key) => hideTile(key, false)", s)
        self.assertIn("onPick={onShow}", s)
        self.assertIn('label={ADD_WORDS.add}', s)
        self.assertEqual(s.count('add: "Add a tile"'), 1)

    def test_the_template_draws_the_visible_tiles_and_offers_the_hidden_ones(self):         # kills: list from `every`, hidden ones not passed to the menu
        s = read("edit", "templates", "GlanceTemplate.jsx")
        self.assertIn("const list = drawnTiles(every), away = hiddenTiles(every)", s)
        self.assertIn("hidden={away.map(", s)
        self.assertIn("show={(key) => act.hide(key, false)}", s)
        self.assertIn('list.every((t) => t.key === "health") ?', s)                         # kills: the empty note keyed on the hidden flag, which no drawn tile has now

    def test_the_template_menu_lists_hidden_tiles_before_your_own_tile(self):               # kills: order swapped, pick of a hidden tile calling add
        s = read("edit", "templates", "glanceTileEditor.jsx")
        self.assertIn("const items = [...hidden.map(", s)
        self.assertLess(s.index("...hidden.map("), s.index('id: "own"'))
        self.assertIn('id === "own" ? tools.add() : show && show(id.slice(5))', s)
        self.assertIn("`show:${t.key}`", s)


if __name__ == "__main__":
    unittest.main()
