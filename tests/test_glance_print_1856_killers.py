"""Row 1264, slice 9 print, the reader's survivors in glance_print.py: the health tile is read the client's way, its tag is empty, and the right half
of a side-by-side pair is found when a pair follows a pair or a single section comes before a pair.

Run: python3 dev/run_tests.py test_glance_print_1856_killers
"""
import unittest
from unittest import mock

from _paths import ROOT   # noqa: F401

import _publish_fixture as fx
from clark import glance, glance_print, publish
from test_glance_word_excel_1264_print import full_section, select


def sec(i, beside=0):
    return {"id": i, "beside": beside}


class HealthTile(unittest.TestCase):
    def test_the_tiles_are_read_the_clients_way(self):
        pub = select(2)
        with mock.patch.object(glance_print.glance, "tiles", wraps=glance.tiles) as m:
            glance_print.read(pub, full_section(pub) | {"content": {"order": ["health"]}})
        self.assertTrue(m.called)
        self.assertIs(m.call_args.kwargs.get("for_client"), True)

    def test_the_health_tile_has_no_tag(self):
        pub = select(2)
        got = glance_print.read(pub, full_section(pub) | {"content": {"order": ["health"]}})
        health = next(t for t in got["tiles"] if t["key"] == "health")
        self.assertEqual(health["tag"], "")
        own = glance_print.read(pub, full_section(pub) | {"content": {"order": ["health"], "health": {"own_row": True}}})
        self.assertEqual(own["health_row"]["tag"], "")


class RightHalf(unittest.TestCase):
    def test_a_pair_followed_directly_by_a_pair(self):
        rows = {"sections": [sec("a", 1), sec("b"), sec("c", 1), sec("d")]}
        self.assertTrue(glance_print._right_half(rows, sec("d")))
        self.assertTrue(glance_print._right_half(rows, sec("b")))
        self.assertFalse(glance_print._right_half(rows, sec("c", 1)))

    def test_a_single_followed_by_a_pair(self):
        rows = {"sections": [sec("s"), sec("a", 1), sec("b")]}
        self.assertTrue(glance_print._right_half(rows, sec("b")))
        self.assertFalse(glance_print._right_half(rows, sec("s")))

    def test_per_line_of_the_right_half_after_a_pair(self):
        rows = {"sections": [sec("a", 1), sec("b"), sec("c", 1), sec("d")]}
        self.assertEqual(glance_print.per_line(sec("d"), {}, rows), 2)
        self.assertEqual(glance_print.per_line(sec("s"), {}, {"sections": [sec("s"), sec("a", 1), sec("b")]}), 4)


if __name__ == "__main__":
    unittest.main()
