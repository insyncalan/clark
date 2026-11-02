"""#251: the page's freshness read keeps an item's first and latest-by-a-person events and reads only the rows added since.

Run: python3 dev/run_tests.py test_review_cache
data_for used to read every history row of the project's items on every call. history.review_events gives freshness the same
answer from two events per item, kept between calls (history.ReviewCache) and brought up to date from the new log rows only.
"""
import unittest
from datetime import datetime, timezone
from unittest import mock

from _demo import USER, DemoStore
import _paths  # noqa: F401
from clark import freshness as fresh, history, store as store_module

TODAY = "2026-10-29"
NOW = [datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)]


def answers(con, ids, many=None, cache=None):
    """{id: freshness answer} from the full events (many) or from review_events."""
    events = history.history_many(con, ids) if many else history.review_events(con, ids, cache)
    row = {"status": "Open"}
    return {i: fresh.freshness(row, events[i], TODAY) for i in ids}


class Kept(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        for target, value in (("clark.store.clock", lambda: NOW[0]), ("clark.store.today", lambda: TODAY)):
            patcher = mock.patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        NOW[0] = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
        self.store = self.demo.store

    def at(self, day):
        NOW[0] = datetime(2026, 10, day, 9, 0, tzinfo=timezone.utc)

    def con(self):
        return store_module.connect(self.store.path, readonly=True)

    def same(self, ids, cache=None):
        con = self.con()
        try:
            self.assertEqual(answers(con, ids, cache=cache), answers(con, ids, many=True))
        finally:
            con.close()

    def busy_history(self):
        """Actions with people's changes, an ask-clark change, an import, undone steps, labels and links at both ends."""
        d, s = self.demo, self.store
        a1 = d.action()
        self.at(2)
        a2 = d.action(description="Second")
        self.at(3)
        a3 = d.action(description="Third")
        d.update("actions", a1, {"owner": "Sam Example"})
        self.at(4)
        third = d.update("actions", a1, {"due_date": "2030-01-31"})
        self.at(5)
        s.undo(third, USER)
        self.at(6)
        with s.step("assistant", USER, actor="clark", src_ref="mail 1") as st:
            st.update("actions", a3, {"owner": "Alex Example"})
        self.at(7)
        with s.step("excel", USER) as st:
            st.update("actions", a2, {"priority": "High"})
        self.at(8)
        with s.step("dashboard", USER) as st:
            r = st.create("raid", {"project": "ABC", "type": "Risk", "description": "A risk", "raised": "2026-10-01", "source": "demo"})
            st.update("actions", a2, {"labels": "Sensitive"})
            st.create("links", {"from_item": a1, "to_item": a2, "source": "demo"})
            st.create("links", {"from_item": a3, "to_item": a1, "source": "demo"})
        return [a1, a2, a3, r, "ABC-A-999"]

    def test_the_answer_is_the_one_the_full_history_gives(self):
        ids = self.busy_history()
        self.same(ids)
        con = self.con()
        try:
            got = history.review_events(con, ids)
        finally:
            con.close()
        for i in ids:
            self.assertLessEqual(len(got[i]), 4, "an item keeps its two events, and a link's other end adds few")
        self.assertEqual(got["ABC-A-999"], [])

    def test_a_kept_item_follows_every_later_step(self):
        ids = self.busy_history()
        cache = history.ReviewCache()
        self.same(ids, cache)
        a1, a2, a3, r = ids[:4]
        later = (lambda: self.demo.update("actions", a3, {"priority": "Low"}),
                 lambda: self.demo.update("raid", r, {"description": "A sharper risk"}),
                 lambda: self.store.undo(self.demo.last_step(), USER),
                 lambda: self.demo.update("actions", a1, {"status": "Delayed"}))
        for day, change in zip((10, 12, 14, 20), later):
            self.at(day)
            change()
            with self.subTest(day=day):
                self.same(ids, cache)
        self.assertEqual(answers(self.con(), [a1], cache=cache)[a1]["last_reviewed"], "2026-10-20")

    def test_a_kept_item_follows_a_batch_undo_an_import_and_a_link(self):
        ids = self.busy_history()
        cache = history.ReviewCache()
        self.same(ids, cache)
        a1, a2, a3 = ids[:3]

        def batch_undo():
            self.at(9)
            first = self.demo.update("actions", a1, {"priority": "Low"})
            second = self.demo.update("actions", a2, {"priority": "Low"})
            self.at(10)
            self.assertTrue(self.store.undo_many([first, second], USER)["reversed"])

        def import_rows():
            with self.store.step("excel", USER, src_ref="Excel import: plan.xlsx") as st:
                st.update("actions", a3, {"owner": "Pat Example"})
                st.create("actions", {"project": "ABC", "description": "Imported", "raised": "2026-10-01", "source": "demo"})

        def link_two():
            with self.store.step("dashboard", USER) as st:
                st.create("links", {"from_item": a3, "to_item": ids[3], "source": "demo"})

        for day, change in ((9, batch_undo), (12, import_rows), (14, link_two)):
            if day != 9:
                self.at(day)
            change()
            with self.subTest(step=change.__name__):
                self.same(ids, cache)
        con = self.con()
        try:
            self.assertEqual(answers(con, [a1], cache=cache)[a1]["last_reviewed"], "2026-10-09")
            self.assertEqual(answers(con, [a3], cache=cache)[a3]["last_reviewed"], "2026-10-14")
        finally:
            con.close()

    def test_the_cache_stops_at_its_bound_and_still_answers_right(self):
        ids = self.busy_history()[:4]
        cache = history.ReviewCache(limit=2)
        for asked in (ids[:1], ids[1:2], ids[2:3], ids[3:4], ids[:2], ids[:1]):
            self.same(asked, cache)
            self.assertLessEqual(len(cache.events), 2)
        self.same(ids[2:4], cache)
        self.assertEqual(sorted(cache.events), sorted(ids[2:4]), "the items kept longest ago went, the ones asked for stayed")
        self.same(ids, cache)
        self.assertEqual(len(cache.events), 0, "one call that asks for more than the bound is answered and keeps nothing")
        self.at(25)
        self.demo.update("actions", ids[0], {"priority": "Low"})
        self.same(ids[:2], cache)
        self.assertEqual(len(cache.events), 2)

    def test_the_default_bound_is_large_and_a_store_keeps_the_default(self):
        self.assertGreaterEqual(history.ReviewCache().limit, 10000)
        self.store.data_for("ABC")
        self.assertEqual(self.store.review_cache.limit, history.ReviewCache.LIMIT)

    def test_an_item_asked_for_later_is_read_whole_then_kept(self):
        ids = self.busy_history()
        cache = history.ReviewCache()
        self.same(ids[:2], cache)
        self.at(21)
        self.demo.update("actions", ids[2], {"priority": "Low"})
        self.same(ids, cache)

    def test_a_log_that_lost_rows_is_read_again(self):
        ids = self.busy_history()
        cache = history.ReviewCache()
        self.same(ids, cache)
        con = self.store.con
        con.execute("DELETE FROM item_events WHERE item_id = ?", (ids[0],))
        con.execute("DELETE FROM change_log WHERE item_id = ?", (ids[0],))
        con.commit()
        self.same(ids, cache)

    def test_an_item_whose_first_stamp_cannot_be_read_is_read_whole(self):
        ids = self.busy_history()
        con = self.store.con
        con.execute("UPDATE item_events SET at = '  not a time' WHERE item_id = ? AND event_id = "
                    "(SELECT min(event_id) FROM item_events WHERE item_id = ?)", (ids[0], ids[0]))
        con.commit()
        cache = history.ReviewCache()
        self.same(ids, cache)
        self.same(ids, cache)

    def test_a_dashboard_event_that_is_an_undo_is_not_a_review(self):
        self.at(2)
        first, second = self.demo.action(), self.demo.action(description="Second")
        self.at(9)
        self.demo.update("actions", first, {"priority": "High"})
        self.demo.update("actions", second, {"priority": "High"})
        con = self.store.con
        newest = ("SELECT max(c.rowid) FROM change_log c JOIN item_events e ON e.change = c.rowid "
                  "WHERE c.item_id = ? AND c.field = 'priority'")
        con.execute("UPDATE item_events SET undoes = 1 WHERE change = (%s)" % newest, (first,))
        con.execute("UPDATE change_log SET via = 'revert:1' WHERE rowid = (%s)" % newest, (second,))
        con.commit()
        for kept in (None, history.ReviewCache()):
            self.same([first, second], kept)
        con = self.con()
        try:
            self.assertEqual(answers(con, [first, second])[first]["last_reviewed"], "2026-10-02")
        finally:
            con.close()

    def test_an_empty_log_then_a_first_row(self):
        con = self.con()
        try:
            self.assertEqual(history.review_events(con, [], history.ReviewCache()), {})
        finally:
            con.close()
        cache = history.ReviewCache()
        self.same(["ABC-A-001"], cache)
        a = self.demo.action()
        self.same([a], cache)


class Cheap(unittest.TestCase):
    """The cost no longer follows the log: counted in the database's own steps, which do not vary with the machine's load."""

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.ids = [self.demo.action(description=f"Action {n}") for n in range(3)]
        con = self.demo.store.con
        step = self.demo.last_step()
        base = con.execute("SELECT max(rowid) FROM change_log").fetchone()[0]
        rows = 6000
        con.execute("BEGIN")                  # one transaction: this connection commits every statement unless told otherwise
        con.executemany("INSERT INTO change_log (apply_id, tbl, item_id, field, old_value, new_value, op, via) "
                        "VALUES (?, 'actions', ?, 'status', '1', '2', 'update', 'dashboard')",
                        [(step, "XYZ-A-%03d" % (n % 50)) for n in range(rows)])
        con.executemany("INSERT INTO item_events (at, apply_id, item_id, change, kind, route, place, actor) "
                        "VALUES ('2026-10-01 09:00:00', ?, ?, ?, 'change', 'dashboard', 'cell', 'you')",
                        [(step, "XYZ-A-%03d" % (n % 50), base + n + 1) for n in range(rows)])
        con.execute("COMMIT")

    def steps(self):
        """The database's virtual-machine steps (in hundreds) one review_events call takes, with the cache the store keeps."""
        cache = self.demo.store.review_cache or history.ReviewCache()
        self.demo.store.review_cache = cache
        count = [0]
        con = store_module.connect(self.demo.store.path, readonly=True)
        con.set_progress_handler(lambda: count.__setitem__(0, count[0] + 1) or 0, 100)
        try:
            history.review_events(con, self.ids, cache)
        finally:
            con.close()
        return count[0]

    def test_a_call_after_the_first_does_not_read_the_log(self):
        first = self.steps()
        again = self.steps()
        self.assertGreater(first, 100, "the first call reads the large log")
        self.assertLess(again * 20, first)

    def test_a_call_after_an_edit_reads_only_what_the_edit_added(self):
        first = self.steps()
        self.demo.update("actions", self.ids[0], {"priority": "High"})
        self.assertLess(self.steps() * 20, first)

    def test_data_for_fills_the_stores_cache(self):
        self.assertIsNone(self.demo.store.review_cache)
        self.demo.store.data_for("ABC")
        self.assertIsNotNone(self.demo.store.review_cache)
        self.assertEqual(len(self.demo.store.review_cache.events), len(self.ids))


if __name__ == "__main__":
    unittest.main()
