"""#96 G4, the Checklist template (store type checklist): its checker, one step and one Undo, the published file (a linked work item
that is hidden, archived, client-off or Sensitive is absent, an empty template stays out), the served View and Edit, and the file drawn
at 1400 and 900 px in light and dark.

Run: python3 dev/run_tests.py test_tpl_checklist
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
from clark.section_kinds import base, checklist

MARK = "ZQ-CHECKLIST-MARK"


def body(*items):
    return json.dumps({"v": 1, "items": list(items)})


def line(text="Send the plan", done=0):
    return {"text": text, "done": done}


def link(ref):
    return {"item": ref}


class Checker(unittest.TestCase):
    def check(self, text):
        return store_module.check_section_body("checklist", text)

    def refuses(self, text):
        with self.assertRaises(store_module.Invalid) as got:
            self.check(text)
        self.assertNotIn(MARK, str(got.exception), "a refusal never quotes the content")
        return str(got.exception)

    def test_the_module_is_built_and_ready(self):
        self.assertIs(section_kinds.REGISTRY["checklist"], checklist)
        self.assertTrue(checklist.READY)
        self.assertEqual(section_bodies.EMPTY["checklist"], "")
        self.assertEqual(self.check(""), "")

    def test_good_content_is_stored_canonical_and_stable(self):
        text = self.check(body(line("Send the plan", 1), link("ABC-A-001"), link("ABC-004"), link("ABC-D-002")))
        self.assertEqual(json.loads(text), {"v": 1, "items": [line("Send the plan", 1), link("ABC-A-001"), link("ABC-004"), link("ABC-D-002")]})
        self.assertEqual(self.check(text), text)
        self.assertEqual(json.loads(self.check(body())), {"v": 1, "items": []})

    def test_the_shape_is_checked_field_by_field(self):
        for bad in ('{"v":1}', '{"items":[]}', '{"v":2,"items":[]}', '{"v":true,"items":[]}', '{"v":1,"items":{}}', '{"v":1,"items":[],"x":1}',
                    '[]', '{"v":1,"items":["ABC-A-001"]}', '{"v":1,"items":[[]]}', '{"v":1,"items":[null]}'):
            with self.subTest(bad=bad):
                self.refuses(bad)

    def test_a_line_is_typed_or_linked_and_nothing_else(self):
        for item in ({"item": "ABC-A-001", "text": "x"}, {"item": "ABC-A-001", "done": 1}, {"text": "x"}, {"done": 1}, {}, {"text": "x", "done": 0, "more": 1},
                     {"item": 1}, {"item": None}, {"item": "abc-a-001"}, {"item": "ABC-M-001"}, {"item": "ABC-U-001"}, {"item": "ABC-A-1"},
                     {"item": "ABC-A-001 "}, {"item": "ABC-A-001\n"}, {"item": "../ABC-A-001"}, {"item": "ABC-A-001<b>"}):
            with self.subTest(item=item):
                self.refuses(body(item))

    def test_the_tick_is_zero_or_one_and_nothing_else(self):
        for done in (2, -1, True, False, None, "1", "yes", 0.5, [1]):
            with self.subTest(done=done):
                text = json.dumps({"v": 1, "items": [{"text": "x", "done": done}]})
                if done == 0.5:
                    text = '{"v":1,"items":[{"text":"x","done":0.5}]}'
                self.refuses(text)

    def test_a_typed_line_is_plain_visible_text_of_at_most_200_characters(self):
        self.check(body(line("x" * 200)))
        for text in ("", " ", " Send", "Send ", "x" * 201, "Send\nit", "Send‮it", "Send​it", "Send\u0000it", None, 5, ["a"]):
            with self.subTest(text=text):
                self.refuses(body(line(text)))
        self.refuses('{"v":1,"items":[{"text":"\\ud800","done":0}]}')

    def test_a_work_item_is_linked_once_and_the_list_is_at_most_twenty(self):
        self.refuses(body(link("ABC-A-001"), link("ABC-A-001")))
        self.check(body(*[line(f"Line {n}") for n in range(20)]))
        self.refuses(body(*[line(f"Line {n}") for n in range(21)]))
        self.refuses(body(*[link(f"ABC-A-{n:03d}") for n in range(1, 22)]))

    def test_the_hostile_generic_cases_are_refused_before_the_shape(self):
        self.refuses("[" * 5000)
        self.refuses('{"v":1,"items":[],"v":1}')
        self.refuses('{"v":1.5,"items":[]}')
        self.refuses("x" * (checklist.LIMIT + 1))
        self.refuses(json.dumps({"v": 1, "items": [line("\U0001F600" * 200)] * 21}))

    def test_the_limit_fits_the_change_route(self):
        from clark import server as sv
        self.assertGreaterEqual(sv.ROUTE_BODY_LIMITS["/api/change"], checklist.LIMIT + 8 * 1024)
        worst = body(*[line("\U0001F600" * 200, 1) for _ in range(20)])
        self.assertLessEqual(len(self.check(worst)), checklist.LIMIT, "the largest valid content fits its limit")
        self.assertLess(len(json.dumps({"project": "ABC", "kind": "report_sections", "op": "update", "id": "ABC-S-001", "changes": {"body": worst}})),
                        sv.ROUTE_BODY_LIMITS["/api/change"], "and its request fits the route")

    def test_published_keeps_typed_lines_and_only_the_work_items_the_file_kept(self):
        ctx = base.Context({"actions": [{"id": "ABC-A-001"}], "raid": [{"id": "ABC-004"}], "decisions": [{"id": "ABC-D-001"}], "milestones": [{"id": "ABC-M-001"}]}, "2030-01-15")
        value = json.loads(self.check(body(link("ABC-A-001"), link("ABC-A-002"), link("ABC-004"), link("ABC-D-001"), link("ABC-D-009"), line("Typed", 1))))
        self.assertEqual(checklist.published(value, ctx), {"v": 1, "items": [link("ABC-A-001"), link("ABC-004"), link("ABC-D-001"), line("Typed", 1)]})
        only_gone = json.loads(self.check(body(link("ABC-A-002"), link("ABC-D-009"))))
        self.assertIsNone(checklist.published(only_gone, ctx))
        self.assertIsNone(section_bodies.published("checklist", json.loads(self.check(body())), ctx))
        self.assertIsNone(section_bodies.published("checklist", only_gone, base.Context()), "no context, no linked line")
        self.assertEqual(section_bodies.published("checklist", json.loads(self.check(body(line()))), base.Context()), {"v": 1, "items": [line()]})


class Stored(Api):
    def make(self):
        return self.ok("new", values={"type": "checklist", "title": "Next steps"}, after=None)["ref"]

    def write(self, ref, text):
        return self.change(self.req(changes.UPDATE, id=ref, changes={"body": text}))

    def test_one_change_is_one_step_and_one_undo_puts_the_old_body_back(self):
        ref = self.make()
        first = self.write(ref, body(line()))[1]
        second = self.write(ref, body(line("Send the plan", 1)))[1]
        self.assertNotEqual(first["apply_id"], second["apply_id"])
        self.assertEqual(self.undo({"project": "ABC", "apply_id": second["apply_id"]})[0], 200)
        self.assertEqual(json.loads(self.s.read("report_sections", ref=ref)["body"])["items"], [line()])
        self.assertEqual(self.undo({"project": "ABC", "apply_id": first["apply_id"]})[0], 200)
        self.assertEqual(self.s.read("report_sections", ref=ref)["body"], "")

    def test_a_refused_body_writes_nothing(self):
        ref = self.make()
        self.write(ref, body(line()))
        before = self.snapshot()
        status, got = self.write(ref, body(line("Send the plan", 2)))
        self.assertEqual((status, got["ok"], got["message"]), (400, False, checklist.BAD_TICK))
        self.assertEqual(self.snapshot(), before)


class Published(Api):
    def plant(self):
        d = self.demo
        self.kept = d.action(description=f"{MARK} kept", due_date="2030-02-01")
        self.done = d.action(description=f"{MARK} finished", due_date="2030-02-01")
        d.update("actions", self.done, {"status": "Closed"})
        self.off = d.action(description=f"{MARK} client off", due_date="2030-02-01", client_visible=0)
        self.secret = d.action(description=f"{MARK} sensitive", due_date="2030-02-01")
        self.hid = d.action(description=f"{MARK} hidden", due_date="2030-02-01")
        self.arc = d.action(description=f"{MARK} archived", due_date="2030-02-01")
        with self.s.step("dashboard", USER) as st:
            st.create("report_hidden", {"project": "ABC", "item_id": self.hid})
            self.risk = st.create("raid", {"project": "ABC", "type": "Risk", "description": f"{MARK} risk", "raised": "2026-10-01", "source": "demo",
                                           "impact": "High", "likelihood": "High", "owner": "Pat Demo"})
        self.s.con.execute("INSERT OR IGNORE INTO item_labels (item_id, label) VALUES (?, 'Sensitive')", (self.secret,))
        with self.s.step("dashboard", USER) as st:
            st.archive("actions", self.arc)

    def section(self, items, title="Next steps"):
        ref = self.ok("new", values={"type": "checklist", "title": title}, after=None)["ref"]
        self.assertEqual(self.change(self.req(changes.UPDATE, id=ref, changes={"body": body(*items)}))[0], 200)
        return ref

    def built(self):
        out = publish.build(self.s, "ABC", now="2030-01-15")
        return out["published"], out["body"].decode("utf-8")

    def test_only_what_the_file_keeps_is_published(self):
        self.plant()
        ref = self.section([link(self.kept), link(self.done), link(self.off), link(self.secret), link(self.hid), link(self.arc), link(self.risk), line(f"{MARK} typed", 1)])
        built, text = self.built()
        sec = next(s for s in built["sections"] if s["id"] == ref)
        self.assertEqual(sec["items"], [link(self.kept), link(self.done), link(self.risk), line(f"{MARK} typed", 1)])
        for gone in (self.off, self.secret, self.hid, self.arc, f"{MARK} client off", f"{MARK} sensitive", f"{MARK} hidden", f"{MARK} archived"):
            self.assertNotIn(gone, text)
        self.assertIn(f"{MARK} typed", text)

    def test_an_empty_template_and_one_with_nothing_left_stay_out(self):
        self.plant()
        empty = self.ok("new", values={"type": "checklist", "title": "Fictional empty list"}, after=None)["ref"]
        gone = self.section([link(self.off), link(self.hid)], "Fictional gone list")
        built, text = self.built()
        ids = [s["id"] for s in built["sections"]]
        self.assertNotIn(empty, ids)
        self.assertNotIn(gone, ids)
        self.assertNotIn("Fictional empty list", text)
        self.assertNotIn("Fictional gone list", text)

    def test_a_hidden_checklist_section_is_not_in_the_file(self):
        self.plant()
        ref = self.section([line(f"{MARK} typed")])
        self.assertEqual(self.change(self.req(changes.UPDATE, id=ref, changes={"hidden": 1}))[0], 200)
        built, text = self.built()
        self.assertNotIn(ref, [s["id"] for s in built["sections"]])
        self.assertNotIn(f"{MARK} typed", text)

    def test_the_file_carries_no_edit_part_and_no_server_route_for_it(self):
        self.plant()
        self.section([line(f"{MARK} typed")])
        _, text = self.built()
        for owner_only in ("tple-", "Link a work item", "/api/change"):
            self.assertNotIn(owner_only, text)


class InThePage(Base):
    def setUp(self):
        super().setUp()
        d = self.demo
        self.a_open = d.action(description="Chase the supplier file", due_date="2030-02-01")
        self.a_done = d.action(description="Book the room", due_date="2030-02-01")
        d.update("actions", self.a_done, {"status": "Closed"})
        self.a_secret = d.action(description=f"{MARK} sensitive", due_date="2030-02-01")
        self.a_off = d.action(description=f"{MARK} client off", due_date="2030-02-01", client_visible=0)
        self.a_cancel = d.action(description=f"{MARK} cancelled", due_date="2030-02-01")
        d.update("actions", self.a_cancel, {"status": "Cancelled"})
        self.store.con.execute("INSERT OR IGNORE INTO item_labels (item_id, label) VALUES (?, 'Sensitive')", (self.a_secret,))
        self.store.con.commit()
        with self.store.step("dashboard", USER) as st:
            self.ref = st.create("report_sections", {"project": "ABC", "type": "checklist", "title": "Next steps", "sort_order": 999,
                                                       "body": body(line("Send the plan", 1), link(self.a_open), link(self.a_done), link(self.a_secret),
                                                                    link(self.a_off), link(self.a_cancel), line("Book the venue", 0))})

    def page(self, cdp, width=1400, dark=False):
        p = self.visit(cdp)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, p.sid)      # a headless page is otherwise not focused, so blur() fires nothing
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        if dark:
            p.js("document.documentElement.dataset.theme = 'dark'")
        return p

    def stored(self):
        return json.loads(self.store.read("report_sections", ref=self.ref)["body"])["items"]

    def test_view_draws_the_lines_with_words_for_the_state_and_leaves_out_what_the_client_does_not_see(self):
        for width, dark in ((1400, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.page(cdp, width, dark)
                sec = f'[data-id="{self.ref}"]'
                p.until(f"!!document.querySelector('{sec} .tpl-check-row')", "the lines drew")
                got = p.js(f"[...document.querySelectorAll('{sec} .tpl-check-row')].map(r => [...r.children].slice(1).map(c => c.textContent))")
                self.assertEqual(got, [["Send the plan", "Done"], ["Chase the supplier file", "To do"], ["Book the room", "Done"], ["Book the venue", "To do"]])
                self.assertEqual(p.js(f"document.querySelector('{sec} .tpl-check-count').textContent"), "2 of 4 done")
                self.assertNotIn(MARK, p.js(f"document.querySelector('{sec}').textContent"))
                self.assertEqual(p.js(f"document.querySelectorAll('{sec} input, {sec} button, {sec} select').length"), 0, "View is read only")
                self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"))

    def test_a_linked_line_follows_its_work_item(self):
        with chrome() as cdp:
            p = self.page(cdp)
            sec = f'[data-id="{self.ref}"]'
            p.until(f"!!document.querySelector('{sec} .tpl-check-row')", "drawn")
            self.assertEqual(p.js(f"document.querySelector('{sec} .tpl-check-count').textContent"), "2 of 4 done")
        self.demo.update("actions", self.a_open, {"status": "Closed"})
        with chrome() as cdp:
            p = self.page(cdp)
            p.until(f"!!document.querySelector('{sec} .tpl-check-row')", "drawn")
            self.assertEqual(p.js(f"document.querySelector('{sec} .tpl-check-count').textContent"), "3 of 4 done")

    def test_view_leaves_the_section_out_while_it_has_nothing_to_show(self):
        with self.store.step("dashboard", USER) as st:
            empty = st.create("report_sections", {"project": "ABC", "type": "checklist", "title": "Fictional empty list", "sort_order": 1000})
            only_off = st.create("report_sections", {"project": "ABC", "type": "checklist", "title": "Fictional off list", "sort_order": 1001, "body": body(link(self.a_off))})
        with chrome() as cdp:
            p = self.page(cdp)
            for ref in (empty, only_off):
                self.assertFalse(p.js(f"!!document.querySelector('[data-id=\"{ref}\"]')"))
            p.edit()
            p.until(f"!!document.querySelector('[data-id=\"{empty}\"] .tple-empty')", "Edit shows the empty state")
            self.assertIn("No lines yet.", p.js(f"document.querySelector('[data-id=\"{empty}\"] .tple-empty').textContent"))
            self.assertTrue(p.js(f"!!document.querySelector('[data-id=\"{only_off}\"]')"), "Edit still shows it")

    def fill(self, p, selector, text):
        p.js(f"(function(){{var e=document.querySelector({json.dumps(selector)}); e.focus(); e.value={json.dumps(text)};}})()")

    def test_edit_adds_a_line_in_one_step_and_undo_takes_it_back(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.edit()
            sec = f'[data-id="{self.ref}"]'
            p.until(f"!!document.querySelector('{sec} .tple-typed')", "the form")
            self.fill(p, f"{sec} .tple-typed [name=text]", "Call the supplier")
            p.js(f"document.querySelector('{sec} .tple-typed button').click()")
            p.saved()
            self.assertEqual(self.stored()[-1], line("Call the supplier", 0))
            self.assertEqual(p.toast(), "Line added.")
            p.js("document.querySelector('[data-undo]').click()")
            self.assertTrue(wait(lambda: self.stored()[-1] == line("Book the venue", 0), 10), "Undo took the line back")

    def test_edit_ticks_a_line_in_one_step_and_a_refused_save_puts_the_box_back(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.edit()
            sec = f'[data-id="{self.ref}"]'
            p.until(f"!!document.querySelector('{sec} .tple-tick')", "the boxes")
            p.js(f"document.querySelector('{sec} input[aria-label=\"Done: Book the venue\"]').click()")
            self.assertTrue(wait(lambda: line("Book the venue", 1) in self.stored(), 10), "ticked")
            p.until("!!document.querySelector('[data-undo]')", "toast")
            self.assertEqual(p.toast(), "Line ticked.")
            self.failure = lambda req: (400, {"ok": False, "message": "Nothing was changed. Try again."})
            before = self.stored()
            p.js(f"document.querySelector('{sec} input[aria-label=\"Done: Book the venue\"]').click()")
            p.until(f"document.querySelector('{sec} input[aria-label=\"Done: Book the venue\"]').checked === true", "the box went back to what was saved")
            self.assertEqual(self.stored(), before)

    def test_edit_refuses_a_long_line_in_plain_words_and_writes_nothing(self):
        before = self.stored()
        with chrome() as cdp:
            p = self.page(cdp)
            p.edit()
            sec = f'[data-id="{self.ref}"]'
            p.until(f"!!document.querySelector('{sec} .tple-typed')", "the form")
            self.fill(p, f"{sec} .tple-typed [name=text]", "x" * 201)
            p.js(f"document.querySelector('{sec} .tple-typed button').click()")
            p.until("!!document.querySelector('.toast-text')", "a message")
            self.assertEqual(p.toast(), "A line needs 1 to 200 characters. Type what is to be done.")
            self.assertEqual(self.stored(), before)

    def test_edit_links_a_work_item_changes_a_line_and_removes_one(self):
        extra = self.demo.action(description=f"{MARK} not linked, client off", due_date="2030-02-01", client_visible=0)
        with chrome() as cdp:
            p = self.page(cdp)
            p.edit()
            sec = f'[data-id="{self.ref}"]'
            p.until(f"!!document.querySelector('{sec} select')", "the list")
            offered = p.js(f"[...document.querySelectorAll('{sec} select option')].map(o => o.value)")
            self.assertNotIn(self.a_open, offered, "a linked work item is not offered again")
            self.assertNotIn(self.a_cancel, offered, "a cancelled one is not offered")
            self.assertIn(extra, offered, "Edit sees every work item")
            p.js(f"(function(){{var s=document.querySelector('{sec} select'); s.value={json.dumps(extra)}; s.dispatchEvent(new Event('change', {{bubbles: true}}));}})()")
            self.assertTrue(wait(lambda: self.stored().count(link(extra)) == 1, 10))
            self.fill(p, f"{sec} input[aria-label='Checklist line']", "Send the final plan")
            p.js(f"document.querySelector('{sec} input[aria-label=\"Checklist line\"]').blur()")
            self.assertTrue(wait(lambda: line("Send the final plan", 1) in self.stored(), 10), "the words changed where they were")
            p.js(f"document.querySelector('{sec} button[aria-label=\"Remove Book the venue\"]').click()")
            self.assertTrue(wait(lambda: not any(i.get("text") == "Book the venue" for i in self.stored()), 10))

    def test_edit_is_reachable_by_keyboard(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.edit()
            sec = f'[data-id="{self.ref}"]'
            p.until(f"!!document.querySelector('{sec} .tple-typed')", "the form")
            self.assertEqual(p.js(f"[...document.querySelectorAll('{sec} .tple input, {sec} .tple select, {sec} .tple button')].filter(e => e.tabIndex < 0).length"), 0)
            p.js(f"document.querySelector('{sec} .tple-typed [name=text]').focus()")
            p.type("Kick-off")
            for kind in ("keyDown", "keyUp"):
                cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "text": "\r"}, p.sid)
            self.assertTrue(wait(lambda: line("Kick-off", 0) in self.stored(), 10), "Enter in the form adds the line")


class TheFile(Base):
    def setUp(self):
        super().setUp()
        d = self.demo
        self.a_open = d.action(description="Chase the supplier file", due_date="2030-02-01")
        self.a_done = d.action(description="Book the room", due_date="2030-02-01")
        d.update("actions", self.a_done, {"status": "Closed"})
        self.a_off = d.action(description=f"{MARK} client off", due_date="2030-02-01", client_visible=0)
        self.a_hid = d.action(description=f"{MARK} hidden", due_date="2030-02-01")
        with self.store.step("dashboard", USER) as st:
            st.create("report_hidden", {"project": "ABC", "item_id": self.a_hid})
            st.create("report_sections", {"project": "ABC", "type": "checklist", "title": "Next steps", "sort_order": 999,
                                          "body": body(line("Send the plan", 1), link(self.a_open), link(self.a_done), link(self.a_off), link(self.a_hid), line("Book the venue", 0))})
            st.create("report_sections", {"project": "ABC", "type": "checklist", "title": "Fictional empty list", "sort_order": 1000})
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

    def test_the_file_draws_the_lines_read_only_and_nothing_hidden(self):
        text = self.path.read_text(encoding="utf-8")
        self.assertNotIn(MARK, text)
        self.assertNotIn("Fictional empty list", text)
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.draw(cdp, width, dark)
                got = p.js("[...document.querySelectorAll('[data-tpl=checklist] .tpl-check-row')].map(r => [...r.children].slice(1).map(c => c.textContent))")
                self.assertEqual(got, [["Send the plan", "Done"], ["Chase the supplier file", "To do"], ["Book the room", "Done"], ["Book the venue", "To do"]])
                self.assertEqual(p.js("document.querySelector('[data-tpl=checklist] .tpl-check-count').textContent"), "2 of 4 done")
                self.assertEqual(p.js("document.querySelectorAll('[data-tpl=checklist] input, [data-tpl=checklist] button, [data-tpl=checklist] select, [data-tpl=checklist] a').length"), 0)
                self.assertEqual(p.js("document.querySelectorAll('.sec[data-type=checklist]').length"), 1, "the empty one is not drawn")
                self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"))

    def test_text_contrast_is_at_least_4_5_to_1_in_light_and_dark(self):
        script = """(() => {
          const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
          const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
          const ratio = (a, b) => { const x = lum(rgb(a)), y = lum(rgb(b)); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
          const out = [];
          for (const sel of ['.tpl-check-count', '.tpl-check-text', '.tpl-check-state', '.tpl-check-row.is-done .tpl-check-text', '.tpl-check-row.is-done .tpl-check-state', '.tpl-check-row.is-done .tpl-check-box']) {
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
