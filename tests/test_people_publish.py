"""#115: a person's email and owner_id never reach a published report. A distinctive email is planted on a person who owns a
published action, the project is published, and the address and the link column are searched for in everything the publish
reads and writes. Fictional names. Run: python3 -m unittest test_people_publish"""
import json
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
import _publish_fixture as fx
from clark import publish
from clark.store import open_store

PLANTED = "zq.planted.person@leak-check.example"


class Planted(unittest.TestCase):
    def test_the_email_and_the_owner_link_are_in_no_publish_table_and_not_in_the_file(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = fx.build_db(Path(tmp.name) / "clark.db", fx.load())
        store = open_store(db, onedrive_roots=[])
        self.addCleanup(store.close)
        with store.step("dashboard", "Demo User") as st:
            pid = st.add_person(name="Quin Planted", email=PLANTED, source="test")
        with store.step("dashboard", "Demo User") as st:
            st.update("actions", "PUB-A-001", {"owner": "Quin Planted", "owner_id": pid})
        self.assertEqual(store.con.execute("SELECT owner_id FROM actions WHERE id = 'PUB-A-001'").fetchone()[0], pid)
        inputs = publish.read_inputs(store, "PUB", "2026-10-28")
        shown = json.dumps(publish.select(inputs), ensure_ascii=False)
        for text in (json.dumps(inputs, ensure_ascii=False, default=str), shown):
            self.assertNotIn(PLANTED, text)
            self.assertNotIn(PLANTED.upper(), text.upper())
            self.assertNotIn("owner_id", text)
        out = Path(tmp.name) / "out"
        out.mkdir()
        result = publish.publish(store, "PUB", out, now="2026-10-28", branding=tempfile.mkdtemp(prefix="clark-no-brand-"), by_user="Demo User")
        body = Path(result["path"]).read_text(encoding="utf-8")
        self.assertNotIn(PLANTED, body)
        self.assertNotIn("owner_id", body)
        self.assertNotIn("Quin Planted", "".join(str(tuple(r)) for r in store.con.execute("SELECT * FROM publications")))


if __name__ == "__main__":
    unittest.main()
