"""Row 1114: the published Use cases tab draws the editor's list read only: tabs with counts (no On the dashboard tab), sort,
Group by with groups that shut, a count line and the filtered-empty state with Clear.

Run: python3 dev/run_tests.py test_publish_uc_list_1114
"""
import copy
import tempfile
import unittest
from pathlib import Path

import _publish_fixture as fx  # noqa: E402
from clark import page, publish  # noqa: E402
from test_publish import EMPTY_BRANDING, chrome, opened, wait  # noqa: E402
import test_server  # noqa: E402,F401  (this file drives Chrome through test_publish: it is in the browser tier)


def made(extra=True):
    plant = fx.load()
    d = plant["data"]
    if extra:
        row = copy.deepcopy(d["use_cases"][0])
        row.update(id="PUB-U-006", title="ZQ-SECOND-USECASE", status="High risk", ref="0.5", sort_order=6)
        d["use_cases"].append(row)
    pub = publish.select(fx.inputs(plant))
    return publish.render(pub, page.page_html(EMPTY_BRANDING), plant["as_at"], pub["data"]["project"]["name"])


class RealBrowser(unittest.TestCase):
    def go(self, cdp, text, tmp):
        path = Path(tmp) / "r.html"
        path.write_text(text, encoding="utf-8")
        sid = opened(cdp, path.as_uri())
        self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"))
        cdp.js("document.querySelector('[data-view=usecases]').click()", sid)
        self.assertTrue(wait(lambda: cdp.js("document.querySelector('h1').textContent", sid) == "Use cases"))
        return sid

    def test_tabs_sort_group_count_and_empty(self):
        with tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
            sid = self.go(cdp, made(), tmp)
            js = lambda s: cdp.js(s, sid)  # noqa: E731
            self.assertEqual(js("[...document.querySelectorAll('[data-tab]')].map(t => t.dataset.tab).join()"), "all,committed,risk")
            self.assertEqual(js("document.querySelector('[data-tab=all] em').textContent"), "2")
            self.assertEqual(js("document.querySelector('[data-tab=risk] em').textContent"), "1")
            self.assertEqual(js("document.querySelector('#ucp-count').textContent"), "2 use cases")
            self.assertEqual(js("document.querySelector('.ucp .num').textContent"), "0.5")          # Ref order: 0.5 before the fixture's
            js("document.querySelector('[data-sort=status]').click()")
            self.assertEqual(js("document.querySelector('.ucp-title').textContent"), "ZQ-SECOND-USECASE")  # High risk first
            js("document.querySelector('[data-tab=risk]').click()")
            self.assertEqual(js("document.querySelectorAll('.ucp').length"), 1)
            self.assertEqual(js("document.querySelector('#ucp-count').textContent"), "1 use case")
            js("document.querySelector('[data-tab=committed]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-empty] [data-clear-all]')")))
            js("document.querySelector('[data-clear-all]').click()")
            self.assertEqual(js("document.querySelectorAll('.ucp').length"), 2)
            self.assertEqual(js("document.querySelector('[data-tab=all]').getAttribute('aria-pressed')"), "true")

    def test_group_by_status_and_a_group_shuts(self):
        with tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
            sid = self.go(cdp, made(), tmp)
            js = lambda s: cdp.js(s, sid)  # noqa: E731
            js("document.querySelector('#ucp-group, [aria-label^=\"Group by\"]').click()")
            self.assertTrue(wait(lambda: js("!![...document.querySelectorAll('[role^=menuitem]')].find(e => e.textContent.trim() === 'Status')")))
            self.assertFalse(js("[...document.querySelectorAll('[role^=menuitem]')].some(e => e.textContent.includes('On the dashboard'))"))
            js("[...document.querySelectorAll('[role^=menuitem]')].find(e => e.textContent.trim() === 'Status').click()")
            self.assertTrue(wait(lambda: js("document.querySelectorAll('.ucp-group').length") == 2))
            js("document.querySelector('.ucp-group .grp-b').click()")
            self.assertEqual(js("document.querySelectorAll('.ucp').length"), 1)
            self.assertEqual(js("document.querySelector('.ucp-group .grp-b').getAttribute('aria-expanded')"), "false")

    def test_a_file_with_no_use_cases_keeps_its_words(self):
        plant = fx.load()
        plant["data"]["use_cases"] = []
        pub = publish.select(fx.inputs(plant))
        self.assertFalse(pub["data"].get("use_case_pages"))
        # no list, no tabs: the words stay with the component
        src = (Path(__file__).resolve().parent.parent / "src/clark/page/src/components/UseCasesTab.jsx").read_text(encoding="utf-8")
        self.assertIn("No use cases are shared in this report.", src)


if __name__ == "__main__":
    unittest.main()
