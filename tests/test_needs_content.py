"""The 'Needs from you' section's content (src/clark/section_bodies.py, #121): the rows' checker, what is published of them, and the real
change route and publish path over a real store. Fictional data. No browser (the page's own tests are in test_needs_page.py).

Run: python3 dev/run_tests.py test_needs_content
"""
import json
import re
import time
import unittest

from _publish_fixture import spellings
from clark import publish, section_bodies as sb
from clark.store import BODY_RULES
from test_changes import Api, KIND

MARK = "ZQ-NEEDS-MARK"
HOSTILE = ["<script>alert('" + MARK + "')</script>", '"><img src=x onerror=alert(1)>', "</script><script>x", "javascript:alert(1)", "<!--", "&lt;b&gt;&amp;"]


def row(**more):
    return {"what": "Choose the pilot site", "kind": "decision", "from": "Steering group", "by": "2027-03-04", "hidden": 0, **more}


def body(*rows):
    return json.dumps({"v": 1, "rows": list(rows)})


def check(text):
    return sb.check("needs", text, BODY_RULES)


def stored(*rows):
    return json.loads(check(body(*rows)))


class Checker(unittest.TestCase):
    def refuses(self, text, words=None):
        began = time.monotonic()
        with self.assertRaises(sb.Bad) as e:
            check(text)
        self.assertLess(time.monotonic() - began, 1)
        if words is not None:
            self.assertEqual(str(e.exception), words)
        return str(e.exception)

    def test_a_good_list_is_stored_whole_in_order_and_in_one_canonical_text(self):
        first, second = row(what="Confirm the supplier list", kind="information", by=""), row(hidden=1)
        text = check(body(first, second))
        self.assertEqual(text, json.dumps({"rows": [first, second], "v": 1}, sort_keys=True, separators=(",", ":")))
        self.assertEqual(check(text), text, "saving it again changes nothing")
        self.assertEqual(json.loads(text)["rows"], [first, second], "the order is the list's")

    def test_a_row_with_only_what_and_kind_is_filled_in_whole(self):
        got = json.loads(check(json.dumps({"rows": [{"what": "Send the access list", "kind": "information"}]})))
        self.assertEqual(got, {"v": 1, "rows": [{"what": "Send the access list", "kind": "information", "from": "", "by": "", "hidden": 0}]})

    def test_text_is_trimmed_and_made_nfc(self):
        got = stored(row(what="  Cafe\u0301 menu  ", **{"from": " Example team "}))["rows"][0]
        self.assertEqual((got["what"], got["from"]), ("Caf\u00e9 menu", "Example team"))

    def test_an_empty_list_is_a_list_with_no_rows_and_no_text_is_no_content(self):
        self.assertEqual(json.loads(check(body()))["rows"], [])
        self.assertEqual(check(""), "")
        self.assertEqual(check(None), "")

    def test_every_kind_is_taken_and_no_other(self):
        for kind in sb.NEEDS_KINDS:
            self.assertEqual(stored(row(kind=kind))["rows"][0]["kind"], kind)
        self.assertEqual(sb.NEEDS_KINDS, ("decision", "information", "date"))
        for bad in ("Decision", "decisions", "", " ", None, 1, True, ["decision"], {"a": 1}, "decision ", "task"):
            self.refuses(body(row(kind=bad)), sb.NEEDS_KIND)

    def test_the_row_count_at_the_limit_and_over(self):
        self.assertEqual(len(stored(*[row(what=f"Row {n}") for n in range(sb.NEEDS_MAX_ROWS)])["rows"]), 100)
        self.refuses(body(*[row(what=f"Row {n}") for n in range(sb.NEEDS_MAX_ROWS + 1)]), sb.NEEDS_TOO_MANY)

    def test_the_longest_rows_of_the_longest_list_still_fit_the_byte_limit(self):
        """Every list the row limits allow can be saved: 100 rows of the longest text, each letter written as six ASCII bytes."""
        long = row(what="\u00e9" * sb.NEEDS_WHAT_MAX, **{"from": "\u00e9" * sb.NEEDS_FROM_MAX})
        self.assertEqual(len(stored(*[long] * sb.NEEDS_MAX_ROWS)["rows"]), 100)

    def test_what_is_needed_has_a_visible_letter_and_at_most_300_characters(self):
        self.assertEqual(len(stored(row(what="x" * 300))["rows"][0]["what"]), 300)
        self.refuses(body(row(what="x" * 301)), sb.NEEDS_WHAT_LONG)
        self.assertEqual(len(stored(row(what="\U0001F600" * 300))["rows"][0]["what"]), 300, "characters, not bytes")
        self.refuses(body(row(what="\U0001F600" * 301)), sb.NEEDS_WHAT_LONG)
        for bad in ("", " ", "   ", None, 5, ["x"], {"a": 1}, True):
            self.refuses(body(row(what=bad)), sb.NEEDS_WHAT_MISSING)
        self.refuses(json.dumps({"rows": [{"kind": "date"}]}), sb.NEEDS_ROW_SHAPE)             # no `what` at all

    def test_from_may_be_empty_and_is_at_most_100_characters(self):
        self.assertEqual(stored(row(**{"from": ""}))["rows"][0]["from"], "")
        self.assertEqual(len(stored(row(**{"from": "x" * 100}))["rows"][0]["from"]), 100)
        self.refuses(body(row(**{"from": "x" * 101})), sb.NEEDS_FROM_LONG)
        for bad in (5, None, ["x"], True):
            self.refuses(body(row(**{"from": bad})), sb.NEEDS_FROM_BAD)

    def test_by_is_empty_or_a_real_day_from_2000_to_2100(self):
        for good in ("", "2000-01-01", "2100-12-31", "2028-02-29", "2400-02-29"[:0] or "2024-02-29", "2026-12-31"):
            self.assertEqual(stored(row(by=good))["rows"][0]["by"], good)
        for bad in ("2027-02-29", "2100-02-29", "2026-02-30", "2026-04-31", "2026-13-01", "2026-00-10", "2026-01-00", "1999-12-31", "2101-01-01",
                    "0001-01-01", "9999-12-31", "04-03-2027", "2027-3-4", "2027/03/04", "soon", "2027-03-04 ", " 2027-03-04", "2027-03-04T00:00",
                    "\uff12\uff10\uff12\uff16-01-01", "2026-01-0\u0661", 20270304, 5, True, ["2027-03-04"], {"a": 1}):
            self.refuses(body(row(by=bad)), sb.NEEDS_BY)
        self.assertEqual(stored(row(by=None))["rows"][0]["by"], "", "null is no date")

    def test_hidden_is_zero_or_one_and_nothing_else(self):
        self.assertEqual([stored(row(hidden=h))["rows"][0]["hidden"] for h in (0, 1)], [0, 1])
        for bad in (True, False, 2, -1, "1", "0", None, [1], 1.0 and "x"):
            self.refuses(body(row(hidden=bad)), sb.NEEDS_HIDDEN)
        self.refuses('{"rows": [{"what": "x", "kind": "date", "hidden": 1.0}]}', sb.BAD_NUMBER)

    def test_the_shape_is_one_object_with_a_version_and_rows_and_nothing_more(self):
        self.refuses("[]", sb.NEEDS_SHAPE)
        self.refuses("[" + json.dumps(row()) + "]", sb.NEEDS_SHAPE)
        self.refuses("{}", sb.NEEDS_SHAPE)
        self.refuses('{"v": 1}', sb.NEEDS_SHAPE)
        self.refuses('{"rows": {}}', sb.NEEDS_SHAPE)
        self.refuses('{"rows": "x"}', sb.NEEDS_SHAPE)
        self.refuses('{"v": 2, "rows": []}', sb.NEEDS_SHAPE)
        self.refuses('{"v": true, "rows": []}', sb.NEEDS_SHAPE)
        self.refuses('{"v": "1", "rows": []}', sb.NEEDS_SHAPE)
        self.refuses('{"v": 1, "rows": [], "groups": []}', sb.NEEDS_SHAPE)
        self.assertEqual(json.loads(check('{"rows": []}')), {"v": 1, "rows": []}, "no version is version 1")
        for bad in (None, 5, "x", [], [row()], True):
            self.refuses(json.dumps({"rows": [bad]}), sb.NEEDS_ROW_SHAPE)

    def test_a_key_the_row_does_not_know_is_refused_never_dropped_and_never_kept(self):
        for extra in ({"note": "x"}, {"id": "ABC-1"}, {"url": "https://example.test"}, {"": "x"}, {"What": "x"}, {"by ": "x"}):
            self.refuses(body(row(**extra)), sb.NEEDS_ROW_SHAPE)
        self.refuses(body(row(), {"what": "x", "kind": "date", "extra": 1}), sb.NEEDS_ROW_SHAPE)

    def test_hidden_characters_and_line_breaks_are_refused_by_the_text_rules(self):
        for ch in ("\u202e", "\u200b", "\u2066", "\ufeff", "\u0000", "\u0007", "\n", "\t", "\u2028", "\u2029", "\ue000"):
            self.refuses(body(row(what="x" + ch + "y")), sb.BAD_TEXT)
            self.refuses(body(row(**{"from": "x" + ch + "y"})))
        self.refuses(body(row(what="\u2800\u3164")), sb.NEEDS_WHAT_MISSING)
        self.refuses(body(row(**{"from": "\u2800\u3164"})), sb.NEEDS_FROM_BAD)
        self.refuses('{"rows": [{"what": "\\ud800", "kind": "date"}]}', sb.BAD_TEXT)

    def test_markup_is_only_text_and_stays_text(self):
        got = stored(row(what=HOSTILE[0], **{"from": HOSTILE[1]}))["rows"][0]
        self.assertEqual((got["what"], got["from"]), (HOSTILE[0], HOSTILE[1]))

    def test_hostile_content_is_refused_quickly(self):
        self.refuses('{"rows": [' + "[" * 20 + "]" * 20 + "]}")
        self.refuses('{"rows": [{"what": "x", "kind": "date", "what": "y"}]}', sb.REPEATED)
        self.refuses('{"rows": [{"what": "x", "kind": "date", "hidden": %s}]}' % ("9" * 5000), sb.BAD_NUMBER)
        self.refuses('{"rows": [{"what": "x", "kind": "date", "by": NaN}]}', sb.BAD_NUMBER)

    def test_a_refusal_never_quotes_the_value_and_is_in_plain_words(self):
        for bad in (row(what=MARK + "\u202e"), row(kind=MARK), row(by=MARK), row(hidden=MARK), row(**{"from": MARK * 20}), row(**{MARK: 1})):
            self.assertNotIn(MARK, self.refuses(body(bad)))
        for name in dir(sb):
            if name.startswith("NEEDS_") and isinstance(getattr(sb, name), str):
                words = getattr(sb, name)
                self.assertTrue(words.endswith("."), words)
                self.assertFalse(re.match(r"\s*clark\b", words, re.I), words)
                for jargon in ("JSON", "json", "schema", "parse", "NaN", "template", "RAID", "database", "payload", "null", " id ", "field", "string", "array", "object"):
                    self.assertNotIn(jargon, words, words)


class Published(unittest.TestCase):
    def test_only_the_rows_that_show_are_published_with_the_four_fields_and_the_date_as_DD_MM_YYYY(self):
        value = stored(row(what="One", kind="information", **{"from": "Team A"}, by="2027-03-04"), row(what=MARK, hidden=1), row(what="Two", kind="date", by=""))
        got = sb.published("needs", value)
        self.assertEqual(got, {"rows": [{"what": "One", "kind": "information", "from": "Team A", "by": "04-03-2027"},
                                        {"what": "Two", "kind": "date", "from": "Steering group", "by": ""}]})
        self.assertNotIn(MARK, json.dumps(got))
        for r in got["rows"]:
            self.assertEqual(set(r), {"what", "kind", "from", "by"}, "no hidden flag, nothing else")

    def test_no_row_to_show_leaves_the_section_out(self):
        self.assertIsNone(sb.published("needs", {"v": 1, "rows": []}))
        self.assertIsNone(sb.published("needs", stored(row(hidden=1), row(hidden=1))))
        self.assertIsNone(sb.published("needs", {}))
        self.assertIsNone(sb.published("needs", []))
        self.assertIsNone(sb.published("needs", {"rows": "x"}))

    def test_nothing_is_published_from_a_row_that_does_not_have_the_checked_shape(self):
        good = {"what": "Fine", "kind": "date", "from": "", "by": "", "hidden": 0}
        bad = [{**good, "kind": "task"}, {**good, "by": "2027-02-29"}, {**good, "by": "04-03-2027"}, {**good, "hidden": True}, {**good, "hidden": "0"},
               {**good, "what": ""}, {**good, "what": 5}, {**good, "from": None}, {**good, "by": None}, "x", None, 5, [good], {"what": "x"}]
        got = sb.published("needs", {"v": 1, "rows": bad + [good]})
        self.assertEqual(got, {"rows": [{"what": "Fine", "kind": "date", "from": "", "by": ""}]})

    def test_it_does_not_change_what_it_is_given_and_never_copies_a_field_it_does_not_name(self):
        value = {"v": 1, "rows": [{"what": "Fine", "kind": "date", "from": "", "by": "", "hidden": 0, "secret": MARK}], "other": MARK}
        before = json.dumps(value)
        self.assertNotIn(MARK, json.dumps(sb.published("needs", value)))
        self.assertEqual(json.dumps(value), before)

    def test_the_tracker_is_untouched(self):
        self.assertEqual(sb.published("tracker", {"rows": [row()]}), {})


class Route(Api):
    def make(self):
        return self.ok("new", values={"type": "needs", "title": "Needs from you"})["ref"]

    def write(self, ref, *rows):
        return self.change(self.req("update", id=ref, changes={"body": body(*rows)}))

    def steps(self):
        return self.snapshot()[0]

    def stored(self, ref):
        return self.s.read(KIND, ref=ref)["body"]

    def test_a_new_section_has_no_rows(self):
        ref = self.make()
        self.assertEqual(self.stored(ref), sb.EMPTY["needs"])
        self.assertEqual(sb.EMPTY["needs"], "")

    def test_each_save_is_one_step_with_one_undo_that_puts_the_list_back(self):
        ref = self.make()
        lists = [[row(what="One")], [row(what="One"), row(what="Two", kind="date", by="")], [row(what="One", hidden=1), row(what="Two", kind="date", by="")],
                 [row(what="One", hidden=1)], []]
        steps, ids, texts = [self.steps()], [], [self.stored(ref)]
        for rows in lists:
            status, got = self.write(ref, *rows)
            self.assertEqual((status, got["ok"]), (200, True), got)
            steps.append(self.steps())
            ids.append(got["apply_id"])
            texts.append(self.stored(ref))
        self.assertEqual([b - a for a, b in zip(steps, steps[1:])], [1] * 5, "one step each: add, add, hide, remove, remove")
        for apply_id, text in zip(reversed(ids), reversed(texts[:-1])):
            self.assertEqual(self.undone(apply_id)[0], 200)
            self.assertEqual(self.stored(ref), text, "one Undo puts back exactly the list before")

    def test_saving_the_same_list_again_makes_no_step(self):
        ref = self.make()
        self.write(ref, row())
        before = self.steps()
        status, got = self.write(ref, row())
        self.assertEqual((status, got["ok"], got.get("apply_id")), (200, True, None))
        self.assertEqual(self.steps(), before)

    def test_a_refused_list_writes_nothing_and_says_why_in_words(self):
        ref = self.make()
        self.write(ref, row())
        before = self.snapshot()
        for rows, words in (([row(what="")], sb.NEEDS_WHAT_MISSING), ([row(by="2027-02-29")], sb.NEEDS_BY), ([row(kind="x")], sb.NEEDS_KIND),
                            ([row()] * 101, sb.NEEDS_TOO_MANY)):
            status, got = self.write(ref, *rows)
            self.assertEqual((status, got["ok"], got["message"]), (400, False, words))
        self.assertEqual(self.snapshot(), before)

    def test_the_reply_and_the_undo_words_carry_none_of_the_rows(self):
        ref = self.make()
        status, got = self.write(ref, row(what=MARK))
        self.assertNotIn(MARK, json.dumps(got))
        words = self.undone(got["apply_id"])[1]["words"]
        self.assertNotIn(MARK, words)

    def test_a_needs_section_can_be_deleted_and_put_back_with_its_rows(self):
        ref = self.make()
        self.write(ref, row(what="One"))
        kept = self.stored(ref)
        deleted = self.ok("delete", id=ref)
        self.assertNotIn(ref, self.ids_now())
        self.assertEqual(self.undone(deleted["apply_id"])[0], 200)
        self.assertEqual(self.stored(ref), kept)


class InTheFile(Api):
    def build(self):
        return publish.build(self.s, "ABC", now="2030-01-15")

    def sections(self):
        return {s["id"]: s for s in self.build()["published"]["sections"]}

    def make(self, *rows, **more):
        ref = self.ok("new", values={"type": "needs", "title": "Needs from you"}, **more)["ref"]
        if rows:
            status, got = self.change(self.req("update", id=ref, changes={"body": body(*rows)}))
            self.assertEqual(status, 200, got)
        return ref

    def data_block(self, text):
        found = re.findall(r'<script type="application/json" id="clark-data">(.*?)</script>', text, re.S)
        self.assertEqual(len(found), 1)
        return json.loads(found[0])

    def test_the_file_carries_the_shown_rows_and_a_hidden_row_is_absent_in_every_spelling(self):
        ref = self.make(row(what="Shown row", **{"from": "Team A"}), row(what=MARK, **{"from": MARK}, hidden=1))
        entry = self.sections()[ref]
        self.assertEqual(entry["rows"], [{"what": "Shown row", "kind": "decision", "from": "Team A", "by": "04-03-2027"}])
        self.assertEqual(set(entry), {"id", "type", "title", "beside", "rows"})
        text = self.build()["body"].decode("utf-8")
        for spelling in spellings(MARK):
            self.assertNotIn(spelling, text)

    def test_a_hidden_section_and_a_list_with_nothing_to_show_are_absent(self):
        hidden_section = self.make(row(what=MARK))
        self.ok("update", id=hidden_section, changes={"hidden": 1})
        empty = self.make()
        all_left_out = self.make(row(what=MARK + "2", hidden=1))
        got = self.sections()
        for ref in (hidden_section, empty, all_left_out):
            self.assertNotIn(ref, got)
        text = self.build()["body"].decode("utf-8")
        for marker in (MARK, MARK + "2"):
            for spelling in spellings(marker):
                self.assertNotIn(spelling, text)

    def test_a_row_is_data_in_the_block_never_markup_and_never_in_an_attribute(self):
        ref = self.make(*[row(what=h, **{"from": h}) for h in HOSTILE])
        before = len(re.findall(r"<script\b", self.build()["body"].decode("utf-8")))
        text = self.build()["body"].decode("utf-8")
        self.assertEqual(len(re.findall(r'id="clark-data"', text)), 1)
        self.assertEqual(len(re.findall(r"<script\b", text)), before)
        block = re.search(r'<script type="application/json" id="clark-data">(.*?)</script>', text, re.S).group(1)
        for ch in "<>&\u2028\u2029":
            self.assertNotIn(ch, block, "none of them is raw inside the block")
        rows = {s["id"]: s for s in self.data_block(text)["sections"]}[ref]["rows"]
        self.assertEqual([r["what"] for r in rows], HOSTILE, "it arrives intact, as data")
        outside = text.replace(block, "")
        for h in HOSTILE:
            self.assertNotIn(h, outside, "the words are nowhere but in the data block")
        self.assertNotIn("<script>alert", text)

    def test_the_view_page_draws_only_text_for_the_rows(self):
        src = publish.Path(publish.__file__).parent / "page" / "src"
        for name in ("components/Needs.jsx", "edit/NeedsEdit.jsx", "logic/needs.js"):
            code = (src / name).read_text(encoding="utf-8")
            self.assertNotIn("dangerouslySetInnerHTML", code, name)
            self.assertNotIn("innerHTML", code, name)
