"""Row 1263 hostile cases for the count logic: figures.js storedCount/bodyOf/countOf (run in node) and figures4.py checker/publisher."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC
from _tpl_figures import typed
from clark import section_bodies, store as store_module
from clark.section_kinds import base, figures4

PAGE_SRC = SRC / "clark" / "page" / "src"
_JS = {}


def js(expr):
    """Evaluate `expr` (uses storedCount, bodyOf, countOf) over templates/figures.js bundled for node; returns the JSON result."""
    if "file" not in _JS:
        sys.path.insert(0, str(ROOT / "dev" / "tools"))
        import esbuild
        tmp = Path(tempfile.mkdtemp())
        entry = tmp / "e.js"
        entry.write_text(f'export * from "{PAGE_SRC}/templates/figures.js";\n', encoding="utf-8")
        out = tmp / "f.cjs"
        done = esbuild.run(["--bundle", "--format=cjs", "--platform=node", "--charset=utf8", "--tsconfig-raw={}", f"--outfile={out}", str(entry)],
                           cwd=str(tmp), capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        _JS["file"] = out
    code = f'const m=require({json.dumps(str(_JS["file"]))});const {{storedCount,bodyOf,countOf}}=m;console.log(JSON.stringify({expr}))'
    r = subprocess.run(["node", "-e", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def sc(t, body):
    return js(f"storedCount({{type:{json.dumps(t)},body:{json.dumps(body)}}})")


class JsCount(unittest.TestCase):
    def test_storedCount_only_whole_3_or_4_on_figures4(self):
        for count, want in ((3, 3), (4, 4), (5, 0), (0, 0), (-3, 0), (3.5, 0), ("3", 0), ("4", 0), (None, 0), (True, 0), ([3], 0), ({"a": 3}, 0)):
            with self.subTest(count=count):
                self.assertEqual(sc("figures4", json.dumps({"v": 1, "count": count, "figures": []})), want)
        self.assertEqual(sc("figures4", '{"v":1,"count":3.0,"figures":[]}'), 3, "3.0 is 3 in JSON text (the checker refuses it server-side)")

    def test_storedCount_non_figures4_and_bad_bodies(self):
        for t in ("figures3", "text", "raid", None):
            with self.subTest(t=t):
                self.assertEqual(sc(t, '{"v":1,"count":4,"figures":[]}'), 0)
        for b in ("", "not json", "null", "3", "[]", '"x"', "{", None):
            with self.subTest(b=b):
                self.assertEqual(sc("figures4", b), 0)

    def test_published_section_without_body_reads_section_count(self):
        self.assertEqual(js('storedCount({type:"figures4",count:3,figures:[]})'), 3)
        self.assertEqual(js('storedCount({type:"figures4",figures:[]})'), 0)
        self.assertEqual(js('storedCount({type:"figures4",count:"3"})'), 0)
        self.assertEqual(js('storedCount({type:"figures3",count:4})'), 0)

    def test_countOf_defaults(self):
        self.assertEqual(js('countOf({type:"figures4"})'), 4)
        self.assertEqual(js('countOf({type:"figures3"})'), 3)
        self.assertEqual(js('countOf({type:"figures4",body:"{\\"v\\":1,\\"count\\":3}"})'), 3)
        self.assertEqual(js('countOf({type:"figures3",body:"{\\"v\\":1,\\"count\\":4}"})'), 3)
        self.assertEqual(js('countOf({type:"figures4",body:"{\\"v\\":1,\\"count\\":9}"})'), 4)

    def test_bodyOf_count_and_empty(self):
        empty = '{mode:"typed",label:"",value:"",detail:"",asof:""}'
        full = '{mode:"typed",label:"A",value:"1",detail:"",asof:""}'
        self.assertEqual(js(f"bodyOf([{empty},{empty}])"), "")
        self.assertEqual(js(f"bodyOf([{empty}],3)"), '{"v":1,"count":3,"figures":[]}', "empty slots with a count keep the count")
        self.assertEqual(js(f"bodyOf([{empty}],0)"), "")
        self.assertEqual(json.loads(js(f"bodyOf([{full},{empty},{full}],3)"))["figures"].__len__(), 3)
        self.assertEqual(json.loads(js(f"bodyOf([{full}],4)"))["count"], 4)
        self.assertNotIn("count", json.loads(js(f"bodyOf([{full}])")))
        self.assertNotIn("count", json.loads(js(f"bodyOf([{full}],undefined)")))

    def test_bodyOf_output_is_accepted_by_the_checker(self):
        empty = '{mode:"typed",label:"",value:"",detail:"",asof:""}'
        for c in (3, 4):
            body = js(f"bodyOf([{empty}],{c})")
            self.assertEqual(json.loads(section_bodies.check("figures4", body, store_module.BODY_RULES))["count"], c)


class Checker(unittest.TestCase):
    def check(self, t, v):
        return json.loads(section_bodies.check(t, json.dumps(v), store_module.BODY_RULES))

    def test_bad_counts_refused(self):
        for c in ("3", "", 0, 5, -3, -4, 3.5, 4.0, None, True, False, [3], {"n": 3}, 2**40):
            with self.subTest(count=c), self.assertRaises(base.Bad):
                self.check("figures4", {"v": 1, "count": c, "figures": []})

    def test_count_on_other_types_refused(self):
        for t in ("figures3", "raid3", "checklist"):
            with self.subTest(t=t):
                with self.assertRaises(base.Bad):
                    self.check(t, {"v": 1, "count": 3, "figures": []})

    def test_empty_slots_with_count_and_no_figures_key(self):
        self.assertEqual(self.check("figures4", {"v": 1, "count": 3, "figures": [typed()]})["count"], 3)
        self.assertEqual(self.check("figures4", {"v": 1, "count": 3}), {"v": 1, "count": 3, "figures": []})

    def test_fourth_kept_while_count_3_and_fifth_refused(self):
        rows = [typed(label=f"L{i}", value=str(i)) for i in range(4)]
        got = self.check("figures4", {"v": 1, "count": 3, "figures": rows})
        self.assertEqual([f["label"] for f in got["figures"]], ["L0", "L1", "L2", "L3"])
        with self.assertRaises(base.Bad):
            self.check("figures4", {"v": 1, "count": 3, "figures": rows + [typed(label="L4", value="4")]})

    def test_extra_key_refused(self):
        with self.assertRaises(base.Bad):
            self.check("figures4", {"v": 1, "count": 3, "figures": [], "counts": 3})


class Publisher(unittest.TestCase):
    ctx = base.Context({}, "2030-01-15")
    rows = [typed(label=f"L{i}", value=str(i)) for i in range(4)]

    def pub(self, t, v):
        return section_bodies.published(t, v, self.ctx)

    def test_untrusted_counts_not_published(self):
        for c in ("3", 0, 5, -3, True, None, [3]):
            with self.subTest(count=c):
                got = self.pub("figures4", {"v": 1, "count": c, "figures": self.rows})
                self.assertNotIn("count", got)
                self.assertEqual(len(got["figures"]), 4)

    def test_float_count_in_unchecked_value(self):
        # the publish path checks first (3.0 is refused), so this is publisher-only: it must not crash
        got = self.pub("figures4", {"v": 1, "count": 3.0, "figures": self.rows})
        self.assertNotIn("count", got)

    def test_count_3_cuts_to_three_count_4_keeps_four_none_is_four(self):
        self.assertEqual(len(self.pub("figures4", {"v": 1, "count": 3, "figures": self.rows})["figures"]), 3)
        self.assertEqual(len(self.pub("figures4", {"v": 1, "count": 4, "figures": self.rows})["figures"]), 4)
        self.assertEqual(len(self.pub("figures4", {"v": 1, "figures": self.rows})["figures"]), 4)

    def test_empty_slots_with_count_publish_nothing(self):
        self.assertIsNone(self.pub("figures4", {"v": 1, "count": 3, "figures": []}))
        self.assertIsNone(self.pub("figures4", {"v": 1, "count": 3, "figures": [typed(label="", value="", detail="", asof="")] * 3}))

    def test_label_without_value_waits_and_is_not_published_with_count(self):
        got = self.pub("figures4", {"v": 1, "count": 3, "figures": [typed(label="A", value=""), self.rows[1]]})
        self.assertEqual([f["label"] for f in got["figures"]], ["L1"])
        self.assertEqual(got["count"], 3)

    def test_figures3_never_count(self):
        self.assertNotIn("count", self.pub("figures3", {"v": 1, "count": 3, "figures": self.rows}))

    def test_live_in_4th_dropped_when_count_3(self):
        v = {"v": 1, "count": 3, "figures": self.rows[:3] + [{"mode": "live", "metric": "risks"}]}
        self.assertEqual(len(self.pub("figures4", v)["figures"]), 3)


if __name__ == "__main__":
    unittest.main()
