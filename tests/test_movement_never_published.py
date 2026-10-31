"""#136: Movement never leaves in a published file. The planted-marker test (design-136, section D, "Client-safe pin").

Plants, on one milestone of the plant project, an internal note, a rebaseline whose reason, "agreed with" name and source are
markers, a Movement choice and a state, written through the real change route (the Movement place) and the writer. Publishes
with To client ticked, then searches the finished bytes (the page, its data block and the client-folder copy) for every marker,
the Movement phrases, the new decision and the key names the Movement reply uses. Also: no publishing module names the read,
the view or the route, NEVER_PUBLISH and PUBLISH_FIELDS are as before, and the file is byte-equal with and without a history."""
import json
import re
import unittest
from pathlib import Path

import _publish_fixture as fx
from _paths import SRC
from clark import changes, movement_view, publish
from clark import store as clark_store
from test_publish_route import DAY, USER, WANTED, Rig

INTERNAL = "ZQ-INTERNAL-NOTE-5521 supplier wants more money"
REASON = "ZQ-REASON-7710 build ran long"
WHO = "ZQ-AGREED-WITH-3302 Pat Placeholder"
SOURCE = "ZQ-SOURCE-9184 steering minutes"
HOLD_WORDS = "ZQ-HOLD-4417"
MARKERS = {"internal note": INTERNAL, "reason": REASON, "agreed with": WHO, "source": SOURCE}
PHRASES = ("Rebaselined", "Movement choice", "Undone", "Internal only", "Never moved", "Agreed date moved", "What changed",
           "Decide what to do", "Move the agreed date", "holding; agreed date unchanged", "Nothing has changed since it was first agreed")
M = "PUB-M-001"                                   # agreed 15-10-2026, client-visible, in the published file


def history_on(rig):
    """The history to hide: through the change route, in the Movement place, then the writer for the internal note."""
    change = changes.make_change(rig.db, [], USER)

    def go(fields, **more):
        status, got = change({"project": "PUB", "kind": "milestones", "op": "update", "id": M, "changes": fields,
                              "place": "movement", **more})
        assert status == 200, got
        return got
    go({"forecast_date": "2034-12-01"})
    moved = go({"baseline_date": "2035-01-31"}, rebaseline={"agreed_with": WHO, "reason": REASON, "source": SOURCE})
    go({"movement": "hold"})
    go({"state": "At risk", "state_reason": "Waiting on the vendor"})
    with rig.store.step("dashboard", USER) as st:
        st.update("milestones", M, {"internal_note": INTERNAL})
    return moved


class Planted(unittest.TestCase):
    def setUp(self):
        self.rig = Rig(self)
        self.moved = history_on(self.rig)
        status, got = self.rig.publish(to_client=True)
        self.assertEqual((status, got["ok"], got["action"]), (200, True, "done"), got)
        self.local = (self.rig.local / "chosen.html").read_bytes().decode("utf-8")
        self.client = (self.rig.client / WANTED).read_bytes().decode("utf-8")
        match = re.search(r'<script type="application/json" id="clark-data">(.*?)</script>', self.local, re.S)
        self.assertTrue(match, "the file has its data block")
        self.block = match.group(1)

    def where(self):
        return {"the page": self.local, "its data block": self.block, "the client copy": self.client}

    def test_the_copy_is_the_file(self):
        self.assertEqual(self.local, self.client)
        self.assertIn(self.block, self.client)

    def test_no_marker_in_the_page_the_data_block_or_the_client_copy_in_any_spelling(self):
        for where, text in self.where().items():
            for name, marker in MARKERS.items():
                for spelling in fx.spellings(marker):
                    self.assertNotIn(spelling, text, f"{name} ({spelling!r}) is in {where}")

    def test_no_movement_phrase_is_added_to_the_finished_bytes(self):
        """A phrase the page's own code already holds (a label for something else) is counted: the history must add none."""
        base = Rig(self)
        status, got = base.publish(to_client=True)
        self.assertEqual((status, got["ok"]), (200, True), got)
        plain = (base.local / "chosen.html").read_bytes().decode("utf-8")
        for phrase in PHRASES:
            for spelling in fx.spellings(phrase):
                self.assertEqual(self.local.count(spelling), plain.count(spelling), f"{phrase!r} ({spelling!r}) was added")
                self.assertEqual(self.client.count(spelling), plain.count(spelling), f"{phrase!r} in the client copy")
        for phrase in ("Rebaselined", "Movement choice", "What changed", "holding; agreed date unchanged"):
            self.assertNotIn(phrase, self.local, "and these are in no file at all")

    def test_the_decision_a_rebaseline_made_is_not_in_the_file(self):
        self.assertRegex(self.moved["decision"], r"^PUB-D-\d{3}$")
        decision = self.rig.store.read("decisions", ref=self.moved["decision"])
        self.assertEqual(decision["client_visible"], 0)
        for where, text in self.where().items():
            self.assertNotIn(self.moved["decision"], text, where)
            self.assertNotIn(decision["decision"], text, where)

    def test_the_movement_replys_key_names_are_not_in_the_data_block(self):
        parsed = json.loads(self.block)
        names = set()

        def walk(value):
            if isinstance(value, dict):
                names.update(value)
                for v in value.values():
                    walk(v)
            elif isinstance(value, list):
                for v in value:
                    walk(v)
        walk(parsed)
        mine = set(movement_view.ROW_KEYS) | set(movement_view.ENTRY_KEYS) | set(movement_view.SUMMARY_KEYS)
        mine |= {"by_user", "before", "after", "src_ref", "undone_by", "is_undo", "in_force", "event_id", "internal_note", "movement"}
        shared = {"state", "owner", "percent", "name", "id", "original", "forecast", "agreed", "rows", "tag", "help", "at", "text",
                  "total", "kind", "step", "why", "days", "moved", "moves", "mark", "colour", "slip", "variance", "expected",
                  "decision", "state_reason"}      # the last two are published columns of the file's own (decisions, Q4 of #39)
        self.assertEqual((names & mine) - shared, set(), "key names only the Movement read uses")

    def test_the_one_date_of_its_history_the_file_holds_is_the_original_date(self):
        parsed = json.loads(self.block)
        found = []

        def walk(value):
            if isinstance(value, dict):
                if value.get("id") == M:
                    found.append(value)
                for v in value.values():
                    walk(v)
            elif isinstance(value, list):
                for v in value:
                    walk(v)
        walk(parsed)
        self.assertTrue(found)
        row = found[0]
        self.assertNotIn("internal_note", row)
        self.assertEqual(row.get("baseline_date"), "2035-01-31")
        self.assertEqual(json.dumps(parsed).count("2026-10-15"), json.dumps(parsed).count('"original_date": "2026-10-15"'),
                         "the first agreed date appears only as original_date")

    def test_the_state_reason_is_published_only_as_the_milestones_own_text_as_ruled_on_39(self):
        # Q4 of #39: a milestone's state_reason is published (design-136's list of owner-only things named it; the code does not)
        self.assertIn("Waiting on the vendor", self.local)


class Unchanged(unittest.TestCase):
    def test_the_published_field_lists_are_as_they_were(self):
        self.assertTrue({"internal_note", "movement", "source", "reasoning", "by_user"} <= clark_store.NEVER_PUBLISH)
        for table, fields in publish.PUBLISH_FIELDS.items():
            self.assertFalse(set(fields) & {"internal_note", "movement"}, table)
            self.assertFalse(set(fields) & clark_store.NEVER_PUBLISH - {"state_reason"}, table)
        self.assertNotIn("internal_note", publish.PUBLISH_FIELDS["milestones"])
        self.assertNotIn("movement", publish.PUBLISH_FIELDS["milestones"])
        self.assertEqual(publish.PUBLISH_FIELDS["milestones"], (
            "id", "name", "description", "baseline_date", "forecast_date", "status", "sort_order", "percent_complete",
            "state_reason", "owner", "actual_date", "client_message", "workstream"))
        self.assertEqual(clark_store.NEVER_PUBLISH, frozenset({
            "internal_note", "movement", "source", "reasoning", "options", "response_action", "keywords", "aliases", "lead",
            "publish_local", "publish_client", "by_user", "device"}))

    def test_no_publishing_module_names_the_read_the_view_or_the_route(self):
        names = ("milestone_moves", "movement_view", "movement_read", "milestone_rows.movement", "/api/movement", "MOVE_FIELDS",
                 "MOVE_SQL")
        for module in ("publish.py", "publish_flow.py", "to_client.py", "excel_cover.py", "draft_email.py", "docx_build.py",
                       "excel.py", "page.py"):
            path = Path(SRC) / "clark" / module
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            for name in names:
                self.assertNotIn(name, text, f"{module} names {name}")
        text = (Path(SRC) / "clark" / "store.py").read_text(encoding="utf-8")
        start = text.index("    def publish_inputs")
        body = text[start:text.index("\n    def ", start + 10)]
        for name in names:
            self.assertNotIn(name, body, "publish_inputs")


class ByteEqual(unittest.TestCase):
    """The same visible data with a very different history gives the same bytes: nothing of the history reaches the file."""

    def publish(self, build):
        rig = Rig(self)
        build(rig)
        status, got = rig.publish(to_client=True)
        self.assertEqual((status, got["ok"]), (200, True), got)
        return (rig.local / "chosen.html").read_bytes()

    def test_a_milestone_moved_twice_and_one_never_moved_give_the_same_file(self):
        def plain(rig):
            with rig.store.step("dashboard", USER) as st:
                st.update("milestones", M, {"forecast_date": "2026-11-20"})

        def busy(rig):
            change = changes.make_change(rig.db, [], USER)
            kept = rig.store.read("milestones", ref=M)["client_message"]
            for fields in ({"forecast_date": "2026-11-05"}, {"movement": "hold"}, {"forecast_date": "2026-12-01"},
                           {"client_message": "Briefly late."}, {"client_message": kept}, {"movement": None},
                           {"forecast_date": "2026-11-20"}):
                status, got = change({"project": "PUB", "kind": "milestones", "op": "update", "id": M, "changes": fields,
                                      "place": "movement"})
                self.assertEqual(status, 200, got)
            with rig.store.step("dashboard", USER) as st:
                st.update("milestones", M, {"internal_note": INTERNAL})
            with rig.store.step("dashboard", USER) as st:
                st.update("milestones", M, {"internal_note": None})
        a, b = self.publish(plain), self.publish(busy)
        self.assertEqual(a, b)
        self.assertNotIn(INTERNAL.encode(), b)


if __name__ == "__main__":
    unittest.main()
