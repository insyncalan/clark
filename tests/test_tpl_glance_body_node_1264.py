"""Row 1264 slice 4: killer tests for the pure body rules (templates/glanceBody.js): the health tile's value, colour and reason, and the
canonical body (defaults are never stored). Fictional data only.

Run: python3 dev/run_tests.py test_tpl_glance_body_node_1264
Quick tier: no browser. Bundled by the pinned esbuild and run in node (skipped when node is not on the machine).
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

ENTRY = ROOT / "tests" / "fixtures" / "glancebody_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "gb.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=GB", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    return _BUNDLE["code"]


def run_node(probe):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(bundle() + ";\nconst G = GB;\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


def health_tile(project):
    return run_node("G.builtinTiles(G.readBody({source: {}}), [], '2030-01-15', %s).find((t) => t.key === 'health')" % json.dumps(project))


class HealthTile(unittest.TestCase):
    def test_no_health_is_the_words_not_set_in_neutral_with_no_reason(self):
        for project in (None, {}, {"health": ""}):
            with self.subTest(project=project):
                t = health_tile(project)
                self.assertEqual((t["value"], t["rag"], t["reason"]), ("Not set", "n", ""))

    def test_an_unknown_health_word_is_neutral(self):
        self.assertEqual(health_tile({"health": "Sideways"})["rag"], "n")

    def test_each_health_word_gives_its_colour_and_keeps_its_reason(self):
        for word, rag in (("On track", "g"), ("At risk", "a"), ("Off track", "r")):
            with self.subTest(word=word):
                t = health_tile({"health": word, "health_reason": "Fictional reason"})
                self.assertEqual((t["value"], t["rag"], t["reason"]), (word, rag, "Fictional reason"))

    def test_a_health_with_no_reason_has_an_empty_reason(self):
        self.assertEqual(health_tile({"health": "At risk"})["reason"], "")


class Compact(unittest.TestCase):
    def test_the_default_order_is_not_stored(self):
        self.assertEqual(run_node("G.compact(G.readBody({content: {v: 1}}))"), {"v": 1})

    def test_a_changed_order_is_stored(self):
        got = run_node("G.compact(G.withChange(G.readBody({content: {v: 1}}), {order: ['risks', 'health', 'overdue', 'decisions']}))")
        self.assertEqual(got, {"v": 1, "order": ["risks", "health", "overdue", "decisions"]})


def read(body):
    return run_node("G.readBody({body: %s})" % json.dumps(json.dumps(body)))


B1 = {"id": "bud", "label": "Fictional", "figure": "1"}


class ReadBody(unittest.TestCase):
    def test_a_body_with_nothing_has_every_field_at_its_default(self):
        self.assertEqual(read({}), {"v": 1, "health": {"shown": True, "own_row": False}, "per_row": 4, "order": ["health", "overdue", "risks", "decisions"],
                                    "builtin": {k: {"hidden": False, "outline": ""} for k in ("overdue", "risks", "decisions")}, "bespoke": []})

    def test_a_per_row_that_is_not_3_or_4_reads_as_4_and_3_is_kept(self):
        for wrong in (9, 5, 0, 2, "3", None, True):
            self.assertEqual(read({"per_row": wrong})["per_row"], 4, repr(wrong))
        self.assertEqual(read({"per_row": 3})["per_row"], 3)

    def test_a_never_written_body_starts_with_the_health_eye_off_and_a_written_one_without_the_field_shows_it(self):
        got = run_node("""[{body: ""}, {body: '{"v":1}'}, {body: "{}"}, {body: '{"v":1,"health":{"shown":true}}'}, {}, null, {content: {v: 1}}, {body: '{"v":1,"health":{"shown":false}}'}].map((s) => G.readBody(s).health.shown)""")
        self.assertEqual(got, [False, True, True, True, False, False, True, False])

    def test_the_first_change_to_a_never_written_body_stores_the_eye_off(self):
        got = run_node("""G.compact(G.withChange(G.readBody({body: ""}), {outline: ["risks", "A"]}))""")
        self.assertEqual(got, {"v": 1, "health": {"shown": False}, "builtin": {"risks": {"outline": "A"}}})
        got = run_node("""G.compact(G.withChange(G.readBody({body: '{"v":1}'}), {outline: ["risks", "A"]}))""")
        self.assertEqual(got, {"v": 1, "builtin": {"risks": {"outline": "A"}}})

    def test_every_field_read_back(self):
        got = read({"health": {"shown": False, "own_row": True}, "builtin": {"risks": {"hidden": True, "outline": "A"}, "decisions": {"outline": "N"}},
                    "bespoke": [B1], "order": ["bud", "risks"]})
        self.assertEqual(got["health"], {"shown": False, "own_row": True})
        self.assertEqual(got["builtin"]["risks"], {"hidden": True, "outline": "A"})
        self.assertEqual(got["builtin"]["decisions"], {"hidden": False, "outline": "N"})
        self.assertEqual(got["builtin"]["overdue"], {"hidden": False, "outline": ""})
        self.assertEqual(got["order"], ["bud", "risks", "health", "overdue", "decisions"])
        self.assertEqual(got["bespoke"], [B1])

    def test_wrong_shapes_fall_back_to_the_defaults(self):
        base = read({})
        for body in ({"health": "x"}, {"health": 3}, {"health": None}, {"builtin": "x"}, {"builtin": 5}, {"builtin": None}, {"builtin": {"risks": "x"}}, {"builtin": {"risks": None}},
                     {"builtin": {"risks": {"hidden": "yes", "outline": "Z"}}}, {"health": {"shown": 1, "own_row": "no"}}, {"order": "risks"},
                     {"order": ["nope", 3]}, {"bespoke": "x"}, {"bespoke": [None, 3, "x", {"label": "no id"}, {"id": 4}]}):
            with self.subTest(body=body):
                self.assertEqual(read(body), base)

    def test_a_typed_tile_may_not_take_a_built_in_name(self):
        self.assertEqual(read({"bespoke": [{"id": "risks", "label": "x"}, B1]})["bespoke"], [B1])

    def test_the_order_drops_unknown_and_repeated_names_and_appends_the_missing_ones(self):
        self.assertEqual(read({"bespoke": [B1], "order": ["risks", "gone", "risks", "bud"]})["order"], ["risks", "bud", "health", "overdue", "decisions"])
        self.assertEqual(read({"order": "decisions"})["order"], ["health", "overdue", "risks", "decisions"])


class WithChange(unittest.TestCase):
    def apply(self, body, change):
        return run_node("G.withChange(G.readBody({body: %s}), %s)" % (json.dumps(json.dumps(body)), json.dumps(change)))

    def test_hide_and_show_a_counting_tile_and_health(self):
        self.assertTrue(self.apply({}, {"hide": ["risks", True]})["builtin"]["risks"]["hidden"])
        self.assertFalse(self.apply({"builtin": {"risks": {"hidden": True}}}, {"hide": ["risks", False]})["builtin"]["risks"]["hidden"])
        self.assertFalse(self.apply({}, {"hide": ["health", True]})["health"]["shown"])
        self.assertTrue(self.apply({"health": {"shown": False}}, {"hide": ["health", False]})["health"]["shown"])

    def test_a_hide_touches_only_its_own_tile(self):
        got = self.apply({}, {"hide": ["risks", True]})
        self.assertEqual((got["builtin"]["overdue"]["hidden"], got["builtin"]["decisions"]["hidden"], got["health"]["shown"]), (False, False, True))

    def test_an_outline_and_an_order(self):
        self.assertEqual(self.apply({}, {"outline": ["overdue", "R"]})["builtin"]["overdue"]["outline"], "R")
        self.assertEqual(self.apply({"builtin": {"overdue": {"outline": "R"}}}, {"outline": ["overdue", ""]})["builtin"]["overdue"]["outline"], "")
        self.assertEqual(self.apply({}, {"order": ["risks", "health", "overdue", "decisions"]})["order"], ["risks", "health", "overdue", "decisions"])

    def test_the_old_body_is_not_touched(self):
        self.assertEqual(run_node("(function(){ const u = G.readBody({body: '{}'}); G.withChange(u, {hide: ['risks', true], order: ['risks']}); return [u.builtin.risks.hidden, u.order]; })()"),
                         [False, ["health", "overdue", "risks", "decisions"]])


class CompactFields(unittest.TestCase):
    def c(self, change):
        return run_node("G.compact(G.withChange(G.readBody({body: '{}'}), %s))" % json.dumps(change))

    def test_a_hidden_health_is_stored_and_a_shown_one_is_not(self):
        self.assertEqual(self.c({"hide": ["health", True]}), {"v": 1, "health": {"shown": False}})
        self.assertEqual(self.c({"hide": ["health", False]}), {"v": 1})

    def test_a_hidden_counting_tile_and_an_outline_are_stored_and_nothing_else_is(self):
        self.assertEqual(self.c({"hide": ["risks", True]}), {"v": 1, "builtin": {"risks": {"hidden": True}}})
        self.assertEqual(self.c({"outline": ["overdue", "A"]}), {"v": 1, "builtin": {"overdue": {"outline": "A"}}})

    def test_the_own_row_flag_is_stored_when_set(self):
        self.assertEqual(run_node("G.compact(G.readBody({body: '{\"health\": {\"own_row\": true}}'}))"), {"v": 1, "health": {"own_row": True}})

    def test_the_health_tile_has_no_detail_line(self):
        self.assertEqual(health_tile({"health": "On track"})["detail"], "")


class Moved(unittest.TestCase):
    def mv(self, order, key, before, drawn):
        return run_node("G.moved(%s, %s, %s, %s)" % (json.dumps(order), json.dumps(key), json.dumps(before), json.dumps(drawn)))

    def test_before_a_tile(self):
        self.assertEqual(self.mv(["a", "b", "c", "d"], "d", "b", ["a", "b", "c", "d"]), ["a", "d", "b", "c"])
        self.assertEqual(self.mv(["a", "b", "c", "d"], "a", "c", ["a", "b", "c", "d"]), ["b", "a", "c", "d"])

    def test_to_the_end_goes_after_the_last_drawn_tile(self):
        self.assertEqual(self.mv(["a", "b", "c", "d"], "a", None, ["a", "b", "c", "d"]), ["b", "c", "d", "a"])
        self.assertEqual(self.mv(["a", "h", "b", "c"], "a", None, ["a", "b", "c"]), ["h", "b", "c", "a"])
        self.assertEqual(self.mv(["a", "b", "h", "c"], "c", None, ["a", "b", "c"]), ["a", "b", "c", "h"])
        self.assertEqual(self.mv(["a", "b", "c", "h"], "a", None, ["a", "b", "c"]), ["b", "c", "a", "h"])


class BuiltinTiles(unittest.TestCase):
    def tiles(self, body, project=None):
        return run_node("G.builtinTiles(G.readBody({body: %s}), [], '2030-01-15', %s)" % (json.dumps(json.dumps(body)), json.dumps(project)))

    def test_order_hidden_outline_and_colour_follow_the_body(self):
        got = self.tiles({"order": ["risks", "health"], "health": {"shown": False}, "builtin": {"risks": {"hidden": True, "outline": "R"}}},
                         {"health": "On track"})
        self.assertEqual([t["key"] for t in got], ["risks", "health", "overdue", "decisions"])
        risks, health = got[0], got[1]
        self.assertEqual((risks["hidden"], risks["outline"], risks["rag"], risks["auto"]), (True, "R", "r", "g"))
        self.assertEqual((health["hidden"], health["outline"], health["rag"], health["auto"]), (True, "", "g", "g"))
        self.assertEqual((got[2]["hidden"], got[2]["outline"]), (False, ""))

    def test_the_words_of_a_hand_set_colour_and_of_health(self):
        got = self.tiles({"builtin": {"risks": {"outline": "R"}}}, {"health": "On track"})
        self.assertEqual(got[2]["word"], "High")
        self.assertEqual(got[3]["word"], "On track")
        self.assertEqual(got[0]["word"], "")


if __name__ == "__main__":
    unittest.main()
