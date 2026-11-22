"""Row 1336 part 3, the control: the At a glance template in Edit under Cards draws the DOM it drew on main. The Classic bin and the Classic help
text are drawn only when the Classic Theme is layered (GlanceTemplate.jsx, the `extra:` line and the Hint line); under Cards no tile carries a bin
or a `tdel` button, the typed tile keeps its own controls, and the help line is the shared text plus the two template sentences. Chrome at 1400 and
900 px, light. Fictional data only.

Run: TZ=UTC python3 dev/run_tests.py test_theme_glance_cards_dom_1336_p3
"""
import json
import unittest

from test_theme_glance_edit_1336 import ClassicEdit, tearDownModule  # noqa: F401
from test_server import chrome

OWN = {"id": "t1", "label": "Fictional own tile", "figure": "7", "tag": "Fine", "note": "Fictional note", "tone": "green"}
HINT = ("Drag a tile to move it, or hold Alt and press an arrow key. Use the eye to hide or show a tile. Right-click a tile to change its colour. "
        "Hidden tiles are left out of the published page. The eye on Project health hides it completely. "
        "Use Add a tile to make your own. Click the pencil on your own tile to edit it.")
PROBE = """(function(sel){ var g = document.querySelector(sel + ' [data-glance-template]'), out = { theme: !!document.getElementById('theme'), tiles: {} };
  g.querySelectorAll('.tcell').forEach(function(c){ out.tiles[c.dataset.tile] = { cls: c.className,
    kids: Array.prototype.map.call(c.children, function(k){ return k.tagName.toLowerCase() + '.' + k.className; }),
    bins: c.querySelectorAll('[data-tile-bin], .tdel').length }; });
  var h = document.querySelector(sel + ' [data-glance-hint]'); out.hint = { text: h.textContent, tag: h.tagName.toLowerCase(), cls: h.className };
  return out; })"""


class CardsDom(ClassicEdit):
    theme_name = None
    test_T1_classic_tile_padding_is_12_and_16_and_the_pill_clears_the_border = None      # the Classic tests of the base class are not run here
    test_T2_classic_status_dot_is_8_by_8_and_shown = None
    test_T3_the_block_sits_before_the_row_1314_block_which_stays_the_last_row_block = None

    def look3(self, width, body):
        status, got = self.real_change({"project": "ABC", "kind": "report_sections", "op": "update", "id": self.ref, "changes": {"body": json.dumps(body)}})
        assert status == 200, got
        with chrome() as cdp:
            return self.page(cdp, width, False).js(f"({PROBE})({json.dumps(self.sel())})")

    def test_D1_cards_draws_no_bin_and_the_shared_help_line(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.look3(width, {"v": 1, "bespoke": [OWN]})
                self.assertFalse(got["theme"], got)
                self.assertEqual(sorted(got["tiles"]), ["decisions", "health", "overdue", "risks", "t1"], got)
                for k, t in got["tiles"].items():
                    self.assertEqual(t["bins"], 1 if k == "t1" else 0, (k, t))      # the typed tile keeps its own tdel (OwnControls); no built-in tile has a bin
                self.assertEqual(got["hint"], {"text": HINT, "tag": "p", "cls": "glance-hint"}, got)

    def test_D2_the_tiles_draw_the_elements_and_classes_main_draws(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                tiles = self.look3(width, {"v": 1, "bespoke": [OWN]})["tiles"]
                self.assertEqual({k: (t["cls"], t["kids"]) for k, t in tiles.items()}, MAIN_DOM, tiles)


del ClassicEdit      # only CardsDom runs here, not the Classic tests the base class carries

# Read from origin/main's page (the same probe run on a checkout of main: the Cards DOM did not change).
MAIN_DOM = {
    "decisions": ("tcell", ["button.tgrip", "button.teye", "button.fig go rag-a"]),
    "health": ("tcell health", ["button.tgrip", "button.teye", "div.fig health-fig rag-g"]),
    "overdue": ("tcell", ["button.tgrip", "button.teye", "button.fig go rag-r"]),
    "risks": ("tcell", ["button.tgrip", "button.teye", "button.fig go rag-r"]),
    "t1": ("tcell own", ["button.tgrip", "button.teye", "button.tpen", "button.tdel", "div.fig tpl-gt-tile tone-g"]),
}

if __name__ == "__main__":
    unittest.main()
