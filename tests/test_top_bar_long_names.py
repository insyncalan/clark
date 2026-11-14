"""A very long project name and a very long person name in the top bar at 900 and 1400 px: the bar's items do not overlap or run past the
window, no control is hidden, the page does not scroll sideways, and the profile menu (which carries the person's name) stays inside the window.
Chrome is required: these tests fail, never skip, without it.

Run: python3 dev/run_tests.py test_top_bar_long_names
"""
import unittest

import json

from test_publish_dialog import Base
from test_server import chrome

LONG_PROJECT = "Example Client onboarding programme, phase two, northern region, including the extended regional rollout and wind-down"
LONG_PERSON = "Example Person With A Very Long Hyphenated-Family-Name"
LONG_EMAIL = "example.person.with.a.very.long.address.that.keeps.going@a-very-long-example-company-name.example.org"

BAR = """(function(){
  var W = document.documentElement.clientWidth, bad = [];
  var items = [...document.querySelectorAll('header.top > *')].filter(e => e.getClientRects().length);
  var r = items.map(e => [e.className || e.id, e.getBoundingClientRect()]);
  for (var i = 0; i < r.length; i++) {
    if (r[i][1].right > W + 0.5 || r[i][1].left < -0.5) bad.push('past ' + r[i][0]);
    for (var j = i + 1; j < r.length; j++) if (r[i][1].width && r[j][1].width && r[i][1].left < r[j][1].right - 0.5 && r[j][1].left < r[i][1].right - 0.5 && r[i][1].top < r[j][1].bottom - 0.5 && r[j][1].top < r[i][1].bottom - 0.5) bad.push(r[i][0] + ' over ' + r[j][0]);
  }
  var must = ['#profile-btn', '.top .hdr-project', '.top .tabs'].filter(s => { var e = document.querySelector(s); if (!e) return true; var b = e.getBoundingClientRect(); return !(b.width > 0 && b.height > 0 && b.right <= W + 0.5); });
  var tabs = [...document.querySelectorAll('.top .tab')].filter(t => { var b = t.getBoundingClientRect(), n = document.querySelector('.top .tabs').getBoundingClientRect(); return b.left < n.left - 1 || b.right > n.right + 1; }).length;
  return {bad: bad, missing: must, page: document.documentElement.scrollWidth - W, tabsOutOfRow: tabs};
})()"""

MENU = """(function(){
  var W = document.documentElement.clientWidth, m = document.querySelector('#profile-menu'), b = m.getBoundingClientRect(), out = [];
  if (b.left < -0.5 || b.right > W + 0.5) out.push('menu past the window ' + [b.left, b.right]);
  [...m.querySelectorAll('*')].forEach(e => { var c = e.getBoundingClientRect(); if (c.width && (c.right > b.right + 0.5 || c.left < b.left - 0.5)) out.push('overflow ' + (e.className || e.tagName)); });
  return {out: out, page: document.documentElement.scrollWidth - W};
})()"""


class LongNames(Base):
    def prepare(self, p):
        p.until("!!document.querySelector('.top .hdr-project > span')", "the bar shows")
        p.js(f"document.querySelector('.top .hdr-project > span').textContent = {LONG_PROJECT!r}")
        p.js("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")

    def check(self, width, edit):
        f = self.rig.data_dir / "settings.json"
        old = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        f.write_text(json.dumps({**old, "profile_name": LONG_PERSON, "profile_email": LONG_EMAIL}), encoding="utf-8")
        with chrome() as cdp:
            p = self.page(cdp)
            p.width(width)
            self.prepare(p)
            if edit:
                p.js("(document.querySelector('.top [data-mode=edit]') || {click(){}}).click()")
            where = f"at {width} px, {'Edit' if edit else 'View'}"
            got = p.js(BAR)
            self.assertEqual(got["bad"], [], "the bar's items overlap or run past the window " + where)
            self.assertEqual(got["missing"], [], "a control is hidden " + where)
            self.assertLessEqual(got["page"], 0, "the page scrolls sideways " + where)
            self.assertEqual(got["tabsOutOfRow"], 0, "a tab is outside the tab row " + where)
            p.until("(() => { if (document.querySelector('#profile-menu')) return true; if (Date.now() - (window.__t || 0) > 1000) { window.__t = Date.now(); document.querySelector('#profile-btn').click(); } return !!document.querySelector('#profile-menu'); })()", "the profile menu opened")
            p.until("document.querySelector('#profile-menu').textContent.includes('Example Person')", "the long name is in the menu")
            self.assertTrue(p.js("document.querySelector('#profile-menu').textContent.includes('Example Person')"), "the long name is shown in the menu " + where)
            m = p.js(MENU)
            self.assertEqual(m["out"], [], "the profile menu does not fit " + where)
            self.assertLessEqual(m["page"], 0, "the menu makes the page scroll sideways " + where)


for _w in (900, 1400):
    for _e in (False, True):
        setattr(LongNames, "test_%d_%s" % (_w, "edit" if _e else "view"), lambda self, w=_w, e=_e: self.check(w, e))


if __name__ == "__main__":
    unittest.main()
