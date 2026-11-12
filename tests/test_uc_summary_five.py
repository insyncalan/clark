"""Row 1108: the dashboard's Use case summary shows the first 5 use cases, with a discreet "Show all N use cases" / "Show the first 5".

Run: python3 dev/run_tests.py test_uc_summary_five
Same harness and fictional data as test_glance_page. Laptop widths only: 1400 and 900 px.
"""
import unittest

from _publish import PublishedFile
from test_glance_page import Setup, USER, tearDownModule  # noqa: F401
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


if __name__ == "__main__":
    unittest.main()
