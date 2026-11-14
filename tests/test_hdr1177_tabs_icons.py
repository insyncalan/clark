"""Item 1177: the one slim sticky header holds the four tabs, the search button, the ask clark button and the profile circle, all inside its
box at 1400 px. Chrome is required: these tests fail, never skip, without it.

Run: python3 dev/run_tests.py test_hdr1177_tabs_icons
"""
import sqlite3

from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

BOX = """(function(sel){
  var h = document.querySelector('.top'), e = h && h.querySelector(sel);
  if (!h || !e) return null;
  var a = h.getBoundingClientRect(), b = e.getBoundingClientRect();
  return {w: b.width, h: b.height, inside: b.left >= a.left - 0.5 && b.right <= a.right + 0.5 && b.top >= a.top - 0.5 && b.bottom <= a.bottom + 0.5,
          shown: getComputedStyle(e).display !== 'none' && getComputedStyle(e).visibility !== 'hidden'};
})"""


class HeaderTabsAndIcons(Base):
    def open(self, cdp):
        p = self.visit(cdp)
        size(cdp, p, 1400, 800)
        p.until("!!document.querySelector('.top #ask-btn') && !!document.querySelector('.top #profile-btn')", "the header shows its buttons")
        p.js("window.scrollTo(0, 0)")
        return p

    def test_the_header_is_85px_tall_and_sticky_at_1400(self):      # item 1177: the box the other parts sit in
        with chrome() as cdp:
            with sqlite3.connect(str(self.store.path)) as con:
                con.execute("UPDATE app_settings SET ask_enabled = 1 WHERE id = 1")
            p = self.open(cdp)
            got = p.js("(function(){var h=document.querySelector('.top'), s=getComputedStyle(h);"
                       "return [Math.round(h.getBoundingClientRect().height), s.position, s.top, s.zIndex];})()")
            self.assertEqual(got, [85, "sticky", "0px", "30"], f"the header should be 85 px, sticky, top 0, z-index 30; got {got}")

    def test_the_four_tabs_are_inside_the_header_in_order_at_1400(self):
        with chrome() as cdp:
            with sqlite3.connect(str(self.store.path)) as con:
                con.execute("UPDATE app_settings SET ask_enabled = 1 WHERE id = 1")
            p = self.open(cdp)
            names = p.js("[...document.querySelectorAll('.top .tab')].map(t => t.textContent.trim())")
            self.assertEqual(names, ["Dashboard", "Work items", "Milestones", "Use cases"], f"the header tabs should be the four, in order; got {names}")
            for view in ("dashboard", "work", "milestones", "usecases"):
                got = p.js(f"{BOX}('.tab[data-view={view}]')")
                self.assertTrue(got and got["inside"] and got["shown"] and got["h"] > 0, f"the {view} tab should be drawn inside the header; got {got}")

    def test_search_ask_and_profile_are_inside_the_header_at_1400(self):
        with chrome() as cdp:
            with sqlite3.connect(str(self.store.path)) as con:
                con.execute("UPDATE app_settings SET ask_enabled = 1 WHERE id = 1")
            p = self.open(cdp)
            for name, sel in (("search", "#pal-btn"), ("ask clark", "#ask-btn"), ("profile", "#profile-btn")):
                got = p.js(f"{BOX}('{sel}')")
                self.assertTrue(got and got["inside"] and got["shown"] and got["w"] > 0 and got["h"] > 0,
                                f"the {name} button should be drawn inside the header; got {got}")

    def test_the_icons_sit_on_the_right_of_the_tabs_in_the_order_search_ask_profile_at_1400(self):
        with chrome() as cdp:
            with sqlite3.connect(str(self.store.path)) as con:
                con.execute("UPDATE app_settings SET ask_enabled = 1 WHERE id = 1")
            p = self.open(cdp)
            xs = p.js("(function(){var r=s=>document.querySelector('.top '+s).getBoundingClientRect();"
                      "return [r('.tab[data-view=usecases]').right, r('#pal-btn').left, r('#ask-btn').left, r('#profile-btn').left];})()")
            self.assertEqual(xs, sorted(xs), f"the order left to right should be last tab, search, ask clark, profile; got {xs}")
            self.assertEqual(len(set(xs)), 4, f"no two of the four should start at the same place; got {xs}")
