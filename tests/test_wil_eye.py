"""Row 1113, wish 3: the Work items list in the dashboard's Edit mode has the Work items page's own Client-visible eye on each row.
It is the same control (edit/cells/Eye.jsx): a press hides the item from the client everywhere, a press on a hidden one shows it. A hidden
item stays listed in Edit, drawn exactly as the Work items page draws an item that is off, so it can be shown again; it is not in the
published page, and not in the client's counts."""
import json
import unittest

from clark import publish
import test_tpl_workitems as base
from test_tpl_workitems import TODAY
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome, wait

OWNERS = ["Pat Demo", "Lee Demo", "Sam Demo", "Kim Demo"]


def tile_values(built):
    return {c["tile"]: c["value"] for s in built["published"]["sections"] if s["type"] == "glancetemplate" for c in s["content"].get("counts", [])}      # row 1266: the default At a glance is the template, whose counts are in its section content


class Eye(base.InThePage):
    def setUp(self):
        super().setUp()
        self.ref = self.add({"mode": "all", "owner": OWNERS})

    def eye(self, ref, item):
        return f"[data-id=\"{ref}\"] .wil-table tbody tr[data-id=\"{item}\"] .weye"

    def edit_rows(self, p):
        p.until(f"!!document.querySelector('[data-id=\"{self.ref}\"] .wil-table tbody tr')", "the list drew")
        return self.rows(p, self.ref)

    def pressed(self, p, item):
        return p.js(f"(document.querySelector({json.dumps(self.eye(self.ref, item))}) || {{getAttribute: () => null}}).getAttribute('aria-pressed')")

    def hidden(self):
        return {r[0] for r in self.store.con.execute("SELECT item_id FROM report_hidden WHERE project = 'ABC'")}

    def flag(self, item):
        return self.store.con.execute("SELECT client_visible FROM actions WHERE id = ?", (item,)).fetchone()[0]

    def built(self):
        built = publish.build(self.store, "ABC", now=TODAY)
        sec = next(s for s in built["published"]["sections"] if s["id"] == self.ref)
        return built, sec["items"]

    def test_edit_lists_the_items_the_eye_took_off_and_draws_them_as_the_work_items_page_does(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.edit()
                self.assertEqual(self.edit_rows(p), [self.a_due, self.a_off, self.a_eye, self.a_later, self.risk],
                                 "the two items the client eye took off are listed; Sensitive and archived ones never are")
                here = {i: p.js(f"document.querySelector({json.dumps(self.eye(self.ref, i))}).outerHTML") for i in (self.a_due, self.a_off, self.a_eye)}
                self.assertEqual([self.pressed(p, i) for i in (self.a_due, self.a_off, self.a_eye)], ["true", "false", "false"])
                p.js("location.hash = '#work&p=ABC&f=mode:all'")
                p.until(f"!!document.querySelector('#work tr[data-id=\"{self.a_eye}\"] .weye')", "the Work items page drew")
                for item, html in here.items():
                    page = p.js(f"document.querySelector('#work tr[data-id=\"{item}\"] .weye').outerHTML")
                    self.assertEqual(html, page, f"{item}: the eye in the section is the Work items page's eye, word for word")

    def test_row_1268_a_row_is_one_line_with_a_letter_tile_and_an_item_off_is_greyed(self):
        with chrome() as cdp:
            p = self.show(cdp, 1400)
            p.edit()
            self.edit_rows(p)
            q = f"[data-id=\"{self.ref}\"] .wil-table tbody tr"
            got = p.js(f"[...document.querySelectorAll({json.dumps(q)})].map(r => [r.dataset.id, r.classList.contains('wil-off'), !!r.querySelector('td.wil-c-tile .ico'), r.lastElementChild.previousElementSibling.classList.contains('wil-c-id')])")
            self.assertEqual({r[0]: r[1] for r in got}, {self.a_due: False, self.a_off: True, self.a_eye: True, self.a_later: False, self.risk: False},
                             "only the items the eye has taken off are greyed")
            self.assertTrue(all(r[2] and r[3] for r in got), "each row has the letter tile first and the ID last (the eye follows it)")
            self.assertEqual(p.js(f"[...document.querySelectorAll({json.dumps(q + ' .wil-c-title')})].every(e => getComputedStyle(e).whiteSpace === 'nowrap')"), True, "one line")

    def test_a_press_on_the_eye_flips_the_item_and_a_hidden_one_is_shown_again(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            self.edit_rows(p)
            p.js(f"document.querySelector({json.dumps(self.eye(self.ref, self.a_due))}).click()")
            p.until(f"document.querySelector({json.dumps(self.eye(self.ref, self.a_due))}).getAttribute('aria-pressed') === 'false'", "the eye turned off")
            self.assertTrue(wait(lambda: self.hidden() == {self.a_eye, self.a_due}), f"the store hides it: {self.hidden()}")
            self.assertEqual(self.rows(p, self.ref), [self.a_due, self.a_off, self.a_eye, self.a_later, self.risk], "still listed in Edit, so it can be shown again")
            self.assertEqual(p.js(f"document.querySelectorAll('#peek, [data-id=\"{self.ref}\"] .wil-table tr[data-id]').length && !location.hash.includes('item=')"), True,
                             "the press did not open the peek")
            _, items = self.built()
            self.assertNotIn(self.a_due, items)
            p.js(f"document.querySelector({json.dumps(self.eye(self.ref, self.a_due))}).click()")
            p.until(f"document.querySelector({json.dumps(self.eye(self.ref, self.a_due))}).getAttribute('aria-pressed') === 'true'", "the eye turned on")
            self.assertTrue(wait(lambda: self.hidden() == {self.a_eye}), "shown again in the store")
            # an item whose own client flag is off: the press turns the flag on
            p.js(f"document.querySelector({json.dumps(self.eye(self.ref, self.a_off))}).click()")
            p.until(f"document.querySelector({json.dumps(self.eye(self.ref, self.a_off))}).getAttribute('aria-pressed') === 'true'", "the eye turned on")
            self.assertTrue(wait(lambda: self.flag(self.a_off) == 1), "its own client-visible flag is on")
            _, items = self.built()
            self.assertIn(self.a_off, items)

    def test_a_hidden_item_is_not_in_the_published_page_or_the_clients_counts(self):
        before, items = self.built()
        self.assertIn(self.a_due, items)
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            self.edit_rows(p)
            p.js(f"document.querySelector({json.dumps(self.eye(self.ref, self.a_due))}).click()")
            self.assertTrue(wait(lambda: self.a_due in self.hidden()), "hidden by the press")
        after, items = self.built()
        self.assertNotIn(self.a_due, items)
        self.assertNotIn("Chase the supplier file", after["body"].decode("utf-8"))
        self.assertIn("Chase the supplier file", before["body"].decode("utf-8"))
        self.assertNotEqual(tile_values(before), tile_values(after), f"the client's counts moved: {tile_values(before)} then {tile_values(after)}")

    def test_a_list_of_only_hidden_items_says_it_is_left_out_of_the_published_page(self):
        ref = self.add({"mode": "all", "owner": ["Sam Demo"]})          # Sam's items: one Sensitive, one archived (never listed), one client-off
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            p.until(f"!!document.querySelector('[data-id=\"{ref}\"] [data-wil-say=all-hidden]')", "Edit says every item is hidden")
            self.assertEqual(self.rows(p, ref), [self.a_off])
        self.assertNotIn(ref, [s["id"] for s in publish.build(self.store, "ABC", now=TODAY)["published"]["sections"]])


for _name in [n for n in dir(base.InThePage) if n.startswith("test_") and n not in vars(Eye)]:
    setattr(Eye, _name, None)       # the helpers of the list's page tests are reused; their tests are run by test_tpl_workitems


if __name__ == "__main__":
    unittest.main()
