"""Help > Start here, "The loop" (merged Help review, PR 1346): the five step cards keep their words whole at 1400 and 900.
At 900 the cards were 108 px wide: labels such as "2 · UPDATE" wrapped and headings split over three or four lines.
Measured in a real browser, light and dark; the text of a card never reaches past the card, a step label stays on one line,
a heading takes at most two lines. No wording is under test."""
import unittest

from test_report_editor import Base
from test_server import chrome

MEASURE = """JSON.stringify([...document.querySelectorAll('#help .hp-steps li')].map(l => {
  const r = l.getBoundingClientRect(), lh = e => parseFloat(getComputedStyle(e).lineHeight) || e.getBoundingClientRect().height;
  const n = l.querySelector('.hp-n'), b = l.querySelector('.hp-st b');
  const past = [...l.querySelectorAll('.hp-n, .hp-st, .hp-st b, p')].filter(e => e.getBoundingClientRect().right > r.right + 0.5).length;
  return { label: Math.round(n.getBoundingClientRect().height / lh(n)), head: Math.round(b.getBoundingClientRect().height / lh(b)), past, w: Math.round(r.width) };
}))"""


class LoopCards(Base):
    def test_cards_keep_words_whole(self):
        import json
        with chrome() as cdp:
            p = self.visit(cdp)
            for scheme in ("light", "dark"):
                cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, p.sid)
                for w in (1400, 900):
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    p.until("innerWidth==%d" % w, "resize")
                    p.js("window.clarkPage.help.open('start')")
                    p.until("!!document.querySelector('#help .hp-steps li')", "the loop")
                    cards = json.loads(p.js(MEASURE))
                    self.assertEqual(len(cards), 5)
                    for c in cards:
                        where = "%s %d %s" % (scheme, w, c)
                        self.assertEqual(c["label"], 1, "step label on one line: " + where)
                        self.assertLessEqual(c["head"], 2, "heading at most two lines: " + where)
                        self.assertEqual(c["past"], 0, "text inside its card: " + where)


if __name__ == "__main__":
    unittest.main()
