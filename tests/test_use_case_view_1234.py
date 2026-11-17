"""The Use case summary view settings (row 1234): n (a number or all) with Show all, scroll toggle, tracker position; one rule for Edit and published.
Run: python3 dev/run_tests.py test_use_case_view_1234
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

import sys
sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

ENTRY = ROOT / "tests" / "fixtures" / "use_case_view_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}


def run(probe):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "v.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=V", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"], cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(_BUNDLE["code"] + ";\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


class Normalize(unittest.TestCase):
    def test_empty_and_bad_values_give_the_default(self):
        d = {"n": 5, "scroll": False, "tracker": "top"}
        for raw in ("null", "undefined", "'x'", "[]", "{}"):
            self.assertEqual(run(f"V.normalizeView({raw})"), d, raw)

    def test_each_field_falls_back_alone(self):
        self.assertEqual(run("V.normalizeView({n: 0, scroll: 'yes', tracker: 'left'})"), {"n": 5, "scroll": False, "tracker": "top"})
        self.assertEqual(run("V.normalizeView({n: 2.5})")["n"], 5)
        self.assertEqual(run("V.normalizeView({n: -3})")["n"], 5)

    def test_good_values_are_kept(self):
        self.assertEqual(run("V.normalizeView({n: 8, scroll: true, tracker: 'bottom'})"), {"n": 8, "scroll": True, "tracker": "bottom"})
        self.assertEqual(run("V.normalizeView({n: 'all', tracker: 'off'})")["n"], "all")
        self.assertEqual(run("V.normalizeView({n: '7'})")["n"], 7)

    def test_stored_json_string_and_object_agree(self):
        saved = {"n": 3, "scroll": True, "tracker": "off"}
        self.assertEqual(run(f"V.normalizeView({json.dumps(json.dumps(saved))})"), saved)
        self.assertEqual(run(f"V.normalizeView({json.dumps(saved)})"), saved)
        self.assertEqual(run("V.normalizeView('{bad json')"), {"n": 5, "scroll": False, "tracker": "top"})
        self.assertEqual(run("V.normalizeView(" + json.dumps('{"n":"all","scroll":1}') + ")"), {"n": "all", "scroll": False, "tracker": "top"})

    def test_unknown_keys_are_dropped(self):
        got = run("V.normalizeView({n: 2, extra: 1, visible: 9, nested: {a: 1}})")
        self.assertEqual(got, {"n": 2, "scroll": False, "tracker": "top"})
        got = run("V.normalizeView(" + json.dumps('{"n":4,"junk":true}') + ")")
        self.assertEqual(sorted(got), ["n", "scroll", "tracker"])


class Rows(unittest.TestCase):
    def test_count_limits_and_counts_the_rest(self):
        self.assertEqual(run("V.shownRows(12, {n: 5})"), {"shown": 5, "hidden": 7})
        self.assertEqual(run("V.shownRows(3, {n: 5})"), {"shown": 3, "hidden": 0})
        self.assertEqual(run("V.shownRows(5, {n: 5})"), {"shown": 5, "hidden": 0})

    def test_show_all_and_all_draw_every_row(self):
        self.assertEqual(run("V.shownRows(12, {n: 5}, true)"), {"shown": 12, "hidden": 0})
        self.assertEqual(run("V.shownRows(12, {n: 'all'})"), {"shown": 12, "hidden": 0})

    def test_negative_or_fractional_totals_are_safe(self):
        self.assertEqual(run("V.shownRows(-4, {n: 5})"), {"shown": 0, "hidden": 0})

    def test_visible_items_keep_order(self):
        self.assertEqual(run("V.visibleItems(['a','b','c','d'], {n: 2})"), ["a", "b"])
        self.assertEqual(run("V.visibleItems(['a','b','c'], {n: 2}, true)"), ["a", "b", "c"])

    def test_show_all_control_only_when_rows_hidden_and_not_scrolling(self):
        self.assertTrue(run("V.needsShowAll(9, {n: 5})"))
        self.assertFalse(run("V.needsShowAll(9, {n: 5}, true)"))
        self.assertFalse(run("V.needsShowAll(4, {n: 5})"))
        self.assertFalse(run("V.needsShowAll(9, {n: 5, scroll: true})"))


class ScrollAndTracker(unittest.TestCase):
    def test_scroll_height_in_rows(self):
        self.assertEqual(run("V.scrollRows({n: 6, scroll: true})"), 6)
        self.assertEqual(run("V.scrollRows({n: 6, scroll: false})"), 0)
        self.assertEqual(run("V.scrollRows({n: 'all', scroll: true})"), 0)

    def test_tracker_place(self):
        self.assertEqual(run("V.trackerPlace({tracker: 'top'})"), {"above": True, "below": False, "on": True})
        self.assertEqual(run("V.trackerPlace({tracker: 'bottom'})"), {"above": False, "below": True, "on": True})
        self.assertEqual(run("V.trackerPlace({tracker: 'off'})"), {"above": False, "below": False, "on": False})
        self.assertEqual(run("V.trackerPlace({})")["above"], True)

    def test_edit_and_published_agree(self):
        saved = {"n": 3, "scroll": True, "tracker": "bottom"}
        again = run(f"V.normalizeView(JSON.parse(JSON.stringify({json.dumps(saved)})))")
        self.assertEqual(again, saved)


class ViewOf(unittest.TestCase):
    def of(self, section, from_file=False):
        return run(f"V.viewOf({json.dumps(section)}, {json.dumps(from_file)})")

    def test_live_reads_the_body_text(self):
        body = json.dumps({"n": 3, "scroll": True, "tracker": "bottom"})
        self.assertEqual(self.of({"body": body}), {"set": True, "n": 3, "scroll": True, "tracker": "bottom"})
        self.assertEqual(self.of({"body": json.dumps({"n": "all"})})["n"], "all")

    def test_a_file_reads_its_own_entry_and_ignores_the_body(self):
        entry = {"id": "s1", "title": "Use case summary", "n": 2, "tracker": "off", "body": json.dumps({"n": 9, "tracker": "bottom"})}
        self.assertEqual(self.of(entry, True), {"set": True, "n": 2, "scroll": False, "tracker": "off"})

    def test_nothing_or_nonsense_is_the_default_and_not_set(self):
        default = {"set": False, "n": 5, "scroll": False, "tracker": "top"}
        for section in (None, {}, {"body": ""}, {"body": "not json"}, {"body": "[1]"}, {"body": "3"}, {"body": None}, {"body": 7}):
            with self.subTest(section=section):
                self.assertEqual(self.of(section), default)
        for section in (None, "x", [1]):
            with self.subTest(file=section):
                self.assertEqual(self.of(section, True), default)

    def test_a_tracker_only_body_is_not_set_and_a_body_is_written_from_the_keys_given(self):
        self.assertEqual(self.of({"body": json.dumps({"tracker": "bottom"})}), {"set": False, "n": 5, "scroll": False, "tracker": "bottom"})
        self.assertEqual(json.loads(run("V.bodyOf({tracker: 'bottom'})")), {"tracker": "bottom"})
        self.assertEqual(json.loads(run("V.bodyOf({n: 3, tracker: 'bottom'})")), {"n": 3, "tracker": "bottom"})
        self.assertEqual(run("V.givenOf({body: '{\"tracker\":\"off\"}'})"), {"tracker": "off"})
        self.assertEqual(run("[V.givenOf(null), V.givenOf({body: ''}), V.givenOf({body: 'x'})]"), [{}, {}, {}])

    def test_one_bad_field_falls_back_alone(self):
        self.assertEqual(self.of({"body": json.dumps({"n": 0, "scroll": "yes", "tracker": "left"})}), {"set": True, "n": 5, "scroll": False, "tracker": "top"})

    def test_a_null_count_is_not_set(self):
        self.assertFalse(self.of({"body": json.dumps({"n": None, "tracker": "off"})})["set"])
        self.assertFalse(self.of({"n": None, "tracker": "off"}, True)["set"])
        self.assertEqual(self.of({"body": json.dumps({"n": None, "tracker": "off"})})["n"], 5)

    def test_the_body_written_holds_only_the_complete_setting(self):
        body = run('V.bodyOf({"n": 0, "scroll": "yes", "tracker": "left", "extra": 1})')
        self.assertEqual(json.loads(body), {"n": 5, "scroll": False, "tracker": "top"})
        # only the keys given are written (row 1234c); Configure gives all three once a number is chosen
        self.assertEqual(list(json.loads(run('V.bodyOf({"n": 3, "scroll": true, "tracker": "off"})'))), ["n", "scroll", "tracker"])
        self.assertEqual(list(json.loads(run('V.bodyOf({"n": 3})'))), ["n"])

    def test_a_hand_edited_null_key_is_not_given(self):
        self.assertEqual(run('V.givenOf({body: "{\\"n\\":null,\\"tracker\\":\\"bottom\\"}"})'), {"tracker": "bottom"})
        self.assertEqual(run('V.givenOf({body: "{\\"scroll\\":null}"})'), {})

    def test_the_browser_keys_are_not_read(self):
        self.assertNotIn("localStorage", (PAGE_SRC / "logic" / "useCaseView.js").read_text(encoding="utf-8"))
        self.assertNotIn("clark.uc", (PAGE_SRC / "components" / "UseCases.jsx").read_text(encoding="utf-8").replace("clark.ucAll", ""))


if __name__ == "__main__":
    unittest.main()

