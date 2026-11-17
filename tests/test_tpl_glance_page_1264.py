"""Row 1264 slice 3: the glance template's View, low tiles at full width, in a real browser (1400 and 900 px, light and dark): the three
counting tiles and the bespoke ones, label on one line, no overflow, shape and tag word beside colour, border contrast read from the tokens.
Fictional data only. Every word the tests expect is an At a glance word that exists already or text typed into the fixture; the words of
the library card and of Edit are WORDS_PENDING (section_kinds/glancetemplate.py) and are not shown by this slice.

Run: python3 dev/run_tests.py test_tpl_glance_page_1264
"""
import json
import re
import unittest

from _demo import USER
from _paths import SRC
from test_report_editor import Base, tearDownModule  # noqa: F401
from test_server import chrome
from test_changes import KIND

TOKENS = (SRC / "clark" / "brand" / "tokens.css").read_text(encoding="utf-8")
SHELL = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
WORDS_PENDING = "[words pending]"        # the words of the library card and of Edit: not approved, never shown by this slice

SHAPES = {"g": "circle", "a": "triangle", "r": "square", "b": "diamond", "n": "ring"}
BESPOKE = [{"id": "b1", "label": "Fictional green", "figure": "7", "tag": "Fine", "note": "Fictional note one", "tone": "green"},
           {"id": "b2", "label": "Fictional amber", "figure": "2", "tag": "Careful", "note": "Fictional note two", "tone": "amber"},
           {"id": "b3", "label": "Fictional red", "figure": "9", "tag": "Late", "tone": "red"},
           {"id": "b4", "label": "Fictional blue", "figure": "1", "tag": "Info", "tone": "blue"},
           {"id": "b5", "label": "Fictional neutral", "figure": "4", "tone": "neutral"}]


def lum(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def tokens(mode):
    """The colour tokens of brand/tokens.css for `mode`: the light block, with the dark block laid over it for dark."""
    head, rest = TOKENS.split(":root[data-theme=dark] {", 1)
    light = dict(re.findall(r"(--[\w-]+):\s*(#[0-9A-Fa-f]{6})", head))
    if mode == "light":
        return light
    dark = rest.split("\n}", 1)[0]
    return {**light, **dict(re.findall(r"(--[\w-]+):\s*(#[0-9A-Fa-f]{6})", dark))}


def rule(selector):
    """The declarations of the first shell.css rule that starts with `selector`."""
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", SHELL)
    assert m, selector
    return m.group(1)


class Contrast(unittest.TestCase):
    """T57, T58: from the tokens, no browser."""

    EDGE = {"g": "--status-green", "a": "--status-amber-text", "r": "--status-red", "b": "--brand-blue", "n": "--grey-500"}
    TAG = {"g": "--status-green-text", "a": "--status-amber-text", "r": "--status-red-text", "b": "--brand-blue-strong", "n": "--text-muted"}

    def test_t57_every_tone_border_gives_3_to_1_and_every_tag_4_5_to_1_in_both_looks(self):
        for mode in ("light", "dark"):
            t = tokens(mode)
            surface = t["--surface"] if mode == "dark" else "#FFFFFF"
            for tone, name in self.EDGE.items():
                with self.subTest(mode=mode, tone=tone):
                    self.assertGreaterEqual(contrast(t[name], surface), 3.0, f"{name} border on {surface}")
                    self.assertGreaterEqual(contrast(t[self.TAG[tone]], surface), 4.5, f"{self.TAG[tone]} tag word on {surface}")

    def test_t57b_the_amber_border_is_the_text_token_because_the_plain_amber_fails(self):
        light = tokens("light")
        self.assertLess(contrast(light["--status-amber"], "#FFFFFF"), 3.0, "the plain amber token is the one that fails (2.22:1)")
        self.assertIn("--edge: var(--status-amber-text)", rule(".tpl-gt-tile.tone-a"))
        self.assertNotIn("var(--status-amber)", rule(".tpl-gt-tile.tone-a"))

    def test_t58_the_css_reads_tokens_only(self):
        css = "".join(rule(s) for s in (".tpl-gt", ".tpl-gt-tile", ".tpl-gt-k", ".tpl-gt-v", ".tpl-gt-tag", ".tpl-gt-note", ".tpl-gt-dot"))
        css += "".join(rule(f".tpl-gt-tile.tone-{c}") for c in "garb")
        self.assertIsNone(re.search(r"font-size:\s*\d", css), "no bare font size")
        self.assertIsNone(re.search(r"#[0-9A-Fa-f]{3,6}\b|rgb", css), "no colour value of its own")
        self.assertIn("font-size: var(--size-caption)", rule(".tpl-gt-k"))
        self.assertIn("white-space: nowrap", rule(".tpl-gt-k, .tpl-gt-tag, .tpl-gt-note"))
        self.assertRegex(SHELL, r"@media \(max-width: 900px\) \{ \.tpl-gt, \.tpl-gt\[data-cols=\"3\"\], \.slot-left \.tpl-gt, \.slot-right \.tpl-gt \{ grid-template-columns: minmax\(0, 1fr\); \} \}")


def seed_rows(test):
    """A counting tile is drawn only when its kind has rows (the published file's rule): one row of each kind."""
    test.demo.action(description="Fictional action for the glance tiles", due_date="2020-01-01")
    with test.store.step("dashboard", USER) as st:
        st.create("raid", {"project": "ABC", "type": "Risk", "description": "Fictional glance risk", "raised": "2026-10-01", "source": "demo",
                           "impact": "High", "likelihood": "High", "owner": "Pat Demo"})
        st.create("decisions", {"project": "ABC", "decision": "Fictional glance decision", "status": "Pending", "needed_by": "2031-02-01", "source": "demo"})


class Page(Base):
    """T51 to T56, T59 to T62."""

    def setUp(self):
        super().setUp()
        seed_rows(self)

    def make(self, body, title="Fictional glance template"):
        with self.store.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": "glancetemplate", "title": title, "sort_order": 999})
        status, got = self.real_change({"project": "ABC", "kind": KIND, "op": "update", "id": ref, "changes": {"body": json.dumps(body)}})
        assert status == 200, got
        return ref

    def look(self, ref, width, theme):
        """What the section draws, per tile, at `width` and `theme`; None when the section is not on the page."""
        with chrome() as cdp:
            p = self.visit(cdp)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
            p.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}")
            p.until("!!document.querySelector('#report .sec')", "the page")
            sec = f"document.querySelector('[data-id={json.dumps(ref)}]')"
            if not p.js(f"!!{sec}"):
                return None
            p.until(f"!!{sec}.querySelector('[data-gt]') || true", "drawn")
            return p.js(f"""(function(){{ var s = {sec}, g = s.querySelector('[data-gt]'); if (!g) return {{tiles: []}};
              var box = s.getBoundingClientRect(), gr = g.getBoundingClientRect();
              var tiles = [...g.querySelectorAll('.tpl-gt-tile')].map(function(t){{
                var k = t.querySelector('.tpl-gt-k'), dot = t.querySelector('.tpl-gt-dot'), tag = t.querySelector('.tpl-gt-tag'), note = t.querySelector('.tpl-gt-note'), v = t.querySelector('.tpl-gt-v');
                var r = t.getBoundingClientRect(), kr = k.getBoundingClientRect(), cs = getComputedStyle(t), dcs = getComputedStyle(dot);
                var lh = parseFloat(getComputedStyle(k).lineHeight) || kr.height;
                return {{key: t.dataset.tile, cls: t.className, label: k.textContent, figure: v && v.textContent, tag: tag && tag.textContent, note: note && note.textContent,
                         ws: getComputedStyle(k).whiteSpace, oneLine: kr.height <= lh * 1.5, clipped: k.scrollWidth > k.clientWidth,
                         left: r.left, right: r.right, top: r.top, width: r.width, height: r.height, border: cs.borderTopColor, borderW: cs.borderTopWidth,
                         shape: dcs.clipPath + '|' + dcs.borderRadius + '|' + dcs.backgroundColor + '|' + dcs.borderTopWidth, edge: cs.getPropertyValue('--edge').trim(),
                         bg: cs.backgroundColor, noteOne: note ? note.getBoundingClientRect().height <= (parseFloat(getComputedStyle(note).lineHeight) || 20) * 1.5 : true,
                         tagColor: tag && getComputedStyle(tag).color}}; }});
              return {{tiles: tiles, inside: gr.left >= box.left - 1 && gr.right <= box.right + 1, overflow: document.documentElement.scrollWidth > window.innerWidth,
                      sec: [box.left, box.right], text: s.textContent}}; }})()""")

    # T51
    def test_t51_the_three_counting_tiles_draw_in_order_with_the_words_that_exist(self):
        ref = self.make({"v": 1})
        got = self.look(ref, 1400, "light")
        self.assertEqual([t["key"] for t in got["tiles"]], ["overdue", "risks", "decisions"])
        self.assertEqual([t["label"] for t in got["tiles"]], ["Overdue actions", "High risks and issues", "Decisions needed"])
        for t in got["tiles"]:
            self.assertRegex(t["figure"], r"^\d+$")
            self.assertTrue(t["note"], "one note line")
            self.assertNotIn(WORDS_PENDING, t["label"] + t["note"])
        self.assertNotIn("words pending", got["text"].lower(), "no placeholder word reaches the page")

    # T52
    def test_t52_each_tile_has_a_dot_a_label_a_figure_a_tag_word_and_a_note_and_the_figure_matches_the_rows(self):
        ref = self.make({"v": 1})
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}] [data-gt]')", "the tiles")
            got = p.js(f"""[...document.querySelectorAll('[data-id={json.dumps(ref)}] .tpl-gt-tile')].map(t => [t.dataset.tile, t.querySelector('.tpl-gt-v').textContent,
                (t.querySelector('.tpl-gt-tag') || {{}}).textContent || '', !!t.querySelector('.tpl-gt-dot[aria-hidden=true]')])""")
            built = p.js("""Object.fromEntries([...document.querySelectorAll('[data-fig]')].map(f => [f.dataset.fig, (f.querySelector('.v') || {}).textContent]))""")
        for key, figure, tag, dot in got:
            self.assertTrue(dot, "a dot that a reader of the screen does not hear")
            if built.get(key) is not None:
                self.assertEqual(figure, built[key], f"{key}: the same figure as the At a glance section")
            self.assertIn(tag, {"", "Overdue", "Waiting", "Watch", "High", "On track", "At risk", "Off track"}, "an existing tag word")
        self.assertTrue(any(t for _, _, t, _ in got), "at least one tile says its state in a word")

    # T53
    def test_t53_colour_is_never_the_only_signal_every_tone_has_its_own_shape_and_a_tag_word(self):
        ref = self.make({"v": 1, "bespoke": BESPOKE, "builtin": {"overdue": {"hidden": True}, "risks": {"hidden": True}, "decisions": {"hidden": True}}})
        got = self.look(ref, 1400, "light")
        by = {t["key"]: t for t in got["tiles"]}
        shapes = {tone: by[key]["shape"] for tone, key in zip("garbn", ("b1", "b2", "b3", "b4", "b5"))}
        self.assertEqual(len(set(shapes.values())), 5, f"five tones, five shapes: {shapes}")
        self.assertTrue(shapes["g"].startswith("none|50%"), "green is a filled circle")
        self.assertTrue(shapes["r"].startswith("none|0px"), "red is a filled square")
        self.assertIn("2px", shapes["n"].split("|")[3], "neutral is a ring")
        for key in ("b1", "b2", "b3", "b4"):
            self.assertTrue(by[key]["tag"], f"{key}: a tag word beside the colour")
        self.assertEqual({k: by[k]["tag"] for k in ("b1", "b2", "b3", "b4")}, {"b1": "Fine", "b2": "Careful", "b3": "Late", "b4": "Info"})
        self.assertIn("polygon", shapes["a"])
        self.assertIn("polygon", shapes["b"])
        self.assertEqual(SHAPES.keys(), set("garbn"))

    # T54
    def test_t54_the_label_never_wraps_at_1400_or_900_light_or_dark(self):
        ref = self.make({"v": 1, "bespoke": [{"id": "b1", "label": "Fictional tile with a longer label here", "figure": "3", "tag": "Careful", "note": "Fictional note", "tone": "amber"}]})
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme):
                    got = self.look(ref, width, theme)
                    self.assertEqual(len(got["tiles"]), 4)
                    for t in got["tiles"]:
                        self.assertEqual(t["ws"], "nowrap", t["key"])
                        self.assertTrue(t["oneLine"], f"{t['key']}: one line")
                        self.assertTrue(t["noteOne"], f"{t['key']}: the note is one line")
                    for t in got["tiles"][:3]:
                        self.assertFalse(t["clipped"], f"{t['label']}: a built-in label is whole, not cut")

    # T55
    def test_t55_nothing_overflows_at_1400_and_900_light_and_dark(self):
        ref = self.make({"v": 1, "bespoke": BESPOKE})
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme):
                    got = self.look(ref, width, theme)
                    self.assertFalse(got["overflow"], "no sideways scroll")
                    self.assertTrue(got["inside"], "the tiles sit inside the section")
                    for t in got["tiles"]:
                        self.assertTrue(got["sec"][0] - 1 <= t["left"] and t["right"] <= got["sec"][1] + 1, f"{t['key']} inside the section")

    # T56
    def test_t56_at_1400_the_tiles_share_a_line_and_at_900_each_takes_the_full_width(self):
        ref = self.make({"v": 1})
        wide = self.look(ref, 1400, "light")["tiles"]
        self.assertEqual(len({round(t["top"]) for t in wide}), 1, "three low tiles on one line at 1400")
        narrow = self.look(ref, 900, "light")["tiles"]
        self.assertEqual(len({round(t["top"]) for t in narrow}), 3, "one tile per line at 900")
        self.assertEqual(len({round(t["width"]) for t in narrow}), 1, "all the same width")

    # T57, in the browser: the border drawn is the token read from the CSS
    def test_t57c_the_border_drawn_is_the_token_in_light_and_in_dark(self):
        ref = self.make({"v": 1, "bespoke": BESPOKE})
        for theme in ("light", "dark"):
            got = self.look(ref, 1400, theme)
            by = {t["key"]: t for t in got["tiles"]}
            tk = tokens(theme)
            for key, name in (("b1", "--status-green"), ("b2", "--status-amber-text"), ("b3", "--status-red"), ("b4", "--brand-blue"), ("b5", "--grey-500")):
                with self.subTest(theme=theme, tile=key):
                    h = tk[name].lstrip("#")
                    self.assertEqual(by[key]["border"], f"rgb({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)})")
                    self.assertEqual(by[key]["borderW"], "2px")

    # T59
    def test_t59_a_hidden_counting_tile_is_left_out_and_the_order_and_the_outline_are_followed(self):
        ref = self.make({"v": 1, "order": ["decisions", "overdue"], "builtin": {"risks": {"hidden": True}, "decisions": {"outline": "R"}}})
        got = self.look(ref, 1400, "light")
        self.assertEqual([t["key"] for t in got["tiles"]], ["decisions", "overdue"])
        self.assertIn("tone-r", got["tiles"][0]["cls"], "the outline set by hand shows")
        self.assertNotIn("High risks and issues", got["text"])

    # T60
    def test_t60_bespoke_tiles_follow_the_counting_ones_and_a_hidden_one_is_not_on_the_page(self):
        ref = self.make({"v": 1, "bespoke": [BESPOKE[0], {**BESPOKE[1], "hidden": True}, BESPOKE[2]]})
        got = self.look(ref, 1400, "light")
        self.assertEqual([t["key"] for t in got["tiles"]], ["overdue", "risks", "decisions", "b1", "b3"])
        self.assertNotIn("Fictional amber", got["text"])
        self.assertNotIn("Fictional note two", got["text"])

    # T61
    def test_t61_a_section_with_every_tile_hidden_is_left_out_of_the_page(self):
        ref = self.make({"v": 1, "builtin": {"overdue": {"hidden": True}, "risks": {"hidden": True}, "decisions": {"hidden": True}},
                         "bespoke": [{**BESPOKE[0], "hidden": True}]})
        self.assertIsNone(self.look(ref, 1400, "light"), "no tile to show: no section")

    # T62
    def test_t62_a_label_of_the_longest_length_stays_on_one_line_inside_the_tile_at_900(self):
        longest = "Fictional label of forty characters ok!!"
        self.assertEqual(len(longest), 40)
        ref = self.make({"v": 1, "bespoke": [{"id": "b1", "label": longest, "figure": "123456789012", "tag": "Twelve words", "note": "n" * 60, "tone": "red"}]})
        for theme in ("light", "dark"):
            got = self.look(ref, 900, theme)
            t = got["tiles"][-1]
            self.assertEqual(t["label"], longest)
            self.assertTrue(t["oneLine"] and t["noteOne"])
            self.assertFalse(got["overflow"])
            self.assertTrue(got["sec"][0] - 1 <= t["left"] and t["right"] <= got["sec"][1] + 1)


if __name__ == "__main__":
    unittest.main()
