"""#306: the sent record's triggers abort with 'a sent record is never changed / deleted / replaced'. Those are database words for a
person who is not meant to see them, so this pins that they never reach a screen: a trigger that fires inside the "I sent it" route
is answered by the server's own fixed 500 words (nothing from the exception), and no file the page is built from or served from
carries them. Fictional names. Run: python3 dev/run_tests.py test_sent_record_words_stay_off_page"""
import json
import sqlite3
import unittest
from datetime import date
from unittest import mock

import _paths  # noqa: F401
from _paths import SRC
from _demo import DemoStore
from clark import draft_email_feed as feed
from clark import server as sv
from clark.store import Store
from test_draft_email_route import Running

WORDS = ("a sent record is never changed", "a sent record is never deleted", "a sent record is never replaced")
FORBIDDEN = ("UPDATE email_sent SET mode = 'chase' WHERE seq = 1", "DELETE FROM email_sent WHERE seq = 1",
             "UPDATE email_sent_items SET item_id = 'X' WHERE seq = 1", "DELETE FROM email_sent_items WHERE seq = 1",
             "INSERT OR REPLACE INTO email_sent (seq, project, day, mode, by_user) VALUES (1, 'ABC', '2026-01-01', 'chase', 'x')")


class Trigger(unittest.TestCase):
    DAY = "2026-10-28"

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.a = self.demo.action(description="Share the plan", owner="Dana Hart", status="Open")
        self.seam = feed.make_sent(self.store.path, [], by_user="Sam Lee", today=date(2026, 10, 28))
        self.running = Running(draft_email_sent=self.seam)
        self.addCleanup(self.running.close)
        self.body = json.dumps({"project": "ABC", "ids": [self.a], "mode": "chase", "day": self.DAY}).encode()
        status, _, data = self.running.api("POST", "/api/draft-email/sent", self.body)        # one sent record to protect
        self.assertEqual(status, 200, data)

    def test_a_trigger_that_fires_in_the_route_answers_in_the_servers_fixed_words(self):
        for sql in FORBIDDEN:
            with self.subTest(sql=sql):
                real = Store.log_email_sent

                def breaks(store, *a, **k):
                    store.con.execute(sql)                                # the database refuses: sqlite3.IntegrityError from the trigger
                    return real(store, *a, **k)
                with mock.patch.object(Store, "log_email_sent", breaks), self.assertLogs(sv.LOG, "ERROR"):
                    status, _, data = self.running.api("POST", "/api/draft-email/sent", self.body)
                self.assertEqual(status, 500)
                reply = json.loads(data)
                self.assertEqual((reply["code"], reply["message"]), ("server_error", sv.MESSAGES["server_error"]))
                for words in WORDS:
                    self.assertNotIn(words, data.decode().lower())
        con = sqlite3.connect(self.store.path)
        try:
            self.assertEqual(con.execute("SELECT count(*) FROM email_sent").fetchone()[0], 1, "the sent record is as it was")
        finally:
            con.close()

    def test_the_trigger_words_are_in_no_file_the_page_is_built_or_served_from(self):
        triggers = {"store.py", "schema.sql"}
        for path in sorted(p for p in (SRC / "clark").rglob("*") if p.is_file() and p.suffix in (".py", ".js", ".jsx", ".html", ".css", ".json", ".sql")):
            if path.name in triggers or "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace").lower()
            for words in WORDS:
                self.assertNotIn(words, text, f"{path.relative_to(SRC)} carries a database word a person could read")


if __name__ == "__main__":
    unittest.main()
