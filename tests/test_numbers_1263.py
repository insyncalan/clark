"""Row 1263: the one Numbers card (store type figures4) that holds three or four numbers. The count control, the Typed | Live switch
of each number, the reading of both stored types (figures3 and figures4), and the published file. Fictional data only.

Run: python3 dev/run_tests.py test_numbers_1263
Needs Chrome (the page tests fail, never skip, without it).
"""
import json
import unittest

from _classic_page import classic
from _demo import USER
from _paths import SRC
from _tpl_figures import body, typed
from clark import docx_build, section_bodies, store as store_module
from clark.section_kinds import base
from test_report_editor import Base as PageBase
from test_server import chrome, wait

WIDTHS = (1400, 900)


def _shell(p, width):
    p.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)


class Section(PageBase):
    def setUp(self):
        super().setUp()
        classic(self)      # Classic is the look applied (row 1363): the page carries the theme's CSS

    def add(self, kind, raw):
        with self.store.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": kind, "title": "Numbers", "sort_order": 999})
            st.update("report_sections", ref, {"body": raw if isinstance(raw, str) else json.dumps(raw)})
        return ref

    def stored(self, ref):
        return json.loads(self.store.read("report_sections", ref=ref)["body"])

    def open_edit(self, cdp, ref, width):
        p = self.visit(cdp)
        _shell(p, width)
        p.edit()
        p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}] [data-slot]')", "Edit")
        return p


class Library(unittest.TestCase):
    def test_the_count_is_for_the_numbers_card_only_and_three_or_four(self):
        ok = lambda t, v: json.loads(section_bodies.check(t, json.dumps(v), store_module.BODY_RULES))
        self.assertEqual(ok("figures4", {"v": 1, "count": 3, "figures": [typed()] * 3})["count"], 3)
        self.assertEqual(ok("figures4", {"v": 1, "count": 4, "figures": [typed()] * 4})["count"], 4)
        self.assertNotIn("count", ok("figures4", {"v": 1, "figures": [typed()]}), "an old body is not given a count")
        self.assertEqual(len(ok("figures4", {"v": 1, "count": 3, "figures": [typed()] * 4})["figures"]), 4, "a 4th number is kept while the count is 3")
        for t, v in (("figures3", {"v": 1, "count": 3, "figures": []}), ("figures4", {"v": 1, "count": 2, "figures": []}),
                     ("figures4", {"v": 1, "count": "3", "figures": []}), ("figures4", {"v": 1, "count": True, "figures": []}),
                     ("figures4", {"v": 1, "count": 4, "figures": [typed()] * 5})):
            with self.subTest(t=t, v=v), self.assertRaises(base.Bad):
                section_bodies.check(t, json.dumps(v), store_module.BODY_RULES)

    def test_the_published_entry_carries_count_only_when_the_body_has_one(self):
        ctx = base.Context({}, "2030-01-15")
        pub = lambda t, v: section_bodies.published(t, v, ctx)
        rows = [typed(label=f"L{i}", value=str(i)) for i in range(4)]
        self.assertEqual(pub("figures4", {"v": 1, "count": 3, "figures": rows})["count"], 3)
        self.assertEqual([f["label"] for f in pub("figures4", {"v": 1, "count": 3, "figures": rows})["figures"]], ["L0", "L1", "L2"], "the kept 4th number is not published")
        self.assertEqual(pub("figures4", {"v": 1, "count": 3, "figures": [typed(label="", value=""), rows[1], rows[2], rows[3]]}).get("figures")[0]["label"], "L1", "a blank place does not pull the 4th in")
        self.assertNotIn("count", pub("figures4", {"v": 1, "figures": rows}))
        self.assertEqual(len(pub("figures4", {"v": 1, "figures": rows})["figures"]), 4)
        self.assertNotIn("count", pub("figures3", {"v": 1, "figures": rows}))
        self.assertEqual(len(pub("figures3", {"v": 1, "figures": rows})["figures"]), 3)

    def test_word_and_excel_do_not_draw_either_type_and_a_count_changes_nothing_there(self):
        self.assertNotIn("figures4", docx_build.TITLES)
        self.assertNotIn("figures3", docx_build.TITLES)
        src = (SRC / "clark" / "docx_build.py").read_text(encoding="utf-8")
        self.assertNotIn('"count"', src, "Word reads no count")


class Page(Section):
    def test_the_count_and_source_switches_are_the_mock_ups_size_in_light_and_dark_at_1400_and_900(self):
        ref = self.add("figures4", {"v": 1, "figures": [typed()]})
        sec = f"[data-id={json.dumps(ref)}]"
        probe = ("(function(s){return Array.from(document.querySelectorAll(s + ' [data-count] button, ' + s + ' [data-source] button')).map(function(b){"
                 "var r=b.getBoundingClientRect(), c=getComputedStyle(b); return [Math.round(r.height), r.width>=40, c.fontSize, c.borderTopLeftRadius, c.borderTopWidth, "
                 "b.getAttribute('aria-checked')==='true' ? c.fontWeight : '-']})})(" + json.dumps(sec) + ")")
        for width in WIDTHS:
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.open_edit(cdp, ref, width)
                    p.js(f"document.documentElement.dataset.theme = {json.dumps('dark' if dark else '')}")
                    got = p.js(probe)
                    self.assertEqual(len(got), 2 + 4 * 2, got)      # 3 and 4, then Typed and Live for each of four numbers
                    for h, wide, size, radius, border, weight in got:
                        self.assertEqual((h, wide, size, radius, border), (32, True, "14px", "8px", "1px"))
                    self.assertEqual({w for *_, w in got} - {"-"}, {"600"})
                    self.assertEqual(p.js(f"document.querySelector('{sec} [data-count]').getAttribute('aria-label')"), "How many numbers")
                    self.assertEqual(p.js(f"[...document.querySelectorAll('{sec} [data-count] button')].map(b => b.textContent + b.getAttribute('aria-checked')).join()"), "3false,4true")

    def test_a_new_numbers_section_with_a_count_of_three_draws_three_wider_columns(self):
        ref = self.add("figures4", {"v": 1, "count": 3, "figures": [typed(label=f"L{i}", value=str(i)) for i in range(3)]})
        sec = f"[data-id={json.dumps(ref)}]"
        cols = f"getComputedStyle(document.querySelector('{sec} .tpl-figs')).gridTemplateColumns.split(' ').length"
        for width, want in ((1400, 3), (900, 1)):      # AP3: three across at 1400, one column at 900 (rules-2.css; shell.css has no 900 rule)
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp)
                _shell(p, width)
                p.until(f"!!document.querySelector('{sec} .tpl-figs')", "View")
                self.assertEqual(p.js(f"document.querySelectorAll('{sec} [data-fig=figure]').length"), 3)
                self.assertEqual(p.js(cols), want)
        with chrome() as cdp:
            p = self.open_edit(cdp, ref, 1400)
            p.js(f"document.querySelector('{sec} [data-count] button:last-child').click()")
            self.assertTrue(wait(lambda: self.stored(ref).get("count") == 4, 10), self.stored(ref))
            p.until(f"document.querySelectorAll('{sec} [data-slot]').length === 4", "four places")
            p.js(f"document.querySelector('{sec} [data-count] button:first-child').click()")
            self.assertTrue(wait(lambda: self.stored(ref).get("count") == 3, 10), self.stored(ref))
            p.until(f"document.querySelectorAll('{sec} [data-slot]').length === 3 && !!document.querySelector('{sec} .tpl-slots.n3')", "three places")

    def test_a_filled_4th_number_survives_4_to_3_to_4_one_change_and_one_undo_each(self):
        rows = [typed(label=f"L{i}", value=str(i)) for i in range(4)]
        ref = self.add("figures4", {"v": 1, "figures": rows})
        sec = f"[data-id={json.dumps(ref)}]"
        n = lambda: self.store.read("report_sections", ref=ref)
        with chrome() as cdp:
            p = self.open_edit(cdp, ref, 1400)
            step = self.demo.last_step()
            p.clear_toast()
            p.js(f"document.querySelector('{sec} [data-count] button:first-child').click()")
            p.saved()
            self.assertEqual(self.stored(ref)["count"], 3)
            self.assertEqual(self.demo.last_step(), step + 1, "4 to 3 is one change")
            self.assertEqual([f["label"] for f in self.stored(ref)["figures"]], ["L0", "L1", "L2", "L3"], "4 to 3 keeps the 4th number stored")
            p.until(f"document.querySelectorAll('{sec} [data-slot]').length === 3", "three drawn")
            p.clear_toast()
            p.js(f"document.querySelector('{sec} [data-count] button:last-child').click()")
            p.saved()
            self.assertEqual(self.stored(ref)["count"], 4)
            self.assertEqual(self.demo.last_step(), step + 2, "3 to 4 is one change")
            p.until(f"document.querySelectorAll('{sec} [data-slot]').length === 4", "four drawn")
            self.assertEqual(p.js(f"document.querySelector('{sec} [data-slot=\"3\"] input').value"), "L3", "the 4th number is back")
            self.assertEqual([f["label"] for f in self.stored(ref)["figures"]], ["L0", "L1", "L2", "L3"])
            p.js("document.querySelector('[data-undo]').click()")      # one Undo takes back the 3 to 4 only
            self.assertTrue(wait(lambda: self.stored(ref).get("count") == 3, 10), self.stored(ref))
            self.assertEqual(len(self.stored(ref)["figures"]), 4)
            p.until(f"document.querySelectorAll('{sec} [data-slot]').length === 3", "three drawn again")
            p.clear_toast()
            p.js(f"document.querySelector('{sec} [data-count] button:first-child').click()")      # already 3: nothing changes
            p.js(f"document.querySelector('{sec} [data-count] button:last-child').click()")
            p.saved()
            p.js("document.querySelector('[data-undo]').click()")
            self.assertTrue(wait(lambda: self.stored(ref).get("count") == 3 and len(self.stored(ref)["figures"]) == 4, 10), self.stored(ref))

    def test_each_number_has_a_typed_live_switch_then_its_fields(self):
        self.demo.plant_builtin_sections()
        ref = self.add("figures4", {"v": 1, "figures": [typed()]})
        sec = f"[data-id={json.dumps(ref)}]"
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                p = self.open_edit(cdp, ref, width)
                names = p.js(f"[...document.querySelectorAll('{sec} [data-slot=\"0\"] [data-source] button')].map(b => b.textContent + (b.disabled ? '!' : '')).join()")
                self.assertEqual(names, "Typed,Live")
                self.assertEqual(p.js(f"document.querySelectorAll('{sec} [data-slot=\"0\"] input').length"), 4, "typed: four fields")
                p.js(f"document.querySelector('{sec} [data-slot=\"0\"] [data-source] button:last-child').click()")
                self.assertTrue(wait(lambda: self.stored(ref)["figures"][0].get("mode") == "live", 10), self.stored(ref))
                p.until(f"document.querySelectorAll('{sec} [data-slot=\"0\"] input').length === 0", "a live number shows no typed fields")
                with self.store.step("dashboard", USER) as st:
                    st.update("report_sections", ref, {"body": store_module.check_section_body("figures4", body(typed()))})

    def test_live_is_disabled_when_no_live_figure_is_offered(self):
        ref = self.add("figures4", {"v": 1, "figures": [typed()]})      # a new project has no Actions, RAID or Decisions section
        with chrome() as cdp:
            p = self.open_edit(cdp, ref, 1400)
            self.assertEqual(p.js(f"document.querySelector('[data-id={json.dumps(ref)}] [data-slot=\"0\"] [data-source] button:last-child').disabled"), True)

    def test_an_old_figures3_and_an_old_figures4_section_draw_three_and_four_across_and_are_not_rewritten(self):
        three = self.add("figures3", {"v": 1, "figures": [typed(label=f"L{i}", value=str(i)) for i in range(3)]})
        four = self.add("figures4", {"v": 1, "figures": [typed(label=f"L{i}", value=str(i)) for i in range(4)]})
        before = [self.store.read("report_sections", ref=r)["body"] for r in (three, four)]
        for width, want in ((1400, (3, 4)), (900, (1, 1))):      # AP5: as before at 1400; at 900 the one-column rule applies to old sections too
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp)
                _shell(p, width)
                for ref, n, cols in ((three, 3, want[0]), (four, 4, want[1])):
                    sec = f"[data-id={json.dumps(ref)}]"
                    p.until(f"!!document.querySelector('{sec} .tpl-figs')", "View")
                    self.assertEqual(p.js(f"document.querySelectorAll('{sec} [data-fig=figure]').length"), n)
                    self.assertEqual(p.js(f"getComputedStyle(document.querySelector('{sec} .tpl-figs')).gridTemplateColumns.split(' ').length"), cols)
        self.assertEqual([self.store.read("report_sections", ref=r)["body"] for r in (three, four)], before, "viewing wrote nothing")
        with chrome() as cdp:
            p = self.open_edit(cdp, three, 1400)
            self.assertEqual(p.js(f"document.querySelectorAll('[data-id={json.dumps(three)}] [data-slot]').length"), 3)
            self.assertEqual(p.js(f"!!document.querySelector('[data-id={json.dumps(three)}] [data-count]')"), False, "figures3 has no count control")

    def test_nothing_overflows_at_900_with_four_numbers_in_edit(self):
        ref = self.add("figures4", {"v": 1, "figures": [typed(label=f"Label {i}", value=str(i)) for i in range(4)]})
        with chrome() as cdp:
            p = self.open_edit(cdp, ref, 900)
            self.assertEqual(p.js("document.documentElement.scrollWidth - document.documentElement.clientWidth"), 0)


if __name__ == "__main__":
    unittest.main()
