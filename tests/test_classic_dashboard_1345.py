"""Row 1345: the Classic Dashboard layout against prototype 2.0 (Contents list at 66, content column 262 wide to the right margin, section heading 20, section
padding 20 top and 22 left, At a glance without the far-right status words). Chrome is required: these tests fail, never skip, without it.
Sizes are the prototype's measured in Chrome at the same width (1385 px of page: a 1400 window less its scrollbar). Fictional data only.

Run: python3 dev/run_tests.py test_classic_dashboard_1345
"""
import json
import unittest

from _demo import USER

from test_classic_contents_1318 import Classic as Base
from test_inline_67 import size
from test_server import chrome
from clark import page, theme  # noqa: F401

NAME = "prototype-2.0"
MARK = "/* Row 1345 block"
MARK2 = "/* Row 1345 title block"

M = ("(function(){var r=function(e){var b=e.getBoundingClientRect();return [Math.round(b.left), Math.round(b.width)];}, s=document.querySelector('#report .secs > .sec[data-id=ABC-S-003]'), cs=getComputedStyle(s);"
     "var n=document.querySelector('.cnt'), h=s.querySelector('.sec-h');"
     "return {cnt: n ? r(n) : null, secs: r(document.querySelector('.secs')), head: getComputedStyle(h).fontSize, pt: cs.paddingTop, pl: cs.paddingLeft,"
     "tw: [...document.querySelectorAll('.glance .fig .tw')].map(e => getComputedStyle(e).display), vw: document.documentElement.clientWidth};})()")


class Dash(Base):
    def setUp(self):
        super().setUp()
        # row 1266: a new project starts with the Headline and the At a glance template; the figures strip these tests pin (.glance, .hpill, .tw) is the
        # older At a glance section type, which an existing report keeps, so one is stored here (after the defaults); the first section measured is Header
        with self.store.step("dashboard", USER) as st:
            st.create("report_sections", {"project": "ABC", "type": "glance", "title": "At a glance (figures)", "sort_order": 10 ** 9})

    def measure(self, width, density="compact"):
        with chrome() as cdp:
            p = self.at(cdp, width)
            p.js("document.documentElement.dataset.density = %r" % density)
            p.until("getComputedStyle(document.querySelector('.sec-h')).fontSize !== ''", "the density is applied")
            return p.js(M)


for _n in [n for n in dir(Base) if n.startswith('test_')]:      # the 1318 tests run in their own file
    setattr(Dash, _n, None)


class Measured(Dash):
    def test_at_1400_compact_contents_at_66_and_the_column_at_262_to_the_right_margin(self):
        got = self.measure(1400)
        self.assertEqual(got["vw"], 1385)
        self.assertEqual(got["cnt"], [66, 168])
        self.assertEqual(got["secs"], [262, 1039])      # 1385 - 262 - (700 - 616 = 84)

    def test_at_1400_compact_heading_is_20_and_padding_is_20_top_22_left(self):
        got = self.measure(1400)
        self.assertEqual([got["head"], got["pt"], got["pl"]], ["20px", "20px", "22px"])

    def test_at_900_compact_heading_is_20_and_padding_is_20_top_22_left_and_no_contents_column(self):
        got = self.measure(900)
        self.assertEqual([got["head"], got["pt"], got["pl"]], ["20px", "20px", "22px"])
        self.assertEqual(got["cnt"][1], 0)

    def test_at_a_glance_shows_no_status_word_beside_the_figure_at_1400_and_900(self):
        for w in (1400, 900):
            got = self.measure(w)
            self.assertTrue(got["tw"], "the strip has figures with a word")
            self.assertEqual(set(got["tw"]), {"none"}, w)

    def test_comfortable_keeps_its_heading_and_padding(self):
        got = self.measure(1400, "comfortable")
        self.assertEqual([got["head"], got["pt"], got["pl"]], ["19px", "14px", "20px"])

    def test_the_health_word_is_plain_text_in_the_tone_colour(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            got = p.js("(function(){var e=document.querySelector('.glance .hpill'), c=getComputedStyle(e);return [c.fontSize, c.fontWeight, c.textTransform, c.backgroundColor, c.paddingLeft];})()")
        self.assertEqual(got, ["20px", "700", "none", "rgba(0, 0, 0, 0)", "0px"])


HM = """(function(){var q=function(s){return document.querySelector(s)}, g=function(s){return getComputedStyle(q(s))}, r=function(s){var b=q(s).getBoundingClientRect(); return [Math.round(b.left), Math.round(b.width), Math.round(b.height)];};
return {title: [g('.tpl-rh-title').fontSize, g('.tpl-rh-title').lineHeight, g('.tpl-rh-title').fontWeight, g('.tpl-rh-title').marginBottom, g('.tpl-rh-title').letterSpacing],
meta: [g('.tpl-rh-meta').marginTop, g('.tpl-rh-meta').marginBottom], health: [g('.tpl-rh').gap, g('.tpl-rh').paddingTop, g('.tpl-rh').borderTopWidth, g('.tpl-rh').borderBottomWidth, g('.tpl-rh').flexDirection, g('.tpl-rh').marginBottom],
pill: [g('.tpl-rh-pill').fontWeight, g('.tpl-rh-pill').paddingLeft, g('.tpl-rh-pill').paddingTop, g('.tpl-rh-pill').gap, g('.tpl-rh-pill').letterSpacing, g('.tpl-rh-pill').textTransform, r('.tpl-rh-pill')[2]],
lead: [g('.tpl-rh-h').fontSize, g('.tpl-rh-h').fontWeight, g('.tpl-rh-h').marginBottom], sub: [g('.tpl-rh-p').marginTop],
sec: [getComputedStyle(q('.tpl-rh-block').parentNode).paddingLeft, getComputedStyle(q('.tpl-rh-block').parentNode).paddingTop], block: r('.tpl-rh-block')};})()"""


class TitleBlock(Dash):
    """The Report headline section (row 1261) as prototype 2.0 index.html lines 111-119 draws it, measured at 1400 and 900."""

    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            st.create("report_sections", {"project": "ABC", "type": "reportheadline", "title": "Fictional headline", "sort_order": -1,
                                           "body": json.dumps({"v": 1, "health": "at_risk", "headline": "Fictional plan holds", "sentence": "Fictional reason."})})

    def check(self, width, col):
        with chrome() as cdp:
            p = self.at(cdp, width)
            p.js("document.documentElement.dataset.density = 'compact'")
            got = p.js(HM)
            vw = p.js("document.documentElement.clientWidth")
        self.assertEqual(got["title"], ["30px", "36px", "600", "4px", "-0.3px"])
        self.assertEqual(got["meta"], ["0px", "4px"])
        self.assertEqual(got["health"], ["12px", "12px", "1px", "1px", "row", "0px"])
        self.assertEqual(got["pill"], ["700", "12px", "2px", "6px", "0.42px", "uppercase", 28])
        self.assertEqual(got["lead"], ["16px", "700", "4px"])
        self.assertEqual(got["sub"], ["0px"])
        self.assertEqual(got["sec"], ["0px", "0px"])
        self.assertEqual(got["block"][:2], col(vw) if callable(col) else col)

    def test_at_1400(self):
        self.check(1400, [262, 1017])      # the column less the section's 22 right padding

    def test_at_900(self):
        self.check(900, lambda vw: [20, vw - 66])      # the page less 20, 24 and the section's 22 right padding


class Killers(Dash):
    def test_the_health_word_keeps_no_tracking_and_has_its_own_colour_for_each_state(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            got = p.js("(function(){var e=document.querySelector('.glance .hpill'), out=[getComputedStyle(e).letterSpacing];"
                       "['g','a','r','n'].forEach(function(k){e.className='pill hpill '+k; out.push(getComputedStyle(e).color);});"
                       "var v=function(n){var t=document.createElement('i'); t.style.color='var('+n+')'; document.body.appendChild(t); var c=getComputedStyle(t).color; t.remove(); return c;};"
                       "return out.concat(['--status-green-text','--status-amber-text','--status-red-text','--text-muted'].map(v));})()")
        self.assertEqual(got[0], "normal")
        self.assertEqual(got[1:5], got[5:9])
        self.assertEqual(len(set(got[1:5])), 4)

    def test_a_section_in_the_right_half_of_a_pair_keeps_its_own_padding(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            p.js("document.documentElement.dataset.density = 'compact'; document.querySelectorAll('#report .secs > .sec')[1].classList.add('slot-right')")
            got = p.js("getComputedStyle(document.querySelectorAll('#report .secs > .sec')[1]).paddingLeft")
        self.assertNotEqual(got, "22px")

    def test_at_900_the_column_is_at_20_and_ends_24_before_the_right_edge(self):
        got = self.measure(900)
        self.assertEqual(got["secs"], [20, got["vw"] - 44])      # one column; prototype 856 wide on a 900 page without a scrollbar


class Text(unittest.TestCase):
    def test_the_block_is_one_comment_then_these_lines(self):
        rules = (theme_folder() / "rules.css").read_text(encoding="utf-8")
        block = rules[rules.index(MARK):rules.index(MARK2)]
        lines = [l for l in block.split("\n")[1:] if l.strip()]
        self.assertEqual(rules.count(MARK), 1)
        self.assertEqual(lines, LINES)

    def test_the_title_block_rules_are_these_lines(self):
        rules = (theme_folder() / "rules.css").read_text(encoding="utf-8")
        block = rules[rules.index(MARK2):rules.index("/* Row 1345 layout rows")]
        self.assertEqual(rules.count(MARK2), 1)
        self.assertEqual([l for l in block.split("\n")[1:] if l.strip()], HEAD_LINES)


def theme_folder():
    from _paths import ROOT
    return ROOT / "src" / "clark" / "themes" / NAME


LINES = [
    '@media screen and (min-width: 1000px) {',
    '  html:has(.rbar + #report .cnt-grid) main { max-width: none; margin: 0; padding-left: 66px; padding-right: max(var(--space-5), calc(50vw - 616px)); }',
    '  html:has(.rbar + #report .cnt-grid) #report.frame.report { padding-left: 0; padding-right: 0; }',
    '  html[data-density] #report.frame .cnt-grid > .secs { margin-right: 0; }',
    '}',
    'html:not([data-density="comfortable"]) .rbar + #report { --sec-pad-t: 20px; --size-sec: var(--size-h3); }',
    'html:not([data-density="comfortable"]) .rbar + #report .secs > .sec:not(.slot-right) { padding-left: 22px; }',
    '.glance .fig .tw { display: none; }',
    '.glance .fig .hpill { padding: 0; background: none; font-size: 20px; font-weight: 700; letter-spacing: 0; text-transform: none; }',
    '.glance .fig .hpill.g { color: var(--status-green-text); } .glance .fig .hpill.a { color: var(--status-amber-text); } .glance .fig .hpill.r { color: var(--status-red-text); } .glance .fig .hpill.n { color: var(--text-muted); }',
]

HEAD_LINES = [
    'html:not([data-density="comfortable"]) .rbar + #report .secs > .sec:not(.slot-right):has(> .tpl-rh-block) { padding-top: 0; padding-left: 0; }',
    '.sec:has(> .tpl-rh-block) { padding-top: 0; padding-left: 0; }',
    '.tpl-rh-block { margin: 0; }',
    '.tpl-rh-title { font-family: var(--font-head); font-size: 30px; line-height: 1.2; font-weight: 600; margin: 0 0 4px; letter-spacing: -.01em; }',
    '.tpl-rh-meta { margin: 0 0 16px; }',
    '.tpl-rh-block .tpl-rh { margin: 0; gap: 12px; padding: 12px 0; }',
    '.tpl-rh-block .tpl-rh-pill { gap: 6px; font-size: 14px; font-weight: 700; padding: 2px 12px; min-height: 28px; letter-spacing: .03em; text-transform: uppercase; }',
    '.tpl-rh-block .tpl-rh-h { font-size: 16px; font-weight: 600; margin: 0 0 4px; }',
    '.tpl-rh-block .tpl-rh-h + .tpl-rh-p { margin-top: 0; }',
    '@media (max-width: 900px) { .tpl-rh-block .tpl-rh { flex-direction: row; gap: 12px; } }',
]

if __name__ == "__main__":
    unittest.main()
