"""#160: the "Not reviewed after (days)" setting: its check, and the chip, the filter value and the optional tile following it.

Run: python3 dev/run_tests.py test_review_days
The Python check (freshness.check_days) and the page's (reviewSetting.js parseReviewDays) must refuse and accept the same values in
the same words. The page's pure modules run in node when it is on the machine (as test_freshness does).
"""
import json
import shutil
import subprocess
import unittest

from _paths import ROOT, SRC  # noqa: F401

from clark import freshness as f  # noqa: E402

PAGE = ROOT / "src" / "clark" / "page" / "src"
GOOD = [14, "14", " 7 ", 1, 3650, "30"]
BAD = [0, "0", -3, "-3", "", "  ", "abc", "1.5", 1.5, "1e3", "14 days", None, True, False, 3651, "99999", "٣", []]


class Check(unittest.TestCase):
    def test_a_whole_number_of_days_is_taken(self):
        for v in GOOD:
            with self.subTest(v=v):
                self.assertEqual(f.check_days(v), {"ok": True, "days": int(str(v).strip())})

    def test_zero_and_anything_that_is_not_a_number_is_refused_in_plain_words(self):
        for v in BAD:
            with self.subTest(v=v):
                r = f.check_days(v)
                self.assertFalse(r["ok"])
                self.assertEqual(r["message"], f.DAYS_WORDS)
        self.assertIn("The setting stays as it was.", f.DAYS_WORDS)

    def test_the_default_is_fourteen(self):
        self.assertEqual(f.DEFAULT_DAYS, 14)

    def test_the_rule_follows_the_number_it_is_given(self):
        row, ev = {"status": "Open"}, [{"at": "2026-10-01 09:00:00.000", "actor": "you", "route": "dashboard", "event_id": 1}]
        self.assertFalse(f.not_reviewed(row, ev, "2026-10-15"))             # 14 days: not yet
        self.assertTrue(f.not_reviewed(row, ev, "2026-10-15", days=13))
        self.assertTrue(f.not_reviewed(row, ev, "2026-10-16"))
        self.assertFalse(f.not_reviewed(row, ev, "2026-10-16", days=30))


class Page(unittest.TestCase):
    def run_js(self, body):
        node = shutil.which("node")
        if not node:
            self.skipTest("no node")
        mods = {"F": "filters.js", "R": "reviewSetting.js", "G": "glanceTiles.js", "W": "workItems.js"}
        head = "".join(f'import * as {k} from "{(PAGE / v).as_uri()}"; ' for k, v in mods.items())
        done = subprocess.run([node, "--input-type=module", "-e", head + body], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_the_page_and_the_server_say_the_same(self):
        out = self.run_js(f"console.log(JSON.stringify({json.dumps(GOOD + BAD)}.map((v) => R.parseReviewDays(v))));")
        want = [f.check_days(v) for v in GOOD + BAD]
        # a JSON null, a list and a bool are not text or numbers on the page either; the two agree on every value
        self.assertEqual(out, want)

    def test_the_chip_the_filter_value_and_the_tile_follow_one_number(self):
        out = self.run_js('''const T = "2026-10-28";
          const rows = [{id: "a", kind: "action", status: "Open", raised: "2026-10-20"}, {id: "b", kind: "action", status: "Open", raised: "2026-10-01"},
                        {id: "c", kind: "action", status: "Closed", raised: "2026-01-01"}, {id: "d", kind: "action", status: "Open"}];
          const s = F.toggleValue(F.initial(), "reviewed", "stale"), seen = [];
          const look = () => seen.push([F.getReviewDays(), F.labelOf("reviewed", "stale"), F.options(rows, "reviewed", s, T)[0].label,
            F.applyFilters(rows, s, T).map((r) => r.id), G.notReviewedTile(rows, T, F.getReviewDays())]);
          look(); F.setReviewDays(5); look(); F.setReviewDays(1); look(); F.setReviewDays(0); look(); F.setReviewDays("x"); look();
          console.log(JSON.stringify(seen));''')
        self.assertEqual([o[0] for o in out], [14, 5, 1, 14, 14])
        self.assertEqual([o[1] for o in out], ["Not reviewed in 14 days", "Not reviewed in 5 days", "Not reviewed in 1 day",
                                               "Not reviewed in 14 days", "Not reviewed in 14 days"])
        self.assertEqual([o[2] for o in out], [o[1] for o in out])
        self.assertEqual([o[3] for o in out], [["b"], ["a", "b"], ["a", "b"], ["b"], ["b"]])
        for o in out:                                   # the tile counts exactly the rows the list shows
            self.assertEqual(o[4]["value"], len(o[3]))
            self.assertEqual(o[4]["key"], "stale")
            self.assertEqual(o[4]["rag"], "a" if o[3] else "g")
        self.assertEqual(out[1][4]["detail"], "in 5 days")
        self.assertEqual(out[2][4]["detail"], "in 1 day")

    def test_the_tile_opens_the_list_it_counts_and_a_project_without_a_number_uses_fourteen(self):
        out = self.run_js('''const t = G.notReviewedTile([], "2026-10-28", 14);
          console.log(JSON.stringify([F.encode(t.filter), t.value, t.rag, R.daysOf({}), R.daysOf({review_days: 30}), R.daysOf({review_days: 0}),
            R.daysOf(null), R.daysOf({review_days: "abc"}), G.tileWord("stale", "a")]));''')
        self.assertEqual(out, ["reviewed:stale", 0, "g", 14, 30, 14, 14, 14, "Needs a look"])


if __name__ == "__main__":
    unittest.main()
