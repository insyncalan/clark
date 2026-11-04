"""#97: the eye on a work item (Show to the client, Hide from the client): `client_visible` is changed on an action, a RAID item and
a decision exactly as on a use case. The same 0-or-1 words, one step, one Undo, a history line, and a hidden item leaves the
published file. All rows are fictional.

Run: python3 dev/run_tests.py test_changes_item_eye
"""
import sqlite3
import unittest

from _demo import USER, DemoStore
from clark import changes, history, publish
from clark.publish import select


class Eye(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)
        self.a = self.demo.action(workstream="Build", owner="Sara Khan")
        with self.s.step("dashboard", USER) as st:
            self.r = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier slips", "impact": "High",
                                        "likelihood": "Medium", "raised": "2026-10-01", "source": "demo"})
            self.d = st.create("decisions", {"project": "ABC", "decision": "Use the new tool", "status": "Pending",
                                             "needed_by": "2030-01-05", "source": "demo"})
        self.refs = {"actions": self.a, "raid": self.r, "decisions": self.d}

    def eye(self, kind, value, **more):
        return self.change({"project": "ABC", "kind": kind, "op": "update", "id": self.refs[kind], "changes": {"client_visible": value},
                            "place": "menu", **more})

    def flag(self, kind):
        return self.s.read(kind, ref=self.refs[kind])["client_visible"]

    def count(self):
        con = sqlite3.connect(str(self.s.path))
        try:
            return con.execute("SELECT count(*) FROM change_log").fetchone()[0]
        finally:
            con.close()

    def test_each_kind_hides_and_shows_with_one_undo_and_a_reply_the_page_can_draw(self):
        for kind in self.refs:
            with self.subTest(kind=kind):
                self.assertEqual(self.flag(kind), 1)
                status, body = self.eye(kind, 0)
                self.assertEqual((status, body.get("message")), (200, None), body)
                self.assertEqual((self.flag(kind), body["undoable"], body["item"]["client_visible"]), (0, True, 0))
                status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
                self.assertEqual((status, undone["ok"]), (200, True), undone)
                self.assertEqual(self.flag(kind), 1)
                self.assertIn("shown to the client again", undone["words"])
                self.assertIn(self.refs[kind], undone["words"])      # a work item is called by its id
                status, _ = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
                self.assertEqual(status, 409)

    def test_showing_again_and_a_change_that_changes_nothing(self):
        for kind in self.refs:
            self.eye(kind, 0)
            status, _ = self.eye(kind, 1)
            self.assertEqual((status, self.flag(kind)), (200, 1))
            status, same = self.eye(kind, 1)
            self.assertEqual((status, same["undoable"]), (200, False))      # nothing changed: no step, so no Undo

    def test_a_bad_value_is_refused_in_the_use_cases_words_and_nothing_is_written(self):
        before = self.count()
        for kind in self.refs:
            for bad in (True, False, 2, -1, "1", "yes", None, 1.0, [1], {"a": 1}, ""):
                with self.subTest(kind=kind, bad=bad):
                    status, body = self.eye(kind, bad)
                    self.assertEqual((status, body["ok"], body["message"]), (400, False, changes.FLAG_WORDS))
                    self.assertEqual(self.flag(kind), 1)
        self.assertEqual(self.count(), before)

    def test_the_eye_goes_in_one_step_with_other_fields_and_one_undo_takes_both_back(self):
        status, body = self.change({"project": "ABC", "kind": "actions", "op": "update", "id": self.a,
                                    "changes": {"client_visible": 0, "owner": "Dana Hart"}})
        self.assertEqual(status, 200, body)
        self.assertEqual(len({r["via"] for r in self.s.step_rows(body["apply_id"])}), 1)
        self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        row = self.s.read("actions", ref=self.a)
        self.assertEqual((row["client_visible"], row["owner"]), (1, "Sara Khan"))

    def test_another_projects_item_and_a_missing_one_are_refused(self):
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Other Programme", "health": "On track"})
            other = st.create("actions", {"project": "XYZ", "description": "Theirs", "raised": "2026-10-01", "source": "demo"})
        before = self.count()
        for ref in (other, "ABC-A-999"):
            status, body = self.change({"project": "ABC", "kind": "actions", "op": "update", "id": ref, "changes": {"client_visible": 0}})
            self.assertEqual((status, body["ok"], body["message"]), (400, False, changes.ITEM_NOT_MINE))
        self.assertEqual((self.s.read("actions", ref=other)["client_visible"], self.count()), (1, before))

    def test_history_says_who_where_and_from_to_and_the_undo_too(self):
        status, body = self.eye("actions", 0)
        self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        events = history.history(self.s.con, self.a)
        made = [e for e in events if e["field"] == "client_visible" and not e["is_undo"]][0]
        self.assertEqual((made["by_user"], made["place"], made["before"], made["after"]), (USER, "menu", "1", "0"))
        back = [e for e in events if e["is_undo"]][0]
        self.assertEqual((back["before"], back["after"], back["undoes"]), ("0", "1", made["event_id"]))
        self.assertEqual(history.field_name("actions", "client_visible"), "Shown to the client")

    def test_a_hidden_item_leaves_the_published_file_and_showing_it_puts_it_back(self):
        def published():
            out = select({"data": self.s.data_for("ABC"), "hidden": [], "sections": [], "label_rules": [], "as_at": "2026-10-20"})["data"]
            return {k: {r["id"] for r in out[k]} for k in ("actions", "raid", "decisions")}
        shown = published()
        for kind in self.refs:
            self.assertIn(self.refs[kind], shown[kind], kind)
        steps = {kind: self.eye(kind, 0)[1]["apply_id"] for kind in self.refs}
        hidden = published()
        for kind in self.refs:
            self.assertNotIn(self.refs[kind], hidden[kind], kind)
        for kind in self.refs:
            self.undo({"project": "ABC", "apply_id": steps[kind]})
        self.assertEqual(published(), shown)

    def test_a_new_row_may_be_hidden_from_the_start_and_only_with_0_or_1(self):
        """#97: Duplicate of a hidden item creates its copy hidden, in the same step (one Undo)."""
        for kind, vals in (("actions", {"description": "Copy of a"}), ("raid", {"type": "Risk", "description": "Copy of r"}),
                           ("decisions", {"decision": "Copy of d"})):
            for eye in (0, 1):
                r = self.change({"project": "ABC", "kind": kind, "op": "new", "values": {**vals, "client_visible": eye}, "place": "menu"})
                self.assertEqual(r[0], 200, r)
                self.assertEqual(self.s.read(kind, ref=r[1]["ref"])["client_visible"], eye, (kind, eye))
            bad = self.change({"project": "ABC", "kind": kind, "op": "new", "values": {**vals, "client_visible": True}, "place": "menu"})
            self.assertNotEqual(bad[0], 200, "True is not 0 or 1")
            self.assertNotEqual(self.change({"project": "ABC", "kind": kind, "op": "new", "values": {**vals, "client_visible": "0"}, "place": "menu"})[0], 200)


class Duplicate(unittest.TestCase):
    """#488: Duplicate sends the item's id (`copy_of`) and the copy carries the item's labels and its hiding from the report, in the
    same step with one Undo. A copy of a Sensitive (or default-excluded) item stays out of the published file."""
    KINDS = {"actions": ("description", {}), "raid": ("description", {"type": "Risk", "impact": "High", "likelihood": "Low"}),
             "decisions": ("decision", {})}

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)
        with self.s.step("dashboard", USER) as st:
            st.create("labels", {"name": "Embargoed", "default_choice": "exclude"})

    def make(self, kind, title):
        field, extra = self.KINDS[kind]
        base = {"project": "ABC", "source": "demo", field: title, **extra}
        if kind == "decisions":
            base["status"] = "Pending"
        else:
            base["raised"] = "2026-10-01"
        with self.s.step("dashboard", USER) as st:
            return st.create(kind, base)

    def label(self, item, name):
        with self.s.step("dashboard", USER) as st:
            st.create("item_labels", {"item_id": item, "label": name})

    def hide(self, item):
        with self.s.step("dashboard", USER) as st:
            st.create("report_hidden", {"project": "ABC", "item_id": item})

    def labels(self, item):
        return [r["label"] for r in self.s.read("item_labels") if r["item_id"] == item]

    def hidden(self, item):
        return self.s.read("report_hidden", ref=f"ABC|{item}") is not None

    def dup(self, kind, ref):
        field, extra = self.KINDS[kind]
        values = {field: "Copy of " + self.s.read(kind, ref=ref)[field], **extra}
        return self.change({"project": "ABC", "kind": kind, "op": "new", "values": values, "copy_of": ref, "place": "menu"})

    def published(self):
        return publish.build(self.s, "ABC", now="2026-10-29")["body"].decode("utf-8")

    def test_a_copy_of_a_sensitive_or_default_excluded_item_stays_out_of_the_published_report(self):
        for kind in self.KINDS:
            for name in ("Sensitive", "Embargoed"):
                with self.subTest(kind=kind, label=name):
                    token = f"ZQ{kind}{name}SRC"
                    src = self.make(kind, token)
                    self.label(src, name)
                    status, body = self.dup(kind, src)
                    self.assertEqual(status, 200, body)
                    self.assertEqual(self.s.read(kind, ref=body["ref"])["client_visible"], 1)
                    self.assertEqual(self.labels(body["ref"]), [name])
                    self.assertNotIn(token, self.published(), "neither the item nor its copy reaches the client")

    def test_a_copy_of_a_report_hidden_item_stays_hidden(self):
        for kind in self.KINDS:
            with self.subTest(kind=kind):
                token = f"ZQ{kind}HIDDENSRC"
                src = self.make(kind, token)
                self.hide(src)
                status, body = self.dup(kind, src)
                self.assertEqual(status, 200, body)
                self.assertTrue(self.hidden(body["ref"]))
                self.assertNotIn(token, self.published(), "the copy's title holds the item's title")

    def test_a_plain_copy_is_published_and_has_no_labels_or_hiding(self):
        for kind in self.KINDS:
            with self.subTest(kind=kind):
                token = f"ZQ{kind}PLAINSRC"
                src = self.make(kind, token)
                status, body = self.dup(kind, src)
                self.assertEqual(status, 200, body)
                self.assertEqual((self.labels(body["ref"]), self.hidden(body["ref"])), ([], False))
                self.assertIn(token + " (copy)", self.published())

    def test_the_labels_and_the_hiding_go_in_one_step_and_one_undo_takes_all_back(self):
        src = self.make("actions", "ZQONESTEP")
        self.label(src, "Sensitive")
        self.hide(src)
        status, body = self.dup("actions", src)
        self.assertEqual(status, 200, body)
        copy = body["ref"]
        self.assertEqual((self.labels(copy), self.hidden(copy)), (["Sensitive"], True))
        status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual((status, undone["ok"]), (200, True), undone)
        self.assertEqual((self.s.read("actions", ref=copy), self.labels(copy), self.hidden(copy)), (None, [], False))

    def set_eye(self, kind, ref, eye):
        with self.s.step("dashboard", USER) as st:
            st.update(kind, ref, {"client_visible": eye})

    def test_a_copy_keeps_the_items_eye_whether_or_not_the_request_carries_it(self):
        """#424: a client-visible source gives a client-visible copy, a hidden one a hidden copy; one Undo removes it all."""
        for kind in self.KINDS:
            for eye in (1, 0):
                for sent in (False, True):
                    with self.subTest(kind=kind, eye=eye, sent=sent):
                        src = self.make(kind, f"ZQEYE{kind}{eye}{sent}")
                        self.set_eye(kind, src, eye)
                        self.label(src, "Sensitive")
                        field, extra = self.KINDS[kind]
                        values = {field: "Copy of x", **extra, **({"client_visible": 1 - eye} if sent else {})}
                        status, body = self.change({"project": "ABC", "kind": kind, "op": "new", "values": values, "copy_of": src, "place": "menu"})
                        self.assertEqual(status, 200, body)
                        copy = body["ref"]
                        self.assertEqual(self.s.read(kind, ref=copy)["client_visible"], eye)
                        status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
                        self.assertEqual((status, undone["ok"]), (200, True), undone)
                        self.assertEqual((self.s.read(kind, ref=copy), self.labels(copy)), (None, []))
                        self.assertEqual(self.s.read(kind, ref=src)["client_visible"], eye)

    def test_copy_of_must_be_an_active_item_of_this_project_of_the_same_kind(self):
        src = self.make("actions", "ZQBAD")
        other = self.make("raid", "ZQBADR")
        arch = self.make("actions", "ZQARCH")
        with self.s.step("dashboard", USER) as st:
            st.archive("actions", arch)
        before = len(self.s.read("actions"))
        for bad in ("ABC-A-999", other, arch, "XYZ-A-001", 7, ["x"], ""):
            with self.subTest(copy_of=bad):
                status, body = self.change({"project": "ABC", "kind": "actions", "op": "new", "values": {"description": "x"}, "copy_of": bad, "place": "menu"})
                self.assertNotEqual(status, 200, body)
        self.assertEqual(len(self.s.read("actions")), before, "a refusal writes nothing")
        status, body = self.change({"project": "ABC", "kind": "milestones", "op": "new", "values": {"name": "m"}, "copy_of": src, "place": "menu"})
        self.assertNotEqual(status, 200, body)

    def test_a_copy_takes_every_field_from_the_stored_item_and_none_from_the_request(self):
        """#442: as the prototype (system/prototype/peek.js, Duplicate): the item again, with " (copy)" on its title and its source
        "Duplicated from" the item. Status, latest update, use case and the rest are the stored item's; what the request sends is not used."""
        with self.s.step("dashboard", USER) as st:
            st.create("use_cases", {"project": "ABC", "ref": "UC9", "title": "Payroll", "status": "On track", "source": "demo"})
        uc = [u["id"] for u in self.s.read("use_cases") if u["ref"] == "UC9"][0]
        own = {"actions": {"status": "Delayed", "latest_update": "ZQ waiting on the supplier", "priority": "High", "owner": "Ada Quill",
                           "due_date": "2026-11-20", "client_message": "ZQ for the client"},
               "raid": {"status": "Open", "impact": "High", "likelihood": "High", "owner": "Ada Quill", "response_action": "ZQ ring them",
                        "due_date": "2026-11-21", "type": "Issue"},
               "decisions": {"status": "Made", "date": "2026-10-02", "made_by": "Ada Quill", "needed_by": "2026-10-01", "reasoning": "ZQ cheaper",
                             "options": "ZQ a or b", "revisit": "ZQ in spring"}}
        sent = {"actions": {"description": "ZQ sent", "owner": "Someone Else", "priority": "Low", "latest_update": "ZQ sent update"},
                "raid": {"type": "Risk", "description": "ZQ sent", "owner": "Someone Else", "impact": "Low"},
                "decisions": {"decision": "ZQ sent", "made_by": "Someone Else", "status": "Pending"}}
        for kind, fields in own.items():
            with self.subTest(kind=kind):
                title = self.KINDS[kind][0]
                src = self.make(kind, f"ZQFULL{kind}")
                with self.s.step("dashboard", USER) as st:
                    st.update(kind, src, {**fields, "use_case": uc})
                was = self.s.read(kind, ref=src)
                status, body = self.change({"project": "ABC", "kind": kind, "op": "new", "values": sent[kind], "copy_of": src, "place": "menu"})
                self.assertEqual(status, 200, body)
                copy = self.s.read(kind, ref=body["ref"])
                self.assertEqual(copy[title], f"ZQFULL{kind} (copy)")
                self.assertEqual(copy["source"], "Duplicated from " + src)
                self.assertEqual(copy["use_case"], uc)
                for f in (*fields, *changes.COPIED[kind]):
                    self.assertEqual(copy[f], was[f], (kind, f))
                if kind == "raid":
                    self.assertEqual(copy["priority"], was["priority"], "worked out again from the copied impact and likelihood")
                self.assertNotEqual(copy["id"], src)
                self.assertFalse(self.hidden(body["ref"]), "a shown item's copy with a latest update or reasoning stays shown, as the item is")

    def test_a_forged_labels_value_on_duplicate_is_refused_and_writes_nothing(self):
        """Item 612: the copy's labels are the stored item's only. A request that sends labels (to drop Sensitive, or to add one), or
        a label's reason, in the values or beside them, is refused, and nothing is written."""
        src = self.make("actions", "ZQFORGED")
        self.label(src, "Sensitive")
        actions, labels = len(self.s.read("actions")), len(self.s.read("item_labels"))
        forged = [{"labels": v} for v in ([], ["Urgent"], "Urgent", "", None)] + [{"label_reason": "x"}, {"label_suggested": 1}]
        for extra in forged:
            for where in ("values", "request"):
                with self.subTest(extra=extra, where=where):
                    values = {"description": "x", **(extra if where == "values" else {})}
                    req = {"project": "ABC", "kind": "actions", "op": "new", "values": values, "copy_of": src, "place": "menu",
                           **(extra if where == "request" else {})}
                    status, body = self.change(req)
                    self.assertNotEqual(status, 200, body)
        self.assertEqual((len(self.s.read("actions")), len(self.s.read("item_labels"))), (actions, labels), "a refusal writes nothing")
        self.assertEqual(self.labels(src), ["Sensitive"])

    def test_a_long_title_still_ends_with_copy_and_fits(self):
        src = self.make("actions", "x" * 200)
        status, body = self.change({"project": "ABC", "kind": "actions", "op": "new", "values": {"description": "x (copy)"}, "copy_of": src, "place": "menu"})
        self.assertEqual(status, 200, body)
        got = self.s.read("actions", ref=body["ref"])["description"]
        self.assertEqual((len(got), got.endswith(" (copy)")), (200, True))

    def test_an_eye_off_or_sensitive_items_copy_with_an_update_stays_out_of_the_published_file(self):
        """#442: the copy now carries the item's latest update and reasoning too: neither reaches the client file through a copy."""
        for kind, extra in (("actions", {"latest_update": "ZQUPDSECRET"}), ("decisions", {"reasoning": "ZQUPDSECRET"})):
            for how in ("eye", "Sensitive", "hidden"):
                with self.subTest(kind=kind, how=how):
                    token = f"ZQ{kind}{how}COPYSRC"
                    src = self.make(kind, token)
                    with self.s.step("dashboard", USER) as st:
                        st.update(kind, src, extra)
                    if how == "eye":
                        self.set_eye(kind, src, 0)
                    elif how == "hidden":
                        self.hide(src)
                    else:
                        self.label(src, "Sensitive")
                    status, body = self.dup(kind, src)
                    self.assertEqual(status, 200, body)
                    page = self.published()
                    self.assertNotIn(token, page, "neither the item nor its copy reaches the client")
                    self.assertNotIn("ZQUPDSECRET", page)

    def test_a_new_row_may_not_send_the_eye_as_null(self):
        status, body = self.change({"project": "ABC", "kind": "actions", "op": "new", "values": {"description": "x", "client_visible": None}, "place": "menu"})
        self.assertNotEqual(status, 200, body)


if __name__ == "__main__":
    unittest.main()
