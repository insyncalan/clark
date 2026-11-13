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


    def test_the_cards_stack_in_one_column_at_900_with_dividers_between_and_sit_in_a_row_at_1400(self):
        """The stacked layout from 1180 px down (PR 1352): one card per row, a dashed line under each but the last, no side line, no
        connector after a card. Mutants: the single column, the side line, the last card's line, the connector."""
        import json
        probe = """JSON.stringify([...document.querySelectorAll('#help .hp-steps li')].map(l => { const c = getComputedStyle(l), a = getComputedStyle(l, '::after'), r = l.getBoundingClientRect();
          return { top: Math.round(r.top), left: Math.round(r.left), right: parseFloat(c.borderRightWidth), bottom: parseFloat(c.borderBottomWidth), bstyle: c.borderBottomStyle, after: a.display }; }))"""
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.until("innerWidth==%d" % w, "resize")
                p.js("window.clarkPage.help.open('start')")
                p.until("!!document.querySelector('#help .hp-steps li')", "the loop")
                cards = json.loads(p.js(probe))
                self.assertEqual(len(cards), 5)
                if w == 900:
                    self.assertEqual(len({c["left"] for c in cards}), 1, "one column: %s" % cards)
                    self.assertEqual(sorted(c["top"] for c in cards), [c["top"] for c in cards], "in order, down the page")
                    self.assertEqual(len({c["top"] for c in cards}), 5, "one card to a row")
                    for c in cards:
                        self.assertEqual(c["right"], 0, "no side line when stacked: %s" % c)
                    for c in cards[:-1]:
                        self.assertEqual((c["bstyle"], c["bottom"] > 0), ("dashed", True), "a dashed line under a card: %s" % c)
                        self.assertEqual(c["after"], "none", "no connector when stacked: %s" % c)
                    self.assertEqual(cards[-1]["bottom"], 0, "no line under the last card")
                else:
                    self.assertEqual(len({c["top"] for c in cards}), 1, "five in a row at 1400: %s" % cards)

if __name__ == "__main__":
    unittest.main()
