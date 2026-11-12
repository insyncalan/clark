"""The Settings head and menu (item 1024, option A): the title, a line of help and a menu with one entry for each page, in a real browser at
1400 and 900 px, light and dark. At both widths the menu is a list down the left with ONE page at its right (narrower than 900 px the menu is
still the row of buttons under the title; a later step turns that into one dropdown line; that is not tested here). Run: python3 dev/run_tests.py test_settings_head

What is asserted: the title and the help line; an entry for each page (Projects, People, Published reports, Profile, Feedback, Folder, Brand,
Appearance, Reports, Backups, Export and import, Claude and AI, Logs and diagnostics, Version and updates) in five groups, and none for
an old name; exactly one page is drawn and the other pages' headings are not; a click shows the page, puts the address on
#settings&s=<page> and moves focus to the page's heading; Back and Forward step between pages; the keyboard does the same (arrows, Enter);
the list stands at the left of the page at 1400 and 900 px, the page never
scrolls sideways and nothing overlaps; each entry is at least 24 px high and wide; its text is at least 13 px and 4.5:1 on its ground; the
focus ring is 2 px. Chrome is required: these tests fail, never skip, without it.

item 1024, no pin weakened: every check below keeps the strength of the one it replaces. The one long page became one page at a time, so
"scrolls to the card" is "shows the page", and an anchor is an address. The chips' row at 900 px is kept as it was until its own step.
"""
import json
import re
import unittest

from test_appearance import scheme
from test_publish_dialog import Base, PAGE_SRC
from test_server import chrome, wait
from _mouse import click_centre, menu_item_js
from _new_page import reload_to_new_page_cdp

WIDTHS = (1400, 900)
MODES = ("light", "dark")
GROUPS = ["Everyday", "Publishing", "Look and feel", "Data and safety", "Advanced"]
HELP = "Where reports are published, how clark looks for you, when an item counts as not reviewed, the log, your backups and asking Claude."
# (menu name, address key, heading that takes the focus, that heading's text): the menu in plan order
PAGES = [("Projects", "projects", "projects-h", "Projects"), ("People", "people", "people-h", "People"), ("Published reports", "published", "pubs-h", None),
         ("Profile", "profile", "profile-h", "Profile"), ("Feedback", "feedback", "feedback-h", "Feedback"),
         ("Folder", "folder", "client-folder-h", "Publishing"), ("Brand", "brand", "brands-h", "Brands"),
         ("Appearance", "appearance", "personal-h", "Personal"), ("Reports", "reports", "review-days-h", "Freshness"), ("Backups", "backups", "safety-h", "Backups"),
         ("Export and import", "export", "data-card-h", "Data"), ("Claude and AI", "claude-ai", "ask-settings-h", "Claude and AI"), ("Logs and diagnostics", "logs", "diagnostics-h", "Logs and diagnostics"),
         ("Version and updates", "version", "update-h", "Version and updates")]
RETIRED = ["Asking", "Personal", "Freshness", "Gantt", "Brands", "Client folder", "Publishing", "Data", "AI"]      # old chip names that are no entry now


def ratio(a, b):
    def lum(rgb):
        out = []
        for c in rgb:
            c /= 255
            out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
        return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def rgb(text):
    return [int(x) for x in re.findall(r"\d+", text)[:3]]


class Head(Base):
    def open_settings(self, p, w, mode="light", page=None):
        """Open Settings (on `page`, an address key, else plain: Projects) and wait for its menu, its heading and the one marked entry."""
        p.width(w)
        scheme(p, mode)
        p.js("location.hash = '#settings&p=PUB" + (f"&s={page}" if page else "") + "'")
        want = next(h for _, s, h, _ in PAGES if s == (page or "projects"))
        p.until(f"!!document.querySelector('.set-menu .set-item') && !!document.getElementById('{want}') && document.querySelectorAll('.set-menu [aria-current]').length === 1",
                "Settings, its menu and its page drew")
        p.settled("Settings finished drawing and scrolling")

    def chips(self, p):
        return p.js("[...document.querySelectorAll('.set-menu .set-item')].map(b => b.textContent)")

    def numbers(self, p, head_id):
        """What a red page check needs to name itself (the hosted macOS runner printed no numbers): the heading's box, the scroll, the window,
        the menu list (its box and position), the active entry (its name and box), the scroll margin and padding that keep a heading clear of
        the top bar, and whether the runner asks for reduced motion."""
        return p.js(f"""(function(){{
          var h = document.getElementById('{head_id}'), r = h ? h.getBoundingClientRect() : null;
          var menu = document.querySelector('.set-menu'), m = menu ? menu.getBoundingClientRect() : null;
          var act = document.querySelector('.set-menu [aria-current]'), a = act ? act.getBoundingClientRect() : null;
          var pad = document.scrollingElement ? getComputedStyle(document.scrollingElement).scrollPaddingTop : 'n/a';
          return 'head_id=' + '{head_id}' + ' heading top=' + (r ? r.top : 'none') + ' bottom=' + (r ? r.bottom : 'none') +
            ' scrollY=' + window.scrollY + ' innerHeight=' + window.innerHeight +
            ' menu top=' + (m ? m.top : 'none') + ' bottom=' + (m ? m.bottom : 'none') + ' position=' + (menu ? getComputedStyle(menu).position : 'n/a') +
            ' active entry=' + (act ? act.textContent : 'none') + ' top=' + (a ? a.top : 'none') + ' bottom=' + (a ? a.bottom : 'none') +
            ' heading scroll-margin-top=' + (h ? getComputedStyle(h).scrollMarginTop : 'n/a') +
            ' scroll-padding-top=' + pad +
            ' reduced-motion=' + matchMedia('(prefers-reduced-motion: reduce)').matches;
        }})()""")

    def marked(self, p):
        return p.js("[...document.querySelectorAll('.set-menu [aria-current]')].map(b => b.textContent + '=' + b.getAttribute('aria-current'))")

    def choose(self, p, name):
        click_centre(p.cdp, p.sid, menu_item_js(json.dumps(name)), f"the {name} entry")      # a real mouse: a JS click has no mousedown, so nothing ends the router's restore loop

    def on_page(self, p, slug, head_id, name):
        """The page is shown: its heading has the focus and is in view, the address names it, its entry is marked. A red, whichever check
        it is, names its numbers (the hosted macOS runner printed none)."""
        try:
            p.settled("the page change finished")      # before anything is measured
            p.until(f"document.activeElement && document.activeElement.id === '{head_id}'", f"focus is on {head_id}")
            p.until(f"(function(){{var r = document.getElementById('{head_id}').getBoundingClientRect(); return r.top >= 56 && r.bottom <= window.innerHeight;}})()",
                    "the heading is in view, clear of the top bar")
            self.assertEqual(self.marked(p), [f"{name}=page"])
            self.assertEqual(p.js("(location.hash.match(/&s=([^&]*)/) || [0, 'projects'])[1]"), slug, "the address names the page")
            p.settled("the page change finished")
        except AssertionError as e:
            raise AssertionError(f"{e} :: {self.numbers(p, head_id)}") from None

    def test_C_the_title_the_help_line_and_an_entry_for_each_page_that_exists(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode)
                    self.assertEqual(p.js("document.querySelector('.set-head h1').textContent"), "Settings")
                    self.assertEqual(p.js("document.querySelector('.set-head p').textContent"), HELP)
                    self.assertEqual(self.chips(p), [name for name, *_ in PAGES])
                    self.assertEqual(p.js("[...document.querySelectorAll('.set-menu .set-group-h')].map(h => h.textContent)"), GROUPS)
                    for name, slug, head_id, text in PAGES:
                        if slug == "published":
                            continue      # row 1087: the entry opens the Published reports page of its own, not a Settings page (the test after this one)
                        self.open_settings(p, w, mode, slug)
                        if text:
                            self.assertEqual(p.js(f"document.getElementById('{head_id}').textContent"), text, "the page's heading is its card's heading")
                        self.assertEqual(p.js(f"document.getElementById('{head_id}').getAttribute('tabindex')"), "-1")
                        self.assertEqual(p.js("document.querySelectorAll('[data-settings-page]').length"), 1, "exactly one page is drawn")
                        others = [h for _, s, h, _ in PAGES if s != slug and h != head_id]
                        self.assertEqual(p.js("[" + ",".join(f"'{h}'" for h in others) + "].filter(h => document.getElementById(h)).length"), 0, "no other page's heading is drawn")
                    for gone in RETIRED:
                        self.assertNotIn(gone, self.chips(p), f"no entry named {gone}: that name is not a page")
                    self.assertNotIn("Settings are not ready yet.", p.js("document.querySelector('main').innerText"))

    def test_C_a_click_shows_the_page_and_focuses_its_heading_and_back_and_forward_step_between_pages(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, w)
                for name, slug, head_id, _ in reversed(PAGES):
                    if slug == "published":
                        continue      # it leaves Settings for the page of its own: pinned in the test after this one
                    p.js("window.scrollTo(0, 0)")
                    p.settled("the scroll to the top finished")      # the click comes only when nothing is moving
                    self.choose(p, name)
                    self.on_page(p, slug, head_id, name)
                self.assertTrue(p.js("location.hash.indexOf('#settings') === 0"), "the page's own address is kept")
                # Back and Forward: one history step for each page change
                self.open_settings(p, w, page="people")
                self.choose(p, "Profile")
                self.on_page(p, "profile", "profile-h", "Profile")
                p.js("history.back()")
                p.until("document.querySelector('.set-menu [aria-current]').textContent === 'People'", "Back shows the page before")
                self.assertTrue(p.js("location.hash.indexOf('&s=people') > 0"))
                p.js("history.forward()")
                p.until("document.querySelector('.set-menu [aria-current]').textContent === 'Profile'", "Forward shows the page after")
                # a page that is not there opens Projects
                p.js("location.hash = '#settings&p=PUB&s=nonsense'")
                p.until("document.querySelector('.set-menu [aria-current]').textContent === 'Projects'", "an unknown page opens Projects")

    def test_C_the_reports_page_holds_both_its_cards_in_order_and_no_other_page_holds_either(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, w, page="reports")
                self.assertEqual(p.js("[...document.querySelectorAll('.set-cards [id$=-h]')].map(h => h.id).filter(id => id === 'review-days-h' || id === 'gantt-setting-h')"),
                                 ["review-days-h", "gantt-setting-h"], "Freshness then Gantt, both on Reports")
                self.open_settings(p, w, page="appearance")
                self.assertEqual(p.js("!!document.getElementById('gantt-setting-h') || !!document.getElementById('review-days-h')"), False, "neither is on Appearance")

    def test_C_a_heading_the_scroll_did_not_bring_into_view_is_scrolled_to(self):
        """The hosted macOS runner found a heading 4466 px down with scrollY=0 after the click (window.scrollTo did not take). Here scrollTo does
        nothing and the window is scrolled past the heading by hand: choosing a page still shows its heading."""
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 1400)
            p.js("document.body.style.minHeight = '4000px'; window.scrollTo(0, 400); window.scrollTo = function () {};")
            p.until("window.scrollY >= 300", "the window is scrolled down")
            # the menu is above the window here (the page is scrolled past it), so no mouse can reach it: this one click stays a JS click
            p.js("[...document.querySelectorAll('.set-menu .set-item')].find(b => b.textContent === 'People').click()")
            self.on_page(p, "people", "people-h", "People")

    def one_frame_later(self, p):
        """Two animation frames have run since this call (a restore queued with requestAnimationFrame has run by then)."""
        p.js("window.__frames = 0; requestAnimationFrame(function () { requestAnimationFrame(function () { window.__frames = 1; }); })")
        p.until("window.__frames === 1", "two animation frames passed")

    def test_C_the_heading_scrolled_to_stays_in_view_one_frame_later(self):
        """The page change scrolls to the top, finds the heading far down (a long page above it), and scrolls to the heading. A second
        scroll to the saved place, queued for the next frame, must not pull the window back off the heading."""
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 1400)
            p.js("document.body.style.minHeight = '8000px'; document.querySelector('.set-cards').style.marginTop = '3000px'; window.scrollTo(0, 0)")
            p.settled("the scroll to the top finished")
            self.choose(p, "People")
            p.until("document.activeElement && document.activeElement.id === 'people-h'", "focus is on people-h")
            self.one_frame_later(p)
            p.settled("the scroll finished")
            self.assertTrue(p.js("(function(){var r = document.getElementById('people-h').getBoundingClientRect(); return r.top >= 56 && r.bottom <= window.innerHeight;})()"),
                            "the heading is still in view one frame after the change; " + self.numbers(p, "people-h"))

    def test_C_a_heading_under_the_top_bar_is_scrolled_to(self):
        """A heading inside the window but under the 56 px bar is as hidden as one outside it: the fallback scrolls to it too."""
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 1400)
            p.js("document.body.style.minHeight = '8000px'; document.querySelector('.set-cards').style.marginTop = '2000px';")
            p.js("window.scrollTo(0, Math.round(document.getElementById('projects-h').getBoundingClientRect().top + window.scrollY - 20)); window.scrollTo = function () {};")
            p.until("window.scrollY > 1000", "the window is scrolled down to the Projects heading")
            # the scroll to the top does nothing (as on the hosted macOS run); People's heading is then 20 px under the window's top, under the bar
            p.js("[...document.querySelectorAll('.set-menu .set-item')].find(b => b.textContent === 'People').click()")
            p.until("document.activeElement && document.activeElement.id === 'people-h'", "focus is on people-h")
            self.one_frame_later(p)
            p.settled("the scroll finished")
            self.assertTrue(p.js("document.getElementById('people-h').getBoundingClientRect().top >= 56"),
                            "the heading is clear of the top bar; " + self.numbers(p, "people-h"))

    def test_C_arriving_from_another_screen_focuses_the_heading_but_a_reload_leaves_the_focus(self):
        """Settings unmounts whenever the view changes, so each arrival from another screen is a first draw: the heading takes the focus
        then (the closed menu left it on nothing). A reload of the address keeps the focus where the browser put it."""
        with chrome() as cdp:
            p = self.page(cdp)
            p.js("location.hash = '#settings&p=PUB&s=backups'")
            p.until("!!document.getElementById('safety-h')", "Backups drew")
            p.until("document.activeElement && document.activeElement.id === 'safety-h'", "an arrival from the Dashboard focuses the heading")
            p.js("location.hash = '#dashboard&p=PUB'")
            p.until("!document.getElementById('safety-h')", "the Dashboard drew")
            p.js("location.hash = '#settings&p=PUB&s=logs'")
            p.until("document.activeElement && document.activeElement.id === 'diagnostics-h'", "a second arrival focuses the heading too")
            reload_to_new_page_cdp(cdp, p.sid, "!!document.getElementById('diagnostics-h')", "Settings drew again")
            p.settled("the reloaded page finished drawing")
            self.assertNotEqual(p.js("document.activeElement && document.activeElement.id"), "diagnostics-h", "a reload leaves the focus alone")

    def test_C_the_profile_menus_link_to_published_reports_opens_its_page(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.js("document.querySelector('#profile-btn').click()")
            p.until("!!document.querySelector('#profile-menu [data-kind=published]')", "the menu has Published reports")
            p.js("document.querySelector('#profile-menu [data-kind=published]').click()")
            p.until("location.hash.indexOf('#published') === 0 && !!document.getElementById('pubs-page')", "the Published reports page of its own opens")
            self.assertFalse(p.js("!!document.querySelector('.set-menu')"), "it is no Settings page")

    def test_C_the_menu_entry_published_reports_opens_the_page_of_its_own_at_1400_and_900(self):
        """Option A for the clash with row 1087: the entry is a link to that page. One history entry: Back returns to the Settings page it came from."""
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, w, page="people")
                self.choose(p, "Published reports")
                p.until("location.hash === '#published&p=PUB' && !!document.getElementById('pubs-page')", "the page of its own drew")
                self.assertFalse(p.js("!!document.querySelector('.set-menu')"), "no Settings menu on it")
                self.assertEqual(p.js("document.querySelector('#pubs-page h1').textContent"), "Published reports")
                p.js("history.back()")
                p.until("location.hash.indexOf('&s=people') > 0 && document.querySelector('.set-menu [aria-current]').textContent === 'People'", "Back shows the Settings page it came from")

    def test_C_published_reports_is_no_settings_anchor_for_help(self):
        """Published reports is its own page (row 1087), so Help has no go:settings#pubs: SETTINGS_ANCHOR does not map it and the find-a-past-publication job goes to the Dashboard."""
        store = (PAGE_SRC / "help" / "helpStore.js").read_text(encoding="utf-8")
        self.assertNotIn("pubs", re.search(r"const SETTINGS_ANCHOR = \{(.*?)\};", store, re.S).group(1))
        content = json.loads((PAGE_SRC / "help" / "helpContent.json").read_text(encoding="utf-8"))
        self.assertNotIn("settings#pubs", json.dumps(content))

    def test_C_every_help_anchor_for_settings_opens_its_own_page(self):
        """go:settings#update, #profile, #people and #folder each open the page that holds what they name (SETTINGS_ANCHOR in helpStore.js); an anchor that is not mapped opens Projects."""
        for anchor, slug, head in (("update", "version", "update-h"), ("profile", "profile", "profile-h"), ("people", "people", "people-h"), ("folder", "folder", "client-folder-h"), ("nothing", "projects", "projects-h")):
            with self.subTest(anchor=anchor), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, 1400, page="backups")
                p.js("window.clarkPage.help.goTo('settings#%s')" % anchor)
                p.until("!!document.getElementById('%s')" % head, "the %s page drew" % slug)
                self.assertEqual(p.js("(location.hash.match(/&s=([^&]*)/) || [0, 'projects'])[1]"), slug, "the address names the page")

    def test_C_a_help_link_to_settings_folder_opens_the_folder_page(self):
        """The Help step "Settings > Folder" (go:settings#folder, held from view today) goes to the Folder page, not Projects: the page's own goTo takes the same path as the link."""
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 1400)
            p.js("window.clarkPage.help.goTo('settings#folder')")
            p.until("!!document.getElementById('client-folder-h')", "the Folder page drew")
            self.assertEqual(p.js("(location.hash.match(/&s=([^&]*)/) || [0, 'projects'])[1]"), "folder", "the address names the page")

    def test_C_arrows_move_between_entries_and_enter_chooses(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 1400)
            p.js("document.querySelector('.set-menu .set-item').focus()")
            p.key("ArrowDown", code="ArrowDown", vk=40)
            self.assertEqual(p.js("document.activeElement.textContent"), "People", "the arrow moves to the next entry")
            p.key("Tab", code="Tab", vk=9)
            self.assertEqual(p.js("document.activeElement.textContent"), "Published reports", "Tab moves on in menu order")
            self.assertEqual(p.js("document.querySelectorAll('.set-menu .set-item').length"), len(PAGES))
            for _ in range(3):
                p.key("ArrowDown", code="ArrowDown", vk=40)
            self.assertEqual(p.js("document.activeElement.textContent"), "Folder")
            p.js("window.scrollTo(0, 0)")
            p.key("Enter", code="Enter", vk=13)
            self.on_page(p, "folder", "client-folder-h", "Folder")
            self.assertEqual(p.js("getComputedStyle(document.activeElement).outlineWidth"), "2px", "the heading shows the ring after the keyboard")

    def test_C_the_list_is_at_the_left_at_1400_and_900(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode)
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")
                    self.assertTrue(p.js("(function(){var n = document.querySelector('.set-menu'); return n.scrollWidth <= n.clientWidth;})()"), "the menu does not scroll sideways")
                    chips = p.js("[...document.querySelectorAll('.set-menu .set-item')].map(b => { const r = b.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; })")
                    nav = p.js("(function(){var r = document.querySelector('.set-menu').getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom];})()")
                    first = p.js("(function(){var r = document.querySelector('.set-cards .frame').getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom];})()")
                    for a, b in zip(chips, chips[1:]):
                        self.assertTrue(b[1] >= a[3] - 1 or b[0] >= a[2] - 1, "no two links overlap")
                    for h, wd in ((c[3] - c[1], c[2] - c[0]) for c in chips):
                        self.assertGreaterEqual(h, 24)
                        self.assertGreaterEqual(wd, 24)
                    if w >= 900:
                        self.assertEqual(p.js("getComputedStyle(document.querySelector('.set-list')).flexDirection"), "column")
                        self.assertLessEqual(max(c[0] for c in chips) - min(c[0] for c in chips), 1, "the links stand in one column")
                        self.assertTrue(all(b[1] > a[1] for a, b in zip(chips, chips[1:])), "each link is below the one before")
                        self.assertLessEqual(nav[2], first[0] + 1, "the list is at the left of the page")
                        self.assertLess(nav[2] - nav[0], w / 3, "the list does not eat the width")
                        self.assertGreater(first[2] - first[0], w / 2, "the page keeps most of the width")
                        self.assertGreater(first[2] - first[0], w / 2, "the page keeps most of the width")
                    else:
                        self.assertEqual(p.js("getComputedStyle(document.querySelector('.set-list')).flexWrap"), "wrap")
                        self.assertEqual(chips[0][1], chips[1][1], "the first two chips share a row")
                        self.assertLessEqual(nav[3], first[1] + 1, "the chips are above the page")
                        self.assertGreater(first[2] - first[0], w * 0.8, "the page has the full width")

    # ---- round 2 of item 1024c: the review's findings ----
    def test_C_at_900_the_list_stays_under_the_top_bar(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 900)
            self.assertEqual(p.js("getComputedStyle(document.querySelector('.set-menu')).position"), "sticky", "the list at 900 px stays under the top bar")

    def test_C_row_buttons_stay_on_one_line_at_900_and_1400(self):
        for w in (900, 1400):
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, w)
                p.until("!!document.querySelector('.set-cards [data-row-menu]')", "the Projects table has its row menu buttons")
                self.assertEqual(p.js("getComputedStyle(document.querySelector('.set-cards [data-row-menu]')).whiteSpace"), "nowrap")
                self.assertLessEqual(p.js("document.querySelector('.set-cards [data-row-menu]').getBoundingClientRect().height"), 34, "the row menu button is one line high")
                self.assertEqual(p.js("[...document.querySelectorAll('td.acts .btn')].map(b => getComputedStyle(b).whiteSpace)").count("nowrap"),
                                 p.js("document.querySelectorAll('td.acts .btn').length"), "every row button (td.acts .btn) is nowrap")
                self.assertGreater(p.js("document.querySelectorAll('td.acts .btn').length"), 0, "the rule is checked on at least one button")
                self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")

    def test_C_every_entry_name_is_whole_on_one_line_and_a_rows_buttons_stand_on_one_line_at_900_1400(self):
        """Round 5: at 900 px 'Export and import', 'Logs and diagnostics' and 'Version and updates' wrapped to two lines in the narrow list and the
        Projects row buttons (Open, Edit, Archive) stacked one per line. Names stay whole (no ellipsis, no clipping); the list is made wide enough."""
        lines = """[...document.querySelectorAll('.set-menu .set-item')].map(b => {
          const r = document.createRange(); r.selectNodeContents(b);
          const boxes = [...r.getClientRects()], tops = new Set(boxes.map(x => Math.round(x.top)));
          const cs = getComputedStyle(b), bb = b.getBoundingClientRect();
          return {name: b.textContent, lines: tops.size, height: bb.height, one_line: parseFloat(cs.lineHeight) + parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom) + parseFloat(cs.borderTopWidth) + parseFloat(cs.borderBottomWidth),
                  min: parseFloat(cs.minHeight) || 0, clipped: b.scrollWidth > b.clientWidth, ellipsis: cs.textOverflow === 'ellipsis'};
        })"""
        rows = """[...document.querySelectorAll('.set-cards tr')].map(tr => [...tr.querySelectorAll('td.acts .btn')].map(b => Math.round(b.getBoundingClientRect().top))).filter(t => t.length)"""
        for w in (900, 1400):
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, w)
                for e in p.js(lines):
                    self.assertEqual(e["lines"], 1, f"{e['name']} is on one line at {w} px: {e}")
                    self.assertLessEqual(e["height"], max(e["one_line"], e["min"]) + 1, f"{e['name']} is one line high at {w} px: {e}")
                    self.assertFalse(e["clipped"] or e["ellipsis"], f"{e['name']} is whole, not cut at {w} px: {e}")
                p.until("!!document.querySelector('.set-cards [data-row-menu]')", "the Projects table has its row menu buttons")
                tops = p.js(rows)
                self.assertTrue(tops, "the table has rows with buttons")
                for t in tops:
                    self.assertLessEqual(max(t) - min(t), 2, f"a row's buttons stand on one line at {w} px: {tops}")
                self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), f"no sideways scroll at {w} px")

    def test_C_a_red_page_check_names_the_menu_the_active_entry_the_heading_and_the_scroll(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 900)
            with self.assertRaises(AssertionError) as caught:
                self.on_page(p, "projects", "projects-h", "People")      # a wrong entry name: the check must fail, and say where everything stood
            said = str(caught.exception)
            for want in ("scrollY=", "menu top=", "active entry=", "heading top=", "innerHeight="):
                self.assertIn(want, said)
            self.assertNotIn("set-nav", said, "the old bar is not read")

    def test_C_up_down_home_and_end_move_in_a_column_or_a_wrapped_row_and_a_held_modifier_is_left_alone(self):
        def press(p, key, vk, mods=0):
            for kind in ("keyDown", "keyUp"):
                p.cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": key, "windowsVirtualKeyCode": vk, "modifiers": mods}, p.sid)
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 900)
            p.js("document.querySelector('.set-menu .set-item').focus()")
            press(p, "ArrowRight", 39)
            self.assertEqual(p.js("document.activeElement.textContent"), "Projects", "Right does not move: Left and Right are left to the browser")
            press(p, "ArrowDown", 40)
            self.assertEqual(p.js("document.activeElement.textContent"), "People", "Down moves to the next entry")
            press(p, "ArrowLeft", 37)
            self.assertEqual(p.js("document.activeElement.textContent"), "People", "Left does not move")
            press(p, "ArrowUp", 38)
            self.assertEqual(p.js("document.activeElement.textContent"), "Projects", "Up moves to the one before")
            press(p, "End", 35)
            self.assertEqual(p.js("document.activeElement.textContent"), PAGES[-1][0], "End moves to the last entry")
            press(p, "Home", 36)
            self.assertEqual(p.js("document.activeElement.textContent"), "Projects", "Home moves to the first entry")
            for mods, name in ((1, "Alt"), (2, "Ctrl"), (4, "Meta")):      # the protocol's bits: 1 Alt, 2 Ctrl, 4 Meta
                press(p, "ArrowDown", 40, mods)
                self.assertEqual(p.js("document.activeElement.textContent"), "Projects", f"{name} held: the arrow is left to the browser")

    def test_C_a_reload_at_the_folder_page_keeps_it_while_the_project_loads(self):
        with chrome() as cdp:
            p = self.page(cdp, "#settings&p=PUB&s=folder")
            # a reload where the project's data is a moment late: the address is rewritten by nothing in the meantime
            cdp.call("Page.enable", {}, p.sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": """(function(){ var f = window.fetch; window.__marks = []; window.__writes = [];
                ['pushState', 'replaceState'].forEach(function(m){ var o = history[m]; history[m] = function(st, t, u){ window.__writes.push(m + ' ' + u); return o.apply(this, arguments); }; });
                window.fetch = function(u){ var a = arguments; if (String(u).indexOf('/api/data') < 0) return f.apply(this, a);
                  return new Promise(function(ok){ setTimeout(function(){ ok(f.apply(window, a)); }, 1200); }); };
                window.addEventListener('hashchange', function(){ window.__marks.push(location.hash); }); })();"""}, p.sid)
            reload_to_new_page_cdp(cdp, p.sid, "!!document.querySelector('#profile-btn')", "the page loaded again")
            p.until("!!document.getElementById('client-folder-h')", "the Folder page drew once the project loaded")
            self.assertIn("s=folder", p.js("location.hash"), "the address still names the Folder page")
            self.assertEqual(p.js("document.querySelector('.set-menu [aria-current]').textContent"), "Folder")
            # settingsFallback rewrites with replaceState (no hashchange), so the history calls themselves are watched from before the page script
            self.assertEqual([w for w in p.js("window.__writes") if "s=folder" not in w], [], "the entry was not rewritten to Projects while the project loaded")
            self.assertTrue(p.js("location.hash.indexOf('s=folder') >= 0 && window.__marks.length === 0"), "the address was not rewritten while the project loaded")

    def test_C_the_group_lists_are_labelled_by_ids_that_are_the_headings_own(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 1400)
            got = p.js("""[...document.querySelectorAll('.set-menu .set-list')].map(l => { const h = l.previousElementSibling && l.previousElementSibling.classList.contains('set-group-note') ? l.previousElementSibling.previousElementSibling : l.previousElementSibling;
              return [l.getAttribute('aria-labelledby'), h && h.id, h && h.classList.contains('set-group-h')]; })""")
            self.assertEqual(got, [[f"set-group-{i}", f"set-group-{i}", True] for i in range(len(GROUPS))], "each list names the heading just above it, by its id")
            self.assertEqual(p.js("[...document.querySelectorAll('[id^=set-group-]')].map(e => e.id)"), [f"set-group-{i}" for i in range(len(GROUPS))], "the ids are unique")

    def test_C_each_list_is_named_by_its_group_heading(self):
        names = "[...document.querySelectorAll('.set-menu .set-list')].map(l => { const h = document.getElementById(l.getAttribute('aria-labelledby') || '-'); return h ? h.textContent : null; })"
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 1400)
            self.assertEqual(p.js(names), GROUPS)
            p.width(900)
            self.assertEqual(p.js(names), GROUPS, "the names stay the same at 900 px")

    def test_C_a_junk_page_in_the_address_is_dropped_from_the_bar_at_startup(self):
        with chrome() as cdp:
            p = self.page(cdp, "#settings&p=PUB&s=nonsense")
            p.until("!!document.querySelector('.set-menu .set-item')", "Settings drew")
            p.until("location.hash === '#settings&p=PUB'", "the junk value is gone from the address bar")

    def test_C_text_size_and_contrast_in_light_and_dark(self):
        for mode in MODES:
            with self.subTest(mode=mode), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, 1400, mode)
                got = p.js("""[...document.querySelectorAll('.set-menu .set-item:not([aria-current])')].map(b => { const s = getComputedStyle(b);
                    return [parseFloat(s.fontSize), s.color, s.backgroundColor, s.borderTopColor]; })""")
                self.assertEqual(len(got), len(PAGES) - 1)
                for size, color, ground, edge in got:
                    self.assertGreaterEqual(size, 13)
                    self.assertGreaterEqual(ratio(rgb(color), rgb(ground)), 4.5, f"{mode}: the entry text on its ground")
                    self.assertGreaterEqual(ratio(rgb(edge), rgb(ground)), 3, f"{mode}: the entry's edge on its ground")
                cur = p.js("(function(){var s = getComputedStyle(document.querySelector('.set-menu [aria-current]')); return [s.color, s.backgroundColor];})()")
                self.assertGreaterEqual(ratio(rgb(cur[0]), rgb(cur[1])), 4.5, f"{mode}: the marked entry's text on its fill")
                for size, color, ground in p.js("""[...document.querySelectorAll('.set-menu .set-group-h')].map(h => { const s = getComputedStyle(h);
                        return [parseFloat(s.fontSize), s.color, getComputedStyle(document.querySelector('.set-menu')).backgroundColor]; })"""):
                    self.assertGreaterEqual(size, 13)
                    self.assertGreaterEqual(ratio(rgb(color), rgb(ground)), 4.5, f"{mode}: a group heading on the menu's ground")
                p.js("document.querySelector('.set-menu .set-item').focus()")
                p.key("Tab", code="Tab", vk=9)
                p.key("Tab", code="Tab", vk=9, )
                ring = p.js("(function(){var s = getComputedStyle(document.activeElement); return [s.outlineWidth, s.outlineStyle, s.outlineColor];})()")
                self.assertEqual(ring[:2], ["2px", "solid"])
                brand = p.js("(function(){var d = document.createElement('i'); d.style.color = 'var(--brand-blue)'; document.body.appendChild(d); var c = getComputedStyle(d).color; d.remove(); return c;})()")
                self.assertEqual(ring[2], brand, "the ring is the brand blue")


if __name__ == "__main__":
    unittest.main()
