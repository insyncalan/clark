"""Row 1264 slice 6: killer tests (set C) for the Glance template's tile editor, in a real browser. They pin: two sections that both hold a tile with
the same id open one editor only, a Done that arrives after the editor closed does nothing, and a tile moved to the end goes after the own tiles.

Run: python3 dev/run_tests.py test_tpl_glance_editor_1264_killers_c
"""
import json

from _demo import USER
from test_changes import KIND
from test_report_editor import ALT, tearDownModule  # noqa: F401
from test_server import chrome, wait
from test_tpl_glance_editor_1264 import OWN, Editor


class Killers(Editor):
    def test_C80_an_editor_opens_in_its_own_section_only_when_two_sections_hold_the_same_tile_id(self):
        self.seed([OWN])
        with self.store.step("dashboard", USER) as st:
            other = st.create("report_sections", {"project": "ABC", "type": "glancetemplate", "title": "Fictional second glance", "sort_order": 999,
                                                  "body": json.dumps({"v": 1, "bespoke": [OWN]})})
        with chrome() as cdp:
            p = self.page(cdp)
            p.until(f"!!document.querySelector('[data-id=\"{other}\"] [data-tile=t1] [data-tile-pencil]')", "the second section drew")
            self.click(p, "[data-tile=t1] [data-tile-pencil]")
            self.editor_open(p)
            got = p.js(f"""(function(){{ var a = document.querySelector({json.dumps(f'[data-id="{self.ref}"] [data-tile=t1] [data-tile-pencil]')}),
              b = document.querySelector({json.dumps(f'[data-id="{other}"] [data-tile=t1] [data-tile-pencil]')});
              return {{first: a.getAttribute('aria-expanded'), second: b.getAttribute('aria-expanded'),
                       editors: document.querySelectorAll('[data-tile-editor]').length,
                       inSecond: document.querySelectorAll({json.dumps(f'[data-id="{other}"] [data-tile-editor]')}).length}}; }})()""")
            self.assertEqual(got, {"first": "true", "second": "false", "editors": 1, "inSecond": 0})

    def test_C83_a_done_that_arrives_after_the_editor_closed_does_nothing(self):
        self.seed([OWN])
        with chrome() as cdp:
            p = self.page(cdp)
            self.click(p, "[data-tile=t1] [data-tile-pencil]")
            self.editor_open(p)
            p.js(f"window.__done = document.querySelector({self.q('[data-tile-editor] [data-done]')}); window.__bad = 0;"
                 " window.addEventListener('unhandledrejection', () => { window.__bad++; });")
            self.click(p, "[data-tile-editor] [data-cancel]")
            p.until(f"!document.querySelector({self.q('[data-tile-editor]')})", "the editor closed")
            before = self.applies()
            p.js("window.__done.click()")
            p.js("new Promise(r => setTimeout(r, 400))")
            self.assertEqual(p.js("window.__bad"), 0, "no error from the late Done")
            self.assertEqual(self.applies(), before)
            self.assertFalse(p.js(f"!!document.querySelector({self.q('[data-tile-editor]')})"))

    def test_C88_a_built_in_tile_moved_to_the_end_goes_after_the_own_tiles(self):
        status, got = self.real_change({"project": "ABC", "kind": KIND, "op": "update", "id": self.ref, "changes": {"body": json.dumps(
            {"v": 1, "bespoke": [OWN], "order": ["overdue", "risks", "decisions", "health", "t1"]})}})
        assert status == 200, got
        with chrome() as cdp:
            p = self.page(cdp)
            p.js(f"document.querySelector({self.q('[data-tile=health] [data-tile-grip]')}).focus()")
            p.key("ArrowRight", ALT, code="ArrowRight", vk=39)
            self.assertTrue(wait(lambda: self.body().get("order") == ["overdue", "risks", "decisions", "t1", "health"], 10), f"stored: {self.body()}")
