"""Row 1305: the Classic Theme's page header. The project name stays on one line and is cut with an ellipsis only at half the header's width;
the full name is the hover tip of the editor's name button (with its "Click to change project", kept) and the title of the file's name.
Cards (no Theme) is the page byte for byte: no title, no tip change, none of the CSS reaches it.

Run: python3 dev/run_tests.py test_theme_header_1305
Chrome is required: the page parts fail, never skip, without it.
"""
import re
import unittest
from unittest import mock

from _paths import ROOT  # noqa: F401
from test_glance_page import Setup
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome
from _publish import PublishedFile
import _testpage as testpage
from clark import page, theme

NAME = "prototype-2.0"
RULES = (ROOT / "src" / "clark" / "themes" / NAME / "rules.css").read_text(encoding="utf-8")
M1305 = "/* Row 1305"
# the block runs to the next Row comment, whichever row that is (later rows land after it)
PART_1305 = RULES[RULES.index(M1305):RULES.index("/* Row ", RULES.index(M1305) + 1)]
LONG = "A very long project name that goes on and on and on and on and on and on and on and on and on"
HEADER = "document.querySelector('.top-hdr, .top-file')"

NAME_PROBE = """(() => { const bar = %s, n = document.querySelector('.hdr-project, .top-name'), s = n.querySelector('span') || n, c = getComputedStyle(s);
  const b = bar.getBoundingClientRect(), r = n.getBoundingClientRect(), id = (n.closest('.hdr-id, .top-id') || n).getBoundingClientRect();
  const kids = [...bar.children].map((e) => e.getBoundingClientRect());
  return {ws: c.whiteSpace, to: c.textOverflow, ov: c.overflow, h: r.height, lh: parseFloat(getComputedStyle(n).lineHeight), idW: id.width, nameW: r.width, barW: b.width,
          barH: b.height, clip: s.scrollWidth > s.clientWidth, title: (s.title || n.title || ''), text: s.textContent, wide: document.documentElement.scrollWidth <= innerWidth,
          overlap: kids.some((k, i) => kids.some((o, j) => j > i && k.width > 0 && o.width > 0 && k.right > o.left + 1 && k.left < o.right - 1 && k.bottom > o.top + 1 && k.top < o.bottom - 1))}; })()"""



class Text(unittest.TestCase):
    def test_the_block_has_one_comment_naming_the_places_left_alone_and_no_colour_or_path(self):
        comment = PART_1305.split("\n")[0]
        self.assertTrue(comment.endswith("*/"))
        self.assertIn("row 1305", comment.lower())
        for left in (".cover-switch", "Gantt", ".hdr-project", ".top-name"):
            self.assertIn(left, comment)
        self.assertIsNone(re.search(r"#\d", comment))
        self.assertNotIn("/tmp", comment)
        self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", "\n".join(PART_1305.split("\n")[1:])))
        self.assertEqual([l for l in PART_1305.split("\n")[1:] if l.strip()], [
            ".hdr-id, .top-id { max-width: 50%; }",
            ".hdr-project, .hdr-project > span, .top-name { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }"])

    def test_every_title_and_tip_is_set_only_when_classic_is_on(self):
        src = ROOT / "src" / "clark" / "page" / "src"
        top = (src / "components" / "TopBar.jsx").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"title=\{classicTheme\(\) \? ", top)), 2)
        sw = (src / "edit" / "ProjectSwitch.jsx").read_text(encoding="utf-8")
        self.assertIn('tip={classicTheme() ? `${shown}. Click to change project` : "Click to change project"}', sw)
        self.assertNotIn("labelTitle", (src / "components" / "Menu.jsx").read_text(encoding="utf-8"))

    def test_the_file_stays_under_128_kib_and_the_block_is_above_row_1393_only(self):
        self.assertLess(len(RULES.encode("utf-8")), 131072)
        self.assertGreater(RULES.index(M1305), RULES.index("/* Row 1318"))

    def test_cards_has_none_of_it_and_classic_is_cards_plus_the_theme_style(self):
        cards = page.page_html(branding=page.NO_BRAND)
        self.assertNotIn(".hdr-id, .top-id", cards)
        classic = page.page_html(branding=page.NO_BRAND, theme=NAME)
        self.assertIn(".hdr-id, .top-id { max-width: 50%; }", classic)
        self.assertEqual(classic.replace('\n<style id="theme">\n' + theme.css(NAME) + "\n</style>", "", 1), cards)
        self.assertNotIn(".hdr-id, .top-id", (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8"))


class Editor(Setup):
    def setUp(self):
        orig = testpage.html
        m = mock.patch.object(testpage, "html", lambda branding=None: page.layer_theme(orig(), theme.css(NAME)))
        m.start()
        self.addCleanup(m.stop)
        super().setUp()

    def measure(self, width, hash_):
        with chrome() as cdp:
            p = self.show(cdp, width, False, hash_=hash_, settings=True)
            p.until("!!document.querySelector('.top-hdr .hdr-project[data-tip^=\"Example Programme\"]') && document.documentElement.dataset.ready === '1'", "the header drew")
            short = p.js(NAME_PROBE % HEADER)
            tip = p.js("(() => { const b = document.querySelector('.top-hdr .hdr-project'); return {title: b.title, tip: b.dataset.tip, inner: b.querySelector('span').title}; })()")
            p.js("(() => { const s = document.querySelector('.hdr-project > span'); s.textContent = %r; })()" % LONG)
            long = p.js(NAME_PROBE % HEADER)
            return short, long, tip

    def test_the_name_is_one_line_cut_at_half_the_header_and_the_button_keeps_its_tip_at_1400_and_900(self):
        for width in (1400, 900):
            for hash_ in ("#dashboard&p=ABC", "#work&p=ABC"):
                with self.subTest(width=width, page=hash_):
                    short, long, tip = self.measure(width, hash_)
                    self.assertEqual((short["ws"], short["to"], short["ov"]), ("nowrap", "ellipsis", "hidden"))
                    self.assertLessEqual(short["h"], short["lh"] + 1)
                    self.assertEqual((long["ws"], long["to"]), ("nowrap", "ellipsis"))
                    self.assertLessEqual(long["h"], long["lh"] + 1, "one line however long the name")
                    self.assertTrue(long["clip"], "the long name is cut")
                    self.assertLessEqual(long["idW"], long["barW"] * 0.5 + 1, "the name's box stops at half the header")
                    self.assertGreater(long["idW"], long["barW"] * (0.25 if width == 900 else 0.3), "it is cut only because it reached the half (at 900 the ask clark button of row 1349 stays in the header and takes room)")
                    self.assertEqual(long["barH"], short["barH"], "a long name does not grow the bar")
                    self.assertFalse(long["overlap"], "nothing in the header is pushed over or under another")
                    self.assertTrue(long["wide"])
                    full = "Example Programme. Click to change project"
                    self.assertEqual((tip["title"], tip["tip"]), (full, full), "the button's own tip has the full name and keeps Click to change project")
                    self.assertEqual(tip["inner"], "", "no title on the inner span, so the tip is not hidden when the pointer is on the name")


class Cards(Setup):
    """Cards (no Theme): no title anywhere on the name, the button's tip is the old one."""

    def test_the_editor_header_has_no_name_title_and_the_old_tip_at_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width, False, hash_="#dashboard&p=ABC", settings=True)
                p.until("!!document.querySelector('.top-hdr .hdr-project') && document.documentElement.dataset.ready === '1'", "the header drew")
                got = p.js("(() => { const b = document.querySelector('.top-hdr .hdr-project'); return {title: b.title, tip: b.dataset.tip, inner: [...b.querySelectorAll('[title]')].length, any: document.querySelectorAll('.top-hdr [title]:not(button)').length, ws: getComputedStyle(b.querySelector('span')).whiteSpace}; })()")
                self.assertEqual((got["title"], got["tip"]), ("Click to change project", "Click to change project"))
                self.assertEqual(got["inner"], 0, "Cards: no title on the name")
                self.assertNotEqual(got["ws"], "nowrap", "Cards keeps the wrapped name of row 1239")


class InTheFile(PublishedFile, Setup):
    theme = "classic"

    def test_the_published_report_has_the_same_name_rule_and_the_full_name_title_at_1400_and_900(self):
        path = self.publish()
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.draw(cdp, path, width, dark)
                    p.until("!!document.querySelector('.top-file .top-name')", "the bar drew")
                    self.assertEqual(p.js("document.querySelector('.top-name').title"), p.js("document.querySelector('.top-name').textContent"))
                    p.js("document.querySelector('.top-name').textContent = %r" % LONG)
                    got = p.js(NAME_PROBE % HEADER)
                    self.assertEqual((got["ws"], got["to"], got["ov"]), ("nowrap", "ellipsis", "hidden"))
                    self.assertLessEqual(got["h"], got["lh"] + 1)
                    self.assertLessEqual(got["idW"], got["barW"] * 0.5 + 1)
                    self.assertFalse(got["overlap"])


if __name__ == "__main__":
    unittest.main()
