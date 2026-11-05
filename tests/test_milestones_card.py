"""Row 835: on the Milestones page the timeline (or calendar) and the list sit in one card, as in the prototype.

Run: python3 dev/run_tests.py test_milestones_card
Headless Chrome at 1400 and 900 px, light and dark, View and Edit. The card is a bordered surface with a radius and the
shared shadow, padded by the space tokens; the switch, the viewer and the list are inside it with room to spare; the
Dashboard's block (a section place) stays flat. The 13 px floor and the earlier switch pins are kept by the neighbours.
"""
import json
import re
import shutil
import time

from _paths import SRC

from test_milestones_parity import Switcher
from test_server import chrome, wait

MEASURE = """(() => {
  const m = document.querySelector('.msv[data-place=page]');
  if (!m) return null;
  const c = getComputedStyle(m), r = m.getBoundingClientRect();
  const inside = (sel) => { const e = m.querySelector(sel); if (!e) return null; const b = e.getBoundingClientRect(); return {l: b.left - r.left, r: r.right - b.right, t: b.top - r.top, b: r.bottom - b.bottom}; };
  const bar = document.querySelector('.wbar'), w = bar && bar.getBoundingClientRect();
  return {place: m.dataset.place, bg: c.backgroundColor, border: c.borderTopWidth + ' ' + c.borderTopStyle, borderColour: c.borderTopColor,
          radius: parseFloat(c.borderTopLeftRadius), shadow: c.boxShadow, padT: parseFloat(c.paddingTop), padL: parseFloat(c.paddingLeft),
          sw: inside('.msv-sw'), wrap: inside('.mv-wrap'), list: inside('.msl'), wbarAbove: w ? w.bottom <= r.top + 0.5 : null,
          noScroll: document.documentElement.scrollWidth <= window.innerWidth,
          page: getComputedStyle(document.documentElement.querySelector('main, body')).backgroundColor};
})()"""


class MilestonesCard(Switcher):
    # the switcher's own tests live in test_milestones_parity; only the helpers are borrowed here
    test_each_switch_shows_its_icon_and_its_word_and_keeps_its_name = None
    test_the_choice_is_still_remembered_for_each_place_and_the_keys_work = None
    test_a_published_file_shows_the_same_two_switches_and_remembers_nothing = None
    test_every_new_string_is_plain_words = None

    def test_the_timeline_and_the_list_are_in_one_card(self):
        for width in (1400, 900):
            for mode in ("view", "edit"):
                for theme in ("light", "dark"):
                    with self.subTest(width=width, mode=mode, theme=theme), chrome() as cdp:
                        sid = self.visit(cdp, width, "#milestones&p=TUL", theme=theme)
                        if mode == "edit":
                            cdp.js("document.querySelector('[data-mode=edit]').click()", sid)
                            self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-mode=edit]').getAttribute('aria-pressed') === 'true'", sid)), "Edit is on")
                        time.sleep(0.4)
                        s = cdp.js(MEASURE, sid)
                        self.assertIsNotNone(s, "the page block drew")
                        self.assertEqual(s["border"], "1px solid", "a bordered card")
                        self.assertNotEqual(s["bg"], "rgba(0, 0, 0, 0)", "a filled card")
                        self.assertNotEqual(s["shadow"], "none", "the shared shadow")
                        self.assertGreaterEqual(s["radius"], 12, "the shared large radius")
                        self.assertGreaterEqual(s["padT"], 16, "padded by the space tokens, top")
                        self.assertGreaterEqual(s["padL"], 20, "padded by the space tokens, sides")
                        for part in ("sw", "wrap", "list"):
                            p = s[part]
                            self.assertIsNotNone(p, part)
                            self.assertGreaterEqual(p["l"], 19.5, f"{part} clear of the left edge")
                            self.assertGreaterEqual(p["r"], 19.5, f"{part} clear of the right edge")
                            self.assertGreaterEqual(p["t"], 15.5, f"{part} clear of the top edge")
                            self.assertGreaterEqual(p["b"], 0, f"{part} inside the card")
                        self.assertTrue(s["wbarAbove"], "the header rows stay above the card")
                        self.assertTrue(s["noScroll"], "no page-wide scroll")

    def test_only_the_milestones_page_gets_the_card(self):
        css = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
        rule = re.search(r'^\.msv\[data-place="page"\] \{([^}]*)\}', css, re.M)
        self.assertIsNotNone(rule, "the card rule is keyed to the page place")
        self.assertNotRegex(re.search(r"^\.msv \{([^}]*)\}", css, re.M).group(1), r"border|box-shadow|background", "the bare block stays flat")
        self.assertNotRegex(rule.group(1), r"#[0-9a-fA-F]{3}|rgba?\(|hsl", "tokens only")
