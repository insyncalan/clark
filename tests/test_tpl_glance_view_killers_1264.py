"""Row 1264 slice 3: killer tests for the View's tile rules (templates/GlanceTemplate.jsx): which counting tiles have rows, which typed tiles
draw, an outline that is not one of the four, the order of tiles the order list does not name. Fictional data only.

Run: python3 dev/run_tests.py test_tpl_glance_view_killers_1264
"""
import json
import unittest

from _demo import USER
from test_report_editor import Base, tearDownModule  # noqa: F401
from test_tpl_glance_page_1264 import Page, seed_rows


def add(test, kind):
    if kind == "action":
        test.demo.action(description="Fictional action for the glance tiles", due_date="2020-01-01")
        return
    with test.store.step("dashboard", USER) as st:
        if kind in ("Risk", "Issue"):
            st.create("raid", {"project": "ABC", "type": kind, "description": "Fictional glance " + kind.lower(), "raised": "2026-10-01", "source": "demo",
                               "impact": "High", "likelihood": "High", "owner": "Pat Demo"})
        else:
            st.create("decisions", {"project": "ABC", "decision": "Fictional glance decision", "status": "Pending", "needed_by": "2031-02-01", "source": "demo"})


class Tiles(Base):
    make = Page.make
    look = Page.look

    def raw(self, body):
        """A body the change route would refuse (an older or hand-written one): written straight to the store."""
        with self.store.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": "glancetemplate", "title": "Fictional glance template", "sort_order": 999})
        self.store.con.execute("UPDATE report_sections SET body = ? WHERE id = ?", (json.dumps(body), ref))
        self.store.con.commit()
        return ref

    def keys(self, body, raw=False):
        got = self.look(self.raw(body) if raw else self.make(body), 1400, "light")
        return None if got is None else [t["key"] for t in got["tiles"]]

    def test_a_counting_tile_is_drawn_only_for_its_own_kind_of_row(self):
        for kind, want in (("action", ["overdue"]), ("Risk", ["risks"]), ("Issue", ["risks"]), ("decision", ["decisions"])):
            with self.subTest(kind=kind):
                super().setUp()
                add(self, kind)
                self.assertEqual(self.keys({"v": 1, "bespoke": [{"id": "b1", "label": "Fictional", "figure": "1", "tone": "green"}]})[:len(want)], want)
                self.assertEqual(self.keys({"v": 1, "bespoke": [{"id": "b1", "label": "Fictional", "figure": "1", "tone": "green"}]}), want + ["b1"])

    def test_a_typed_tile_with_a_blank_label_is_not_drawn(self):
        seed_rows(self)
        got = self.keys({"v": 1, "builtin": {n: {"hidden": True} for n in ("overdue", "risks", "decisions")}, "bespoke": [{"id": "b1", "label": "   ", "figure": "1"}]}, raw=True)
        self.assertEqual(got, [], "a typed tile needs a label: with none the section has nothing but the emptied sentence")

    def test_an_outline_that_is_not_one_of_the_four_is_the_automatic_colour(self):
        seed_rows(self)
        auto = self.look(self.make({"v": 1}), 1400, "light")["tiles"]
        odd = self.look(self.raw({"v": 1, "builtin": {"overdue": {"outline": "Z"}, "risks": {"outline": "zz"}}}), 1400, "light")["tiles"]
        self.assertEqual([t["cls"] for t in odd], [t["cls"] for t in auto])

    def test_tiles_the_order_does_not_name_follow_the_named_ones_in_the_default_order(self):
        seed_rows(self)
        self.assertEqual(self.keys({"v": 1, "order": ["decisions"]}, raw=True), ["decisions", "overdue", "risks"])
        self.assertEqual(self.keys({"v": 1, "order": ["risks", "health"]}, raw=True), ["risks", "overdue", "decisions"])


if __name__ == "__main__":
    unittest.main()
