"""Row 1294 (mock-up A8, first slice): the ask clark page has two tabs, "All projects" and the open project's own, in a real browser at 1400 and 900.

Run: python3 dev/run_tests.py test_ask_tabs_1294
The project's tab is shown first and holds the switch, the folders and a "Used from All projects" card with a Change button; the All projects tab
holds the connections and the model. No tab shows money (rule 2 of the approved design: no cost limit, no monthly limit). Chrome is required."""
import os
import re
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from _editor_checks import for_project
from _paths import SRC
from test_ask_settings import make_db, service
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import page

WIDTHS = (1400, 900)
MONEY = re.compile(r"[$£€]|cost limit|monthly|spend|\bprice\b|\bbudget\b", re.I)

CONTRAST = """(() => {
  const rgb = s => s.match(/[\\d.]+/g).slice(0, 3).map(Number);
  const lum = c => { const [r, g, b] = c.map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  return [...document.querySelectorAll('[data-ask-tab]')].map(b => { const s = getComputedStyle(b); const f = lum(rgb(s.color)), g = lum(rgb(s.backgroundColor)); return (Math.max(f, g) + 0.05) / (Math.min(f, g) + 0.05); });
})()"""


class Tabs(unittest.TestCase):
    def setUp(self):
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(self.s.close)
        d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, d, True)
        self.s.httpd.app_settings = service(make_db(d))

    def show(self, cdp):
        self.sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
        js = lambda e: cdp.js(e, self.sid)          # noqa: E731
        self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-tab]')"), 20), "the tabs are on the page")
        return js

    def until(self, js, expr, what, seconds=20):
        self.assertTrue(wait(lambda: js(expr), seconds), f"{what}: {expr}")

    def test_two_tabs_all_projects_first_then_the_project_and_the_project_is_shown(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.assertEqual(js("[...document.querySelectorAll('[data-ask-tab]')].map(b => b.innerText)"), ["All projects", "ABC"])
            self.assertEqual(js("[...document.querySelectorAll('[data-ask-tab]')].map(b => b.getAttribute('aria-current'))"), [None, "true"])
            self.assertEqual(js("document.querySelector('#ask-tabs').getAttribute('aria-label')"), "Asking settings for")
            self.until(js, "!!document.querySelector('[data-ask-switch]') && !!document.querySelector('#ask-used-all')", "the project tab holds the switch and the Used from All projects card")
            self.assertFalse(js("!!document.querySelector('#ai-settings')"), "the connections are not on the project tab")
            self.assertEqual(js("document.querySelector('#ask-used-all h2').textContent"), "Used from All projects")
            self.assertTrue(js("['#ask-used-all', '#ask-used-all h2', '[data-ask-goall]'].every(q => document.querySelector(q).offsetHeight > 0)"), "the card and its Change button are on show, not hidden")
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.until(js, "document.documentElement.scrollWidth <= window.innerWidth", f"no sideways scroll at {w}")
                self.until(js, "[...document.querySelectorAll('[data-ask-tab]')].every(b => { const r = b.getBoundingClientRect(); return r.width > 0 && r.right <= window.innerWidth; })", f"both tabs inside the page at {w}")

    def test_the_all_projects_tab_holds_the_connections_and_not_the_projects_own_parts(self):
        with chrome() as cdp:
            js = self.show(cdp)
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.until(js, "!!document.querySelector('#ai-settings') && !!document.querySelector('#ask-all')", "the All projects tab shows")
            self.assertEqual(js("[...document.querySelectorAll('[data-ask-tab]')].map(b => b.getAttribute('aria-current'))"), ["true", None])
            self.assertFalse(js("!!document.querySelector('[data-ask-switch], #ask-folders, #ask-folders-none, [data-ask-choose], #ask-used-all')"), "the project's own parts are not on the All projects tab")
            self.assertEqual(js("document.querySelectorAll('#ask-settings-h').length"), 1, "one first heading for Skip to settings")
            js("document.querySelector('[data-ask-tab=project]').click()")
            self.until(js, "!!document.querySelector('[data-ask-switch]') && !document.querySelector('#ai-settings')", "back on the project tab")
            self.assertEqual(js("document.querySelectorAll('#ask-settings-h').length"), 1)

    def test_change_on_the_project_tab_opens_the_all_projects_tab_and_the_tabs_work_with_the_keyboard(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.until(js, "!!document.querySelector('[data-ask-goall]')", "the Change button")
            self.assertEqual(js("document.querySelector('[data-ask-goall]').innerText"), "Change")
            js("document.querySelector('[data-ask-goall]').click()")
            self.until(js, "!!document.querySelector('#ai-settings') && !document.querySelector('[data-ask-switch]')", "Change opens All projects")
            # the tabs are real buttons: focusable, with their names, and Enter or Space (a click on a button) is what presses them
            self.assertEqual(js("[...document.querySelectorAll('[data-ask-tab]')].every(b => b.tagName === 'BUTTON' && b.type === 'button' && b.tabIndex === 0)"), True)
            js("document.querySelector('[data-ask-tab=project]').focus()")
            self.assertEqual(js("document.activeElement.innerText"), "ABC")

    def test_turning_asking_off_in_the_project_tab_changes_nothing_on_the_all_projects_tab(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.until(js, "(document.querySelector('[data-ask-switch]') || {disabled: true}).disabled === false", "the switch can be pressed")
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.until(js, "!!document.querySelector('#ai-settings') && !/Checking/i.test(document.querySelector('#ai-settings').innerText)", "All projects, its first read settled")
            before = js("document.querySelector('#ai-settings').innerText")
            js("window.__ask_seen_checking = false; new MutationObserver(() => { if (/Checking/i.test(document.querySelector('#ask-state') ? document.querySelector('#ask-state').textContent : '')) window.__ask_seen_checking = true; }).observe(document.body, {subtree: true, childList: true, characterData: true, attributes: true})")
            js("document.querySelector('[data-ask-tab=project]').click()")
            self.until(js, "(document.querySelector('[data-ask-switch]') || {disabled: true}).disabled === false", "the switch")
            time.sleep(0.5)      # the read, if one were made, shows its Checking line within this time
            self.assertFalse(js("window.__ask_seen_checking"), "showing the project tab again does not read the switch again (no Checking line)")
            js("document.querySelector('[data-ask-switch]').click()")
            self.until(js, "document.querySelector('[data-ask-switch]').getAttribute('aria-pressed') === 'false'", "asking off for the project")
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.until(js, "!!document.querySelector('#ai-settings') && !/Checking/i.test(document.querySelector('#ai-settings').innerText)", "All projects again, settled")
            self.assertEqual(js("document.querySelector('#ai-settings').innerText"), before, "the connections read the same")

    def test_no_tab_shows_money_and_no_file_path_or_prototype_note(self):
        with chrome() as cdp:
            js = self.show(cdp)
            for tab, mark in (("project", "#ask-used-all"), ("all", "#ai-settings")):
                js(f"document.querySelector('[data-ask-tab={tab}]').click()")
                self.until(js, f"!!document.querySelector('{mark}')", f"the {tab} tab shows")
                text = js("document.querySelector('.set-cards').innerText")
                self.assertFalse(MONEY.search(text), f"money wording on the {tab} tab: {MONEY.search(text)}")
                self.assertNotRegex(text, r"(?i)prototype|mock-?up|\.html|\.jsx|/Users/|/home/")

    def test_the_sources_name_no_money_and_the_tab_words_are_plain(self):
        src = (Path(page.PAGE).parent / "src" / "edit" / "AskSettings.jsx").read_text(encoding="utf-8")
        words = re.findall(r'"([^"\n]*)"', src[src.index("const ALL = "):src.index("const NOT_READY")])
        self.assertFalse([w for w in words if MONEY.search(w)], words)
        self.assertIn("Used from All projects", src)


    def test_both_tabs_read_in_light_and_dark_at_1400_and_900(self):
        for scheme in ("light", "dark"):
            for w in WIDTHS:
                with self.subTest(scheme=scheme, width=w), chrome() as cdp:
                    js = self.show(cdp)
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, self.sid)
                    self.until(js, "document.documentElement.scrollWidth <= window.innerWidth", f"no sideways scroll, {scheme} {w}")
                    ratios = js(CONTRAST)
                    self.assertEqual(len(ratios), 2)
                    self.assertTrue(all(r >= 4.5 for r in ratios), f"tab text contrast {ratios} in {scheme} at {w}")


class TabHeight(unittest.TestCase):
    """Row 1351: the tab pills are 29 px high in Classic and still 36 px in Cards, at 1400 and 900, light and dark."""

    def height(self, theme, width, scheme):
        s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=theme))
        self.addCleanup(s.close)
        d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, d, True)
        s.httpd.app_settings = service(make_db(d))
        with chrome() as cdp:
            sid = navigate(cdp, s.port, for_project("#settings&p=ABC&s=claude"))
            js = lambda e: cdp.js(e, sid)          # noqa: E731
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-tab]')"), 20), "the tabs are on the page")
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
            js("document.querySelectorAll('[data-ask-tab]').forEach(b => { b.style.transition = 'none'; })")
            return js("[...document.querySelectorAll('[data-ask-tab]')].map(b => b.getBoundingClientRect().height)")

    def test_classic_29_and_cards_36(self):
        for scheme in ("light", "dark"):
            for w in WIDTHS:
                with self.subTest(scheme=scheme, width=w):
                    self.assertEqual(self.height("prototype-2.0", w, scheme), [29, 29], f"Classic tab pills, {scheme} {w}")
                    self.assertEqual(self.height(None, w, scheme), [36, 36], f"Cards tab pills, {scheme} {w}")


if __name__ == "__main__":
    unittest.main()
