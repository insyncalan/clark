"""Item 1268: a page of Work items lists reaches the Word report, the client workbook and the At a glance tiles as the built-in sections do.

Run: python3 dev/run_tests.py test_work_items_list_exports
The rows are the #39 plant (made up) through publish.select(); the three built-in work sections are switched off and one list per
kind takes their place. Nothing a client may not see is in any file, whatever a list's filter says.
"""
import copy
import io
import json
import unittest

from _paths import ROOT   # noqa: F401  (puts src/ on the path)

import _publish_fixture as fx
from openpyxl import load_workbook
from clark import docx_build, docx_read, glance, publish

BUILT_IN = ("raid", "actions", "decisions")


def pages(lists, hide_built_in=True, plant=None):
    inp = fx.inputs(plant)
    for s in inp["sections"]:
        if hide_built_in and s["type"] in BUILT_IN:
            s["hidden"] = 1
    for n, (title, body) in enumerate(lists):
        inp["sections"].append({"id": f"wl-{n}", "type": "workitems", "title": title, "hidden": 0, "sort_order": 90 + n,
                                "body": json.dumps(body)})
    return inp


def three():
    return [("Risks and issues", {"mode": "all", "kinds": ["risk", "issue"]}), ("Open actions", {"mode": "all", "kinds": ["action"]}),
            ("Decisions", {"mode": "all", "kinds": ["decision"]})]


def word_text(pub):
    return "\n".join(str(b) for b in docx_read.read(docx_build.build(pub), "r.docx").blocks)


class Exports(unittest.TestCase):
    def test_the_lists_carry_the_rows_the_built_in_sections_carry(self):
        base = publish.select(fx.inputs())
        lists = publish.select(pages(three()))
        for kind in ("actions", "raid", "decisions"):
            self.assertEqual(sorted(r["id"] for r in lists["data"][kind]), sorted(r["id"] for r in base["data"][kind]), kind)
        ids = [i for s in lists["sections"] if s["type"] == "workitems" for i in s["items"]]
        want = [r["id"] for k in ("actions", "raid", "decisions") for r in base["data"][k]]
        self.assertEqual(sorted(ids), sorted(want))

    def test_word_prints_every_row_of_the_lists_and_the_page_without_lists_prints_none(self):
        text = word_text(publish.select(pages(three())))
        base = publish.select(fx.inputs())
        for k in ("actions", "raid", "decisions"):
            for r in base["data"][k]:
                self.assertIn(r["id"], text, r["id"])
        for title in ("Risks and issues", "Open actions", "Decisions"):
            self.assertIn(title, text)
        bare = word_text(publish.select(pages([])))
        self.assertNotIn("PUB-A-001", bare)

    def test_the_client_workbook_has_a_sheet_for_each_list_and_only_the_rows_a_list_carries(self):
        pub = publish.select(pages([("Open actions", {"mode": "all", "kinds": ["action"], "max": 1})]))
        from clark import excel_client
        self.assertEqual([t for t in excel_client.sheet_tables(pub) if t in ("actions", "raid", "decisions")], ["actions"])
        wb = load_workbook(io.BytesIO(excel_client.workbook_bytes(pub)))
        cells = [str(c.value) for ws in wb.worksheets for row in ws.iter_rows() for c in row if c.value is not None]
        self.assertTrue(any("PUB-A-001" in c for c in cells))
        self.assertFalse(any("PUB-001" == c or "PUB-D-001" == c for c in cells), "a risk or a decision is on no sheet when no list carries it")

    def test_at_a_glance_counts_are_the_same_with_the_lists_in_the_client_version(self):
        def tiles(inp):
            rows = dict(inp["data"], report_sections=inp["sections"])
            return {t["tile"]: (t["value"], t["detail"]) for t in glance.tiles(rows, inp["as_at"], for_client=True, hidden=set())}
        built_in = tiles(fx.inputs())
        lists = tiles(pages(three()))
        self.assertEqual(lists, built_in)
        self.assertEqual({"overdue", "risks", "decisions"} - set(lists), set(), "no tile is dropped for want of a built-in section")
        only = tiles(pages([("Open actions", {"mode": "all", "kinds": ["action"]})]))
        self.assertIn("overdue", only)
        self.assertNotIn("risks", only, "a client who can only open actions has no risk tile")
        self.assertNotIn("decisions", only)

    def test_hostile_a_hidden_item_never_reaches_a_list_whatever_the_filter(self):
        plant = fx.load()
        hide = plant["data"]["actions"][0]["id"]
        plant["hidden"] = list(plant.get("hidden") or []) + [hide]
        plant["data"]["actions"][1]["client_visible"] = 0
        off = plant["data"]["actions"][1]["id"]
        plant["data"]["actions"][2]["archived"] = 1
        gone = plant["data"]["actions"][2]["id"]
        pub = publish.select(pages([("All", {"mode": "all", "kinds": ["action", "risk", "issue", "assumption", "dependency", "decision"]})], plant=plant))
        listed = [i for s in pub["sections"] if s["type"] == "workitems" for i in s["items"]]
        for bad in (hide, off, gone):
            self.assertNotIn(bad, listed)
            self.assertNotIn(bad, word_text(pub))
            self.assertNotIn(bad, json.dumps(pub["data"]))
        self.assertTrue(listed)

    def test_a_hidden_list_exposes_nothing_and_leaves_the_built_in_rows_out(self):
        inp = pages([("Open actions", {"mode": "all", "kinds": ["action"]})])
        inp["sections"][-1]["hidden"] = 1
        pub = publish.select(inp)
        self.assertEqual([len(pub["data"][k]) for k in BUILT_IN], [0, 0, 0])
        self.assertEqual(publish.listed_types(inp["sections"]), set())

    def test_a_list_of_one_kind_opens_only_that_kind(self):
        pub = publish.select(pages([("Open actions", {"mode": "all", "kinds": ["action"]})]))
        self.assertTrue(pub["data"]["actions"])
        self.assertEqual((pub["data"]["raid"], pub["data"]["decisions"]), ([], []))

    def test_a_list_that_names_no_kind_does_not_reopen_a_hidden_built_in_section(self):
        pub = publish.select(pages([("Everything", {"mode": "all"})]))
        self.assertEqual([len(pub["data"][k]) for k in BUILT_IN], [0, 0, 0])


if __name__ == "__main__":
    unittest.main()
