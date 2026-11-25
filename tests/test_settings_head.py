"""The Settings head: the title, a line of help and one link for each card on the page, in a real browser at 1400 and 900 px,
light and dark. Issues 697 and 842: at 900 px and wider the links are a list down the left with the cards at the right (only 1400 and 900
are tested: no narrower width is). Run: python3 dev/run_tests.py test_settings_head

What is asserted: the title and the help line; a chip for each card that is on the page (Essentials, Profile, Publishing, Personal, Freshness, Gantt, Logs and diagnostics, Projects, Data, Backups, Version and updates, Brands, People, Asking, Feedback, Quit) and none
for a card that is not; a click opens the page and marks it (aria-current); the keyboard does the same (Tab to an item,
Enter); the list stands at the left of the cards at 900 px and wider, the page never scrolls sideways and nothing overlaps; each chip is at least 24 px high and wide; the chip text is at least 13 px
and 4.5:1 on its ground; the focus ring is 2 px. Chrome is required: these tests fail, never skip, without it.
"""
import os
import re
import unittest

from _paths import ROOT
from test_appearance import scheme
from test_publish_dialog import Base
from test_server import chrome, wait

WIDTHS = (1400, 900)
MODES = ("light", "dark")
HELP = "Where reports are published, how clark looks for you, when an item counts as not reviewed, the log, your backups and asking Claude."
CARDS = [("Essentials", "essentials-h"), ("Profile", "profile-h"), ("Publishing", "client-folder-h"), ("Personal", "personal-h"), ("Freshness", "review-days-h"), ("Gantt", "gantt-setting-h"), ("Work items board", "board-setting-h"), ("Logs and diagnostics", "diagnostics-h"), ("Projects", "projects-h"), ("Data", "data-card-h"), ("Backups", "safety-h"),
         ("Version and updates", "update-h"), ("Brands", "brands-h"), ("Theme", "theme-settings-h"), ("People", "people-h"), ("Asking", "ask-settings-h"), ("Quit", "quit-h")]


# Row 1024: Settings shows one page at a time. The pages by group, as the menu names them, with the cards (name, heading id) each draws.
OLD_GROUPS = [("Everyday", [("projects", "Projects", [("Projects", "projects-h")]), ("people", "People", [("People", "people-h")]),
                        ("profile", "Profile", [("Essentials", "essentials-h"), ("Profile", "profile-h")])]),
          ("Publishing", [("folder", "Folder", [("Publishing", "client-folder-h")]), ("brand", "Brand", [("Brands", "brands-h")]), ("theme", "Theme", [("Theme", "theme-settings-h")])]),
          ("Look and feel", [("appearance", "Appearance", [("Personal", "personal-h")]), ("reports", "Reports", [("Freshness", "review-days-h"), ("Gantt", "gantt-setting-h"), ("Work items board", "board-setting-h")])]),
          ("Data and safety", [("backups", "Backups", [("Backups", "safety-h")]), ("data", "Export and import", [("Data", "data-card-h")])]),
          ("Advanced", [("claude", "Claude and AI", [("Asking", "ask-settings-h")]), ("logs", "Logs and diagnostics", [("Logs and diagnostics", "diagnostics-h")]),
                        ("version", "Version and updates", [("Version and updates", "update-h"), ("Quit", "quit-h")])])]
VIEWS = ROOT / "src" / "clark" / "page" / "src" / "components" / "Views.jsx"
# Row 1299 1a: the Classic theme's four groups (Views.jsx GROUPS_CLASSIC), the menu the Classic tests (window, tabs, overview) walk; (slug, menu name, cards)
CLASSIC_GROUPS = [("You", [("profile", "Profile", [("Essentials", "essentials-h"), ("Profile", "profile-h")]), ("appearance", "Look", [("Personal", "personal-h"), ("Theme", "theme-settings-h")])]),
                  ("All projects", [("projects", "Projects overview", [("Projects", "projects-h")]), ("backups", "Backups", [("Backups", "safety-h")])]),
                  ("Project settings", [("reports", "Reports and pages", [("Freshness", "review-days-h"), ("Gantt", "gantt-setting-h"), ("Work items board", "board-setting-h")]),
                                        ("brand", "Brand and publishing", [("Publishing", "client-folder-h"), ("Brands", "brands-h")]), ("people", "People", [("People", "people-h")]),
                                        ("claude", "ask clark", [("Asking", "ask-settings-h")]), ("data", "Export and import", [("Data", "data-card-h")])]),
                  ("Help and about", [("version", "Version and updates", [("Version and updates", "update-h"), ("Quit", "quit-h")]), ("logs", "Logs and diagnostics", [("Logs and diagnostics", "diagnostics-h")])])]
CLASSIC_PAGES = [page for _, pages in CLASSIC_GROUPS for page in pages]
GROUPS = OLD_GROUPS      # row 1299 1a: the four groups are the Classic theme's only; these tests run with the Cards look, which keeps the five groups
PAGES = [page for _, pages in GROUPS for page in pages]      # (slug, menu name, cards)
PAGE_OF = {head: slug for slug, _, cards in PAGES for _, head in cards}      # which page a card's heading is on
FIRST = "projects"      # the plain address is the Projects page (router.SETTINGS_PAGES[0]); the old slugs all work


def address(slug, project="PUB"):
    """The address of a Settings page: the first page is the plain one."""
    return f"#settings&p={project}" + ("" if slug == FIRST else f"&s={slug}")


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
    def open_settings(self, p, w, mode="light", page=FIRST):
        p.width(w)
        scheme(p, mode)
        rate = int(os.environ.get("CLARK_TEST_CPU_THROTTLE", "0") or 0)      # tests only: a slow runner (macOS headless) on any machine
        if rate > 1:
            p.cdp.call("Emulation.setCPUThrottlingRate", {"rate": rate}, p.sid)
        slow = int(os.environ.get("CLARK_TEST_SLOW_RAF", "0") or 0)      # tests only: a frame callback every N ms, like macOS headless
        if slow:
            p.js("(function(){ var r = window.requestAnimationFrame.bind(window); window.requestAnimationFrame = function(f){ return setTimeout(function(){ r(f); }, %d); }; })()" % slow)
        p.js(f"location.hash = '{address(page)}'")
        heads = " && ".join(f"!!document.getElementById('{head}')" for _, head in dict(((s, c) for s, _, c in PAGES))[page])
        p.until(f"!!document.querySelector('.set-nav .set-chip[aria-current]') && {heads}", "Settings, its menu and the page's cards drew")
        p.settled("Settings finished drawing and scrolling")

    def to_page(self, p, slug):
        """Another Settings page by its address, in the page that is open (nothing reloads); wait until it is the marked one with its cards drawn."""
        p.js(f"location.hash = '{address(slug)}'")
        heads = " && ".join(f"!!document.getElementById('{head}')" for _, head in dict(((s, c) for s, _, c in PAGES))[slug])
        name = {s: n for s, n, _ in PAGES}[slug]
        p.until(f"(document.querySelector('.set-chip[aria-current]') || {{}}).textContent === '{name}' && {heads}", f"the {name} page drew")

    def go_page(self, p, slug):
        """Open a Settings page by its menu item, as a person does, and wait until it is the marked one with its cards drawn."""
        name = {s: n for s, n, _ in PAGES}[slug]
        heads = " && ".join(f"!!document.getElementById('{head}')" for _, head in dict(((s, c) for s, _, c in PAGES))[slug])
        drew = f"(function(){{var c = document.querySelector('.set-chip[aria-current]'); return !!c && c.textContent === '{name}';}})() && {heads}"
        p.until(f"[...document.querySelectorAll('.set-nav .set-chip')].some(b => b.textContent === '{name}')", f"the {name} menu item is drawn")
        p.settled(f"the {name} menu item stopped moving before it is clicked")
        self.click_chip(p, name)
        if not wait(lambda: p.js(drew), 15):
            # The evidence is read only after the wait failed: a passing run costs nothing extra.
            chip = p.js("(document.querySelector('.set-chip[aria-current]')||{}).textContent")
            self.fail(f"the {name} page drew; location.hash={p.js('location.hash')!r}; marked chip={chip!r}; heading present={p.js(heads)}; trail={self.trail(p)}")
        p.settled("the page finished drawing")

    def chips(self, p):
        return p.js("[...document.querySelectorAll('.set-nav .set-chip')].map(b => b.textContent)")

    def numbers(self, p, head_id):
        """What a red 'heading in view' needs to name itself (the hosted macOS runner printed no numbers): the heading's box, the scroll, the
        window, the sticky set-bar, the scroll margin and padding that keep a heading clear of it, and whether the runner asks for reduced motion."""
        return p.js(f"""(function(){{
          var h = document.getElementById('{head_id}'), r = h ? h.getBoundingClientRect() : null;
          var bar = document.querySelector('.set-head'), b = bar ? bar.getBoundingClientRect() : null;
          var nav = document.querySelector('.set-nav'), n = nav ? nav.getBoundingClientRect() : null;
          var card = h ? (h.closest('section, .card') || h) : null;
          var pad = document.scrollingElement ? getComputedStyle(document.scrollingElement).scrollPaddingTop : 'n/a';
          return 'head_id=' + '{head_id}' + ' heading top=' + (r ? r.top : 'none') + ' bottom=' + (r ? r.bottom : 'none') +
            ' scrollY=' + window.scrollY + ' innerHeight=' + window.innerHeight +
            ' set-head top=' + (b ? b.top : 'none') + ' bottom=' + (b ? b.bottom : 'none') + ' position=' + (bar ? getComputedStyle(bar).position : 'n/a') +
            ' set-nav top=' + (n ? n.top : 'none') + ' bottom=' + (n ? n.bottom : 'none') + ' position=' + (nav ? getComputedStyle(nav).position : 'n/a') +
            ' card scroll-margin-top=' + (card ? getComputedStyle(card).scrollMarginTop : 'n/a') +
            ' heading scroll-margin-top=' + (h ? getComputedStyle(h).scrollMarginTop : 'n/a') +
            ' scroll-padding-top=' + pad +
            ' reduced-motion=' + matchMedia('(prefers-reduced-motion: reduce)').matches;
        }})()""")

    def click_chip(self, p, name):
        """A person's click: the mouse moves to the chip's centre, goes down and comes up (Input.dispatchMouseEvent). A JS .click() has no
        mousedown, and the router's scroll restore after the hash change (router.js restore()) ends only on wheel, touchstart, keydown or
        mousedown, so on a slow runner (macOS headless: slow requestAnimationFrame) it was still alive and put the jump back to 0. Also
        starts a record of window.scrollY at +0/+100/+500/+2000 ms, which a failure prints."""
        find = f"[...document.querySelectorAll('.set-nav .set-chip')].find(b => b.textContent === '{name}')"
        at = None
        for _ in range(6):      # the menu is taller than a 900 px window: a person wheels the page down, then scrolls the list to the item, as often as it takes
            p.cdp.call("Input.dispatchMouseEvent", {"type": "mouseWheel", "x": p.js("innerWidth") - 60, "y": 300, "deltaX": 0, "deltaY": 3000}, p.sid)
            p.settled("the scroll to the foot finished")
            p.js(f"{find}.scrollIntoView({{block: 'center'}})")
            p.settled("the scroll to the menu item finished")
            if os.environ.get("CLARK_TEST_LATE_SCROLL") == "1":      # tests only: the wheel's scroll arrives after the page looked still (macOS headless), once per chip
                p.js("window.__late = window.__late || 0; if (window.__late++ % 6 === 0) window.scrollTo(0, 99999)")
            measure = f"(function(){{ var r = ({find}).getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2, innerWidth, innerHeight]; }})()"
            at = p.js(measure)
            if not (0 <= at[0] <= at[2] and 0 <= at[1] <= at[3]):
                # macOS run 45203372794, job 137792514843: the chip was read at y=1044 in a 900 px window with scrollY=0 after all 6 tries, so the scroll was
                # not applied (or was put back to 0) when it was measured. A GUESS, not measured: this try waits up to 3 s for the scroll to land, bringing the chip to the middle on each look; no run shows yet that it helps.
                seen = [at]

                def looked():
                    p.js(f"{find}.scrollIntoView({{block: 'center', behavior: 'instant'}})")
                    seen[0] = p.js(measure)
                    return 0 <= seen[0][0] <= seen[0][2] and 0 <= seen[0][1] <= seen[0][3]
                wait(looked, 3)
                at = seen[0]
            if 0 <= at[0] <= at[2] and 0 <= at[1] <= at[3]:
                break
        self.assertTrue(0 <= at[0] <= at[2] and 0 <= at[1] <= at[3], f"the {name} chip is inside the window to be clicked: {at}; scrollY={p.js('scrollY')}")
        # The pointer goes to the chip and the press waits until the real element is under it: a layout shift or a late scroll between the
        # measure and the press (macOS: slow frames) would put the press on another row. The wait only moves the pointer (no press) until the chip is under it at the same point twice running; then one press, one release.
        under = {}

        def on_chip():
            # A scroll that arrived late (the wheel's, on a slow runner) can have put the chip out of the window or under the sticky top bar since it was measured: bring it back (an instant scroll) before the pointer goes to it.
            p.js(f"(function(){{ var b = {find}, r = b.getBoundingClientRect(); if (document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2) !== b) b.scrollIntoView({{block: 'center', behavior: 'instant'}}); }})()")
            now = p.js(f"(function(){{ var b = {find}, r = b.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2; return [x, y, document.elementFromPoint(x, y) === b]; }})()")
            if under.get("at") == now[:2] and now[2]:
                return True
            under["at"] = now[:2]
            under["last"] = now
            p.cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": now[0], "y": now[1], "button": "none", "buttons": 0, "clickCount": 0}, p.sid)
            return False
        self.assertTrue(wait(on_chip, 15), f"the pointer is on the {name} menu item and it stopped moving; last read (x, y, chip under it): {under.get('last')}; scrollY={p.js('scrollY')}")
        for kind in ("mousePressed", "mouseReleased"):
            params = {"type": kind, "x": under["at"][0], "y": under["at"][1], "button": "left", "buttons": 1 if kind == "mousePressed" else 0, "clickCount": 1}
            p.cdp.call("Input.dispatchMouseEvent", params, p.sid)
        p.js("""(function(){ window.__trail = [];
          [0, 100, 500, 2000].forEach(function(ms){ setTimeout(function(){ window.__trail.push('+' + ms + 'ms scrollY=' + Math.round(window.scrollY)); }, ms); });
        })()""")

    def trail(self, p):
        return p.js("(window.__trail || []).join(', ') + ' hasFocus=' + document.hasFocus() + ' visibilityState=' + document.visibilityState")

    def at_top(self, p, head_id):
        """The card is in view and its heading has the focus."""
        p.settled("the chip's scroll finished")      # before anything is measured: the smooth scroll may still be running (macOS)
        if not wait(lambda: p.js(f"document.activeElement && document.activeElement.id === '{head_id}'"), 15):
            p.t.fail(f"focus is on {head_id}; after the click: " + self.trail(p))
        in_view = f"(function(){{var r = document.getElementById('{head_id}').getBoundingClientRect(); return r.top >= 56 && r.bottom <= window.innerHeight;}})()"
        if not wait(lambda: p.js(in_view), 15):
            p.t.fail("the heading is in view, clear of the top bar; " + self.numbers(p, head_id) + "; after the click: " + self.trail(p))
        # A window.scrollTo while the smooth scroll is still running cancels it and leaves the next chip's scroll stuck near the top, so
        # the position and the animations are checked again once the heading is found: still no animation, the same scrollY 100 ms apart.
        p.settled("the chip's scroll finished")

    def test_C_the_title_the_help_line_and_a_menu_item_for_each_page_that_exists(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode)
                    self.assertEqual(p.js("document.querySelector('.set-head h1').textContent"), "Settings")
                    self.assertEqual(p.js("document.querySelector('.set-head p').textContent"), HELP)
                    self.assertEqual(self.chips(p), [name for _, name, _ in PAGES])
                    self.assertEqual(p.js("[...document.querySelectorAll('.set-group-name')].map(e => e.textContent)"), [g for g, _ in GROUPS])
                    self.assertEqual(p.js("document.querySelector('.set-chip[aria-current]').textContent"), next(n for sl, n, _ in PAGES if sl == FIRST), "the plain address marks Projects, the page the router starts on")
                    for slug, name, cards in PAGES:
                        self.go_page(p, slug)
                        self.assertEqual(p.js("[...document.querySelectorAll('.set-chip[aria-current]')].map(b => b.textContent)"), [name], "one marked item")
                        self.assertEqual(p.js("[...document.querySelectorAll('.set-cards h2[id], .set-cards h3[id]')].map(h => h.id).filter(i => i.endsWith('-h'))"),
                                         [head for _, head in cards], f"the {name} page draws its cards and no others")
                        for card, head_id in cards:
                            said = p.js(f"document.getElementById('{head_id}').textContent")
                            self.assertEqual(said, card, "a card's heading says its name") if card != "Asking" else self.assertTrue(said.startswith("Asking in "), "the Asking card's heading says Asking in the project (row 1351)")
                            self.assertEqual(p.js(f"document.getElementById('{head_id}').getAttribute('tabindex')"), "-1")
                    for gone in ("AI", "Client folder", "Published reports"):
                        self.assertNotIn(gone, self.chips(p), f"no menu item for {gone}: there is no such page")
                    self.assertNotIn("Settings are not ready yet.", p.js("document.querySelector('main').innerText"))

    def test_C_a_click_opens_the_page_and_marks_it_and_the_address_keeps_it(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, w)
                for slug, name, cards in reversed(PAGES):
                    self.go_page(p, slug)
                    self.assertEqual(p.js("location.hash"), address(slug, "PUB"), "the page is in the address")
                    head_id = cards[0][1]
                    p.cdp.call("Input.dispatchMouseEvent", {"type": "mouseWheel", "x": p.js("innerWidth") - 60, "y": 300, "deltaX": 0, "deltaY": -3000}, p.sid)      # each page keeps the place it was left at (router.js): a wheel up to the top of it
                    in_view = f"(function(){{var r = document.getElementById('{head_id}').getBoundingClientRect(); return r.top >= 56 && r.top < window.innerHeight;}})()"
                    wait(lambda: p.js(in_view), 15)      # the wheel's scroll starts later than the wheel is sent (macOS), and a settled read before it starts sees a still page: wait for the heading itself
                    p.settled("the scroll to the top finished")
                    self.assertTrue(p.js(in_view),
                                    f"{head_id} starts in view, clear of the top bar: " + p.js("'top=' + document.getElementById('" + head_id + "').getBoundingClientRect().top + ' scrollY=' + scrollY"))

    def test_C_keyboard_tab_to_a_menu_item_and_enter(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 1400)
            p.js("document.querySelector('.set-nav .set-chip').focus()")
            p.key("Tab", code="Tab", vk=9)
            self.assertEqual(p.js("document.activeElement.textContent"), PAGES[1][1], "Tab moves from item to item")
            self.assertEqual(p.js("document.querySelectorAll('.set-nav .set-chip').length"), len(PAGES))
            p.key("Enter", code="Enter", vk=13)
            p.until(f"document.getElementById('{PAGES[1][2][0][1]}') !== null && document.querySelector('.set-chip[aria-current]').textContent === '{PAGES[1][1]}'", "Enter opened the page")
            self.assertEqual(p.js("document.querySelector('.set-chip[aria-current]').getAttribute('aria-current')"), "page")
            self.assertEqual(p.js("document.activeElement.textContent"), PAGES[1][1], "the focus stays on the item")
            self.assertEqual(p.js("getComputedStyle(document.activeElement).outlineWidth"), "2px", "the item shows the ring after the keyboard")

    def test_C_the_list_is_at_the_left_at_900_and_wider_and_a_row_of_chips_below_900(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode)
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")
                    self.assertTrue(p.js("(function(){var n = document.querySelector('.set-nav'); return n.scrollWidth <= n.clientWidth;})()"), "the list does not scroll sideways")
                    chips = p.js("[...document.querySelectorAll('.set-nav .set-chip')].map(b => { const r = b.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; })")
                    nav = p.js("(function(){var r = document.querySelector('.set-bar').getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom];})()")
                    first = p.js("(function(){var r = document.querySelector('.set-cards > section').getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom];})()")
                    for a, b in zip(chips, chips[1:]):
                        self.assertTrue(b[1] >= a[3] - 1 or b[0] >= a[2] - 1, "no two links overlap")
                    for h, wd in ((c[3] - c[1], c[2] - c[0]) for c in chips):
                        self.assertGreaterEqual(h, 24)
                        self.assertGreaterEqual(wd, 24)
                    # 1400 and 900 are both at or above the 900 px line: the list at the left. Only these two widths are tested.
                    self.assertEqual(p.js("getComputedStyle(document.querySelector('.set-nav')).flexDirection"), "column")
                    self.assertLessEqual(max(c[0] for c in chips) - min(c[0] for c in chips), 1, "the links stand in one column")
                    self.assertTrue(all(b[1] > a[1] for a, b in zip(chips, chips[1:])), "each link is below the one before")
                    self.assertLessEqual(nav[2], first[0] + 1, "the list is at the left of the cards")
                    self.assertLess(nav[2] - nav[0], w / 3, "the list does not eat the width")
                    self.assertGreater(first[2] - first[0], w / 2, "the cards keep most of the width")

    def test_C_text_size_and_contrast_in_light_and_dark(self):
        for mode in MODES:
            with self.subTest(mode=mode), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, 1400, mode)
                # item 1200: the rows are soft (no outline, no fill at rest), so the text is read on the bar's ground and the one thing that needs 3:1 is the violet marker of the marked row
                got = p.js("""[...document.querySelectorAll('.set-nav .set-chip:not([aria-current])')].map(b => { const s = getComputedStyle(b);
                    return [parseFloat(s.fontSize), s.color, s.backgroundColor === 'rgba(0, 0, 0, 0)' ? getComputedStyle(document.querySelector('.set-bar')).backgroundColor : s.backgroundColor, s.borderTopWidth]; })""")
                for size, color, ground, border in got:
                    self.assertGreaterEqual(size, 13)
                    self.assertGreaterEqual(ratio(rgb(color), rgb(ground)), 4.5, f"{mode}: the chip text on its ground")
                    self.assertEqual(border, "0px", f"{mode}: a soft row has no outline")
                marker, bar = p.js("""[getComputedStyle(document.querySelector('.set-chip[aria-current]'), '::before').backgroundColor, getComputedStyle(document.querySelector('.set-bar')).backgroundColor]""")
                self.assertGreaterEqual(ratio(rgb(marker), rgb(bar)), 3, f"{mode}: the marker of the marked row on the bar")
                p.js("document.querySelector('.set-nav .set-chip').focus()")
                p.key("Tab", code="Tab", vk=9)
                p.key("Tab", code="Tab", vk=9, )
                ring = p.js("(function(){var s = getComputedStyle(document.activeElement); return [s.outlineWidth, s.outlineStyle, s.outlineColor];})()")
                self.assertEqual(ring[:2], ["2px", "solid"])
                brand = p.js("(function(){var d = document.createElement('i'); d.style.color = 'var(--brand-blue)'; document.body.appendChild(d); var c = getComputedStyle(d).color; d.remove(); return c;})()")
                self.assertEqual(ring[2], brand, "the ring is the brand blue")


if __name__ == "__main__":
    unittest.main()
