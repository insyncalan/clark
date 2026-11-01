"""The checker registry for sections that carry content (src/clark/section_bodies.py): the generic shape check, hostile content,
the canonical text, the plug-in points a later item fills. Pure: no store, no file.

Run: python3 dev/run_tests.py test_section_bodies
"""
import ast
import json
import time
import unittest
from unittest import mock

from _paths import SRC
from clark import section_bodies as sb
from clark.store import BODY_RULES

TYPES = ("needs", "tracker")


def check(kind, body):
    return sb.check(kind, body, BODY_RULES)


class Generic(unittest.TestCase):
    """The tests of the generic layer (shape, limits, canonical text) hand a type's content in whatever form they like, so the
    needs checker (its own tests are in test_needs_content.py) is put aside for them: it takes any content that passed the generic check."""

    def setUp(self):
        patch = mock.patch.dict(sb.CHECKERS, {"needs": lambda value, rules: value})
        patch.start()
        self.addCleanup(patch.stop)


class Registry(unittest.TestCase):
    def test_one_checker_per_content_type_keyed_by_type(self):
        self.assertEqual(set(sb.CHECKERS), set(TYPES))
        self.assertIs(sb.CHECKERS["needs"], sb._checked_needs)
        self.assertIs(sb.CHECKERS["tracker"], sb._checked_tracker)
        self.assertEqual(set(sb.EMPTY), set(TYPES))
        self.assertEqual(set(sb.LIMITS), set(TYPES))

    def test_the_module_is_pure_and_imports_nothing_from_clark(self):
        tree = ast.parse((SRC / "clark" / "section_bodies.py").read_text(encoding="utf-8"))
        names = [a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
                 for a in ([n] if isinstance(n, ast.ImportFrom) else n.names)]
        self.assertTrue(all(isinstance(n, str) for n in names))
        modules = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | \
                  {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        self.assertEqual(modules, {"json", "unicodedata"})

    def test_a_type_with_no_checker_has_no_content(self):
        for kind in ("text", "raid", "docs", "other"):
            with self.assertRaises(sb.Bad):
                check(kind, '{"a":1}')

    def test_the_type_decides_which_checker_runs(self):
        seen = []

        def mine(value, rules):
            seen.append(("mine", value))
            return {"mine": 1}
        with mock.patch.dict(sb.CHECKERS, {"needs": mine}):
            self.assertEqual(check("needs", '{"a":1}'), '{"mine":1}')              # what is stored is what the checker handed back
            self.assertEqual(check("tracker", '{"groups":[]}'), check("tracker", '{}'))      # the other type is untouched: its own checker rebuilds it
        self.assertEqual(seen, [("mine", {"a": 1})])

    def test_a_checker_can_refuse_in_its_own_words_and_a_checker_that_returns_a_string_is_a_fault(self):
        def refuses(value, rules):
            raise sb.Bad("Needs from you can have at most 100 rows.")
        with mock.patch.dict(sb.CHECKERS, {"needs": refuses}):
            with self.assertRaises(sb.Bad) as e:
                check("needs", '{"a":1}')
        self.assertEqual(str(e.exception), "Needs from you can have at most 100 rows.")
        with mock.patch.dict(sb.CHECKERS, {"needs": lambda value, rules: "not a structure"}):
            with self.assertRaises(sb.Bad):
                check("needs", '{"a":1}')

    def test_the_tracker_publishes_nothing_of_its_content_yet_and_needs_publishes_only_its_shown_rows(self):
        self.assertEqual(sb.published("tracker", {"rows": [{"what": "<script>"}]}), {})
        self.assertIsNone(sb.published("needs", {"rows": [{"what": "<script>"}]}), "a row without the checked shape is not published")


class Canonical(Generic):
    def test_the_stored_text_is_rebuilt_sorted_compact_and_ascii(self):
        got = check("needs", ' { "b" : [ 1 , true , null ] , "a" : "caf\u00e9" } ')
        self.assertEqual(got, '{"a":"caf\\u00e9","b":[1,true,null]}')
        self.assertEqual(check("needs", got), got)                                  # saving it again changes nothing

    def test_a_list_is_content_too(self):
        self.assertEqual(check("needs", '[1, 2]'), "[1,2]")

    def test_nothing_is_empty_content(self):
        for kind in TYPES:
            self.assertEqual(check(kind, ""), "")
            self.assertEqual(check(kind, None), "")

    def test_text_is_made_nfc(self):
        self.assertEqual(json.loads(check("needs", json.dumps({"a": "e\u0301"})))["a"], "\u00e9")

    def test_markup_is_only_text_and_stays_text(self):
        got = check("needs", json.dumps({"a": "<script>alert(1)</script> <img src=x onerror=y>"}))
        self.assertEqual(json.loads(got), {"a": "<script>alert(1)</script> <img src=x onerror=y>"})


class Hostile(Generic):
    def refuses(self, body, kind="needs", words=None):
        began = time.monotonic()
        with self.assertRaises(sb.Bad) as e:
            check(kind, body)
        self.assertLess(time.monotonic() - began, 1)
        if words:
            self.assertEqual(str(e.exception), words)
        return str(e.exception)

    def test_not_text(self):
        for body in (5, 1.5, True, ["a"], {"a": 1}, b"{}"):
            self.refuses(body, words=sb.NOT_TEXT)

    def test_the_top_level_is_an_object_or_a_list(self):
        for body in ('"x"', "5", "true", "null"):
            self.refuses(body, words=sb.NOT_TEXT)

    def test_not_json(self):
        for body in ("{", "{'a': 1}", "{a: 1}", "[1,]", "   ", "<p>x</p>"):
            self.refuses(body, words=sb.NOT_READABLE)

    def test_numbers_with_a_fraction_or_not_a_number_are_refused(self):
        for body in ('{"a": 1.5}', '{"a": 1e3}', '{"a": NaN}', '{"a": Infinity}', '{"a": -Infinity}', '[0.1]'):
            self.refuses(body, words=sb.BAD_NUMBER)

    def test_a_very_long_number_is_refused_quickly(self):
        self.refuses('{"a": %s}' % ("9" * 5000), words=sb.BAD_NUMBER)
        self.refuses('{"a": -%s}' % ("9" * 400), words=sb.BAD_NUMBER)
        self.assertEqual(check("needs", '{"a": 999999999999999}'), '{"a":999999999999999}')      # fifteen digits are fine

    def test_a_repeated_key_is_refused(self):
        self.refuses('{"a": 1, "a": 2}', words=sb.REPEATED)
        self.refuses('{"x": {"a": 1, "a": 2}}', words=sb.REPEATED)
        self.refuses(json.dumps({"e\u0301": 1, "\u00e9": 2}), words=sb.REPEATED)          # one key after NFC

    def test_deep_nesting_is_refused(self):
        self.refuses("[" * 9 + "]" * 9, words=sb.TOO_DEEP)
        self.assertEqual(check("needs", "[" * 8 + "]" * 8), "[" * 8 + "]" * 8)
        self.refuses("[" * 100000 + "]" * 100000)                                       # also over the byte limit; never an error
        with mock.patch.dict(sb.LIMITS, {"needs": 10 ** 7}):
            self.refuses("[" * 200000 + "]" * 200000, words=sb.TOO_DEEP)                 # the parser's own limit, said in words

    def test_over_the_byte_limit_is_refused_before_it_is_read(self):
        with mock.patch.object(sb.json, "loads", side_effect=AssertionError("must not parse")):
            self.refuses('{"a": "%s"}' % ("x" * sb.LIMITS["needs"]), words=sb.TOO_BIG)
            self.refuses("a" * (sb.LIMITS["tracker"] + 1), kind="tracker", words=sb.TOO_BIG)

    def test_the_limit_counts_bytes_not_characters(self):
        word = "\u00e9" * (sb.LIMITS["needs"] // 6 - 20)                  # two bytes typed, six once stored: just under the limit
        self.assertTrue(check("needs", json.dumps({"a": word}, ensure_ascii=False)))
        self.refuses(json.dumps({"a": "\u00e9" * (sb.LIMITS["needs"] // 2 + 1)}, ensure_ascii=False), words=sb.TOO_BIG)

    def test_a_body_at_the_limit_is_kept_and_one_byte_over_is_refused(self):
        limit = sb.LIMITS["needs"]
        pad = limit - len('{"a":""}')
        self.assertEqual(len(check("needs", '{"a":"%s"}' % ("x" * pad))), limit)
        self.refuses('{"a":"%s"}' % ("x" * (pad + 1)), words=sb.TOO_BIG)

    def test_the_stored_text_is_over_the_limit_when_escapes_make_it_longer(self):
        body = json.dumps({"a": "\u00e9" * (sb.LIMITS["needs"] // 6 + 100)}, ensure_ascii=False)       # two bytes a letter as typed, six once stored in ASCII: under the limit typed, over it stored
        self.refuses(body, words=sb.TOO_BIG)

    def test_hidden_characters_are_refused_in_a_value_and_in_a_key(self):
        for ch in ("\u202e", "\u200b", "\u2066", "\ufeff", "\u0000", "\u0007", "\n", "\t", "\u2028", "\u2029", "\ue000"):
            self.refuses(json.dumps({"a": "x" + ch + "y"}), words=sb.BAD_TEXT)
            self.refuses(json.dumps({"x" + ch + "y": 1}), words=sb.BAD_TEXT)

    def test_a_lone_surrogate_is_refused(self):
        self.refuses('{"a": "\\ud800"}', words=sb.BAD_TEXT)
        self.refuses('{"\\udc00": 1}', words=sb.BAD_TEXT)
        self.refuses('{"a": "\ud800"}', words=sb.BAD_TEXT)                   # and one in the text itself

    def test_the_words_never_quote_the_value(self):
        for body in ('{"a": "SECRET-ZQ\\u202e"}', '{"SECRET-ZQ": 1.5}', '{"SECRET-ZQ": 1, "SECRET-ZQ": 2}', "SECRET-ZQ"):
            self.assertNotIn("SECRET-ZQ", self.refuses(body))

    def test_the_words_are_plain(self):
        for words in (sb.NOT_TEXT, sb.TOO_BIG, sb.NOT_READABLE, sb.TOO_DEEP, sb.BAD_NUMBER, sb.REPEATED, sb.BAD_TEXT, sb.BAD_VALUE, sb.NOT_SAVED_YET):
            self.assertTrue(words.endswith("."), words)
            for jargon in ("JSON", "json", "schema", "parse", "NaN", "id"):
                self.assertNotIn(jargon, words.replace("hidden", ""), words)
            self.assertFalse(words.lower().startswith("clark"))
