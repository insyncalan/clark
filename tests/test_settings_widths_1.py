"""Settings cards, first half alphabetically (Asking, Backups, Brands, Data, Freshness, Gantt, Logs and diagnostics), in a real browser
at 1400 and 900 px only. Run: python3 dev/run_tests.py test_settings_widths_1

What is asserted for each card at each width: the card is on the page; the page has no sideways scroll; the card does not scroll sideways
inside itself and stays inside the window; its main controls (a button, field or choice) are drawn, have a size, and sit inside the card.
Chrome is required: these tests fail, never skip, without it.
"""
import unittest

import test_settings_head
from test_publish_dialog import Base
from test_server import chrome

WIDTHS = (1400, 900)
# (name, the id of the card or of its heading, how many controls are the least a person should see)
CARDS = [("AI", "ai-h", 0), ("Asking", "ask-settings-h", 1), ("Backups", "safety-h", 1), ("Brands", "brands-h", 1),
         ("Data", "data-card-h", 2), ("Freshness", "review-days-h", 1), ("Gantt", "gantt-setting-h", 3), ("Logs and diagnostics", "diagnostics-h", 4)]
LOOK = """((id) => {
  const e = document.getElementById(id);
  if (!e) return null;
  const card = e.closest('section');
  if (!card) return {noSection: true};
  const r = card.getBoundingClientRect();
  const seen = [...card.querySelectorAll('button, input:not([type=hidden]), select, textarea, a[href]')].filter(c => {
    const b = c.getBoundingClientRect(), s = getComputedStyle(c);
    return b.width > 0 && b.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  });
  return {page: document.documentElement.scrollWidth - window.innerWidth, inner: card.scrollWidth - card.clientWidth, left: r.left, right: r.right - window.innerWidth,
          wide: r.width, controls: seen.length, outside: seen.filter(c => c.getBoundingClientRect().right > r.right + 1 || c.getBoundingClientRect().left < r.left - 1).map(c => c.id || c.textContent.trim().slice(0, 20))};
})(%r)"""


class SettingsWidthsOne(Base):
    def open_settings(self, p, w):
        test_settings_head.Head.open_settings(self, p, w)      # the module is imported, not the class, so its own tests do not run again

    def test_C_each_card_fits_at_1400_and_900_with_its_controls_drawn(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, w)
                for name, ident, least in CARDS:
                    with self.subTest(card=name):
                        look = p.js(LOOK % ident)
                        self.assertIsNotNone(look, f"{name}: the card is on the Settings page at {w}")
                        self.assertNotIn("noSection", look, f"{name}: the id is inside a section (a card), not a bare heading at {w}")
                        self.assertLessEqual(look["page"], 0, f"{name}: the page does not scroll sideways at {w}")
                        self.assertLessEqual(look["inner"], 0, f"{name}: the card does not scroll sideways inside itself at {w}")
                        self.assertGreaterEqual(look["left"], 0, f"{name}: the card starts inside the window at {w}")
                        self.assertLessEqual(look["right"], 0, f"{name}: the card ends inside the window at {w}")
                        self.assertGreaterEqual(look["controls"], least, f"{name}: its controls are drawn at {w}")
                        self.assertEqual(look["outside"], [], f"{name}: every control is inside the card at {w}")


if __name__ == "__main__":
    unittest.main()
