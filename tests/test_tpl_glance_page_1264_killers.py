"""Row 1264 slice 3, killer tests from the mutation review: what test_tpl_glance_page_1264 leaves open. Fictional data only.

Run: python3 dev/run_tests.py test_tpl_glance_page_1264_killers
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from test_report_editor import EMPTY_BRANDING, Base, Pg, tearDownModule  # noqa: F401
from test_server import chrome
import test_tpl_glance_page_1264 as P

from clark import publish

HIDE3 = {n: {"hidden": True} for n in ("overdue", "risks", "decisions")}


class Killers(Base):
    make = P.Page.make
    look = P.Page.look

    def test_k1_a_bespoke_tile_draws_its_own_figure_and_note(self):
        ref = self.make({"v": 1, "builtin": HIDE3, "bespoke": P.BESPOKE})
        by = {t["key"]: t for t in self.look(ref, 1400, "light")["tiles"]}
        self.assertEqual([by[k]["figure"] for k in ("b1", "b2", "b3", "b4", "b5")], ["7", "2", "9", "1", "4"])
        self.assertEqual(by["b1"]["note"], "Fictional note one")
        self.assertEqual(by["b2"]["note"], "Fictional note two")
        self.assertIsNone(by["b3"]["note"], "no note typed: no note drawn")

    def test_k2_a_hand_set_no_colour_outline_shows_the_neutral_tone_and_no_tag_word(self):
        P.seed_rows(self)
        ref = self.make({"v": 1, "builtin": {"risks": {"outline": "N"}}})
        by = {t["key"]: t for t in self.look(ref, 1400, "light")["tiles"]}
        self.assertIn("tone-n", by["risks"]["cls"])
        self.assertIsNone(by["risks"]["tag"], "no colour has no word")

    def test_k3_a_key_missing_from_the_order_comes_after_the_listed_ones(self):
        P.seed_rows(self)
        ref = self.make({"v": 1, "order": ["b2"], "bespoke": P.BESPOKE[:2]})
        got = [t["key"] for t in self.look(ref, 1400, "light")["tiles"]]
        self.assertEqual(got, ["b2", "overdue", "risks", "decisions", "b1"])

    def test_k4_the_tag_word_is_drawn_in_the_tag_token_of_its_tone_in_both_looks(self):
        ref = self.make({"v": 1, "builtin": HIDE3, "bespoke": [{**b, "tag": "Word"} for b in P.BESPOKE]})
        want = {"b1": "--status-green-text", "b2": "--status-amber-text", "b3": "--status-red-text", "b4": "--brand-blue-strong", "b5": "--text-muted"}
        for theme in ("light", "dark"):
            tk = P.tokens(theme)
            by = {t["key"]: t for t in self.look(ref, 1400, theme)["tiles"]}
            for key, name in want.items():
                with self.subTest(theme=theme, tile=key):
                    h = tk[name].lstrip("#")
                    self.assertEqual(by[key]["tagColor"], f"rgb({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)})")

    def draw_file(self, cdp):
        out = tempfile.mkdtemp(prefix="clark-1264-k-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        path = Path(publish.publish(self.store, "ABC", out, by_user=USER, now="2030-01-15", branding=EMPTY_BRANDING)["path"])
        tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
        p = Pg(self, cdp, sid)
        p.until("document.documentElement.dataset.ready === '1' && !!document.querySelector('h1')", "the file drew")
        return p

    def tiles_in_file(self, ref):
        with chrome() as cdp:
            p = self.draw_file(cdp)
            return p.js(f"(function(){{ var s = document.querySelector('[data-id={json.dumps(ref)}]'); if (!s) return null;"
                        " return [...s.querySelectorAll('.tpl-gt-tile')].map(function(t){ return t.dataset.tile; }); })()")

    def test_k5_a_published_file_draws_the_bespoke_tiles_and_no_counting_tile(self):
        ref = self.make({"v": 1, "bespoke": P.BESPOKE[:2]})
        self.assertEqual(self.tiles_in_file(ref), ["b1", "b2"], "the file carries no counts yet")

    def test_k6_a_published_file_leaves_out_a_glance_section_that_has_only_counting_tiles(self):
        ref = self.make({"v": 1})
        self.assertIsNone(self.tiles_in_file(ref), "nothing to show in a file: no section")

    def test_k7_with_no_rows_a_counting_tile_is_not_drawn_but_a_bespoke_one_is(self):
        ref = self.make({"v": 1, "bespoke": P.BESPOKE[:1]})
        self.assertEqual([t["key"] for t in self.look(ref, 1400, "light")["tiles"]], ["b1"], "no rows of a kind, no counting tile of it")

    def test_k8_a_figure_of_zero_is_drawn_for_a_bespoke_and_for_a_counting_tile(self):
        self.demo.action(description="Fictional action not yet due", due_date="2099-01-01")
        ref = self.make({"v": 1, "builtin": {"risks": {"hidden": True}, "decisions": {"hidden": True}}, "bespoke": [{**P.BESPOKE[0], "figure": "0"}]})
        by = {t["key"]: t for t in self.look(ref, 1400, "light")["tiles"]}
        self.assertEqual(by["b1"]["figure"], "0", "a typed 0 is a figure")
        self.assertEqual(by["overdue"]["figure"], "0", "no overdue action is a 0, not a blank")

    def test_k9_the_neutral_dot_is_a_ring_with_no_fill(self):
        ref = self.make({"v": 1, "builtin": HIDE3, "bespoke": P.BESPOKE[4:]})
        shape = {t["key"]: t for t in self.look(ref, 1400, "light")["tiles"]}["b5"]["shape"].split("|")
        self.assertEqual(shape[2], "rgba(0, 0, 0, 0)", "a ring is empty inside")
        self.assertEqual(shape[1], "50%")


if __name__ == "__main__":
    unittest.main()
