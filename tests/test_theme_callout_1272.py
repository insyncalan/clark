"""Row 1272, the two points no other change carries: the library card's sketch for the Callout is look B (a tinted box, an edge, no stripe) and a
Plain callout in Edit draws a dashed outline. Both are Classic only: the Cards look keeps its amber stripe sketch and the plain box with no outline.
Real page, as Chrome computes it at 1400 and 900 px; the rule texts are pinned too. Fictional data only.

Run: TZ=Asia/Dubai python3 dev/run_tests.py test_theme_callout_1272   (needs Chrome)
"""
import json
import re
import unittest
from unittest import mock

import _testpage as testpage
from _paths import SRC
from clark import page, theme
from test_report_editor import Base
from test_server import chrome
from test_templates import OPEN

NAME = "prototype-2.0"
RULES = (SRC / "clark" / "themes" / NAME / "rules.css").read_text(encoding="utf-8")
SHELL = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
SK = "document.querySelector('[data-template=callout] .ad-sk')"
PROBE = f"""(() => {{ const k = {SK}, cs = getComputedStyle(k), kids = [...k.children].map((i) => getComputedStyle(i));
  return {{ classes: k.className, left: cs.borderLeftWidth, top: cs.borderTopWidth, bg: cs.backgroundColor, kids: kids.length,
    dot: kids[0] ? [kids[0].borderTopLeftRadius, kids[0].width] : null }}; }})()"""
# Row 1272: the card's colours as Chrome computes them, against the same token expression drawn on a probe element (so the pin follows the tokens, not a literal).
COLOURS = """(() => { const k = %s, probe = (css) => { const d = document.createElement('div'); d.style.cssText = css; document.body.appendChild(d); const v = getComputedStyle(d); const o = [v.backgroundColor, v.borderTopColor, v.color]; d.remove(); return o; };
  const cs = getComputedStyle(k), kids = [...k.children].map((i) => getComputedStyle(i).backgroundColor);
  const want = probe('background:var(--brand-blue-tint);border:1px solid color-mix(in srgb, var(--status-blue) 45%%, var(--brand-blue-tint))');
  const ink = probe('background:color-mix(in srgb, var(--status-blue-text) 55%%, var(--brand-blue-tint))')[0];
  return { bg: [cs.backgroundColor, want[0]], edge: [cs.borderTopColor, want[1]], text: [cs.color, getComputedStyle(k.parentElement).color], ink: kids.map((c) => [c, ink]).slice(0, 3), kids: kids }; })()""" % SK
BOX = "document.querySelector('[data-id=%s] .tpl-callout')"


class Rules(unittest.TestCase):
    def block(self):
        i = RULES.index("/* Row 1272 ")
        return RULES[i:RULES.index("/* Row ", i + 1)]

    def test_the_block_sits_after_row_1318_and_before_row_1393_and_the_file_stays_under_128_kib(self):
        self.assertGreater(RULES.index("/* Row 1272 "), RULES.index("/* Row 1318"))
        self.assertLess(RULES.index("/* Row 1272 "), RULES.index("/* Row 1393"))
        self.assertLess(len(RULES.encode("utf-8")), 131072)

    def test_the_rules_use_tokens_only_and_draw_no_stripe(self):
        for line in self.block().splitlines()[1:]:
            self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(", line), line)
            self.assertNotRegex(line, r"border-(left|inline-start)", line)
        self.assertNotIn("sk-callout-b", SHELL)
        self.assertIn("var(--status-blue)", self.block())

    def test_the_cards_sketch_is_not_touched(self):
        js = (SRC / "clark" / "page" / "src" / "logic" / "templates.js").read_text(encoding="utf-8")
        self.assertIn('"callout": ["", ["background:var(--status-amber-tint);border-left:3px solid var(--status-amber)"]]', js)


class Shared(Base):
    classic = True

    def setUp(self):
        orig = testpage.html
        css = theme.css(NAME) if self.classic else None
        m = mock.patch.object(testpage, "html", lambda branding=None: page.layer_theme(orig(), css) if css else orig())
        m.start()
        self.addCleanup(m.stop)
        super().setUp()

    def at(self, cdp, width):
        p = self.visit(cdp)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.edit()
        return p

    def sketch(self, width):
        with chrome() as cdp:
            p = self.at(cdp, width)
            p.js(OPEN % json.dumps("ABC-S-003"))
            p.until("!!document.querySelector('[data-template=callout] .ad-sk')", "the Callout card is drawn with its sketch")
            return p.js(PROBE)

    def colours(self, width):
        with chrome() as cdp:
            p = self.at(cdp, width)
            p.js(OPEN % json.dumps("ABC-S-003"))
            p.until("!!document.querySelector('[data-template=callout] .ad-sk')", "the Callout card is drawn with its sketch")
            return p.js(COLOURS)

    def make_plain(self):
        from _demo import USER
        from test_changes import KIND
        with self.store.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": "callout", "title": "Fictional callout", "sort_order": 999})
        body = {"v": 1, "title": "Fictional plain", "paras": ["Fictional words."], "colour": "plain"}
        status, got = self.real_change({"project": "ABC", "kind": KIND, "op": "update", "id": ref, "changes": {"body": json.dumps(body)}})
        assert status == 200, got
        return ref



class Classic(Shared):
    def test_classic_library_card_is_look_b_with_no_stripe(self):
        for width in (1400, 900):
            got = self.sketch(width)
            self.assertIn("sk-callout-b", got["classes"], width)
            self.assertEqual((got["left"], got["top"]), ("1px", "1px"), f"{width}: an even 1px edge, no 3px stripe")
            self.assertEqual(got["kids"], 3, "an icon dot and two bars")
            self.assertEqual(got["dot"][0], "50%", "the icon is a dot")
            self.assertNotEqual(got["bg"], "rgb(255, 248, 225)")

    def test_classic_library_card_thumbnail_colours_are_pinned(self):
        for width in (1400, 900):
            got = self.colours(width)
            self.assertEqual(got["bg"][0], got["bg"][1], f"{width}: the tint fill")
            self.assertEqual(got["edge"][0], got["edge"][1], f"{width}: the 45% edge")
            for have, want in got["ink"]:
                self.assertEqual(have, want, f"{width}: the icon dot and the bars use the ink mix")
            self.assertNotEqual(got["bg"][0], got["ink"][0][0], "the box and its dot differ")
            self.assertEqual(got["text"][0], got["text"][1], f"{width}: the sketch carries no text colour of its own")

    def test_classic_plain_box_in_edit_has_a_dashed_border_and_padding_not_an_outline_and_view_has_none(self):
        ref = self.make_plain()
        for width in (1400, 900):
            with chrome() as cdp:
                p = self.visit(cdp)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                view = p.js(f"getComputedStyle({BOX % json.dumps(ref)}).outlineStyle")
                self.assertEqual(view, "none", f"{width}: View draws no outline")
                p.edit()
                p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}] .cb .tpl-callout.k-plain')", "the plain callout in Edit")
                cs = "getComputedStyle(document.querySelector('[data-id=%s] .cb .tpl-callout.k-plain'))" % json.dumps(ref)
                self.assertEqual(p.js(f"{cs}.borderTopStyle + ' ' + {cs}.borderTopWidth + ' ' + {cs}.outlineStyle"), "dashed 1px none", width)
                want = p.js("(() => { const d = document.createElement('div'); d.style.cssText = 'padding:var(--space-2) var(--space-3);border-color:var(--text-muted);border-style:solid'; document.body.appendChild(d); const v = getComputedStyle(d); const o = [v.paddingTop, v.paddingLeft, v.borderTopColor]; d.remove(); return o; })()")
                self.assertEqual(p.js(f"[{cs}.paddingTop, {cs}.paddingLeft, {cs}.borderTopColor]"), want, f"{width}: the mock-up's padding and edge colour")


class Cards(Shared):
    classic = False

    def test_cards_keeps_its_amber_sketch(self):
        for width in (1400, 900):
            got = self.sketch(width)
            self.assertNotIn("sk-callout-b", got["classes"])
            self.assertEqual(got["kids"], 1, "Cards keeps its one-part amber sketch")
            self.assertEqual(got["left"], "0px")

    def test_cards_plain_box_in_edit_has_no_outline(self):
        ref = self.make_plain()
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}] .cb .tpl-callout.k-plain')", "the plain callout in Edit")
            self.assertEqual(p.js("getComputedStyle(document.querySelector('[data-id=%s] .cb .tpl-callout.k-plain')).borderTopStyle" % json.dumps(ref)), "solid", "Cards keeps the base box edge, transparent")


if __name__ == "__main__":
    unittest.main()
