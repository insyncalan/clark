"""Row 1264 slice 5: bespoke tiles, the store half. The limits live in check() and the page's copy (templates/glanceLimits.js) holds the
same numbers; what published() carries is text that stays text in a workbook. One test per limit is built to fail when that limit moves.
Fictional data only. Words a person would read are WORDS_PENDING: the tests name the key, never a sentence.

Run: python3 dev/run_tests.py test_tpl_glance_store_1264
"""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from clark import excel
from clark.section_kinds import base, glancetemplate as gt

PAGE = Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "src" / "templates" / "glanceLimits.js"


class Rules:
    plain = staticmethod(lambda t: True)
    visible = staticmethod(lambda t: any(c.isalnum() for c in t))


def check(v):
    return gt.check(v, Rules)


def refused(v):
    try:
        check(v)
    except base.Bad as e:
        return str(e)
    return None


def tile(**k):
    return {"id": "t1", "label": "Go-live", **k}


def page_consts():
    got = dict(re.findall(r"^export const ([A-Z_]+) = (\d+);", PAGE.read_text(encoding="utf-8"), re.M))
    return {k: int(v) for k, v in got.items()}


class LimitsAtTheEdge(unittest.TestCase):          # T07 to T10: each limit, one below, at, one over; a mutant that moves it by one fails here
    def test_each_text_limit_is_exact_and_names_its_own_key(self):
        for field, most in (("label", 40), ("figure", 12), ("tag", 12), ("note", 60)):
            with self.subTest(field=field):
                self.assertIsNone(refused({"v": 1, "bespoke": [tile(**{field: "a" * (most - 1)})]}))
                self.assertIsNone(refused({"v": 1, "bespoke": [tile(**{field: "a" * most})]}))
                self.assertEqual(refused({"v": 1, "bespoke": [tile(**{field: "a" * (most + 1)})]}), gt.WORDS_PENDING[field + "_long"])

    def test_the_limit_counts_the_trimmed_text(self):
        self.assertIsNone(refused({"v": 1, "bespoke": [tile(label="  " + "a" * 40 + "  ")]}))
        self.assertIsNotNone(refused({"v": 1, "bespoke": [tile(label="a" * 41 + "  ")]}))

    def test_the_tile_cap_is_exact_and_the_tile_count_is_checked_before_any_tile(self):
        many = lambda n: {"v": 1, "bespoke": [tile(id=f"t{i}", label=f"T{i}") for i in range(n)]}
        self.assertIsNone(refused(many(11)))
        self.assertIsNone(refused(many(12)))
        self.assertEqual(refused(many(13)), gt.WORDS["too_many"])
        self.assertEqual(refused({"v": 1, "bespoke": [tile(id=f"t{i}", label="x" * 99) for i in range(13)]}), gt.WORDS["too_many"])

    def test_five_tones_exactly(self):
        self.assertEqual(set(gt.TONES), {"green", "amber", "red", "blue", "neutral"})
        self.assertEqual(len(gt.TONES), 5)
        for t in gt.TONES:
            self.assertIsNone(refused({"v": 1, "bespoke": [tile(tone=t)]}))
        self.assertEqual(refused({"v": 1, "bespoke": [tile(tone="grey")]}), gt.WORDS_PENDING["bad_tone"])

    def test_an_id_clash_is_refused_with_its_own_key_even_when_the_texts_differ(self):
        self.assertEqual(refused({"v": 1, "bespoke": [tile(), tile(label="Other")]}), gt.WORDS_PENDING["dup_id"])
        self.assertEqual(refused({"v": 1, "bespoke": [tile(id="health")]}), gt.WORDS_PENDING["bad_id"])


class PageCopy(unittest.TestCase):                 # T57: the counters on the page read the numbers the server enforces
    def test_the_page_holds_the_same_numbers_as_check(self):
        c = page_consts()
        self.assertEqual({k: c[k] for k in ("BESPOKE_MAX", "LABEL_MAX", "FIGURE_MAX", "TAG_MAX", "NOTE_MAX")},
                         {"BESPOKE_MAX": gt.BESPOKE_MAX, "LABEL_MAX": gt.LABEL_MAX, "FIGURE_MAX": gt.FIGURE_MAX, "TAG_MAX": gt.TAG_MAX, "NOTE_MAX": gt.NOTE_MAX})

    def test_the_page_tones_are_the_server_tones(self):
        m = re.search(r"export const TONES = \[([^\]]*)\]", PAGE.read_text(encoding="utf-8"))
        self.assertEqual(tuple(re.findall(r'"([a-z]+)"', m.group(1))), gt.TONES)

    def test_the_page_counts_characters_like_the_server(self):
        line = re.search(r"export const chars = .*", PAGE.read_text(encoding="utf-8")).group(0)
        self.assertIn("Array.from(", line)
        self.assertNotIn("s.length", line)


class AsText(unittest.TestCase):                   # T34, T58: the file carries tile words as text, never as something a workbook runs
    EVIL = ("=1+1", "+SUM(A1)", "-2", "@cmd", "#N/A")

    def test_published_keeps_every_word_as_a_string_exactly(self):
        for word in self.EVIL:
            with self.subTest(word=word):
                out = gt.published(check({"v": 1, "bespoke": [tile(label=word, figure=word[:12], tag=word, note=word)]}), None)["content"]["bespoke"][0]
                for k in ("label", "figure", "tag", "note"):
                    self.assertIs(type(out[k]), str)
                self.assertEqual(out["label"], word)
                self.assertEqual(out["note"], word)

    def test_the_workbook_writer_stores_such_a_word_as_a_string_cell(self):
        wb = Workbook()
        ws = wb.active
        for i, word in enumerate(self.EVIL, 1):
            out = gt.published(check({"v": 1, "bespoke": [tile(label=word)]}), None)["content"]["bespoke"][0]
            cell = ws.cell(row=i, column=1, value=excel.cell_text(out["label"]))
            excel.protect_text_cell(cell)
            self.assertEqual(cell.data_type, "s", word)

    def test_only_the_tile_fields_reach_the_file(self):
        out = gt.published({"v": 1, "bespoke": [dict(tile(), hidden=False, extra="leak-word")]}, None)["content"]["bespoke"][0]
        self.assertEqual(set(out), {"id", "label", "figure", "tag", "note", "tone"})
        self.assertNotIn("leak-word", repr(out))


@unittest.skipUnless(shutil.which("node"), "node is needed")
class PageBehaviour(unittest.TestCase):            # killer: the page's within() and chars() are run, not only read as text
    def run_js(self, expr):
        with tempfile.TemporaryDirectory() as d:
            m = Path(d) / "g.mjs"
            m.write_text(PAGE.read_text(encoding="utf-8"), encoding="utf-8")
            js = "import(process.argv[1]).then(g => console.log(JSON.stringify(%s)))" % expr
            out = subprocess.run(["node", "-e", js, m.as_uri()], capture_output=True, text=True, timeout=60)
            self.assertEqual(out.returncode, 0, out.stderr[:200])
            return json.loads(out.stdout)

    def test_within_is_inclusive_at_each_limit_and_counts_code_points(self):
        got = self.run_js("[g.within('a'.repeat(g.NOTE_MAX - 1), g.NOTE_MAX), g.within('a'.repeat(g.NOTE_MAX), g.NOTE_MAX), g.within('a'.repeat(g.NOTE_MAX + 1), g.NOTE_MAX),"
                          " g.chars('\\u{1F600}'), g.within('\\u{1F600}'.repeat(g.TAG_MAX), g.TAG_MAX), g.within('\\u{1F600}'.repeat(g.TAG_MAX + 1), g.TAG_MAX), g.chars(null)]")
        self.assertEqual(got, [True, True, False, 1, True, False, 0])


if __name__ == "__main__":
    unittest.main()
