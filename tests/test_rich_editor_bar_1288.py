"""Row 1288: the Classic rich editor draws the approved mock-up's toolbar and bubble (computed style, 1400 and 900, light and dark).

Run: python3 dev/run_tests.py test_rich_editor_bar_1288
Toolbar: Quote and Divider are ONE drop-down button after the checklist (the mock-up's 1C), not two buttons. Bubble: its last button reads
"Ask AI" with an ellipsis and its words are purple (the mock-up draws only the words purple; light is the mock-up's value, dark is the lightened one).
Cards (no #theme layer) keeps its two buttons and the words "Draft with AI": proved in the same run.
Chrome is required: the test fails, never skips, without it.
"""
import json
import unittest

from _paths import ROOT

import _rich_page as rp  # noqa: E402
from clark import theme  # noqa: E402
from test_server import chrome  # noqa: E402

CSS = theme.css("prototype-2.0")
LOOKS = [(1400, "light"), (1400, "dark"), (900, "light"), (900, "dark")]
PURPLE = {"light": "rgb(70, 53, 184)", "dark": "rgb(158, 123, 255)"}


def layer(h, on):
    h.ev("var o = document.getElementById('theme'); if (o) o.remove(); true")
    if on:
        h.ev(f"var s = document.createElement('style'); s.id = 'theme'; s.textContent = {json.dumps(CSS)}; document.head.appendChild(s); true")


def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    l = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * l[0] + 0.7152 * l[1] + 0.0722 * l[2]


def ratio(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


class Contrast(unittest.TestCase):
    """The Ask AI words read on their panel at 4.5 to 1, light and dark (dark is not drawn: the dark value is the light hue lightened until it does)."""

    def test_ask_ai_reads_on_the_panel_in_light_and_both_dark_blocks(self):
        import re
        tokens = (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "tokens.css").read_text(encoding="utf-8")
        light = re.search(r"^:root \{(.*?)^\}", tokens, re.S | re.M).group(1)
        darks = re.findall(r":root\[data-theme=(?:dark|auto)\]\s*\{(.*?)\n\s*\}", tokens, re.S)
        get = lambda b, n: re.search(re.escape(n) + r":\s*(#[0-9A-Fa-f]{6})", b).group(1).upper()
        self.assertGreaterEqual(ratio(get(light, "--ai-fg"), "#FFFFFF"), 4.5)
        self.assertEqual(len(darks), 2)
        for b in darks:
            self.assertGreaterEqual(ratio(get(b, "--ai-fg"), get(b, "--surface")), 4.5)


class Bar(unittest.TestCase):
    def open(self, h, classic, w, th):
        layer(h, classic)
        h.resize(w)
        h.theme(th)
        h.mount("<p>Some words here</p>", ai="current")

    def test_classic_has_one_more_blocks_button_and_cards_keeps_two(self):
        with rp.Harness(chrome) as h:
            for classic in (True, False):
                for w, th in LOOKS:
                    self.open(h, classic, w, th)
                    names = h.ev("[...document.querySelectorAll('.rt-bar .rt-btn')].map(b => b.getAttribute('aria-label') || b.textContent)")
                    where = f"classic={classic} {w} {th}: {names}"
                    if classic:
                        self.assertNotIn("Quote", names, where)
                        self.assertNotIn("Divider", names, where)
                        i = names.index("Checklist")
                        self.assertEqual(names[i + 1], "More blocks: Quote, Divider", where)
                        box = h.ev("(b => { const r = b.getBoundingClientRect(); return [r.width, r.height]; })(document.querySelector('.rt-bar .rt-more'))")
                        self.assertGreaterEqual(box[0], 40, where)
                        self.assertEqual(h.ev("document.querySelector('.rt-bar .rt-more').title"), "More blocks: Quote, Divider", where)   # the aria-label AND the tooltip
                    else:
                        self.assertIn("Quote", names, where)
                        self.assertIn("Divider", names, where)
                        self.assertFalse(h.ev("!!document.querySelector('.rt-bar .rt-more')"), where)

    def test_a_one_line_editor_draws_no_more_button_and_a_normal_one_does(self):
        with rp.Harness(chrome) as h:
            for w, th in LOOKS[::2]:
                layer(h, True)
                h.resize(w)
                h.theme(th)
                where = f"{w} {th}"
                h.mount("<p>Some words here</p>", ai="current", one_line=True)
                self.assertTrue(h.until("!!document.querySelector('.rt-bar')"), where)
                self.assertFalse(h.ev("!!document.querySelector('.rt-bar .rt-more')"), "oneLine " + where)
                h.mount("<p>Some words here</p>", ai="current")
                self.assertTrue(h.ev("!!document.querySelector('.rt-bar .rt-more')"), "normal " + where)

    def test_undo_in_a_one_line_editor_does_not_bring_the_old_paragraphs_back(self):
        """Row 1288 (review): an old several-paragraph text shows joined on one line; that join is not an edit, so Undo before any edit has nothing to undo."""
        with rp.Harness(chrome) as h:
            h.mount("<p>First part</p><p>Second part</p>", ai="current", one_line=True)
            self.assertEqual(h.ev("[...document.querySelectorAll('.rt-host .ProseMirror p')].map(p => p.textContent)"), ["First part Second part"])
            h.key("z", h.mod, "KeyZ", 90)
            h.ev("new Promise(r => setTimeout(r, 300))")
            self.assertEqual(h.ev("[...document.querySelectorAll('.rt-host .ProseMirror p')].map(p => p.textContent)"), ["First part Second part"], "Undo leaves the joined line")
            h.type("!")
            h.key("z", h.mod, "KeyZ", 90)
            self.assertTrue(h.until("document.querySelector('.rt-host .ProseMirror').textContent === 'First part Second part'"), "a later edit is still undone")

    def test_the_drop_down_lists_quote_and_divider_and_quote_works(self):
        with rp.Harness(chrome) as h:
            self.open(h, True, 1400, "light")
            h.ev("document.querySelector('.rt-bar .rt-more').click(); true")
            self.assertTrue(h.until("document.querySelectorAll('.rt-bar [role=menu] [role=menuitem]').length === 2"))
            self.assertEqual(h.ev("[...document.querySelectorAll('.rt-bar [role=menu] [role=menuitem]')].map(b => b.textContent.trim())"), ["Quote", "Divider"])
            h.ev("document.querySelectorAll('.rt-bar [role=menu] [role=menuitem]')[0].click(); true")
            self.assertTrue(h.until("!!document.querySelector('.rt-host blockquote')"))

    def test_the_bubble_ends_with_purple_ask_ai(self):
        with rp.Harness(chrome) as h:
            for classic in (True, False):
                for w, th in LOOKS:
                    self.open(h, classic, w, th)
                    h.select_all()
                    self.assertTrue(h.until("!!document.querySelector('.rt-bubble [data-rt-bubble-ai]')"))
                    got = h.ev("(b => ({t: b.textContent, c: getComputedStyle(b).color, last: b === b.parentNode.lastElementChild}))(document.querySelector('.rt-bubble [data-rt-bubble-ai]'))")
                    where = f"classic={classic} {w} {th}: {got}"
                    self.assertTrue(got["last"], where)
                    if classic:
                        self.assertEqual(got["t"], "Ask AI…", where)
                        self.assertEqual(got["c"], PURPLE[th], where)
                    else:
                        self.assertEqual(got["t"], "Draft with AI", where)
                        self.assertNotIn(got["c"], PURPLE.values(), where)


if __name__ == "__main__":
    unittest.main()
