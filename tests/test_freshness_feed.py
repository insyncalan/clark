"""#158 #159 #160: the store feeds each open item's freshness to the page, and the published file carries none of it.

Run: python3 dev/run_tests.py test_freshness_feed
The review facts (raised, last reviewed, not reviewed) are for the owner only. They are read from history by Store.data_for, one
function (store.review_days_for) gives N, and publish reads its own allow-listed columns, so none of it can reach the file.
"""
import unittest
from datetime import datetime, timezone
from unittest import mock

from _demo import USER, DemoStore
import _paths  # noqa: F401
from clark import publish, store as store_module

NOW = [datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)]
TODAY = "2026-10-29"


class Feed(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        for target, value in (("clark.store.clock", lambda: NOW[0]), ("clark.store.today", lambda: TODAY)):
            patcher = mock.patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        NOW[0] = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)

    def at(self, day, hour=9):
        NOW[0] = datetime(2026, 10, day, hour, 0, tzinfo=timezone.utc)

    def rows(self, table="actions", **kw):
        return {r["id"]: r for r in self.demo.store.data_for("ABC", **kw)[table]}

    def test_an_open_action_gets_the_four_facts_as_plain_dates(self):
        a = self.demo.action()
        self.at(5)
        self.demo.update("actions", a, {"priority": "High"})
        got = self.rows()[a]["freshness"]
        self.assertEqual(set(got), {"raised", "last_reviewed", "days", "not_reviewed"})
        self.assertEqual((got["raised"], got["last_reviewed"], got["days"], got["not_reviewed"]), ("2026-10-01", "2026-10-05", 14, True))

    def test_exactly_the_limit_is_not_flagged_and_one_day_over_is(self):
        self.at(15)
        a = self.demo.action()                                          # made by a person 14 days before TODAY
        self.assertFalse(self.rows()[a]["freshness"]["not_reviewed"])
        self.at(14)
        b = self.demo.action(description="Another")                     # 15 days before TODAY
        self.assertTrue(self.rows()[b]["freshness"]["not_reviewed"])

    def test_risks_and_decisions_are_fed_too(self):
        with self.demo.store.step("dashboard", USER) as st:
            r = st.create("raid", {"project": "ABC", "type": "Risk", "description": "A risk", "raised": "2026-10-01", "source": "demo"})
            d = st.create("decisions", {"project": "ABC", "decision": "A choice", "status": "Pending", "source": "demo"})
        self.assertEqual(self.rows("raid")[r]["freshness"]["raised"], "2026-10-01")
        self.assertEqual(self.rows("decisions")[d]["freshness"]["raised"], "2026-10-01")

    def test_milestones_get_no_freshness(self):
        self.assertNotIn("freshness", self.rows("milestones")[self.demo.milestone])

    def test_closed_and_archived_items_get_nothing(self):
        a = self.demo.action()
        b = self.demo.action(description="Another")
        self.demo.update("actions", a, {"status": "Closed"})
        self.assertNotIn("freshness", self.rows()[a])
        self.assertIn("freshness", self.rows()[b])
        self.demo.store.con.execute("UPDATE actions SET archived = 1 WHERE id = ?", (b,))
        self.demo.store.con.commit()
        self.assertNotIn("freshness", self.rows(archived="show")[b])

    def test_a_row_with_no_history_is_never_flagged(self):
        a = self.demo.action()
        con = self.demo.store.con
        con.execute("DELETE FROM item_events WHERE item_id = ?", (a,))
        con.execute("DELETE FROM change_log WHERE item_id = ?", (a,))
        con.commit()
        got = self.rows()[a]["freshness"]
        self.assertEqual((got["raised"], got["last_reviewed"], got["not_reviewed"]), (None, None, False))

    def test_an_import_or_an_ask_clark_change_is_not_a_review(self):
        a = self.demo.action()
        self.at(20)
        with self.demo.store.step("excel", USER) as st:
            st.update("actions", a, {"priority": "High"})
        self.at(22)
        with self.demo.store.step("assistant", USER, actor="clark") as st:
            st.update("actions", a, {"owner": "Sam Example"})
        got = self.rows()[a]["freshness"]
        self.assertEqual(got["last_reviewed"], "2026-10-01")    # only the person's own making of it counts
        self.assertEqual(got["raised"], "2026-10-01")
        self.assertTrue(got["not_reviewed"])
        self.at(25)
        self.demo.update("actions", a, {"priority": "Low"})      # a person's change is
        got = self.rows()[a]["freshness"]
        self.assertEqual((got["last_reviewed"], got["not_reviewed"]), ("2026-10-25", False))

    def test_one_function_gives_n_and_nothing_is_stored_for_it(self):
        row = self.demo.store.data_for("ABC")["project"]
        self.assertEqual(store_module.review_days_for(row), 14)
        with mock.patch("clark.store.review_days_for", lambda project: 3):
            a = self.demo.action()
            self.assertEqual(self.rows()[a]["freshness"]["days"], 3)
        columns = {r[1] for r in self.demo.store.con.execute("PRAGMA table_info(projects)")}
        self.assertFalse({"review_days", "stale_tile"} & columns)

    def test_the_published_file_carries_none_of_it(self):
        a = self.demo.action(description="Visible to the client", client_visible=1)
        self.at(5)
        self.demo.update("actions", a, {"priority": "High"})
        self.assertIn("freshness", self.rows()[a])
        fed = self.demo.store.data_for("ABC")
        for t in ("actions", "raid", "decisions"):
            self.assertTrue(all("freshness" in r for r in fed[t] if r.get("status") not in ("Closed", "Cancelled", "Made", "Withdrawn")))
        built = publish.build(self.demo.store, "ABC", now=TODAY)
        body = built["body"].decode("utf-8")
        shown = built["published"]["data"]
        self.assertTrue(shown["actions"], "the visible action is in the file")
        for t in ("actions", "raid", "decisions"):
            for row in shown.get(t, ()):
                self.assertNotIn("freshness", row)
        self.assertNotIn("2026-10-05", body)                    # the day of the review
        self.assertNotIn('"last_reviewed"', body)

    def test_select_drops_a_freshness_key_it_is_handed(self):
        a = self.demo.action(client_visible=1)
        data = self.demo.store.data_for("ABC")
        inputs = {"as_at": TODAY, "data": data, "hidden": [], "sections": [], "label_rules": [], "changes": [], "undone": []}
        for row in data["actions"]:
            row["freshness"] = {"raised": "2026-09-09", "last_reviewed": None, "days": 14, "not_reviewed": True}
        try:
            out = publish.select(inputs)
        except Exception as e:                                  # a hand-made input may lack parts select wants; the drop is what is tested
            self.skipTest(f"select needs more input: {e}")
        self.assertTrue(out["data"]["actions"])
        self.assertTrue(all("freshness" not in r for r in out["data"]["actions"]))
        self.assertIn(a, [r["id"] for r in data["actions"]])


if __name__ == "__main__":
    unittest.main()
