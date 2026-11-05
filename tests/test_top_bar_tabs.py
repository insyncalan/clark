"""#681, row 757: the top bar at 1400, 901, 900 and 800 px, light and dark, on the Dashboard, Use cases and Settings, in View and Edit, with a long
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

WIDTHS = (1400, 901, 900, 800)

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
                p.js("(function(){ var s = document.querySelector('.top .projbtn > span') || document.querySelector('.top .proj'); "
                     "s.textContent = 'Customer onboarding programme, phase two, northern region'; })()")
            if active:
                p.js(f"[...document.querySelectorAll('.top .tab')].filter(t => t.textContent.trim() === '{active}')[0].click()")
                p.until(f"[...document.querySelectorAll('.top .tab')].some(t => t.textContent.trim() === '{active}' && t.getAttribute('aria-selected') === 'true')", f"{active} is the open tab")
            p.js("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
            return p.js(MEASURE)

    def check(self, width, theme, long_name=False, edit=False, active=None):
        got = self.measure(width, theme, long_name, edit, active)
        where = f"at {width} px, {theme}{', long name' if long_name else ''}{', Edit' if edit else ''}{', ' + active if active else ', Dashboard'}"
        self.assertGreaterEqual(len(got["tabs"]), 3, where)
        scrolls = got["row"][2] > got["row"][3] + 1
        for t in got["tabs"]:
            self.assertEqual(t["lines"], 1, f"{where}: the {t['name']!r} tab is on {t['lines']} lines")
            self.assertFalse(t["over"], f"{where}: the {t['name']!r} tab is wider than its box")
            if t["open"] or not scrolls:       # the open tab is whole inside the tab row's box; with no scroll every tab is
                self.assertGreaterEqual(t["left"], got["row"][0] - 0.5, f"{where}: {t['name']!r} starts left of the tab row")
                self.assertLessEqual(t["right"], got["row"][1] + 0.5, f"{where}: {t['name']!r} is cut off by the tab row's right edge")
        self.assertEqual(sum(1 for t in got["tabs"] if t["open"]), 1, where)
        if scrolls:
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


for _w in WIDTHS:
    for _t in ("light", "dark"):
        setattr(TopBarTabs, f"test_at_{_w}_{_t}", lambda self, w=_w, t=_t: self.check(w, t))
        setattr(TopBarTabs, f"test_at_{_w}_{_t}_long_name_in_edit", lambda self, w=_w, t=_t: self.check(w, t, True, True))
        setattr(TopBarTabs, f"test_settings_at_{_w}_{_t}", lambda self, w=_w, t=_t: self.check(w, t, False, False, "Settings"))
        setattr(TopBarTabs, f"test_settings_at_{_w}_{_t}_long_name_in_edit", lambda self, w=_w, t=_t: self.check(w, t, True, True, "Settings"))
        setattr(TopBarTabs, f"test_settings_at_{_w}_{_t}_long_name_in_view", lambda self, w=_w, t=_t: self.check(w, t, True, False, "Settings"))
        setattr(TopBarTabs, f"test_use_cases_at_{_w}_{_t}_long_name_in_view", lambda self, w=_w, t=_t: self.check(w, t, True, False, "Use cases"))

if __name__ == "__main__":
    unittest.main()
