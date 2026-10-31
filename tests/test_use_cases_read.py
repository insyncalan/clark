"""#163: the read route for the Use Cases page (GET /api/use-cases, src/clark/use_cases_read.py, server.py).

Run: python3 dev/run_tests.py test_use_cases_read
The data is the publish plant in a real store; the server is a real one on 127.0.0.1. The route reads and writes nothing.
"""
import hashlib
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

import _publish_fixture as fx
from _paths import SRC  # noqa: F401  (puts src/ on the path)
from clark import __main__ as launcher, server as sv, use_cases_read
from clark.store import open_store


class Rig:
    def __init__(self, case, reader=True):
        tmp = tempfile.TemporaryDirectory()
        case.addCleanup(tmp.cleanup)
        self.db = Path(tmp.name) / "clark.db"
        self.plant = fx.load()
        fx.build_db(self.db, self.plant)
        self.on_file = lambda code: {"PUB-U-001"}          # stands in for the publish side's rule
        self.store = open_store(self.db, onedrive_roots=[])
        case.addCleanup(self.store.close)
        self.httpd = sv.LocalServer((sv.HOST, 0), data_for=self.store.data_for,
                                    use_cases=use_cases_read.make_read(self.store.data_for, self.on_file) if reader else None)
        self.httpd.handle_error = lambda *a: None
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        case.addCleanup(self.close)

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def get(self, path, token=None, method="GET"):
        conn = http.client.HTTPConnection(sv.HOST, self.httpd.server_port, timeout=20)
        try:
            headers = {"Host": f"127.0.0.1:{self.httpd.server_port}"}
            if token is not False:
                headers[sv.TOKEN_HEADER] = token or sv.TOKEN
            conn.request(method, path, None, headers)
            r = conn.getresponse()
            raw = r.read()
            return r.status, json.loads(raw) if raw else None
        finally:
            conn.close()

    def digest(self):
        return hashlib.sha256(self.db.read_bytes()).hexdigest()


class Base(unittest.TestCase):
    def setUp(self):
        self.rig = Rig(self)
        self.status, self.body = self.rig.get("/api/use-cases?project=PUB")
        self.by_id = {u["id"]: u for u in self.body["use_cases"]} if self.status == 200 else {}


class WhatItReturns(Base):
    def test_the_project_use_cases_in_order(self):
        self.assertEqual(self.status, 200)
        self.assertEqual(self.body["project"], "PUB")
        self.assertEqual([u["id"] for u in self.body["use_cases"]], ["PUB-U-001", "PUB-U-002", "PUB-U-003"])

    def test_one_use_case_has_its_fields(self):
        u = self.by_id["PUB-U-001"]
        self.assertEqual((u["ref"], u["status"], u["headline"], u["on_dashboard"]), ("1.1", "On track", "Going to plan", True))
        self.assertIn("ZQ-KEEP-USECASE-1", u["name"])
        self.assertEqual((u["linked"], u["open"]), (1, 1))
        self.assertEqual([s["id"] for s in u["next_steps"]], ["PUB-A-001"])
        self.assertEqual([m["id"] for m in u["milestones"]], ["PUB-M-001"])

    def test_a_use_case_that_is_off_the_dashboard_is_still_listed_with_its_work(self):
        u = self.by_id["PUB-U-002"]
        self.assertIs(u["on_dashboard"], False)
        self.assertEqual([s["id"] for s in u["next_steps"]], ["PUB-A-002"])        # the editor shows it, the file does not

    def test_on_dashboard_is_what_the_rule_it_was_given_says(self):
        """Only the injected rule decides: a rule that names PUB-U-003 puts that one on, whatever its stored eye says. (The
        real rule is tested against the plant in RealRule below.)"""
        read = use_cases_read.make_read(self.rig.store.data_for, lambda code: {"PUB-U-003"})
        self.assertEqual([u["id"] for u in read("PUB") if u["on_dashboard"]], ["PUB-U-003"])

    def test_a_use_case_with_nothing_linked_has_none(self):
        u = self.by_id["PUB-U-003"]
        self.assertEqual((u["linked"], u["open"], u["next_steps"], u["milestones"]), (0, 0, [], []))

    def test_only_the_named_fields_are_returned(self):
        u = self.by_id["PUB-U-001"]
        self.assertEqual(set(u), {"id", "ref", "name", "headline", "status", "standing", "on_dashboard", "linked", "open",
                                  "next_steps", "milestones"})
        self.assertEqual(set(u["next_steps"][0]), {"id", "description", "owner", "due_date", "status", "client_visible"})
        self.assertEqual(set(u["milestones"][0]), {"id", "name", "baseline_date", "forecast_date", "status", "client_visible"})
        text = json.dumps(self.body)
        for key in ("internal_note", "source", "response_action", "reasoning", "options", "publish_local", "publish_client"):
            self.assertNotIn(self.rig.plant["markers"][key], text)

    def test_an_archived_use_case_and_an_archived_item_are_left_out(self):
        data = fx.load()["data"]
        data["use_cases"][0]["archived"] = 1
        data["actions"][0]["archived"] = 1
        out = use_cases_read.use_cases_of(data, set())
        self.assertNotIn("PUB-U-001", [u["id"] for u in out])
        data["use_cases"][0]["archived"] = 0
        first = use_cases_read.use_cases_of(data, set())[0]
        self.assertEqual((first["linked"], first["next_steps"]), (0, []))

    def test_a_closed_item_is_linked_but_not_open(self):
        data = fx.load()["data"]
        data["actions"][0]["status"] = "Closed"
        first = use_cases_read.use_cases_of(data, set())[0]
        self.assertEqual((first["linked"], first["open"], first["next_steps"]), (1, 0, []))


class RealRule(unittest.TestCase):
    """The rule the launcher gives the route (`use_case_ids_on_file`, today publish.select's choice), over the publish plant in a
    real store. A change to it, or to what #168 will point it at, must show here."""

    def on_dashboard(self, change=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        plant = fx.load()
        if change:
            change(plant)
        db = fx.build_db(Path(tmp.name) / "clark.db", plant)
        store = open_store(db, onedrive_roots=[])
        self.addCleanup(store.close)
        read = use_cases_read.make_read(store.data_for, launcher.use_case_ids_on_file(store))
        return sorted(u["id"] for u in read("PUB") if u["on_dashboard"])

    def test_only_the_use_case_the_file_carries_is_on_the_dashboard(self):
        # U-002 has the eye off, U-003 is labelled Sensitive
        self.assertEqual(self.on_dashboard(), ["PUB-U-001"])

    def test_a_use_case_left_off_the_report_is_not(self):
        self.assertEqual(self.on_dashboard(lambda plant: plant["hidden"].append("PUB-U-001")), [])

    def test_a_hidden_use_cases_section_puts_none_on(self):
        def hide(plant):
            for s in plant["sections"]:
                if s["type"] == "usecases":
                    s["hidden"] = 1
        self.assertEqual(self.on_dashboard(hide), [])

    def test_a_label_the_rules_exclude_takes_it_off(self):
        def label(plant):
            plant["data"]["labels"]["PUB-U-001"] = ["Commercial"]          # the plant's Commercial label is an exclude rule
        self.assertEqual(self.on_dashboard(label), [])

    def test_sensitive_in_capitals_takes_it_off(self):
        def label(plant):
            plant["data"]["labels"]["PUB-U-001"] = ["SENSITIVE"]
        self.assertEqual(self.on_dashboard(label), [])

    def test_a_use_case_with_the_eye_on_and_no_label_comes_on(self):
        def eye(plant):
            for u in plant["data"]["use_cases"]:
                if u["id"] == "PUB-U-002":
                    u["client_visible"] = 1
        self.assertEqual(self.on_dashboard(eye), ["PUB-U-001", "PUB-U-002"])


class Milestones(unittest.TestCase):
    def test_a_closed_action_does_not_bring_its_milestone(self):
        data = fx.load()["data"]
        first = use_cases_read.use_cases_of(data, set())[0]
        self.assertEqual([m["id"] for m in first["milestones"]], ["PUB-M-001"])
        data["actions"][0]["status"] = "Closed"
        first = use_cases_read.use_cases_of(data, set())[0]
        self.assertEqual((first["next_steps"], first["milestones"]), ([], []))

    def test_an_archived_milestone_is_left_out(self):
        data = fx.load()["data"]
        data["milestones"][0]["archived"] = 1
        self.assertEqual(use_cases_read.use_cases_of(data, set())[0]["milestones"], [])

    def test_milestones_of_is_the_only_rule(self):
        steps = [{"milestone": "M-2"}, {"milestone": None}]
        ms = [{"id": "M-1"}, {"id": "M-2"}]
        self.assertEqual(use_cases_read.milestones_of(steps, ms), [{"id": "M-2"}])


class HostileText(unittest.TestCase):
    def test_text_is_cleaned(self):
        data = fx.load()["data"]
        u = data["use_cases"][0]
        u["standing"] = '<p onclick="x()">ok</p><script>bad()</script><iframe src="https://x.invalid"></iframe>'
        u["title"] = "Name\x00 with\x07 controls"
        out = use_cases_read.use_cases_of(data, set())[0]
        self.assertEqual(out["standing"], "<p>ok</p>")
        self.assertEqual(out["name"], "Name with controls")

    def test_long_text_is_returned_whole(self):
        data = fx.load()["data"]
        data["use_cases"][0]["headline"] = "h" * 5000
        data["actions"][0]["description"] = "d" * 2503 + "END"
        out = use_cases_read.use_cases_of(data, set())[0]
        self.assertEqual(len(out["headline"]), 5000)
        self.assertTrue(out["next_steps"][0]["description"].endswith("END"))

    def test_invisible_formatting_characters_are_dropped(self):
        data = fx.load()["data"]
        data["actions"][0]["owner"] = "Sam\u202eevil\u200b\ue000\u2028x"
        data["use_cases"][0]["title"] = "Gate\u200dway"
        out = use_cases_read.use_cases_of(data, set())[0]
        self.assertEqual(out["next_steps"][0]["owner"], "Samevilx")
        self.assertEqual(out["name"], "Gateway")

    def test_a_missing_owner_or_date_is_null_not_empty(self):
        data = fx.load()["data"]
        data["actions"][0].update(owner=None, due_date=None)
        data["milestones"][0]["forecast_date"] = None
        out = use_cases_read.use_cases_of(data, set())[0]
        step, ms = out["next_steps"][0], out["milestones"][0]
        self.assertEqual((step["owner"], step["due_date"], ms["forecast_date"]), (None, None, None))
        self.assertNotEqual(step["description"], "")
        data["actions"][0]["owner"] = 7                      # not text: empty, not null
        self.assertEqual(use_cases_read.use_cases_of(data, set())[0]["next_steps"][0]["owner"], "")

    def test_a_missing_client_visible_counts_as_off(self):
        data = fx.load()["data"]
        del data["actions"][0]["client_visible"]
        self.assertIs(use_cases_read.use_cases_of(data, set())[0]["next_steps"][0]["client_visible"], False)

    def test_a_bad_sort_order_does_not_stop_the_list(self):
        data = fx.load()["data"]
        data["use_cases"][0]["sort_order"] = "first"
        data["milestones"][0]["sort_order"] = None
        out = use_cases_read.use_cases_of(data, set())
        self.assertEqual(len(out), 3)

    def test_a_field_that_is_not_text_is_empty(self):
        data = fx.load()["data"]
        data["use_cases"][0]["headline"] = {"a": 1}
        data["use_cases"][0]["standing"] = "x" * 300_000
        out = use_cases_read.use_cases_of(data, set())[0]
        self.assertEqual((out["headline"], out["standing"]), ("", ""))

    def test_look_alike_letters_are_kept_as_plain_text_and_markup_is_escaped(self):
        data = fx.load()["data"]
        data["use_cases"][0]["standing"] = "<p>арр &lt;b&gt; <b>x</b></p>"
        out = use_cases_read.use_cases_of(data, set())[0]["standing"]
        self.assertNotIn("<b>", out)
        self.assertIn("арр", out)


class TheRoute(Base):
    def test_nothing_is_written(self):
        before = self.rig.digest()
        for _ in range(3):
            self.rig.get("/api/use-cases?project=PUB")
        self.assertEqual(before, self.rig.digest())

    def test_a_bad_request_is_refused(self):
        for path in ("/api/use-cases", "/api/use-cases?project=", "/api/use-cases?project=pub",
                     "/api/use-cases?project=PUB&project=PUB", "/api/use-cases?project=PUB&archived=show",
                     "/api/use-cases?project=PUB%27--", "/api/use-cases?project=../x"):
            status, body = self.rig.get(path)
            self.assertEqual((status, body["code"]), (400, "bad_project_code"), path)

    def test_an_unknown_project_is_not_found(self):
        status, body = self.rig.get("/api/use-cases?project=NOPE")
        self.assertEqual((status, body["code"]), (404, "project_not_found"))

    def test_the_token_is_needed(self):
        self.assertEqual(self.rig.get("/api/use-cases?project=PUB", token=False)[0], 403)
        self.assertEqual(self.rig.get("/api/use-cases?project=PUB", token="wrong")[0], 403)

    def test_only_get_reads_it(self):
        self.assertNotEqual(self.rig.get("/api/use-cases?project=PUB", method="DELETE")[0], 200)

    def test_without_a_reader_there_is_no_route(self):
        rig = Rig(self, reader=False)
        status, body = rig.get("/api/use-cases?project=PUB")
        self.assertEqual((status, body["code"]), (404, "not_found"))
        status, body = rig.get("/api/use-cases?project=pub&x=1")       # a bad request to a route that isn't there is still not found
        self.assertEqual((status, body["code"]), (404, "not_found"))


if __name__ == "__main__":
    unittest.main()
