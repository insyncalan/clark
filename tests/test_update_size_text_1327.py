"""Row 1327: the size of the newest release as a person reads it. Under 10 MB one decimal ("4.2 MB"), 10 MB and over whole
("12 MB"), never "0 MB" (smallest "0.1 MB"), an unknown size shows no size. One rule: clark.updates.size_text.

Run: python3 dev/run_tests.py test_update_size_text_1327
"""
import unittest

from clark import updates


class SizeText(unittest.TestCase):
    def test_under_ten_mb_has_one_decimal(self):
        for n, want in ((1_700_000, "1.7 MB"), (4_200_000, "4.2 MB"), (4_249_999, "4.2 MB"), (4_250_000, "4.3 MB"), (9_949_999, "9.9 MB")):
            self.assertEqual(updates.size_text(n), want, n)

    def test_never_zero_the_smallest_is_a_tenth(self):
        for n, want in ((1, "0.1 MB"), (40_000, "0.1 MB"), (49_999, "0.1 MB"), (50_000, "0.1 MB"), (149_999, "0.1 MB"), (150_000, "0.2 MB")):
            self.assertEqual(updates.size_text(n), want, n)

    def test_the_edge_below_ten_rounds_up_to_whole_ten(self):
        for n in (9_950_000, 9_990_000, 9_999_999, 10_000_000):
            self.assertEqual(updates.size_text(n), "10 MB", n)

    def test_ten_mb_and_over_is_whole(self):
        for n, want in ((10_400_000, "10 MB"), (10_500_000, "11 MB"), (12_000_000, "12 MB"), (38_300_000, "38 MB")):
            self.assertEqual(updates.size_text(n), want, n)

    def test_an_unknown_size_shows_nothing(self):
        for n in (None, 0, -5, "12", 4.2, True):
            self.assertEqual(updates.size_text(n), "", repr(n))


if __name__ == "__main__":
    unittest.main()
