"""#936, Quote and Link preview borders: in Edit's page neither draws a coloured side stripe (the quote is a quiet panel, the link
preview a plain frame); the published file is unchanged (it carries no Edit part, and the prototype draws neither).
The Callout has no side stripe from #1272 (option B: a tinted box, an icon and a word); it is a 1 px edge like the others.

Run: python3 dev/run_tests.py test_card_borders_936_notes
Needs Chrome. Fictional data only. Laptop widths 1400 and 900 px, light and dark.
"""
import json
import unittest

from _demo import USER
from _publish import PublishedFile
import test_glance_page as glance
from test_server import chrome

from clark import store as store_module

READ = """(() => {
  const w = (s, side) => { const e = document.querySelector(s); return e ? getComputedStyle(e)['border' + side + 'Width'] : null; };
  const c = (s) => { const e = document.querySelector(s); return e ? getComputedStyle(e).borderLeftColor : null; };
  return {quote: w('.tpl-quote', 'Left'), lc: w('.tpl-lc', 'Left'), lcTop: w('.tpl-lc', 'Top'), callout: w('.tpl-callout', 'Left'),
          quoteColor: c('.tpl-quote'), lcColor: c('.tpl-lc'), calloutColor: c('.tpl-callout'),
          quoteBg: getComputedStyle(document.querySelector('.tpl-quote')).backgroundColor, active: document.getAnimations().length};
})()"""


class Notes(PublishedFile, glance.Setup):
    def plant_notes(self):
        with self.store.step("dashboard", USER) as st:
            for n, (kind, body) in enumerate((
                    ("quote", {"v": 1, "quote": "Fictional thanks.", "by": "Sam Example", "role": "Fictional sponsor"}),
                    ("callout", {"v": 1, "tone": "decision", "title": "Fictional decision", "paras": ["Fictional words."]}),
                    ("linkcard", {"v": 1, "href": "https://example.org/pilot", "title": "Pilot", "site": "Example", "text": ["Updated weekly."]}))):
                st.create("report_sections", {"project": "ABC", "type": kind, "title": "Fictional %s" % kind, "sort_order": 990 + n,
                                              "body": store_module.check_section_body(kind, json.dumps(body))})

    def settled(self, p):
        p.until("document.getAnimations().length === 0 && !!document.querySelector('.tpl-quote') && !!document.querySelector('.tpl-lc')",
                "the notes drew and nothing is moving")
        return p.js(READ)

    def test_edit_pages_notes_have_no_side_stripe(self):
        self.plant_notes()
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width, dark)
                    got = self.settled(p)
                    self.assertEqual(got["quote"], "0px", "the quote has no side stripe")
                    self.assertNotEqual(got["quoteBg"], "rgba(0, 0, 0, 0)", "the quote is a quiet panel instead")
                    self.assertEqual(got["lc"], got["lcTop"], "the link preview's left edge is as thin as its top")
                    self.assertEqual(got["lc"], "1px")
                    self.assertEqual(got["callout"], "1px", "the callout has an even edge, no stripe (#1272)")

    def test_the_published_file_shows_an_older_callouts_tone_word(self):
        self.plant_notes()                                  # its callout is an older one: a tone and no category, colour or icon
        path = self.publish()
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.draw(cdp, path, width, False)
                self.settled(p)
                self.assertEqual(p.js("document.querySelector('.tpl-callout-tone').textContent"), "Decision needed")

    def test_the_published_file_draws_the_quiet_marker_and_has_an_even_callout_edge(self):
        self.plant_notes()
        path = self.publish()
        for width, dark in ((1400, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                got = self.settled(self.draw(cdp, path, width, dark))
                self.assertEqual((got["quote"], got["lc"], got["callout"]), ("0px", "1px", "1px"), "no decorative stripe, the callout has an even edge")
                self.assertNotEqual(got["quoteBg"], "rgba(0, 0, 0, 0)", "the quote is a quiet panel")
                self.assertEqual(got["lc"], got["lcTop"], "the link preview's left edge is as thin as its top")


if __name__ == "__main__":
    unittest.main()
