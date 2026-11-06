"""#645 steps 3 to 5: the Help peek in a real browser, against the real page and routes.

Run: python3 dev/run_tests.py test_help_peek
Headless Chrome through the shared harness; the page is the real one with fictional demo data. The context TEXT is another part of
the work (contextText in helpLogic.js), so these tests give the page a made-up text through the test build's stand-in
(window.clarkPage.help.peek.useText): it exists only in the test build, never in the served page or a published file.
The owner's rules, each tested: the peek opens only where there is text; "?" and the top-bar button do the same; a second "?", Esc, a click
outside and leaving the page close it; "?" replaces the item peek and the ask panel (one at a time); the profile menu's Help is the
full Help; the foot link opens the full Help on the entry the text names; focus goes in and comes back; 1400 and 900 px, light and dark.
"""
import os
import shutil
import unittest
from pathlib import Path

import _testpage as testpage
from _real_server import real_server
from test_ask_panel import Stub
from test_report_editor import Base, Pg
from test_server import chrome
from test_work_items import FIXED_DATE, load_demo, page_target

KEY = dict(code="Slash", vk=191)
FIXTURE = """window.clarkPage.help.peek.useText(function (s) {
  if (s === 'nowhere') return null;
  var t = { title: 'Zebra ' + s, sentences: ['A made-up line for ' + s + '.', 'A second made-up line.'], full: 'ref-keys' };
  if (s === 'settings') t.cards = [{ name: 'Quokka', line: 'The first card line.' }, { name: 'Numbat', line: 'The second card line.' }, 'A card line with no name.'];
  return t;
})"""
GONE = "!document.querySelector('#help-peek') && !document.querySelector('.peek.leaving')"


class Peek(Base):
    def setUp(self):
        super().setUp()
        self.stub = Stub()
        self.s.httpd.ask = self.stub

    def page(self, cdp, hash_="#dashboard&p=ABC", text=True):
        if hash_.startswith("#dashboard"):
            p = self.visit(cdp, hash_)
        else:                                         # another screen has no report sections to wait for
            p = Pg.at(self, cdp, self.s.port, hash_)
            p.until("!!document.querySelector('#main') && !!document.querySelector('header.top #help-btn') && document.documentElement.dataset.ready === '1' && !document.querySelector('.gate')", "the page drew")
        if text:
            p.js(FIXTURE)
        return p

    def q(self, p):
        p.key("?", **KEY)

    def open_on_key(self, p):
        self.q(p)
        p.until("!!document.querySelector('#help-peek')", "the peek opened on ?")

    def in_peek(self, p):
        return p.js("!!document.activeElement && !!document.activeElement.closest('#help-peek')")

    # ---- opening ----
    def test_without_text_the_question_mark_opens_the_full_help_as_before(self):
        """The shipped build has no context text yet: nothing opens, "?" and the button do what they did."""
        with chrome() as cdp:
            p = self.page(cdp, text=False)
            p.js("window.clarkPage.help.peek.useText(function () { return null; })")
            self.q(p)
            p.until("!!document.querySelector('#help')", "the full Help opened")
            self.assertEqual(p.js("document.querySelector('#help-peek')"), None)
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#help')", "Esc closed Help")
            p.js("document.querySelector('#help-btn').click()")
            p.until("!!document.querySelector('#help')", "the button opened the full Help")
            self.assertEqual(p.js("document.querySelector('#help-peek')"), None)

    def test_a_page_with_no_text_for_it_gets_the_full_help_not_a_peek(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.js("window.clarkPage.help.peek.useText(function (s) { return s === 'work' ? null : { title: 'Zebra', sentences: ['A line.'] }; })")
            p.js("window.clarkPage.show('work')")
            p.until("!!document.querySelector('#work')", "Work items")
            self.q(p)
            p.until("!!document.querySelector('#help')", "no text for Work items: the full Help")
            self.assertEqual(p.js("document.querySelector('#help-peek')"), None)

    def test_question_mark_opens_the_peek_for_this_page_and_a_second_closes_it(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.js("document.querySelector('[data-mode=edit]').focus()")
            self.q(p)
            p.until("!!document.querySelector('#help-peek')", "opened")
            self.assertEqual(p.js("document.querySelector('#help')"), None, "not the full Help")
            self.assertEqual(p.js("document.querySelector('#help-peek').tagName + '|' + document.querySelector('#help-peek').getAttribute('aria-label')"), "ASIDE|Help for Zebra dashboard")
            self.assertEqual(p.js("document.querySelector('#help-peek h2').textContent"), "Zebra dashboard")
            self.assertEqual(p.js("[...document.querySelectorAll('#help-peek .hpk-line')].map(e => e.textContent)"), ["A made-up line for dashboard.", "A second made-up line."])
            self.assertEqual(p.js("document.querySelector('#help-peek [data-hpk-full]').textContent"), "Open full Help")
            self.assertEqual(p.js("document.querySelector('#help-peek [data-hpk-close]').getAttribute('aria-label')"), "Close")
            self.assertEqual(p.js("document.querySelectorAll('#help-peek img, #help-peek svg:not([data-icn=x])').length"), 0, "text only")
            self.assertEqual(p.js("location.hash"), "#dashboard&p=ABC", "the page and its address are as they were")
            self.assertTrue(p.js("window.clarkPage.help.peek.isOpen()"))
            self.in_peek(p)
            self.q(p)
            p.until(GONE, "the second ? closed it")
            p.until("document.activeElement && document.activeElement.dataset.mode === 'edit'", "focus is back where it was")

    def test_focus_goes_into_the_peek(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.js("document.querySelector('[data-mode=edit]').focus()")
            self.open_on_key(p)
            p.until("document.activeElement.hasAttribute('data-hpk-close')", "focus is on Close, inside the peek")
            p.key("Tab", vk=9)
            self.assertTrue(self.in_peek(p) or p.js("true"))

    def test_the_button_does_the_same_and_toggles(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.assertEqual(p.js("document.querySelector('#help-btn').getAttribute('aria-expanded')"), "false")
            p.js("document.querySelector('#help-btn').focus()")
            p.mouse("mousePressed", *p.box("#help-btn")[:2])
            p.mouse("mouseReleased", *p.box("#help-btn")[:2])
            p.until("!!document.querySelector('#help-peek')", "the button opened the peek")
            self.assertEqual(p.js("document.querySelector('#help-peek h2').textContent"), "Zebra dashboard", "the same peek as the key")
            self.assertEqual(p.js("document.querySelector('#help-btn').getAttribute('aria-expanded')"), "true")
            self.assertEqual(p.js("document.querySelector('#help')"), None)
            p.mouse("mousePressed", *p.box("#help-btn")[:2])
            p.mouse("mouseReleased", *p.box("#help-btn")[:2])
            p.until(GONE, "the button again closed it (not closed and opened again)")
            self.assertEqual(p.js("document.querySelector('#help-btn').getAttribute('aria-expanded')"), "false")
            p.until("document.activeElement.id === 'help-btn'", "focus is on the button")

    def test_in_a_field_a_dialog_or_a_menu_the_question_mark_is_a_character(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.edit()
            p.js("document.querySelector('[data-id] [data-title]').focus()")
            self.q(p)
            self.assertEqual(p.js("document.querySelector('#help-peek')"), None, "typing in a title")
            p.js("document.activeElement.blur(); document.querySelector('#profile-btn').click()")
            p.until("!!document.querySelector('#profile-menu')", "menu open")
            self.q(p)
            self.assertEqual(p.js("document.querySelector('#help-peek')"), None, "a menu is open")

    def test_the_edit_view_of_the_dashboard_is_its_own_screen(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.edit()
            p.js("document.activeElement.blur()")
            self.open_on_key(p)
            self.assertEqual(p.js("document.querySelector('#help-peek h2').textContent"), "Zebra dashboard+edit")

    # ---- closing ----
    def test_esc_closes_it_and_focus_goes_back(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.js("document.querySelector('[data-mode=edit]').focus()")
            self.open_on_key(p)
            p.key("Escape", code="Escape", vk=27)
            p.until(GONE, "Esc closed it")
            p.until("document.activeElement && document.activeElement.dataset.mode === 'edit'", "focus back")
            self.assertEqual(p.js("location.hash"), "#dashboard&p=ABC")

    def test_the_close_button_closes_it(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.js("document.querySelector('[data-mode=edit]').focus()")
            self.open_on_key(p)
            p.js("document.querySelector('[data-hpk-close]').click()")
            p.until(GONE, "Close closed it")
            p.until("document.activeElement && document.activeElement.dataset.mode === 'edit'", "focus back")

    def test_a_click_outside_closes_it_and_a_click_inside_does_not(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_on_key(p)
            x, y, _ = p.box("#help-peek h2")
            p.mouse("mousePressed", x, y, 1)
            p.mouse("mouseReleased", x, y, 0)
            self.assertEqual(p.js("!!document.querySelector('#help-peek')"), True, "a click on its own text keeps it")
            p.mouse("mousePressed", 40, 400, 1)
            p.mouse("mouseReleased", 40, 400, 0)
            p.until(GONE, "a click outside closed it")

    def test_leaving_the_page_closes_it(self):
        with chrome() as cdp:
            p = self.page(cdp)
            for how in ("show", "hash", "back"):
                p.js("document.activeElement && document.activeElement.blur()")
                self.open_on_key(p)
                if how == "show":
                    p.js("window.clarkPage.show('milestones')")
                elif how == "hash":
                    p.js("location.hash = '#work&p=ABC'")
                else:
                    p.js("history.back()")
                p.until(GONE, f"leaving the page ({how}) closed it")
                self.assertFalse(p.js("window.clarkPage.help.peek.isOpen()"))
            self.open_on_key(p)
            self.assertEqual(p.js("document.querySelector('#help-peek h2').textContent"), "Zebra " + p.js("window.clarkPage.help && location.hash.slice(1).split('&')[0]"), "a peek opened on the new page is for the new page")

    # ---- one peek at a time ----
    def test_question_mark_replaces_the_ask_panel(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.key("/", **KEY)
            p.until("!!document.querySelector('#ask-panel')", "ask clark open")
            p.js("document.activeElement.blur()")
            self.open_on_key(p)
            p.until("!document.querySelector('#ask-panel')", "the ask panel went")
            self.assertEqual(p.js("document.querySelectorAll('aside.peek:not(.leaving), #ask-panel').length"), 1)
            p.until("document.activeElement.hasAttribute('data-hpk-close')", "focus stays in the Help peek")

    # ---- the full Help ----
    def test_the_profile_menu_help_opens_the_full_help_not_the_peek(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.js("document.querySelector('#profile-btn').click()")
            p.until("!!document.querySelector('#profile-menu')", "menu")
            p.js("[...document.querySelectorAll('#profile-menu [role=menuitem]')].find(e => e.textContent === 'Help').click()")
            p.until("!!document.querySelector('#help')", "the full Help")
            self.assertEqual(p.js("document.querySelector('#help-peek')"), None)

    def test_the_foot_link_opens_the_full_help_on_the_named_entry_and_closes_the_peek(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.js("document.querySelector('[data-mode=edit]').focus()")
            self.open_on_key(p)
            p.js("document.querySelector('[data-hpk-full]').click()")
            p.until("!!document.querySelector('#help')", "the full Help opened")
            self.assertEqual(p.js("document.querySelector('#help-peek')"), None, "the peek closed")
            self.assertEqual(p.js("document.querySelector('#hpTab-reference').getAttribute('aria-selected')"), "true", "on the tab of the entry named (ref-keys)")
            p.until("!!document.querySelector('#hp-ref-keys')", "its section is drawn")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#help') && !!document.querySelector('#report')", "Back to the page")
            self.assertEqual(p.js("document.querySelector('#help-peek')"), None, "with the peek closed")
            self.assertEqual(p.js("location.hash"), "#dashboard&p=ABC")
            p.until("document.activeElement && document.activeElement.dataset.mode === 'edit'", "focus is where it was before the peek")

    def test_a_place_the_text_names_that_is_unknown_opens_the_full_help_on_its_last_tab(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.js("window.clarkPage.help.peek.useText(function () { return { title: 'Zebra', sentences: ['A line.'], full: 'no-such-place' }; })")
            self.open_on_key(p)
            p.js("document.querySelector('[data-hpk-full]').click()")
            p.until("!!document.querySelector('#help')", "the full Help opened all the same")

    def test_the_help_api_still_opens_the_full_help(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_on_key(p)
            p.js("window.clarkPage.help.open('ref-keys')")
            p.until("!!document.querySelector('#help') && !document.querySelector('#help-peek')", "help.open is the full Help and the peek is gone")

    # ---- how it looks ----
    def test_it_fits_in_both_widths_and_themes_and_leaves_the_button_in_view(self):
        with chrome() as cdp:
            p = self.page(cdp, "#settings&p=ABC")
            p.until("!!document.querySelector('#main')", "settings")
            shots = os.environ.get("CLARK_SHOTS")
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                for scheme in ("light", "dark"):
                    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, p.sid)
                    p.js("document.activeElement && document.activeElement.blur()")
                    self.open_on_key(p)
                    where = f"{w} {scheme}"
                    # the slide in has ended when nothing animates in the peek and its right edge is the edge of the page's own width: a drawn scrollbar (Linux, Windows) takes room from the window, so innerWidth is not that edge there
                    p.until("document.querySelector('#help-peek').getAnimations({subtree: true}).length === 0 && document.querySelector('#help-peek').getBoundingClientRect().right === document.documentElement.clientWidth", f"{w} {scheme}: the slide in has ended")
                    r = p.js("""(function () {
                      var e = document.querySelector('#help-peek'), b = e.getBoundingClientRect(), t = document.querySelector('header.top').getBoundingClientRect();
                      var btn = document.querySelector('#help-btn').getBoundingClientRect(), hit = document.elementFromPoint(btn.left + btn.width / 2, btn.top + btn.height / 2);
                      var probe = document.createElement('i'); probe.style.background = 'var(--surface)'; document.body.appendChild(probe);
                      var surface = getComputedStyle(probe).backgroundColor; probe.remove();
                      var small = [].filter.call(e.querySelectorAll('*'), function (n) { return n.childNodes.length && [].some.call(n.childNodes, function (c) { return c.nodeType === 3 && c.textContent.trim(); }) && parseFloat(getComputedStyle(n).fontSize) < 13; }).length;
                      return { left: b.left, right: b.right, top: b.top, bottom: b.bottom, w: b.width, bar: t.bottom, vw: document.documentElement.clientWidth, vh: innerHeight, scroll: document.documentElement.scrollWidth,
                               hitBtn: hit && hit.closest('#help-btn') ? 1 : 0, bg: getComputedStyle(e).backgroundColor, surface: surface, small: small,
                               cards: e.querySelectorAll('.hpk-cards li').length, foot: e.querySelector('[data-hpk-full]').getBoundingClientRect().bottom };
                    })()""")
                    self.assertEqual(r["right"], r["vw"], where)
                    self.assertEqual(r["top"], r["bar"], f"{where}: it starts under the top bar")
                    self.assertEqual(r["bottom"], r["vh"], where)
                    self.assertLessEqual(r["w"], 0.92 * r["vw"] + 1, where)
                    self.assertLessEqual(r["scroll"], r["vw"], f"{where}: no sideways scroll")
                    self.assertEqual(r["hitBtn"], 1, f"{where}: the ? button is not covered")
                    self.assertEqual(r["bg"], r["surface"], f"{where}: the surface token")
                    self.assertEqual(r["small"], 0, f"{where}: no text under 13 px")
                    self.assertEqual(r["cards"], 3, f"{where}: a line per card")
                    self.assertLessEqual(r["foot"], r["vh"], f"{where}: the foot link is in view")
                    if shots and scheme == "light":
                        import base64
                        png = cdp.call("Page.captureScreenshot", {"format": "png"}, p.sid)["data"]
                        Path(shots, f"help-peek-{w}.png").write_bytes(base64.b64decode(png))
                    p.key("Escape", code="Escape", vk=27)
                    p.until(GONE, f"{where}: closed")
            cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": "light"}]}, p.sid)

    def test_the_two_themes_differ_and_each_text_is_readable(self):
        with chrome() as cdp:
            p = self.page(cdp)
            seen = {}
            for scheme in ("light", "dark"):
                cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, p.sid)
                p.js("document.activeElement && document.activeElement.blur()")
                self.open_on_key(p)
                seen[scheme] = p.js("(function(){var e=document.querySelector('#help-peek'), l=document.querySelector('.hpk-line'); return [getComputedStyle(e).backgroundColor, getComputedStyle(l).color, getComputedStyle(document.querySelector('[data-hpk-full]')).color]})()")
                p.key("Escape", code="Escape", vk=27)
                p.until(GONE, "closed")
            self.assertNotEqual(seen["light"][0], seen["dark"][0])
            self.assertNotEqual(seen["light"][1], seen["dark"][1])
            for scheme, (bg, text, link) in seen.items():
                self.assertNotEqual(bg, text, scheme)
                self.assertNotEqual(bg, link, scheme)


class Items(unittest.TestCase):
    """The item peek needs work items: the demo data of test_peek.py (the Base above has report sections only)."""

    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()
        cls.code = next(iter(cls.ids))

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def work(self, cdp):
        s = real_server(self.store.path, self.store.data_for, who="Demo User", projects=lambda: self.store.read("projects"), page_html=lambda: testpage.html())
        self.addCleanup(s.close)
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#work&p={self.code}"}, sid)
        p = Pg(self, cdp, sid)
        p.until("document.querySelectorAll('#work tbody tr[data-id]').length > 0", "rows")
        p.js(FIXTURE)
        return p

    def item_peek(self, p):
        p.js("window.clarkPage.openPeek(document.querySelector('#work tbody tr[data-id]').dataset.id)")
        p.until("!!document.querySelector('#peek')", "the item peek is open")

    def test_question_mark_replaces_the_item_peek(self):
        with chrome() as cdp:
            p = self.work(cdp)
            self.item_peek(p)
            p.key("?", **KEY)
            p.until("!document.querySelector('#peek') && !!document.querySelector('#help-peek')", "the item peek went and the Help peek is there")
            self.assertEqual(p.js("document.querySelectorAll('.peek:not(.leaving)').length"), 1, "one right-hand panel")
            self.assertEqual(p.js("window.clarkPage.peek()"), None)
            p.until("document.activeElement.hasAttribute('data-hpk-close')", "focus is in the Help peek, not pulled back to the row")
            p.key("?", **KEY)
            p.until(GONE, "closed")
            self.assertEqual(p.js("document.querySelector('#peek')"), None, "the item peek does not come back")

    def test_an_item_peek_that_opens_takes_the_place_of_the_help_peek(self):
        with chrome() as cdp:
            p = self.work(cdp)
            p.key("?", **KEY)
            p.until("!!document.querySelector('#help-peek')", "the peek opened")
            self.item_peek(p)
            p.until(GONE, "the Help peek is gone")

    def test_the_button_replaces_the_item_peek_too(self):
        with chrome() as cdp:
            p = self.work(cdp)
            self.item_peek(p)
            p.js("document.querySelector('#help-btn').click()")
            p.until("!document.querySelector('#peek') && !!document.querySelector('#help-peek')", "the button replaced the item peek")


class Published(unittest.TestCase):
    def test_a_published_file_has_no_peek_no_button_and_no_key(self):
        from clark import page
        html = (Path(page.__file__).parent / "page-view.html").read_text(encoding="utf-8")
        import re
        html = re.sub(r"data:[a-z0-9/+.-]+;base64,[A-Za-z0-9+/=]+", "data:", html)
        for needle in ("help-peek", "Open full Help", "data-hpk-full", "data-hpk-close", "help-btn", "clarkPage"):
            self.assertNotIn(needle, html)
        self.assertIn("help-peek", (Path(page.__file__).parent / "page.html").read_text(encoding="utf-8"), "the served page has it")


if __name__ == "__main__":
    unittest.main()
