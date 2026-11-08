"""Row 757: the project button in the top bar does not collapse in a 915 px window (it runs the 900 px layout) or at 900 px, on any tab, in light and
dark, in View and Edit, with a long project name written as an invented name. The button keeps a readable width with an ellipsis, stays clear of the first
tab, the tab row scrolls inside its own box and the page does not scroll sideways. Chrome is required: these tests fail, never skip, without it.

Run: python3 dev/run_tests.py test_top_bar_tabs_915
"""
import sqlite3
import unittest

from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

TABS = (None, "Work items", "Milestones", "Use cases", "Settings")      # None is the Dashboard
LONG = "Example Client onboarding programme, phase two, northern region"

MEASURE = """(function(){
  var pb = document.querySelector('.top .projbtn'), sp = pb.querySelector(':scope > span'), b = pb.getBoundingClientRect(), s = sp.getBoundingClientRect();
  var row = document.querySelector('.top .tabs'), f = row.getBoundingClientRect();      // the tab row's own edge: its first tab may be scrolled out of view
 
  return {btn: b.width, text: s.width, trunc: sp.scrollWidth > sp.clientWidth, gap: f.left - b.right, rowScrolls: row.scrollWidth > row.clientWidth + 1,
          page: document.documentElement.scrollWidth - document.documentElement.clientWidth};
})()"""


class ProjectButtonFit(Base):
    def measure(self, width, theme, edit, active):
        with sqlite3.connect(str(self.store.path)) as con:
            con.execute("UPDATE app_settings SET ask_enabled = 1 WHERE id = 1")
        with chrome() as cdp:
            p = self.visit(cdp)
            size(cdp, p, width, 700)
            p.until("!!document.querySelector('#ask-btn') && !!document.querySelector('.top .projbtn > span')", "the bar shows")
            p.js(f"document.documentElement.setAttribute('data-theme', '{theme}')")
            if edit:
                p.js("document.querySelector('.top [data-mode=edit]').click()")
            if active == "Settings":      # row 976: Settings is no tab; it opens from the profile circle's menu
                p.js("document.querySelector('#profile-btn').click()")
                p.until("!!document.querySelector('#profile-menu')", "the profile menu opened")
                p.js("document.querySelector('#profile-menu [data-kind=settings], #profile-menu [data-kind=who]').click()")
                p.until("document.querySelector('h1') && document.querySelector('h1').textContent === 'Settings'", "Settings opened from the menu")
                self.assertEqual(p.js("document.querySelectorAll('.top .tab[data-view=settings]').length"), 0, "Settings is not a top-bar tab")
            elif active:
                p.js(f"[...document.querySelectorAll('.top .tab')].filter(t => t.textContent.trim() === '{active}')[0].click()")
                p.until(f"[...document.querySelectorAll('.top .tab')].some(t => t.textContent.trim() === '{active}' && t.getAttribute('aria-selected') === 'true')", active)
            p.js(f"document.querySelector('.top .projbtn > span').textContent = {LONG!r}")
            p.js("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
            return p.js(MEASURE)

    def check(self, width, theme, edit, active):
        got = self.measure(width, theme, edit, active)
        where = f"at {width} px, {theme}, {'Edit' if edit else 'View'}, {active or 'Dashboard'}: {got}"
        self.assertGreaterEqual(got["btn"], 70, "the project button collapsed; " + where)
        self.assertGreaterEqual(got["text"], 30, "the project name has no room; " + where)
        self.assertTrue(got["trunc"], "the long name is not cut with an ellipsis; " + where)
        self.assertGreaterEqual(got["gap"], 8, "the project button touches the tab row; " + where)
        self.assertLessEqual(got["page"], 0, "the page scrolls sideways; " + where)
        self.assertFalse(got["rowScrolls"], "the tab row scrolls sideways; " + where)
        # row 804: no tab has a View | Edit switch in the top bar (it is the Dashboard report bar's pill), so the bar has room and the button may be wider on every tab


for _w in (900, 915):
    for _t in ("light", "dark"):
        for _e in (False, True):
            for _a in TABS:
                _n = "test_%s_%s_%s_%s" % (_w, _t, "edit" if _e else "view", (_a or "dashboard").replace(" ", "_").lower())
                setattr(ProjectButtonFit, _n, lambda self, w=_w, t=_t, e=_e, a=_a: self.check(w, t, e, a))

if __name__ == "__main__":
    unittest.main()
