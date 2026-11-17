"""Row 1234: the approved words of the add-a-use-case picker are all there, and "Find a field" is not (it was dropped).

Run: python3 dev/run_tests.py test_uc_picker_words
Same page, store and data as test_uc_picker_table. Widths 1400 and 900 only.
"""
import unittest

from _demo import USER
from test_glance_page import Setup, tearDownModule  # noqa: F401
from test_server import chrome

Q = "document.querySelector('form.picker')"
ROWS = "document.querySelectorAll('form.picker tbody tr').length"

# Everything a person or a screen reader gets from the picker: its text, the placeholder, the aria-label and title of every part.
ALL_WORDS = """(() => { const f = document.querySelector('form.picker'); const out = [f.textContent];
  for (const e of document.querySelectorAll('form.picker, form.picker *, .pkt-panel, .pkt-panel *')) {
    for (const a of ['placeholder', 'aria-label', 'title', 'value', 'alt']) if (e.getAttribute(a)) out.push(e.getAttribute(a)); }
  return out.join('\\n'); })()"""
SEARCH = "document.querySelector('form.picker input[type=search]')"
EMPTY = "Nothing matches your search. Clear it to see what can be added."


class Words(Setup):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            for n, (title, status, ref) in enumerate([("Supplier portal", "High risk", "1.10"), ("Month end close", "On track", "2.1")], 3):
                st.create("use_cases", {"project": "ABC", "title": title, "status": status, "ref": ref, "sort_order": n, "headline": "x", "client_visible": 0, "source": "demo"})

    def edit(self, cdp, width):
        p = self.show(cdp, width)
        p.js("document.querySelector('[data-mode=edit]').click()")
        p.until("!!document.querySelector('.uc [data-uc-status]')", "Edit shows the status buttons")
        return p

    def show_picker(self, p):
        p.js("document.querySelector('[data-uc-back]').scrollIntoView({block: 'center'})")
        x, y, _ = p.box("[data-uc-back]")
        p.mouse("mouseMoved", x, y)
        p.mouse("mousePressed", x, y, 1)
        p.mouse("mouseReleased", x, y)
        p.until("!!" + Q, "the picker")

    def test_every_approved_word_is_there_and_find_a_field_is_not(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.edit(cdp, width)
                self.show_picker(p)
                self.assertEqual(p.js(SEARCH + ".placeholder"), "Search by name, ID or status")
                self.assertEqual(p.js("document.querySelector('[data-filter] .sr').textContent"), "Filters", "screen-reader text of the filter button")
                self.assertEqual(p.js("document.querySelector('form.picker [data-result]').textContent"), "Result: 2 of 2 shown")
                p.js("document.querySelector('[data-filter]').click()")
                p.until("!!document.querySelector('.pkt-panel')", "the panel")
                self.assertEqual(p.js("document.querySelector('.pkt-panel').getAttribute('aria-label')"), "Filters", "the panel's aria-label")
                self.assertEqual(p.js("document.querySelector('.pkt-more').textContent"), "More fields", "the group heading")
                self.assertEqual(p.js("[...document.querySelectorAll('.pkt-field')].map(b => b.textContent).filter(t => t === 'Open steps' || t === 'Work items').join()"),
                                 "Open steps,Work items")
                self.assertEqual(p.js("document.querySelector('.pkt-panel [data-not=\"1\"]').textContent"), "is not any of")
                # at 0 ticked the button has no number
                self.assertEqual(p.js("document.querySelector('form.picker button[type=submit]').textContent"), "Add selected", "no count at 0")
                self.assertEqual(p.js("document.querySelector('form.picker button[type=submit]').disabled"), True, "nothing to add at 0")
                # a tick makes the submit say Add 1
                p.js("document.querySelector('form.picker tbody input').click()")
                p.until("document.querySelector('form.picker button[type=submit]').textContent === 'Add 1'", "the submit says Add 1")
                # an empty search says what to do
                p.js("(() => { const i = %s; i.value = 'zzzqqq'; i.dispatchEvent(new Event('input', {bubbles: true})); })()" % SEARCH)
                p.until(ROWS + " === 0", "nothing matches")
                self.assertIn(EMPTY, p.js(Q + ".textContent"), "the empty search words")
                words = p.js(ALL_WORDS)
                self.assertNotIn("find a field", words.lower())
                self.assertNotIn("Find a field", words)


if __name__ == "__main__":
    unittest.main()
