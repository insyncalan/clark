"""The project menu in the top bar. Each project is its name on one line and "N open items" on its own line under it (the name
is cut with an ellipsis when too long), never run together on one line; the menu is no wider than the room, with no sideways scroll.
Measured at 1400 and 900, light and dark, View and Edit. Invented names.

Run: python3 dev/run_tests.py test_project_menu_layout
"""
import unittest

from test_publish_dialog import Base, WIDTHS
from test_server import chrome

PROJECTS = [{"code": "PUB", "name": "Mossgrove Customer Portal", "open": 9},
            {"code": "ABC", "name": "Harbourside Rollout Programme West", "open": 1},
            {"code": "XYZ", "name": "Harbourside Rollout Programme West Extension Phase Two Delivery", "open": 12}]
MEASURE = """(function(){
  var m = document.querySelector('#project-menu'), mr = m.getBoundingClientRect();
  return {menu: [mr.left, mr.right, mr.width], bar: document.documentElement.scrollWidth - window.innerWidth,
    rows: [].map.call(m.querySelectorAll('[role=menuitemradio]'), function(r){
      var b = r.querySelector('b').getBoundingClientRect(), s = r.querySelector('small').getBoundingClientRect(), rr = r.getBoundingClientRect(),
          ck = r.querySelector('.ck').getBoundingClientRect(), sp = r.querySelector('b').parentNode.getBoundingClientRect();
      return {h: rr.height, nameBottom: b.bottom, countTop: s.top, nameRight: b.right, countRight: s.right, rowRight: rr.right, nameLines: r.querySelector('b').getClientRects().length,
              countLines: r.querySelector('small').getClientRects().length, ckRight: ck.right, spLeft: sp.left, text: r.querySelector('small').textContent};
    })};
})()"""


class ProjectMenuLayout(Base):
    def test_C_the_count_sits_under_the_name_in_both_themes_and_modes_at_both_widths(self):
        self.rig.httpd.projects = lambda archived=False: PROJECTS
        with chrome() as cdp:
            p = self.page(cdp)
            p.until("document.querySelector('#project-name').tagName === 'BUTTON'", "the name is a menu button")
            for w in WIDTHS:
                p.width(w)
                for mode in ("view", "edit"):
                    p.js("document.querySelector('.top [data-mode=%s]').click()" % mode)
                    for theme in ("light", "dark"):
                        p.js("document.documentElement.setAttribute('data-theme', '%s')" % theme)
                        where = "%d %s %s" % (w, mode, theme)
                        p.js("document.querySelector('#project-name').click()")
                        p.until("!!document.querySelector('#project-menu')", "the menu opened " + where)
                        m = p.js(MEASURE)
                        self.assertEqual(len(m["rows"]), 3, where)
                        for r in m["rows"]:
                            self.assertGreaterEqual(r["countTop"], r["nameBottom"] - 0.5, "%s: the count is below the name, not beside it" % where)
                            self.assertEqual((r["nameLines"], r["countLines"]), (1, 1), "%s: neither wraps" % where)
                            self.assertLessEqual(r["h"], 60, "%s: the row is two lines, not three" % where)
                            self.assertLessEqual(r["nameRight"], r["rowRight"] + 0.5, where)
                            self.assertLessEqual(r["countRight"], r["rowRight"] + 0.5, where)
                            self.assertLessEqual(r["ckRight"], r["spLeft"] + 0.5, "%s: the tick does not overlap the words" % where)
                        self.assertLessEqual(m["bar"], 0, "%s: no sideways overflow" % where)
                        self.assertLessEqual(m["menu"][1], w + 0.5, where)
                        self.assertLessEqual(m["menu"][2], 361, where)
                        self.assertGreaterEqual(m["menu"][2], 200, where)
                        p.key("Escape", "Escape", 27)
                        p.until("!document.querySelector('#project-menu')", "closed " + where)


if __name__ == "__main__":
    unittest.main()
