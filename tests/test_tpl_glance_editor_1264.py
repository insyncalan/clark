"""Row 1264 slice 6: the Glance template's tile editor and colours, in a real browser (T72 to T79): Add a tile (button and menu), the pencil on an
own tile, the in-page editor with its limits, Delete and Remove, Done and Cancel, pop out and back, five colours each with a shape, the
toasts, the two errors, the 12 tile limit, one Undo step for a tile change. The words are the ruled ones (the 1264 words files, groups 4 to 9
and 14, v2 D and E). Fictional data only.

Run: python3 dev/run_tests.py test_tpl_glance_editor_1264
"""
import json
import pathlib
import re
import unittest

from _demo import USER
from test_changes import KIND
from test_glance_page import plant
from test_report_editor import ALT, Base, tearDownModule  # noqa: F401
from test_server import chrome, wait

SHELL = (pathlib.Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
OWN = {"id": "t1", "label": "Fictional own tile", "figure": "7", "tag": "Fine", "note": "Fictional note", "tone": "green"}


class Editor(Base):
    def setUp(self):
        super().setUp()
        plant(self)
        with self.store.step("dashboard", USER) as st:
            self.ref = st.create("report_sections", {"project": "ABC", "type": "glancetemplate", "title": "Fictional glance", "sort_order": 998})

    def seed(self, bespoke):
        status, got = self.real_change({"project": "ABC", "kind": KIND, "op": "update", "id": self.ref,
                                        "changes": {"body": json.dumps({"v": 1, "bespoke": bespoke})}})
        assert status == 200, got

    def page(self, cdp, width=1400, dark=False):
        p = self.visit(cdp)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, p.sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        if dark:
            p.js("document.documentElement.dataset.theme = 'dark'")
        p.edit()
        p.until(f"!!document.querySelector('{self.sel('[data-tile=decisions]')}')", "the tiles drew")
        return p

    def sel(self, rest=""):
        return f'[data-id="{self.ref}"] {rest}'.strip()

    def q(self, rest):
        return json.dumps(self.sel(rest))

    def body(self):
        raw = self.store.read("report_sections", ref=self.ref)["body"]
        return json.loads(raw) if raw else {}

    def applies(self):
        return self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]

    def toast(self, p):
        return p.js("(document.querySelector('.toast-text') || {}).textContent || ''")

    def click(self, p, sel):
        p.js(f"document.querySelector({self.q(sel)}).click()")

    def undo(self, p):
        p.js("document.querySelector('[data-undo]').click()")
        p.until("!document.querySelector('[data-undo]')", "undone")

    def open_add(self, p):
        self.click(p, ".tileadd")
        p.until("!!document.querySelector('.ddmenu[role=menu]')", "the Add menu")

    def editor_open(self, p):
        p.until(f"!!document.querySelector({self.q('[data-tile-editor]')})", "the editor")

    def fill(self, p, field, value):
        p.js(f"""(function(){{ var i = document.querySelector({self.q(f'[data-f={field}]')}); i.focus(); i.value = {json.dumps(value)};
                 i.dispatchEvent(new Event('input', {{bubbles: true}})); }})()""")


class Adding(Editor):
    def test_T72_add_a_tile_opens_the_editor_with_the_defaults_and_done_stores_it_in_one_step(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.assertEqual(p.js(f"document.querySelector({self.q('.tileadd')}).textContent.trim()"), "Add a tile")
            self.open_add(p)
            self.assertEqual(p.js("[...document.querySelectorAll('.ddmenu[role=menu] [role=menuitem]')].map(b => b.textContent)"),
                             ["Your own tileA label, a figure or short text, a tag and a colour you set"])
            before = self.applies()
            p.js("document.querySelector('.ddmenu[role=menu] [role=menuitem]').click()")
            self.editor_open(p)
            self.assertEqual(self.applies(), before, "nothing is stored until Done")
            p.until("document.activeElement.dataset.f === 'label'", "the label takes the focus")
            got = p.js(f"""(function(){{ var e = document.querySelector({self.q('[data-tile-editor]')});
              return {{name: e.getAttribute('aria-label'), h: e.querySelector('h4').textContent.trim(),
                       fields: ['label', 'figure', 'tag', 'note'].map(function(f){{ var i = e.querySelector('[data-f=' + f + ']'); return [i.getAttribute('aria-label'), i.value]; }}),
                       counters: [...e.querySelectorAll('label small')].map(s => s.textContent),
                       buttons: [...e.querySelectorAll('.foot button')].map(b => b.textContent.trim())}}; }})()""")
            self.assertEqual(got["name"], "Edit tile")
            self.assertEqual(got["h"], "Edit tile")
            self.assertEqual(got["fields"], [["Label", "New tile"], ["Figure or short text", "0"], ["Tag text", ""], ["Note", ""]])
            self.assertEqual(got["counters"], ["8 of 40", "1 of 12", "optional, 0 of 12", "optional, 0 of 60"])
            self.assertEqual(got["buttons"], ["Cancel", "Done"], "a tile not stored yet has no Remove tile")
            self.fill(p, "label", "Fictional new")
            self.fill(p, "figure", "42")
            self.click(p, "[data-tile-editor] [data-tone=blue]")
            self.click(p, "[data-tile-editor] [data-done]")
            self.assertTrue(wait(lambda: len(self.body().get("bespoke", [])) == 1, 10), f"stored: {self.body()}")
            t = self.body()["bespoke"][0]
            self.assertEqual({k: v for k, v in t.items() if k != "id"}, {"label": "Fictional new", "figure": "42", "tone": "blue"})
            self.assertEqual(self.applies(), before + 1, "one step")
            p.until("!!document.querySelector('[data-undo]')", "the toast")
            self.assertEqual(self.toast(p), "Added: Fictional new")
            self.assertFalse(p.js(f"!!document.querySelector({self.q('[data-tile-editor]')})"), "the editor closed")
            self.undo(p)
            self.assertTrue(wait(lambda: not self.body().get("bespoke"), 10), f"undone: {self.body()}")
            self.assertEqual(self.applies(), before + 2, "the undo is one step")

    def test_T72_cancel_on_a_new_tile_stores_nothing_and_says_so(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_add(p)
            p.js("document.querySelector('.ddmenu[role=menu] [role=menuitem]').click()")
            self.editor_open(p)
            before = self.applies()
            self.click(p, "[data-tile-editor] [data-cancel]")
            p.until("!!document.querySelector('.toast-text')", "the note")
            self.assertEqual(self.toast(p), "Changes to the tile cancelled")
            self.assertEqual(self.applies(), before)
            self.assertFalse(self.body().get("bespoke"))
            self.assertTrue(p.js("document.activeElement.classList.contains('tileadd')"), "focus back on Add a tile")

    def test_T72_a_new_tile_takes_the_lowest_unused_id_and_is_drawn_last(self):
        self.seed([dict(OWN, id="t2")])
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_add(p)
            p.js("document.querySelector('.ddmenu[role=menu] [role=menuitem]').click()")
            self.editor_open(p)
            self.fill(p, "label", "Fictional second")
            self.click(p, "[data-tile-editor] [data-done]")
            self.assertTrue(wait(lambda: len(self.body().get("bespoke", [])) == 2, 10), f"stored: {self.body()}")
            self.assertEqual(sorted(t["id"] for t in self.body()["bespoke"]), ["t1", "t2"])
            p.until(f"!!document.querySelector({self.q('[data-tile=t1]')})", "the new tile drew")
            ids = p.js(f"[...document.querySelectorAll({self.q('[data-tile]')})].map(e => e.dataset.tile)")
            self.assertEqual(ids[-1], "t1", f"the new tile is last: {ids}")
            self.assertEqual(ids[-2], "t2")

    def test_T72_the_limit_of_12_tiles_is_said_and_no_13th_is_made(self):
        self.seed([{"id": f"t{i}", "label": f"Fictional {i}", "figure": str(i)} for i in range(1, 13)])
        with chrome() as cdp:
            p = self.page(cdp)
            before = self.applies()
            self.open_add(p)
            self.assertEqual(p.js("document.querySelector('.ddmenu[role=menu] [role=menuitem]').textContent"), "Your own tileYou can have up to 12 tiles.")
            p.js("document.querySelector('.ddmenu[role=menu] [role=menuitem]').click()")
            p.until("!!document.querySelector('.toast-text')", "the note")
            self.assertEqual(self.toast(p), "You can have up to 12 tiles.")
            self.assertFalse(p.js(f"!!document.querySelector({self.q('[data-tile-editor]')})"))
            self.assertEqual(self.applies(), before)


class Editing(Editor):
    def setUp(self):
        super().setUp()
        self.seed([OWN])

    def pencil(self, p, tid="t1"):
        self.click(p, f"[data-tile={tid}] [data-tile-pencil]")
        self.editor_open(p)
        p.until("document.activeElement.dataset.f === 'label'", "the label has the focus")

    def test_T73_the_pencil_opens_the_editor_and_done_changes_the_tile_in_one_step_and_one_undo(self):
        with chrome() as cdp:
            p = self.page(cdp)
            pen, bin_ = self.q("[data-tile=t1] [data-tile-pencil]"), self.q("[data-tile=t1] [data-tile-bin]")
            self.assertEqual(p.js(f"document.querySelector({pen}).getAttribute('aria-label')"), "Edit Fictional own tile")
            self.assertEqual(p.js(f"document.querySelector({pen}).title"), "Edit this tile")
            self.assertEqual(p.js(f"document.querySelector({bin_}).getAttribute('aria-label')"), "Delete Fictional own tile")
            self.assertEqual(p.js(f"document.querySelector({bin_}).title"), "Delete this tile")
            self.pencil(p)
            self.assertEqual(p.js(f"document.querySelector({self.q('[data-tile-editor] [data-f=label]')}).value"), "Fictional own tile")
            before = self.applies()
            self.fill(p, "label", "Fictional changed")
            self.fill(p, "note", "")
            self.click(p, "[data-tile-editor] [data-tone=red]")
            self.click(p, "[data-tile-editor] [data-done]")
            self.assertTrue(wait(lambda: self.body()["bespoke"][0].get("label") == "Fictional changed", 10), f"stored: {self.body()}")
            self.assertEqual(self.body()["bespoke"][0], {"id": "t1", "label": "Fictional changed", "figure": "7", "tag": "Fine", "tone": "red"})
            self.assertEqual(self.applies(), before + 1)
            p.until("!!document.querySelector('[data-undo]')", "the toast")
            self.assertEqual(self.toast(p), "Tile saved")
            self.undo(p)
            self.assertTrue(wait(lambda: self.body()["bespoke"][0].get("label") == "Fictional own tile", 10), f"undone: {self.body()}")
            self.assertEqual(self.body()["bespoke"][0], OWN)

    def test_T73_an_empty_label_is_not_saved_the_error_says_why_and_the_editor_stays(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.pencil(p)
            before = self.applies()
            self.fill(p, "label", "   ")
            self.click(p, "[data-tile-editor] [data-done]")
            p.until("!!document.querySelector('.toast-text')", "the note")
            self.assertEqual(self.toast(p), "The tile was not saved. Give it a label, then try again.")
            self.assertEqual(p.js(f"(document.querySelector({self.q('[data-tile-editor] .err')}) || {{}}).textContent"), "Give the tile a label.")
            self.assertEqual(p.js(f"document.querySelector({self.q('[data-tile-editor] [data-f=label]')}).getAttribute('aria-invalid')"), "true")
            self.assertEqual(p.js("document.activeElement.dataset.f"), "label")
            self.assertEqual(self.applies(), before)
            self.assertEqual(self.body()["bespoke"][0]["label"], "Fictional own tile")

    def test_T73_cancel_and_esc_put_the_tile_back_with_no_step(self):
        with chrome() as cdp:
            p = self.page(cdp)
            before = self.applies()
            self.pencil(p)
            self.fill(p, "label", "Fictional typed")
            self.click(p, "[data-tile-editor] [data-cancel]")
            p.until("!!document.querySelector('.toast-text')", "the note")
            self.assertEqual(self.toast(p), "Changes to the tile cancelled")
            self.assertEqual(p.js(f"document.querySelector({self.q('[data-tile=t1] .tpl-gt-k')}).textContent"), "Fictional own tile")
            self.assertTrue(p.js("document.activeElement.hasAttribute('data-tile-pencil')"), "focus back on the pencil")
            self.pencil(p)
            p.key("Escape", 0, code="Escape", vk=27)
            p.until(f"!document.querySelector({self.q('[data-tile-editor]')})", "closed by Esc")
            self.assertEqual(self.applies(), before)

    def test_T74_the_bin_deletes_and_remove_tile_removes_each_in_one_step_with_its_toast_and_undo(self):
        with chrome() as cdp:
            p = self.page(cdp)
            before = self.applies()
            self.click(p, "[data-tile=t1] [data-tile-bin]")
            self.assertTrue(wait(lambda: not self.body().get("bespoke"), 10), f"stored: {self.body()}")
            p.until("!!document.querySelector('[data-undo]')", "the toast")
            self.assertEqual(self.toast(p), "Deleted: Fictional own tile")
            self.assertEqual(self.applies(), before + 1)
            self.undo(p)
            self.assertTrue(wait(lambda: self.body().get("bespoke") == [OWN], 10), f"undone: {self.body()}")
            p.until(f"!!document.querySelector({self.q('[data-tile=t1]')})", "back on the page")
            self.pencil(p)
            self.assertEqual(p.js(f"document.querySelector({self.q('[data-tile-editor] [data-remove]')}).textContent.trim()"), "Remove tile")
            self.click(p, "[data-tile-editor] [data-remove]")
            self.assertTrue(wait(lambda: not self.body().get("bespoke"), 10), f"stored: {self.body()}")
            p.until("!!document.querySelector('[data-undo]')", "the toast")
            self.assertEqual(self.toast(p), "Removed: Fictional own tile")

    def test_T75_pop_out_makes_the_editor_larger_and_bring_back_returns_it_with_what_was_typed(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.pencil(p)
            pop, ed = self.q("[data-tile-editor] [data-pop]"), self.q("[data-tile-editor]")
            self.assertEqual(p.js(f"document.querySelector({pop}).getAttribute('aria-label')"), "Pop out to a larger editor")
            small = p.js(f"document.querySelector({ed}).getBoundingClientRect().width")
            self.fill(p, "label", "Fictional typed")
            p.js(f"document.querySelector({pop}).focus()")
            self.click(p, "[data-tile-editor] [data-pop]")
            self.assertEqual(p.js(f"document.querySelector({pop}).getAttribute('aria-label')"), "Bring back to the tile")
            self.assertEqual(p.js(f"document.querySelector({pop}).getAttribute('aria-pressed')"), "true")
            big = p.js(f"document.querySelector({ed}).getBoundingClientRect().width")
            self.assertGreater(big, small * 1.5, "larger")
            self.assertEqual(p.js(f"document.querySelector({self.q('[data-f=label]')}).value"), "Fictional typed")
            self.assertTrue(p.js("document.activeElement.hasAttribute('data-pop')"), "focus stays on the button")
            self.click(p, "[data-tile-editor] [data-pop]")
            self.assertEqual(p.js(f"document.querySelector({pop}).getAttribute('aria-label')"), "Pop out to a larger editor")
            self.assertEqual(p.js(f"document.querySelector({self.q('[data-f=label]')}).value"), "Fictional typed")

    def test_T76_the_limits_cut_typing_and_count_in_characters(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.pencil(p)
            self.fill(p, "label", "x" * 50)
            self.fill(p, "figure", "y" * 20)
            self.fill(p, "tag", "\U0001F600" * 14)
            self.fill(p, "note", "n" * 80)
            got = p.js(f"""(function(){{ var e = document.querySelector({self.q('[data-tile-editor]')});
              return {{v: ['label', 'figure', 'tag', 'note'].map(f => Array.from(e.querySelector('[data-f=' + f + ']').value).length), c: [...e.querySelectorAll('label small')].map(s => s.textContent)}}; }})()""")
            self.assertEqual(got["v"], [40, 12, 12, 60])
            self.assertEqual(got["c"], ["40 of 40", "12 of 12", "optional, 12 of 12", "optional, 60 of 60"])

    def test_T77_five_colours_each_with_its_own_shape_and_the_sentence_and_the_choice_is_a_radio_group(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.pencil(p)
            got = p.js(f"""(function(){{ var e = document.querySelector({self.q('[data-tile-editor]')}), g = e.querySelector('[role=radiogroup]');
              return {{group: g.getAttribute('aria-label'), head: [...e.querySelectorAll('.lbl')].map(x => x.textContent), live: e.querySelector('.live').textContent,
                       radios: [...g.querySelectorAll('[role=radio]')].map(b => [b.dataset.tone, b.textContent.trim(), b.getAttribute('aria-checked')])}}; }})()""")
            self.assertEqual(got["group"], "Tile colour")
            self.assertEqual(got["head"], ["Colour"])
            self.assertEqual(got["live"], "The colour is a shape and the tag word too, never colour alone.")
            self.assertEqual(got["radios"], [["green", "GreenOn track", "true"], ["amber", "AmberAt risk", "false"], ["red", "RedOff track", "false"], ["blue", "BlueInfo", "false"], ["neutral", "Neutral", "false"]])
            shapes = p.js(f"[...document.querySelectorAll({self.q('[data-tile-editor] [role=radio] svg')})].map(s => s.firstElementChild.tagName + ':' + (s.firstElementChild.getAttribute('d') || s.firstElementChild.getAttribute('fill')))")
            self.assertEqual(len(set(shapes)), 5, f"five shapes: {shapes}")
            self.click(p, "[data-tile-editor] [data-tone=blue]")
            self.assertEqual(p.js(f"document.querySelector({self.q('[data-tile-editor] [data-tone=blue]')}).getAttribute('aria-checked')"), "true")
            self.assertTrue(p.js(f"document.querySelector({self.q('[data-tile=t1] .tpl-gt-tile')}).className.includes('tone-b')"), "the tile shows the pick before Done")

    def test_T78_an_own_tile_has_grip_eye_pencil_bin_the_eye_hides_it_and_alt_arrow_moves_it(self):
        self.seed([OWN, {**OWN, "id": "t2", "label": "Fictional second"}])
        with chrome() as cdp:
            p = self.page(cdp)
            order = lambda: p.js(f"[...document.querySelectorAll({self.q('.glance > .tcell')})].map(e => e.dataset.tile)")  # noqa: E731
            self.assertEqual(order(), ["health", "overdue", "risks", "decisions", "t1", "t2"])
            self.assertEqual(p.js(f"[...document.querySelectorAll({self.q('[data-tile=t1] button')})].map(b => Object.keys(b.dataset).filter(k => k.startsWith('tile'))[0])"),
                             ["tileGrip", "tileEye", "tilePencil", "tileBin"], "the tab order")
            before = self.applies()
            p.js(f"document.querySelector({self.q('[data-tile=t2] [data-tile-grip]')}).focus()")
            p.key("ArrowLeft", ALT, code="ArrowLeft", vk=37)
            self.assertTrue(wait(lambda: self.body().get("order") is not None, 10), f"stored: {self.body()}")
            self.assertEqual(self.body()["order"], ["health", "overdue", "risks", "decisions", "t2", "t1"])
            self.assertEqual(self.applies(), before + 1)
            p.until("!!document.querySelector('[data-undo]')", "the toast")
            self.assertEqual(self.toast(p), "Fictional second moved.")
            self.click(p, "[data-tile=t1] [data-tile-eye]")
            self.assertTrue(wait(lambda: any(t.get("hidden") for t in self.body()["bespoke"]), 10), f"stored: {self.body()}")
            self.assertEqual([t["id"] for t in self.body()["bespoke"] if t.get("hidden")], ["t1"])
            p.until(f"document.querySelector({self.q('[data-tile=t1]')}).classList.contains('is-hidden')", "the tile drew dimmed")

    def test_T79_it_fits_at_1400_and_900_in_light_and_dark_and_the_popped_out_editor_stays_inside_the_window(self):
        self.seed([{**OWN, "id": f"t{i}", "tone": tone, "label": "Fictional label of forty characters ok!!", "figure": "123456789012", "tag": "Twelve words", "note": "n" * 60}
                   for i, tone in enumerate(("green", "amber", "red", "blue", "neutral"), 1)])
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.page(cdp, width, dark)
                    got = p.js(f"""(function(){{ var g = document.querySelector({self.q('.glance')}), gr = g.getBoundingClientRect();
                      return {{overflow: document.documentElement.scrollWidth > window.innerWidth,
                               out: [...g.querySelectorAll('.tcell')].filter(c => c.getBoundingClientRect().right > gr.right + 1).map(c => c.dataset.tile),
                               small: [...g.querySelectorAll('.tpl-gt-tile *')].filter(e => parseFloat(getComputedStyle(e).fontSize) < 13 && e.textContent.trim()).length,
                               tones: [...g.querySelectorAll('.tpl-gt-tile')].map(t => getComputedStyle(t).borderTopColor)}}; }})()""")
                    self.assertFalse(got["overflow"], f"no sideways scroll: {p.js('[...document.querySelectorAll(\'body *\')].filter(e => e.getBoundingClientRect().right > window.innerWidth + 1).slice(0, 6).map(e => e.tagName + \'.\' + e.className + \' \' + Math.round(e.getBoundingClientRect().right) + \' \' + window.innerWidth)')}")
                    self.assertEqual(got["out"], [], "every tile inside the section")
                    self.assertEqual(got["small"], 0, "no text under 13px")
                    self.assertEqual(len(set(got["tones"])), 5, f"five border colours: {got['tones']}")
                    self.pencil(p, "t4")
                    self.click(p, "[data-tile-editor] [data-pop]")
                    box = p.js(f"""(function(){{ var r = document.querySelector({self.q('[data-tile-editor]')}).getBoundingClientRect();
                      var small = [...document.querySelectorAll({self.q('[data-tile-editor] *')})].filter(e => parseFloat(getComputedStyle(e).fontSize) < 13 && e.textContent.trim()).length;
                      return {{l: r.left, r: r.right, t: r.top, b: r.bottom, w: window.innerWidth, h: window.innerHeight, small: small, overflow: document.documentElement.scrollWidth > window.innerWidth}}; }})()""")
                    self.assertTrue(box["l"] >= 0 and box["r"] <= box["w"] and box["t"] >= 0 and box["b"] <= box["h"], f"inside the window: {box}")
                    self.assertEqual(box["small"], 0)
                    self.assertFalse(box["overflow"])


class Css(unittest.TestCase):
    def rule(self, selector):
        m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", SHELL)
        self.assertTrue(m, selector)
        return m.group(1)

    def test_T79_the_editor_css_reads_tokens_only_and_no_size_under_13px(self):
        css = "".join(self.rule(s) for s in (".tpl-ed", ".tpl-ed h4", ".tpl-ed .inp", ".tpl-ed .col", ".tpl-ed .foot", ".tpl-ed.pop", ".tpl-add"))
        self.assertIsNone(re.search(r"#[0-9A-Fa-f]{3,6}\b|rgb\(|rgba\(", css), "no colour value of its own")
        self.assertIsNone(re.search(r"font-size:\s*\d", css), "no bare font size")

    def test_T77_red_is_a_diamond_and_blue_a_square_as_in_the_approved_mock_up(self):
        self.assertIn("polygon(50% 0, 100% 50%, 50% 100%, 0 50%)", self.rule(".tone-r .tpl-gt-dot"))
        self.assertIn("border-radius", self.rule(".tone-b .tpl-gt-dot"))
        self.assertNotIn("clip-path", self.rule(".tone-b .tpl-gt-dot"))
