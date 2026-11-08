"""#681, row 757: the top bar at 1400, 901 and 900 px, light and dark, on the Dashboard, Use cases and Settings, in View and Edit, with a long
project name: every tab label is whole on one line, the bar stays one 56 px row, the project name shortens first, then the tab row scrolls inside
its own box with the open tab fully inside it, nothing is clipped or overlapped, and the page does not scroll sideways. Chrome is required: these
tests fail, never skip, without it.

Run: python3 dev/run_tests.py test_top_bar_tabs
"""
import sqlite3
import unittest

from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

WIDTHS = (1400, 901, 900)      # the owner's scope is 1400 and 900 px (901 is the neighbour that must not move)

# Each tab's box and line count; the bar's top-level items (the tab row among them); the tab row's scroll; the project name's box; the page's sideways scroll.
MEASURE = """(function(){
  var bar = document.querySelector('header.top').getBoundingClientRect(), out = {tabs: [], items: [], bar: [bar.left, bar.right, bar.top, bar.bottom]};
  var row = document.querySelector('.top .tabs'), rb = row.getBoundingClientRect(), dd = document.querySelector('.top .dd:has(> .projbtn)');
  out.row = [rb.left, rb.right, row.scrollWidth, row.clientWidth];
  out.name = dd ? dd.getBoundingClientRect().width : 0;
  document.querySelectorAll('.top .tab').forEach(function(t){
    var r = t.getBoundingClientRect(), s = document.createRange(); s.selectNodeContents(t);
    var lines = new Set(Array.from(s.getClientRects()).filter(function(q){ return q.width > 0; }).map(function(q){ return Math.round(q.top); }));
    out.tabs.push({name: t.textContent.trim(), left: r.left, right: r.right, lines: lines.size, over: t.scrollWidth > t.clientWidth + 1, open: t.getAttribute('aria-selected') === 'true'});
  });
  Array.from(document.querySelector('header.top').children).forEach(function(c){
    var r = c.getBoundingClientRect(); if (r.width > 0) out.items.push({cls: c.className || 'item', left: r.left, right: r.right, top: r.top, bottom: r.bottom});
  });
  out.scroll = [document.documentElement.scrollWidth, document.documentElement.clientWidth];
  return out;
})()"""


class TopBarTabs(Base):
    def measure(self, width, theme, long_name=False, edit=False, active=None):
        with sqlite3.connect(str(self.store.path)) as con:      # asking on: the ask clark button is in the bar, the widest case
            con.execute("UPDATE app_settings SET ask_enabled = 1 WHERE id = 1")
        with chrome() as cdp:
            p = self.visit(cdp)
            size(cdp, p, width, 700)
            p.until("!!document.querySelector('#ask-btn')", "the ask button shows")
            p.js(f"document.documentElement.setAttribute('data-theme', '{theme}')")
            if edit:
                p.js("document.querySelector('.top [data-mode=edit]').click()")
            if long_name:       # the longest name a person is likely to give a project: it must shorten, never push a tab out
                self.assertTrue(p.js("(function(){ var s = document.querySelector('.top .projbtn > span') || document.querySelector('.top .proj'); "
                                     "if (!s) return false; s.textContent = 'Customer onboarding programme, phase two, northern region'; return true; })()"),
                                f"at {width} px, {theme}: the long-name check found no project name in the top bar ('.top .projbtn > span' or '.top .proj'), "
                                "so it did not test a long name at all; the bar's markup has changed")
            if active == "Settings":      # row 976: Settings is no tab; it opens from the profile circle's menu
                p.js("document.querySelector('#profile-btn').click()")
                p.until("!!document.querySelector('#profile-menu')", "the profile menu opened")
                p.js("document.querySelector('#profile-menu [data-kind=settings], #profile-menu [data-kind=who]').click()")
                p.until("document.querySelector('h1') && document.querySelector('h1').textContent === 'Settings'", "Settings opened from the menu")
            elif active:
                p.js(f"[...document.querySelectorAll('.top .tab')].filter(t => t.textContent.trim() === '{active}')[0].click()")
                p.until(f"[...document.querySelectorAll('.top .tab')].some(t => t.textContent.trim() === '{active}' && t.getAttribute('aria-selected') === 'true')", f"{active} is the open tab")
            p.js("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
            got = p.js(MEASURE)
            # each tab can be brought inside the tab row (the row scrolls in its own box): its box then lies within the row's
            got["reach"] = p.js("Array.from(document.querySelectorAll('.top .tab')).map(function(t){ t.scrollIntoView({inline: 'nearest', block: 'nearest'}); "
                                "var r = t.getBoundingClientRect(), b = document.querySelector('.top .tabs').getBoundingClientRect(); "
                                "return {name: t.textContent.trim(), inside: r.left >= b.left - 0.5 && r.right <= b.right + 0.5}; })")
            got["scroll_after"] = p.js("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
            return got

    def box(self, p, selector):
        return p.js(f"(function(){{ var e = document.querySelector({selector!r}); if (!e) return null; var r = e.getBoundingClientRect(); return [r.width, e.scrollWidth, e.clientWidth]; }})()")

    def switch_widths(self, width, theme):
        out = []
        for edit in (False, True):       # a fresh page each: the name is lengthened after the mode is set, as check() does
            with chrome() as cdp:
                p = self.visit(cdp)
                size(cdp, p, width, 700)
                p.js(f"document.documentElement.setAttribute('data-theme', '{theme}')")
                p.until("!!document.querySelector('.modes')", f"at {width} px, {theme}: the View/Edit switch (.modes; the Dashboard report bar's pill) never appeared")
                if edit:
                    p.js("document.querySelector('.modes [data-mode=edit]').click()")
                p.js("document.querySelector('.top .projbtn > span').textContent = 'Customer onboarding programme, phase two, northern region'")
                out.append(self.box(p, ".modes"))
        return out

    def tab_style(self, width):
        with chrome() as cdp:
            p = self.visit(cdp)
            size(cdp, p, width, 700)
            return p.js("(function(){ var s = getComputedStyle(document.querySelector('.top .tab')); return [s.paddingLeft, s.paddingRight, s.whiteSpace]; })()")

    def check(self, width, theme, long_name=False, edit=False, active=None):
        got = self.measure(width, theme, long_name, edit, active)
        where = f"at {width} px, {theme}{', long name' if long_name else ''}{', Edit' if edit else ''}{', ' + active if active else ', Dashboard'}"
        self.assertGreaterEqual(len(got["tabs"]), 3, where)
        scrolls = got["row"][2] > got["row"][3] + 1       # a sub-pixel overhang from the name's share of the shrink is not a scroll
        for t in got["tabs"]:
            self.assertEqual(t["lines"], 1, f"{where}: the {t['name']!r} tab is on {t['lines']} lines")
            self.assertFalse(t["over"], f"{where}: the {t['name']!r} tab is wider than its box")
            if t["open"] or not scrolls:       # the open tab is whole inside the tab row's box; with no scroll every tab is
                self.assertGreaterEqual(t["left"], got["row"][0] - 0.5, f"{where}: {t['name']!r} starts left of the tab row")
                self.assertLessEqual(t["right"], got["row"][1] + 1, f"{where}: {t['name']!r} is cut off by the tab row's right edge")
        self.assertNotIn("Settings", [t["name"] for t in got["tabs"]], f"{where}: Settings is not a top-bar tab (row 976)")
        self.assertEqual(sum(1 for t in got["tabs"] if t["open"]), 0 if active == "Settings" else 1, where)      # on Settings no tab is pressed: it is not a tab
        if scrolls and width > 800:       # 800 px and below stay as main has them (the name keeps its width, the row scrolls): row 757 is 900 px only
            self.assertLessEqual(got["name"], 73, f"{where}: the tab row scrolls while the project name is still {got['name']} px wide")
        self.assertAlmostEqual(got["bar"][3] - got["bar"][2], 56, delta=0.5, msg=f"{where}: the bar is not one 56 px row")
        self.assertGreaterEqual(got["row"][0], got["bar"][0], f"{where}: the tab row starts left of the bar")
        self.assertLessEqual(got["row"][1], got["bar"][1] + 0.5, f"{where}: the tab row runs past the bar")
        items = got["items"]
        for k, a in enumerate(items):
            self.assertLessEqual(a["right"], got["bar"][1] + 0.5, f"{where}: {a['cls']!r} is clipped by the window")
            for b in items[k + 1:]:
                apart = a["right"] <= b["left"] + 0.5 or b["right"] <= a["left"] + 0.5 or a["bottom"] <= b["top"] + 0.5 or b["bottom"] <= a["top"] + 0.5
                self.assertTrue(apart, f"{where}: {a['cls']!r} overlaps {b['cls']!r}")
        self.assertLessEqual(got["scroll"][0], got["scroll"][1], f"{where}: the page scrolls sideways {got['scroll']}")

    # Under 1 px: the pressed segment is set in the medium weight, which makes its word about half a pixel wider; a real shift is far more.
    def test_the_view_edit_switch_is_the_same_width_in_view_and_in_edit_with_a_long_name(self):
        for width in WIDTHS:
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme):
                    view, edit = self.switch_widths(width, theme)
                    self.assertIsNotNone(view, f"at {width} px, {theme}: no '.modes' (the View and Edit switch) on the page")
                    self.assertAlmostEqual(view[0], edit[0], delta=1, msg=f"at {width} px, {theme}: the View/Edit switch is {view[0]} px wide in View and {edit[0]} px in Edit")
                    self.assertLessEqual(view[1], view[2] + 1, f"at {width} px, {theme}: the View/Edit switch is squeezed narrower than its content")

    def test_the_tabs_tighten_their_padding_at_1000_px_and_below_and_never_wrap(self):
        for width, pad in ((1400, "14px"), (1001, "14px"), (1000, "8px"), (900, "8px"), (800, "8px"), (600, "6px")):
            with self.subTest(width=width):
                left, right, wrap = self.tab_style(width)
                self.assertEqual([left, right], [pad, pad], f"at {width} px the tab padding should be {pad}; got {left} and {right}")
                self.assertEqual(wrap, "nowrap", f"at {width} px a tab label may wrap onto a second line (white-space is {wrap!r})")

    # Row 854: the logo is a Home button. It is a real button, reached with Tab (first stop in the bar, after the skip link of row 862), draws a focus ring, is named by
    # its existing words, and goes to the first tab (the Dashboard) of the same project, in View and in Edit.
    def home(self, width, theme, edit):
        with chrome() as cdp:
            p = self.visit(cdp)       # ready() waits for the Dashboard's sections, so open there and go to Work items by its tab
            size(cdp, p, width, 700)
            p.js(f"document.documentElement.setAttribute('data-theme', '{theme}')")
            if edit:       # row 804: View | Edit is the Dashboard's pill, so Edit is chosen there, before Work items opens
                p.js("document.querySelector('.top [data-mode=edit]').click()")
            p.js("document.querySelector('.top .tab[data-view=work]').click()")
            p.until("document.querySelector('.top .tab[aria-selected=true]').dataset.view === 'work'", "Work items did not open")
            self.assertEqual(p.js("document.querySelectorAll('.top [data-mode]').length"), 0, "no View | Edit switch on Work items")
            where = f"at {width} px, {theme}, {'Edit' if edit else 'View'}"
            self.assertEqual(p.js("document.querySelector('.top .logo') && document.querySelector('.top .logo').tagName"), "BUTTON", f"{where}: the logo is not a button")
            self.assertTrue(p.js("(document.querySelector('.top .logo').getAttribute('aria-label') || '').trim().length > 0"), f"{where}: the logo has no accessible name")
            p.js("document.activeElement && document.activeElement.blur()")
            p.key("Tab", 0, "Tab", 9)
            self.assertTrue(p.js("document.activeElement.classList.contains('skip')"), f"{where}: the first Tab stop is not the skip link (row 862)")
            p.key("Tab", 0, "Tab", 9)
            self.assertTrue(p.js("document.activeElement.classList.contains('logo')"), f"{where}: Tab does not reach the logo after the skip link")
            self.assertNotEqual(p.js("getComputedStyle(document.activeElement).outlineStyle"), "none", f"{where}: the focused logo has no focus ring")
            self.assertGreater(p.js("parseFloat(getComputedStyle(document.activeElement).outlineWidth)"), 0, f"{where}: the focus ring has no width")
            for kind in ("keyDown", "keyUp"):       # a real Enter, with its text as a keyboard sends it: a bare key event does not press a button
                cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13,
                                                    **({"text": "\r"} if kind == "keyDown" else {})}, p.sid)
            p.until("location.hash.indexOf('#dashboard') === 0 && location.hash.indexOf('p=ABC') > 0", f"{where}: Enter on the logo does not go to the Dashboard of the same project")
            self.assertEqual(p.js("document.querySelector('.top .tab[aria-selected=true]').dataset.view"), "dashboard", f"{where}: the first tab is not the pressed one")
            p.js("document.querySelector('.top .tab[data-view=work]').click()")
            p.until("document.querySelector('.top .tab[aria-selected=true]').dataset.view === 'work'", f"{where}: could not return to Work items")
            p.js("document.querySelector('.top .logo').click()")
            p.until("location.hash.indexOf('#dashboard') === 0", f"{where}: a click on the logo does not go to the Dashboard")


    def test_800_and_641_px_do_not_scroll_the_page_sideways_as_on_main(self):
        # Row 757 is 900 px only: below 801 px the tab row keeps main's rule (it scrolls inside its own box), so the bar never grows wider than the window.
        for width in (800, 700, 641):
            for active, edit in ((None, False), ("Settings", False), ("Settings", True), (None, True)):
                got = self.measure(width, "light", True, edit, active)
                self.assertLessEqual(got["scroll"][0], got["scroll"][1], f"at {width} px, {active}: the page scrolls sideways {got['scroll']}")
                self.assertLessEqual(max(i["right"] for i in got["items"]), got["bar"][1] + 0.5, f"at {width} px, {active}: an item runs past the window")

    def test_the_tab_row_keeps_room_for_its_tabs_at_420_and_360_px(self):
        # Row 1033: at 420 px the project name kept 160 px, so the tab row got 61 px (360 px: 1 px) and Settings, last of the five tabs, sat far off the
        # bar's edge. The name gives way first (as it does from 801 to 1000 px); the row keeps room for at least a tab and a quarter and still scrolls inside its box.
        # Row 976 (a branch) drops the Settings tab from the bar; this test then needs only the row's room, so it names the last tab, whichever it is.
        for width in (420, 360):
            for edit in (False, True):
                with self.subTest(width=width, edit=edit):
                    got = self.measure(width, "light", True, edit)
                    where = f"at {width} px{', Edit' if edit else ''}"
                    self.assertGreaterEqual(got["row"][1] - got["row"][0], 110, f"{where}: the tab row is only {got['row'][1] - got['row'][0]:.0f} px wide; the project name is {got['name']:.0f} px")
                    self.assertGreaterEqual(got["name"], 48, f"{where}: the project name box is squeezed to {got['name']:.0f} px")
                    self.assertLessEqual(max(i["right"] for i in got["items"]), got["bar"][1] + 0.5, f"{where}: an item runs past the window")
                    self.assertLessEqual(got["scroll"][0], got["scroll"][1], f"{where}: the page scrolls sideways {got['scroll']}")

    def test_the_tab_row_is_usable_on_the_settings_route_at_420_and_360_px(self):
        # Row 976 + row 1033: Settings is no tab, so the Settings route shows no open tab; the row still keeps at least 110 px, the page does not scroll
        # sideways, and every tab (Dashboard, Work items, ...) can be brought into the row.
        for width in (420, 360):
            for edit in (False, True):
                with self.subTest(width=width, edit=edit):
                    got = self.measure(width, "light", True, edit, active="Settings")
                    where = f"at {width} px{', Edit' if edit else ''}, Settings route"
                    self.assertGreaterEqual(got["row"][1] - got["row"][0], 110, f"{where}: the tab row is {got['row'][1] - got['row'][0]:.0f} px wide")
                    self.assertLessEqual(got["scroll"][0], got["scroll"][1], f"{where}: the page scrolls sideways {got['scroll']}")
                    self.assertLessEqual(got["scroll_after"][0], got["scroll_after"][1], f"{where}: bringing a tab into view scrolls the page sideways {got['scroll_after']}")
                    names = [t["name"] for t in got["reach"]]
                    self.assertEqual(names[0], "Dashboard", where)
                    self.assertIn("Work items", names, where)
                    self.assertNotIn("Settings", names, where)
                    self.assertTrue(all(t["inside"] for t in got["reach"]), f"{where}: a tab cannot be brought into the row {got['reach']}")

    def test_the_tab_row_is_not_squeezed_from_420_to_800_px(self):
        for width in (420, 480, 481, 600, 700, 800):
            with self.subTest(width=width):
                got = self.measure(width, "light", True, False)
                row = got["row"][1] - got["row"][0]
                self.assertGreaterEqual(row, 110, f"at {width} px the tab row is only {row:.0f} px wide; the project name is {got['name']:.0f} px")
                self.assertGreaterEqual(got["name"], 48, f"at {width} px the project name box is {got['name']:.0f} px")
                self.assertLessEqual(got["scroll"][0], got["scroll"][1], f"at {width} px the page scrolls sideways {got['scroll']}")
                self.assertGreaterEqual(len(got["tabs"]), 4, f"at {width} px the tabs are {[t['name'] for t in got['tabs']]}")

    def test_a_row_narrowed_after_the_scroll_shows_the_open_tab_again_at_900(self):
        # The exact failing case: 900 px, the profile circle in the bar, the last tab open; then the tab row narrows (as it does when the mode switch joins
        # the bar on leaving the Dashboard) and the open tab, already scrolled to, must be brought into the row again.
        with sqlite3.connect(str(self.store.path)) as con:
            con.execute("UPDATE app_settings SET ask_enabled = 1 WHERE id = 1")
        with chrome() as cdp:
            p = self.visit(cdp)
            size(cdp, p, 900, 700)
            p.until("!!document.querySelector('#ask-btn') && !!document.querySelector('#profile-btn')", "the ask button and the profile circle show")
            p.js("[...document.querySelectorAll('.top .tab')].filter(t => t.textContent.trim() === 'Use cases')[0].click()")      # row 976: the last tab (Settings was it before)
            p.js("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
            p.js("(function(){ var s = document.createElement('span'); s.id = 'test-spacer'; s.style.cssText = 'flex:none;width:90px;height:1px'; "
                 "document.querySelector('.top .tabs').after(s); })()")
            # A bounded wait, not a fixed sleep: under load the observer's re-scroll can land after 300 ms. A real regression still fails at the end of it.
            p.until("(function(){ var row = document.querySelector('.top .tabs').getBoundingClientRect(), "
                    "t = document.querySelector('.top .tab[aria-selected=true]').getBoundingClientRect(); return t.right <= row.right + 0.5 && t.left >= row.left - 0.5; })()",
                    "the open tab comes back into the tab row")
            # it must still be whole after the layout and the fonts have settled
            p.js("new Promise(r => setTimeout(r, 1500))")
            got = p.js("(function(){ var row = document.querySelector('.top .tabs').getBoundingClientRect(), "
                       "t = document.querySelector('.top .tab[aria-selected=true]').getBoundingClientRect(); return [t.left, t.right, row.left, row.right]; })()")
            self.assertGreaterEqual(got[0], got[2] - 0.5, f"Use cases starts left of the tab row {got}")
            self.assertLessEqual(got[1], got[3] + 0.5, f"Use cases is cut off by the tab row's right edge {got}")


class SkipLink(Base):
    """Row 862: 'Skip to content' is the first Tab stop, hidden until focused; Enter moves focus into <main>; the rest of the order is unchanged."""
    def skip(self, width, theme, edit):
        with chrome() as cdp:
            p = self.visit(cdp)
            size(cdp, p, width, 700)
            p.js(f"document.documentElement.setAttribute('data-theme', '{theme}')")
            if edit:
                p.js("document.querySelector('.top [data-mode=edit]').click()")
            where = f"at {width} px, {theme}, {'Edit' if edit else 'View'}"
            first = "(function(){ var e = document.querySelector('a.skip'); if (!e) return null; var r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; })()"
            hidden = p.js(first)
            self.assertIsNotNone(hidden, f"{where}: no skip link")
            self.assertLessEqual(hidden[3], 0, f"{where}: the skip link is on screen before it has focus")
            p.js("document.activeElement && document.activeElement.blur()")
            p.key("Tab", 0, "Tab", 9)
            self.assertTrue(p.js("document.activeElement.classList.contains('skip')"), f"{where}: the first Tab stop is not the skip link")
            self.assertEqual(p.js("document.activeElement.textContent.trim()"), "Skip to content")
            shown = p.js(first)
            self.assertGreaterEqual(shown[1], 0, f"{where}: the focused skip link is above the window")
            self.assertGreater(shown[2], shown[0], f"{where}: the focused skip link has no width")
            self.assertNotEqual(p.js("getComputedStyle(document.activeElement).outlineStyle"), "none", f"{where}: no focus ring")
            self.assertNotEqual(p.js("getComputedStyle(document.activeElement).color"), p.js("getComputedStyle(document.activeElement).backgroundColor"))
            p.key("Tab", 0, "Tab", 9)      # the order after it is the one it had: the logo, then the rest of the bar
            self.assertTrue(p.js("document.activeElement.classList.contains('logo')"), f"{where}: the second Tab stop is not the logo")
            p.js("document.querySelector('a.skip').focus()")      # a blur keeps Tab's starting point at the logo, so put focus back on the link itself
            self.assertTrue(p.js("document.activeElement.classList.contains('skip')"), f"{where}: the skip link would not take focus")
            for kind in ("keyDown", "keyUp"):
                cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13,
                                                    **({"text": "\r"} if kind == "keyDown" else {})}, p.sid)
            p.until("document.activeElement && document.activeElement.id === 'main'", f"{where}: Enter on the skip link does not put focus on the main area")
            self.assertEqual(p.js("document.querySelector('.top .tab[aria-selected=true]').dataset.view"), "dashboard", f"{where}: the skip link changed the page")
            self.assertEqual(p.js("document.querySelectorAll('button.skip, .skip[role=button]').length"), 0)

    def test_the_source_has_the_link_first_and_main_can_take_focus(self):
        from pathlib import Path
        src = Path(__file__).resolve().parent.parent / "src" / "clark" / "page"
        app = (src / "src" / "components" / "App.jsx").read_text(encoding="utf-8")
        self.assertRegex(app, r'<a\s+class="skip"\s+href="#main"[^>]*>\s*Skip to content\s*</a>')
        self.assertLess(app.index('class="skip"'), app.index("<TopBar"), "the skip link must come before the top bar")
        self.assertRegex(app, r'<main\s+id="main"\s+tabIndex=\{-1\}')
        self.assertRegex((src / "shell.css").read_text(encoding="utf-8"), r"\.skip\s*\{")


for _w in (1400, 900):
    for _t in ("light", "dark"):
        for _e in (False, True):
            setattr(SkipLink, f"test_skip_link_at_{_w}_{_t}_{'edit' if _e else 'view'}", lambda self, w=_w, t=_t, e=_e: self.skip(w, t, e))


for _w in WIDTHS:
    for _t in ("light", "dark"):
        setattr(TopBarTabs, f"test_at_{_w}_{_t}", lambda self, w=_w, t=_t: self.check(w, t))
        for _e in (False, True) if _w in (1400, 900) else ():
            setattr(TopBarTabs, f"test_the_logo_goes_home_at_{_w}_{_t}_{'edit' if _e else 'view'}", lambda self, w=_w, t=_t, e=_e: self.home(w, t, e))
        setattr(TopBarTabs, f"test_at_{_w}_{_t}_long_name_in_edit", lambda self, w=_w, t=_t: self.check(w, t, True, True))
        setattr(TopBarTabs, f"test_settings_at_{_w}_{_t}", lambda self, w=_w, t=_t: self.check(w, t, False, False, "Settings"))
        setattr(TopBarTabs, f"test_settings_at_{_w}_{_t}_long_name_in_edit", lambda self, w=_w, t=_t: self.check(w, t, True, True, "Settings"))
        setattr(TopBarTabs, f"test_settings_at_{_w}_{_t}_long_name_in_view", lambda self, w=_w, t=_t: self.check(w, t, True, False, "Settings"))
        setattr(TopBarTabs, f"test_work_items_at_{_w}_{_t}_long_name_in_edit", lambda self, w=_w, t=_t: self.check(w, t, True, True, "Work items"))
        setattr(TopBarTabs, f"test_use_cases_at_{_w}_{_t}_long_name_in_view", lambda self, w=_w, t=_t: self.check(w, t, True, False, "Use cases"))

if __name__ == "__main__":
    unittest.main()
