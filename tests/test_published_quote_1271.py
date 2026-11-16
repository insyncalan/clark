"""#1271, the Quote in the published file: look B (grey panel, a 3px blue rule above, the name in small capitals with the role under it),
and the Tile and Heading switches honoured when off.

Run: python3 dev/run_tests.py -j 1 test_published_quote_1271
A real project is published with four quotes (both switches on, Tile off, Heading off, both off), the finished file is opened from file://
in headless Chrome at 1400 and 900, and each quote is read as drawn. All rows are fictional.
"""
import json
import unittest

from _demo import USER
from _publish import PublishedFile
import test_glance_page as glance
from test_server import chrome

from clark import publish
from clark import store as store_module
from test_report_editor import EMPTY_BRANDING

WORDS = "Fictional words of thanks."
CASES = {"on": {}, "no-tile": {"tile": False}, "no-heading": {"heading": False}, "neither": {"tile": False, "heading": False}}

# Run in the page: what a quote section is drawn as, by its title.
READ = r"""(() => {
  const out = {};
  document.querySelectorAll(".secs > [data-type=quote]").forEach((sec) => {
    const q = sec.querySelector(".tpl-quote"), nm = sec.querySelector(".tpl-quote-nm"), rl = sec.querySelector(".tpl-quote-rl");
    const head = sec.querySelector(".sec-head"), rule = getComputedStyle(q, "::before"), box = getComputedStyle(sec), qs = getComputedStyle(q);
    const hb = head.getBoundingClientRect();
    out[sec.dataset.id] = {
      tile: !/^rgba\(0, 0, 0, 0\)$|transparent/.test(box.backgroundColor) || box.boxShadow !== "none" || (parseFloat(box.borderTopWidth) > 0 && box.borderTopColor !== "rgba(0, 0, 0, 0)"),
      headingShown: hb.width > 4 && hb.height > 4 && getComputedStyle(head).clip === "auto",
      panel: qs.backgroundColor, ruleH: rule.height, ruleBg: rule.backgroundColor, ruleDisplay: rule.display,
      nameCaps: nm && getComputedStyle(nm).textTransform, nameText: nm && nm.textContent, roleText: rl && rl.textContent,
      roleBelow: nm && rl ? rl.getBoundingClientRect().top >= nm.getBoundingClientRect().bottom - 1 : null,
      wide: document.documentElement.scrollWidth <= window.innerWidth,
      words: q.querySelector("blockquote").textContent,
    };
  });
  return out;
})()"""


class PublishedQuote(PublishedFile, glance.Setup):
    def plant(self):
        refs = {}
        with self.store.step("dashboard", USER) as st:
            for n, (name, off) in enumerate(CASES.items()):
                body = {"v": 1, "quote": WORDS, "by": "Sam Example", "role": "Fictional sponsor", **off}
                refs[name] = st.create("report_sections", {"project": "ABC", "type": "quote", "title": f"Fictional quote {name}", "sort_order": 990 + n,
                                                           "body": store_module.check_section_body("quote", json.dumps(body))})
        return refs

    def test_the_file_carries_a_switch_only_when_it_is_off(self):
        refs = self.plant()
        got = {s["id"]: s.get("content", {}) for s in publish.build(self.store, "ABC", now="2026-10-28", branding=EMPTY_BRANDING)["published"]["sections"]}
        for name, off in CASES.items():
            self.assertEqual({k: v for k, v in got[refs[name]].items() if k in ("tile", "heading")}, off, name)

    def test_the_file_draws_look_b_and_honours_the_switches_at_both_widths(self):
        refs = self.plant()
        path = self.publish()
        for width in (1400, 900):
            for density in ("comfortable", "compact"):
              with self.subTest(width=width, density=density), chrome() as cdp:
                p = self.draw(cdp, path, width)
                p.js("document.documentElement.dataset.density = %s" % json.dumps(density))
                drawn = p.js(READ)
                for name, off in CASES.items():
                    with self.subTest(case=name):
                        d = drawn[refs[name]]
                        self.assertEqual(d["words"], WORDS)
                        self.assertEqual((d["nameText"], d["roleText"], d["nameCaps"]), ("Sam Example", "Fictional sponsor", "uppercase"))
                        self.assertTrue(d["roleBelow"], "the role is under the name")
                        self.assertEqual((d["ruleDisplay"], d["ruleH"]), ("block", "3px"), "the blue rule above the words")
                        self.assertNotEqual(d["ruleBg"], d["panel"])
                        self.assertNotIn(d["panel"], ("rgba(0, 0, 0, 0)", "transparent"), "the grey panel")
                        if density == "comfortable":      # the compact look draws no card, only a line between sections, which Tile off also removes
                            self.assertEqual(d["tile"], "tile" not in off, "the tile is drawn only when it is on")
                        elif "tile" in off:
                            self.assertFalse(d["tile"], "no card and no line when Tile is off")
                        self.assertEqual(d["headingShown"], "heading" not in off, "the heading is drawn only when it is on")
                        self.assertTrue(d["wide"], "no sideways scroll")


if __name__ == "__main__":
    unittest.main()
