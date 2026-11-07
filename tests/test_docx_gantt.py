"""#1012 follow-up: the Gantt tab as a picture in the Word report (src/clark/docx_graphics.py gantt, docx_build.section_gantt).

Run: python3 dev/run_tests.py test_docx_gantt
What is asserted: the picture is the page's chart (a phase navy bar, a task bar with a lighter done part, a milestone diamond amber or
green, the Today line in the status red where today falls), read back from the PNG's pixels; the words (number, name, dates, done,
status, legend) are real Word text; only the lines publish.select left in the copy are in the file (an eye-off line, its note and
its id are in no part, picture included); a line the page would leave out (no usable start day) is left out and counted with the
page's words "N of M lines shown"; 500 lines give runs of at most 30 lines, a bounded picture each, in bounded time; no Gantt in
the file, or none that can be drawn, is no section. Mutation proofs are in the PR text.
"""
import copy
import io
import re
import time
import unittest
import xml.etree.ElementTree as ET
import zipfile
from datetime import date

from _paths import ROOT   # noqa: F401  (puts src/ on the path)

import test_gantt_publish as gp
from clark import docx_build, docx_graphics as g, publish
from clark.docx_build import TOKENS
from test_docx_graphics import NS, parts, read_png

TODAY = "2026-11-06"


def published(lines=None, today=None, **project):
    out = copy.deepcopy(publish.select(copy.deepcopy(gp.plant(lines, **project))))
    out["sections"] = list(out["sections"]) + [{"id": "gantt-1", "type": "gantt", "title": "Gantt", "beside": 0}]
    if today:
        out["as_at"] = today
    return out


def words(data):
    doc = ET.fromstring(parts(data)["word/document.xml"])
    return ["".join(t.text or "" for t in p.iter("{%s}t" % NS["w"])) for p in doc.iter("{%s}p" % NS["w"])]


def pictures(data):
    return [v for k, v in sorted(parts(data).items()) if k.startswith("word/media/")]


def gantt_pictures(p):
    """The Gantt's pictures in the file made from published `p`: every picture the file holds that the same file without its Gantt section lacks."""
    bare = copy.deepcopy(p)
    bare["sections"] = [x for x in bare["sections"] if x["type"] != "gantt"]
    other = set(pictures(docx_build.build(bare)))
    return [x for x in pictures(docx_build.build(p)) if x not in other]


def colour_at(png, x, y):
    w, h, palette, pix = read_png(png)
    return palette[pix[y][x]]


def line(n, name, **kw):
    return gp.line(f"PUB-GNT-{n:03d}", name, **kw)


class ThePicture(unittest.TestCase):
    def setUp(self):
        self.lines = [
            {"id": "A", "type": "phase", "name": "Build", "start": "2026-11-02", "end": "2026-12-18", "pct": 20},
            {"id": "B", "type": "task", "parent": "A", "name": "Dig", "start": "2026-11-02", "end": "2026-11-30", "pct": 50},
            {"id": "C", "type": "milestone", "parent": "A", "name": "Handover", "start": "2026-12-01", "end": "2026-12-01", "pct": 100},
            {"id": "D", "type": "milestone", "name": "Open", "start": "2026-12-10", "end": "2026-12-10", "pct": 0},
        ]
        self.made = g.gantt(self.lines, TODAY, TOKENS)
        (self.png, self.w, self.h), self.run = self.made["pictures"][0]
        self.t = g.tokens(TOKENS)
        self.first, self.last = self.made["start"], self.made["end"]
        ppd = (g.WIDTH - 2 * g.PAD) / ((self.last - self.first).days + 1)
        self.x = lambda d: g.PAD + round((date.fromisoformat(d) - self.first).days * ppd)
        self.cy = lambda i: g.G_TOP + i * g.G_LANE + g.G_LANE // 2

    def test_the_time_line_is_the_pages_whole_months_and_at_least_half_a_year(self):
        self.assertEqual((self.first, self.last), (date(2026, 11, 1), date(2027, 4, 30)))

    def test_a_phase_is_a_navy_bar(self):
        self.assertEqual(colour_at(self.png, self.x("2026-11-20"), self.cy(0)), self.t["brand-navy"])

    def test_a_task_is_a_bar_with_a_lighter_done_part(self):
        task = g.mix(self.t["brand-blue-strong"], self.t["text"], 0.6)
        lighter = g.mix(self.t["white"], task, 0.3)
        x1, x2 = self.x("2026-11-02"), self.x("2026-12-01")                                   # the bar's ends (the end day is counted)
        at = lambda share: x1 + round((x2 - x1) * share)
        self.assertEqual(colour_at(self.png, at(0.45), self.cy(1)), lighter)                  # done is 50 percent: lighter up to half
        self.assertEqual(colour_at(self.png, at(0.55), self.cy(1)), task)
        self.assertEqual(colour_at(self.png, at(0.9), self.cy(1)), task)

    def test_a_milestone_is_a_diamond_amber_and_green_when_done(self):
        self.assertEqual(colour_at(self.png, self.x("2026-12-01"), self.cy(2)), self.t["status-green"])
        self.assertEqual(colour_at(self.png, self.x("2026-12-10"), self.cy(3)), self.t["status-amber"])
        self.assertEqual(colour_at(self.png, self.x("2026-12-10") + 12, self.cy(3)), self.t["surface"])       # outside the diamond

    def test_the_today_line_is_red_where_today_falls_and_absent_when_there_is_no_today(self):
        for i in range(len(self.run)):
            self.assertEqual(colour_at(self.png, self.x(TODAY), g.G_TOP + i * g.G_LANE + 1), self.t["status-red"])
        (png, w, h), _ = g.gantt(self.lines, "not a day", TOKENS)["pictures"][0]            # no usable today: the line is not drawn
        _, _, palette, _ = read_png(png)
        self.assertNotIn(self.t["status-red"], palette)
        far = g.gantt(self.lines, "2031-01-01", TOKENS)                                     # today far away: the time line grows to hold it, as the page's does
        self.assertEqual(far["end"], date(2031, 1, 31))

    def test_no_text_is_in_the_picture_and_every_colour_is_a_token_or_a_mix_of_tokens(self):
        _, _, palette, _ = read_png(self.png)
        task = g.mix(self.t["brand-blue-strong"], self.t["text"], 0.6)
        allowed = {v.upper() for v in self.t.values()} | {task, g.mix(self.t["white"], task, 0.3)}
        self.assertTrue(set(palette) <= allowed, set(palette) - allowed)


class InTheWordFile(unittest.TestCase):
    def setUp(self):
        self.p = published(today=TODAY)
        self.data = docx_build.build(self.p)
        self.text = words(self.data)

    def test_the_section_has_its_title_one_picture_and_the_words_as_real_text(self):
        self.assertIn("Gantt", self.text)
        self.assertEqual(len(gantt_pictures(self.p)), 1)
        for w in ("Build", "Dig", "Pour", "Phase / task", "Start", "End", "Done", "Status", "Phase · Task (lighter part = done) · Milestone · Achieved · Today",
                  "02-11-2026", "13-11-2026", "10%"):
            self.assertTrue(any(w in t for t in self.text), w)
        self.assertIn("No", self.text)

    def test_a_picture_has_alt_text_made_of_the_words_beside_it(self):
        xml = parts(self.data)["word/document.xml"].decode("utf-8")
        alt = re.findall(r'descr="([^"]*)"', xml)
        self.assertTrue(any("Dig, 02-11-2026" in a for a in alt))

    def test_the_eye_off_line_its_note_and_its_id_are_in_no_part_picture_included(self):
        for name, body in parts(self.data).items():
            text = body.decode("latin-1")
            for secret in (gp.SECRET, gp.D, gp.SECRET_NOTE, str(gp.SECRET_BUDGET)):
                self.assertNotIn(secret, text, name)

    def test_the_rows_are_in_the_published_order_and_only_the_published_lines(self):
        names = [t for t in self.text if t in ("Build", "Dig", "Pour")]
        self.assertEqual(names, ["Build", "Dig", "Pour"])
        self.assertEqual(len(self.p["data"]["gantt"]["lines"]), 3)

    def test_the_outline_numbers_are_the_pages(self):
        out = docx_build._gantt_numbers(g.gantt_lines(self.p["data"]["gantt"]["lines"])[0])
        self.assertEqual(out, ["1", "1.1", "1.2"])
        mixed = [{"line": {"id": "x", "parent": None}, "type": t} for t in ("task", "milestone", "phase", "task", "milestone")]
        mixed[3]["line"]["parent"] = "p"
        mixed[2]["line"]["id"] = "p"
        self.assertEqual(docx_build._gantt_numbers(mixed), ["T-1", "M-1", "1", "1.1", "M-2"])

    def test_status_is_the_pages_done_late_in_progress_not_started(self):
        d = date(2026, 11, 6)
        r = lambda s, e, p, t="task": {"start": date.fromisoformat(s), "end": date.fromisoformat(e), "pct": p, "type": t}
        self.assertEqual(docx_build._gantt_status(r("2026-10-01", "2026-10-30", 100), d), "done")
        self.assertEqual(docx_build._gantt_status(r("2026-10-01", "2026-10-30", 40), d), "late")
        self.assertEqual(docx_build._gantt_status(r("2026-11-01", "2026-11-30", 0), d), "inprogress")
        self.assertEqual(docx_build._gantt_status(r("2026-12-01", "2026-12-30", 0), d), "notstarted")
        self.assertEqual(docx_build._gantt_status(r("2026-11-06", "2026-11-06", 0, "milestone"), d), "notstarted")

    def test_no_gantt_in_the_file_is_no_section(self):
        p = published()
        del p["data"]["gantt"]
        self.assertNotIn("Gantt", words(docx_build.build(p)))
        self.assertEqual(gantt_pictures(p), [])
        self.assertEqual(docx_build.sections({"sections": [{"id": "a", "type": "gantt", "title": "Gantt", "beside": 0}], "data": {}}, None), [])

    def test_a_gantt_the_client_may_not_see_is_never_drawn(self):
        out = copy.deepcopy(publish.select(copy.deepcopy(gp.plant(show_gantt_client=0))))
        self.assertNotIn("gantt", out["data"])
        out["sections"] = out["sections"] + [{"id": "g", "type": "gantt", "title": "Gantt", "beside": 0}]
        self.assertEqual(gantt_pictures(out), [])

    def test_the_same_published_rows_give_the_same_bytes(self):
        self.assertEqual(docx_build.build(self.p), docx_build.build(copy.deepcopy(self.p)))


class HostileData(unittest.TestCase):
    def test_an_eye_off_line_that_reached_the_builder_is_not_drawn_and_not_counted(self):
        lines = [{"id": "a", "name": "On", "type": "task", "start": "2026-11-02", "end": "2026-11-03", "pct": 0, "show": 1},
                 {"id": "b", "name": "Off", "type": "task", "start": "2026-11-02", "end": "2026-11-03", "pct": 0, "show": 0},
                 {"id": "c", "name": "Off2", "type": "task", "start": "2026-11-02", "end": "2026-11-03", "pct": 0, "show": False}]
        drawn, left = g.gantt_lines(lines)
        self.assertEqual(([r["line"]["id"] for r in drawn], left), (["a"], 0))

    def test_garbage_dates_are_left_out_and_counted_as_the_page_does(self):
        lines = [{"id": "ok", "name": "Fine", "type": "task", "start": "2026-11-02", "end": "garbage", "pct": "x"}]
        bad = ["", None, "2026-13-40", "2026-02-30", "2026/11/02", "02-11-2026", "1999-12-31", "2101-01-01", 20261102, "2026-11-02T00:00", "٢026-11-02"]
        lines += [{"id": f"b{i}", "name": f"Bad {i}", "type": "task", "start": s, "end": "2026-11-03", "pct": 0} for i, s in enumerate(bad)]
        drawn, left = g.gantt_lines(lines)
        self.assertEqual((len(drawn), left), (1, len(bad)))
        self.assertEqual((drawn[0]["end"], drawn[0]["pct"]), (drawn[0]["start"], 0))             # an end that is no day is the start; done that is no number is 0
        p = published([gp.line("PUB-GNT-001", "Fine")])
        p["data"]["gantt"]["lines"] += [{"id": "z", "name": "Gone", "type": "task", "start": "nope", "end": "nope", "pct": 0}] * 3
        text = words(docx_build.build(p))
        self.assertIn("1 of 4 lines shown", text)
        self.assertNotIn("Gone", " ".join(text))

    def test_an_end_before_the_start_a_milestone_on_two_days_and_a_strange_type_read_as_the_page_reads_them(self):
        drawn, _ = g.gantt_lines([
            {"name": "r", "type": "task", "start": "2026-11-10", "end": "2026-11-01", "pct": 5},
            {"name": "m", "type": "milestone", "start": "2026-11-10", "end": "2026-11-20", "pct": 5},
            {"name": "t", "type": "bogus", "start": "2026-11-10", "end": "2026-11-12", "pct": 500}])
        self.assertEqual([(r["type"], r["end"].day, r["pct"]) for r in drawn], [("task", 10, 5), ("milestone", 10, 5), ("task", 12, 100)])

    def test_nothing_drawable_gives_a_count_and_no_picture_and_no_lines_gives_no_section(self):
        self.assertIsNone(g.gantt([], TODAY, TOKENS))
        self.assertIsNone(g.gantt("not a list", TODAY, TOKENS))
        only_bad = g.gantt([{"name": "x", "start": "bad"}], TODAY, TOKENS)
        self.assertEqual((only_bad["pictures"], only_bad["left_out"]), ([], 1))
        p = published([gp.line("PUB-GNT-001", "Fine")])
        p["data"]["gantt"]["lines"] = [{"id": "z", "name": "Gone", "start": "nope"}]
        text = words(docx_build.build(p))
        self.assertIn("0 of 1 lines shown", text)
        self.assertEqual(gantt_pictures(p), [])

    def test_five_hundred_lines_give_runs_of_thirty_a_bounded_picture_each_in_bounded_time(self):
        lines = [gp.line(f"PUB-GNT-{n:03d}", f"Line {n}", type=("phase", "task", "milestone")[n % 3], start=f"20{20 + n % 70}-0{1 + n % 9}-1{n % 9}",
                         end=f"20{20 + n % 70}-1{n % 3}-2{n % 9}", pct=n % 120, parent=None) for n in range(1, 501)]
        lines[7]["start"] = "garbage"
        lines[9]["start"] = "2026-02-31"
        started = time.time()
        p = published(lines, gantt_hidden_columns="show,note,budget,effort,baseline_start,baseline_end")
        data = docx_build.build(p)
        self.assertLess(time.time() - started, 30)
        pics = gantt_pictures(p)
        total = len(p["data"]["gantt"]["lines"])
        left = 0                                                                            # publish.select already dropped the garbage-date lines and the ones ending before they start (logged by id)
        self.assertTrue(100 < total < 500, total)
        self.assertNotIn("Line 8", words(data))                                             # line 8 had the garbage start (an exact paragraph)
        self.assertEqual(len(pics), -(-total // g.GANTT_CHUNK))
        for png in pics:
            w, h, _, _ = read_png(png)
            self.assertEqual((w, h <= g.G_TOP + g.G_LANE * g.GANTT_CHUNK + 2), (g.WIDTH, True))
        self.assertEqual(sum(1 for t in words(data) if re.fullmatch(r"Line \d+", t)), total - left)
        self.assertFalse(any("lines shown" in t for t in words(data)))

    def test_a_name_with_markup_is_only_text(self):
        p = published([gp.line("PUB-GNT-001", "</w:t><w:p> & \"x\"")])
        data = docx_build.build(p)
        ET.fromstring(parts(data)["word/document.xml"])
        self.assertIn("</w:t><w:p> & \"x\"", words(data))


if __name__ == "__main__":
    unittest.main()
