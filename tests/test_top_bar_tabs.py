"""#681: the top bar at 1400, 901, 900 and 800 px, light and dark: every tab label is whole on one line, nothing is clipped or
overlapped, and the page does not scroll sideways. Chrome is required: these tests fail, never skip, without it.

Run: python3 dev/run_tests.py test_top_bar_tabs
"""
import unittest

from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

WIDTHS = (1400, 901, 900, 800)

# For each tab: its box, the box of its text, and the line height. Then the bar's other items, and the page's sideways scroll.
MEASURE = """(function(){
  var bar = document.querySelector('header.top').getBoundingClientRect(), out = {tabs: [], items: [], bar: [bar.left, bar.right]};
  document.querySelectorAll('.top .tab').forEach(function(t){
    var r = t.getBoundingClientRect(), s = document.createRange(); s.selectNodeContents(t);
    var lines = new Set(Array.from(s.getClientRects()).filter(function(q){ return q.width > 0; }).map(function(q){ return Math.round(q.top); }));
    out.tabs.push({name: t.textContent.trim(), left: r.left, right: r.right, lines: lines.size, over: t.scrollWidth > t.clientWidth + 1});
  });
  Array.from(document.querySelector('header.top').children).forEach(function(c){
    var r = c.getBoundingClientRect(); if (r.width > 0) out.items.push({cls: c.className, left: r.left, right: r.right});
  });
  out.scroll = [document.documentElement.scrollWidth, document.documentElement.clientWidth];
  return out;
})()"""


class TopBarTabs(Base):
    def measure(self, width, theme, long_name=False, edit=False):
        with chrome() as cdp:
            p = self.visit(cdp)
            size(cdp, p, width, 700)
            p.js(f"document.documentElement.setAttribute('data-theme', '{theme}')")
            if edit:
                p.js("document.querySelector('.top [data-mode=edit]').click()")
            if long_name:       # the longest name a person is likely to give a project: it must shorten, never push a tab out
                self.assertTrue(p.js("(function(){ var s = document.querySelector('.top .projbtn > span') || document.querySelector('.top .proj'); "
                                     "if (!s) return false; s.textContent = 'Customer onboarding programme, phase two, northern region'; return true; })()"),
                                f"at {width} px, {theme}: the long-name check found no project name in the top bar ('.top .projbtn > span' or '.top .proj'), "
                                "so it did not test a long name at all; the bar's markup has changed")
            return p.js(MEASURE)

    def box(self, p, selector):
        return p.js(f"(function(){{ var e = document.querySelector({selector!r}); if (!e) return null; var r = e.getBoundingClientRect(); return [r.width, e.scrollWidth, e.clientWidth]; }})()")

    def switch_widths(self, width, theme):
        out = []
        for edit in (False, True):       # a fresh page each: the name is lengthened after the mode is set, as check() does
            with chrome() as cdp:
                p = self.visit(cdp)
                size(cdp, p, width, 700)
                p.js(f"document.documentElement.setAttribute('data-theme', '{theme}')")
                p.until("!!document.querySelector('.modes')", f"at {width} px, {theme}: the View/Edit switch (.modes; on the Dashboard it is the report bar's pill, off it the top bar's) never appeared")
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

    def check(self, width, theme, long_name=False, edit=False):
        got = self.measure(width, theme, long_name, edit)
        where = f"at {width} px, {theme}{', long name' if long_name else ''}{', Edit' if edit else ''}"
        self.assertGreaterEqual(len(got["tabs"]), 3, where)
        for t in got["tabs"]:
            self.assertEqual(t["lines"], 1, f"{where}: the {t['name']!r} tab is on {t['lines']} lines")
            self.assertFalse(t["over"], f"{where}: the {t['name']!r} tab is wider than its box")
            self.assertGreaterEqual(t["left"], got["bar"][0], f"{where}: {t['name']!r} starts left of the bar")
            self.assertLessEqual(t["right"], got["bar"][1] + 0.5, f"{where}: {t['name']!r} runs past the bar")
        items = sorted(got["items"], key=lambda i: i["left"])
        for a, b in zip(items, items[1:]):
            self.assertLessEqual(a["right"], b["left"] + 0.5, f"{where}: {a['cls']!r} overlaps {b['cls']!r}")
        self.assertLessEqual(items[-1]["right"], got["bar"][1] + 0.5, f"{where}: {items[-1]['cls']!r} is clipped by the window")
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
            p.js("document.querySelector('.top .tab[data-view=work]').click()")
            p.until("document.querySelector('.top .tab[aria-selected=true]').dataset.view === 'work'", "Work items did not open")
            if edit:
                p.js("document.querySelector('.top [data-mode=edit]').click()")
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
            p.js("document.activeElement.blur()")
            p.key("Tab", 0, "Tab", 9)
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

if __name__ == "__main__":
    unittest.main()
