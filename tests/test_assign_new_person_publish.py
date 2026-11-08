"""Row 986: a person added from the Assign to picker is not published beyond what the owner field already publishes (the owner's
NAME on a client-visible item; never the email, the person's id, the owner_id link, or the person of a hidden item).
Run: python3 dev/run_tests.py test_assign_new_person_publish
Red until the build: the add is made through the real change route with `new_person`, which is an unknown key today."""
import json
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
import _publish_fixture as fx
from clark import changes, publish
from clark.store import open_store

PLANTED = "zq.planted.newperson@leak-check.example"
NOTE_NAME = "Quin Plantedname"


class NewPersonNotPublished(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        db = fx.build_db(Path(self.tmp.name) / "clark.db", fx.load())
        self.store = open_store(db, onedrive_roots=[])
        self.addCleanup(self.store.close)
        self.change = changes.make_change(db, [], "Demo User")

    def add(self, ref, name, email=None, kind="actions"):
        person = {"name": name, **({"email": email} if email else {})}
        status, body = self.change({"project": "PUB", "kind": kind, "op": "update", "id": ref, "changes": {"owner": name},
                                    "new_person": person, "place": "cell"})
        self.assertEqual((status, body.get("message")), (200, None), body)

    def test_the_publish_whitelist_names_no_person_column(self):
        """Pin (green before and after): PUBLISH_FIELDS holds no people table, owner_id or new_person. Mutation: add 'owner_id'."""
        self.assertNotIn("people", publish.PUBLISH_FIELDS)
        for table, fields in publish.PUBLISH_FIELDS.items():
            for bad in ("owner_id", "new_person", "email", "needs_details"):
                self.assertNotIn(bad, fields, table)

    def test_the_email_the_id_and_the_link_are_in_nothing_the_publish_reads_or_writes(self):
        """Fixture: a new person with a planted email assigned to a published action. Mutation: copy owner_id or email into inputs."""
        self.add("PUB-A-001", NOTE_NAME, PLANTED)
        pid = self.store.con.execute("SELECT id FROM people WHERE name = ?", (NOTE_NAME,)).fetchone()[0]
        inputs = publish.read_inputs(self.store, "PUB", "2026-10-28")
        shown = json.dumps(publish.select(inputs), ensure_ascii=False)
        for text in (json.dumps(inputs, ensure_ascii=False, default=str), shown):
            for leak in (PLANTED, PLANTED.upper(), "owner_id", f'"{pid}"'):
                self.assertNotIn(leak.upper() if leak == PLANTED.upper() else leak, text.upper() if leak == PLANTED.upper() else text)
        out = Path(self.tmp.name) / "out"
        out.mkdir()
        result = publish.publish(self.store, "PUB", out, now="2026-10-28", branding=tempfile.mkdtemp(prefix="clark-no-brand-"), by_user="Demo User")
        body = Path(result["path"]).read_text(encoding="utf-8")
        for leak in (PLANTED, "owner_id", pid):
            self.assertNotIn(leak, body)
        self.assertIn(NOTE_NAME, body, "the owner NAME is published, as the owner field already is")
        self.assertNotIn(PLANTED, "".join(str(tuple(r)) for r in self.store.con.execute("SELECT * FROM publications")))

    def test_a_person_added_to_a_hidden_item_is_in_no_published_file(self):
        """Fixture: the action's eye is off (client_visible 0). The person's name appears nowhere in the file. Mutation: publish
        the people list or the names the picker knows."""
        with self.store.step("dashboard", "Demo User") as st:
            st.update("actions", "PUB-A-001", {"client_visible": 0})
        self.add("PUB-A-001", NOTE_NAME, PLANTED)
        out = Path(self.tmp.name) / "out2"
        out.mkdir()
        result = publish.publish(self.store, "PUB", out, now="2026-10-28", branding=tempfile.mkdtemp(prefix="clark-no-brand-"), by_user="Demo User")
        body = Path(result["path"]).read_text(encoding="utf-8")
        self.assertNotIn(NOTE_NAME, body)
        self.assertNotIn(PLANTED, body)

    def test_a_person_added_and_then_undone_leaves_no_trace_in_the_file(self):
        """Undo removes the person; nothing of them remains in the published copy. Mutation: leave the name in an item."""
        self.add("PUB-A-001", NOTE_NAME)
        undo = changes.make_undo(self.store.path, [], "Demo User")
        step = self.store.con.execute("SELECT max(apply_id) FROM applies").fetchone()[0]
        self.assertEqual(undo({"project": "PUB", "apply_id": step})[0], 200)
        out = Path(self.tmp.name) / "out3"
        out.mkdir()
        result = publish.publish(self.store, "PUB", out, now="2026-10-28", branding=tempfile.mkdtemp(prefix="clark-no-brand-"), by_user="Demo User")
        self.assertNotIn(NOTE_NAME, Path(result["path"]).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
