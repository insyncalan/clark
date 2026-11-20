"""Row 1264 slice 6: killer tests for the mutation sweep of the tile editor (S6, sweep A2). Fictional data only.

Run: python3 dev/run_tests.py test_tpl_glance_editor_1264_killers
"""
import json
import pathlib
import shutil
import subprocess
import unittest

from test_report_editor import ALT, tearDownModule  # noqa: F401
from test_server import chrome, wait
from _demo import USER
from test_changes import KIND
from test_tpl_glance_editor_1264 import OWN, Editor

BODY = pathlib.Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "src" / "templates" / "glanceBody.js"


@unittest.skipUnless(shutil.which("node"), "node is needed")
class Body(unittest.TestCase):
    def run_js(self, expr):
        js = "import(process.argv[1]).then(g => console.log(JSON.stringify(%s)))" % expr
        out = subprocess.run(["node", "-e", js, BODY.as_uri()], capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr[:300])
        return json.loads(out.stdout)

    def test_K1_a_new_id_is_the_lowest_number_no_tile_has(self):
        got = self.run_js("[g.nextId({bespoke: []}), g.nextId({bespoke: [{id: 't1'}, {id: 't3'}]}), g.nextId({bespoke: [{id: 't1'}, {id: 't2'}]}), g.nextId({bespoke: [{id: 't2'}]})]")
        self.assertEqual(got, ["t1", "t2", "t3", "t1"])

    def test_K2_a_new_own_tile_goes_last_in_the_order_and_in_the_tiles(self):
        got = self.run_js("(() => { const u = g.readBody({body: JSON.stringify({v: 1, bespoke: [{id: 't1', label: 'A'}]})}); const n = g.withChange(u, {put: {id: 't2', label: 'B'}}); return [n.order, n.bespoke.map(t => t.id), u.order.length]; })()")
        self.assertEqual(got, [["health", "overdue", "risks", "decisions", "t1", "t2"], ["t1", "t2"], 5])

    def test_K3_a_tile_is_sent_trimmed_with_empty_fields_left_out_and_only_known_tones(self):
        got = self.run_js("[g.cleanTile({id: 't1', label: '  A  ', figure: ' 7 ', tag: '', note: '   ', tone: 'neutral', hidden: 1}),"
                          " g.cleanTile({id: 't1', label: 'A', tag: ' x ', note: ' y ', tone: 'purple'}),"
                          " g.cleanTile({id: 't1', label: 'A', tone: 'blue', hidden: true}),"
                          " g.compact({v: 1, health: {shown: true, own_row: false}, order: ['health', 'overdue', 'risks', 'decisions', 't1'], builtin: {overdue: {}, risks: {}, decisions: {}}, bespoke: [{id: 't1', label: ' A ', figure: ' 7 '}]}).bespoke]")
        self.assertEqual(got, [{"id": "t1", "label": "A", "figure": "7"}, {"id": "t1", "label": "A", "tag": "x", "note": "y"},
                               {"id": "t1", "label": "A", "tone": "blue", "hidden": True}, [{"id": "t1", "label": "A", "figure": "7"}]])


class Killers(Editor):
    def pencil(self, p, tid="t1"):
        self.click(p, f"[data-tile={tid}] [data-tile-pencil]")
        self.editor_open(p)
        p.until("document.activeElement.dataset.f === 'label'", "the label has the focus")

    def test_K4_each_tone_draws_its_own_class_and_the_border_follows_it(self):
        self.seed([OWN, {**OWN, "id": "t2", "tone": "amber"}, {**OWN, "id": "t3", "tone": "neutral"}, {**OWN, "id": "t4", "tone": "green", "hidden": True}])
        with chrome() as cdp:
            p = self.page(cdp)
            cls = lambda t: p.js(f"document.querySelector({self.q(f'[data-tile={t}] .tpl-gt-tile')}).className")  # noqa: E731
            self.assertIn("tone-g", cls("t1").split())
            self.assertIn("tone-a", cls("t2").split())
            self.assertIn("tone-n", cls("t3").split())
            col = lambda t: p.js(f"getComputedStyle(document.querySelector({self.q(f'[data-tile={t}] .tpl-gt-tile')})).borderTopColor")  # noqa: E731
            self.assertEqual(len({col("t1"), col("t2"), col("t3")}), 3, "green, amber and neutral each have their own border colour")
            self.assertEqual(p.js(f"document.querySelectorAll({self.q('[data-tile=t4]')}).length"), 0, "a hidden own tile is not drawn in Edit (row 1303)")

    def test_K5_done_on_a_new_tile_without_a_colour_stores_no_tone(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_add(p)
            p.js("document.querySelector('.ddmenu[role=menu] [role=menuitem]').click()")
            self.editor_open(p)
            self.assertEqual(p.js(f"document.querySelector({self.q('[data-tile-editor] [aria-checked=true]')}).dataset.tone"), "neutral")
            p.until("document.activeElement.dataset.f === 'label'", "the label takes the focus")
            p.until("document.activeElement.selectionEnd - document.activeElement.selectionStart === 8", "the label text is selected")
            self.click(p, "[data-tile-editor] [data-done]")
            self.assertTrue(wait(lambda: len(self.body().get("bespoke", [])) == 1, 10), f"stored: {self.body()}")
            self.assertEqual(sorted(self.body()["bespoke"][0]), ["figure", "id", "label"])

    def test_K6_the_pencil_shows_the_stored_colour_and_a_second_press_closes_it(self):
        self.seed([{**OWN, "tone": "blue"}])
        with chrome() as cdp:
            p = self.page(cdp)
            pen = self.q("[data-tile=t1] [data-tile-pencil]")
            self.assertEqual(p.js(f"document.querySelector({pen}).getAttribute('aria-expanded')"), "false")
            self.pencil(p)
            self.assertEqual(p.js(f"document.querySelector({pen}).getAttribute('aria-expanded')"), "true")
            self.assertEqual(p.js(f"document.querySelector({self.q('[data-tile-editor] [aria-checked=true]')}).dataset.tone"), "blue")
            self.click(p, "[data-tile=t1] [data-tile-pencil]")
            p.until(f"!document.querySelector({self.q('[data-tile-editor]')})", "the second press closed it")

    def test_K7_done_keeps_the_hidden_flag_of_the_tile(self):
        self.seed([{**OWN, "hidden": True}])
        with chrome() as cdp:
            p = self.page(cdp)
            self.assertEqual(p.js(f"document.querySelectorAll({self.q('[data-tile=t1]')}).length"), 0, "a hidden own tile is not drawn in Edit, so it has no pencil (row 1303)")
            self.assertIs(self.body()["bespoke"][0].get("hidden"), True)

    def test_K8_done_with_nothing_changed_closes_silently_and_makes_no_step(self):
        self.seed([OWN])
        with chrome() as cdp:
            p = self.page(cdp)
            self.pencil(p)
            before = self.applies()
            self.click(p, "[data-tile-editor] [data-done]")
            p.until(f"!document.querySelector({self.q('[data-tile-editor]')})", "the editor closed")
            self.assertEqual(self.toast(p), "", "nothing changed: no toast")
            self.assertEqual(self.applies(), before, "no step")

    def test_K9_the_error_mark_is_on_the_label_only_and_only_after_done_was_tried(self):
        self.seed([OWN])
        with chrome() as cdp:
            p = self.page(cdp)
            self.pencil(p)
            self.fill(p, "label", "")
            self.fill(p, "figure", "")
            self.fill(p, "tag", "")
            self.assertEqual(p.js(f"document.querySelectorAll({self.q('[data-tile-editor] .inp.bad')}).length"), 0, "no mark before Done")
            self.click(p, "[data-tile-editor] [data-done]")
            p.until(f"document.querySelectorAll({self.q('[data-tile-editor] .inp.bad')}).length > 0", "the mark")
            self.assertEqual(p.js(f"[...document.querySelectorAll({self.q('[data-tile-editor] .inp.bad')})].map(i => i.dataset.f)"), ["label"])

    def test_K10_remove_tile_closes_the_editor_and_puts_the_focus_on_add_a_tile(self):
        self.seed([OWN])
        with chrome() as cdp:
            p = self.page(cdp)
            self.pencil(p)
            self.click(p, "[data-tile-editor] [data-remove]")
            self.assertTrue(wait(lambda: not self.body().get("bespoke"), 10), f"stored: {self.body()}")
            p.until(f"!document.querySelector({self.q('[data-tile-editor]')})", "the editor closed")
            p.until("document.activeElement.classList.contains('tileadd')", "focus on Add a tile")

    def test_K11_arrows_move_the_colour_with_wrap_and_only_the_checked_one_is_in_the_tab_order(self):
        self.seed([{**OWN, "tone": "green"}])
        with chrome() as cdp:
            p = self.page(cdp)
            self.pencil(p)
            tab = lambda: p.js(f"[...document.querySelectorAll({self.q('[data-tile-editor] [role=radio]')})].map(b => b.tabIndex)")  # noqa: E731
            checked = lambda: p.js(f"document.querySelector({self.q('[data-tile-editor] [aria-checked=true]')}).dataset.tone")  # noqa: E731
            self.assertEqual(tab(), [0, -1, -1, -1, -1])
            p.js(f"document.querySelector({self.q('[data-tile-editor] [data-tone=green]')}).focus()")
            p.key("ArrowDown", 0, code="ArrowDown", vk=40)
            self.assertTrue(wait(lambda: checked() == "amber", 5), checked())
            p.until("document.activeElement.dataset.tone === 'amber'", "the focus follows the pick")
            p.key("ArrowUp", 0, code="ArrowUp", vk=38)
            self.assertTrue(wait(lambda: checked() == "green", 5), checked())
            p.until("document.activeElement.dataset.tone === 'green'", "the focus follows the pick")
            p.key("ArrowUp", 0, code="ArrowUp", vk=38)
            self.assertTrue(wait(lambda: checked() == "neutral", 5), "up from the first wraps to the last: " + checked())
            p.until("document.activeElement.dataset.tone === 'neutral'", "the focus follows the pick")
            p.key("ArrowRight", 0, code="ArrowRight", vk=39)
            self.assertTrue(wait(lambda: checked() == "green", 5), "right from the last wraps to the first: " + checked())

    def second_section(self, bespoke):
        with self.store.step("dashboard", USER) as st:
            other = st.create("report_sections", {"project": "ABC", "type": "glancetemplate", "title": "Fictional other glance", "sort_order": 999})
        status, got = self.real_change({"project": "ABC", "kind": KIND, "op": "update", "id": other,
                                        "changes": {"body": json.dumps({"v": 1, "bespoke": bespoke})}})
        self.assertEqual(status, 200, got)
        return other

    def test_K12_an_open_editor_shows_only_under_the_tile_of_its_own_section_even_when_ids_match(self):
        self.seed([OWN])
        other = self.second_section([OWN])
        with chrome() as cdp:
            p = self.page(cdp)
            p.until(f"!!document.querySelector('[data-id=\"{other}\"] [data-tile=t1]')", "the other section drew")
            self.pencil(p)
            self.assertEqual(p.js(f"document.querySelectorAll('[data-id=\"{other}\"] [data-tile-editor]').length"), 0, "no editor in the other section")
            self.assertEqual(p.js(f"document.querySelector('[data-id=\"{other}\"] [data-tile-pencil]').getAttribute('aria-expanded')"), "false")
            self.assertEqual(p.js(f"document.querySelectorAll({self.q('[data-tile-editor]')}).length"), 1)

    def test_K13_a_new_tile_draft_is_not_drawn_in_another_section_that_has_the_same_new_id(self):
        self.seed([OWN])
        other = self.second_section([OWN])
        with chrome() as cdp:
            p = self.page(cdp)
            p.until(f"!!document.querySelector('[data-id=\"{other}\"] .tileadd')", "the other section drew")
            self.open_add(p)
            p.js("document.querySelector('.ddmenu[role=menu] [role=menuitem]').click()")
            self.editor_open(p)
            self.assertEqual(p.js(f"document.querySelectorAll('[data-id=\"{other}\"] .pending').length"), 0)
            self.assertEqual(p.js(f"document.querySelectorAll('[data-id=\"{other}\"] [data-tile-editor]').length"), 0)
            self.assertEqual(p.js(f"document.querySelectorAll({self.q('.pending [data-tile-editor]')}).length"), 1)

    def test_K14_the_bin_of_an_open_tile_leaves_no_editor_to_come_back_with_an_undo(self):
        self.seed([OWN])
        with chrome() as cdp:
            p = self.page(cdp)
            self.pencil(p)
            self.click(p, "[data-tile=t1] [data-tile-bin]")
            self.assertTrue(wait(lambda: not self.body().get("bespoke"), 10), f"stored: {self.body()}")
            p.until(f"!document.querySelector({self.q('[data-tile-editor]')})", "the editor closed")
            self.undo(p)
            p.until(f"!!document.querySelector({self.q('[data-tile=t1]')})", "the tile is back")
            self.assertEqual(p.js(f"document.querySelectorAll({self.q('[data-tile-editor]')}).length"), 0, "no editor came back")
            self.assertEqual(p.js(f"document.querySelector({self.q('[data-tile=t1] [data-tile-pencil]')}).getAttribute('aria-expanded')"), "false")

    def test_K15_the_error_mark_and_its_words_show_on_the_label_field_alone(self):
        self.seed([OWN])
        with chrome() as cdp:
            p = self.page(cdp)
            self.pencil(p)
            for name in ("label", "figure", "tag", "note"):
                self.fill(p, name, "")
            self.click(p, "[data-tile-editor] [data-done]")
            p.until(f"document.querySelectorAll({self.q('[data-tile-editor] .err')}).length > 0", "the error")
            self.assertEqual(p.js(f"document.querySelectorAll({self.q('[data-tile-editor] .err')}).length"), 1)
            self.assertEqual(p.js(f"document.querySelectorAll({self.q('[data-tile-editor] [aria-invalid=true]')}).length"), 1)

    def test_K16_esc_in_the_editor_does_not_reach_a_listener_on_the_section(self):
        self.seed([OWN])
        with chrome() as cdp:
            p = self.page(cdp)
            self.pencil(p)
            p.js(f"window.__esc = 0; document.querySelector({self.q('')}).addEventListener('keydown', function (e) {{ if (e.key === 'Escape') window.__esc++; }});")
            p.key("Escape", 0, code="Escape", vk=27)
            p.until(f"!document.querySelector({self.q('[data-tile-editor]')})", "closed by Esc")
            self.assertEqual(p.js("window.__esc"), 0, "Esc stopped at the editor")

    def test_K17_done_and_remove_pressed_again_after_the_editor_closed_do_nothing(self):
        self.seed([OWN])
        with chrome() as cdp:
            p = self.page(cdp)
            p.js("window.__rej = 0; window.addEventListener('unhandledrejection', function () { window.__rej++; });")
            self.pencil(p)
            p.js(f"window.__done = document.querySelector({self.q('[data-tile-editor] [data-done]')}); window.__rm = document.querySelector({self.q('[data-tile-editor] [data-remove]')});")
            self.fill(p, "label", "Fictional changed")
            self.click(p, "[data-tile-editor] [data-done]")
            self.assertTrue(wait(lambda: self.body()["bespoke"][0].get("label") == "Fictional changed", 10), f"stored: {self.body()}")
            p.until(f"!document.querySelector({self.q('[data-tile-editor]')})", "the editor closed")
            before = self.applies()
            p.js("window.__done.click(); window.__rm.click();")
            p.js("new Promise(r => setTimeout(r, 700))")
            self.assertEqual(p.js("window.__rej"), 0, "no error")
            self.assertEqual(self.applies(), before, "no step")
            self.assertEqual(self.body()["bespoke"][0]["label"], "Fictional changed")

    def test_K18_moving_a_built_in_tile_to_the_end_puts_it_after_the_tiles_typed(self):
        self.seed([OWN])
        with chrome() as cdp:
            p = self.page(cdp)
            p.js(f"document.querySelector({self.q('[data-tile=decisions] [data-tile-grip]')}).focus()")
            p.key("ArrowRight", ALT, code="ArrowRight", vk=39)
            self.assertTrue(wait(lambda: self.body().get("order") is not None, 10), f"stored: {self.body()}")
            self.assertEqual(self.body()["order"], ["health", "overdue", "risks", "t1", "decisions"])

    def test_K19_an_own_tile_has_no_outline_menu_on_a_right_click(self):
        self.seed([OWN])
        with chrome() as cdp:
            p = self.page(cdp)
            p.js(f"document.querySelector({self.q('[data-tile=t1]')}).dispatchEvent(new MouseEvent('contextmenu', {{bubbles: true, cancelable: true}}))")
            p.js("new Promise(r => setTimeout(r, 300))")
            self.assertEqual(p.js(f"document.querySelectorAll('[data-outline]').length"), 0, "no outline menu on an own tile")
            p.js(f"document.querySelector({self.q('[data-tile=decisions]')}).dispatchEvent(new MouseEvent('contextmenu', {{bubbles: true, cancelable: true}}))")
            p.until(f"document.querySelectorAll('[data-outline]').length > 0", "a counting tile still has it")


if __name__ == "__main__":
    unittest.main()
