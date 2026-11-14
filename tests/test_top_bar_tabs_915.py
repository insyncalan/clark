"""Row 757: the project switcher in the top bar (row 1064: the chevron alone, the name not drawn) does not collapse at 900 px (the file's name keeps the 915 px
window it once also checked; the tests below run at 900 px only, the narrower of the two supported widths, where the bar is tightest), on any tab, in light and dark, in View and Edit, with a long project name written as an
invented name. The button keeps a readable width with an ellipsis, stays clear of the first tab, the tab row does not scroll and the page does not scroll
sideways. Chrome is required: these tests fail, never skip, without it.

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
  var pb = document.querySelector('.top .hdr-project'), sp = pb.querySelector(':scope > span'), b = pb.getBoundingClientRect(), s = sp.getBoundingClientRect();
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
            p.until("!!document.querySelector('#profile-btn') && !!document.querySelector('.top .hdr-project > span')", "the bar shows")      # item 1177: no ask button in the header at 900
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
            p.js(f"document.querySelector('.top .hdr-project > span').textContent = {LONG!r}")
            p.js("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
            return p.js(MEASURE)

    def check(self, width, theme, edit, active):
        got = self.measure(width, theme, edit, active)
        where = f"at {width} px, {theme}, {'Edit' if edit else 'View'}, {active or 'Dashboard'}: {got}"
        # row 1064: the name is not drawn (it is read out only), so the button is the chevron alone; a long name must not widen it
        self.assertGreaterEqual(got["btn"], 20, "the project switcher collapsed; " + where)
        self.assertLessEqual(got["btn"], 48, "a long project name widened the switcher; " + where)
        self.assertLessEqual(got["text"], 2, "the project name is drawn in the bar; " + where)
        self.assertGreaterEqual(got["gap"], 8, "the project button touches the tab row; " + where)
        self.assertLessEqual(got["page"], 0, "the page scrolls sideways; " + where)
        self.assertFalse(got["rowScrolls"], "the tab row scrolls sideways; " + where)
        # row 804: no tab has a View | Edit switch in the top bar (it is the Dashboard report bar's pill), so the bar has room and the button may be wider on every tab


for _w in (900,):
    for _t in ("light", "dark"):
        for _e in (False, True):
            for _a in TABS:
                _n = "test_%s_%s_%s_%s" % (_w, _t, "edit" if _e else "view", (_a or "dashboard").replace(" ", "_").lower())
                setattr(ProjectButtonFit, _n, lambda self, w=_w, t=_t, e=_e, a=_a: self.check(w, t, e, a))

if __name__ == "__main__":
    unittest.main()
