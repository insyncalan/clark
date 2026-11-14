"""Mutation killers (tests only) for the parts of publish_flow.py and docx_graphics.py that the pull requests of 2026-11-11 changed:
the hidden-section run markers (limits, duplicates, ids, character references, a list body), the project brand lookup, and the pixels
of the Word picture's text (the pitch of the letters, the end of the time line). Fictional data only.

Run: python3 dev/run_tests.py test_mutants_publish_flow_graphics
"""
import json
import shutil
import unittest
from datetime import date
from pathlib import Path

import _paths  # noqa: F401
import test_brand_isolation as bi
from test_docx_graphics import read_png
from test_gantt_markers import Base

from clark import brands, docx_graphics as g, page, publish_flow
from clark.docx_build import TOKENS


class RunMarkers(Base):
    def section(self, ref, body, hidden=1):
        self.sql("INSERT INTO report_sections (project, id, type, title, body, beside, hidden, sort_order) VALUES ('ABC',?,?,?,?,0,?,?)",
                 (ref, "text", "Title " + ref, body, hidden, 9000 + len(ref)))

    def runs(self, prefix, got, longest=100000):
        return [m for m in got if m.startswith(prefix) and len(m) <= longest]

    def test_the_limits_are_300_runs_and_100000_characters(self):
        self.assertEqual((publish_flow.MAX_RUN_MARKERS, publish_flow.MAX_RUN_CHARS), (300, 100000))

    def test_exactly_300_of_400_runs_become_markers(self):
        self.section("s-many", "".join("<p>Capped run number %04d</p>" % i for i in range(400)))
        self.assertEqual(len(self.runs("Capped run number", self.got()[1], 40)), 300)

    @staticmethod
    def big(n, size):
        return "Bigrun%03d" % n + "x" * (size - 9)

    def test_runs_up_to_exactly_100000_characters_all_count(self):
        self.section("s-fit", "".join("<p>%s</p>" % self.big(i, 1000) for i in range(100)))
        self.assertEqual(len(self.runs("Bigrun", self.got()[1], 1001)), 100)

    def test_a_run_that_would_pass_100000_by_one_is_left_out_and_so_is_every_run_after_it(self):
        body = "".join("<p>%s</p>" % self.big(i, 1000) for i in range(99)) + "<p>%s</p>" % self.big(99, 1001) + "<p>Short tail run text</p>"
        self.section("s-over", body)
        got = self.got()[1]
        self.assertEqual(len(self.runs("Bigrun", got, 1001)), 99)
        self.assertNotIn(self.big(99, 1001), got)
        self.assertNotIn("Short tail run text", got)

    def test_a_run_of_exactly_eight_characters_is_a_marker_seven_is_not(self):
        self.section("s-len", "<p>QWERTYUI</p><p>ASDFGHJ</p>")
        got = self.got()[1]
        self.assertIn("QWERTYUI", got)
        self.assertNotIn("ASDFGHJ", got)

    def test_a_run_in_two_hidden_sections_is_added_once_with_the_id_of_the_first(self):
        self.section("s-a", "<p>Twice hidden words here</p>")
        self.section("s-b", "<p>Twice hidden words here</p>")
        calls = []
        publish_flow.hidden_section_markers(self.s, "ABC", [], set(), lambda value, ref: calls.append((value, ref)))
        self.assertEqual([c[0] for c in calls].count("Twice hidden words here"), 1)
        self.assertTrue(all(ref in ("s-a", "s-b") for _, ref in calls), calls)

    def test_each_marker_carries_the_id_of_its_section(self):
        self.section("s-id", "<p>Words with an owner id</p>")
        calls = []
        publish_flow.hidden_section_markers(self.s, "ABC", [], set(), lambda value, ref: calls.append((value, ref)))
        self.assertIn(("Words with an owner id", "s-id"), calls)

    def test_a_json_list_body_gives_each_string_as_a_marker(self):
        self.section("s-list", json.dumps(["Zqlist first secret string", ["Zqlist nested secret string"], {"k": "Zqlist keyed secret string"}]))
        got = self.got()[1]
        for m in ("Zqlist first secret string", "Zqlist nested secret string", "Zqlist keyed secret string"):
            self.assertIn(m, got)

    def test_a_character_reference_does_not_split_a_run(self):
        self.section("s-ref", "<p>Tom &amp; Jerry secret plan</p>")
        self.assertIn("Tom & Jerry secret plan", self.got()[1])


class BrandLookup(bi.Rig):
    def test_a_code_that_is_not_text_is_the_plain_page_even_if_a_store_would_answer(self):
        self.set_brand("zebra")
        store = bi.FakeStore({"brand": "zebra"})
        self.assertEqual(publish_flow.brand_of(store, "ABC", self.root), self.zebra)
        for code in (None, 5, b"ABC", ["ABC"]):
            self.assertIs(publish_flow.brand_of(store, code, self.root), page.NO_BRAND, repr(code))

    def test_a_row_with_no_brand_is_generic_not_a_brand_called_x(self):
        other = self.root / "branding" / "x"
        shutil.copytree(self.zebra, other)
        (other / brands.MANIFEST).write_text(json.dumps({"id": "x", "name": "X Co", "version": "1.0.0"}), encoding="utf-8")
        for row in ({"brand": ""}, {"brand": None}, {}):
            self.assertIs(publish_flow.brand_of(bi.FakeStore(row), "ABC", self.root), page.NO_BRAND, repr(row))
        self.assertEqual(publish_flow.brand_of(bi.FakeStore({"brand": "x"}), "ABC", self.root), other)

    def test_a_branding_given_to_the_publisher_wins_whatever_it_is(self):
        class Empty:
            def __bool__(self):
                return False
        mine = Empty()
        pub = publish_flow.Publisher(self.s.path, [], branding=mine, data_dir=self.s.path.parent, brand_root=self.root)
        self.assertIs(pub.project_brand(self.s, "ABC"), mine)

    def test_without_a_brand_root_the_clark_folder_that_holds_branding_is_used(self):
        pub = publish_flow.Publisher(self.s.path, [], data_dir=self.s.path.parent)
        self.assertEqual(pub.brand_root, Path(page.BRANDING).parent)
        self.assertEqual(pub.brand_root / "branding", Path(page.BRANDING))


class PictureText(unittest.TestCase):
    def setUp(self):
        self.t = g.tokens(TOKENS)

    def test_letters_are_six_font_dots_apart(self):
        c = g.Canvas(60, 20, self.t["surface"])
        g.draw_text(c, 0, 0, "II", self.t["text"])
        _, _, palette, rows = read_png(c.png())
        ink = [x for x in range(60) if palette[rows[0][x]] == self.t["text"]]
        # "I" is 01110 on its top row: font dots 1 to 3, so pixels 2 to 7; the second letter starts 6 dots on: dots 7 to 9, pixels 14 to 19
        self.assertEqual(ink, [2, 3, 4, 5, 6, 7, 14, 15, 16, 17, 18, 19])
        self.assertEqual(g.text_width("II"), 24)

    def test_the_time_line_of_the_gantt_ends_on_its_last_pixel(self):
        lines = [{"id": "A", "type": "task", "name": "Whole", "start": "2026-11-01", "end": "2027-04-30", "pct": 0}]
        made = g.gantt(lines, "2026-11-06", TOKENS)
        self.assertEqual((made["start"], made["end"]), (date(2026, 11, 1), date(2027, 4, 30)))
        (png, _, _), _ = made["pictures"][0]
        _, _, palette, rows = read_png(png)
        cy = g.G_TOP + g.G_LANE // 2
        task = g.mix(self.t["brand-blue-strong"], self.t["text"], 0.6)
        self.assertEqual(palette[rows[cy][g.X1 - 1]], task)
        self.assertEqual(palette[rows[cy][g.X1 + 2]], self.t["surface"])
        self.assertEqual(palette[rows[cy][g.X0 + 1]], task)
        self.assertEqual(palette[rows[cy][g.X0 - 2]], self.t["surface"])


if __name__ == "__main__":
    unittest.main()
