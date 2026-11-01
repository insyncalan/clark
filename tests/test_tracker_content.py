"""The progress tracker's own shape (src/clark/section_bodies.py `_checked_tracker`, guarded) and the change route's size limit
(src/clark/server.py CHANGE_BODY_LIMIT, guarded): the widest tracker the checker accepts is stored under its limit, anything else is refused
in plain words that never quote the value.

Run: python3 dev/run_tests.py test_tracker_content
"""
import copy
import json
import unittest

from _paths import SRC
from clark import section_bodies as sb, server as sv
from clark.store import BODY_RULES

LETTER = "\U00010400"        # one letter that takes four bytes typed and twelve ASCII bytes once stored: the worst case


def check(body):
    return sb.check("tracker", body if isinstance(body, str) else json.dumps(body), BODY_RULES)


def line(**more):
    got = {"no": "1", "text": "Set up the test site", "start": "2030-01-01", "end": "2030-02-01", "status": "inprogress",
           "weight": 400, "planned": 1000, "achieved": 800, "tasks": 12, "agents": None, "workflows": 3}
    got.update(more)
    return got


DEMO = {"v": 1, "overall": {"actual": 625, "planned": 700, "health": "atrisk", "note": "One supplier is late."},
        "columns": {"tasks": True, "agents": False, "workflows": True},
        "groups": [{"name": "Build", "lines": [line(), line(no="2", text="Train the team", status="planned", planned=0, achieved=0)]},
                   {"name": "Launch", "lines": []}]}


def biggest(letter=LETTER):
    """The largest body the checker accepts: the most groups and lines, every text at its longest, in the given letter."""
    spread = [sb.TRACKER_MAX_LINES // sb.TRACKER_MAX_GROUPS + (k < sb.TRACKER_MAX_LINES % sb.TRACKER_MAX_GROUPS) for k in range(sb.TRACKER_MAX_GROUPS)]
    return {"v": 1, "overall": {"actual": 1000, "planned": 1000, "health": "ontrack", "note": letter * sb.TRACKER_NOTE_MAX},
            "columns": {"tasks": True, "agents": True, "workflows": True},
            "groups": [{"name": letter * sb.TRACKER_NAME_MAX,
                        "lines": [line(no=letter * sb.TRACKER_NO_MAX, text=letter * sb.TRACKER_TEXT_MAX, tasks=99999, agents=99999, workflows=99999)
                                  for _ in range(n)]} for n in spread]}


class Shape(unittest.TestCase):
    def refuses(self, body, words=None):
        with self.assertRaises(sb.Bad) as e:
            check(body)
        if words is not None:
            self.assertEqual(str(e.exception), words)
        return str(e.exception)

    def test_a_good_tracker_is_kept_whole_and_saving_it_again_changes_nothing(self):
        got = check(DEMO)
        self.assertEqual(json.loads(got), DEMO)
        self.assertEqual(check(got), got)
        self.assertEqual(check(json.dumps(DEMO, indent=4)), got)

    def test_what_is_missing_takes_its_default_and_nothing_is_added_that_was_not_named(self):
        got = json.loads(check({"groups": [{"name": "Build", "lines": [{"text": "One"}]}]}))
        self.assertEqual(got["overall"], {"actual": None, "planned": None, "health": "", "note": ""})
        self.assertEqual(got["columns"], {"tasks": False, "agents": False, "workflows": False})
        self.assertEqual(got["groups"][0]["lines"][0], {"no": "", "text": "One", "start": "", "end": "", "status": "planned",
                                                         "weight": 0, "planned": 0, "achieved": 0, "tasks": None, "agents": None, "workflows": None})
        self.assertEqual(json.loads(check({})), {"v": 1, "overall": got["overall"], "columns": got["columns"], "groups": []})

    def test_a_group_with_no_lines_is_kept(self):
        self.assertEqual(json.loads(check({"groups": [{"name": "Later"}]}))["groups"], [{"name": "Later", "lines": []}])

    def test_the_list_form_and_a_wrong_version_are_refused(self):
        self.refuses([1, 2], sb.TRACKER_SHAPE)
        self.refuses({"v": 2}, sb.TRACKER_SHAPE)
        self.refuses({"v": "1"}, sb.TRACKER_SHAPE)
        self.refuses({"v": True}, sb.TRACKER_SHAPE)

    def test_an_unknown_key_is_refused_at_every_level_never_dropped(self):
        for mutate, words in ((lambda d: d.update(extra=1), sb.TRACKER_SHAPE),
                              (lambda d: d["overall"].update(extra=1), sb.TRACKER_OVERALL),
                              (lambda d: d["columns"].update(extra=True), sb.TRACKER_COLUMNS_BAD),
                              (lambda d: d["groups"][0].update(extra=1), sb.TRACKER_GROUP_SHAPE),
                              (lambda d: d["groups"][0]["lines"][0].update(extra=1), sb.TRACKER_LINE_SHAPE)):
            with self.subTest(words=words):
                body = copy.deepcopy(DEMO)
                mutate(body)
                self.refuses(body, words)

    def test_the_wrong_type_at_each_place_is_refused(self):
        for mutate, words in ((lambda d: d.update(overall=[]), sb.TRACKER_OVERALL),
                              (lambda d: d.update(columns=[]), sb.TRACKER_COLUMNS_BAD),
                              (lambda d: d.update(groups={}), sb.TRACKER_SHAPE),
                              (lambda d: d["groups"].append("x"), sb.TRACKER_GROUP_SHAPE),
                              (lambda d: d["groups"][0].update(lines={}), sb.TRACKER_GROUP_SHAPE),
                              (lambda d: d["groups"][0]["lines"].append([]), sb.TRACKER_LINE_SHAPE),
                              (lambda d: d["groups"][0]["lines"].append({"no": "9"}), sb.TRACKER_LINE_SHAPE),
                              (lambda d: d["groups"].append({"lines": []}), sb.TRACKER_GROUP_SHAPE),
                              (lambda d: d["columns"].update(tasks=1), sb.TRACKER_COLUMNS_BAD),
                              (lambda d: d["groups"][0]["lines"][0].update(text=5), sb.TRACKER_TEXT_MISSING),
                              (lambda d: d["groups"][0].update(name=None), sb.TRACKER_NAME_MISSING)):
            with self.subTest(words=words):
                body = copy.deepcopy(DEMO)
                mutate(body)
                self.refuses(body, words)

    def test_a_percentage_is_a_whole_number_of_tenths_from_0_to_1000(self):
        for field in ("weight", "planned", "achieved"):
            for good in (0, 1, 625, 1000):
                body = copy.deepcopy(DEMO)
                body["groups"][0]["lines"][0][field] = good
                self.assertEqual(json.loads(check(body))["groups"][0]["lines"][0][field], good)
            for bad in (-1, 1001, 100000, 1.5, "50", None, True, False, [], {}):
                with self.subTest(field=field, bad=bad):
                    body = copy.deepcopy(DEMO)
                    body["groups"][0]["lines"][0][field] = bad
                    self.assertIn(self.refuses(body), (sb.TRACKER_PERCENT, sb.BAD_NUMBER))

    def test_the_overall_figures_are_empty_or_0_to_1000_and_the_health_is_one_of_three_or_empty(self):
        for field in ("actual", "planned"):
            for good in (None, 0, 1000):
                body = copy.deepcopy(DEMO)
                body["overall"][field] = good
                self.assertEqual(json.loads(check(body))["overall"][field], good)
            for bad in (-1, 1001, "5", True, 2.5):
                body = copy.deepcopy(DEMO)
                body["overall"][field] = bad
                self.assertIn(self.refuses(body), (sb.TRACKER_OVERALL, sb.BAD_NUMBER))
        for good in ("", "ontrack", "atrisk", "offtrack", None):
            body = copy.deepcopy(DEMO)
            body["overall"]["health"] = good
            self.assertEqual(json.loads(check(body))["overall"]["health"], good or "")
        for bad in ("On track", "ONTRACK", "green", 1, []):
            body = copy.deepcopy(DEMO)
            body["overall"]["health"] = bad
            self.refuses(body, sb.TRACKER_OVERALL)

    def test_a_status_is_one_of_the_four_words(self):
        for good in sb.TRACKER_STATUSES:
            body = copy.deepcopy(DEMO)
            body["groups"][0]["lines"][0]["status"] = good
            self.assertEqual(json.loads(check(body))["groups"][0]["lines"][0]["status"], good)
        for bad in ("Planned", "done", "", "in progress", None, 1, []):
            body = copy.deepcopy(DEMO)
            body["groups"][0]["lines"][0]["status"] = bad
            self.refuses(body, sb.TRACKER_STATUS)

    def test_the_extra_counts_are_whole_numbers_or_empty(self):
        for bad in (-1, 100000, "3", True, 1.5):
            body = copy.deepcopy(DEMO)
            body["groups"][0]["lines"][0]["agents"] = bad
            self.assertIn(self.refuses(body), (sb.TRACKER_COUNT, sb.BAD_NUMBER))

    def test_dates_are_real_and_an_end_is_not_before_its_start(self):
        for bad in ("2030-02-30", "2030-13-01", "1999-12-31", "2101-01-01", "01-02-2030", "2030-1-1", "tomorrow", 5, "٢030-01-01"):
            for field in ("start", "end"):
                body = copy.deepcopy(DEMO)
                body["groups"][0]["lines"][0][field] = bad
                self.assertIn(self.refuses(body), (sb.TRACKER_DATE,))
        body = copy.deepcopy(DEMO)
        body["groups"][0]["lines"][0].update(start="2030-03-01", end="2030-02-01")
        self.refuses(body, sb.TRACKER_DATE_ORDER)
        for ok in (("2030-02-01", "2030-02-01"), ("", "2030-02-01"), ("2030-02-01", ""), ("", ""), (None, None)):
            body = copy.deepcopy(DEMO)
            body["groups"][0]["lines"][0].update(start=ok[0], end=ok[1])
            check(body)

    def test_text_is_trimmed_must_be_visible_and_has_a_length_limit(self):
        body = copy.deepcopy(DEMO)
        body["groups"][0]["name"], body["groups"][0]["lines"][0]["text"] = "  Build  ", "  One  "
        got = json.loads(check(body))
        self.assertEqual((got["groups"][0]["name"], got["groups"][0]["lines"][0]["text"]), ("Build", "One"))
        for field_in, words in ((("name",), sb.TRACKER_NAME_MISSING), (("text",), sb.TRACKER_TEXT_MISSING)):
            for blank in ("", "   ", " ", "⠀"):
                body = copy.deepcopy(DEMO)
                (body["groups"][0] if field_in == ("name",) else body["groups"][0]["lines"][0])[field_in[0]] = blank
                self.refuses(body, words)
        for place, limit, words in ((("name",), sb.TRACKER_NAME_MAX, sb.TRACKER_NAME_LONG), (("text",), sb.TRACKER_TEXT_MAX, sb.TRACKER_TEXT_LONG),
                                    (("no",), sb.TRACKER_NO_MAX, sb.TRACKER_NO_BAD)):
            for n, ok in ((limit, True), (limit + 1, False)):
                body = copy.deepcopy(DEMO)
                (body["groups"][0] if place == ("name",) else body["groups"][0]["lines"][0])[place[0]] = "x" * n
                if ok:
                    check(body)
                else:
                    self.refuses(body, words)
        for n, ok in ((sb.TRACKER_NOTE_MAX, True), (sb.TRACKER_NOTE_MAX + 1, False)):
            body = copy.deepcopy(DEMO)
            body["overall"]["note"] = "x" * n
            check(body) if ok else self.refuses(body, sb.TRACKER_NOTE_LONG)

    def test_markup_is_only_text_and_hidden_characters_are_refused(self):
        body = copy.deepcopy(DEMO)
        body["groups"][0]["lines"][0]["text"] = "<script>alert(1)</script>"
        self.assertEqual(json.loads(check(body))["groups"][0]["lines"][0]["text"], "<script>alert(1)</script>")
        for ch in ("‮", "​", " ", "\u0000", "\n", ""):
            body = copy.deepcopy(DEMO)
            body["groups"][0]["name"] = "a" + ch + "b"
            self.refuses(body, sb.BAD_TEXT)

    def test_the_counts_of_groups_and_lines_have_limits(self):
        groups = lambda n, lines: {"groups": [{"name": f"G{i}", "lines": [line() for _ in range(lines)]} for i in range(n)]}
        check(groups(sb.TRACKER_MAX_GROUPS, 1))
        self.refuses(groups(sb.TRACKER_MAX_GROUPS + 1, 0), sb.TRACKER_TOO_MANY_GROUPS)
        check(groups(1, sb.TRACKER_MAX_LINES_PER_GROUP))
        self.refuses(groups(1, sb.TRACKER_MAX_LINES_PER_GROUP + 1), sb.TRACKER_TOO_MANY_LINES)
        check(groups(5, sb.TRACKER_MAX_LINES // 5))
        self.refuses({"groups": [{"name": f"G{i}", "lines": [line() for _ in range(100)]} for i in range(5)] + [{"name": "More", "lines": [line()]}]},
                     sb.TRACKER_TOO_MANY_LINES)

    def test_the_words_never_quote_the_value_and_are_plain(self):
        secret = "SECRET-ZQ"
        for mutate in (lambda d: d["groups"][0]["lines"][0].update(status=secret), lambda d: d["groups"][0]["lines"][0].update(start=secret),
                       lambda d: d["groups"][0]["lines"][0].update(text=secret * 40), lambda d: d["overall"].update(health=secret),
                       lambda d: d["groups"][0].update(name=secret * 20), lambda d: d["groups"][0]["lines"][0].update(planned=secret),
                       lambda d: d.update(**{secret: 1})):
            body = copy.deepcopy(DEMO)
            mutate(body)
            self.assertNotIn(secret, self.refuses(body))
        for name in dir(sb):
            if name.startswith("TRACKER_") and isinstance(getattr(sb, name), str) and name.isupper() and " " in getattr(sb, name):
                words = getattr(sb, name)
                self.assertTrue(words.endswith("."), words)
                self.assertFalse(words.lower().startswith("clark"), words)
                for jargon in ("JSON", "json", "schema", "parse", "NaN"):
                    self.assertNotIn(jargon, words)

    def test_the_tracker_still_publishes_nothing_of_its_content(self):
        self.assertEqual(sb.published("tracker", json.loads(check(DEMO))), {})

    def test_the_checker_is_the_registered_one_and_a_needs_body_is_not_a_tracker(self):
        self.assertIs(sb.CHECKERS["tracker"], sb._checked_tracker)
        self.refuses({"v": 1, "rows": []}, sb.TRACKER_SHAPE)


class TooLong(Shape):
    def test_a_line_or_note_that_is_too_long_says_what_to_do(self):
        for words in (sb.TRACKER_TEXT_LONG, sb.TRACKER_NOTE_LONG):
            self.assertIn("Shorten it", words)
        body = copy.deepcopy(DEMO)
        body["groups"][0]["lines"][0]["text"] = "a" * (sb.TRACKER_TEXT_MAX + 1)
        self.assertEqual(self.refuses(body), sb.TRACKER_TEXT_LONG)
        body = copy.deepcopy(DEMO)
        body["overall"]["note"] = "a" * (sb.TRACKER_NOTE_MAX + 1)
        self.assertEqual(self.refuses(body), sb.TRACKER_NOTE_LONG)


class Size(unittest.TestCase):
    """Non-ASCII text is stored as \\u escapes (up to twelve bytes a letter), so the size limit has to fit the checker's own largest tracker."""

    def test_the_largest_tracker_the_checker_accepts_is_saved_within_the_stored_limit(self):
        body = biggest()
        self.assertEqual(sum(len(g["lines"]) for g in body["groups"]), sb.TRACKER_MAX_LINES)
        stored = check(json.dumps(body, ensure_ascii=False))
        self.assertLessEqual(len(stored.encode("ascii")), sb.LIMITS["tracker"])
        self.assertLess(len(stored), 262144)
        self.assertEqual(check(stored), stored)

    def test_the_same_tracker_in_plain_ascii_is_well_inside_the_limit(self):
        body = biggest()
        for g in body["groups"]:
            g["name"] = "g" * sb.TRACKER_NAME_MAX
            for ln in g["lines"]:
                ln["text"], ln["no"] = "t" * sb.TRACKER_TEXT_MAX, "9" * sb.TRACKER_NO_MAX
        self.assertLess(len(check(body)), sb.LIMITS["tracker"] // 4)

    def test_the_limit_is_kept_for_a_body_of_another_size(self):
        with self.assertRaises(sb.Bad) as e:
            check("x" * (sb.LIMITS["tracker"] + 1))
        self.assertEqual(str(e.exception), sb.TOO_BIG)
        self.assertEqual(sb.LIMITS["needs"], 262144)             # the needs limit is untouched

    def test_the_change_route_limit_is_one_named_constant_and_the_small_routes_are_unchanged(self):
        self.assertEqual(sv.ROUTE_BODY_LIMITS["/api/change"], sv.CHANGE_BODY_LIMIT)
        self.assertEqual(sv.CHANGE_BODY_LIMIT, 16 * 1024)
        self.assertLessEqual(sv.CHANGE_BODY_LIMIT, sv.BODY_LIMIT)
        for route, limit in (("/api/undo", 4 * 1024), ("/api/sneak/read", 4 * 1024), ("/api/profile", 2 * 1024), ("/api/draft-email", 16 * 1024)):
            self.assertEqual(sv.ROUTE_BODY_LIMITS[route], limit, route)


if __name__ == "__main__":
    unittest.main()
