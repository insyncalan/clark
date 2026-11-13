"""Row 1108: the dashboard's Use case summary shows the first 5 use cases, with a discreet "Show all N use cases" / "Show the first 5".

Run: python3 dev/run_tests.py test_uc_summary_five
Same harness and fictional data as test_glance_page. Laptop widths only: 1400 and 900 px.
"""
import json
import unittest

from _publish import PublishedFile
from test_glance_page import Setup, USER, tearDownModule  # noqa: F401
from _new_page import reload_to_new_page
from test_server import chrome

ROWS = "document.querySelectorAll('.ucrows > .ucrow').length"
BUTTON = "(document.querySelector('[data-ucall]') || {}).textContent"


class FirstFive(Setup):
    def more(self, n):
        with self.store.step("dashboard", USER) as st:
            for i in range(n):
                st.create("use_cases", {"project": "ABC", "title": f"Extra {i}", "status": "On track", "ref": f"3.{i}", "source": "demo"})

    def test_with_five_or_fewer_there_is_no_control(self):
        self.more(3)                                                  # 2 + 3 = 5
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertEqual(p.js(ROWS), 5)
            self.assertIsNone(p.js(BUTTON))

    def test_with_more_the_first_five_show_and_the_control_expands_and_reduces_while_the_count_stays(self):
        self.more(4)                                                  # 2 + 4 = 6
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.assertEqual(p.js(ROWS), 5)
                self.assertEqual(p.js(BUTTON), "Show all 6 use cases")
                self.assertEqual(p.js("document.querySelector('.uctotal').textContent"), "6 use cases", "the count covers every use case")
                self.assertEqual(p.js("document.querySelectorAll('.meter i').length"), 6, "so does the meter")
                p.js("document.querySelector('[data-ucall]').click()")
                p.until(f"{ROWS} === 6", "all shown")
                self.assertEqual(p.js(BUTTON), "Show the first 5")
                p.js("document.querySelector('[data-ucall]').click()")
                p.until(f"{ROWS} === 5", "reduced")

    def test_the_editor_keeps_show_all_across_a_reload(self):
        self.more(4)
        with chrome() as cdp:
            p = self.show(cdp)
            p.js("document.querySelector('[data-ucall]').click()")
            p.until(f"{ROWS} === 6", "all shown")
            self.assertEqual(p.js("localStorage.getItem('clark.ucAll')"), "true")
            p.reload()
            p.until("!!document.querySelector('.uc')", "the summary drew again")
            self.assertEqual(p.js(ROWS), 6, "the choice came back")
            self.assertEqual(p.js(BUTTON), "Show the first 5")
            self.assertIsNone(p.js("document.querySelector('[data-ucall]').getAttribute('aria-expanded')"), "the label says the state, so no aria-expanded")


class PublishedFive(PublishedFile, Setup):
    more = FirstFive.more

    def test_a_file_shows_five_remembers_nothing_and_ignores_a_stored_choice(self):
        self.more(4)
        path = self.publish()
        with chrome() as cdp:
            p = self.draw(cdp, path)
            p.js("localStorage.setItem('clark.ucAll', 'true')")
            p.reload()
            self.assertEqual(p.js(ROWS), 5, "an editor's stored choice does not reach a file")
            p.js("document.querySelector('[data-ucall]').click()")
            p.until(f"{ROWS} === 6", "all shown")
            p.js("localStorage.removeItem('clark.ucAll')")
            p.js("document.querySelector('[data-ucall]').click()")
            p.until(f"{ROWS} === 5", "reduced")
            self.assertEqual(p.js("Object.keys(localStorage).filter(k => k.indexOf('clark.') === 0 && k.indexOf('ucAll') >= 0)"), [], "nothing was remembered")

    def test_printing_a_file_shows_every_row_and_no_button_while_the_count_stays(self):
        self.more(4)
        path = self.publish()
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.draw(cdp, path, width)
                self.assertEqual(p.js(ROWS), 5)
                cdp.call("Emulation.setEmulatedMedia", {"media": "print"}, p.sid)
                p.js("window.dispatchEvent(new Event('beforeprint'))")
                p.until(f"{ROWS} === 6", "every use case is on the paper")
                self.assertEqual(p.js("getComputedStyle(document.querySelector('[data-ucall]')).display"), "none")
                self.assertEqual(p.js("document.querySelector('.uctotal').textContent"), "6 use cases")
                self.assertEqual(p.js("document.querySelectorAll('.meter i').length"), 6)
                p.js("window.dispatchEvent(new Event('afterprint'))")
                p.until(f"{ROWS} === 5", "the screen is as it was")


    def test_the_choice_is_kept_in_this_browser_and_the_control_says_whether_all_are_shown(self):
        self.more(4)
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertEqual(p.js("document.querySelector('[data-ucall]').getAttribute('aria-expanded')"), None, "Show all carries no aria-expanded")
            p.js("document.querySelector('[data-ucall]').click()")
            p.until(f"{ROWS} === 6", "all shown")
            self.assertEqual(p.js("document.querySelector('[data-ucall]').getAttribute('aria-expanded')"), None)
            self.assertEqual(p.js("window.localStorage.getItem('clark.ucAll')"), "true", "the choice is remembered")
            reload_to_new_page(p.js, f"{ROWS} === 6 && !!document.querySelector('[data-ucall]')", "still all shown after a reload")
            self.assertEqual(p.js(BUTTON), "Show the first 5")
            p.js("document.querySelector('[data-ucall]').click()")
            p.until(f"{ROWS} === 5", "reduced")
            self.assertEqual(p.js("window.localStorage.getItem('clark.ucAll')"), "false")
            reload_to_new_page(p.js, f"{ROWS} === 5 && !!document.querySelector('[data-ucall]')", "still the first five after a reload")


class AddedBeyondFive(Setup):
    """A use case put on the page that sorts after the fifth is not left out of sight: the list opens to show it."""

    more = FirstFive.more

    def click(self, p, selector):
        p.js(f"document.querySelector({json.dumps(selector)}).scrollIntoView({{block: 'center'}})")
        x, y, _ = p.box(selector)
        p.mouse("mouseMoved", x, y)
        p.mouse("mousePressed", x, y, 1)
        p.mouse("mouseReleased", x, y)

    def type_in(self, p, selector, text):
        p.js(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); e.focus(); e.select(); }})()")
        p.cdp.call("Input.insertText", {"text": text}, p.sid)

    def test_a_use_case_added_and_put_on_the_page_past_the_fifth_opens_the_whole_list(self):
        self.more(4)                                                  # 6 on the page, the first five show
        for n, width in enumerate((1400, 900)):                      # the store is shared by the two widths: 7, then 8 on the page
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.js("document.querySelector('[data-mode=edit]').click()")
                p.until("!!document.querySelector('#ucAdd')", "Edit")
                self.assertEqual(p.js(ROWS), 5)
                self.click(p, "#ucAdd")
                p.until("!!document.querySelector('#ucF')", "the box")
                ref = f"9.{width}"
                self.type_in(p, "#ucI", ref)
                self.type_in(p, "#ucT", f"Late {ref}")
                p.js("document.querySelector('#ucF').requestSubmit()")
                p.until("!document.querySelector('#ucF')", "the box closed")
                p.until("(document.querySelector('.toast-text') || {}).textContent.indexOf('added, hidden') > 0", "the added toast")
                made = {r["ref"]: r for r in self.store.read("use_cases", "ABC")}[ref]
                self.click(p, "[data-uc-back]")
                p.until("!!document.querySelector('form.picker')", "the picker")
                p.js("document.querySelector('form.picker .pick input[value=\"%s\"]').click()" % made["id"])
                p.js("document.querySelector('form.picker button[type=submit]').click()")
                p.until("!document.querySelector('form.picker')", "the picker closed")
                p.until(f"{ROWS} === {7 + n}", "all are shown, so the new one is not out of sight")
                self.assertEqual(p.js(BUTTON), "Show the first 5")


if __name__ == "__main__":
    unittest.main()
