"""#96 G4, the Key dates template (store type keydates): its checker, one step and one Undo, the published file (a hidden, archived,
cancelled or section-hidden milestone is absent, an empty template stays out), the served View and Edit, and the file drawn at 1400 and
900 px in light and dark.

Run: python3 dev/run_tests.py test_tpl_keydates
Needs Chrome (the #33 harness): the page tests fail, never skip, without it. Fictional data only.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from test_changes import Api
from test_report_editor import EMPTY_BRANDING, Base, Pg, tearDownModule  # noqa: F401
from test_server import chrome, wait

from clark import changes, publish, section_bodies, section_kinds, store as store_module
from clark.section_kinds import base, keydates

MARK = "ZQ-KEYDATES-MARK"


def body(*items):
    return json.dumps({"v": 1, "items": list(items)})


def typed(label="Go live", date="2030-02-01"):
    return {"label": label, "date": date}


def milestone(ref):
    return {"milestone": ref}


class Checker(unittest.TestCase):
    def check(self, text):
        return store_module.check_section_body("keydates", text)

    def refuses(self, text):
        with self.assertRaises(store_module.Invalid) as got:
            self.check(text)
        self.assertNotIn(MARK, str(got.exception), "a refusal never quotes the content")
        return str(got.exception)

    def test_the_module_is_built_and_ready(self):
        self.assertIs(section_kinds.REGISTRY["keydates"], keydates)
        self.assertTrue(keydates.READY)
        self.assertEqual(section_bodies.EMPTY["keydates"], "")
        self.assertEqual(self.check(""), "", "no content is no content")

    def test_good_content_is_stored_canonical_and_stable(self):
        text = self.check(body(typed("Go live", "2030-02-01"), milestone("ABC-M-001")))
        self.assertEqual(json.loads(text), {"v": 1, "items": [typed(), milestone("ABC-M-001")]})
        self.assertEqual(self.check(text), text, "saving it again changes nothing")
        self.assertEqual(json.loads(self.check(body())), {"v": 1, "items": []})
        self.assertEqual(json.loads(self.check(body(typed("29 February", "2032-02-29"))))["items"][0]["date"], "2032-02-29", "a real leap day")

    def test_the_shape_is_checked_field_by_field(self):
        for bad in ('{"v":1}', '{"items":[]}', '{"v":2,"items":[]}', '{"v":true,"items":[]}', '{"v":1,"items":{}}', '{"v":1,"items":[],"x":1}',
                    '[]', '{"v":1,"items":["ABC-M-001"]}', '{"v":1,"items":[[]]}', '{"v":1,"items":[null]}'):
            with self.subTest(bad=bad):
                self.refuses(bad)

    def test_an_item_is_a_milestone_or_a_typed_date_and_nothing_else(self):
        for item in ({"milestone": "ABC-M-001", "label": "x"}, {"milestone": "ABC-M-001", "date": "2030-01-01"}, {"label": "Go live"},
                     {"date": "2030-01-01"}, {"label": "x", "date": "2030-01-01", "extra": 1}, {}, {"milestone": 1}, {"milestone": None},
                     {"milestone": "abc-m-001"}, {"milestone": "ABC-A-001"}, {"milestone": "ABC-M-1"}, {"milestone": "ABC-M-001 "},
                     {"milestone": "ABC-M-001\n"}, {"milestone": "../ABC-M-001"}, {"milestone": "ABC-M-001<b>"}):
            with self.subTest(item=item):
                self.refuses(body(item))

    def test_a_typed_label_is_plain_visible_text_of_at_most_120_characters(self):
        self.check(body(typed("x" * 120)))
        for label in ("", " ", " Go live", "Go live ", "x" * 121, "Go\nlive", "Go‮live", "Go​live", "Go\u0000live", None, 5, ["a"], "\ud800"):
            with self.subTest(label=label):
                self.refuses(body(typed(label)) if label != "\ud800" else '{"v":1,"items":[{"label":"\\ud800","date":"2030-01-01"}]}')

    def test_a_typed_day_is_a_real_day_in_the_stored_form(self):
        for day in ("2030-02-31", "2030-13-01", "2030-00-10", "soon", "", "15-01-2030", "2030-1-5", "2030-01-15T10:00", "2030-01-15 ", None, 20300115,
                    "２０３０-０１-１５", "0000-01-01"):
            with self.subTest(day=day):
                self.refuses(body(typed("Go live", day)))

    def test_a_milestone_is_in_the_list_once_and_the_list_is_at_most_twelve(self):
        self.refuses(body(milestone("ABC-M-001"), milestone("ABC-M-001")))
        self.check(body(*[typed(f"Date {n}") for n in range(12)]))
        self.refuses(body(*[typed(f"Date {n}") for n in range(13)]))
        self.refuses(body(*[milestone(f"ABC-M-{n:03d}") for n in range(1, 14)]))

    def test_the_hostile_generic_cases_are_refused_before_the_shape(self):
        self.refuses("{" * 5000)
        self.refuses('{"v":1,"items":[],"v":1}')
        self.refuses('{"v":1,"items":[{"label":"a","date":"2030-01-01"}],"items":[]}')
        self.refuses('{"v":1.5,"items":[]}')
        self.refuses("x" * (keydates.LIMIT + 1))
        self.refuses(json.dumps({"v": 1, "items": [typed("x" * 120, "2030-01-01")] * 12}) + " " * keydates.LIMIT)
        self.refuses(json.dumps({"v": 1, "items": [typed("\U0001F600" * 120)] * 13}))

    def test_the_limit_fits_the_change_route(self):
        from clark import server as sv
        self.assertGreaterEqual(sv.ROUTE_BODY_LIMITS["/api/change"], keydates.LIMIT + 8 * 1024)
        worst = body(*[typed("é" * 120) for _ in range(12)])
        self.assertLessEqual(len(self.check(worst)), keydates.LIMIT, "the largest valid content fits its limit")

    def test_published_keeps_typed_dates_and_only_the_milestones_the_file_kept(self):
        ctx = base.Context({"milestones": [{"id": "ABC-M-001", "status": "Planned"}, {"id": "ABC-M-003", "status": "Cancelled"}]}, "2030-01-15")
        value = json.loads(self.check(body(milestone("ABC-M-001"), milestone("ABC-M-002"), milestone("ABC-M-003"), typed())))
        self.assertEqual(keydates.published(value, ctx), {"v": 1, "items": [milestone("ABC-M-001"), typed()]})
        only_gone = json.loads(self.check(body(milestone("ABC-M-002"), milestone("ABC-M-003"))))
        self.assertIsNone(keydates.published(only_gone, ctx), "nothing left, so the section stays out")
        self.assertIsNone(section_bodies.published("keydates", json.loads(self.check(body())), ctx))
        self.assertIsNone(section_bodies.published("keydates", only_gone, base.Context()), "no context, no milestone")


class Stored(Api):
    def make(self, title="Key dates"):
        return self.ok("new", values={"type": "keydates", "title": title}, after=None)["ref"]

    def write(self, ref, text):
        return self.change(self.req(changes.UPDATE, id=ref, changes={"body": text}))

    def test_one_change_is_one_step_and_one_undo_puts_the_old_body_back(self):
        ref = self.make()
        first = self.write(ref, body(typed()))[1]
        second = self.write(ref, body(typed(), typed("Review", "2030-03-01")))[1]
        self.assertEqual(self.s.con.execute("SELECT count(*) FROM applies WHERE apply_id IN (?, ?)", (first["apply_id"], second["apply_id"])).fetchone()[0], 2)
        self.assertEqual(self.undo({"project": "ABC", "apply_id": second["apply_id"]})[0], 200)
        self.assertEqual(json.loads(self.s.read("report_sections", ref=ref)["body"])["items"], [typed()])
        self.assertEqual(self.undo({"project": "ABC", "apply_id": first["apply_id"]})[0], 200)
        self.assertEqual(self.s.read("report_sections", ref=ref)["body"], "")

    def test_a_refused_body_writes_nothing(self):
        ref = self.make()
        self.write(ref, body(typed()))
        before = self.snapshot()
        status, got = self.write(ref, body(typed("Go live", "2030-02-31")))
        self.assertEqual((status, got["ok"]), (400, False))
        self.assertEqual(got["message"], keydates.BAD_DAY)
        self.assertEqual(self.snapshot(), before)


class Published(Api):
    def plant(self):
        with self.s.step("dashboard", USER) as st:
            self.ok_ms = st.create("milestones", {"project": "ABC", "name": f"{MARK} kept", "baseline_date": "2030-04-01", "source": "demo"})
            self.hid_ms = st.create("milestones", {"project": "ABC", "name": f"{MARK} hidden", "baseline_date": "2030-05-01", "source": "demo"})
            self.arc_ms = st.create("milestones", {"project": "ABC", "name": f"{MARK} archived", "baseline_date": "2030-06-01", "source": "demo"})
            self.can_ms = st.create("milestones", {"project": "ABC", "name": f"{MARK} cancelled", "baseline_date": "2030-07-01", "source": "demo", "status": "Cancelled"})
            st.create("report_hidden", {"project": "ABC", "item_id": self.hid_ms})
        with self.s.step("dashboard", USER) as st:
            st.archive("milestones", self.arc_ms)

    def section(self, items, title="Key dates"):
        ref = self.ok("new", values={"type": "keydates", "title": title}, after=None)["ref"]
        self.assertEqual(self.change(self.req(changes.UPDATE, id=ref, changes={"body": body(*items)}))[0], 200)
        return ref

    def built(self):
        out = publish.build(self.s, "ABC", now="2030-01-15")
        return out["published"], out["body"].decode("utf-8")

    def test_only_what_the_file_keeps_is_published(self):
        self.plant()
        ref = self.section([milestone(self.ok_ms), milestone(self.hid_ms), milestone(self.arc_ms), milestone(self.can_ms), typed(f"{MARK} typed", "2030-02-01")])
        built, text = self.built()
        sec = next(s for s in built["sections"] if s["id"] == ref)
        self.assertEqual(sec["items"], [milestone(self.ok_ms), typed(f"{MARK} typed", "2030-02-01")])
        for gone in (self.hid_ms, self.arc_ms, f"{MARK} hidden", f"{MARK} archived"):
            self.assertNotIn(gone, text)
        self.assertNotIn(self.can_ms, json.dumps(sec), "a cancelled milestone's date is not in the section")
        self.assertIn(f"{MARK} typed", text)
        self.assertIn(f"{MARK} kept", text, "the kept milestone is in the file's own milestones")

    def test_an_empty_template_and_one_with_nothing_left_stay_out_and_the_neighbour_takes_the_row(self):
        self.plant()
        empty = self.ok("new", values={"type": "keydates", "title": "Fictional empty dates"}, after=None)["ref"]
        gone = self.section([milestone(self.hid_ms), milestone(self.can_ms)], "Fictional gone dates")
        text_ref = self.ok("new", values={"type": "text", "title": "Fictional notes"}, after=gone)["ref"]
        self.change(self.req(changes.UPDATE, id=gone, changes={"beside": 1}))
        built, text = self.built()
        ids = [s["id"] for s in built["sections"]]
        self.assertNotIn(empty, ids)
        self.assertNotIn(gone, ids)
        self.assertNotIn("Fictional empty dates", text)
        self.assertNotIn("Fictional gone dates", text)
        self.assertEqual(next(s for s in built["sections"] if s["id"] == text_ref)["beside"] if text_ref in ids else 0, 0)

    def test_a_hidden_milestones_section_takes_its_dates_out_of_the_file(self):
        self.plant()
        ref = self.section([milestone(self.ok_ms), typed(f"{MARK} typed")])
        ms = next(r for r in self.s.read("report_sections", "ABC") if r["type"] == "milestones")
        self.assertEqual(self.change(self.req(changes.UPDATE, id=ms["id"], changes={"hidden": 1}))[0], 200)
        built, text = self.built()
        sec = next(s for s in built["sections"] if s["id"] == ref)
        self.assertEqual(sec["items"], [typed(f"{MARK} typed")], "the milestone's date goes with its section")
        self.assertNotIn(f"{MARK} kept", text)

    def test_a_hidden_keydates_section_is_not_in_the_file(self):
        self.plant()
        ref = self.section([typed(f"{MARK} typed")])
        self.assertEqual(self.change(self.req(changes.UPDATE, id=ref, changes={"hidden": 1}))[0], 200)
        built, text = self.built()
        self.assertNotIn(ref, [s["id"] for s in built["sections"]])
        self.assertNotIn(f"{MARK} typed", text)

    def test_the_file_carries_no_edit_part_and_no_server_route_for_it(self):
        self.plant()
        self.section([typed(f"{MARK} typed")])
        _, text = self.built()
        for owner_only in ("tple-", "Take a date from a milestone", "/api/change"):
            self.assertNotIn(owner_only, text)


LATER = "2099-12-31"


class InThePage(Base):
    """The served page: View draws the dates, Edit fills them in place, in a real browser."""

    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            self.m2 = st.create("milestones", {"project": "ABC", "name": "Second gate", "baseline_date": "2030-05-01", "source": "demo"})
            self.m_hid = st.create("milestones", {"project": "ABC", "name": f"{MARK} cancelled", "baseline_date": "2030-06-01", "source": "demo", "status": "Cancelled"})
            self.ref = st.create("report_sections", {"project": "ABC", "type": "keydates", "title": "Key dates", "sort_order": 999,
                                                       "body": body(milestone(self.demo.milestone), milestone(self.m2), milestone(self.m_hid), typed("Board meeting", "2030-04-10"))})

    def page(self, cdp):
        p = self.visit(cdp)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, p.sid)      # a headless page is otherwise not focused, so blur() fires nothing
        return p

    def shown(self, p):
        return p.js(f"[...document.querySelectorAll('[data-id=\"{self.ref}\"] .tpl-dates-row')].map(r => [...r.children].map(c => c.textContent))")

    def stored(self):
        return json.loads(self.store.read("report_sections", ref=self.ref)["body"])["items"]

    def test_view_draws_the_dates_soonest_first_in_dd_mm_yyyy_and_leaves_out_a_cancelled_milestone(self):
        for width, dark in ((1400, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.page(cdp)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                if dark:
                    p.js("document.documentElement.dataset.theme = 'dark'")
                p.until(f"!!document.querySelector('[data-id=\"{self.ref}\"] .tpl-dates-row')", "the dates drew")
                got = self.shown(p)
                self.assertEqual([r[:2] for r in got], [["01-03-2030", "Pilot live"], ["10-04-2030", "Board meeting"], ["01-05-2030", "Second gate"]])
                self.assertNotIn(MARK, p.js(f"document.querySelector('[data-id=\"{self.ref}\"]').textContent"))
                self.assertEqual(p.js(f"document.querySelectorAll('[data-id=\"{self.ref}\"] input, [data-id=\"{self.ref}\"] button, [data-id=\"{self.ref}\"] select').length"), 0, "View is read only")
                self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")

    def test_view_leaves_the_section_out_while_it_has_nothing_to_show(self):
        with self.store.step("dashboard", USER) as st:
            empty = st.create("report_sections", {"project": "ABC", "type": "keydates", "title": "Fictional empty dates", "sort_order": 1000})
        with chrome() as cdp:
            p = self.page(cdp)
            self.assertFalse(p.js(f"!!document.querySelector('[data-id=\"{empty}\"]')"))
            p.edit()
            p.until(f"!!document.querySelector('[data-id=\"{empty}\"] .tple-empty')", "Edit shows the empty state")
            self.assertIn("No dates yet.", p.js(f"document.querySelector('[data-id=\"{empty}\"] .tple-empty').textContent"))

    def fill(self, p, selector, text):
        p.js(f"(function(){{var e=document.querySelector({json.dumps(selector)}); e.focus(); e.value={json.dumps(text)};}})()")

    def test_edit_adds_a_typed_date_in_one_step_and_undo_takes_it_back(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.edit()
            sec = f'[data-id="{self.ref}"]'
            p.until(f"!!document.querySelector('{sec} .tple-typed')", "the form")
            self.fill(p, f"{sec} .tple-typed [name=label]", "Go live")
            self.fill(p, f"{sec} .tple-typed [name=date]", "15-06-2030")
            p.js(f"document.querySelector('{sec} .tple-typed button').click()")
            p.saved()
            self.assertEqual(self.stored()[-1], typed("Go live", "2030-06-15"))
            self.assertEqual(p.toast(), "Date added.")
            applies = self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]
            p.js("document.querySelector('[data-undo]').click()")
            self.assertTrue(wait(lambda: self.stored()[-1] == typed("Board meeting", "2030-04-10"), 10), "Undo took the date back")
            self.assertEqual(self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0], applies + 1, "an Undo is one step")

    def test_edit_refuses_an_unreadable_day_in_plain_words_and_writes_nothing(self):
        before = self.stored()
        with chrome() as cdp:
            p = self.page(cdp)
            p.edit()
            sec = f'[data-id="{self.ref}"]'
            p.until(f"!!document.querySelector('{sec} .tple-typed')", "the form")
            self.fill(p, f"{sec} .tple-typed [name=label]", "Go live")
            self.fill(p, f"{sec} .tple-typed [name=date]", "31-02-2030")
            p.js(f"document.querySelector('{sec} .tple-typed button').click()")
            p.until("!!document.querySelector('.toast-text')", "a message")
            self.assertEqual(p.toast(), "That isn't a day clark can read. Type it as DD-MM-YYYY, for example 15-01-2030.")
            self.assertEqual(self.stored(), before)
            self.assertFalse(p.toast().startswith("clark"), "a message never starts with the product name")

    def test_edit_takes_a_milestone_changes_a_typed_date_and_removes_one(self):
        with self.store.step("dashboard", USER) as st:
            m3 = st.create("milestones", {"project": "ABC", "name": "Third gate", "baseline_date": "2030-08-01", "source": "demo"})
        with chrome() as cdp:
            p = self.page(cdp)
            p.edit()
            sec = f'[data-id="{self.ref}"]'
            p.until(f"!!document.querySelector('{sec} select')", "the list")
            self.assertEqual(p.js(f"[...document.querySelectorAll('{sec} select option')].map(o => o.textContent)"), ["Choose a milestone…", "Third gate"], "taken ones are not offered again")
            p.js(f"(function(){{var s=document.querySelector('{sec} select'); s.value={json.dumps(m3)}; s.dispatchEvent(new Event('change', {{bubbles: true}}));}})()")
            p.saved()
            self.assertEqual(self.stored()[-1], milestone(m3))
            self.fill(p, f"{sec} input[aria-label='Date, DD-MM-YYYY']", "11-04-2030")
            p.js(f"document.querySelector('{sec} input[aria-label=\"Date, DD-MM-YYYY\"]').blur()")
            self.assertTrue(wait(lambda: typed("Board meeting", "2030-04-11") in self.stored(), 10), "the day was changed where it was")
            p.js(f"document.querySelector('{sec} button[aria-label=\"Remove Board meeting\"]').click()")
            self.assertTrue(wait(lambda: not any(i.get("label") == "Board meeting" for i in self.stored()), 10))

    def test_edit_is_reachable_by_keyboard(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.edit()
            sec = f'[data-id="{self.ref}"]'
            p.until(f"!!document.querySelector('{sec} .tple-typed')", "the form")
            self.assertEqual(p.js(f"[...document.querySelectorAll('{sec} .tple input, {sec} .tple select, {sec} .tple button')].filter(e => e.tabIndex < 0).length"), 0)
            p.js(f"document.querySelector('{sec} .tple-typed [name=label]').focus()")
            p.type("Kick-off")
            p.key("Tab", code="Tab", vk=9)
            p.type("01-07-2030")
            for kind in ("keyDown", "keyUp"):
                cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "text": "\r"}, p.sid)
            self.assertTrue(wait(lambda: typed("Kick-off", "2030-07-01") in self.stored(), 10), "Enter in the form adds the date")


class TheFile(Base):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            self.m_hid = st.create("milestones", {"project": "ABC", "name": f"{MARK} hidden", "baseline_date": "2030-06-01", "source": "demo"})
            st.create("report_hidden", {"project": "ABC", "item_id": self.m_hid})
            st.create("report_sections", {"project": "ABC", "type": "keydates", "title": "Key dates", "sort_order": 999,
                                          "body": body(milestone(self.demo.milestone), milestone(self.m_hid), typed("Board meeting", "2030-04-10"))})
            st.create("report_sections", {"project": "ABC", "type": "keydates", "title": "Fictional empty dates", "sort_order": 1000})
        self.out = tempfile.mkdtemp(prefix="clark-g4-")
        self.addCleanup(shutil.rmtree, self.out, ignore_errors=True)
        self.path = Path(publish.publish(self.store, "ABC", self.out, by_user=USER, now="2030-01-15", branding=EMPTY_BRANDING)["path"])

    def draw(self, cdp, width, dark):
        tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": self.path.as_uri()}, sid)
        p = Pg(self, cdp, sid)
        p.until("document.documentElement.dataset.ready === '1' && !!document.querySelector('h1')", "the file drew")
        if dark:
            p.js("document.documentElement.dataset.theme = 'dark'")
        return p

    def test_the_file_draws_the_dates_read_only_with_the_files_own_milestones_and_nothing_hidden(self):
        text = self.path.read_text(encoding="utf-8")
        self.assertNotIn(MARK, text)
        self.assertNotIn("Fictional empty dates", text)
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.draw(cdp, width, dark)
                rows = p.js("[...document.querySelectorAll('[data-tpl=keydates] .tpl-dates-row')].map(r => [...r.children].map(c => c.textContent))")
                self.assertEqual([r[:2] for r in rows], [["01-03-2030", "Pilot live"], ["10-04-2030", "Board meeting"]])
                self.assertEqual(p.js("document.querySelectorAll('[data-tpl=keydates] input, [data-tpl=keydates] button, [data-tpl=keydates] select, [data-tpl=keydates] a').length"), 0)
                self.assertEqual(p.js("document.querySelectorAll('.sec[data-type=keydates]').length"), 1, "the empty one is not drawn")
                self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"))

    def test_text_contrast_is_at_least_4_5_to_1_in_light_and_dark(self):
        script = """(() => {
          const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
          const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
          const ratio = (a, b) => { const x = lum(rgb(a)), y = lum(rgb(b)); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
          const out = [];
          for (const sel of ['.tpl-dates-day', '.tpl-dates-label', '.tpl-dates-words']) {
            const el = document.querySelector(sel); if (!el) { out.push([sel, 0]); continue; }
            let bg = el, back = 'rgba(0, 0, 0, 0)';
            while (bg && /rgba\\(.*, 0\\)|transparent/.test(back)) { back = getComputedStyle(bg).backgroundColor; bg = bg.parentElement; }
            out.push([sel, ratio(getComputedStyle(el).color, back)]);
          }
          return JSON.stringify(out);
        })()"""
        for dark in (False, True):
            with self.subTest(dark=dark), chrome() as cdp:
                p = self.draw(cdp, 1400, dark)
                for sel, ratio in json.loads(p.js(script)):
                    self.assertGreaterEqual(ratio, 4.5, sel)


if __name__ == "__main__":
    unittest.main()
