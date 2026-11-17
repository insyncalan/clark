"""Row 1264 slice 5: bespoke tiles, the store half. The limits live in check() and the page's copy (templates/glanceLimits.js) holds the
same numbers; what published() carries is text that stays text in a workbook. One test per limit is built to fail when that limit moves.
Fictional data only. Words a person would read are the approved refusal texts, read by key from glancetemplate.words().

Run: python3 dev/run_tests.py test_tpl_glance_store_1264
"""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
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
            for n in (most - 1, most, most + 1, most * 2):
                with self.subTest(field=field, length=n):
                    got = refused({"v": 1, "bespoke": [tile(**{field: "a" * n})]})
                    kept = None if got else check({"v": 1, "bespoke": [tile(**{field: "a" * n})]})["bespoke"][0][field]
                    self.assertEqual((got, kept), (gt.words()[field + "_long"], None) if n > most else (None, "a" * n))

    def test_the_limit_counts_the_trimmed_text_and_stores_it_trimmed(self):
        for pad in ("  ", "\t", "\n "):
            for label, answer in ((pad + "a" * 40 + pad, "a" * 40), ("a" * 40 + pad, "a" * 40), (pad + "a" * 40, "a" * 40), ("a" * 41 + pad, None), (pad + "a" * 41, None)):
                with self.subTest(pad=repr(pad), label=len(label)):
                    got = refused({"v": 1, "bespoke": [tile(label=label)]})
                    self.assertEqual(got if answer is None else check({"v": 1, "bespoke": [tile(label=label)]})["bespoke"][0]["label"],
                                     gt.words()["label_long"] if answer is None else answer)

    def test_the_tile_cap_is_exact_and_the_tile_count_is_checked_before_any_tile(self):
        many = lambda n, label="T": {"v": 1, "bespoke": [tile(id=f"t{i}", label=f"{label}{i}") for i in range(n)]}
        for n, kept, answer in ((11, 11, None), (12, 12, None), (13, 0, gt.WORDS["too_many"]), (40, 0, gt.WORDS["too_many"])):
            with self.subTest(tiles=n):
                self.assertEqual((refused(many(n)), len(check(many(n))["bespoke"]) if answer is None else 0), (answer, kept))
        with self.subTest(order="count before text"):
            self.assertEqual(refused({"v": 1, "bespoke": [tile(id=f"t{i}", label="x" * 99) for i in range(13)]}), gt.WORDS["too_many"])
        with self.subTest(order="count before id"):
            self.assertEqual(refused({"v": 1, "bespoke": [tile(id="Bad Id")] * 13}), gt.WORDS["too_many"])

    def test_five_tones_exactly(self):
        self.assertEqual(gt.TONES, ("green", "amber", "red", "blue", "neutral"))
        for t in gt.TONES:
            with self.subTest(tone=t):
                self.assertEqual(refused({"v": 1, "bespoke": [tile(tone=t)]}), None)
        for t in ("grey", "Green", "", "purple", 1):
            with self.subTest(tone=t):
                self.assertEqual(refused({"v": 1, "bespoke": [tile(tone=t)]}), gt.words()["bad_tone"])

    def test_an_id_clash_is_refused_with_its_own_key_even_when_the_texts_differ(self):
        self.assertEqual(refused({"v": 1, "bespoke": [tile(), tile(label="Other")]}), gt.words()["dup_id"])
        self.assertEqual(refused({"v": 1, "bespoke": [tile(id="a"), tile(id="b"), tile(id="a", label="Other")]}), gt.words()["dup_id"])
        self.assertIsNone(refused({"v": 1, "bespoke": [tile(id="a"), tile(id="b")]}))

    def test_a_built_in_tile_name_is_never_a_bespoke_id(self):
        for name in gt.BUILT_IN:
            with self.subTest(id=name):
                self.assertEqual(refused({"v": 1, "bespoke": [tile(id=name)]}), gt.words()["bad_id"])
        self.assertEqual(gt.BUILT_IN, ("health", "overdue", "risks", "decisions"))


class IdAndTextKinds(unittest.TestCase):           # survivors of the first read: the id length, bytes at the size limit, and a falsy value that is not text
    def test_an_id_is_at_most_16_characters(self):
        for n, answer in ((15, None), (16, None), (17, gt.words()["bad_id"]), (0, gt.words()["bad_id"])):
            with self.subTest(length=n):
                tid = "a" + "b" * (n - 1) if n else ""
                self.assertEqual(refused({"v": 1, "bespoke": [tile(id=tid)]}), answer)

    def test_the_id_is_matched_whole_and_starts_with_a_lower_case_letter(self):
        for tid, answer in (("a1", None), ("1a", gt.words()["bad_id"]), ("A", gt.words()["bad_id"]), ("a-b", gt.words()["bad_id"]), ("a_b", gt.words()["bad_id"]), ("a b", gt.words()["bad_id"]), ("\u00e9a", gt.words()["bad_id"]), ("a\n", gt.words()["bad_id"])):
            with self.subTest(id=tid):
                self.assertEqual(refused({"v": 1, "bespoke": [tile(id=tid)]}), answer)

    def test_a_falsy_value_that_is_not_text_is_refused_not_read_as_empty(self):
        for field in ("label", "figure", "tag", "note"):
            for value in (0, False, [], {}, 0.0):
                with self.subTest(field=field, value=repr(value)):
                    self.assertEqual(refused({"v": 1, "bespoke": [tile(**{field: value})]}), gt.words()["bad_text"])

    def test_text_that_is_missing_or_null_is_empty_and_is_not_stored(self):
        for field in ("figure", "tag", "note"):
            for value in (None, "", "   "):
                with self.subTest(field=field, value=value):
                    self.assertNotIn(field, check({"v": 1, "bespoke": [tile(**{field: value})]})["bespoke"][0])
        self.assertEqual(refused({"v": 1, "bespoke": [tile(label=None)]}), gt.words()["label_missing"])
        self.assertEqual(refused({"v": 1, "bespoke": [tile(label="   ")]}), gt.words()["label_missing"])

    def test_the_size_limit_counts_bytes_not_characters(self):       # a tile body cannot reach 32 KB (12 tiles stay near 3 KB), so the limit is lowered to the edge
        body = {"v": 1, "bespoke": [tile(label="\u00e9" * 40, note="\u00e9" * 60)]}
        kept = check(body)
        chars, size = len(str(kept)), len(str(kept).encode("utf-8"))
        self.assertGreater(size, chars)
        for limit, refuse in ((size, False), (size - 1, True), (chars, True), (size + 1, False)):
            with self.subTest(limit=limit):
                with mock.patch.object(gt, "LIMIT", limit):         # the refusal text names the limit, so it is read under the same patch
                    self.assertEqual(refused(body), gt.words()["too_long"] if refuse else None)

    def test_the_real_size_limit_is_32768_bytes(self):
        self.assertEqual(gt.LIMIT, 32768)
        self.assertIn("32 KB", gt.words()["too_long"])


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
        self.assertEqual(line, 'export const chars = (s) => Array.from(typeof s === "string" ? s : "").length;')


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


class PageBehaviour(unittest.TestCase):            # killer: the page's within() and chars() are run, not only read as text
    def setUp(self):
        self.assertIsNotNone(shutil.which("node"), "node is needed: without it the page copy is only read as text, so this fails instead of skipping")

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

    def test_the_numbers_the_page_runs_with_are_the_server_numbers(self):      # killer: the second reader of every page limit, by running the module (the first reads its text)
        got = self.run_js("[g.BESPOKE_MAX, g.LABEL_MAX, g.FIGURE_MAX, g.TAG_MAX, g.NOTE_MAX, g.TONES]")
        self.assertEqual(got, [gt.BESPOKE_MAX, gt.LABEL_MAX, gt.FIGURE_MAX, gt.TAG_MAX, gt.NOTE_MAX, list(gt.TONES)])


if __name__ == "__main__":
    unittest.main()
