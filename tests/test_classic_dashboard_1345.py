"""Row 1345: the Classic Dashboard layout against prototype 2.0 (Contents list at 66, content column 262 wide to the right margin, section heading 20, section
padding 20 top and 22 left, At a glance without the far-right status words). Chrome is required: these tests fail, never skip, without it.
Sizes are the prototype's measured in Chrome at the same width (1385 px of page: a 1400 window less its scrollbar). Fictional data only.

Run: python3 dev/run_tests.py test_classic_dashboard_1345
"""
import unittest

from test_classic_contents_1318 import Classic as Base
from test_inline_67 import size
from test_server import chrome
from clark import page, theme  # noqa: F401

NAME = "prototype-2.0"
MARK = "/* Row 1345 block"

M = ("(function(){var r=function(e){var b=e.getBoundingClientRect();return [Math.round(b.left), Math.round(b.width)];}, s=document.querySelector('#report .secs > .sec:not(.is-hidden)'), cs=getComputedStyle(s);"
     "var n=document.querySelector('.cnt'), h=s.querySelector('.sec-h');"
     "return {cnt: n ? r(n) : null, secs: r(document.querySelector('.secs')), head: getComputedStyle(h).fontSize, pt: cs.paddingTop, pl: cs.paddingLeft,"
     "tw: [...document.querySelectorAll('.glance .fig .tw')].map(e => getComputedStyle(e).display), vw: document.documentElement.clientWidth};})()")


class Dash(Base):
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

    def test_at_900_the_page_keeps_its_margins(self):
        got = self.measure(900)
        self.assertEqual(got["secs"][0], 32)


class Text(unittest.TestCase):
    def test_the_block_is_one_comment_then_these_lines(self):
        rules = (theme_folder() / "rules.css").read_text(encoding="utf-8")
        block = rules[rules.index(MARK):]
        lines = [l for l in block.split("\n")[1:] if l.strip()]
        self.assertEqual(rules.count(MARK), 1)
        self.assertEqual(lines, LINES)


def theme_folder():
    from _paths import ROOT
    return ROOT / "src" / "clark" / "themes" / NAME


LINES = [
    '@media screen and (min-width: 1000px) {',
    '  html:has(.cnt-grid) main { max-width: none; margin: 0; padding-left: 66px; padding-right: max(var(--space-5), calc(50vw - 616px)); }',
    '  html:has(.cnt-grid) #report.frame.report { padding-left: 0; padding-right: 0; }',
    '  html[data-density] #report.frame .cnt-grid > .secs { margin-right: 0; }',
    '}',
    'html:not([data-density="comfortable"]) .rbar + #report { --sec-pad-t: 20px; --size-sec: var(--size-h3); }',
    'html:not([data-density="comfortable"]) .rbar + #report .secs > .sec:not(.slot-right) { padding-left: 22px; }',
    '.glance .fig .tw { display: none; }',
    '.glance .fig .hpill { padding: 0; background: none; font-size: 20px; font-weight: 700; letter-spacing: 0; text-transform: none; }',
    '.glance .fig .hpill.g { color: var(--status-green-text); } .glance .fig .hpill.a { color: var(--status-amber-text); } .glance .fig .hpill.r { color: var(--status-red-text); } .glance .fig .hpill.n { color: var(--text-muted); }',
]

if __name__ == "__main__":
    unittest.main()
