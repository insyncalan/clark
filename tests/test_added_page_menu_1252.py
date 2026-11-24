"""Row 1252 slice 4a: the editor shows an added page as a tab in the top bar and draws its sections. The tab is named as the page is named, sits
after the Gantt tab (or after Use cases while the Gantt is off) in the menu's order, and is left out while the page is hidden from the menu. Its
address is page:<id>; a page that is gone or hidden opens the Dashboard. Classic, 1400 and 900 only. Fictional data only.

Run: python3 dev/run_tests.py test_added_page_menu_1252
"""
import json
import sqlite3
import unittest

from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

SECS = json.dumps([{"id": "s1", "type": "text", "title": "Supplier notes head", "body": "<p>Supplier notes body text</p>"}])
TABS = "[...document.querySelectorAll('.top .tabs .tab')].map(t => t.textContent.trim())"


class AddedPageTab(Base):
    def add(self, name, **values):
        status, body = self.real_change({"project": "ABC", "kind": "added_pages", "op": "new",
                                         "values": {"name": name, "starter": "blank", "sections": SECS, **values}})
        self.assertEqual(status, 200, body)
        return self.store.read("added_pages", project="ABC")[-1]["id"]

    def open(self, cdp, width, hash_="#dashboard&p=ABC"):
        p = self.visit(cdp, hash_)
        size(cdp, p, width, 800)
        p.until("document.querySelectorAll('.top .tabs .tab').length >= 4", "the tabs show")
        return p

    def check_tab(self, width):
        pid = self.add("Supplier status")
        self.add("Secret page", hidden=1)
        with chrome() as cdp:
            p = self.open(cdp, width)
            tabs = p.js(TABS)
            self.assertEqual(tabs[-1], "Supplier status", tabs)
            self.assertNotIn("Secret page", tabs)
            self.assertEqual(tabs[:4], ["Dashboard", "Work items", "Milestones", "Use cases"], tabs)
            p.js("[...document.querySelectorAll('.top .tabs .tab')].filter(t => t.textContent.trim() === 'Supplier status')[0].click()")
            p.until("[...document.querySelectorAll('.top .tabs .tab')].some(t => t.textContent.trim() === 'Supplier status' && t.getAttribute('aria-selected') === 'true')", "the tab is selected")
            p.until("document.body.textContent.includes('Supplier notes body text')", "its section is drawn")
            self.assertEqual(p.js("location.hash.split('&')[0]"), "#page:" + pid)
            self.assertEqual(p.js("document.documentElement.scrollWidth - document.documentElement.clientWidth"), 0, "no sideways scroll")

    def test_tab_1400(self):
        self.check_tab(1400)

    def test_tab_900(self):
        self.check_tab(900)

    def test_after_gantt_in_order(self):
        self.add("Alpha page")
        self.add("Beta page")
        with sqlite3.connect(str(self.store.path)) as con:
            con.execute("UPDATE projects SET show_gantt_editor = 1 WHERE code = 'ABC'")
        with chrome() as cdp:
            p = self.open(cdp, 1400)
            tabs = p.js(TABS)
            self.assertEqual(tabs[-3:], ["Gantt", "Alpha page", "Beta page"], tabs)

    def test_address_opens_the_page_and_a_hidden_one_falls_back(self):
        pid = self.add("Supplier status")
        gone = self.add("Hidden page", hidden=1)
        with chrome() as cdp:
            p = self.open(cdp, 1400, "#page:%s&p=ABC" % pid)
            p.until("document.body.textContent.includes('Supplier notes body text')", "the address opens the page")
            p = self.open(cdp, 1400, "#page:%s&p=ABC" % gone)
            p.until("!!document.querySelector('#report')", "the dashboard")
            self.assertFalse(p.js("document.body.textContent.includes('Supplier notes body text')"))

    def test_tab_bar_values_at_1400(self):
        """AP2: tab text 14px, white at 75%, the selected tab's underline 3px #38E0EE (the bar's height is its own test below)."""
        self.add("Supplier status")
        with chrome() as cdp:
            p = self.open(cdp, 1400)
            got = p.js("""(() => {
              const tabs = [...document.querySelectorAll('.top .tabs .tab')];
              const t = tabs.find((x) => x.textContent.trim() === 'Supplier status'), sel = tabs.find((x) => x.getAttribute('aria-selected') === 'true');
              const cs = getComputedStyle(t), af = getComputedStyle(sel, '::after');
              return { size: cs.fontSize, color: cs.color, selected: sel.textContent.trim(), underline: af.height, ubg: af.backgroundColor,
                       scale: af.transform, bar: document.querySelector('.top').getBoundingClientRect().height };
            })()""")
            self.assertEqual(got["size"], "14px", got)
            self.assertEqual(got["color"], "color(srgb 1 1 1 / 0.75)", got)
            self.assertEqual(got["selected"], "Dashboard", got)
            self.assertEqual(got["underline"], "3px", got)
            self.assertIn(got["ubg"], ("rgb(56, 224, 238)",), got)
            self.assertIn(got["scale"], ("matrix(1, 0, 0, 1, 0, 0)", "none"), "the selected underline is drawn: " + got["scale"])
            p.js("[...document.querySelectorAll('.top .tabs .tab')].filter(t => t.textContent.trim() === 'Supplier status')[0].click()")
            p.until("[...document.querySelectorAll('.top .tabs .tab')].some(t => t.textContent.trim() === 'Supplier status' && t.getAttribute('aria-selected') === 'true')", "the added tab is selected")
            p.until("(() => { const t = [...document.querySelectorAll('.top .tabs .tab')].find((x) => x.getAttribute('aria-selected') === 'true'); return ['rgb(255, 255, 255)', 'color(srgb 1 1 1)'].includes(getComputedStyle(t).color); })()", "the colour change (120ms) is done")
            sel = p.js("(() => { const t = [...document.querySelectorAll('.top .tabs .tab')].find((x) => x.getAttribute('aria-selected') === 'true'); const a = getComputedStyle(t, '::after'); return [getComputedStyle(t).color, a.height, a.backgroundColor]; })()")
            self.assertIn(sel[0], ("rgb(255, 255, 255)", "color(srgb 1 1 1)"), sel)
            self.assertEqual(sel[1:], ["3px", "rgb(56, 224, 238)"], sel)

    @unittest.expectedFailure
    def test_bar_is_56px_at_1400(self):
        """AP2: the bar is 56px (--topbar) at 1400. KNOWN GAP, kept visible: the shipped header (top-hdr, project name over the tabs) measures 85px and
        shell.css sets html:has(.top-hdr) --topbar 85px; 56px is only the :root default. Needs a product ruling; drop expectedFailure when it is settled."""
        with chrome() as cdp:
            p = self.open(cdp, 1400)
            self.assertEqual(p.js("document.querySelector('.top').getBoundingClientRect().height"), 56)
            self.assertEqual(p.js("getComputedStyle(document.documentElement).getPropertyValue('--topbar').trim()"), "56px")

    def test_tabs_scroll_inside_bar_at_900(self):
        """AP2: at 900 the tabs scroll inside the bar and the page is not wider than the window."""
        for i in range(3):
            self.add("Supplier status %d" % i)
        with chrome() as cdp:
            p = self.open(cdp, 900)
            got = p.js("""(() => { const tabs = document.querySelector('.top .tabs'), cs = getComputedStyle(tabs), top = document.querySelector('.top').getBoundingClientRect();
              const r = tabs.getBoundingClientRect();
              return { ox: cs.overflowX, right: r.right, topRight: top.right, sw: document.documentElement.scrollWidth, w: window.innerWidth,
                       tabsSw: tabs.scrollWidth, tabsCw: tabs.clientWidth }; })()""")
            self.assertLessEqual(got["sw"], got["w"], got)
            self.assertIn(got["ox"], ("auto", "scroll"), got)
            self.assertLessEqual(got["right"], got["topRight"], got)

    def gutter(self, p):
        """The gutter of the first section in Edit: the + button's words and the menu's items (opened by the grip), plus the gutter's own box."""
        p.edit()
        first = "document.querySelector('#report .secs > .sec')"
        p.until("!!%s && !!%s.querySelector('[data-add]')" % (first, first), "the gutter is drawn")
        plus = p.js("[%s.querySelector('[data-add]').title, %s.querySelector('[data-add]').getAttribute('aria-label').startsWith('Add a template below ')]" % (first, first))
        box = p.js("(() => { const c = %s.querySelector('.sec-ctl'), r = c.getBoundingClientRect(), s = %s.getBoundingClientRect(); return [c.className.split(' ')[0], Math.round(r.left - s.left), Math.round(r.width)]; })()" % (first, first))
        p.js("%s.querySelector('[data-options]').click()" % first)
        p.until("!!document.querySelector('.menu-item')", "the menu opens")
        menu = p.js("[...document.querySelectorAll('.menu-item')].map(e => e.textContent.trim())")
        p.js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
        return {"plus": plus[0], "plus_label": plus[1], "box": box, "menu": menu}

    @unittest.expectedFailure
    def test_added_page_has_the_dashboards_gutter_and_add_a_template_words(self):
        """AP9 (KNOWN GAP, kept visible): Dashboard.jsx draws an added page read only (editing = !page && ...; 'its sections are edited in its own slice'), so Edit shows
        no gutter there yet. Drop expectedFailure when that slice lands. On an added page the menu item reads 'Add a template below…' and the + button 'Add a template below', with the same gutter as the Dashboard."""
        pid = self.add("Supplier status")
        for width in (1400, 900):
            with chrome() as cdp:
                p = self.open(cdp, width, "#dashboard&p=ABC")
                dash = self.gutter(p)
                p = self.open(cdp, width, "#page:%s&p=ABC" % pid)
                p.until("document.body.textContent.includes('Supplier notes body text')", "the page is drawn")
                added = self.gutter(p)
                self.assertEqual(added["plus"], "Add a template below", (width, added))
                self.assertTrue(added["plus_label"], (width, added))
                self.assertEqual(added["menu"][0], "Add a template below…", (width, added))
                self.assertEqual((added["plus"], added["menu"][0], added["box"]), (dash["plus"], dash["menu"][0], dash["box"]),
                                 "the added page uses the Dashboard's gutter (words and box)")


if __name__ == "__main__":
    unittest.main()
