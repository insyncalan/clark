"""#96 G5, Contacts: the content rules (section_kinds/contacts.py), the file, and the page's View and Edit parts.
Run: python3 dev/run_tests.py test_tpl_contacts
Needs Chrome (the #33 harness): the page tests fail, never skip, without it. Fictional data only.
"""
import json
import unittest

import _tpl_notes as n
from test_server import chrome, wait

PEOPLE = [{"name": "Sam Example", "role": "Fictional lead", "email": "sam@example.org", "phone": "+44 20 7946 0000"},
          {"name": "Alex Example", "role": "", "email": "", "phone": ""}]
GOOD = {"v": 1, "people": PEOPLE}
HOSTILE = {"v": 1, "people": [{"name": n.HOSTILE, "role": n.HOSTILE, "email": "", "phone": ""}]}


class Data(n.DataChecks):
    TYPE, GOOD, WORDS, HOSTILE_BODY = "contacts", GOOD, "Fictional lead", HOSTILE
    LIMIT_BODY = {"v": 1, "people": [{"name": "x" * 81}]}
    BAD = ({"v": 1, "people": "Sam"}, {"v": 1, "people": ["Sam"]}, {"v": 1, "people": [{"role": "Fictional lead"}]},
           {"v": 1, "people": [{"name": "Sam", "email": "not an address"}]}, {"v": 1, "people": [{"name": "Sam", "email": "a@b@c.org"}]},
           {"v": 1, "people": [{"name": "Sam", "email": "<x>@example.org"}]},
           {"v": 1, "people": [{"name": "Sam", "email": "sam@example.org?bcc=x@example.org"}]}, {"v": 1, "people": [{"name": "Sam", "email": "sam%0d@example.org"}]}, {"v": 1, "people": [{"name": "Sam", "phone": "call me"}]},
           {"v": 1, "people": [{"name": f"P{i}"} for i in range(9)]}, {"v": 1, "people": [{"name": 5}]})

    def test_a_person_with_no_details_is_dropped_and_the_order_is_kept(self):
        ref = self.section()
        self.write(ref, {"v": 1, "people": [{"name": "Zed"}, {}, {"name": "", "role": ""}, {"name": "Amy"}]})
        self.assertEqual([p["name"] for p in json.loads(self.stored(ref))["people"]], ["Zed", "Amy"])

    def test_a_person_with_details_but_no_name_is_refused_in_words(self):
        ref = self.section()
        status, got = self.write(ref, {"v": 1, "people": [{"email": "sam@example.org"}]})
        self.assertEqual(status, 400)
        self.assertEqual(got["message"], "Give each contact a name. A contact with details but no name can't be saved.")


class Page(n.PageChecks):
    TYPE, GOOD, HOSTILE_BODY = "contacts", GOOD, HOSTILE
    SHOWS = ("Sam Example", "Fictional lead", "sam@example.org", "+44 20 7946 0000", "Alex Example")
    FIELD, TYPED = "Person 1 name", "Sam Changed"
    CHANGED = lambda self, body: json.loads(body)["people"][0]["name"] == "Sam Changed"

    def test_an_email_is_a_mailto_link_and_nothing_else_is_a_link(self):
        ref = self.make(self.GOOD)
        with chrome() as cdp:
            p = self.visit(cdp)
            links = p.js(f"[...document.querySelectorAll('[data-id={json.dumps(ref)}] a')].map(a => a.getAttribute('href'))")
            self.assertEqual(links, ["mailto:sam@example.org"])

    def test_a_person_without_a_name_is_not_saved_and_the_page_says_so(self):
        ref = self.make(self.GOOD)
        before = self.body_of(ref)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            base = f"[data-id={json.dumps(ref)}]"
            p.until(f"!!document.querySelector('{base} [aria-label=\"Person 2 role\"]')", "the fields")
            n.fill(p, n.field_js(ref, "Person 1 name"), " ")
            p.until(f"!!document.querySelector('{base} p[role=status]')", "the hint")       # p: the section's drag hint (#131) is a span[role=status] too
            self.assertIn("Add a name", p.js(f"document.querySelector('{base} p[role=status]').textContent"))
            self.assertEqual(self.body_of(ref), before)

    def test_a_nameless_person_does_not_hold_back_the_save_of_a_named_one(self):
        ref = self.make(self.GOOD)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            base = f"[data-id={json.dumps(ref)}]"
            p.until(f"!!document.querySelector('{base} .tpl-person')", "the fields")
            p.js("[...document.querySelectorAll('" + base + " .btn')].find(b => b.textContent === 'Add a person').click()")
            p.until(f"document.querySelectorAll('{base} .tpl-person').length === 3", "a blank person")
            n.fill(p, n.field_js(ref, "Person 3 role"), "Fictional helper")
            p.until(f"!!document.querySelector('{base} p[role=status]')", "the hint")
            n.fill(p, n.field_js(ref, "Person 1 name"), "Sam Changed")
            p.until(f"document.querySelectorAll('{base} .tpl-person').length === 3 && !!document.querySelector('{base} p[role=status]')", "the third person and the hint stay")
            self.assertTrue(wait(lambda: self.body_of(ref) and json.loads(self.body_of(ref))["people"][0]["name"] == "Sam Changed", 10), "the named person was saved")
            self.assertEqual(len(json.loads(self.body_of(ref))["people"]), 2, "the nameless person was not")
            self.assertEqual(p.js(n.field_js(ref, "Person 3 role") + ".value"), "Fictional helper", "its draft is still there")
            self.assertIn("Add a name", p.js(f"document.querySelector('{base} p[role=status]').textContent"))

    def test_add_a_person_and_remove_one(self):
        ref = self.make(self.GOOD)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            base = f"[data-id={json.dumps(ref)}]"
            p.until(f"!!document.querySelector('{base} .tpl-person')", "the fields")
            p.js("[...document.querySelectorAll('" + base + " .btn')].find(b => b.textContent === 'Add a person').click()")
            p.until(f"document.querySelectorAll('{base} .tpl-person').length === 3", "a blank person on the page")
            self.assertEqual(len(json.loads(self.body_of(ref))["people"]), 2, "nothing is saved for a blank person")
            p.js("document.querySelector('" + base + " [aria-label=\"Remove person 2\"]').click()")
            p.saved()
            self.assertEqual([x["name"] for x in json.loads(self.body_of(ref))["people"]], ["Sam Example"])

    def _add_person(self, p, base, count):
        p.js("[...document.querySelectorAll('" + base + " .btn')].find(b => b.textContent === 'Add a person').click()")
        p.until(f"document.querySelectorAll('{base} .tpl-person').length === {count}", "a blank person")

    def test_removing_a_saved_person_saves_while_an_added_nameless_row_waits(self):
        ref = self.make(self.GOOD)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            base = f"[data-id={json.dumps(ref)}]"
            p.until(f"!!document.querySelector('{base} .tpl-person')", "the fields")
            self._add_person(p, base, 3)
            n.fill(p, n.field_js(ref, "Person 3 role"), "Fictional helper")
            p.until(f"!!document.querySelector('{base} p[role=status]')", "the hint")
            p.js("document.querySelector('" + base + " [aria-label=\"Remove person 1\"]').click()")
            self.assertTrue(wait(lambda: [x["name"] for x in json.loads(self.body_of(ref))["people"]] == ["Alex Example"], 10), "the removal was saved")
            self.assertEqual(p.js(n.field_js(ref, "Person 2 role") + ".value"), "Fictional helper", "the nameless row waits")

    def test_editing_a_saved_person_after_a_later_one_was_named_and_saved_with_a_nameless_row_between(self):
        ref = self.make({"v": 1, "people": PEOPLE[:1]})
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            base = f"[data-id={json.dumps(ref)}]"
            p.until(f"!!document.querySelector('{base} .tpl-person')", "the fields")
            self._add_person(p, base, 2)
            n.fill(p, n.field_js(ref, "Person 2 role"), "Fictional helper")             # X: a role, no name
            self._add_person(p, base, 3)
            n.fill(p, n.field_js(ref, "Person 3 name"), "Yan Example")                   # Y: named, saved
            self.assertTrue(wait(lambda: len(json.loads(self.body_of(ref))["people"]) == 2, 10), "Y was saved")
            n.fill(p, n.field_js(ref, "Person 1 name"), "Sam Changed")
            self.assertTrue(wait(lambda: json.loads(self.body_of(ref))["people"][0]["name"] == "Sam Changed", 10), "the edit of the first person was saved")
            self.assertEqual(len(json.loads(self.body_of(ref))["people"]), 2, "the nameless row was not")


if __name__ == "__main__":
    unittest.main()
