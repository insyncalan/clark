"""Hunt 19: the Use cases page keeps the keyboard's place when the button that had the focus leaves the page.

Run: python3 dev/run_tests.py test_use_cases_page_focus
Clear the filters (the empty state) and Restore (an archived use case's row) each disappear on use; the focus must not drop to the body.
"""
import unittest

from test_server import chrome
from test_use_cases_list import Setup, tearDownModule  # noqa: F401


class Focus(Setup):
    def test_clear_the_filters_hands_the_focus_to_the_search_box(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width=width)
                self.type_in(p, "#ucl-q", "nothing like this")
                p.until("!!document.querySelector('#usecases [data-clear-all]')", "the empty state")
                p.js("document.querySelector('[data-clear-all]').focus()")
                self.press(p, "Enter")
                p.until("document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 4", "all four are back")
                p.until("document.activeElement && document.activeElement.id === 'ucl-q'", "the search box has the focus")

    def test_restore_hands_the_focus_on(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                with self.store.step("dashboard", self.demo_user()) as st:
                    st.archive("use_cases", self.uc3)
                p = self.show(cdp, width=width)
                p.until("!!document.querySelector('[data-arch-toggle]')", "the footer")
                p.js("document.querySelector('[data-arch-toggle]').click()")
                p.until("!!document.querySelector('[data-restore]')", "the box")
                p.js("document.querySelector('[data-restore]').focus()")
                self.press(p, "Enter")
                p.until(f"!!document.querySelector('#usecases [data-uc=\"{self.uc3}\"]')", "restored")
                p.until(f"document.activeElement.closest && !!document.activeElement.closest('[data-uc=\"{self.uc3}\"]')", "the restored row's name has the focus")

    def demo_user(self):
        from _demo import USER
        return USER


if __name__ == "__main__":
    unittest.main()
