"""#587: the server-side reply check for a client message knows the project. AiService.suggest takes an optional `project` (a project
code); the server validates it against the store and reads the project's codes and names itself (ai_menu.known_for), never from the
request. A reply that adds one of the project's people or item codes is blocked here as well as on the page. Fake provider; fictional
data (roles only). Run: python3 dev/run_tests.py test_ai_service_known"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

import _publish_fixture as plant
from clark import ai_menu, ai_service, ask_service, store as st
from test_ai_route import Fake

WROTE = "We will send the plan on Friday and confirm the date with you."


def said(text):
    return "<<<SUGGESTION\n" + WROTE + " " + text + "\nSUGGESTION>>>"


class Base(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.db = plant.build_db(self.d / "clark.db")
        self.store = st.open_store(self.db, onedrive_roots=[])
        self.addCleanup(self.store.close)
        with self.store.step("dashboard", "tester", place="menu") as s:
            s.update("app_settings", "1", {"ask_enabled": True})
        self.provider = Fake()
        self.service = ask_service.AskService(self.db, self.provider, [])

    def suggest(self, add, store="own", **more):
        ai = ai_service.AiService(self.service, self.store if store == "own" else store)
        self.provider.reply = said(add)
        body = {"option": "rewrite", "place": "client_message", "text": WROTE, **more}
        return ai.suggest(body)


class TheServerKnowsTheProject(Base):
    def test_a_reply_that_adds_a_known_name_is_blocked(self):
        status, got = self.suggest("Ask the Site manager.", project="PUB")
        self.assertEqual((status, got["ok"]), (200, False))
        self.assertIn("person's name", got["message"])

    def test_a_reply_that_adds_a_known_item_code_is_blocked(self):
        status, got = self.suggest("See PUB-A-001.", project="PUB")
        self.assertFalse(got["ok"])
        self.assertIn("item code", got["message"])

    def test_the_same_reply_passes_the_shape_rules_without_a_project(self):
        status, got = self.suggest("Ask the Site manager.")
        self.assertEqual((status, got["ok"]), (200, True))

    def test_a_name_the_text_already_held_may_stay(self):
        wrote = WROTE + " Ask the Site manager."
        ai = ai_service.AiService(self.service, self.store)
        self.provider.reply = "<<<SUGGESTION\nWe will send the plan on Friday and confirm the date. Ask the Site manager.\nSUGGESTION>>>"
        status, got = ai.suggest({"option": "rewrite", "place": "client_message", "text": wrote, "project": "PUB"})
        self.assertTrue(got["ok"], got)

    def test_the_known_set_is_read_by_the_server_from_the_store(self):
        seen = []
        real = ai_menu.known_for
        with mock.patch.object(ai_menu, "known_for", side_effect=lambda s, c: seen.append((s, c)) or real(s, c)):
            self.suggest("Ask the Site manager.", project="PUB")
        self.assertEqual(seen, [(self.store, "PUB")])


class AnUnknownProjectIsRefused(Base):
    def refused(self, status_got):
        status, got = status_got
        self.assertEqual((status, got["code"]), (400, "bad_request"), got)
        self.assertEqual(self.provider.requests, [])      # refused before anything left

    def test_a_project_the_store_does_not_hold(self):
        self.refused(self.suggest("Ask the Site manager.", project="ZZZ"))

    def test_a_project_of_the_wrong_shape_or_type(self):
        for bad in ("", "pub", "PUB'; --", "P", 5, None, ["PUB"]):
            self.refused(self.suggest("Ask the Site manager.", project=bad))

    def test_a_project_with_no_store_to_check_it_against(self):
        self.refused(self.suggest("Ask the Site manager.", store=None, project="PUB"))


if __name__ == "__main__":
    unittest.main()
