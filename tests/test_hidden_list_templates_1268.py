"""Row 1268: a hidden built-in section's rows reach a Work items list alone; every other template sees only what the section left in.

Run: python3 dev/run_tests.py test_hidden_list_templates_1268
Mutation killers for publish.select (shown_ctx). Fictional data, the clock fixed (ON).
"""
import json
import unittest

from _paths import ROOT   # noqa: F401

from clark import publish
from clark import store as store_module
from test_glance import ON, RULES, action, data, sections


def section(sid, kind, body, order):
    return {"id": sid, "type": kind, "title": sid, "body": store_module.check_section_body(kind, json.dumps(body)), "beside": 0, "hidden": 0, "sort_order": order}


def run(hide, extra, **values):
    i = {"data": data(actions=[action(1, "2026-10-20", **values)]), "hidden": [], "sections": sections(*hide) + extra,
         "label_rules": RULES, "as_at": ON, "glance_tiles": []}
    return publish.select(i)


def entry(out, sid):
    return next((s for s in out["sections"] if s["id"] == sid), None)


class Templates(unittest.TestCase):
    def test_a_checklist_naming_an_action_of_a_hidden_section_is_left_out(self):
        out = run(("actions",), [section("s-chk", "checklist", {"v": 1, "items": [{"item": "ABC-A-001"}]}, 50)])
        self.assertIsNone(entry(out, "s-chk"))

    def test_a_checklist_naming_an_action_of_a_shown_section_keeps_it(self):
        out = run((), [section("s-chk", "checklist", {"v": 1, "items": [{"item": "ABC-A-001"}]}, 50)])
        self.assertEqual(entry(out, "s-chk")["items"], [{"item": "ABC-A-001"}])

    def test_a_list_still_names_the_action_of_a_hidden_section_beside_the_checklist(self):
        out = run(("actions",), [section("s-chk", "checklist", {"v": 1, "items": [{"item": "ABC-A-001"}]}, 50),
                                 section("s-list", "workitems", {"mode": "all"}, 51)])
        self.assertIsNone(entry(out, "s-chk"))
        self.assertEqual(entry(out, "s-list")["items"], ["ABC-A-001"])
        self.assertEqual([a["id"] for a in out["data"]["actions"]], ["ABC-A-001"])

    def test_a_latest_update_card_of_a_shown_section_publishes_plain_words(self):
        card = {"v": 1, "cards": [{"id": "ABC-A-001", "source": "latest"}]}
        out = run((), [section("s-cards", "raid3", card, 50)], client_message="Plan nearly agreed.", latest_update="<p>Done &amp; <em>dusted</em></p>")
        self.assertEqual(entry(out, "s-cards")["cards"], [{"id": "ABC-A-001", "text": "Done & dusted"}])


if __name__ == "__main__":
    unittest.main()
