"""Row 1567: a words-only update with "v": 2 sent to a version 1 gallery that holds images is not an HTTP 500 and leaves the pictures as stored
(changes._keep_pictures used to index the one-picture slot "image" for every template). The request is sent to the real server, no stand-in.

Run: python3 dev/run_tests.py test_tpl_gallery_v1_words_v2_1567
Fictional data only. No browser.
"""
import json
import unittest

from _demo import USER, DemoStore
from clark import changes
from test_imagecap_full_server import halves
from test_server import Running


class V1GalleryWordsV2(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = Running(change=changes.make_change(self.demo.store.path, [], USER))
        self.addCleanup(self.s.close)
        self.s.httpd.section_image = changes.make_section_image(self.demo.store.path, [], USER)
        new = {"project": "ABC", "kind": "report_sections", "op": "new", "values": {"type": "gallery", "title": "Fictional v1"}, "after": None}
        self.ref = self.post("/api/change", new)["ref"]
        for n in (1, 2):
            self.post("/api/section-image", {"project": "ABC", "section": self.ref, "slot": str(n), "image": halves(8 + n, 6)})

    def post(self, path, body, want=200):
        status, _, raw = self.s.api("POST", path, json.dumps(body).encode())
        self.assertEqual(status, want, raw)
        return json.loads(raw)

    def stored(self):
        return json.loads(next(r for r in self.demo.store.read("report_sections", "ABC") if r["id"] == self.ref)["body"])

    def words_v2(self):
        words = {"v": 2, "items": {"1": {"caption": "Fictional words"}}}
        return {"project": "ABC", "kind": "report_sections", "op": "update", "id": self.ref, "place": "report", "changes": {"body": json.dumps(words)}}

    def test_words_only_v2_update_on_a_v1_gallery_is_not_a_500(self):
        before = self.stored()
        self.assertEqual((before["v"], sorted(before["pictures"])), (1, ["1", "2"]))
        status, _, raw = self.s.api("POST", "/api/change", json.dumps(self.words_v2()).encode())
        self.assertLess(status, 500, raw)
        self.assertEqual(status, 200, raw)
        self.assertEqual(self.stored()["pictures"], before["pictures"], "the stored pictures are unchanged")

    def test_the_real_server_answers_the_v2_words_update_on_a_v1_gallery(self):
        before = self.stored()
        self.post("/api/change", self.words_v2())
        got = self.stored()
        self.assertEqual(got["pictures"], before["pictures"], "the images are byte for byte as stored")
        self.assertEqual(got["items"], {"1": {"caption": "Fictional words"}}, "the words are taken")


if __name__ == "__main__":
    unittest.main()
