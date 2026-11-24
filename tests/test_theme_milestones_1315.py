"""Row 1315: the Milestones page in the Classic Theme, as Chrome computes it, at 1400 and 900 px, light and dark.

Run: python3 dev/run_tests.py test_theme_milestones_1315
Fails, never skips, without Chrome. Built here: the sentence under the title is hidden and the white card around the timeline and list is flat on screen. The joined
switches with a dark active button come from the rows 1313 and 1319 rules and are checked here on the Milestones page. Checked, not built:
the crumb and the title already match the prototype in the shared CSS. Cards (no theme layer) keeps the installed look.
"""
import re
import tempfile
import time
import unittest
from pathlib import Path

from _paths import ROOT  # noqa: F401
from test_server import chrome

from clark import page

SIZES = (1400, 900)
RULES = (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")
MARK = """<section class="frame milestones" id="milestones"><p class="crumbs">Project</p><div class="head"><div><h1>Milestones</h1>
<p class="head-sub" id="ms-empty">No milestones yet.</p>
<p class="head-sub head-sub-off" id="ms-summary">A line.</p></div></div>
<div class="msv"><div class="msv-sw" role="group"><button type="button" class="msv-b" data-msvb="line" aria-current="true"><span>Timeline</span></button><button type="button" class="msv-b" data-msvb="cal" aria-current="false"><span>Calendar</span></button></div>
<div class="cal-bar"><span class="seg cal-sc"><button type="button" data-scale-b="week" aria-current="false">Week</button><button type="button" data-scale-b="month" aria-current="true">Month</button><button type="button" data-scale-b="quarter" aria-current="false">Quarter</button></span></div></div></section>
<section class="frame milestones" id="other"><div class="msv"><div class="msv-sw"><button type="button" class="msv-b" aria-current="true"><span>Timeline</span></button><button type="button" class="msv-b" aria-current="false"><span>Calendar</span></button></div><span class="seg cal-sc" id="other-sc"><button type="button" data-scale-b="month" aria-current="true">Month</button></span></div></section>
<section class="frame milestones pub" id="pubm"><div class="msv"><div class="msv-sw"><button type="button" class="msv-b" aria-current="true"><span>Timeline</span></button></div></div></section>"""
Q = "document.querySelector(%r)"
STYLE = "(sel, p) => getComputedStyle(document.querySelector(sel))[p]"


def rgb(hex_colour):
    h = hex_colour.lstrip("#")
    return "rgb(%d, %d, %d)" % tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


PINNED = [
    '/* Row 1315 frame and switches (Milestones page, Classic only): the sentence under the title is hidden, and the white card around the timeline and list is flat on screen. The Timeline / Calendar and Week / Month / Quarter switches are already joined with a dark active button by the rules above (rows 1313 and 1319), so nothing is added for them. Scoped to the Milestones page, so the Dashboard section is not touched. */',
    '#milestones .head-sub { display: none; }      /* the sentence under the title is removed (decided 16-11); also the empty and cancelled sentences, which the shared rule leaves shown; it stays in the page for the tests */',
    '@media screen { #milestones.frame.milestones:not(.pub) .msv { background: transparent; border: 0; box-shadow: none; padding: 0; } #milestones.frame.milestones:not(.pub) .msv-sw { top: 0; right: 0; } }      /* row 1315: the white card around the timeline and list (the .msv box, not the frame, which is already bare) is gone on screen, flat like the dashboard frame; the switch moves to the corner of the flat page; print keeps its look */',
]


def own_block():
    """the row 1315 block: from its first comment to the next row's comment (a later row may append after it)."""
    tail = RULES[RULES.index("/* Row 1315 frame"):]
    nxt = tail.find("\n/* Row ", 1)
    return tail if nxt < 0 else tail[:nxt]


class Source(unittest.TestCase):
    def test_the_block_is_exactly_these_lines(self):      # the older pinned test stops at the row 1318 block; a later block is pinned in its own file
        block = own_block()
        self.assertEqual([l for l in block.split("\n") if l.strip()], PINNED)

    def test_the_rules_sit_in_one_block_after_the_row_1315_comment_and_all_start_at_the_milestones_page(self):
        block = own_block().split("*/", 1)[1]
        rules = [l for l in block.splitlines() if l.strip()]
        self.assertEqual(len(rules), 2)
        for r in rules:
            self.assertTrue(r.startswith("#milestones ") or r.startswith("@media screen { #milestones"), r)

    def test_no_hash_digits_and_no_tmp_path_in_the_rules(self):
        self.assertIsNone(re.search(r"#\d+", own_block().replace("#milestones", "")))
        self.assertNotIn("/tmp", RULES)


class Computed(unittest.TestCase):
    def load(self, cdp, width, scheme, theme):
        html = page.page_html(branding=page.NO_BRAND, theme=theme)
        path = Path(tempfile.mkdtemp(prefix="clark-test-")) / "p.html"
        path.write_text(html, encoding="utf-8")
        self.addCleanup(lambda: (path.unlink(), path.parent.rmdir()))
        tid = cdp.call("Target.createTarget", {"url": "about:blank"})["targetId"]
        sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
        end = time.monotonic() + 20
        while cdp.js("document.readyState", sid) != "complete" and time.monotonic() < end:
            time.sleep(0.05)
        cdp.js("""(() => { document.documentElement.setAttribute('data-theme', %r);
            const d = document.createElement('div'); d.innerHTML = %r; document.body.appendChild(d); })()""" % (scheme, MARK), sid)
        return sid

    def css(self, cdp, sid, sel, prop):
        return cdp.js("getComputedStyle(%s)[%r]" % (Q % sel, prop), sid)

    def test_classic_the_switches_are_joined_with_a_dark_active_button_at_the_milestones_page(self):
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                for w in SIZES:
                    sid = self.load(cdp, w, scheme, "prototype-2.0")
                    tag = f"{scheme} {w}"
                    c = lambda s, p: self.css(cdp, sid, s, p)
                    dark = "rgb(43, 56, 80)" if scheme == "dark" else "rgb(6, 47, 58)"      # the active fill since row 1354: the prototype's navy, or #2b3850 in dark
                    self.assertEqual(c('#milestones .msv-b[data-msvb="line"]', "backgroundColor"), dark, tag)
                    self.assertNotEqual(c('#milestones .msv-b[data-msvb="cal"]', "backgroundColor"), dark, tag)
                    self.assertEqual(c('#milestones [data-scale-b="month"]', "backgroundImage"), "none", tag)      # a filled active scale button, the rows 1313 and 1319 rules
                    self.assertNotEqual(c('#milestones [data-scale-b="month"]', "backgroundColor"), c('#milestones [data-scale-b="week"]', "backgroundColor"), tag)
                    self.assertEqual(c("#milestones .msv-sw", "columnGap"), "0px", tag)
                    self.assertEqual(c("#milestones .msv-sw", "overflow"), "hidden", tag)
                    self.assertEqual(c("#milestones .msv-sw", "borderTopWidth"), "1px", tag)
                    self.assertEqual(c('#milestones .msv-b[data-msvb="cal"]', "borderLeftWidth"), "1px", tag)
                    self.assertEqual(c('#milestones .msv-b[data-msvb="line"]', "borderTopLeftRadius"), "0px", tag)
                    self.assertTrue(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), tag)

    def test_classic_the_crumb_title_and_sentence_already_match_the_prototype(self):
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                for w in SIZES:
                    sid = self.load(cdp, w, scheme, "prototype-2.0")
                    tag = f"{scheme} {w}"
                    c = lambda s, p: self.css(cdp, sid, s, p)
                    self.assertEqual(c("#milestones .crumbs", "textTransform"), "none", tag)
                    self.assertEqual(c("#milestones .crumbs", "fontSize"), "13px", tag)
                    self.assertEqual(c("#milestones .crumbs", "letterSpacing"), "normal", tag)
                    self.assertEqual(c("#milestones h1", "fontSize"), "30px", tag)
                    self.assertEqual(c("#ms-summary", "display"), "none", tag)
                    self.assertEqual(c("#ms-empty", "display"), "none", tag)     # the sentence without a last-milestone line is hidden too, in the page for the tests

    def test_cards_still_shows_the_sentence_that_has_no_line(self):
        with chrome() as cdp:
            sid = self.load(cdp, 1400, "light", None)
            self.assertNotEqual(self.css(cdp, sid, "#ms-empty", "display"), "none")

    def test_classic_the_milestones_card_is_flat_on_screen_and_the_other_page_keeps_its_card(self):
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                for w in SIZES:
                    sid = self.load(cdp, w, scheme, "prototype-2.0")
                    tag = f"{scheme} {w}"
                    c = lambda s, p: self.css(cdp, sid, s, p)
                    self.assertEqual(c("#milestones .msv", "backgroundColor"), "rgba(0, 0, 0, 0)", tag)
                    self.assertEqual(c("#milestones .msv", "borderTopWidth"), "0px", tag)
                    self.assertEqual(c("#milestones .msv", "boxShadow"), "none", tag)
                    self.assertEqual(c("#milestones .msv", "paddingLeft"), "0px", tag)
                    self.assertEqual(c("#milestones .msv-sw", "position"), "absolute", tag)      # row 1355: at the top left of the page, not in the right corner
                    self.assertEqual(c("#pubm", "borderTopWidth"), "1px", tag)      # a published file keeps its card
                    self.assertEqual(c("#other .msv", "borderTopWidth"), "1px", tag)
                    self.assertNotEqual(c("#other .msv", "boxShadow"), "none", tag)

    def _row_1260_ap2(self, w):
        """Row 1260 AP2: Cards hides the has-a-line sentence by shell.css .head-sub-off; Classic hides it by rules.css #milestones .head-sub."""
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                tag = f"{scheme} {w}"
                sid = self.load(cdp, w, scheme, None)      # Cards: no theme layer, so only the shared .head-sub-off rule can hide it
                self.assertEqual(self.css(cdp, sid, "#ms-summary", "display"), "none", "Cards " + tag)
                cdp.js("document.getElementById('ms-summary').classList.remove('head-sub-off')", sid)
                self.assertNotEqual(self.css(cdp, sid, "#ms-summary", "display"), "none", "Cards without .head-sub-off " + tag)      # so it is shell.css .head-sub-off that hides it
                sid = self.load(cdp, w, scheme, "prototype-2.0")
                self.assertEqual(self.css(cdp, sid, "#ms-summary", "display"), "none", "Classic " + tag)
                cdp.js("document.getElementById('ms-summary').classList.remove('head-sub-off')", sid)
                self.assertEqual(self.css(cdp, sid, "#ms-summary", "display"), "none", "Classic without .head-sub-off " + tag)      # so it is rules.css:300 that hides it

    def test_at_1400_cards_hides_the_milestones_sentence_by_head_sub_off_and_classic_by_the_milestones_head_sub_rule(self):
        self._row_1260_ap2(1400)

    def test_at_900_cards_hides_the_milestones_sentence_by_head_sub_off_and_classic_by_the_milestones_head_sub_rule(self):
        self._row_1260_ap2(900)

    def test_the_two_hiding_selectors_are_in_the_shared_css_and_the_classic_rules(self):
        shell = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
        self.assertRegex(shell, r"(?m)^\.head-sub-off \{ display: none; \}")
        self.assertRegex(RULES, r"(?m)^#milestones \.head-sub \{ display: none; \}")

    def test_cards_keeps_the_milestones_card(self):
        with chrome() as cdp:
            sid = self.load(cdp, 1400, "light", None)
            self.assertEqual(self.css(cdp, sid, "#milestones .msv", "borderTopWidth"), "1px")
            self.assertNotEqual(self.css(cdp, sid, "#milestones .msv", "boxShadow"), "none")

    def test_cards_keeps_its_switch_look(self):
        with chrome() as cdp:
            for w in SIZES:
                sid = self.load(cdp, w, "light", None)
                tag = f"cards {w}"
                self.assertEqual(self.css(cdp, sid, "#milestones .msv-sw", "columnGap"), "2px", tag)
                self.assertNotEqual(self.css(cdp, sid, '#milestones [data-scale-b="month"]', "backgroundImage"), "none", tag)


if __name__ == "__main__":
    unittest.main()
