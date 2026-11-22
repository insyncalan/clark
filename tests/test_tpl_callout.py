"""#96 G5, Callout: the content rules (section_kinds/callout.py), the file, and the page's View and Edit parts.
Run: python3 dev/run_tests.py test_tpl_callout
Needs Chrome (the #33 harness): the page tests fail, never skip, without it. Fictional data only.
"""
from _classic_page import classic
import json
import unittest

import _tpl_notes as n
from test_server import chrome

GOOD = {"v": 1, "tone": "decision", "title": "Fictional decision", "paras": ["Fictional words about the budget.", "A second fictional line."]}
HOSTILE = {"v": 1, "tone": "warning", "title": n.HOSTILE, "paras": [n.HOSTILE]}


class Data(n.DataChecks):
    TYPE, GOOD, WORDS, HOSTILE_BODY = "callout", GOOD, "Fictional words about the budget.", HOSTILE
    LIMIT_BODY = {"v": 1, "title": "x" * 121}
    BAD = ({"v": 1, "tone": "loud"}, {"v": 1, "title": 5}, {"v": 1, "paras": "one"}, {"v": 1, "paras": [{"a": 1}]},
           {"v": 1, "paras": ["x"] * 7}, {"v": 1, "paras": ["x" * 601]},
           {"v": 1, "category": "x" * 31}, {"v": 1, "category": 5}, {"v": 1, "colour": "pink"}, {"v": 1, "icon": "emoji"}, {"v": 1, "tile": "yes"}, {"v": 1, "heading": 1})

    def test_the_tone_and_empty_paragraphs(self):
        ref = self.section()
        self.write(ref, {"v": 1, "title": "Fictional", "paras": ["", "  ", "Kept"]})
        self.assertEqual(json.loads(self.stored(ref)), {"paras": ["Kept"], "title": "Fictional", "tone": "info", "v": 1})

    def test_the_new_fields_are_kept_and_an_older_callout_is_unchanged(self):
        ref = self.section()
        self.write(ref, GOOD)
        self.assertEqual(json.loads(self.stored(ref)), {"v": 1, "tone": "decision", "title": "Fictional decision", "paras": GOOD["paras"]})
        self.write(ref, {**GOOD, "category": " Budget ", "colour": "green", "icon": "none", "tile": False, "heading": True})
        got = json.loads(self.stored(ref))
        self.assertEqual((got["category"], got["colour"], got["icon"], got["tile"], got["heading"]), ("Budget", "green", "none", False, True))

    def test_the_file_says_the_category_colour_and_icon_in_words(self):
        ref = self.section()
        self.write(ref, {**GOOD, "category": "Budget", "colour": "violet", "icon": "bulb"})
        c = self.file_sections()[ref]["content"]
        self.assertEqual((c["category"], c["colour_name"], c["icon_name"]), ("Budget", "Violet", "Light bulb"))
        self.write(ref, GOOD)                       # an older callout: the colour and icon its tone drew
        c = self.file_sections()[ref]["content"]
        self.assertEqual((c["category"], c["colour_name"], c["icon_name"], c["tile"], c["heading"]), ("Decision needed", "Amber", "Question", True, True), "an older callout keeps its tone word in the file")

    def test_a_tone_alone_is_not_content(self):
        ref = self.section()
        self.write(ref, {"v": 1, "tone": "warning"})
        self.assertNotIn(ref, self.file_sections())


NEW_ICON_NAMES = ("Lightning", "Eye", "Table", "Gear", "Sparkle", "Two ways", "Warning triangle")


class Words(unittest.TestCase):
    """The named lists and defaults themselves (mutation check): every colour and icon, the tone looks, words() alone."""

    def test_every_colour_and_icon_is_named_and_the_tone_looks_are_kept(self):
        from clark.section_kinds import callout
        self.assertEqual(tuple(callout.COLOURS), ("plain", "violet", "amber", "red", "green", "grey"))
        self.assertEqual(len(callout.ICONS), 27)
        self.assertIn("shield", callout.ICONS)
        self.assertEqual(callout.ICONS["warning"], "Warning triangle")
        self.assertNotIn("warn", callout.ICONS)
        self.assertEqual(callout.COLOURS["grey"], "Grey")
        self.assertEqual(callout.TONE_LOOK, {"info": ("violet", "info"), "decision": ("amber", "question"), "warning": ("red", "warning")})
        self.assertEqual(callout.upgrade({"v": 1, "tone": "warning"}),
                         {"v": 1, "tone": "warning", "category": "Warning", "colour": "red", "icon": "warning", "tile": True, "heading": True})

    def test_the_decision_suggestion_icon_is_fork_named_two_ways_and_the_warning_icon_is_named_warning_triangle(self):
        from pathlib import Path
        from clark.section_kinds import callout
        self.assertEqual(callout.words({"v": 1, "icon": "fork"})["icon_name"], "Two ways")
        self.assertEqual(callout.words({"v": 1, "icon": "warning"})["icon_name"], "Warning triangle")
        self.assertNotIn("twoways", callout.ICONS)
        jsx = (Path(callout.__file__).parent.parent / "page" / "src" / "edit" / "templates" / "Callout.jsx").read_text(encoding="utf-8")
        self.assertIn('decision: ["amber", "fork"]', jsx)

    def test_words_alone_carries_the_category_colour_and_icon(self):
        from clark.section_kinds import callout
        self.assertEqual(callout.words({"v": 1, "tone": "warning", "category": "Budget", "colour": "grey", "icon": "shield"}),
                         {"category": "Budget", "colour_name": "Grey", "icon_name": "Shield"})
        self.assertEqual(callout.words({"v": 1, "icon": "none", "colour": "plain"}), {"category": "", "colour_name": "Plain", "icon_name": ""})


class Look(unittest.TestCase):
    """The callout's rules in shell.css (the page and the published file share them): a tinted box, never a stripe; Plain has no box."""

    def rules(self):
        from _paths import ROOT
        css = (ROOT / "src/clark/page/shell.css").read_text(encoding="utf-8")
        return [line for line in css.splitlines() if line.startswith(".tpl-callout")]

    def test_no_callout_rule_draws_a_stripe_or_a_bare_pixel_or_colour(self):
        import re
        rules = self.rules()
        self.assertGreater(len(rules), 6)
        for line in rules:
            self.assertNotRegex(line, r"border-(left|inline-start)", line)
            self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(", line), line)

    def test_plain_has_no_box(self):
        plain = [line for line in self.rules() if ".k-plain" in line]
        self.assertEqual(len(plain), 1)
        self.assertIn("--cc-fill: transparent", plain[0])
        self.assertIn("--cc-edge: transparent", plain[0])


class Page(n.PageChecks):
    TYPE, GOOD, HOSTILE_BODY = "callout", GOOD, HOSTILE
    SHOWS = ("Decision needed", "Fictional decision", "Fictional words about the budget.", "A second fictional line.")
    FIELD, TYPED = "Callout title", "Fictional new title"
    CHANGED = lambda self, body: json.loads(body)["title"] == "Fictional new title"

    def test_an_empty_one_shows_the_starting_text_and_keeps_the_empty_for_now_line(self):
        classic(self)          # the starting text is a Classic look; Cards keeps its old words
        ref = self.make(None)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}] .tpl-edit')", "Edit shows the fields")
            shown = p.js(f"document.querySelector('[data-id={json.dumps(ref)}] .tpl-edit').textContent + ' ' + [...document.querySelectorAll('[data-id={json.dumps(ref)}] .tpl-edit [placeholder]')].map(e => e.getAttribute('placeholder')).join(' ')")
            self.assertIn('Write the one thing the reader must see.', shown)
            self.assertIn('Empty for now: add a title or some words. It stays out of the published page until then.', shown)

    def test_the_tone_is_a_word_and_not_colour_alone(self):
        ref = self.make(self.GOOD)
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertEqual(p.js(f"document.querySelector('[data-id={json.dumps(ref)}] .tpl-callout-tone').textContent"), "Decision needed")
            self.assertEqual(p.js(f"document.querySelector('[data-id={json.dumps(ref)}] .tpl-callout').getAttribute('role')"), "note")

    def test_two_quick_saves_both_keep_their_words(self):
        ref = self.make(self.GOOD)
        n.slow_saves(self)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}] [data-rich=callout]')", "the fields")
            n.fill(p, n.field_js(ref, "Callout title"), "Fictional first title")
            # the words are the one editor (row 1005): typed in it and saved with Cmd or Ctrl+Enter while the title's save is still in flight
            sec = f"[data-id={json.dumps(ref)}]"
            p.js(f"document.querySelector('{sec} [data-rich]').click()")
            p.until(f"!!document.querySelector('{sec} .ProseMirror')", "the editor opened")
            p.js(f"document.querySelector('{sec} .ProseMirror').cxed.editor.commands.insertContent('<p>Fictional second words</p>'); true")
            p.key("Enter", 4 if p.js("/Mac/.test(navigator.platform)") else 2, code="Enter", vk=13)
            from test_server import wait
            self.assertTrue(wait(lambda: "Fictional second words" in json.loads(self.body_of(ref)).get("html", ""), 10), self.body_of(ref))
            got = json.loads(self.body_of(ref))
            self.assertEqual(got["title"], "Fictional first title", "the second save kept the first one's words")

    def test_a_refused_save_puts_the_saved_words_back_and_the_page_says_what_to_do(self):
        ref = self.make(self.GOOD)
        before = self.body_of(ref)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!{n.field_js(ref, 'Callout title')}", "the fields")
            n.fill(p, n.field_js(ref, "Callout title"), "bad\u202ewords")                  # an invisible direction mark: the store refuses it
            p.until("!!document.querySelector('.toast')", "the page said something")
            p.until(f"{n.field_js(ref, 'Callout title')}.value === 'Fictional decision'", "the saved title is back in the field")
            self.assertEqual(self.body_of(ref), before)
            self.assertTrue(p.toast().endswith((".", "?")), p.toast())

    # ---- #1272 slice 2: the look in View and the controls in Edit ----
    def _at(self, cdp, p, width):
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)

    def test_view_draws_the_colour_the_icon_and_the_category_word(self):
        ref = self.make({**GOOD, "category": "Legal hold", "colour": "green", "icon": "lock"})
        old = self.make(GOOD)
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp)
                self._at(cdp, p, width)
                box = lambda r: f"document.querySelector('[data-id={json.dumps(r)}] .tpl-callout')"
                self.assertEqual(p.js(f"{box(ref)}.dataset.colour + ' ' + {box(ref)}.dataset.icon"), "green lock")
                self.assertEqual(p.js(f"{box(ref)}.querySelector('.tpl-callout-tone').textContent"), "Legal hold")
                self.assertTrue(p.js(f"!!{box(ref)}.querySelector('svg[data-icn=lock]')"))
                self.assertEqual(p.js(f"{box(old)}.dataset.colour + ' ' + {box(old)}.dataset.icon"), "amber question", "an older callout draws its tone's look")
                self.assertEqual(p.js(f"{box(old)}.querySelector('.tpl-callout-tone').textContent"), "Decision needed")

    def test_view_names_the_colour_and_the_icon_in_words(self):
        full = self.make({**GOOD, "category": "Budget", "colour": "violet", "icon": "bulb"})
        bare = self.make({**GOOD, "category": "", "colour": "plain", "icon": "none"})
        old = self.make(GOOD)
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp)
                self._at(cdp, p, width)
                words = lambda r: p.js(f"document.querySelector('[data-id={json.dumps(r)}] .tpl-callout .sr-only').textContent")
                self.assertEqual(words(full), "Colour: Violet. Icon: Light bulb.")
                self.assertEqual(words(bare), "Colour: Plain.")
                self.assertEqual(words(old), "Colour: Amber. Icon: Question.", "an older callout names its tone's look")

    def test_a_colour_with_no_word_and_no_icon_draws_its_own_shape_and_plain_draws_none(self):
        a = self.make({**GOOD, "category": "", "colour": "red", "icon": "none"})
        b = self.make({**GOOD, "category": "", "colour": "plain", "icon": "none"})
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertTrue(p.js(f"!!document.querySelector('[data-id={json.dumps(a)}] .tpl-callout svg[data-icn=shRed]')"))
            self.assertFalse(p.js(f"!!document.querySelector('[data-id={json.dumps(b)}] .tpl-callout svg')"))

    def test_a_colour_with_a_word_and_no_icon_draws_no_shape(self):
        ref = self.make({**GOOD, "category": "Budget", "colour": "red", "icon": "none"})
        with chrome() as cdp:
            p = self.visit(cdp)
            box = f"document.querySelector('[data-id={json.dumps(ref)}] .tpl-callout')"
            self.assertEqual(p.js(f"{box}.querySelector('.tpl-callout-tone').textContent"), "Budget")
            self.assertFalse(p.js(f"!!{box}.querySelector('svg')"), "the word is the second cue: the colour draws no shape of its own")
            self.assertIn("noic", p.js(f"{box}.className"))

    def test_edit_the_tile_and_heading_switches_show_the_stored_state(self):
        from test_server import wait
        ref = self.make({**GOOD, "tile": False, "heading": False})
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            sec = f"[data-id={json.dumps(ref)}]"
            q = lambda label: f"document.querySelector('{sec} [aria-label=\"{label}\"]')"
            tile, head = "Show the tile (the card around the callout)", "Show the heading"
            p.until(f"!!{q(tile)}", "the toolbar")
            self.assertEqual(p.js(f"{q(tile)}.getAttribute('aria-checked')"), "false")
            self.assertEqual(p.js(f"{q(head)}.getAttribute('aria-checked')"), "false")
            p.js(f"{q(tile)}.click()")
            self.assertTrue(wait(lambda: json.loads(self.body_of(ref)).get("tile") is True, 10), self.body_of(ref))
            p.until(f"{q(tile)}.getAttribute('aria-checked') === 'true'", "the tile switch shows the saved state (the page redraws after the save lands, not with it)")
            p.js(f"{q(head)}.click()")
            self.assertTrue(wait(lambda: json.loads(self.body_of(ref)).get("heading") is True, 10), self.body_of(ref))

    def test_edit_tags_the_hidden_part_in_the_ticket_words_and_view_has_no_tag(self):
        want = {(True, True): None, (False, True): "Tile not shown in View", (True, False): "Heading not shown in View", (False, False): "Heading and tile not shown in View"}
        for (tile, head), word in want.items():
            ref = self.make({**GOOD, "tile": tile, "heading": head})
            with self.subTest(tile=tile, heading=head), chrome() as cdp:
                p = self.visit(cdp)
                tag = f"[...document.querySelectorAll('[data-id={json.dumps(ref)}] [data-not-shown]')].map(e => e.textContent)"
                self.assertEqual(p.js(tag), [], "View draws no tag")
                p.edit()
                p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}] .tpl-callout, [data-id={json.dumps(ref)}] [aria-label=\"Show the heading\"]')", "the callout in Edit")
                self.assertEqual(p.js(tag), [word] if word else [])

    def test_no_tile_and_no_heading_in_view_and_the_heading_keeps_its_name(self):
        ref = self.make({**GOOD, "tile": False, "heading": False})
        with chrome() as cdp:
            p = self.visit(cdp)
            sec = f"document.querySelector('[data-id={json.dumps(ref)}]')"
            self.assertTrue(p.js(f"{sec}.classList.contains('no-tile') && {sec}.classList.contains('no-head')"))
            self.assertEqual(p.js(f"getComputedStyle({sec}).backgroundColor"), "rgba(0, 0, 0, 0)")
            self.assertLessEqual(p.js(f"{sec}.querySelector('.sec-h').getBoundingClientRect().width"), 2)
            self.assertIn("Fictional callout", p.js(f"{sec}.querySelector('.sec-h').textContent"), "the heading is still in the page for a screen reader")

    def test_edit_a_suggestion_sets_the_word_the_colour_and_the_icon_as_one_step(self):
        for width in (1400, 900):
            ref = self.make(GOOD)
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp)
                self._at(cdp, p, width)
                p.edit()
                sec = f"[data-id={json.dumps(ref)}]"
                p.until(f"!!document.querySelector('{sec} [aria-label=\"Use Warning\"]')", "the toolbar")
                p.js(f"document.querySelector('{sec} [aria-label=\"Use Warning\"]').click()")
                p.saved()
                got = json.loads(self.body_of(ref))
                self.assertEqual((got["category"], got["colour"], got["icon"], got["tone"]), ("Warning", "red", "warning", "warning"))
                p.js(f"document.querySelector('{sec} [aria-label=\"No category\"]').click()")
                from test_server import wait
                self.assertTrue(wait(lambda: "category" not in json.loads(self.body_of(ref)), 10), self.body_of(ref))
                self.assertEqual(json.loads(self.body_of(ref))["colour"], "red")

    def test_the_box_class_follows_the_shape_and_the_tile_and_heading_classes_follow_their_own_field(self):
        shape = self.make({**GOOD, "category": "", "colour": "red", "icon": "none"})
        bare = self.make({**GOOD, "category": "", "colour": "plain", "icon": "none"})
        old = self.make(GOOD)
        tile_only = self.make({**GOOD, "tile": False, "heading": True})
        head_only = self.make({**GOOD, "tile": True, "heading": False})
        with chrome() as cdp:
            p = self.visit(cdp)
            cls = lambda r, sel="": p.js(f"document.querySelector('[data-id={json.dumps(r)}]{sel}').className")
            self.assertNotIn("noic", cls(shape, " .tpl-callout"), "a colour's own shape is an icon: the grid keeps its column")
            self.assertIn("noic", cls(bare, " .tpl-callout"))
            self.assertNotIn("no-head", cls(old)); self.assertNotIn("no-tile", cls(old))
            self.assertIn("no-tile", cls(tile_only)); self.assertNotIn("no-head", cls(tile_only))
            self.assertIn("no-head", cls(head_only)); self.assertNotIn("no-tile", cls(head_only))

    def test_edit_each_suggestion_sets_its_own_colour_and_icon(self):
        from test_server import wait
        for label, want in (("Use Decision needed", ("Decision needed", "amber", "fork", "decision")), ("Use Information", ("Information", "violet", "info", "info"))):
            ref = self.make({**GOOD, "tone": "warning"})
            with self.subTest(label=label), chrome() as cdp:
                p = self.visit(cdp)
                p.edit()
                sec = f"[data-id={json.dumps(ref)}]"
                p.until(f"!!document.querySelector('{sec} [aria-label=\"{label}\"]')", "the toolbar")
                p.js(f"document.querySelector('{sec} [aria-label=\"{label}\"]').click()")
                self.assertTrue(wait(lambda: json.loads(self.body_of(ref)).get("colour") == want[1], 10), self.body_of(ref))
                got = json.loads(self.body_of(ref))
                self.assertEqual((got["category"], got["colour"], got["icon"], got["tone"]), want)

    def test_edit_the_colour_the_icon_and_the_switches_save(self):
        ref = self.make(GOOD)
        from test_server import wait
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            sec = f"[data-id={json.dumps(ref)}]"
            q = lambda label: f"document.querySelector('{sec} [aria-label=\"{label}\"]')"
            p.until(f"!!{q('Green')}", "the toolbar")
            self.assertEqual(p.js(f"{q('Amber')}.getAttribute('aria-checked')"), "true", "an older callout shows its tone's colour")
            p.js(f"{q('Green')}.click()")
            self.assertTrue(wait(lambda: json.loads(self.body_of(ref)).get("colour") == "green", 10), self.body_of(ref))
            self.assertEqual(json.loads(self.body_of(ref))["category"], "Decision needed", "the word an older callout drew is kept")
            p.js(f"{q('Choose an icon')}.click()")
            p.until(f"!!document.querySelector('{sec} [role=listbox]')", "the icons are listed")
            self.assertEqual(p.js(f"document.querySelectorAll('{sec} [role=option]').length"), 27, "26 icons and No icon")
            names = p.js(f"[...document.querySelectorAll('{sec} [role=option]')].map(o => o.textContent)")
            for n in NEW_ICON_NAMES:
                self.assertIn(n, names, "each new icon is in the picker")
            self.assertEqual(names.count("Warning triangle"), 1, "one triangle entry")
            self.assertNotIn("Warning", names, "the old name is not shown beside it")
            self.assertNotIn("Magnifier", names)
            self.assertNotIn("Person", names)
            p.js(f"[...document.querySelectorAll('{sec} [role=option]')].find(o => o.textContent === 'Key').click()")
            self.assertTrue(wait(lambda: json.loads(self.body_of(ref)).get("icon") == "key", 10), self.body_of(ref))
            self.assertFalse(p.js(f"!!document.querySelector('{sec} [role=listbox]')"), "choosing closes the list")
            p.js(f"{q('Show the tile (the card around the callout)')}.click()")
            self.assertTrue(wait(lambda: json.loads(self.body_of(ref)).get("tile") is False, 10), self.body_of(ref))
            p.js(f"{q('Show the heading')}.click()")
            self.assertTrue(wait(lambda: json.loads(self.body_of(ref)).get("heading") is False, 10), self.body_of(ref))
            self.assertTrue(p.js(f"document.querySelector('{sec}').classList.contains('no-tile')"), "Edit keeps the card, dashed")
            self.assertEqual(p.js(f"getComputedStyle(document.querySelector('{sec}')).borderStyle"), "dashed")

    def test_edit_a_category_is_typed_in_the_toolbar_and_over_30_characters_is_not_typed(self):
        ref = self.make(GOOD)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            sel = n.field_js(ref, "Category")
            p.until(f"!!{sel}", "the category field")
            self.assertEqual(p.js(f"{sel}.maxLength"), 30)
            n.fill(p, sel, "Legal hold")
            p.saved()
            got = json.loads(self.body_of(ref))
            self.assertEqual((got["category"], got["colour"], got["icon"]), ("Legal hold", "amber", "question"))

    def test_edit_the_decision_icon_is_two_ways_the_title_and_words_line_up_with_the_category_and_the_counter_counts(self):
        """Row 1272 (read of PR 2089 of 20-11: Two ways): the Decision suggestion sets the Two ways icon (key fork); the title text and the words text start where the
        category word starts; the toolbar says "Title N of 120" (N = characters typed, Edit only)."""
        for width in (1400, 900):
            ref = self.make(GOOD)
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp)
                self._at(cdp, p, width)
                p.edit()
                sec = f"[data-id={json.dumps(ref)}]"
                p.until(f"!!document.querySelector('{sec} [aria-label=\"Use Decision needed\"]')", "the toolbar")
                p.js(f"document.querySelector('{sec} [aria-label=\"Use Decision needed\"]').click()")
                p.saved()
                self.assertEqual(json.loads(self.body_of(ref))["icon"], "fork")
                p.until(f"!!document.querySelector('{sec} .tpl-callout-tone')", "the category word")
                left = p.js(f"""(() => {{ const q = (s) => document.querySelector('{sec} ' + s), edge = (el) => {{ const r = el.getBoundingClientRect(), c = getComputedStyle(el);
                    return Math.round((r.left + parseFloat(c.borderLeftWidth) + parseFloat(c.paddingLeft)) * 10) / 10; }};
                    return [q('.tpl-callout-tone').getBoundingClientRect().left, edge(q('.cb-title')), edge(q('.tpl-callout-main .rt-view'))].map((x) => Math.round(x * 10) / 10); }})()""")
                self.assertEqual(len(set(left)), 1, f"the category word, the title text and the words start at one left edge: {left}")
                self.assertEqual(p.js(f"document.querySelector('{sec} .cb-count').textContent"), f"Title {len(GOOD['title'])} of 120")
                n.fill(p, n.field_js(ref, "Callout title"), "Four")
                p.until(f"document.querySelector('{sec} .cb-count').textContent === 'Title 4 of 120'", "the counter follows what is typed")


class SharedLook(unittest.TestCase):
    """#1272 slice 3: the tile and heading flags are read the same way for every section type; the prompt words are one pair of strings (the #1251 hook)."""

    def run_js(self, probe):
        import shutil, subprocess, tempfile
        from pathlib import Path
        import esbuild  # noqa: E402  (dev/tools)
        if not shutil.which("node"):
            raise unittest.SkipTest("no node")
        notes = Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "src" / "templates" / "notes.js"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "n.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=N", str(notes), f"--outfile={out}"], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            script = Path(tmp) / "probe.js"
            script.write_text(out.read_text(encoding="utf-8") + ";\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
            got = subprocess.run([shutil.which("node"), str(script)], capture_output=True, text=True)
            self.assertEqual(got.returncode, 0, got.stderr)
            return json.loads(got.stdout)

    def test_any_section_type_can_turn_its_tile_and_heading_off(self):
        got = self.run_js("[N.sectionShows({type: 'text'}), N.sectionShows({type: 'text', tile: false}), N.sectionShows({type: 'raid3', heading: false, tile: false}),"
                          " N.sectionShows({type: 'callout', body: JSON.stringify({v: 1, tone: 'info', title: 'T', paras: [], html: '', tile: false})})]")
        self.assertEqual(got, [{"tile": True, "heading": True}, {"tile": False, "heading": True}, {"tile": False, "heading": False}, {"tile": False, "heading": True}])

    def test_the_prompt_words_are_two_placeholders(self):
        self.assertEqual(self.run_js("Object.keys(N.PROMPTS)"), ["title", "words"])
        self.assertEqual(self.run_js("N.PROMPTS"), {"title": "Add a title: what the reader must see", "words": "Click to write."})


if __name__ == "__main__":
    unittest.main()
