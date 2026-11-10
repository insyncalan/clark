"""Issue 1057: the sneak peek (the words box) stays anchored to the bottom of the work item peek while the peek scrolls.

Run: python3 dev/run_tests.py test_peek_sneak_anchor_1057

Measured in a real browser in Edit with a window short enough that the peek scrolls: the words box sits at the foot of the peek, and its
bottom edge does not move when the peek is scrolled to the top, the middle or the end.
"""
import unittest

import test_peek as tp  # noqa: E402
from test_peek_card import CardBrowser  # noqa: E402
from test_server import chrome  # noqa: E402

FIND = """const p = document.querySelector('#peek');
  const sc = [p, ...p.querySelectorAll('*')].filter((e) => e.scrollHeight > e.clientHeight + 4 && /(auto|scroll)/.test(getComputedStyle(e).overflowY))[0];"""
READ = """(() => { %s const w = document.querySelector('[data-sneak]'); const r = w.getBoundingClientRect(); const pr = p.getBoundingClientRect();
  return { wb: r.bottom, pb: pr.bottom, max: sc ? sc.scrollHeight - sc.clientHeight : 0 }; })()""" % FIND
SCROLL = """(() => { %s sc.scrollTop = %%s * (sc.scrollHeight - sc.clientHeight); return sc.scrollTop; })()""" % FIND


class SneakAnchor(unittest.TestCase):
    setUpClass = tp.Browser.__dict__["setUpClass"]
    tearDownClass = tp.Browser.__dict__["tearDownClass"]
    load_page = tp.Browser.load_page
    edit_mode = tp.Browser.edit_mode
    ids_on_page = tp.Browser.ids_on_page
    open_words = tp.Browser.open_words
    show_item = CardBrowser.show_item

    def test_the_words_box_stays_at_the_bottom_of_the_peek_while_it_scrolls(self):
        for width in (1400, 900):
            with chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                item = self.ids_on_page(cdp, sid)[0]
                self.edit_mode(cdp, sid)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 520, "deviceScaleFactor": 1, "mobile": False}, sid)
                self.show_item(cdp, sid, item)
                self.open_words(cdp, sid)
                start = cdp.js(READ, sid)
                self.assertGreater(start["max"], 40, f"{width}: the peek scrolls in this window")
                self.assertLessEqual(abs(start["pb"] - start["wb"]), 40, f"{width}: the box starts at the foot of the peek")
                for frac in (0.5, 1, 0):
                    cdp.js(SCROLL % frac, sid)
                    now = cdp.js(READ, sid)
                    self.assertLess(abs(now["wb"] - start["wb"]), 2, f"{width}: at {frac} of the scroll the box stays at the bottom ({now['wb']} vs {start['wb']})")


if __name__ == "__main__":
    unittest.main()
