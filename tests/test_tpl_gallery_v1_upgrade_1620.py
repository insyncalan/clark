"""Row 1620: a version 1 gallery that holds pictures is upgraded to version 2 by a change that carries columns, shape or order (default
values too: the decision reads the body as sent, before the check drops them); a words-only change leaves it version 1 with its pictures
as stored (row 1567); columns, shape or order without "v": 2 stay refused. Every request goes to the real server, no stand-in.

Run: python3 dev/run_tests.py test_tpl_gallery_v1_upgrade_1620
Fictional data only. No browser.
"""
import json
import unittest

from _demo import USER, DemoStore
from _pictures import GOOD_JPEG
from clark import changes
from test_imagecap_full_server import halves
import test_server  # noqa: F401  (names the harness, so the tier test reads this file as a browser-tier file as run_support does)
from test_server import Running

WORDS = {"1": {"caption": "Fictional one", "alt": "A fictional room"}, "2": {"caption": "Fictional two"}}
ORDER = ["2", "1", "3", "4", "5", "6"]
PLAIN = ["1", "2", "3", "4", "5", "6"]


class V1GalleryUpgrade(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = Running(change=changes.make_change(self.demo.store.path, [], USER))
        self.addCleanup(self.s.close)
        self.s.httpd.section_image = changes.make_section_image(self.demo.store.path, [], USER)

    def post(self, path, body):
        status, _, raw = self.s.api("POST", path, json.dumps(body).encode())
        return status, raw

    def ok(self, path, body):
        status, raw = self.post(path, body)
        self.assertEqual(status, 200, raw)
        return json.loads(raw)

    def v1_gallery(self):
        """A new gallery with a PNG in slot 1, a JPEG in slot 2 and their words: a version 1 body, as row 1567 found it."""
        new = {"project": "ABC", "kind": "report_sections", "op": "new", "values": {"type": "gallery", "title": "Fictional v1"}, "after": None}
        ref = self.ok("/api/change", new)["ref"]
        for slot, image in (("1", halves(9, 6)), ("2", GOOD_JPEG)):
            self.ok("/api/section-image", {"project": "ABC", "section": ref, "slot": slot, "image": image})
        self.ok("/api/change", self.update(ref, {"v": 1, "items": WORDS}))
        before = self.stored(ref)
        self.assertEqual((before["v"], sorted(before["pictures"]), before["items"]), (1, ["1", "2"], WORDS))
        return ref, before

    def update(self, ref, body):
        return {"project": "ABC", "kind": "report_sections", "op": "update", "id": ref, "place": "report", "changes": {"body": json.dumps(body)}}

    def stored(self, ref):
        return json.loads(next(r for r in self.demo.store.read("report_sections", "ABC") if r["id"] == ref)["body"])

    def test_columns_shape_or_order_upgrade_a_v1_gallery_default_values_too(self):
        for layout in ({"columns": 2}, {"columns": 3}, {"shape": "4:3"}, {"order": ORDER}, {"order": PLAIN}):
            with self.subTest(layout=layout):
                ref, before = self.v1_gallery()
                self.ok("/api/change", self.update(ref, {"v": 2, "items": WORDS, **layout}))
                got = self.stored(ref)
                self.assertEqual(got["v"], 2, "the layout field, as sent, upgrades it")
                self.assertEqual(got["items"], WORDS, "every caption and description is kept")
                self.assertEqual(got["pictures"]["o1"], before["pictures"]["1"], "the stored PNG is kept whole as the original o1")
                self.assertIn("1", got["pictures"], "the PNG has its framed copy in slot 1")
                self.assertEqual(got["pictures"]["2"], before["pictures"]["2"], "the JPEG stays as stored under the default shape")
                self.assertNotIn("o2", got["pictures"])
                self.assertLessEqual(set(got["pictures"]), {"1", "2", "o1"}, "each picture stays in its own slot")
                if layout == {"columns": 2}:
                    self.assertEqual(got.get("columns"), 2)
                if layout == {"order": ORDER}:
                    self.assertEqual(got.get("order"), ORDER)

    def test_a_words_only_change_leaves_a_v1_gallery_at_v1_with_its_pictures_as_stored(self):
        for words in ({"v": 2}, {"v": 2, "items": WORDS}, {"v": 1, "items": WORDS}, {"items": WORDS}):
            with self.subTest(words=words):
                ref, before = self.v1_gallery()
                self.ok("/api/change", self.update(ref, words))
                got = self.stored(ref)
                self.assertEqual(got["v"], 1, "words alone never upgrade it")
                self.assertEqual(got["pictures"], before["pictures"], "the pictures are byte for byte as stored")

    def test_layout_fields_without_v2_stay_refused(self):
        for body in ({"columns": 2}, {"shape": "4:3"}, {"order": ORDER}, {"v": 1, "columns": 2}, {"v": 1, "shape": "square"}, {"v": 1, "order": ORDER},
                     {"items": WORDS, "columns": 3}):
            with self.subTest(body=body):
                ref, before = self.v1_gallery()
                status, raw = self.post("/api/change", self.update(ref, body))
                self.assertGreaterEqual(status, 400, raw)
                self.assertLess(status, 500, raw)
                self.assertEqual(self.stored(ref), before, "the stored body is unchanged")


if __name__ == "__main__":
    unittest.main()
