"""#454: the People card's Paste from Excel, the server's half: POST /api/people {op: "paste", rows} is ONE step (one Undo), goes
through the same writer and checks as an add or an edit, names the person in a refusal and writes nothing then, and a person's
email, organisation and role reach no published page. Fictional names.
Run: python3 dev/run_tests.py test_people_paste_route"""
import http.client
import json
import tempfile
import time
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

    def test_an_over_limit_body_is_refused_before_it_is_read(self):
        limit = sv.ROUTE_BODY_LIMITS["/api/people"]
        self.assertEqual(limit, sv.PEOPLE_BODY_LIMIT)
        before, steps = self.srv.call("GET", "/api/people")[1]["people"], self.steps()
        for size in (limit + 1, 4 * limit):
            conn = http.client.HTTPConnection(sv.HOST, self.srv.port, timeout=10)
            try:
                conn.putrequest("POST", "/api/people", skip_host=True, skip_accept_encoding=True)
                conn.putheader("Host", f"127.0.0.1:{self.srv.port}")
                conn.putheader(sv.TOKEN_HEADER, sv.TOKEN)
                conn.putheader("Content-Type", "application/json")
                conn.putheader("Content-Length", str(size))
                conn.endheaders(b"{}")                  # two bytes sent, the rest never: a server that tried to read it would wait
                r = conn.getresponse()
                self.assertEqual((r.status, json.loads(r.read())["code"]), (400, "too_large"), size)
            finally:
                conn.close()
        self.assertEqual(self.srv.call("GET", "/api/people")[1]["people"], before)
        self.assertEqual(self.steps(), steps)

    def test_the_worst_case_500_row_paste_fits_the_limit(self):
        """Every cell at its cap and every character a six-byte escape: the biggest body the page can send. It is read whole (not
        too_large) and is refused only for what is in it (a control character is no email)."""
        row = {"name": "\u0001" * 120, "email": "\u0001" * 254, "organisation": "\u0001" * 100, "role": "\u0001" * 100}
        raw = json.dumps({"op": "paste", "rows": [row] * people_rules.ROW_LIMIT}, separators=(",", ":")).encode()
        self.assertEqual(raw.count(b"\\u0001"), 574 * 500)
        self.assertLessEqual(len(raw), sv.PEOPLE_BODY_LIMIT)
        self.assertGreater(len(raw), 1_700_000)                                  # this really is the worst case, not a small body
        status, body = self.srv.call("POST", "/api/people", raw)
        self.assertEqual(status, 400)
        self.assertNotEqual(body["code"], "too_large")
        self.assertIn("Nothing was changed", body["message"])

    def test_organisation_and_role_are_capped_at_100_on_the_server_too(self):
        for field in ("organisation", "role"):
            status, body = self.paste(SAM, {"name": "Li Wen", field: "x" * 101})
            self.assertEqual(status, 400, field)
            self.assertIn(f"Li Wen: the {field} is too long (at most 100 characters)", body["message"])
            self.assertTrue(body["message"].endswith("Nothing was changed."))
        self.assertEqual(self.paste(SAM, {"name": "Li Wen", "organisation": "x" * 100, "role": "y" * 100})[0], 200)
        self.assertEqual(self.paste({"name": "Li Wen", "organisation": ("x " * 60)})[0], 400)         # counted after the spaces are squashed
        self.assertEqual(self.paste({"name": "Li Wen", "role": "   " + "y" * 100 + "   "})[0], 200)

    def test_a_name_that_matches_only_an_archived_person_is_not_added_again(self):
        pid = self.add("Sam Rivers", email="sam@example.com")["id"]
        self.post({"op": "archive", "id": pid})
        self.add("Kay Moss", aliases="Kay M")
        before, steps = self.srv.call("GET", "/api/people")[1]["people"], self.steps()
        status, body = self.paste(ZED, {"name": "sam  rivers", "role": "Lead"})
        self.assertEqual(status, 400)
        self.assertIn("sam rivers is on the list but has been archived. Restore them from the People card", body["message"])
        self.assertTrue(body["message"].endswith("Nothing was changed."))
        self.assertEqual(self.srv.call("GET", "/api/people")[1]["people"], before)
        self.assertEqual(self.steps(), steps)
        self.post({"op": "restore", "id": pid})                                  # once restored, the same row updates them
        body = self.paste({"name": "Sam Rivers", "role": "Lead"})[1]
        self.assertEqual((body["added"], body["updated"]), (0, 1))
        self.post({"op": "archive", "id": pid})
        self.add("Sam Rivers", email="new@example.com")                          # a live person of that name wins over the archived one
        self.assertEqual(self.paste({"name": "Sam Rivers", "role": "Boss"})[1]["updated"], 1)

    def test_a_name_of_tbc_is_refused_as_a_row_in_any_case(self):
        before, steps = self.srv.call("GET", "/api/people")[1]["people"], self.steps()
        for name in ("tbc", "TBC", "Tbc", "  tBc  "):
            status, body = self.paste(SAM, {"name": name, "email": "tbc@example.com"})
            self.assertEqual(status, 400, name)
            self.assertIn("isn't a name", body["message"])
            self.assertTrue(body["message"].endswith("Nothing was changed."))
        self.assertEqual(self.paste(SAM, {"name": "Tbc Smith"})[0], 200)       # only the whole placeholder, not a name that starts with it
        self.assertEqual(self.srv.call("GET", "/api/people")[1]["people"][0]["name"], "Sam Rivers")
        self.assertEqual(before, [])
        self.assertEqual(self.steps(), steps + 1)

    def test_the_other_ops_still_refuse_rows_and_a_paste_takes_no_other_field(self):
        self.assertEqual(self.post({"op": "add", "name": "A", "rows": []})[0], 400)
        self.assertEqual(self.post({"op": "paste", "name": "A", "rows": [{"name": "A"}]})[0], 400)


class Scale(Base):
    """The paste builds the name and alias index once, not once a row: a big list and a full paste stay quick, and the answers are
    the per-row resolver's (people.resolve over the list as it stands after each row)."""
    paste, steps = Paste.paste, Paste.steps
    BIG = 700                       # people.ID_LIMIT is 999: this many on the list, and the paste adds a third of 500 more

    def fill(self, count):
        s = clark_open(self.path)
        try:
            with s.step("dashboard", USER) as st:
                for n in range(count):
                    st.add_person(source="People list", name=f"Big Person {n:04d}", email=f"big{n}@example.com", aliases=f"BP{n:04d}")
        finally:
            s.close()

    def reference(self, listed, rows):
        """The old behaviour, in memory: for each row people.resolve over the whole list as it stands, then add or fill in."""
        people = [dict(p) for p in listed]
        added = updated = 0
        for row in rows:
            name = " ".join(row["name"].split())
            found = people_rules.resolve(name, people)
            details = {k: " ".join((row.get(k) or "").split()) or None for k in ("email", "organisation", "role")}
            details["email"] = (details["email"] or "").lower() or None
            if found["status"] == "one":
                now = next(p for p in people if p["id"] == found["id"])
                changes = {k: v for k, v in details.items() if v and v != now.get(k)}
                if changes:
                    now.update(changes)
                    updated += 1
            else:
                people.append({"id": f"new{len(people)}", "name": name, "aliases": None, "archived": 0, **{k: v for k, v in details.items() if v}})
                added += 1
        return added, updated, sorted((p["name"], p.get("email"), p.get("organisation"), p.get("role")) for p in people)

    def test_a_500_row_paste_against_a_large_list_stays_fast_and_reads_the_list_once(self):
        self.fill(self.BIG)
        rows = []
        for n in range(people_rules.ROW_LIMIT):
            if n % 3 == 0:
                rows.append({"name": f"big person {n * 5 % self.BIG:04d}", "role": f"Role {n}"})          # a name on the list
            elif n % 3 == 1:
                rows.append({"name": f"BP{n * 5 % self.BIG:04d}", "organisation": f"Org {n}"})            # an alias on the list
            else:
                rows.append({"name": f"Fresh Person {n:03d}", "email": f"fresh{n}@example.com"})          # new
        calls = {"people": 0, "keys": 0}
        real_people, real_key = clark_open(self.path).__class__.people, people_rules.name_key

        def people(store, archived=False):
            calls["people"] += 1
            return real_people(store, archived)

        def key(text):
            calls["keys"] += 1
            return real_key(text)
        from unittest import mock
        with mock.patch("clark.store.Store.people", people), mock.patch.object(people_rules, "name_key", key):
            t0 = time.perf_counter()
            status, body = self.paste(*rows)
            took = time.perf_counter() - t0
        self.assertEqual(status, 200, body)
        self.assertEqual((body["added"], body["updated"]), (sum(n % 3 == 2 for n in range(500)), sum(n % 3 != 2 for n in range(500))))
        # The list is read at most twice (the index, then the reply), and a name is keyed once per person and row, not once per person per row.
        self.assertLessEqual(calls["people"], 2)
        self.assertLess(calls["keys"], 2 * (self.BIG * 2 + 4 * len(rows)))
        self.assertLess(took, 20, f"a 500-row paste against {self.BIG} people took {took:.1f}s")

    def test_the_answers_are_the_per_row_resolvers_on_a_mixed_paste(self):
        for n, extra in enumerate(({"aliases": "Sam Rivers"}, {}, {"aliases": "Jo P;J Park"})):
            self.add(("Samuel Rivers", "Kay Moss", "Jo Park")[n], email=f"p{n}@example.com", **extra)
        gone = self.add("Old Hand", email="old@example.com")["id"]
        self.post({"op": "archive", "id": gone})
        rows = [{"name": "Sam Rivers", "role": "Lead"}, {"name": "S\u0430m Rivers", "organisation": "Look-alike letter"},       # Cyrillic a: the same person
                {"name": "KAY  MOSS", "email": "Kay@Example.com"}, {"name": "j park", "role": "Analyst"},
                {"name": "New One", "email": "NEW@example.com", "organisation": "  Client  "}, {"name": "new one", "role": "Sponsor"},
                {"name": "Another", "organisation": "Supplier"}, {"name": "Samuel Rivers", "role": "Lead"}]
        s = clark_open(self.path)
        try:
            listed = s.people(archived=None)
        finally:
            s.close()
        want_added, want_updated, want_people = self.reference(listed, rows)
        status, body = self.paste(*rows)
        self.assertEqual(status, 200, body)
        self.assertEqual((body["added"], body["updated"]), (want_added, want_updated))
        self.assertEqual(sorted((p["name"], p.get("email"), p.get("organisation"), p.get("role")) for p in body["people"]), want_people)
        self.assertEqual((want_added, want_updated), (2, 5))


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
