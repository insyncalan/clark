"""#1012: the Word report carries the graphics: the milestone plan (marks, ghost, Today line), the Health bar and the progress bars.

Run: python3 dev/run_tests.py test_docx_graphics
The pictures come from src/clark/png_draw.py (a PNG writer in zlib and struct) and src/clark/docx_graphics.py (shapes and design-token
colours only, no text in a picture). What is asserted: the bytes are a valid PNG (signature, IHDR first, every CRC, IDAT inflates to
exactly the right size); the pixels are the token colours (Achieved green, Late red, a progress bar's done part, the Health segment,
the Today line where its date is); the .docx holds the picture as a media part with a relationship, a content type and an inline
drawing, read with the zip and an XML parser only; alt text is made of words the report already shows; hostile rows (none, garbage
dates, thousands of milestones) give a bounded picture in bounded time.
"""
import copy
import io
import re
import struct
import time
import unittest
import xml.etree.ElementTree as ET
import zipfile
import zlib
from datetime import date
from unittest import mock

from _paths import ROOT   # noqa: F401  (puts src/ on the path)

import _publish_fixture as fx
from clark import docx_build, docx_graphics as g, png_draw, publish
from clark.docx_build import TOKENS
from clark.png_draw import Canvas, DrawError

SIG = b"\x89PNG\r\n\x1a\n"


def read_png(data):
    """(width, height, palette, rows) of an indexed PNG made by png_draw, checking every rule on the way."""
    assert data[:8] == SIG, "signature"
    pos, chunks = 8, []
    while pos < len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body, crc = data[pos + 8:pos + 8 + n], struct.unpack(">I", data[pos + 8 + n:pos + 12 + n])[0]
        assert crc == zlib.crc32(kind + body) & 0xFFFFFFFF, f"CRC of {kind!r}"
        chunks.append((kind, body))
        pos += 12 + n
    assert pos == len(data), "no bytes after IEND"
    kinds = [k for k, _ in chunks]
    assert kinds[0] == b"IHDR" and kinds[-1] == b"IEND" and kinds.count(b"IDAT") == 1 and kinds.index(b"PLTE") < kinds.index(b"IDAT"), kinds
    w, h, depth, ctype, comp, filt, lace = struct.unpack(">IIBBBBB", chunks[0][1])
    assert (depth, ctype, comp, filt, lace) == (8, 3, 0, 0, 0)
    raw = zlib.decompress(dict(chunks)[b"IDAT"])
    assert len(raw) == h * (w + 1), "IDAT inflates to the right size"
    plte = dict(chunks)[b"PLTE"]
    palette = ["%02X%02X%02X" % tuple(plte[i:i + 3]) for i in range(0, len(plte), 3)]
    rows = []
    for y in range(h):
        assert raw[y * (w + 1)] == 0, "filter 0"
        rows.append(raw[y * (w + 1) + 1:(y + 1) * (w + 1)])
    return w, h, palette, rows


def pixel(png, x, y):
    w, h, palette, rows = read_png(png)
    return palette[rows[y][x]]


def ms(i, state="On track", **kw):
    row = {"id": f"X-M-{i:03d}", "name": f"Milestone {i}", "baseline_date": "2026-11-20", "forecast_date": "2026-11-20", "status": "Planned",
           "percent_complete": None, "actual_date": None, "state": state, "state_word": state, "slip_days": None}
    row.update(kw)
    return row


def tok():
    return g.tokens(TOKENS)


def lane_x(rows, today, iso):
    """Where the plan puts a date: the page's axis (milestone_rows.timeline_span) over the picture's width."""
    from clark import milestone_rows as mr
    drawn = g._rows(rows)
    start, end = (date.fromisoformat(d) for d in mr.timeline_span(drawn, today))
    return g.X0 + round((date.fromisoformat(iso) - start).days * (g.X1 - g.X0) / (end - start).days)


class PngWriter(unittest.TestCase):
    def test_a_canvas_is_a_valid_png(self):
        c = Canvas(37, 11, "FFFFFF")
        c.rect(2, 2, 9, 9, "C0392B")
        c.circle(20, 5, 4, "008675")
        w, h, palette, rows = read_png(c.png())
        self.assertEqual((w, h), (37, 11))
        self.assertEqual(palette, ["FFFFFF", "C0392B", "008675"])

    def test_the_same_canvas_gives_the_same_bytes(self):
        a, b = Canvas(20, 5, "FFFFFF"), Canvas(20, 5, "FFFFFF")
        for c in (a, b):
            c.polygon([(1, 1), (15, 2), (8, 4)], "000000")
        self.assertEqual(a.png(), b.png())

    def test_a_shape_is_where_it_was_drawn_and_nowhere_else(self):
        c = Canvas(10, 10, "FFFFFF")
        c.rect(2, 3, 5, 6, "FF0000")
        self.assertEqual([c.at(x, 4) for x in (1, 2, 4, 5)], ["FFFFFF", "FF0000", "FF0000", "FFFFFF"])
        self.assertEqual(c.at(3, 2), "FFFFFF")
        self.assertEqual(c.at(3, 5), "FF0000")
        self.assertIsNone(c.at(10, 0))

    def test_wild_coordinates_are_clipped_and_cost_nothing(self):
        c = Canvas(10, 10, "FFFFFF")
        started = time.process_time()
        c.rect(-10 ** 9, -10 ** 9, 10 ** 9, 10 ** 9, "000000")
        c.hline(-10 ** 9, 10 ** 9, 5, "FF0000", dash=(1, 1))
        c.line(-10 ** 9, -10 ** 9, 10 ** 9, 10 ** 9, "00FF00", 2)
        c.circle(10 ** 6, 10 ** 6, 5, "0000FF")
        c.polygon([(-10 ** 6, -10 ** 6), (10 ** 6, 0), (0, 10 ** 6)], "FF00FF")
        self.assertLess(time.process_time() - started, 2)
        read_png(c.png())

    def test_too_large_and_bad_colours_are_refused(self):
        for args in ((0, 5), (5, 0), (3000, 3000)):
            with self.assertRaises(DrawError):
                Canvas(*args, "FFFFFF")
        for bad in ("12345", "GGGGGG", "", None):
            with self.assertRaises(DrawError):
                Canvas(2, 2, bad)
        c = Canvas(2, 2, "000000")
        with self.assertRaises(DrawError):
            for i in range(300):
                c.index("%06X" % i)


class ProgressAndHealth(unittest.TestCase):
    def test_the_done_part_is_brand_blue_and_the_rest_the_track(self):
        png, w, h = g.progress_bar(40, TOKENS)
        t = tok()
        self.assertEqual((pixel(png, 5, 3), pixel(png, int(w * 0.4) - 2, 3), pixel(png, int(w * 0.4) + 2, 3), pixel(png, w - 1, 3)),
                         (t["brand-blue"], t["brand-blue"], t["grey-100"], t["grey-100"]))

    def test_zero_and_full_and_out_of_range(self):
        t = tok()
        self.assertEqual(pixel(g.progress_bar(0, TOKENS)[0], 1, 1), t["grey-100"])
        self.assertEqual(pixel(g.progress_bar(100, TOKENS)[0], g.BAR_W - 1, 1), t["brand-blue"])
        self.assertEqual(g.progress_bar(250, TOKENS)[0], g.progress_bar(100, TOKENS)[0])
        self.assertEqual(g.progress_bar(-5, TOKENS)[0], g.progress_bar(0, TOKENS)[0])

    def test_garbage_gives_no_bar(self):
        for bad in ("lots", None, "", float("nan"), [], {}):
            self.assertIsNone(g.progress_bar(bad, TOKENS), repr(bad))

    def test_the_health_segment_of_the_projects_colour_is_filled(self):
        t = tok()
        for colour, at in (("green", 0), ("amber", 1), ("red", 2)):
            png, w, h = g.health_bar(colour, TOKENS)
            seg = (w - 12) // 3
            got = [pixel(png, i * (seg + 6) + seg // 2, 7) for i in range(3)]
            self.assertEqual(got, [t["status-" + colour] if i == at else t["grey-100"] for i in range(3)], colour)

    def test_a_health_with_no_such_colour_claims_nothing(self):
        t = tok()
        png, w, h = g.health_bar(None, TOKENS)
        self.assertNotIn(t["status-green"], read_png(png)[2])
        self.assertNotIn(t["status-red"], read_png(png)[2])


class Plan(unittest.TestCase):
    TODAY = "2026-11-08"

    def draw(self, rows, today=None):
        out = g.plan(rows, today or self.TODAY, TOKENS)
        return out

    def centre(self, rows, i, iso=None):
        return lane_x(rows, self.TODAY, iso or rows[i]["baseline_date"]), g.TOP + i * g.LANE + g.LANE // 2

    def test_an_achieved_milestone_is_a_green_ring_and_a_late_one_a_red_disc(self):
        t = tok()
        rows = [ms(1, "Achieved", status="Done", actual_date="2026-11-20"), ms(2, "Overdue", baseline_date="2026-12-20")]
        (png, w, h), lanes = self.draw(rows)
        x0, y0 = self.centre(rows, 0, "2026-11-20")
        x1, y1 = self.centre(rows, 1)
        self.assertEqual(pixel(png, x0 + 6, y0), t["status-green"])          # the ring
        self.assertEqual(pixel(png, x0, y0 - 4), t["surface"])               # and its inside
        self.assertEqual(pixel(png, x1 + 6, y1), t["status-red"])
        self.assertEqual(pixel(png, x1 + 5, y1), t["status-red"])
        self.assertNotEqual(pixel(png, x0 + 6, y0), pixel(png, x1 + 6, y1))

    def test_each_state_has_its_own_colour_at_its_mark(self):
        t = tok()
        want = {"On track": "status-green", "At risk": "status-amber", "Slipped": "status-red", "Overdue": "status-red",
                "Forecast": "status-blue", "Achieved": "status-green"}
        for state, token in want.items():
            rows = [ms(1, state, status="Done" if state == "Achieved" else "Planned", actual_date="2026-11-20" if state == "Achieved" else None)]
            (png, w, h), _ = self.draw(rows)
            self.assertIn(t[token], read_png(png)[2], state)
            x, y = self.centre(rows, 0, "2026-11-20")
            cells = {pixel(png, x + dx, y + dy) for dx in range(-8, 9) for dy in range(-8, 9)}
            self.assertIn(t[token], cells, state)

    def test_the_today_line_is_navy_at_its_date_and_in_every_lane(self):
        t = tok()
        rows = [ms(1), ms(2, baseline_date="2026-12-24")]
        (png, w, h), _ = self.draw(rows)
        x = lane_x(rows, self.TODAY, self.TODAY)
        for y in (2, g.TOP + 3, h - 3):
            self.assertEqual(pixel(png, x, y), t["brand-navy"], y)
        self.assertNotEqual(pixel(png, x + 6, g.TOP + 3), t["brand-navy"])

    def test_a_later_today_moves_the_line_right(self):
        rows = [ms(1), ms(2, baseline_date="2026-12-24")]
        a, b = lane_x(rows, "2026-11-08", "2026-11-08"), lane_x(rows, "2026-11-20", "2026-11-20")
        self.assertLess(a, b)
        (png, w, h), _ = self.draw(rows, "2026-11-20")
        self.assertEqual(pixel(png, b, 2), tok()["brand-navy"])

    def test_a_slipped_milestone_has_a_dashed_red_line_back_and_a_ghost(self):
        t = tok()
        rows = [ms(1, "Slipped", baseline_date="2026-11-20", forecast_date="2026-12-30", slip_days=40)]
        (png, w, h), lanes = self.draw(rows)
        self.assertEqual(str(lanes[0]["ghost"]), "2026-12-30")
        x0, y = self.centre(rows, 0, "2026-11-20")
        x1 = lane_x(rows, self.TODAY, "2026-12-30")
        reds = [pixel(png, x, y) == t["status-red"] for x in range(x0 + 12, x1 - 9)]
        self.assertTrue(any(reds) and not all(reds), "dashed, not solid")
        self.assertEqual(pixel(png, x1 + 6, y), t["status-red"])

    def test_the_lanes_follow_the_tables_order_and_an_undated_milestone_has_an_empty_lane(self):
        rows = [ms(1), ms(2, baseline_date=None, forecast_date=None), ms(3, baseline_date="2026-12-24")]
        (png, w, h), lanes = self.draw(rows)
        self.assertEqual([r["row"]["id"] for r in lanes], ["X-M-001", "X-M-002", "X-M-003"])
        self.assertIsNone(lanes[1]["solid"])
        self.assertEqual(h, g.TOP + 3 * g.LANE + 2)

    def test_nothing_to_draw_gives_none(self):
        self.assertIsNone(g.plan([], self.TODAY, TOKENS))
        self.assertIsNone(g.plan([ms(1, baseline_date=None, forecast_date=None)], self.TODAY, TOKENS))

    def test_the_picture_is_a_valid_png(self):
        (png, w, h), _ = self.draw([ms(1), ms(2, "Slipped", slip_days=9), ms(3, "At risk"), ms(4, "Forecast", baseline_date=None)])
        self.assertEqual(read_png(png)[:2], (w, h))

    def test_garbage_dates_and_numbers_are_not_drawn_and_do_not_stop_the_picture(self):
        rows = [ms(1, baseline_date="not a date", forecast_date="9999-99-99"), ms(2, baseline_date="0026-01-01", forecast_date=None),
                ms(3, baseline_date="2126-01-01", forecast_date=None), ms(4, slip_days="lots"), ms(5, slip_days=10 ** 12), ms(6, state="Nonsense"),
                ms(7, baseline_date=12345, forecast_date=["x"]), ms(8, baseline_date="2026-02-30", forecast_date=None)]
        out = self.draw(rows, "also not a date")
        (png, w, h), lanes = out
        self.assertEqual(len(lanes), 8)
        read_png(png)
        self.assertEqual([bool(r["solid"]) for r in lanes], [False, False, False, True, True, True, False, False])

    def test_thousands_of_milestones_make_a_bounded_picture_in_bounded_time(self):
        rows = [ms(i, baseline_date=f"{2000 + i % 100}-{1 + i % 12:02d}-{1 + i % 28:02d}", slip_days=i % 400, state="Slipped") for i in range(5000)]
        started = time.process_time()
        (png, w, h), lanes = self.draw(rows)
        self.assertLess(time.process_time() - started, 5)
        self.assertEqual(len(lanes), g.MAX_LANES)
        self.assertEqual(h, g.TOP + g.MAX_LANES * g.LANE + 2)
        self.assertLess(len(png), 200_000)
        read_png(png)

    def test_a_hundred_years_still_fits_the_ticks(self):
        rows = [ms(1, baseline_date="2000-01-02"), ms(2, baseline_date="2099-12-30")]
        (png, w, h), _ = self.draw(rows, "2050-06-01")
        read_png(png)
        w, h, palette, pix = read_png(png)
        ticks = sum(1 for x in range(w) if palette[pix[g.TOP + 1][x]] == tok()["grey-200"])
        self.assertLessEqual(ticks, g.MAX_TICKS)


def build_with(milestones=None, **project):
    p = publish.select(fx.inputs(None))
    p = copy.deepcopy(p)
    if milestones is not None:
        p["data"]["milestones"] = milestones
    p["data"]["project"].update(project)
    return p, docx_build.build(p)


def parts(data):
    z = zipfile.ZipFile(io.BytesIO(data))
    return {i.filename: z.read(i.filename) for i in z.infolist()}


NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main", "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main", "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships", "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
      "ct": "http://schemas.openxmlformats.org/package/2006/content-types"}


class Labels(unittest.TestCase):
    """#1036: the lane names and the axis dates are in the picture, so the picture reads without the table beside it."""
    TODAY = "2026-11-08"

    def ink(self, png, x0, x1, y0, y1):
        """How many pixels of the text colour lie in x0 <= x < x1, y0 <= y < y1."""
        w, h, palette, rows = read_png(png)
        want = tok()["text"]
        return sum(1 for y in range(y0, min(y1, h)) for x in range(x0, min(x1, w)) if palette[rows[y][x]] == want)

    def gutter(self, png, i):
        w, h, palette, rows = read_png(png)
        return [[palette[v] == tok()["text"] for v in rows[y][:g.LABEL_W]] for y in range(g.TOP + i * g.LANE, g.TOP + (i + 1) * g.LANE)]

    def draw(self, rows):
        return g.plan(rows, self.TODAY, TOKENS)[0][0]

    def test_a_named_lane_has_ink_in_its_own_band_of_the_name_column_and_an_unnamed_one_none(self):
        png = self.draw([ms(1, name="Go live"), ms(2, name=None), ms(3, name="   ")])
        band = lambda i: self.ink(png, 0, g.LABEL_W, g.TOP + i * g.LANE, g.TOP + (i + 1) * g.LANE)
        self.assertGreater(band(0), 20)
        self.assertEqual((band(1), band(2)), (0, 0))

    def test_the_same_name_looks_the_same_in_any_lane_and_a_different_name_looks_different(self):
        png = self.draw([ms(1, name="Go live"), ms(2, name="Sign off"), ms(3, name="Go live")])
        a, b, c = (self.gutter(png, i) for i in range(3))
        self.assertFalse(a == b)
        self.assertTrue(a == c)

    def test_a_small_letter_and_a_capital_are_the_same_picture_but_two_letters_are_not(self):
        png = self.draw([ms(1, name="go live"), ms(2, name="GO LIVE"), ms(3, name="GO LIVF")])
        a, b, c = (self.gutter(png, i) for i in range(3))
        self.assertTrue(a == b)
        self.assertFalse(b == c)

    def test_a_name_stays_in_the_name_column_and_its_own_lane(self):
        png = self.draw([ms(1, name="W" * 400), ms(2, name="x"), ms(3, name="W" * 400)])
        # the time line starts right of the column: no ink between the column and the first mark's lane start but the marks'
        self.assertEqual(self.ink(png, g.LABEL_W, g.X0 - 2, g.TOP, g.TOP + 3 * g.LANE), 0)
        w, h, palette, rows = read_png(png)
        self.assertEqual(self.ink(png, 0, g.LABEL_W, 0, g.TOP), 0)                       # the month band holds no lane name
        self.assertLessEqual(max(x for y in range(g.TOP, g.TOP + 3 * g.LANE) for x in range(g.LABEL_W)
                                 if palette[rows[y][x]] == tok()["text"]), g.PAD + g.LABEL_MAX * 12)

    def test_hostile_names_are_only_pixels_and_never_stop_the_picture(self):
        for name in ('"/><w:p>INJECTED</w:p>', "\u05e9\u05dc\u05d5\u05dd \u202e abc", "\x00\x1b[31m", "&amp; <b>", "\U0001f600" * 50, "a\nb\tc"):
            png = self.draw([ms(1, name=name)])
            read_png(png)
            self.assertGreater(self.ink(png, 0, g.LABEL_W, g.TOP, g.TOP + g.LANE), 0, repr(name))
            self.assertEqual(self.ink(png, g.LABEL_W, g.X0 - 2, g.TOP, g.TOP + g.LANE), 0, repr(name))

    def test_a_character_the_font_lacks_is_a_question_box_not_a_gap(self):
        a = self.gutter(self.draw([ms(1, name="\u05e9")]), 0)
        b = self.gutter(self.draw([ms(1, name="?")]), 0)
        self.assertTrue(a == b)
        self.assertEqual(g.label("a\u05e9  b\n"), "A? B")

    def test_a_long_name_ends_in_two_dots(self):
        self.assertEqual(g.label("x" * 100), "X" * (g.LABEL_MAX - 2) + "..")
        self.assertEqual(g.label("x" * g.LABEL_MAX), "X" * g.LABEL_MAX)

    def test_the_axis_dates_are_in_the_month_band_over_the_time_line_only(self):
        png = self.draw([ms(1), ms(2, baseline_date="2027-02-20")])
        self.assertGreater(self.ink(png, g.X0, g.WIDTH, 0, g.TOP), 40)
        self.assertEqual(self.ink(png, 0, g.X0 - 4, 0, g.TOP), 0)

    def test_the_axis_dates_follow_the_months_shown(self):
        a = self.draw([ms(1), ms(2, baseline_date="2027-02-20")])
        b = self.draw([ms(1, baseline_date="2028-05-20"), ms(2, baseline_date="2028-08-20")])
        band = lambda png: (lambda r: [[r[2][v] for v in row] for row in r[3][:g.TOP]])(read_png(png))
        self.assertFalse(band(a) == band(b))

    def test_a_hundred_years_keeps_the_dates_from_touching(self):
        png = self.draw([ms(1, baseline_date="2001-01-05"), ms(2, baseline_date="2099-12-30")])
        self.assertGreater(self.ink(png, g.X0, g.WIDTH, 0, g.TOP), 0)

    def test_month_words_never_touch_and_never_run_past_the_right_edge(self):
        c = Canvas(g.WIDTH, 30, "#ffffff")
        spans = []
        real = g.draw_text
        with mock.patch.object(g, "draw_text", lambda cv, x, y, text, col: (spans.append((x, x + g.text_width(text))), real(cv, x, y, text, col))):
            months = [date(2026, m, 1) for m in range(1, 13)]
            g.month_labels(c, months, lambda d: g.X0 + (d.month - 1) * 20, "#000000")
            self.assertGreater(len(spans), 1)
            self.assertLess(len(spans), 12)
            for (a0, a1), (b0, _) in zip(spans, spans[1:]):
                self.assertLess(a1, b0)
            spans.clear()
            g.month_labels(c, [date(2026, 1, 1)], lambda d: g.WIDTH - 20, "#000000")
            self.assertEqual(spans, [])
            g.month_labels(c, [date(2026, 1, 1)], lambda d: g.X0, "#000000")
            self.assertEqual(len(spans), 1)

    def test_the_picture_is_as_wide_as_before_and_the_word_file_holds_it_with_the_names_escaped(self):
        nasty = '"/><w:p>INJECTED</w:p>'
        _, data = build_with(milestones=[ms(1, name=nasty), ms(2, name="\u05e9\u05dc\u05d5\u05dd")])
        doc = parts(data)["word/document.xml"]
        ET.fromstring(doc)
        self.assertNotIn(b"<w:p>INJECTED", doc)
        sizes = [read_png(raw)[:2] for n, raw in parts(data).items() if n.startswith("word/media/")]
        self.assertIn((g.WIDTH, g.TOP + 2 * g.LANE + 2), sizes)


class InTheWordFile(unittest.TestCase):
    def setUp(self):
        self.p, self.data = build_with()
        self.parts = parts(self.data)
        self.doc = ET.fromstring(self.parts["word/document.xml"])

    def embeds(self):
        return [b.get("{%s}embed" % NS["r"]) for b in self.doc.iter("{%s}blip" % NS["a"])]

    def test_each_picture_is_a_media_part_with_a_relationship_and_a_content_type(self):
        rels = {r.get("Id"): r for r in ET.fromstring(self.parts["word/_rels/document.xml.rels"]).findall("rel:Relationship", NS)}
        ids = self.embeds()
        self.assertEqual(len(ids), 2)                                       # the Health bar and the milestone plan
        for rid in ids:
            r = rels[rid]
            self.assertTrue(r.get("Type").endswith("/relationships/image"))
            self.assertIsNone(r.get("TargetMode"))
            part = "word/" + r.get("Target")
            self.assertTrue(part.startswith("word/media/") and part.endswith(".png"), part)
            read_png(self.parts[part])
        defaults = {d.get("Extension"): d.get("ContentType") for d in ET.fromstring(self.parts["[Content_Types].xml"]).findall("ct:Default", NS)}
        self.assertEqual(defaults["png"], "image/png")

    def test_no_picture_means_no_media_part_no_png_content_type_and_no_image_relationship(self):
        sections_without = copy.deepcopy(self.p)
        sections_without["sections"] = [s for s in sections_without["sections"] if s["type"] not in ("glance", "milestones")]
        bare = parts(docx_build.build(sections_without))
        self.assertFalse([n for n in bare if n.startswith("word/media/")])
        self.assertNotIn(b'Extension="png"', bare["[Content_Types].xml"])
        self.assertNotIn(b"/image", bare["word/_rels/document.xml.rels"])

    def test_every_drawing_is_inline_with_a_size_that_fits_the_page_and_alt_text(self):
        drawings = list(self.doc.iter("{%s}inline" % NS["wp"]))
        self.assertEqual(len(drawings), 2)
        ids = set()
        for d in drawings:
            ext = d.find("wp:extent", NS)
            cx, cy = int(ext.get("cx")), int(ext.get("cy"))
            self.assertLessEqual(cx, docx_build.TEXT_W * 635)
            self.assertTrue(0 < cy < 16838 * 635)
            doc_pr = d.find("wp:docPr", NS)
            ids.add(doc_pr.get("id"))
            self.assertTrue(doc_pr.get("descr"))
            self.assertEqual(doc_pr.get("descr"), d.find(".//pic:cNvPr", NS).get("descr"))
        self.assertEqual(len(ids), 2)

    def test_the_alt_text_is_words_the_report_already_shows(self):
        text = "".join(t.text or "" for t in self.doc.iter("{%s}t" % NS["w"]))
        for d in self.doc.iter("{%s}docPr" % NS["wp"]):
            for piece in d.get("descr").split("; "):
                for part in piece.split(", "):
                    self.assertIn(part.replace("Project health: ", ""), text.replace("Project health: ", ""), piece)

    def test_the_labels_are_real_word_text_beside_the_picture(self):
        text = "".join(t.text or "" for t in self.doc.iter("{%s}t" % NS["w"]))
        for m in self.p["data"]["milestones"]:
            self.assertIn(m["name"], text)
        self.assertIn("Project health: ", text)

    def test_the_plan_comes_before_the_milestone_table_and_the_health_bar_right_after_its_line(self):
        body = self.doc.find("w:body", NS)
        kinds = []
        for el in body:
            tag = el.tag.split("}")[1]
            kinds.append(tag + ("+pic" if el.find(".//w:drawing", NS) is not None else ""))
        i = kinds.index("tbl", kinds.index("p+pic", kinds.index("p+pic") + 1))
        self.assertEqual(kinds[i - 1], "p+pic")
        h = kinds.index("p+pic")
        text = "".join(t.text or "" for t in body[h - 1].iter("{%s}t" % NS["w"]))
        self.assertTrue(text.startswith("Project health: "), text)

    def test_the_health_bar_has_the_health_colour(self):
        self.assertEqual(self.p["data"]["project"]["health"], "At risk")
        # the first picture in the document is the Health bar (the Health line comes before the milestones)
        rels = ET.fromstring(self.parts["word/_rels/document.xml.rels"]).findall("rel:Relationship", NS)
        target = {r.get("Id"): r.get("Target") for r in rels}[self.embeds()[0]]
        w, h, palette, rows = read_png(self.parts["word/" + target])
        self.assertIn(tok()["status-amber"], palette)
        self.assertNotIn(tok()["status-red"], palette)

    def test_a_progress_bar_sits_under_the_percent_words(self):
        ms_rows = [ms(1, percent_complete=60), ms(2, percent_complete=60), ms(3, percent_complete=10), ms(4, percent_complete="garbage")]
        _, data = build_with(milestones=ms_rows)
        doc = ET.fromstring(parts(data)["word/document.xml"])
        descr = [d.get("descr") for d in doc.iter("{%s}docPr" % NS["wp"])]
        self.assertEqual([x for x in descr if x.endswith("% complete")], ["60% complete", "60% complete", "10% complete", ])
        media = [n for n in parts(data) if n.startswith("word/media/")]
        self.assertEqual(len(media), 2 + 2)                                  # two plan/health pictures + 60% (once, shared) + 10%

    def test_the_same_rows_give_the_same_bytes(self):
        self.assertEqual(build_with()[1], build_with()[1])

    def test_a_brand_colour_reaches_the_pictures(self):
        p = copy.deepcopy(self.p)
        a = parts(docx_build.build(p))
        b = parts(docx_build.build(p, colours={"brand-navy": "123456"}))
        names = [n for n in a if n.startswith("word/media/")]
        self.assertTrue(any(a[n] != b[n] for n in names))

    def test_a_cancelled_milestone_has_no_lane(self):
        rows = [ms(1), ms(2, status="Cancelled")]
        _, data = build_with(milestones=rows)
        img = [v for k, v in sorted(parts(data).items()) if k.startswith("word/media/")][-1]
        w, h, _, _ = read_png(img)
        self.assertEqual(h, g.TOP + g.LANE + 2)

    def test_no_milestones_means_no_plan_and_the_words_none_recorded(self):
        _, data = build_with(milestones=[])
        doc = parts(data)["word/document.xml"].decode("utf-8")
        self.assertEqual(doc.count("<w:drawing>"), 1)
        self.assertIn(docx_build.NONE, doc)

    def test_garbage_dates_and_five_thousand_milestones_build_in_bounded_time_and_size(self):
        rows = [ms(i, baseline_date=("garbage" if i % 3 == 0 else f"{2020 + i % 20}-{1 + i % 12:02d}-{1 + i % 28:02d}"),
                   percent_complete=(i % 7 if i % 2 else "x")) for i in range(5000)]
        started = time.process_time()
        _, data = build_with(milestones=rows)
        self.assertLess(time.process_time() - started, 30)
        self.assertLess(len(data), docx_build.MAX_BYTES)
        for n, raw in parts(data).items():
            if n.startswith("word/media/"):
                read_png(raw)
            else:
                ET.fromstring(raw)
        self.assertLessEqual(len([n for n in parts(data) if n.startswith("word/media/")]), 2 + 7)

    def test_a_hostile_name_is_only_text_in_the_alt_text(self):
        nasty = '"/><w:p>INJECTED</w:p>'
        _, data = build_with(milestones=[ms(1, name=nasty)])
        doc = parts(data)["word/document.xml"]
        root = ET.fromstring(doc)
        self.assertNotIn(b"<w:p>INJECTED", doc)
        self.assertTrue(any(nasty in d.get("descr") for d in root.iter("{%s}docPr" % NS["wp"])))


class PicturesNeverStopTheWords(unittest.TestCase):
    """A picture only adds to words the report already has: whatever goes wrong drawing it, the text is written and no picture is."""

    def text(self, data):
        doc = ET.fromstring(parts(data)["word/document.xml"])
        return doc, "".join(t.text or "" for t in doc.iter("{%s}t" % NS["w"]))

    def test_a_percent_too_large_for_a_float_still_builds_with_its_words(self):
        for bad in (10 ** 400, -10 ** 400, float("inf"), float("-inf")):
            _, data = build_with(milestones=[ms(1, percent_complete=bad)])
            doc, text = self.text(data)
            self.assertIn(f"{bad}% complete", text, repr(bad))
            for n, raw in parts(data).items():
                read_png(raw) if n.startswith("word/media/") else ET.fromstring(raw)

    def test_the_drawing_functions_themselves_do_not_raise_on_huge_numbers(self):
        for bad in (10 ** 400, -10 ** 400):
            self.assertIsNone(g.progress_bar(bad, TOKENS))
        self.assertIsNotNone(g.progress_bar(float("inf"), TOKENS))
        out = g.plan([ms(1, "Slipped", slip_days=10 ** 400)], "2026-11-08", TOKENS)
        self.assertIsNone(out[1][0]["ghost"])
        self.assertIsNone(g.plan([ms(1, "Slipped", slip_days=float("inf"))], "2026-11-08", TOKENS)[1][0]["ghost"])

    def test_a_huge_slip_in_json_still_builds(self):
        _, data = build_with(milestones=[ms(1, "Slipped", slip_days=10 ** 400)])
        self.assertIn("Milestone 1", self.text(data)[1])

    def test_a_failure_in_each_drawing_function_leaves_the_text_only_file(self):
        rows = [ms(1, percent_complete=50)]
        _, whole = build_with(milestones=rows)
        full_text = self.text(whole)[1]
        for name in ("health_bar", "progress_bar", "plan"):
            with mock.patch.object(g, name, side_effect=RuntimeError("boom")):
                _, data = build_with(milestones=rows)
            doc, text = self.text(data)
            self.assertEqual(text, full_text, name)
            self.assertEqual(len(list(doc.iter("{%s}inline" % NS["wp"]))), 2, name)                  # the other two of the three pictures stay
            for n, raw in parts(data).items():
                read_png(raw) if n.startswith("word/media/") else ET.fromstring(raw)

    def test_with_every_drawing_failing_there_is_no_picture_part_at_all(self):
        rows = [ms(1, percent_complete=50)]
        with mock.patch.object(g, "health_bar", side_effect=RuntimeError), mock.patch.object(g, "progress_bar", side_effect=RuntimeError), \
                mock.patch.object(g, "plan", side_effect=RuntimeError):
            _, data = build_with(milestones=rows)
        names = parts(data)
        self.assertFalse([n for n in names if n.startswith("word/media/")])
        self.assertNotIn(b"<w:drawing>", names["word/document.xml"])
        self.assertNotIn(b'Extension="png"', names["[Content_Types].xml"])
        self.assertIn("50% complete", self.text(data)[1])

    def test_a_failure_while_writing_the_picture_xml_also_leaves_the_words(self):
        with mock.patch.object(docx_build, "picture", side_effect=RuntimeError):
            _, data = build_with(milestones=[ms(1, percent_complete=50)])
        self.assertIn("50% complete", self.text(data)[1])
        self.assertNotIn(b"<w:drawing>", parts(data)["word/document.xml"])


class OverflowIsHandledWhereItHappens(unittest.TestCase):
    """The OverflowError catches in docx_graphics itself (not the builder's outer try) turn a number no float can hold into the
    documented fallback. Called directly, so removing either catch fails here."""

    def test_number_returns_none_for_an_int_too_large_for_a_float(self):
        for bad in (10 ** 400, -10 ** 400):
            self.assertIsNone(g._number(bad))
            self.assertIsNone(g.percent(bad))

    def test_number_clamps_an_infinity_without_raising(self):
        self.assertEqual(g._number(float("inf")), 100.0)
        self.assertEqual(g._number(float("-inf")), 0.0)

    def test_the_graphics_functions_themselves_do_not_raise_on_a_huge_percent(self):
        for bad in (10 ** 400, -10 ** 400, float("inf")):
            g.progress_bar(bad, TOKENS)   # no wrapper: must not raise
        self.assertIsNone(g.progress_bar(10 ** 400, TOKENS))

    def test_the_slip_read_falls_back_to_no_slip_for_an_infinite_slip(self):
        # int(float("inf")) raises OverflowError; the fallback is slip 0, so no ghost and the row is still drawn.
        for bad in (float("inf"), float("-inf")):
            rows = g._rows([ms(1, "Slipped", slip_days=bad)])
            self.assertEqual(len(rows), 1)
            self.assertIsNone(rows[0]["ghost"])
            self.assertEqual(rows[0]["solid"], date(2026, 11, 20))


if __name__ == "__main__":
    unittest.main()
