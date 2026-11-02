"""#45: the published At a glance figures and use case strip (publish.add_glance; guarded: the publish module).

Run: python3 dev/run_tests.py test_publish_glance
add_glance counts from select's own output, so a figure can never include a row select dropped. All rows are fictional; the
clock is fixed (ON).
"""
import json
import re
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from clark import glance as g, publish
from test_glance import ON, PLANTED_MARKER, RULES, action, data, decision, raid, sections, use_case

SHAPE_TILE = {"tile", "label", "value", "detail", "colour", "outline"}
SHAPE_STRIP = {"total", "words", "rows"}


def inputs(d, hide=(), tiles=None, left_off=()):
    return {"data": d, "hidden": list(left_off), "sections": sections(*hide), "label_rules": RULES, "as_at": ON,
            "glance_tiles": tiles or []}


def published(d, **kw):
    i = inputs(d, **kw)
    return publish.add_glance(publish.select(i), i)["data"]


def tile_row(tile, order, hidden=0, outline=""):
    return {"project": "ABC", "tile": tile, "hidden": hidden, "outline": outline, "sort_order": order}


def names(pub):
    return [t["tile"] for t in pub["glance"]["tiles"]]


def late(rows, key="due_date"):
    return [r for r in rows if r["status"] not in g.CLOSED and r[key] and r[key] < ON]


def probe():
    acts = [action(1, "2026-10-20", use_case="ABC-U-001"),                       # kept
            action(2, "2026-10-20", use_case="ABC-U-001"),                       # Sensitive
            action(3, "2026-10-20", use_case="ABC-U-001", client_visible=0),     # flag off
            action(4, "2026-10-20", use_case="ABC-U-001"),                       # left off the page by the eye
            action(5, "2026-10-20", use_case="ABC-U-002")]                       # the only item of use case 2; Sensitive
    risks = [raid(1, priority="High"), raid(2, priority="High")]                 # the second is Sensitive
    ucs = [use_case(1), use_case(2, "Flag"), use_case(3, "High risk"), use_case(4, "On track", client_visible=0),
           use_case(5, "Flag", archived=1)]
    return data(actions=acts, raid_=risks, decisions=[decision(1, needed_by="2026-10-01")], use_cases=ucs,
                labels={"ABC-A-002": ["Sensitive"], "ABC-A-005": ["Sensitive"], "ABC-002": ["Sensitive"]})


class Numbers(unittest.TestCase):
    def test_each_number_equals_the_published_list_and_the_editor_keeps_counting_everything(self):
        d = probe()
        pub = published(d, left_off=["ABC-A-004"])
        tiles = {t["tile"]: t for t in pub["glance"]["tiles"]}
        self.assertEqual([a["id"] for a in pub["actions"]], ["ABC-A-001"])
        self.assertEqual(tiles["overdue"]["value"], len(late(pub["actions"])))
        self.assertEqual(tiles["overdue"]["value"], 1)
        self.assertEqual(tiles["risks"]["value"], 1)
        editor = {t["tile"]: t for t in g.tiles(d, ON)}
        self.assertEqual((editor["overdue"]["value"], editor["risks"]["value"]), (5, 2), "the editor counts every open row")

    def test_actions_hidden_removes_the_overdue_tile_and_raid_hidden_removes_high_risks(self):
        d = probe()
        d["glance_tiles"] = [tile_row("decisions", 4096)]
        self.assertNotIn("overdue", names(published(d, hide=("actions",))))
        self.assertIn("risks", names(published(d, hide=("actions",))))
        self.assertNotIn("risks", names(published(d, hide=("raid",))))
        self.assertNotIn("decisions", names(published(d, hide=("decisions",))))

    def test_a_hidden_tile_is_absent_from_the_bytes_and_order_and_outline_follow_the_rows(self):
        d = probe()
        rows = [tile_row("risks", 1024, outline="G"), tile_row("overdue", 2048, hidden=1), tile_row("health", 3072, outline="R"),
                tile_row("decisions", 4096, outline="N")]
        pub = published(d, tiles=rows)
        self.assertEqual(names(pub), ["risks", "health", "decisions"])
        self.assertNotIn("Overdue actions", json.dumps(pub["glance"]))
        by = {t["tile"]: t for t in pub["glance"]["tiles"]}
        self.assertEqual((by["risks"]["outline"], by["health"]["outline"], by["decisions"]["outline"]), ("G", "R", "N"))
        self.assertEqual(by["decisions"]["colour"], "N", "the published colour is the colour shown: an outline of N is none")
        self.assertEqual(by["risks"]["colour"], "G")

    def test_no_rows_gives_the_defaults_and_no_decisions_tile(self):
        self.assertEqual(names(published(probe())), ["health", "overdue", "risks"])

    def test_health_is_always_carried_even_when_its_tile_is_hidden_in_the_editor(self):
        pub = published(probe(), tiles=[tile_row("health", 1024, hidden=1)])
        self.assertEqual(names(pub)[0], "health")
        self.assertEqual(pub["glance"]["tiles"][0]["value"], "At risk")

    def test_the_glance_section_hidden_carries_no_tiles(self):
        pub = published(probe(), hide=("glance",))
        self.assertEqual(pub["glance"]["tiles"], [])
        self.assertIn("strip", pub["glance"], "the use case summary is its own section")


class ReasonInTheFile(unittest.TestCase):
    def reason(self, stored):
        d = probe()
        d["project"]["health_reason"] = stored
        return published(d)["project"]["health_reason"]

    def test_a_stored_reason_reaches_the_file_cleaned_and_capped(self):
        got = self.reason("A\u202eB\u200bC\x00D\r\nE\ud800F<script>" + "y" * 3000)
        self.assertEqual(got[:12], "ABCD\nEF<scri")
        self.assertEqual(len(got), publish.REASON_LIMIT)
        self.assertFalse([c for c in got if c != "\n" and (ord(c) < 32 or c in "\u202e\u200b\ud800")])

    def test_a_good_reason_and_no_reason_are_carried_as_they_are(self):
        self.assertEqual(self.reason("Supplier is late\nand tests slip"), "Supplier is late\nand tests slip")
        self.assertIsNone(self.reason(None))

    def test_the_limit_is_the_writers(self):
        from clark import store
        self.assertEqual(publish.REASON_LIMIT, store.REASON_LIMIT)


class Strip(unittest.TestCase):
    def test_only_kept_use_cases_are_counted_and_each_row_equals_the_published_lists(self):
        pub = published(probe(), left_off=["ABC-A-004"])
        strip = pub["glance"]["strip"]
        self.assertEqual([u["id"] for u in pub["use_cases"]], ["ABC-U-001", "ABC-U-002", "ABC-U-003"])
        self.assertEqual(strip["total"], 3, "client-off and archived use cases are absent")
        self.assertEqual(strip["words"], {"On track": 1, "Flag": 1, "High risk": 1})
        rows = {r["id"]: r for r in strip["rows"]}
        mine = [a for a in pub["actions"] if a["use_case"] == "ABC-U-001"]
        self.assertEqual((rows["ABC-U-001"]["open"], rows["ABC-U-001"]["overdue"]), (len(mine), len(late(mine))))
        self.assertEqual((rows["ABC-U-001"]["open"], rows["ABC-U-001"]["overdue"]), (1, 1))

    def test_a_use_case_linked_only_to_a_sensitive_item_has_nothing(self):
        row = {r["id"]: r for r in published(probe())["glance"]["strip"]["rows"]}["ABC-U-002"]
        self.assertEqual((row["open"], row["overdue"]), (0, 0))

    def test_each_kind_of_hidden_item_leaves_the_figure_at_the_published_one(self):
        for what in ("label", "client", "eye", "archived"):
            with self.subTest(what=what):
                d = data(actions=[action(1, "2026-10-20", use_case="ABC-U-001"),
                                  action(2, "2026-10-20", use_case="ABC-U-001",
                                         **({"client_visible": 0} if what == "client" else {"archived": 1} if what == "archived" else {}))],
                         use_cases=[use_case(1)], labels={"ABC-A-002": ["Sensitive"]} if what == "label" else {})
                pub = published(d, left_off=["ABC-A-002"] if what == "eye" else [])
                row = pub["glance"]["strip"]["rows"][0]
                self.assertEqual((row["open"], row["overdue"]), (1, 1))

    def test_the_strip_is_absent_without_use_cases_or_when_their_section_is_hidden(self):
        self.assertNotIn("strip", published(data(), hide=()).get("glance"))
        self.assertNotIn("strip", published(probe(), hide=("usecases",))["glance"])


class Shape(unittest.TestCase):
    def test_only_the_fixed_shape_and_no_stored_text(self):
        d = probe()
        d["project"].update(internal_note=PLANTED_MARKER, publish_local=PLANTED_MARKER)
        for k in ("actions", "raid", "decisions", "use_cases"):
            for r in d[k]:
                r.update(internal_note=PLANTED_MARKER, source=PLANTED_MARKER, reasoning=PLANTED_MARKER, title=r.get("title", ""))
        d["use_cases"][0].update(headline="Headline", standing="<p>stands</p>")
        pub = published(d, tiles=[tile_row("decisions", 4096)])
        out = pub["glance"]
        self.assertEqual(set(out), {"tiles", "strip"})
        for t in out["tiles"]:
            self.assertEqual(set(t), SHAPE_TILE)
            self.assertIn(t["colour"], ("G", "A", "R", "N"))
            self.assertIn(t["outline"], ("", "G", "A", "R", "N"))
        self.assertEqual(set(out["strip"]), SHAPE_STRIP)
        for r in out["strip"]["rows"]:
            self.assertEqual(set(r), {"id", "open", "overdue"})
        text = json.dumps(out)
        self.assertNotIn(PLANTED_MARKER, text)
        self.assertNotIn("Supplier is a fortnight late", text, "the health reason is the page's to read from the project")
        self.assertNotIn("Headline", text)
        self.assertEqual({t["label"] for t in out["tiles"]}, set(g.TILE_TITLES.values()), "labels are the four fixed titles")

    def test_select_is_not_changed_by_the_figures(self):
        i = inputs(probe(), left_off=["ABC-A-004"])
        chosen = publish.select(i)
        after = publish.add_glance(publish.select(i), i)["data"]
        self.assertEqual({k: v for k, v in after.items() if k != "glance"}, chosen["data"])

    def test_kept_from_agrees_with_kept_rows(self):
        d = {**probe(), "report_sections": sections("raid"), "label_rules": RULES, "report_hidden": [{"item_id": "ABC-A-004"}]}
        whole = g.kept_rows(d, ON)
        again = g.kept_from(publish.select({"data": d, "hidden": ["ABC-A-004"], "sections": d["report_sections"],
                                            "label_rules": RULES, "as_at": ON}), d["report_sections"])
        self.assertEqual(whole, again)


class WholeFile(unittest.TestCase):
    def test_a_real_publish_carries_glance_and_a_hidden_tile_is_not_in_the_bytes(self):
        with DemoStore() as store, tempfile.TemporaryDirectory() as out:
            with store.step("dashboard", USER) as st:
                st.create("actions", {"project": "ABC", "description": "Do it", "raised": "2026-10-01", "due_date": "2026-10-10",
                                      "client_visible": 1, "source": "demo"})
                st.seed_tiles("ABC")
                st.update("glance_tiles", "ABC|overdue", {"hidden": 1})
                st.update("glance_tiles", "ABC|decisions", {"hidden": 0, "outline": "R"})
            got = publish.publish(store, "ABC", Path(out), by_user=USER, now=ON)
            text = Path(got["path"]).read_text(encoding="utf-8")
            block = re.search(r'id="clark-data">(.*?)</script>', text, re.S).group(1)
            glance = json.loads(block)["data"]["glance"]
            self.assertEqual([t["tile"] for t in glance["tiles"]], ["health", "risks", "decisions"])
            self.assertNotIn("Overdue actions", block)
            self.assertEqual(glance["tiles"][-1]["outline"], "R")
            self.assertEqual(json.loads(block)["v"], 1)


class Done(unittest.TestCase):
    """#412: a Done use case is published with its word, counted under Done in the strip, after the other three."""

    def test_done_is_counted_and_carried_in_the_strip(self):
        d = probe()
        d["use_cases"].append(use_case(6, "Done"))
        pub = published(d, left_off=["ABC-A-004"])
        strip = pub["glance"]["strip"]
        self.assertEqual(strip["words"], {"On track": 1, "Flag": 1, "High risk": 1, "Done": 1})
        self.assertEqual(list(strip["words"])[-1], "Done", "Done is counted last")
        self.assertEqual([u["status"] for u in pub["use_cases"] if u["id"] == "ABC-U-006"], ["Done"])

    def test_a_real_publish_carries_a_done_use_case_with_its_word(self):
        with DemoStore() as store, tempfile.TemporaryDirectory() as out:
            with store.step("dashboard", USER) as st:
                st.update("use_cases", store.read("use_cases", "ABC")[0]["id"], {"status": "Done"})
            got = publish.publish(store, "ABC", Path(out), by_user=USER, now=ON)
            text = Path(got["path"]).read_text(encoding="utf-8")
            block = json.loads(re.search(r'id="clark-data">(.*?)</script>', text, re.S).group(1))
            self.assertEqual([u["status"] for u in block["data"]["use_cases"]], ["Done"])
            self.assertEqual(block["data"]["glance"]["strip"]["words"], {"Done": 1})


if __name__ == "__main__":
    unittest.main()
