"""Row 1264 slice 3: the glance template's View, low tiles at full width, in a real browser (1400 and 900 px, light and dark): the three
counting tiles and the bespoke ones, the look of the approved v2 mock-up (one fixed width, left aligned, the At a glance tile with a fading
edge, label and note that wrap), no overflow, shape and tag word beside colour, edge contrast read from the tokens, breakpoint 760.
Fictional data only. Every word the tests expect is an At a glance word that exists already or text typed into the fixture; the words of
the library card and of Edit are not approved yet and are not shown by this slice.

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
PLACEHOLDER = "[words pending]"        # the words of the library card and of Edit: not approved, never shown by this slice

# the shapes of the approved mock-up (v2: SH): Red is a DIAMOND, Blue a rounded SQUARE, Green a circle, Amber a triangle, Neutral a ring
SHAPES = {"g": "circle", "a": "triangle", "r": "diamond", "b": "square", "n": "ring"}
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

    EDGE = {"g": "--status-green", "a": "--status-amber-text", "r": "--status-red", "b": "--brand-blue"}      # Neutral has no coloured edge
    TAG = {"g": "--status-green-text", "a": "--status-amber-text", "r": "--status-red-text", "b": "--brand-blue-strong", "n": "--text-muted"}

    def test_t57_every_tone_border_gives_3_to_1_and_every_tag_4_5_to_1_in_both_looks(self):
        for mode in ("light", "dark"):
            t = tokens(mode)
            surface = t["--surface"] if mode == "dark" else "#FFFFFF"
            for tone, name in self.EDGE.items():
                with self.subTest(mode=mode, tone=tone):
                    self.assertGreaterEqual(contrast(t[name], surface), 3.0, f"{name} edge on {surface}")
            for tone, name in self.TAG.items():
                with self.subTest(mode=mode, tone=tone, part="tag"):
                    self.assertGreaterEqual(contrast(t[name], surface), 4.5, f"{name} tag word on {surface}")

    def test_t57b_the_amber_border_is_the_text_token_because_the_plain_amber_fails(self):
        light = tokens("light")
        self.assertLess(contrast(light["--status-amber"], "#FFFFFF"), 3.0, "the plain amber token is the one that fails (2.22:1)")
        self.assertIn("--edge: var(--status-amber-text)", rule(".tpl-gt-tile.tone-a"))
        self.assertNotIn("var(--status-amber)", rule(".tpl-gt-tile.tone-a"))

    def test_t58_the_css_reads_tokens_only(self):
        css = "".join(rule(s) for s in (".tpl-gt", ".tpl-gt-tile", ".tpl-gt-tile::after", ".tpl-gt-dot", ".tpl-gt-k, .tpl-gt-note", ".tpl-gt-tile .tpl-gt-tag"))
        css += "".join(rule(f".tpl-gt-tile.tone-{c}") for c in "garb") + "".join(rule(f".tone-{c} .tpl-gt-dot") for c in "garbn")
        self.assertIsNone(re.search(r"font-size:\s*\d", css), "no bare font size")
        self.assertIsNone(re.search(r"#[0-9A-Fa-f]{3,6}\b|rgb", css), "no colour value of its own")
        self.assertIn("white-space: normal", rule(".tpl-gt-k, .tpl-gt-note"))
        self.assertNotIn("nowrap", rule(".tpl-gt-k, .tpl-gt-note"))
        self.assertNotIn("ellipsis", SHELL[SHELL.index(".tpl-gt {"):SHELL.index(".tpl-gt-tile .tpl-gt-tag")])
        self.assertIn("--shape: var(--icon-grey)", rule(".tpl-gt-tile"), "the neutral ring is --icon-grey (= --grey-700)")
        self.assertIn("--tag: var(--text-muted)", rule(".tpl-gt-tile"))
        self.assertIn("--edge: transparent", rule(".tpl-gt-tile"), "neutral: no coloured edge")
        self.assertRegex(SHELL, r"@media \(max-width: 760px\) \{ \.tpl-gt-tile \{ flex-basis: 100%; \} \}")
        self.assertNotIn("900px) { .tpl-gt", SHELL, "no 900 rule: the mock-up has the one breakpoint, 760")
        self.assertIn("calc((100% - (var(--cols) - 1) * var(--space-3)) / var(--cols))", rule(".tpl-gt-tile"))
        self.assertIn("--cols: 4", rule(".tpl-gt"))


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
            p.until("document.getAnimations().length === 0", "the colour change of a counting tile (a button with a hover transition) is over")
            return p.js(f"""(function(){{ var s = {sec}, g = s.querySelector('[data-gt]'); if (!g) return {{tiles: []}};
              var box = s.getBoundingClientRect(), gr = g.getBoundingClientRect();
              var tiles = [...g.querySelectorAll('.tpl-gt-tile')].map(function(t){{
                var k = t.querySelector('.tpl-gt-k'), dot = t.querySelector('.tpl-gt-dot'), tag = t.querySelector('.tpl-gt-tag'), note = t.querySelector('.tpl-gt-note'), v = t.querySelector('.tpl-gt-v');
                var r = t.getBoundingClientRect(), kr = k.getBoundingClientRect(), cs = getComputedStyle(t), dcs = getComputedStyle(dot), acs = getComputedStyle(t, '::after');
                var lh = parseFloat(getComputedStyle(k).lineHeight) || kr.height;
                return {{key: t.dataset.tile, cls: t.className, label: k.textContent, figure: v && v.textContent, tag: tag && tag.textContent, note: note && note.textContent,
                         ws: getComputedStyle(k).whiteSpace, oneLine: kr.height <= lh * 1.5, clipped: k.scrollWidth > k.clientWidth, lines: Math.round(kr.height / lh), kBottom: kr.bottom, bottom: r.bottom,
                         ellipsis: getComputedStyle(k).textOverflow, noteWs: note ? getComputedStyle(note).whiteSpace : null, vrow: !!t.querySelector('.vrow'),
                         edgeColor: acs.borderTopColor, edgeW: acs.borderTopWidth, tagRight: tag ? tag.getBoundingClientRect().right : null, vRight: v ? v.getBoundingClientRect().right : null,
                         dotLeft: dot.getBoundingClientRect().left, noteTop: note ? note.getBoundingClientRect().top : null, vBottom: v ? v.getBoundingClientRect().bottom : null,
                         dotColor: dcs.backgroundColor, ringColor: dcs.borderTopColor,
                         left: r.left, right: r.right, top: r.top, width: r.width, height: r.height, border: cs.borderTopColor, borderW: cs.borderTopWidth,
                         shape: dcs.clipPath + '|' + dcs.borderRadius + '|' + dcs.backgroundColor + '|' + dcs.borderTopWidth, edge: cs.getPropertyValue('--edge').trim(),
                         bg: cs.backgroundColor, noteOne: note ? note.getBoundingClientRect().height <= (parseFloat(getComputedStyle(note).lineHeight) || 20) * 1.5 : true,
                         tagColor: tag && getComputedStyle(tag).color}}; }});
              return {{tiles: tiles, inside: gr.left >= box.left - 1 && gr.right <= box.right + 1, overflow: document.documentElement.scrollWidth > window.innerWidth,
                      sec: [box.left, box.right], gt: gr.width, gtLeft: gr.left, text: s.textContent}}; }})()""")

    # T51
    def test_t51_the_three_counting_tiles_draw_in_order_with_the_words_that_exist(self):
        ref = self.make({"v": 1})
        got = self.look(ref, 1400, "light")
        self.assertEqual([t["key"] for t in got["tiles"]], ["overdue", "risks", "decisions"])
        self.assertEqual([t["label"] for t in got["tiles"]], ["Overdue actions", "High risks and issues", "Decisions needed"])
        for t in got["tiles"]:
            self.assertRegex(t["figure"], r"^\d+$")
            self.assertTrue(t["note"], "one note line")
            self.assertNotIn(PLACEHOLDER, t["label"] + t["note"])
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
        self.assertTrue(shapes["b"].startswith("none|2px"), "blue is a filled rounded square")
        self.assertIn("2px", shapes["n"].split("|")[3], "neutral is a ring")
        for key in ("b1", "b2", "b3", "b4"):
            self.assertTrue(by[key]["tag"], f"{key}: a tag word beside the colour")
        self.assertEqual({k: by[k]["tag"] for k in ("b1", "b2", "b3", "b4")}, {"b1": "Fine", "b2": "Careful", "b3": "Late", "b4": "Info"})
        self.assertIn("polygon(50% 0px, 100% 100%, 0px 100%)", shapes["a"], "amber is a triangle")
        self.assertIn("polygon(50% 0px, 100% 50%, 50% 100%, 0px 50%)", shapes["r"], "red is a diamond")
        self.assertEqual(SHAPES.keys(), set("garbn"))

    # T54
    def test_t54_the_label_and_the_note_wrap_and_are_never_cut_at_1400_or_900_light_or_dark(self):
        long = "Fictional tile with a longer label here"
        ref = self.make({"v": 1, "bespoke": [{"id": "b1", "label": long, "figure": "3", "tag": "Careful", "note": "Fictional note with words that go on for quite a while", "tone": "amber"}]})
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme):
                    got = self.look(ref, width, theme)
                    self.assertEqual(len(got["tiles"]), 4)
                    for t in got["tiles"]:
                        self.assertEqual(t["ws"], "normal", t["key"])
                        self.assertFalse(t["clipped"], f"{t['label']}: the label is whole, not cut")
                        self.assertNotEqual(t["ellipsis"], "ellipsis")
                        self.assertLessEqual(t["kBottom"], t["bottom"], "the label stays inside its tile")
                    last = got["tiles"][-1]
                    self.assertEqual(last["label"], long)
                    self.assertGreaterEqual(last["lines"], 2 if width == 900 else 1)
                    self.assertEqual(last["noteWs"], "normal")
                    self.assertFalse(last["noteOne"], "a long note wraps to a second line")

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
    def test_t56_every_tile_is_one_fixed_width_left_aligned_four_to_a_line_and_the_last_line_does_not_stretch(self):
        ref = self.make({"v": 1, "health": {"shown": False}, "bespoke": BESPOKE[:3]})        # 3 counting + 3 bespoke = 6 tiles (Project health off: it takes a place of its own)
        for width in (1400, 900):
            with self.subTest(width=width):
                got = self.look(ref, width, "light")
                tiles = got["tiles"]
                self.assertEqual(len(tiles), 6)
                want = (got["gt"] - 3 * 12) / 4
                for t in tiles:
                    self.assertAlmostEqual(t["width"], want, delta=1.5, msg=f"{t['key']}: a quarter of the line, whatever its text")
                tops = sorted({round(t["top"]) for t in tiles})
                self.assertEqual(len(tops), 2, "four on the first line, two on the second")
                line2 = [t for t in tiles if round(t["top"]) == tops[1]]
                self.assertEqual(len(line2), 2)
                self.assertAlmostEqual(line2[0]["left"], tiles[0]["left"], delta=1, msg="the last line starts at the left")
                self.assertAlmostEqual(tiles[0]["left"], got["gtLeft"], delta=1, msg="left aligned")
                self.assertAlmostEqual(line2[1]["left"], tiles[1]["left"], delta=1, msg="the last line does not stretch")
                self.assertAlmostEqual(line2[1]["right"], tiles[1]["right"], delta=1)
                line1 = [t for t in tiles if round(t["top"]) == tops[0]]
                self.assertEqual({round(t["height"]) for t in line1}, {round(line1[0]["height"])}, "a line is as high as its highest tile")

    def test_t56b_the_only_breakpoint_is_760_one_tile_per_line_at_759_and_760_not_at_761_or_900(self):
        ref = self.make({"v": 1})
        for width in (900, 761):
            with self.subTest(width=width):
                got = self.look(ref, width, "light")["tiles"]
                self.assertEqual(len({round(t["top"]) for t in got}), 1, "the three counting tiles stay on one line")
        for width in (760, 759):
            with self.subTest(width=width):
                got = self.look(ref, width, "light")["tiles"]
                self.assertEqual(len({round(t["top"]) for t in got}), 3, "one tile per line")
                self.assertEqual(len({round(t["width"]) for t in got}), 1, "all the same width")
                self.assertEqual(len({round(t["left"]) for t in got}), 1)

    # T57, in the browser: the border drawn is the token read from the CSS
    def test_t57c_the_border_drawn_is_the_token_in_light_and_in_dark(self):
        ref = self.make({"v": 1, "bespoke": BESPOKE})
        for theme in ("light", "dark"):
            got = self.look(ref, 1400, theme)
            by = {t["key"]: t for t in got["tiles"]}
            tk = tokens(theme)
            def rgb(name):
                h = tk[name].lstrip("#")
                return f"rgb({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)})"
            for key, name in (("b1", "--status-green"), ("b2", "--status-amber-text"), ("b3", "--status-red"), ("b4", "--brand-blue")):
                with self.subTest(theme=theme, tile=key):
                    self.assertEqual(by[key]["edgeColor"], rgb(name), "the 2 px edge is the tone token")
                    self.assertEqual(by[key]["edgeW"], "2px")
            for key in by:
                self.assertEqual(by[key]["border"], rgb("--grey-200"), "the border is the grey-200 line of the At a glance tile")
                self.assertEqual(by[key]["borderW"], "1px")
            self.assertEqual(by["b5"]["edgeColor"], "rgba(0, 0, 0, 0)", "neutral: no coloured edge")
            self.assertEqual(by["b5"]["ringColor"], rgb("--grey-700"), "the neutral ring is --icon-grey = --grey-700")
            self.assertEqual(by["b3"]["dotColor"], rgb("--status-red"))

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

    def test_t61_a_section_with_every_tile_hidden_shows_the_mock_up_sentence(self):
        ref = self.make({"v": 1, "builtin": {"overdue": {"hidden": True}, "risks": {"hidden": True}, "decisions": {"hidden": True}},
                         "bespoke": [{**BESPOKE[0], "hidden": True}]})
        got = self.look(ref, 1400, "light")
        self.assertEqual(got["tiles"], [], "no tile is drawn; the sentence is test_tpl_glance_b4_1264")
        self.assertIn("No tiles on this section.", got["text"])

    # T62
    def test_t62_a_label_of_the_longest_length_wraps_inside_the_tile_at_900(self):
        longest = "Fictional label of forty characters ok!!"
        self.assertEqual(len(longest), 40)
        ref = self.make({"v": 1, "bespoke": [{"id": "b1", "label": longest, "figure": "123456789012", "tag": "Twelve words", "note": "n" * 60, "tone": "red"}]})
        for theme in ("light", "dark"):
            got = self.look(ref, 900, theme)
            t = got["tiles"][-1]
            self.assertEqual(t["label"], longest)
            self.assertGreaterEqual(t["lines"], 2, "a 40 character label in a quarter tile wraps")
            self.assertFalse(t["clipped"])
            self.assertLessEqual(t["kBottom"], t["bottom"])
            self.assertFalse(got["overflow"])
            self.assertTrue(got["sec"][0] - 1 <= t["left"] and t["right"] <= got["sec"][1] + 1)

    # A3: the At a glance layout inside the tile
    def test_t63_the_tile_is_a_column_label_row_with_the_dot_then_the_figure_with_the_tag_at_the_right_then_the_note(self):
        ref = self.make({"v": 1, "bespoke": BESPOKE[:1]})
        t = {x["key"]: x for x in self.look(ref, 1400, "light")["tiles"]}["b1"]
        self.assertTrue(t["vrow"])
        self.assertLess(t["vBottom"] - 1, t["noteTop"], "the note is below the figure row")
        self.assertGreater(t["tagRight"], t["vRight"] + 40, "the tag word is pushed to the right")
        self.assertAlmostEqual(t["tagRight"], t["right"] - 16, delta=2, msg="to the tile's right padding")
        self.assertGreater(t["height"], 90, "the 289 x 102 look, not the 65 px low tile")

if __name__ == "__main__":
    unittest.main()
