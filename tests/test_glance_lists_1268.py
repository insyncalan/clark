"""Row 1268, slice s1: the At a glance tiles count what a Work items list reaches when a built-in section is hidden.

Run: python3 dev/run_tests.py test_glance_lists_1268
A list reaches only its own rows (publish.select), so a tile of a hidden section counts those rows and no other; with no list the
tile stays out as before. Fictional data, the clock fixed (ON).
"""
import json
import unittest

from _paths import ROOT   # noqa: F401

from clark import glance as g, publish
from clark import store as store_module
from test_glance import ON, RULES, action, data, decision, raid, sections


def body(**kw):
    return store_module.check_section_body("workitems", json.dumps({"mode": "all", **kw}))


def run(d, hide, items_filter=None):
    secs = sections(*hide)
    if items_filter is not None:
        secs.append({"id": "s-list", "type": "workitems", "title": "Mine", "body": items_filter, "beside": 0, "hidden": 0, "sort_order": 50})
    i = {"data": d, "hidden": [], "sections": secs, "label_rules": RULES, "as_at": ON, "glance_tiles": []}
    return publish.add_glance(publish.select(i), i)["data"]["glance"]["tiles"]


def probe():
    return data(actions=[action(1, "2026-10-20"), action(2, "2026-10-21"), action(3, "2026-10-22", owner="Pat Demo")],
                raid_=[raid(1, priority="High")], decisions=[decision(1)])


def by(tiles):
    return {t["tile"]: t for t in tiles}


class Lists(unittest.TestCase):
    def test_a_hidden_section_and_no_list_leaves_the_tile_out_as_before(self):
        got = by(run(probe(), ("actions",)))
        self.assertNotIn("overdue", got)
        self.assertIn("risks", got)

    def test_a_list_brings_the_tile_back_counting_its_own_rows_only(self):
        got = by(run(probe(), ("actions",), body(owner=["Pat Demo"])))
        self.assertEqual(got["overdue"]["value"], 1)
        self.assertEqual(got["overdue"]["detail"], "of 1 open action")

    def test_a_list_of_another_kind_does_not_bring_the_tile_back(self):
        self.assertNotIn("overdue", by(run(probe(), ("actions",), body(kinds=["risk"]))))

    def test_a_list_that_reaches_nothing_leaves_the_tile_out(self):
        self.assertNotIn("overdue", by(run(probe(), ("actions",), body(owner=["Nobody Demo"]))))

    def test_a_shown_section_counts_every_row_as_before(self):
        self.assertEqual(by(run(probe(), (), body(owner=["Pat Demo"])))["overdue"]["value"], 3)

    def test_the_decisions_tile_is_hidden_by_default_and_stays_so(self):
        self.assertNotIn("decisions", by(run(probe(), ("decisions",), body(kinds=["decision"]))))

    def test_the_risks_tile_counts_the_listed_risks(self):
        got = by(run(probe(), ("raid",), body(kinds=["risk"])))
        self.assertEqual(got["risks"]["value"], 1)


if __name__ == "__main__":
    unittest.main()
