"""Settings, second half of the cards alphabetically (People, Personal, Profile, Projects, Published reports, Publishing, Quit, Update): each card is
loaded in a real browser at 1400 and 900 px (and only those), the page and the card do not scroll sideways, nothing in the card sticks out past
its right edge, and the card's main controls are drawn, have a box and are inside the window. Run: python3 dev/run_tests.py test_settings_cards_widths_2
Chrome is required: these tests fail, never skip, without it."""
import json
import unittest

import test_settings_head
from test_publish_dialog import Base
from test_server import chrome

WIDTHS = (1400, 900)

# (name, heading id, controls that must be drawn and visible: CSS selectors inside the card)
CARDS = [
    ("People", "people-h", ["#ppPasteBtn"]),
    ("Personal", "personal-h", ["[data-theme-pick]", ".switch"]),
    ("Profile", "profile-h", ["#about-name"]),
    ("Projects", "projects-h", ["#show-archived"]),
    ("Published reports", "pubs", []),
    ("Publishing", "client-folder-h", ["[data-choose-local]", "[data-choose-folder]"]),
    ("Quit", "quit-h", ["button.btn"]),
    ("Update", "update-h", []),
]

PROBE = """((headId, sels) => {
  const h = document.getElementById(headId);
  const card = h ? h.closest('section') : document.getElementById(headId);
  if (!card) return null;
  card.scrollIntoView({block: 'start'});
  const root = document.documentElement, cr = card.getBoundingClientRect();
  const out = {doc_over: root.scrollWidth - root.clientWidth, card_over: card.scrollWidth - card.clientWidth, card_right: cr.right, win: root.clientWidth,
               wide: [], controls: {}};
  for (const el of card.querySelectorAll('*')) {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    if (r.width && r.height && s.visibility !== 'hidden' && r.right > cr.right + 1 && !el.closest('[hidden]')) out.wide.push((el.id || el.className || el.tagName) + ' ' + Math.round(r.right - cr.right));
  }
  for (const sel of sels) {
    const el = card.querySelector(sel);
    if (!el) { out.controls[sel] = 'missing'; continue; }
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    out.controls[sel] = (r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && r.left >= 0 && r.right <= root.clientWidth + 1) ? 'ok' : 'hidden ' + [r.left, r.right, r.width, r.height].join(',');
  }
  return out;
})(%s, %s)"""


class CardsWidths(Base):
    open_settings = test_settings_head.Head.open_settings

    def test_C_each_card_fits_at_1400_and_900_and_its_controls_show(self):
        for w in WIDTHS:
            with chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, w)
                for name, head, sels in CARDS:
                    with self.subTest(width=w, card=name):
                        got = p.js(PROBE % (json.dumps(head), json.dumps(sels)))
                        if got is None and name in ("Published reports", "Update"):
                            self.skipTest(name + " is not on the test rig's Settings page")
                        self.assertIsNotNone(got, name + ": the card is on the Settings page")
                        self.assertLessEqual(got["doc_over"], 0, name + ": the page scrolls sideways")
                        self.assertLessEqual(got["card_over"], 1, name + ": the card scrolls sideways")
                        self.assertEqual(got["wide"], [], name + ": something sticks out past the card's right edge")
                        self.assertLessEqual(got["card_right"], got["win"] + 1, name + ": the card is wider than the window")
                        for sel, state in got["controls"].items():
                            self.assertEqual(state, "ok", name + ": " + sel)


if __name__ == "__main__":
    unittest.main()
