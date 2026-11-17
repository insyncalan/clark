"""Row 1261: Report headline, three edges the first tests leave open (the size limit's edge, the Excel line's health words, the Word
pill staying with the headline under it).

Run: python3 dev/run_tests.py test_reportheadline_killers_1261
"""
import io
import json
import re
import unittest
import zipfile

from _paths import ROOT   # noqa: F401  (puts src/ and vendor/ on the path)

import _publish_fixture as fx
from clark import docx_build, excel_client, publish
from clark.section_kinds import reportheadline as rh
from clark.section_kinds.base import Bad


def select(body):
    i = fx.inputs()
    i["sections"].insert(0, {"project": "PUB", "id": "s-rh", "type": "reportheadline", "title": "", "beside": 0, "hidden": 0,
                             "sort_order": 0, "body": json.dumps(body)})
    return publish.select(i)


class Edges(unittest.TestCase):
    def test_a_body_of_exactly_the_limit_is_kept_and_one_more_byte_is_refused(self):
        base = len(str({"v": 1, "headline": ""}).encode("utf-8"))
        ok = {"v": 1, "headline": "x" * (rh.LIMIT - base)}
        self.assertEqual(len(str(rh.check(ok, None)).encode("utf-8")), rh.LIMIT)
        with self.assertRaises(Bad):
            rh.check({"v": 1, "headline": "x" * (rh.LIMIT - base + 1)}, None)

    def test_the_excel_line_says_each_health_in_its_own_words(self):
        for h, word in (("on_track", "On track"), ("at_risk", "At risk"), ("off_track", "Off track")):
            self.assertEqual(excel_client.headline_line(select({"v": 1, "health": h, "headline": "H"})), word + " · H", h)

    def test_the_word_pill_stays_with_the_headline_under_it(self):
        xml = zipfile.ZipFile(io.BytesIO(docx_build.build(select({"v": 1, "health": "at_risk", "headline": "H", "sentence": "S"})))).read("word/document.xml").decode("utf-8")
        pill = re.search(r"<w:p>(?:(?!</w:p>).)*?At risk(?:(?!</w:p>).)*?</w:p>", xml, re.S).group(0)
        self.assertIn("<w:keepNext/>", pill)


    def paras(self, body):
        xml = zipfile.ZipFile(io.BytesIO(docx_build.build(select(body)))).read("word/document.xml").decode("utf-8")
        return {w: re.search(r"<w:p>(?:(?!</w:p>).)*?" + w + r"(?:(?!</w:p>).)*?</w:p>", xml, re.S).group(0) for w in ("At risk", "Hhead", "Ssent") if w in xml}

    def test_a_pill_with_only_a_headline_keeps_with_it(self):
        self.assertIn("<w:keepNext/>", self.paras({"v": 1, "health": "at_risk", "headline": "Hhead"})["At risk"])

    def test_a_pill_alone_keeps_with_nothing(self):
        self.assertNotIn("<w:keepNext/>", self.paras({"v": 1, "health": "at_risk"})["At risk"])

    def test_a_headline_with_no_sentence_does_not_keep_with_the_next(self):
        self.assertNotIn("<w:keepNext/>", self.paras({"v": 1, "headline": "Hhead"})["Hhead"])

    def test_a_headline_with_a_sentence_keeps_with_it(self):
        self.assertIn("<w:keepNext/>", self.paras({"v": 1, "headline": "Hhead", "sentence": "Ssent"})["Hhead"])


if __name__ == "__main__":
    unittest.main()
