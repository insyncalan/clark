"""#349: the dashboard "as at" a date, rebuilt from the change history (src/clark/as_at.py and GET /api/as-at), against a fixed history.

Run: python3 dev/run_tests.py test_as_at
Every step is made at a fixed time (store.clock is replaced), in UTC, so the days never move with the machine's zone. The data is
made up. The page's side is tests/test_as_at_page.py.
"""
import ast
import hashlib
import http.client
import json
import threading
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
from _demo import USER
from clark import as_at, server as sv, store as clark_store
from clark.store import open_store

UTC = timezone.utc
TOKEN = {sv.TOKEN_HEADER: sv.TOKEN}


class Server:
    """A real LocalServer on a free port in a thread, with only data_for and the as_at seam."""

    def __init__(self, case, data_for, seam):
        self.httpd = sv.LocalServer((sv.HOST, 0), data_for=data_for, as_at=seam)
        self.httpd.handle_error = lambda *a: None
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        case.addCleanup(self.close)

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def ask(self, path, headers=None):
        conn = http.client.HTTPConnection(sv.HOST, self.httpd.server_port, timeout=20)
        try:
            conn.request("GET", path, None, {"Host": f"127.0.0.1:{self.httpd.server_port}", **(headers or {})})
            r = conn.getresponse()
            return r.status, r.read()
        finally:
            conn.close()


def at(text):
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)


class History(unittest.TestCase):
    """Project ABC made on 05-10-2026; one action reworded, a risk added, a label taken off and an item hidden by the eye on
    12-10-2026; the action closed and the week ending moved on 20-10-2026."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.now = at("2026-10-05 09:00")
        patch = mock.patch.object(clark_store, "clock", lambda: self.now)
        patch.start()
        self.addCleanup(patch.stop)
        self.store = open_store(self.dir / "clark.db", onedrive_roots=[])
        self.addCleanup(self.store.close)
        s = self.store
        with s.step("dashboard", USER) as st:
            st.create("projects", {"code": "ABC", "name": "Example Programme", "health": "On track", "week_ending": "2026-10-09"})
            self.a = st.create("actions", {"project": "ABC", "description": "Old words", "raised": "2026-10-05", "source": "demo",
                                           "due_date": "2026-10-30"})
            st.create("item_labels", {"item_id": self.a, "label": "Sensitive"})
        self.now = at("2026-10-12 10:00")
        with s.step("dashboard", USER) as st:
            st.update("actions", self.a, {"description": "New words"})
            self.r = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Key person leaves", "raised": "2026-10-12",
                                        "source": "demo", "impact": "High", "likelihood": "High"})
            st.cancel("item_labels", f"{self.a}|Sensitive")
            st.create("report_hidden", {"project": "ABC", "item_id": self.r})
        self.now = at("2026-10-20 11:00")
        with s.step("dashboard", USER) as st:
            st.update("actions", self.a, {"status": "Closed"})
            st.update("projects", "ABC", {"week_ending": "2026-10-23"})
        self.now = at("2026-11-03 08:00")
        self.seam = as_at.AsAt(s.path, today=lambda: "2026-11-03", tz=UTC)

    def read(self, day, code="ABC"):
        return self.seam.read(code, day)

    def action(self, data):
        (row,) = [r for r in data["actions"] if r["id"] == self.a]
        return row

    def test_before_any_change_the_first_words_the_label_and_no_risk(self):
        status, body = self.read("2026-10-06")
        self.assertEqual(status, 200, body)
        d = body["data"]
        self.assertEqual(body["as_at"], "2026-10-06")
        self.assertEqual(self.action(d)["description"], "Old words")
        self.assertEqual(self.action(d)["status"], "Open")
        self.assertEqual(d["raid"], [])
        self.assertEqual(d["labels"], {self.a: ["Sensitive"]})
        self.assertEqual(d["report_hidden"], [])
        self.assertEqual(d["project"]["week_ending"], "2026-10-09")

    def test_after_the_second_step_the_new_words_the_risk_hidden_and_the_label_gone(self):
        status, body = self.read("2026-10-12")
        self.assertEqual(status, 200, body)
        d = body["data"]
        self.assertEqual(self.action(d)["description"], "New words")
        self.assertEqual(self.action(d)["status"], "Open")
        self.assertEqual([r["id"] for r in d["raid"]], [self.r])
        self.assertEqual(d["report_hidden"], [self.r], "the eye's hidden rows are as they were, so View leaves the risk out")
        self.assertEqual(d["labels"], {})
        self.assertEqual(d["project"]["week_ending"], "2026-10-09")

    def test_today_is_the_same_as_the_live_data(self):
        status, body = self.read("2026-11-03")
        self.assertEqual(status, 200, body)
        live = self.store.data_for("ABC")
        self.assertEqual(json.dumps(body["data"], sort_keys=True), json.dumps(live, sort_keys=True))
        self.assertEqual(self.action(body["data"])["status"], "Closed")
        self.assertEqual(body["data"]["project"]["week_ending"], "2026-10-23")

    def test_freshness_is_counted_on_that_day(self):
        _, early = self.read("2026-10-06")
        _, late = self.read("2026-10-19")
        self.assertIn("freshness", self.action(early["data"]))
        self.assertFalse(self.action(early["data"])["freshness"]["not_reviewed"])
        self.assertEqual(self.action(late["data"])["freshness"]["last_reviewed"], "2026-10-12")

    def test_it_never_writes_clark_db(self):
        self.store.con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        path = self.store.path
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        rows = self.store.con.execute("SELECT count(*) FROM change_log").fetchone()[0]
        for day in ("2026-10-04", "2026-10-06", "2026-10-12", "2026-10-20"):
            self.read(day)
        self.assertEqual(self.store.con.execute("SELECT count(*) FROM change_log").fetchone()[0], rows)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
        self.assertEqual(self.store.read("actions", "ABC")[0]["description"], "New words")
        self.assertEqual(list(self.dir.iterdir()) and sorted(p.name for p in self.dir.iterdir() if p.suffix == ".db"), ["clark.db"])

    def test_refusals_in_plain_words(self):
        self.assertEqual(self.read("2026-10-04")[0], 404)
        self.assertEqual(self.read("2026-10-04")[1]["message"], "This project did not exist yet on 04-10-2026. Pick a later day.")
        self.assertEqual(self.read("2026-11-04")[1]["code"], "future")
        self.assertEqual(self.read("2026-02-30")[1]["code"], "bad_date")
        self.assertEqual(self.read("14-10-2026")[1]["code"], "bad_date")
        self.assertEqual(self.read("2026-10-06", code="ZZZ")[0], 404)
        self.assertEqual(self.read("2026-10-06", code="abc")[1]["code"], "bad_project_code")
        for message in as_at.MESSAGES.values():
            for jargon in ("change_log", "sql", "database", "json", "token"):
                self.assertNotIn(jargon, message.lower())

    def test_cutoff_is_the_end_of_the_day_in_the_zone(self):
        self.assertEqual(as_at.cutoff("2026-10-12", UTC), "2026-10-13 00:00:00")
        from datetime import timedelta
        self.assertEqual(as_at.cutoff("2026-10-12", timezone(timedelta(hours=4))), "2026-10-12 20:00:00")

    def test_the_route(self):
        running = Server(self, self.store.data_for, self.seam)
        status, body = running.ask("/api/as-at?project=ABC&date=2026-10-06", TOKEN)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["data"]["actions"][0]["description"], "Old words")
        for q in ("project=ABC", "project=ABC&date=2026-10-06&x=1", "project=ABC&date=2026-10-06&date=2026-10-07"):
            self.assertEqual(running.ask("/api/as-at?" + q, TOKEN)[0], 400, q)
        self.assertEqual(running.ask("/api/as-at?project=abc&date=2026-10-06", TOKEN)[0], 400)
        status, body = running.ask("/api/as-at?project=ABC&date=2026-10-06")
        self.assertGreaterEqual(status, 400, "without the token nothing is read")
        self.assertNotIn(b"Old words", body)
        running.httpd.as_at = None
        self.assertEqual(running.ask("/api/as-at?project=ABC&date=2026-10-06", TOKEN)[0], 404)

    def test_the_copy_is_rewound_and_clark_db_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "copy.db"
            clark_store.rewound_copy(self.store.path, copy, "2026-10-12 00:00:00")
            con = clark_store.connect(copy, readonly=True)
            try:
                self.assertEqual(con.execute("SELECT description FROM actions").fetchone()[0], "Old words")
                self.assertEqual(con.execute("SELECT count(*) FROM raid").fetchone()[0], 0)
                self.assertEqual(con.execute("SELECT max(at) FROM change_log").fetchone()[0][:10], "2026-10-05")
            finally:
                con.close()
        self.assertEqual(self.store.con.execute("SELECT count(*) FROM raid").fetchone()[0], 1)

    def test_no_publishing_module_reads_it(self):
        src = Path(as_at.__file__).parent
        for name in ("publish.py", "publish_flow.py", "publish_pdf.py", "docx_build.py", "to_client.py", "word_route.py"):
            tree = ast.parse((src / name).read_text(encoding="utf-8"))
            names = {a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
            names |= {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
            self.assertFalse({"as_at", "clark.as_at"} & names, name)


if __name__ == "__main__":
    unittest.main()
