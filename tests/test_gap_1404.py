"""Row 1404: Dashboard At a glance under the Classic Theme, as Chrome computes it at 1400 px: the 'of N ...' note is inside the figure line (14px, muted,
same baseline as the figure), the label is Inter 400, the figure is Inter in the text colour with normal line height. Cards is the control (note on its own line).
Run: TZ=Asia/Dubai python3 dev/run_tests.py test_gap_1404"""
import re
import unittest
from unittest import mock

from _paths import SRC
from test_glance_page import Setup
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome
import _testpage as testpage
from clark import page, theme

NAME = "prototype-2.0"
RULES = ((SRC / "clark" / "themes" / NAME / "rules.css").read_text(encoding="utf-8") + (SRC / "clark" / "themes" / NAME / "rules-2.css").read_text(encoding="utf-8"))
PROBE = """(() => { const cs = (e, p) => getComputedStyle(e)[p], R = (e) => e.getBoundingClientRect();
  return [...document.querySelectorAll('.glance .fig:not(.health-fig)')].map((f) => { const k = f.querySelector('.k'), v = f.querySelector('.v'), dd = f.querySelector('.dd'), row = f.querySelector('.vrow');
    return { key: f.dataset.fig, label: k.textContent, labelFont: cs(k, 'fontFamily').split(',')[0], labelWeight: cs(k, 'fontWeight'), labelSize: cs(k, 'fontSize'),
      figFont: cs(v, 'fontFamily').split(',')[0], figWeight: cs(v, 'fontWeight'), figSize: cs(v, 'fontSize'), figLH: cs(v, 'lineHeight'), figSpacing: cs(v, 'letterSpacing'), figColor: cs(v, 'color'), tint: f.className,
      note: dd ? dd.textContent : null, noteInRow: !!(dd && row && row.contains(dd)), noteSize: dd ? cs(dd, 'fontSize') : null, noteWeight: dd ? cs(dd, 'fontWeight') : null, noteLH: dd ? cs(dd, 'lineHeight') : null, noteColor: dd ? cs(dd, 'color') : null,
      ddCount: f.querySelectorAll('.dd').length, rowAlign: row ? cs(row, 'alignItems') : null, noteBelow: dd ? Math.round(R(dd).top - R(v).bottom) : null, sameLine: dd ? Math.abs((R(dd).bottom) - (R(v).bottom)) < 6 : null, h: Math.round(R(f).height) }; }); })()"""


class Base(Setup):
    themed = True

    def setUp(self):
        orig = testpage.html
        css = theme.css(NAME) if self.themed else None
        m = mock.patch.object(testpage, "html", lambda branding=None: page.layer_theme(orig(), css) if css else orig())
        m.start()
        self.addCleanup(m.stop)
        super().setUp()

    def look(self, width=1400):
        with chrome() as cdp:
            p = self.show(cdp, width, False, standard=True)
            p.until("document.querySelectorAll('.glance .fig').length > 2", "the At a glance drew")
            return p.js(PROBE)


class Classic(Base):
    def test_T1_the_of_note_is_in_the_figure_line_14px_muted(self):
        got = self.look()
        of = [t for t in got if (t["note"] or "").startswith("of ")]
        self.assertTrue(of, got)
        for t in of:
            self.assertTrue(t["noteInRow"], t)
            self.assertEqual(t["noteSize"], "14px", t)
            self.assertEqual(t["noteWeight"], "400", t)                    # 400 explicit, the prototype wins over the ticket
            self.assertEqual(t["noteLH"], "21px", t)                       # line height 1.5 (14px x 1.5)
            self.assertTrue(t["sameLine"], t)
            self.assertEqual(t["noteColor"], "rgb(71, 85, 119)", t)       # the muted text colour
            self.assertEqual(t["ddCount"], 1, t)                           # one note, not a second copy under the row
            self.assertEqual(t["rowAlign"], "baseline", t)                 # the note and the figure share a baseline

    def test_T2_label_is_inter_400_figure_is_inter_text_colour_normal_line_height(self):
        for t in self.look():
            self.assertEqual((t["labelFont"], t["labelWeight"], t["labelSize"]), ("Inter", "400", "13px"), t)
            self.assertEqual(t["figFont"], "Inter", t)
            self.assertEqual((t["figSize"], t["figSpacing"]), ("20px", "normal"), t)
            self.assertNotRegex(t["figLH"], r"^23px$", t)
            if "rag-g" in t["tint"]:
                self.assertEqual(t["figColor"], "rgb(29, 36, 51)", t)

    def test_T3_the_block_sits_before_row_1314_which_stays_the_last_row_line(self):
        rows = [l for l in RULES.split("\n") if l.startswith("/* Row ")]
        self.assertTrue(rows[-1].startswith("/* Row 1314"), rows[-1][:40])
        self.assertLess(RULES.index("/* Row 1404"), RULES.index("/* Row 1314"))
        block = RULES.split("/* Row 1404")[1].split("\n/* Row ")[0]          # to the next Row comment, not to Row 1314: blocks merged in from main between them are not this one
        self.assertIsNone(re.search(r"#[0-9a-fA-F]", block), "colours from tokens only")

    def test_T4_the_note_rule_pins_weight_400_and_line_height_1_5(self):
        rule = re.search(r"\.glance \.fig \.vrow \.dd \{([^}]*)\}", RULES).group(1)
        self.assertRegex(rule, r"font-weight:\s*400\s*;")
        self.assertRegex(rule, r"line-height:\s*1\.5\s*;")
        self.assertRegex(rule, r"color:\s*var\(--text-muted\)\s*;")
        block = RULES.split("/* Row 1404")[1].split("\n/* Row ")[0]
        self.assertIn(".glance .fig .vrow .dd {", block, "the note rule sits inside the Row 1404 block")


class Cards(Base):
    themed = False

    def test_C1_cards_keeps_the_note_on_its_own_line(self):
        got = self.look()
        of = [t for t in got if (t["note"] or "").startswith("of ")]
        self.assertTrue(of, got)
        for t in of:
            self.assertFalse(t["noteInRow"], t)
            self.assertEqual(t["labelWeight"], "600", t)
            self.assertEqual(t["figFont"], "Montserrat", t)


if __name__ == "__main__":
    unittest.main()
