"""#681, row 757: the top bar at 1400, 901, 900 and 800 px, light and dark, on the Dashboard and on Settings, in View and Edit, with a long project name: every tab label is whole on one line, the last tab (Settings) is inside the bar and its own row, nothing is clipped or
overlapped, and the page does not scroll sideways. Chrome is required: these tests fail, never skip, without it.

Run: python3 dev/run_tests.py test_top_bar_tabs
"""
import sqlite3
import unittest

from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

WIDTHS = (1400, 901, 900, 800)

# For each tab: its box, the box of its text, and the line height. Then the bar's other items, and the page's sideways scroll.
MEASURE = """(function(){
  var bar = document.querySelector('header.top').getBoundingClientRect(), out = {tabs: [], items: [], bar: [bar.left, bar.right, bar.top, bar.bottom]};
  var row = document.querySelector('.top .tabs'), rb = row.getBoundingClientRect();
  out.row = [rb.left, rb.right, row.scrollWidth, row.clientWidth];
  document.querySelectorAll('.top .tab').forEach(function(t){
    var r = t.getBoundingClientRect(), s = document.createRange(); s.selectNodeContents(t);
    var lines = new Set(Array.from(s.getClientRects()).filter(function(q){ return q.width > 0; }).map(function(q){ return Math.round(q.top); }));
    out.tabs.push({name: t.textContent.trim(), left: r.left, right: r.right, top: r.top, bottom: r.bottom, lines: lines.size, over: t.scrollWidth > t.clientWidth + 1});
  });
  Array.from(document.querySelector('header.top').children).forEach(function(c){
    var r = c.getBoundingClientRect(); if (r.width > 0) out.items.push({cls: c.className, left: r.left, right: r.right, top: r.top, bottom: r.bottom});
  });
  out.scroll = [document.documentElement.scrollWidth, document.documentElement.clientWidth];
  return out;
})()"""


class TopBarTabs(Base):
    def measure(self, width, theme, long_name=False, edit=False, settings=False):
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
            if settings:
                p.js("[...document.querySelectorAll('.top .tab')].filter(t => t.textContent.trim() === 'Settings')[0].click()")
                p.until("[...document.querySelectorAll('.top .tab')].some(t => t.textContent.trim() === 'Settings' && t.getAttribute('aria-selected') === 'true')", "Settings is the open tab")
            return p.js(MEASURE)

    def check(self, width, theme, long_name=False, edit=False, settings=False):
        got = self.measure(width, theme, long_name, edit, settings)
        where = f"at {width} px, {theme}{', long name' if long_name else ''}{', Edit' if edit else ''}{', Settings' if settings else ''}"
        self.assertGreaterEqual(len(got["tabs"]), 3, where)
        for t in got["tabs"]:
            self.assertEqual(t["lines"], 1, f"{where}: the {t['name']!r} tab is on {t['lines']} lines")
            self.assertFalse(t["over"], f"{where}: the {t['name']!r} tab is wider than its box")
            self.assertGreaterEqual(t["left"], got["bar"][0], f"{where}: {t['name']!r} starts left of the bar")
            self.assertLessEqual(t["right"], got["bar"][1] + 0.5, f"{where}: {t['name']!r} runs past the bar")
            self.assertLessEqual(t["right"], got["row"][1] + 0.5, f"{where}: {t['name']!r} is cut off by the tab row's own edge")
            self.assertLessEqual(t["bottom"], got["bar"][3] + 0.5, f"{where}: {t['name']!r} runs below the bar")
        self.assertLessEqual(got["row"][2], got["row"][3], f"{where}: the tab row scrolls inside itself {got['row']}")
        boxes = [dict(i, label=i["cls"] or "item") for i in got["items"] if i["cls"] != "tabs"] + [dict(t, label=t["name"]) for t in got["tabs"]]
        for k, a in enumerate(boxes):
            for b in boxes[k + 1:]:
                apart = a["right"] <= b["left"] + 0.5 or b["right"] <= a["left"] + 0.5 or a["bottom"] <= b["top"] + 0.5 or b["bottom"] <= a["top"] + 0.5
                self.assertTrue(apart, f"{where}: {a['label']!r} overlaps {b['label']!r}")
        self.assertLessEqual(max(i["right"] for i in got["items"]), got["bar"][1] + 0.5, f"{where}: an item is clipped by the window")
        self.assertLessEqual(got["scroll"][0], got["scroll"][1], f"{where}: the page scrolls sideways {got['scroll']}")


for _w in WIDTHS:
    for _t in ("light", "dark"):
        setattr(TopBarTabs, f"test_at_{_w}_{_t}", lambda self, w=_w, t=_t: self.check(w, t))
        setattr(TopBarTabs, f"test_at_{_w}_{_t}_long_name_in_edit", lambda self, w=_w, t=_t: self.check(w, t, True, True))
        setattr(TopBarTabs, f"test_settings_at_{_w}_{_t}", lambda self, w=_w, t=_t: self.check(w, t, False, False, True))
        setattr(TopBarTabs, f"test_settings_at_{_w}_{_t}_long_name_in_edit", lambda self, w=_w, t=_t: self.check(w, t, True, True, True))
        setattr(TopBarTabs, f"test_settings_at_{_w}_{_t}_long_name_in_view", lambda self, w=_w, t=_t: self.check(w, t, True, False, True))

if __name__ == "__main__":
    unittest.main()
