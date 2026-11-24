"""Hostile tests, Row 1322 (update rows, docx_graphics): the two-line lane-name rule."""
import random
import unittest

from clark import docx_graphics as g
from test_docx_graphics import TOKENS, ms, read_png, tok


class Lines(unittest.TestCase):
    def test_fuzz_every_line_fits_count_is_bounded_and_dots_only_past_the_budget(self):
        rnd = random.Random(1322)
        alphabet = "ABC xyz  -_1é \t"
        for _ in range(4000):
            name = "".join(rnd.choice(alphabet) for _ in range(rnd.randint(0, 60)))
            out = g.lines(name)
            norm = g.label(name, 10 ** 6)
            self.assertTrue(1 <= len(out) <= 2, (name, out))
            self.assertTrue(all(len(x) <= g.LABEL_MAX for x in out), (name, out))
            if len(norm) <= 38:
                self.assertFalse(any(x.endswith("..") and not norm.count("..") for x in out), (name, out))
            elif len(norm) > 39:
                self.assertTrue(out[-1].endswith(".."), (name, out))
            self.assertEqual(g.lines(name), out)

    def test_no_line_starts_or_ends_with_a_space(self):
        # 19 letters, a space, then words that do not fit one line: the hard cut at 19 must not leave a leading blank column
        name = "A" * 19 + " B " + "C" * 14
        for ln in g.lines(name):
            self.assertEqual(ln, ln.strip(), (name, g.lines(name)))

    def test_exactly_38_and_39_characters(self):
        self.assertFalse(any(".." in x for x in g.lines("A" * 38)))
        out = g.lines("A" * 39)
        self.assertTrue(out[-1].endswith("..") and len(out[-1]) == 19, out)
        self.assertEqual(g.lines("A" * 19 + " " + "B" * 18), ["A" * 19, "B" * 18])

    def test_dots_are_not_preceded_by_a_space(self):
        out = g.lines("AAAAAAAAAAAAAAAAAAA BBBBBBBBBBBBBBB CCCCCCCCCCCC DDDD")
        self.assertFalse(out[-1].endswith(" .."), out)

    def test_a_hard_cut_leaves_no_trailing_space_at_the_end_of_line_1(self):
        name = "A" * 18 + " " + "A" * 8 + " " + "A" * 7 + " " + "A" * 23
        out = g.lines(name)
        self.assertEqual(out[0], "A" * 18, out)
        for ln in out:
            self.assertEqual(ln, ln.strip(), out)

    def test_a_two_line_word_wrap_is_kept_and_the_dots_line_is_exactly_19(self):
        self.assertEqual(g.lines("A" * 12 + " " + "B" * 7), ["A" * 12, "B" * 7])
        self.assertEqual(g.lines("A" * 60)[1], "A" * 17 + "..")

    def test_the_dots_line_has_no_space_before_the_dots_and_line_2_no_space_at_the_start(self):
        for name in ("A" * 19 + " " + "B" * 16 + " CC" + "DDDD", "AAAAAAAAAAAAAAAAAAA BBBBBBBBBBBBBBB CCCCCCCCCCCC DDDD"):
            out = g.lines(name)
            self.assertEqual(out[1], out[1].lstrip(), out)
            self.assertFalse(out[1].endswith(" .."), out)
        self.assertEqual(g.lines("A" * 19 + " " + "B" * 16 + " CC" + "DDDD"), ["A" * 19, "B" * 16 + ".."])

    def test_exact_fits_and_three_word_fallback(self):
        self.assertEqual(g.lines("A" * 19), ["A" * 19])
        self.assertEqual(g.lines("A" * 9 + " " + "B" * 9), ["A" * 9 + " " + "B" * 9])
        self.assertEqual(g.lines("A" * 20), ["A" * 19, "A"])
        self.assertEqual(g.lines("AAAAAAAAAAAA BBBBBBBBBBBB CCCCCCCCCCCC"), ["AAAAAAAAAAAA BBBBBB", "BBBBBB CCCCCCCCCCCC"])
        self.assertEqual(g.lines("HELLO", 0, 2), ["H", "E"][:2] if False else g.lines("HELLO", 1, 2))
        self.assertEqual(len(g.lines("HELLO", 0, 2)[0]), 1)

    def test_none_and_non_string_names(self):
        for n in (None, "", 0, 12345678901234567890123456789012345678901234567890, "   ", "\n\t"):
            self.assertTrue(1 <= len(g.lines(n)) <= 2)


class Pixels(unittest.TestCase):
    def test_the_two_lines_are_centred_in_the_taller_lane_with_a_two_pixel_gap(self):
        name = "HHHHHHHH HHHHHHHH HHHHHHHH"
        png = g.plan([ms(1, name=name)], "2026-11-08", TOKENS)[0][0]
        w, h, palette, rows = read_png(png)
        top, space = g.lane_tops(g.TOP, [name], g.LANE)
        lane_h = space
        want = tok()["text"]
        ys = sorted({y for y in range(g.TOP, g.TOP + lane_h) for x in range(g.LABEL_W) if palette[rows[y][x]] == want})
        self.assertEqual(ys[0], g.TOP + (lane_h - (14 * 2 + 2)) // 2)
        self.assertEqual(ys[-1], ys[0] + 14 * 2 + 2 - 1)
        gaps = [b for a, b in zip(ys, ys[1:]) if b - a > 1]
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0] - ys[0], 7 * g.TEXT_SCALE + 2 + 0)


class Pictures(unittest.TestCase):
    def test_a_two_line_lane_grows_and_neighbours_keep_one_line_height(self):
        one = g.plan([ms(1, name="HHH")], "2026-11-08", TOKENS)[0][0]
        two = g.plan([ms(1, name="HHH HHH HHH HHH HHH HHH")], "2026-11-08", TOKENS)[0][0]
        h1, h2 = read_png(one)[1], read_png(two)[1]
        self.assertGreater(h2, h1)
        self.assertLessEqual(h2 - h1, 2 * 7 * g.TEXT_SCALE + 4 - g.LANE)

    def test_two_line_name_pixels_stay_inside_its_lane_and_the_name_column(self):
        name = "HHHHHHHH HHHHHHHH HHHHHHHH"
        png = g.plan([ms(1, name="X"), ms(2, name=name), ms(3, name="X")], "2026-11-08", TOKENS)[0][0]
        w, h, palette, rows = read_png(png)
        tops, _ = g.lane_tops(g.TOP, ["X", name, "X"], g.LANE)
        want = tok()["text"]
        pts = [(x, y) for y in range(h) for x in range(g.LABEL_W) if palette[rows[y][x]] == want]
        lane2 = [(x, y) for x, y in pts if tops[1] <= y < tops[1] + max(g.LANE, 2 * 7 * g.TEXT_SCALE + 4)]
        self.assertTrue(lane2)
        self.assertLess(max(x for x, _ in lane2), g.LABEL_W)
        self.assertGreaterEqual(min(y for _, y in lane2), tops[1])

    def test_gantt_with_many_long_names_builds_and_is_deterministic(self):
        import test_docx_gantt as tg
        lines = [tg.line(i, "LONG NAME NUMBER %d WITH MANY WORDS HERE" % i) for i in range(1, 70)]
        a = g.gantt(lines, "2026-11-08", TOKENS)
        b = g.gantt(lines, "2026-11-08", TOKENS)
        self.assertEqual(a["pictures"], b["pictures"])
        for pic in a["pictures"]:
            self.assertLessEqual(read_png(pic[0][0] if isinstance(pic[0], (list, tuple)) else pic[0])[0], g.WIDTH)


if __name__ == "__main__":
    unittest.main()
