"""Row 1264 slice 1: the glance template's data layer (section_kinds/glancetemplate.py): canonical body, defaults, bad values, limits in
characters, tones, ids, the tile cap, upgrade, same bytes, what is published, the registry, the pins and schema step 29. Fictional data
only. Every refusal message carries the approved text, pinned word for word per key.

Run: python3 dev/run_tests.py test_tpl_glance_rules_1264
"""
import json
import sqlite3
import unittest
from unittest import mock

from clark import section_bodies, section_kinds, starter_check, store as store_module
from clark.section_kinds import base, glancetemplate as gt


class Rules:
    plain = staticmethod(lambda t: True)
    visible = staticmethod(lambda t: any(c.isalnum() for c in t))


def check(v):
    return gt.check(v, Rules)


def tile(**k):
    return {"id": "t1", "label": "Go-live", **k}


def bad(value):
    with unittest.TestCase().assertRaises(base.Bad) as got:
        check(value)
    return str(got.exception)


def _many(n):
    return {"v": 1, "bespoke": [tile(id=f"t{i}", label=f"Tile {i}") for i in range(n)]}


CASES = [
    ("not_object", []),
    ("unknown_field", {"v": 1, "extra": 1}),
    ("not_bool", {"v": 1, "health": {"shown": 1}}),
    ("bad_outline", {"v": 1, "builtin": {"risks": {"outline": "red"}}}),
    ("bad_tone", {"v": 1, "bespoke": [tile(tone="purple")]}),
    ("bad_id", {"v": 1, "bespoke": [tile(id="T 1")]}),
    ("dup_id", {"v": 1, "bespoke": [tile(), tile()]}),
    ("bad_order", {"v": 1, "order": ["nope"]}),
    ("too_many", _many(13)),
    ("label_missing", {"v": 1, "bespoke": [{"id": "t1", "label": "  "}]}),
    ("label_long", {"v": 1, "bespoke": [tile(label="a" * 41)]}),
    ("figure_long", {"v": 1, "bespoke": [tile(figure="a" * 13)]}),
    ("tag_long", {"v": 1, "bespoke": [tile(tag="a" * 13)]}),
    ("note_long", {"v": 1, "bespoke": [tile(note="a" * 61)]}),
    ("bad_text", {"v": 1, "bespoke": [tile(note=5)]}),
    ("too_long", {"v": 1, "bespoke": [tile(id=f"t{i}", label="a" * 40, figure="a" * 12, tag="a" * 12, note="a" * 60) for i in range(12)]}),
    ("bad_per_row", {"v": 1, "per_row": 5}),
]

APPROVED_TEXT = {
    "not_object": "At a glance must be one set of fields. Check it and try again.",
    "unknown_field": "At a glance has a field it does not keep. Reload the page and try again.",
    "not_bool": "A yes or no setting in At a glance has the wrong kind of value. Check it and try again.",
    "bad_outline": "The outline colour of a tile is green, amber, red or no colour. Choose one of those.",
    "bad_tone": "The colour of a tile is green, amber, red, blue or neutral. Choose one of those.",
    "bad_id": "A tile in At a glance has a name it cannot keep. Reload the page and try again.",
    "dup_id": "Two tiles in At a glance have the same name. Reload the page and try again.",
    "bad_order": "The order of the tiles in At a glance cannot be kept. Reload the page and try again.",
    "too_many": "You can have up to 12 tiles.",
    "label_missing": "Give the tile a label.",
    "label_long": "The tile label is too long (40 characters at most). Shorten it and try again.",
    "figure_long": "The tile figure is too long (12 characters at most). Shorten it and try again.",
    "tag_long": "The tile tag is too long (12 characters at most). Shorten it and try again.",
    "note_long": "The tile note is too long (60 characters at most). Shorten it and try again.",
    "bad_text": "A tile in At a glance has text of the wrong kind. Check it and try again.",
    "too_long": "At a glance is too long to keep (32 KB at most in all). Remove a tile or shorten the text and try again.",
    "bad_per_row": "Tiles on a line is 3 or 4. Choose one of those.",
}


class Canonical(unittest.TestCase):                                                  # T01, T02
    def test_t01_a_full_body_is_kept_as_it_is(self):
        body = {"v": 1, "health": {"shown": False, "own_row": True}, "order": ["t1", "overdue", "health", "risks", "decisions"],
                "builtin": {"overdue": {"hidden": True, "outline": "A"}, "risks": {"outline": "G"}, "decisions": {"hidden": True}},
                "bespoke": [{"id": "t1", "label": "Go-live", "figure": "12", "tag": "Watch", "note": "Fictional note", "tone": "amber", "hidden": True}]}
        self.assertEqual(check(body), body)

    def test_t02_defaults_are_filled_by_upgrade_and_not_stored(self):
        self.assertEqual(check({"v": 1}), {"v": 1})
        explicit = {"v": 1, "health": {"shown": True, "own_row": False}, "order": list(gt.BUILT_IN), "builtin": {"overdue": {"hidden": False, "outline": ""}}, "bespoke": []}
        self.assertEqual(check(explicit), {"v": 1})
        u = gt.upgrade({"v": 1})
        self.assertEqual(u["health"], {"shown": True, "own_row": False})
        self.assertIs(u["health"]["own_row"], False)
        self.assertEqual(u["order"], list(gt.BUILT_IN))
        self.assertEqual(u["builtin"], {n: {"hidden": False, "outline": ""} for n in gt.BUILT_IN if n != "health"})
        self.assertEqual(u["bespoke"], [])
        self.assertEqual(gt.upgrade(tile())["v"], 1)
        self.assertEqual(gt.upgrade({"bespoke": [tile()]})["bespoke"], [{"id": "t1", "label": "Go-live", "figure": "", "tag": "", "note": "", "tone": "neutral", "hidden": False}])

    def test_t03_the_two_health_fields_are_only_true_or_false(self):
        for field in ("shown", "own_row"):
            for wrong in (1, 0, "true", None, [], {}):
                with self.subTest(field=field, wrong=wrong):
                    if wrong is None:
                        self.assertEqual(check({"v": 1, "health": {field: None}}), {"v": 1})
                    else:
                        bad({"v": 1, "health": {field: wrong}})
        bad({"v": 1, "health": True})
        bad({"v": 1, "health": "hidden"})
        self.assertEqual(check({"v": 1, "health": {"own_row": True}}), {"v": 1, "health": {"own_row": True}})
        self.assertEqual(check({"v": 1, "health": {"shown": False}}), {"v": 1, "health": {"shown": False}})

    def test_t04_a_field_it_does_not_keep_is_refused_everywhere(self):
        for body in ({"v": 1, "extra": 1}, {"v": 1, "health": {"x": 1}}, {"v": 1, "builtin": {"overdue": {"x": 1}}}, {"v": 1, "builtin": {"health": {}}},
                     {"v": 1, "builtin": {"nope": {}}}, {"v": 1, "bespoke": [tile(extra="secret-word")]}):
            with self.subTest(body=body):
                self.assertNotIn("secret-word", bad(body))
        for body in (None, [], "x", {}, {"v": 2}, {"v": "1"}, {"v": 1, "bespoke": "x"}, {"v": 1, "bespoke": ["x"]}, {"v": 1, "order": "x"}, {"v": 1, "builtin": []}):
            with self.subTest(body=body):
                bad(body)


class Limits(unittest.TestCase):                                                      # T05 to T10
    def test_t05_limits_count_characters_not_bytes(self):
        for field, most in (("label", gt.LABEL_MAX), ("figure", gt.FIGURE_MAX), ("tag", gt.TAG_MAX), ("note", gt.NOTE_MAX)):
            with self.subTest(field=field):
                for letter in ("a", "é", "中", "\U00010400"):
                    self.assertEqual(check({"v": 1, "bespoke": [tile(**{field: letter * most})]})["bespoke"][0][field], letter * most)
                    bad({"v": 1, "bespoke": [tile(**{field: letter * (most + 1)})]})
        self.assertEqual((gt.LABEL_MAX, gt.FIGURE_MAX, gt.TAG_MAX, gt.NOTE_MAX), (40, 12, 12, 60))

    def test_t05b_the_widest_body_fits_the_byte_limit_whatever_the_letters(self):
        for letter in ("a", '"', "\\", "é", "中", "\U00010400"):
            wide = [{"id": f"t{i}", "label": letter * gt.LABEL_MAX, "figure": letter * gt.FIGURE_MAX, "tag": letter * gt.TAG_MAX, "note": letter * gt.NOTE_MAX,
                     "tone": "neutral", "hidden": True} for i in range(gt.BESPOKE_MAX)]
            stored = section_bodies.check("glancetemplate", json.dumps({"v": 1, "bespoke": wide}), store_module.BODY_RULES)
            self.assertLess(len(stored.encode("ascii")), gt.LIMIT, letter)

    def test_t06_the_tone_is_one_of_the_set_and_neutral_when_missing(self):
        self.assertEqual(gt.TONES, ("green", "amber", "red", "blue", "neutral"))
        for tone in gt.TONES:
            self.assertEqual(check({"v": 1, "bespoke": [tile(tone=tone)]})["bespoke"][0].get("tone", "neutral"), tone)
        self.assertNotIn("tone", check({"v": 1, "bespoke": [tile(tone="neutral")]})["bespoke"][0])
        self.assertNotIn("tone", check({"v": 1, "bespoke": [tile()]})["bespoke"][0])
        for wrong in ("purple", "", "Green", 3, ["red"]):
            bad({"v": 1, "bespoke": [tile(tone=wrong)]})
        for outline in ("R", "A", "G", "N"):
            self.assertEqual(check({"v": 1, "builtin": {"risks": {"outline": outline}}})["builtin"]["risks"], {"outline": outline})
        for wrong in ("red", "X", 1, "r"):
            bad({"v": 1, "builtin": {"risks": {"outline": wrong}}})

    def test_t07_ids_are_unique_plain_and_not_a_built_in_name(self):
        bad({"v": 1, "bespoke": [tile(), tile(label="Other")]})
        for wrong in ("", "T1", "a b", "x" * 17, "1a", "health", "overdue", "risks", "decisions", 5, None):
            bad({"v": 1, "bespoke": [tile(id=wrong)]})
        bad({"v": 1, "bespoke": [{"label": "No id"}]})
        self.assertEqual(len(check({"v": 1, "bespoke": [tile(), tile(id="t2")]})["bespoke"]), 2)

    def test_t08_the_tile_cap_is_one_constant(self):
        self.assertEqual(gt.BESPOKE_MAX, 12)
        many = lambda n: {"v": 1, "bespoke": [tile(id=f"t{i}", label=f"Tile {i}") for i in range(n)]}
        self.assertEqual(len(check(many(12))["bespoke"]), 12)
        bad(many(13))
        with mock.patch.object(gt, "BESPOKE_MAX", 3):
            self.assertEqual(len(check(many(3))["bespoke"]), 3)
            bad(many(4))

    def test_t09_a_tile_needs_a_label_and_words_are_trimmed(self):
        for wrong in (None, "", "   ", "!!", 4):
            bad({"v": 1, "bespoke": [{"id": "t1", "label": wrong}]})
        bad({"v": 1, "bespoke": [{"id": "t1"}]})
        got = check({"v": 1, "bespoke": [tile(label="  Go-live  ", figure=" 3 ", tag="  ", note=None)]})["bespoke"][0]
        self.assertEqual(got, {"id": "t1", "label": "Go-live", "figure": "3"})
        for field in ("figure", "tag", "note"):
            bad({"v": 1, "bespoke": [tile(**{field: 5})]})

    def test_t10_the_order_names_known_tiles_once_and_is_completed(self):
        bad({"v": 1, "order": ["health", "health"]})
        bad({"v": 1, "order": ["nope"]})
        bad({"v": 1, "order": ["t9"], "bespoke": [tile()]})
        bad({"v": 1, "order": [3]})
        self.assertEqual(check({"v": 1, "order": ["decisions"]})["order"], ["decisions", "health", "overdue", "risks"])
        self.assertNotIn("order", check({"v": 1, "order": ["health", "overdue"]}))
        self.assertEqual(check({"v": 1, "bespoke": [tile()]}).get("order"), None)
        self.assertEqual(gt.upgrade({"bespoke": [tile()]})["order"], ["health", "overdue", "risks", "decisions", "t1"])
        self.assertEqual(gt.upgrade({"order": ["t1"], "bespoke": [tile()]})["order"], ["t1", "health", "overdue", "risks", "decisions"])


class Reads(unittest.TestCase):                                                       # T11, T12, T15
    def test_t11_upgrade_is_total(self):
        for junk in (None, 0, "x", [], {}, {"v": 9}, {"health": 3, "order": 4, "builtin": 5, "bespoke": 6}, {"bespoke": [None, 3, {"id": 5}, {"label": "x"}]},
                     {"health": {"shown": "no", "own_row": 7}}, {"builtin": {"overdue": {"outline": "zz", "hidden": 2}}}):
            with self.subTest(junk=junk):
                u = gt.upgrade(junk)
                self.assertEqual(set(u), {"v", "health", "per_row", "order", "builtin", "bespoke"})      # slice 9: + per_row
                self.assertEqual(u["health"], {"shown": True, "own_row": False})
                self.assertEqual(sorted(u["order"]), sorted(list(gt.BUILT_IN) + [t["id"] for t in u["bespoke"]]))
        self.assertEqual(gt.upgrade({"bespoke": [None, {"id": "t1", "label": "ok"}, {"id": "t1", "label": "dup"}]})["bespoke"][0]["label"], "ok")
        self.assertEqual(len(gt.upgrade({"bespoke": [None, {"id": "t1", "label": "ok"}, {"id": "t1", "label": "dup"}]})["bespoke"]), 1)

    def test_t12_the_same_content_always_stores_the_same_bytes(self):
        a = {"v": 1, "bespoke": [tile(figure="3")], "builtin": {"overdue": {"outline": "R"}}, "health": {"own_row": True}}
        b = {"health": {"own_row": True, "shown": True}, "builtin": {"overdue": {"outline": "R", "hidden": False}, "risks": {}}, "v": 1,
             "bespoke": [{"hidden": False, "figure": " 3", "tone": "neutral", "label": "Go-live ", "id": "t1", "tag": "", "note": ""}], "order": ["health", "overdue", "risks", "decisions", "t1"]}
        one = section_bodies.check("glancetemplate", json.dumps(a), store_module.BODY_RULES)
        two = section_bodies.check("glancetemplate", json.dumps(b), store_module.BODY_RULES)
        self.assertEqual(one, two)
        self.assertEqual(section_bodies.check("glancetemplate", one, store_module.BODY_RULES), one)

    def test_t15_refusals_use_the_approved_words_and_never_quote_the_value(self):
        self.assertEqual(set(gt.WORDS), set(gt.KEYS_OF_WORDS))
        self.assertEqual(set(gt.APPROVED), set(gt.KEYS_OF_WORDS))
        self.assertEqual(len(gt.APPROVED), 17)
        got = bad({"v": 1, "bespoke": [tile(label="secret-word" * 10)]})
        self.assertEqual(got, gt.WORDS["label_long"])
        self.assertNotIn("secret-word", got)

    def test_t15b_no_message_says_pending_or_is_a_placeholder(self):
        for key, text in gt.words().items():
            with self.subTest(key=key):
                self.assertNotIn("pending", text.lower())
                self.assertNotIn("[", text)
                self.assertTrue(text.endswith("."))
        self.assertFalse(hasattr(gt, "WORDS_PENDING"))

    def test_t15c_no_message_quotes_the_offending_value(self):
        for key, body in CASES:
            if key == "too_long":
                continue
            marked = json.loads(json.dumps(body).replace("Go-live", "zq-offender"))
            with self.subTest(key=key):
                self.assertNotIn("zq-offender", bad(marked))
        for field in ("label", "figure", "tag", "note"):
            self.assertNotIn("zq-offender", bad({"v": 1, "bespoke": [tile(**{field: "zq-offender" * 10})]}))
        for wrong in ("zq-offender", ["zq-offender"], {"zq-offender": 1}):
            for body in ({"v": 1, "bespoke": [tile(tone=wrong)]}, {"v": 1, "builtin": {"risks": {"outline": wrong}}}, {"v": 1, "order": [wrong]},
                         {"v": 1, "health": {"shown": wrong}}, {"v": 1, "bespoke": [tile(id=wrong)]}):
                try:
                    msg = bad(body)
                except TypeError:
                    continue
                self.assertNotIn("zq-offender", msg)

    def test_t15d_every_key_has_one_case_that_says_exactly_the_approved_text(self):
        self.assertEqual([k for k, _ in CASES], list(gt.KEYS_OF_WORDS))
        self.assertEqual({k for k, _ in CASES}, set(APPROVED_TEXT))
        for key, body in CASES:
            with self.subTest(key=key):
                if key == "too_long":
                    with mock.patch.object(gt, "LIMIT", 1024):
                        self.assertEqual(bad(body), APPROVED_TEXT[key].replace("32 KB", "1 KB"))
                else:
                    self.assertEqual(bad(body), APPROVED_TEXT[key])
                self.assertEqual(gt.words()[key], APPROVED_TEXT[key])
                self.assertEqual(gt.APPROVED[key], APPROVED_TEXT[key])

    def test_t15e_the_texts_that_name_a_limit_read_the_constants(self):
        for const, key, field, was, now in (("LABEL_MAX", "label_long", "label", "40", "7"), ("FIGURE_MAX", "figure_long", "figure", "12", "3"),
                                            ("TAG_MAX", "tag_long", "tag", "12", "4"), ("NOTE_MAX", "note_long", "note", "60", "9")):
            with self.subTest(key=key), mock.patch.object(gt, const, int(now)):
                got = bad({"v": 1, "bespoke": [tile(**{field: "a" * (int(now) + 1)})]})
                self.assertEqual(got, APPROVED_TEXT[key].replace(f"({was} characters", f"({now} characters"))
                self.assertIn(f"({now} characters at most)", got)
        with mock.patch.object(gt, "LIMIT", 4096):
            self.assertIn("(4 KB at most in all)", gt.words()["too_long"])
        self.assertEqual((gt.LABEL_MAX, gt.FIGURE_MAX, gt.TAG_MAX, gt.NOTE_MAX, gt.LIMIT), (40, 12, 12, 60, 32768))

    def test_t15f_the_size_check_counts_the_stored_text(self):
        body = {"v": 1, "bespoke": [tile(note="a" * 50)]}
        size = len(str(check(body)).encode("utf-8"))
        with mock.patch.object(gt, "LIMIT", size):
            self.assertEqual(check(body), check(body))
        with mock.patch.object(gt, "LIMIT", size - 1):
            self.assertEqual(bad(body), gt.words()["too_long"])


class Published(unittest.TestCase):                                                   # T13, T14
    def test_t13_hidden_tiles_publish_nothing_of_their_words(self):
        value = check({"v": 1, "bespoke": [tile(label="Shown one", note="shown note"), tile(id="t2", label="Hidden-two", figure="9", tag="hid", note="hidden-note", hidden=True)],
                       "order": ["t2", "t1"]})
        out = gt.published(value, None)
        text = json.dumps(out)
        for word in ("Hidden-two", "hidden-note", "hid\"", "t2"):
            self.assertNotIn(word, text)
        self.assertEqual([t["id"] for t in out["content"]["bespoke"]], ["t1"])
        self.assertEqual(out["content"]["order"], ["t1", "health", "overdue", "risks", "decisions"])
        self.assertEqual(out["content"]["bespoke"][0], {"id": "t1", "label": "Shown one", "figure": "", "tag": "", "note": "shown note", "tone": "neutral"})

    def test_t13b_the_health_eye_and_own_row_are_in_the_file_only_as_flags(self):
        out = gt.published(check({"v": 1, "health": {"shown": False, "own_row": True}, "bespoke": [tile()]}), None)["content"]
        self.assertEqual(out["health"], {"shown": False, "own_row": True})
        plain = gt.published({"v": 1, "bespoke": [tile()]}, None)["content"]
        self.assertEqual(plain["health"], {"shown": True, "own_row": False})
        self.assertEqual(set(plain), {"health", "per_row", "order", "builtin", "bespoke"})      # slice 9: + per_row
        self.assertEqual(plain["builtin"], {n: {"hidden": False, "outline": ""} for n in gt.SETTLED})

    def test_t14_a_body_that_is_not_there_publishes_nothing(self):
        for empty in ("", None, [], 0):
            self.assertIsNone(gt.published(empty, None))
        self.assertIsNone(gt.published({"v": 1, "health": {"shown": False}}, None))      # no own tile, no count, health eye off: nothing to draw
        self.assertEqual(gt.published({"v": 1}, None)["content"]["health"], {"shown": True, "own_row": False})      # an existing body (no health field) shows health
        self.assertIsNone(gt.published(check({"v": 1, "health": {"shown": False}, "bespoke": [tile(hidden=True)]}), None))
        self.assertEqual(gt.EMPTY, "")      # fresh stays left out (row 1251); the Edit writes the eye off on the first change (see test_tpl_glance_body_node_1264)
        self.assertTrue(gt.upgrade({"v": 1})["health"]["shown"])      # no health field (an existing page): shown

    def test_t14b_nothing_of_a_bad_stored_body_reaches_the_file(self):
        out = gt.published({"v": 1, "bespoke": [{"id": "t1", "label": "ok", "x": "leak-word"}, 3], "z": "leak-word"}, None)
        self.assertNotIn("leak-word", json.dumps(out))


class Registered(unittest.TestCase):                                                  # T16, T17
    def test_t16_the_registry_the_store_and_the_schema_know_the_type(self):
        self.assertIs(section_kinds.REGISTRY["glancetemplate"], gt)
        self.assertEqual(len(section_kinds.TYPES), 20)
        self.assertIn("glancetemplate", store_module.SECTION_TYPES)
        self.assertIs(section_bodies.CHECKERS["glancetemplate"], gt.check)
        self.assertEqual(section_bodies.LIMITS["glancetemplate"], gt.LIMIT)
        self.assertTrue(gt.READY is True)

    def test_t17_step_29_lets_an_older_file_keep_the_type_and_a_second_run_changes_nothing(self):
        self.assertEqual(store_module.SCHEMA_VERSION, 37)
        self.assertEqual(starter_check.SCHEMA_VERSION, store_module.SCHEMA_VERSION)
        self.assertEqual(dict(store_module.MIGRATIONS)[29], store_module.migrate_glance_template_section_type)
        self.assertEqual(store_module.GLANCE_TEMPLATE_STEP, 29)
        con = sqlite3.connect(":memory:")
        con.execute(store_module.REPORT_SECTIONS_WITH_REPORT_HEADLINE.replace("CREATE TABLE IF NOT EXISTS report_sections (", "CREATE TABLE report_sections (", 1)
                    .replace("  project TEXT NOT NULL REFERENCES projects(code) ON DELETE CASCADE,", "  project TEXT NOT NULL,"))
        con.execute("INSERT INTO report_sections VALUES ('ABC','s1','callout','T','b',0,0,1)")
        con.execute("INSERT INTO report_sections VALUES ('ABC','s3','reportheadline','T','',0,1,3)")
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute("INSERT INTO report_sections VALUES ('ABC','s2','glancetemplate','T','',0,0,2)")
        store_module.migrate_glance_template_section_type(con)
        con.execute("INSERT INTO report_sections VALUES ('ABC','s2','glancetemplate','T','',0,0,2)")
        before = con.execute("SELECT * FROM report_sections ORDER BY sort_order").fetchall()
        self.assertEqual([r[1] for r in before], ["s1", "s2", "s3"])
        self.assertEqual(before[2], ("ABC", "s3", "reportheadline", "T", "", 0, 1, 3))
        sql = con.execute("SELECT sql FROM sqlite_master WHERE name='report_sections'").fetchone()[0]
        store_module.migrate_glance_template_section_type(con)
        self.assertEqual(con.execute("SELECT * FROM report_sections ORDER BY sort_order").fetchall(), before)
        self.assertEqual(con.execute("SELECT sql FROM sqlite_master WHERE name='report_sections'").fetchone()[0], sql)
        self.assertEqual(con.execute("SELECT count(*) FROM sqlite_master WHERE name LIKE 'report_sections%'").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
