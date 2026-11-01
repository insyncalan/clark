"""#454: the People card's Paste from Excel, the server's half: POST /api/people {op: "paste", rows} is ONE step (one Undo), goes
through the same writer and checks as an add or an edit, names the person in a refusal and writes nothing then, and a person's
email, organisation and role reach no published page. Fictional names.
Run: python3 dev/run_tests.py test_people_paste_route"""
import json
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
import _publish_fixture as fx
from _demo import USER
from clark import people as people_rules
from clark import publish
from clark import server as sv
from clark.store import open_store
from test_people_route import Base, clark_open

SAM = {"name": "Sam Rivers", "email": "Sam.Rivers@Example.com", "organisation": "Supplier", "role": "Delivery lead"}
ZED = {"name": "Zed Newman", "email": "zed@example.com", "organisation": "Client", "role": "Sponsor"}


class Paste(Base):
    def paste(self, *rows):
        return self.post({"op": "paste", "rows": list(rows)})

    def steps(self):
        s = clark_open(self.path)
        try:
            return s.con.execute("SELECT count(*) FROM applies").fetchone()[0]
        finally:
            s.close()

    def test_new_people_are_added_in_one_step_with_all_four_details(self):
        status, body = self.paste(SAM, ZED)
        self.assertEqual(status, 200, body)
        self.assertEqual((body["added"], body["updated"]), (2, 0))
        got = {p["name"]: p for p in body["people"]}
        self.assertEqual((got["Sam Rivers"]["email"], got["Sam Rivers"]["organisation"], got["Sam Rivers"]["role"]),
                         ("sam.rivers@example.com", "Supplier", "Delivery lead"))
        self.assertEqual((got["Zed Newman"]["needs_details"], got["Zed Newman"]["source"]), (0, "People list"))
        s = clark_open(self.path)
        self.addCleanup(s.close)
        self.assertEqual(s.con.execute("SELECT count(DISTINCT apply_id) FROM change_log WHERE tbl = 'people'").fetchone()[0], 1)

    def test_a_person_pasted_without_an_email_needs_details_and_an_email_later_clears_it(self):
        body = self.paste({"name": "Jo Park", "email": "", "organisation": "Client", "role": ""})[1]
        self.assertEqual(body["people"][0]["needs_details"], 1)
        body = self.paste({"name": "jo  park", "email": "jo@example.com"})[1]
        self.assertEqual((body["added"], body["updated"]), (0, 1))
        self.assertEqual((body["people"][0]["needs_details"], body["people"][0]["email"], body["people"][0]["organisation"]), (0, "jo@example.com", "Client"))

    def test_a_name_on_the_list_is_updated_not_added_and_a_blank_cell_keeps_what_is_there(self):
        self.add("Sam Rivers", email="sam@example.com", organisation="Supplier", role="Analyst")
        body = self.paste({"name": "Sam Rivers", "email": "", "organisation": "", "role": "Delivery lead"})[1]
        self.assertEqual((body["added"], body["updated"], len(body["people"])), (0, 1, 1))
        p = body["people"][0]
        self.assertEqual((p["email"], p["organisation"], p["role"]), ("sam@example.com", "Supplier", "Delivery lead"))

    def test_a_name_that_is_an_alias_updates_that_person(self):
        pid = self.add("Samuel Rivers", aliases="Sam Rivers")["id"]
        body = self.paste(SAM)[1]
        self.assertEqual((len(body["people"]), body["updated"]), (1, 1))
        self.assertEqual((body["people"][0]["id"], body["people"][0]["email"]), (pid, "sam.rivers@example.com"))

    def test_the_same_name_twice_in_one_paste_is_one_person(self):
        body = self.paste({"name": "Sam Rivers"}, {"name": "Sam Rivers", "email": "sam@example.com"})[1]
        self.assertEqual((body["added"], body["updated"], len(body["people"])), (1, 1, 1))
        step = body["apply_id"]
        self.assertEqual(self.post({"apply_id": step}, "/api/people/undo")[1]["people"], [])

    def test_one_undo_takes_the_whole_paste_back_including_a_changed_person(self):
        self.add("Sam Rivers", email="sam@example.com", role="Analyst")
        before = self.srv.call("GET", "/api/people")[1]["people"]
        steps = self.steps()
        body = self.paste({"name": "Sam Rivers", "role": "Delivery lead", "organisation": "Supplier"}, ZED)[1]
        self.assertEqual((body["added"], body["updated"]), (1, 1))
        self.assertEqual(self.steps(), steps + 1)                              # one step for the whole paste
        status, undone = self.post({"apply_id": body["apply_id"]}, "/api/people/undo")
        self.assertEqual(status, 200, undone)
        bare = lambda people: [{k: v for k, v in p.items() if k != "updated_at"} for p in people]    # noqa: E731 - the stamp moves with any write
        self.assertEqual(bare(undone["people"]), bare(before))
        self.assertEqual(self.post({"apply_id": body["apply_id"]}, "/api/people/undo")[0] in (400, 409), True)   # and not twice

    def test_a_paste_that_changes_nothing_writes_no_step(self):
        self.paste(SAM)
        steps = self.steps()
        status, body = self.paste(SAM)
        self.assertEqual((status, body["apply_id"], body["added"], body["updated"]), (200, None, 0, 0))
        self.assertEqual(self.steps(), steps)

    def test_a_bad_row_refuses_the_whole_paste_in_words_that_name_the_person_and_writes_nothing(self):
        self.add("Jo Park", email="jo@example.com")
        before, steps = self.srv.call("GET", "/api/people")[1]["people"], self.steps()
        for rows, says in (([SAM, {"name": "Li Wen", "email": "li wen@example.com"}], "Li Wen: That email can't be used"),
                           ([SAM, {"name": "Li Wen", "email": "li@example"}], "Li Wen: That email is not complete"),
                           ([SAM, {"name": "Li Wen", "email": "jo@example.com"}], "Li Wen: That email already belongs to Jo Park"),
                           ([SAM, {"name": "Li Wen", "email": "sam.rivers@example.com"}], "Li Wen: That email already belongs to Sam Rivers"),
                           ([SAM, {"name": "x" * 130}], "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx…: The name is too long"),
                           ([SAM, {"name": "  "}], "A row has no name")):
            status, body = self.paste(*rows)
            self.assertEqual((status, body["ok"]), (400, False), rows)
            self.assertIn(says, body["message"])
            self.assertTrue(body["message"].endswith("Nothing was changed."), body["message"])
        self.assertEqual(self.srv.call("GET", "/api/people")[1]["people"], before)
        self.assertEqual(self.steps(), steps)

    def test_a_name_that_matches_two_people_is_refused_not_guessed(self):
        self.add("Sam Rivers", email="a@example.com")
        self.add("Sam Rivers", email="b@example.com")
        status, body = self.paste({"name": "Sam Rivers", "role": "Lead"})
        self.assertEqual(status, 400)
        self.assertIn("More than one person is called Sam Rivers", body["message"])

    def test_the_shape_and_the_limits_are_checked(self):
        for req in ({"op": "paste"}, {"op": "paste", "rows": []}, {"op": "paste", "rows": "Sam"}, {"op": "paste", "rows": ["Sam"]},
                    {"op": "paste", "rows": [{"email": "a@example.com"}]}, {"op": "paste", "rows": [{"name": 5}]},
                    {"op": "paste", "rows": [{"name": "A", "colour": "red"}]}, {"op": "paste", "rows": [{"name": "A", "role": "x" * 2001}]},
                    {"op": "paste", "rows": [{"name": "A"}], "x": 1}, {"op": "paste", "rows": [{"name": "A", "kind": "group"}]}):
            status, body = self.post(req)
            self.assertEqual((status, body["ok"]), (400, False), req)
        status, body = self.paste(*[{"name": f"Person {n}"} for n in range(people_rules.ROW_LIMIT + 1)])
        self.assertEqual(status, 400)
        self.assertIn("more than 500 rows", body["message"])
        self.assertEqual(self.srv.call("GET", "/api/people")[1]["people"], [])

    def test_the_most_rows_one_paste_takes_fit_the_route_and_are_one_step(self):
        rows = [{"name": f"Person {n:03d} " + "n" * 100, "email": f"p{n}@" + "d" * 60 + ".example", "organisation": "o" * 100, "role": "r" * 100}
                for n in range(people_rules.ROW_LIMIT)]
        self.assertLess(len(json.dumps({"op": "paste", "rows": rows}).encode()), sv.ROUTE_BODY_LIMITS["/api/people"])
        status, body = self.paste(*rows)
        self.assertEqual((status, body["added"]), (200, people_rules.ROW_LIMIT), body.get("message"))
        self.assertEqual(self.post({"apply_id": body["apply_id"]}, "/api/people/undo")[1]["people"], [])

    def test_the_other_ops_still_refuse_rows_and_a_paste_takes_no_other_field(self):
        self.assertEqual(self.post({"op": "add", "name": "A", "rows": []})[0], 400)
        self.assertEqual(self.post({"op": "paste", "name": "A", "rows": [{"name": "A"}]})[0], 400)


class Private(unittest.TestCase):
    """A person's email, organisation and role are on the people list and nowhere else: not in what a publish reads, not in the file."""
    PLANTED = {"email": "zq.planted.person@leak-check.example", "organisation": "Zq Planted Organisation", "role": "Zq Planted Role"}

    def test_a_pasted_persons_details_reach_no_published_page(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = fx.build_db(Path(tmp.name) / "clark.db", fx.load())
        store = open_store(db, onedrive_roots=[])
        self.addCleanup(store.close)
        from clark import changes
        status, body = changes.make_people(db, [], USER)({"op": "paste", "rows": [{"name": "Quin Planted", **self.PLANTED}]})
        self.assertEqual(status, 200, body)
        pid = body["id"] if body["id"] else body["people"][0]["id"]
        with store.step("dashboard", "Demo User") as st:
            st.update("actions", "PUB-A-001", {"owner": "Quin Planted", "owner_id": pid})
        inputs = publish.read_inputs(store, "PUB", "2026-10-28")
        shown = json.dumps(publish.select(inputs), ensure_ascii=False)
        out = Path(tmp.name) / "out"
        out.mkdir()
        result = publish.publish(store, "PUB", out, now="2026-10-28", branding=tempfile.mkdtemp(prefix="clark-no-brand-"), by_user="Demo User")
        body = Path(result["path"]).read_text(encoding="utf-8")
        for text in (json.dumps(inputs, ensure_ascii=False, default=str), shown, body):
            for value in self.PLANTED.values():
                self.assertNotIn(value.lower(), text.lower())
            self.assertNotIn("owner_id", text)

    def test_the_people_card_is_not_in_the_published_page_source(self):
        """The card is an Edit part (edit/index.js hands it over); the published page's own entry never imports it or its route."""
        src = Path(_paths.SRC) / "clark" / "page" / "src"
        view = (src / "view.jsx").read_text(encoding="utf-8")
        self.assertNotIn("api/people", view)
        self.assertNotIn("People", view)
        html = (Path(_paths.SRC) / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        self.assertNotIn("/api/people", html)
        self.assertNotIn("Paste from Excel", html)


if __name__ == "__main__":
    unittest.main()
