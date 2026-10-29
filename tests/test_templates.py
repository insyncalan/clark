"""#96 (section templates and the Add a section box), first slice: the catalogue and its logic (src/clark/page/src/logic/templates.js)
and the box in the real page (edit/AddDialog.jsx) against the real routes. The rules are in docs/handoff/design-96-templates.md.

Run: python3 dev/run_tests.py test_templates
Needs Chrome (the #33 harness): these tests fail, never skip, without it. The logic runs on a bare page bundled by the pinned esbuild
in a temporary folder; the box runs in the page clark serves, with the real change and undo over a real store (fictional data).
"""
import json
import unittest

import test_placement as tp
from _paths import ROOT, SRC
from test_report_editor import Base, IDS
from test_server import chrome, wait

tp.DEMO = ROOT / "tests" / "fixtures" / "templates_demo.js"      # the fixture this file's bundle is made from
sec, lit = tp.sec, tp.lit

_PAGE = {}


def page_html():
    if "html" not in _PAGE:
        tp._PAGE.pop("html", None)
        _PAGE["html"] = tp.test_page_html()
        tp._PAGE.pop("html", None)
    return _PAGE["html"]


# Fictional. Rows: [a] [b] [c d] [e] (a pair in the middle; e is last)
S = [sec("a", "Summary"), sec("b", "Milestones", type="milestones"), sec("c", "This week", beside=1), sec("d", "Next week"), sec("e", "Decisions", type="decisions")]
FIRST_SLICE = ["text", "text-image", "figures-3", "figures-4", "raid-3", "raid-4", "work-items", "docs-links", "callout", "key-dates"]


class Logic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import contextlib
        from test_server import Running
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def setUp(self):
        self.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.server.port}/"}, self.sid)
        self.assertTrue(wait(lambda: self.cdp.js("!!(window.T && window.T.templates)", self.sid)), "the test bundle ran")

    def val(self, expr):
        got = self.cdp.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()", self.sid)
        self.assertIsNotNone(got, expr)
        self.assertFalse(got.startswith("ERROR"), f"{expr}: {got}")
        return json.loads(got)

    def t(self, call):
        return self.val(f"T.templates.{call}")

    # ── the catalogue ────────────────────────────────────────────────────────

    def test_the_first_slice_is_all_there_with_everything_filled_in(self):
        cat = self.t("TEMPLATES")
        self.assertEqual([x["id"] for x in cat], FIRST_SLICE)
        kinds = {k["id"] for k in self.t("KINDS")}
        for x in cat:
            self.assertTrue(x["name"] and x["description"] and x["title"] and x["holds"], x["id"])
            self.assertIn(x["kind"], kinds)
            self.assertTrue(x["fit"] and set(x["fit"]) <= {"full", "half"}, x["id"])
            self.assertTrue(x["description"].endswith("."), f"a sentence: {x['id']}")
            for word in ("TODO", "lorem", "  "):
                self.assertNotIn(word, x["description"])
        self.assertEqual(len({x["id"] for x in cat}), len(cat))
        by = {x["id"]: x for x in cat}
        self.assertEqual(by["key-dates"]["fit"], ["half"])
        self.assertEqual(by["raid-3"]["fit"], by["raid-4"]["fit"], ["full"])
        self.assertEqual(set(by["work-items"]["fit"]), {"full", "half"})

    def test_what_the_store_takes_is_what_the_list_says(self):
        """ACCEPTS is the store's real answer: text is taken; every other template's type is refused by the real route."""
        self.assertEqual(self.t("ACCEPTS"), {"types": ["text"]})
        self.assertEqual(self.t("TEMPLATES.filter(T.templates.available).map(x => x.id)"), ["text"])
        from clark import changes, store
        self.assertEqual(changes.CHANGE_KINDS["report_sections"][changes.NEW], ("type", "title"), "new still takes a type and a title only")
        for x in self.t("TEMPLATES"):
            if x["type"] != "text":
                self.assertNotIn(x["type"], store.SECTION_TYPES, f"{x['id']} needs a section type the store does not have yet (design note, section 6)")

    # ── search, kinds, counts, recently used ─────────────────────────────────

    def test_search_and_kinds_and_counts(self):
        self.assertEqual(len(self.t("list()")), 10)
        self.assertEqual([x["id"] for x in self.t('list({query: "figures"})')], ["figures-3", "figures-4"])
        self.assertEqual([x["id"] for x in self.t('list({query: "KEY dates"})')], ["key-dates"], "case does not matter and every word must match")
        self.assertEqual(self.t('list({query: "zzz"})'), [])
        self.assertEqual([x["id"] for x in self.t('list({kind: "work"})')], ["raid-3", "raid-4", "work-items"])
        self.assertEqual([x["id"] for x in self.t('list({kind: "work", query: "list"})')], ["work-items"])
        c = self.t('counts({query: "key"})')
        self.assertEqual((c["all"], c["figures"], c["dates"], c["text"], c["recent"]), (3, 2, 1, 0, 0))
        self.assertEqual([x["id"] for x in self.t('list({kind: "recent", recent: ["callout", "text", "nope"]})')], ["callout", "text"])

    def test_recently_used_is_newest_first_each_once_at_most_three_and_only_known(self):
        self.assertEqual(self.t('remember([], "text")'), ["text"])
        self.assertEqual(self.t('remember(["text", "callout"], "text")'), ["text", "callout"])
        self.assertEqual(self.t('remember(["a1", "text", "callout", "key-dates"], "raid-3")').__len__(), 3)
        self.assertEqual(self.t('remember(["text", "callout", "key-dates"], "raid-3")'), ["raid-3", "text", "callout"])
        self.assertEqual(self.t('remember(["text", "bogus"], "nope")'), ["text"], "an unknown id is never added or kept")

    # ── where it goes ────────────────────────────────────────────────────────

    def test_it_goes_below_the_whole_row_so_a_pair_is_never_split(self):
        self.assertEqual(self.t(f"anchor({lit(S)}, 'a')"), {"ok": True, "id": "a"})
        self.assertEqual(self.t(f"anchor({lit(S)}, 'c')"), {"ok": True, "id": "d"}, "the left half of a pair: below the pair")
        self.assertEqual(self.t(f"anchor({lit(S)}, 'd')"), {"ok": True, "id": "d"})
        self.assertEqual(self.t(f"anchor({lit(S)}, null)"), {"ok": True, "id": None})
        self.assertEqual(self.t(f"anchor({lit(S)}, 'zz')"), {"ok": False, "message": "That section isn't in the report any more. Reload the page."})

    def test_beside_is_offered_only_to_half_width_templates_next_to_a_section_on_its_own(self):
        st = lambda after, tid: self.t(f"besideState({lit(S)}, {lit(after)}, T.templates.find({lit(tid)}))")
        self.assertEqual(st("a", "text"), {"ok": True}, "the next row (Milestones) is alone")
        self.assertEqual(st("e", "text"), {"ok": False, "message": "This is the last section, so there is nothing to sit beside."})
        self.assertEqual(st("b", "text"), {"ok": False, "message": "The next row already has two sections. Place it on its own row."})
        self.assertEqual(st("a", "raid-3"), {"ok": False, "message": "This template needs the full width. Place it on its own row."})
        self.assertEqual(st("a", "key-dates"), {"ok": True})
        self.assertEqual(st(None, "text"), {"ok": False, "message": "There is no section yet to sit beside."})
        self.assertEqual(st("c", "text"), {"ok": True}, "below the pair; the next row (Decisions) is alone")

    # ── the request each template sends ──────────────────────────────────────

    def test_text_sends_the_new_request_the_store_takes_and_nothing_else(self):
        p = self.t(f"plan({lit(S)}, 'text', 'a', false)")
        self.assertTrue(p["ok"])
        self.assertEqual(p["requests"], [{"op": "new", "values": {"type": "text", "title": "New section"}, "after": "a", "place": "report"}])
        self.assertEqual(p["words"], "Text added.")
        end = self.t(f"plan({lit(S)}, 'text', null, false)")
        self.assertEqual(end["requests"][0]["after"], None)
        pair = self.t(f"plan({lit(S)}, 'text', 'c', false)")
        self.assertEqual(pair["requests"][0]["after"], "d", "below the pair's last section")

    def test_beside_is_a_new_then_a_flag_on_what_was_made(self):
        p = self.t(f"plan({lit(S)}, 'text', 'a', true)")
        self.assertEqual([r["op"] for r in p["requests"]], ["new", "update"])
        self.assertEqual(p["requests"][1], {"op": "update", "id": "$new", "changes": {"beside": 1}, "place": "report"})
        self.assertEqual(p["words"], "Text added, beside the next section.")
        bad = self.t(f"plan({lit(S)}, 'text', 'b', true)")
        self.assertEqual((bad["ok"], bad["message"]), (False, "The next row already has two sections. Place it on its own row."))

    def test_a_flag_left_on_the_last_section_is_cleared_so_the_new_one_does_not_pair_with_it(self):
        stale = [sec("a", "Summary"), sec("z", "Last", beside=1)]
        p = self.t(f"plan({lit(stale)}, 'text', 'z', false)")
        self.assertEqual(p["requests"][1], {"op": "update", "id": "z", "changes": {"beside": 0}, "place": "report"})
        self.assertEqual(len(self.t(f"plan({lit(S)}, 'text', 'e', false)")["requests"]), 1, "no flag, nothing to clear")

    def test_a_template_the_store_cannot_make_yet_sends_nothing(self):
        for tid in FIRST_SLICE[1:]:
            p = self.t(f"plan({lit(S)}, {lit(tid)}, 'a', false)")
            self.assertEqual((p["ok"], p["message"]), (False, "Coming with a later release."), tid)
        self.assertEqual(self.t(f"plan({lit(S)}, 'nope', 'a', false)")["message"], "That template isn't in the list.")
        self.assertEqual(self.t(f"plan({lit(S)}, 'text', 'zz', false)")["message"], "That section isn't in the report any more. Reload the page.")


OPEN = "document.dispatchEvent(new CustomEvent('clark:add-section', {detail: {after: %s, opener: document.activeElement}, cancelable: true, bubbles: true}))"


class Box(Base):
    def open_box(self, p, after, focus=None):
        if focus:
            p.js(f"document.querySelector({json.dumps(focus)}).focus()")
        p.js(OPEN % json.dumps(after))
        p.until("!!document.querySelector('[role=dialog]') && document.activeElement.matches('input[type=search]')", "the box opened with focus in the search box")

    def test_it_opens_by_the_event_with_focus_in_search_and_does_nothing_in_view(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.js(OPEN % '"ABC-S-003"')
            self.assertFalse(p.js("!!document.querySelector('[role=dialog]')"), "View: the event does nothing")
            p.edit()
            self.open_box(p, "ABC-S-003")
            self.assertTrue(p.js("document.activeElement.matches('input[type=search]')"), "focus starts in the search box")
            d = "document.querySelector('[role=dialog]')"
            self.assertEqual(p.js(f"{d}.getAttribute('aria-modal')"), "true")
            self.assertEqual(p.js(f"document.getElementById({d}.getAttribute('aria-labelledby')).textContent"), "Add a section")
            self.assertEqual(p.js("document.querySelector('#main').hasAttribute('inert') && document.querySelector('.top').hasAttribute('inert')"), True,
                             "the page behind cannot be reached")
            self.assertEqual(p.js("document.querySelectorAll('[data-template]').length"), 10)
            self.assertEqual(p.js("[...document.querySelectorAll('.ad-kind')].map(b => b.textContent)"),
                             ["All templates10", "Text and pictures2", "Figures2", "Work items3", "Files and links1", "People and dates1", "Notes1"])
            self.assertEqual(self.sent, [], "opening sends nothing")

    def test_it_takes_the_event_exactly_as_the_gutter_sends_it(self):
        """The contract with #101: a cancelable event on the document, detail {after, opener}; the box claims it and opens."""
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            send = ("(function(){var b=document.querySelector('[data-id=\"ABC-S-003\"] [data-drag]');"
                    "var e=new CustomEvent('clark:add-section',{detail:{after:'ABC-S-003',opener:b},cancelable:true,bubbles:true});"
                    "document.dispatchEvent(e);return e.defaultPrevented;})()")
            self.assertTrue(p.js(send), "the box claimed the request")
            p.until("!!document.querySelector('[role=dialog]') && document.activeElement.matches('input[type=search]')", "the box opened")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('[role=dialog]')", "Esc closed it")
            self.assertTrue(wait(lambda: p.js("document.activeElement.matches('[data-id=\"ABC-S-003\"] [data-drag]')"), 5), "focus went back to the opener")
            self.assertTrue(p.js("(function(){var e=new CustomEvent('clark:add-section',{detail:{after:null,opener:null},cancelable:true,bubbles:true});"
                                 "var seen=false;window.addEventListener('clark:add-section',function(){seen=true;},{once:true});"
                                 "document.dispatchEvent(e);return seen && e.defaultPrevented;})()"), "it also reaches window by bubbling")

    def test_join_the_plus_and_the_menu_entry_open_the_box_end_to_end(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.js("document.querySelector('[data-id=\"ABC-S-003\"] [data-add]').click()")
            p.until("!!document.querySelector('[role=dialog]') && document.activeElement.matches('input[type=search]')", "the + opened the box")
            self.assertIsNone(p.js("document.querySelector('.toast')"), "no 'not available' note")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('[role=dialog]')", "closed")
            self.assertTrue(wait(lambda: p.js("document.activeElement.matches('[data-id=\"ABC-S-003\"] [data-add]')"), 5), "focus back on the +")
            p.menu("ABC-S-011", "add")
            p.until("!!document.querySelector('[role=dialog]')", "the menu entry opened the box")
            self.assertIsNone(p.js("document.querySelector('.toast')"))

    def test_escape_and_cancel_close_it_and_give_focus_back(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.open_box(p, "ABC-S-003", focus='[data-id="ABC-S-003"] [data-drag]')
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('[role=dialog]')", "Esc closed it")
            self.assertTrue(wait(lambda: p.js("document.activeElement.matches('[data-drag]') && document.activeElement.closest('.sec').dataset.id === 'ABC-S-003'"), 5), "focus is back on the opener")
            self.assertFalse(p.js("document.querySelector('#main').hasAttribute('inert')"), "the page is reachable again")
            self.open_box(p, "ABC-S-004", focus='[data-id="ABC-S-004"] [data-options]')
            p.js("document.querySelector('[data-cancel]').click()")
            p.until("!document.querySelector('[role=dialog]')", "Cancel closed it")
            self.assertTrue(wait(lambda: p.js("document.activeElement.matches('[data-options]')"), 5))
            self.assertEqual(self.sent, [])

    def test_tab_stays_inside_the_box(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.open_box(p, "ABC-S-003")
            seen = set()
            for _ in range(40):
                p.key("Tab", code="Tab", vk=9)
                seen.add(p.js("document.activeElement.closest('[role=dialog]') ? 'in' : 'out'"))
            self.assertEqual(seen, {"in"}, "Tab never leaves the box")
            for _ in range(40):
                p.key("Tab", 8, code="Tab", vk=9)      # Shift+Tab
                seen.add(p.js("document.activeElement.closest('[role=dialog]') ? 'in' : 'out'"))
            self.assertEqual(seen, {"in"}, "nor does Shift+Tab")

    def test_search_kinds_and_the_arrow_from_search_to_the_templates(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.open_box(p, "ABC-S-003")
            p.type("key")
            p.until("document.querySelectorAll('[data-template]').length === 3", "the search narrowed the list")
            self.assertEqual(p.js("[...document.querySelectorAll('.ad-kind')].map(b => b.querySelector('.ad-n').textContent)"), ["3", "0", "2", "0", "0", "1", "0"])
            p.key("ArrowDown", code="ArrowDown", vk=40)
            self.assertTrue(p.js("document.activeElement.matches('input[type=search]')"), "none of those can be chosen yet, so Down stays")
            p.js("var s = document.querySelector('input[type=search]'); s.value = ''; s.dispatchEvent(new Event('input', {bubbles: true}))")
            p.type("text")
            p.until("document.querySelectorAll('[data-template]').length > 2 && !!document.querySelector('input[name=template]:checked')", "a search for text")
            p.key("ArrowDown", code="ArrowDown", vk=40)
            self.assertTrue(p.js("document.activeElement.matches('input[name=template]:checked')"), "Down goes from the search to the chosen template")
            p.js("var s = document.querySelector('input[type=search]'); s.focus(); s.value = ''; s.dispatchEvent(new Event('input', {bubbles: true}))")
            p.type("zzz")
            p.until("document.querySelectorAll('[data-template]').length === 0", "nothing matches")
            self.assertIn("No template matches", p.js("document.querySelector('.ad-none').textContent"))
            self.assertTrue(p.js("document.querySelector('[data-place]').disabled"), "nothing chosen: Place it is off")
            p.js("document.querySelector('[data-kind=work]').click()")
            p.js("var s = document.querySelector('input[type=search]'); s.value = ''; s.dispatchEvent(new Event('input', {bubbles: true}))")
            p.until("document.querySelectorAll('[data-template]').length === 3", "Work items shows three")
            self.assertEqual(p.js("document.querySelector('.ad-kind[aria-pressed=true]').dataset.kind"), "work")

    def test_a_template_not_made_yet_is_listed_but_cannot_be_placed(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.open_box(p, "ABC-S-003")
            self.assertEqual(p.js("[...document.querySelectorAll('input[name=template]')].filter(i => !i.disabled).map(i => i.value)"), ["text"])
            self.assertIn("Coming with a later release.", p.js("document.querySelector('[data-template=callout]').textContent"))
            p.js("document.querySelector('[data-kind=notes]').click()")
            p.until("document.querySelectorAll('[data-template]').length === 1", "Notes")
            self.assertEqual(p.js("document.querySelector('.ad-prev h3').textContent"), "Callout", "the preview still shows it")
            self.assertTrue(p.js("document.querySelector('[data-place]').disabled"))
            p.js("document.querySelector('[role=dialog]').requestSubmit()")
            self.assertEqual(self.sent, [], "a submit with a template that is not there yet sends nothing")

    def test_place_a_text_template_below_and_undo_it(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.open_box(p, "ABC-S-003")
            self.assertTrue(p.js("document.querySelector('input[name=template]:checked').value === 'text'"), "the first usable template is chosen")
            p.key("Enter", code="Enter", vk=13)                       # Enter places it
            p.until("document.querySelectorAll('.sec').length === 12", "a section was added")
            self.assertFalse(p.js("!!document.querySelector('[role=dialog]')"))
            new = [i for i in p.ids() if i not in IDS][0]
            self.assertEqual(p.ids()[3], new, "just below the third")
            self.assertEqual(self.sent[-1][1], {"project": "ABC", "kind": "report_sections", "op": "new", "values": {"type": "text", "title": "New section"},
                                                "after": "ABC-S-003", "place": "report"})
            self.assertTrue(wait(lambda: p.js("document.activeElement.matches('[data-title]') && document.activeElement.closest('.sec').dataset.id") == new, 5), "the new title has focus")
            self.assertEqual(p.toast(), "Text added.")
            p.js("document.querySelector('[data-undo]').click()")
            p.until("document.querySelectorAll('.sec').length === 11", "Undo took it away")
            self.assertEqual(self.ids_in_store(), IDS)
            self.open_box(p, "ABC-S-001")
            self.assertEqual(p.js("document.querySelector('.ad-kind:nth-child(2)').textContent"), "Recently used1", "Text is now recently used")

    def test_below_a_pair_goes_below_the_whole_pair(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.open_box(p, "ABC-S-006")                                  # the left half of This week | Next week
            p.js("document.querySelector('[data-place]').click()")
            p.until("document.querySelectorAll('.sec').length === 12", "added")
            new = [i for i in p.ids() if i not in IDS][0]
            self.assertEqual(p.ids().index(new), 7, "below Next week, after the pair")
            self.assertEqual(self.sent[-1][1]["after"], "ABC-S-007")
            self.assertEqual(self.beside_flags()["ABC-S-006"], 1, "the pair is still a pair")
            self.assertEqual(self.beside_flags()[new], 0)

    def test_place_it_beside_the_next_section_is_two_steps_and_the_rows_are_right(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.open_box(p, "ABC-S-004")                                  # the next row, Summary, is alone
            self.assertFalse(p.js("document.querySelector('input[name=where][value=beside]').disabled"))
            p.js("document.querySelector('input[name=where][value=beside]').click()")
            p.js("document.querySelector('[data-place]').click()")
            p.until("document.querySelectorAll('.sec').length === 12 && document.querySelectorAll('.sec.slot-left').length === 2", "added beside")
            new = [i for i in p.ids() if i not in IDS][0]
            self.assertEqual(p.ids()[4], new)
            ops = [r[1]["op"] for r in self.sent]
            self.assertEqual(ops, ["new", "update"])
            self.assertEqual(self.sent[-1][1]["changes"], {"beside": 1})
            self.assertEqual(self.sent[-1][1]["id"], new)
            self.assertEqual(self.beside_flags()[new], 1)
            self.assertEqual(p.js(f"document.querySelector('[data-id=\"{new}\"]').classList.contains('slot-left') && document.querySelector('[data-id=\"ABC-S-005\"]').classList.contains('slot-right')"), True)
            self.assertEqual(p.toast(), "Text added, beside the next section.")

    def test_beside_is_unavailable_with_the_reason_when_the_next_row_is_a_pair_or_there_is_none(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.open_box(p, "ABC-S-005")                                  # the next row is a pair
            self.assertTrue(p.js("document.querySelector('input[name=where][value=beside]').disabled"))
            self.assertEqual(p.js("document.getElementById('ad-w-why').textContent"), "The next row already has two sections. Place it on its own row.")
            self.assertEqual(p.js("document.querySelector('input[name=where][value=beside]').getAttribute('aria-describedby')"), "ad-w-why")
            p.js("document.querySelector('[data-cancel]').click()")
            p.until("!document.querySelector('[role=dialog]')", "closed")
            self.open_box(p, "ABC-S-011")                                  # the last section
            self.assertEqual(p.js("document.getElementById('ad-w-why').textContent"), "This is the last section, so there is nothing to sit beside.")
            p.js("document.querySelector('[data-place]').click()")
            p.until("document.querySelectorAll('.sec').length === 12", "alone at the end")
            self.assertEqual(p.ids()[-1] not in IDS, True)
            self.assertEqual([r[1]["op"] for r in self.sent], ["new"])

    def test_a_refusal_from_clark_is_in_the_toast_and_focus_goes_back(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.failure = lambda req: (409, {"ok": False, "error": "x"})
            self.open_box(p, "ABC-S-003", focus='[data-id="ABC-S-003"] [data-drag]')
            p.js("document.querySelector('[data-place]').click()")
            p.until("!!document.querySelector('.toast.problem')", "the toast says it failed")
            self.assertEqual(p.js("document.querySelectorAll('.sec').length"), 11)
            self.assertTrue(wait(lambda: p.js("document.activeElement.matches('[data-drag]')"), 5), "focus went back to the opener")

    def test_it_fits_at_desktop_and_900_wide_with_no_text_under_13px(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                self.open_box(p, "ABC-S-003")
                self.assertEqual(p.js("document.documentElement.scrollWidth <= window.innerWidth"), True, f"{width}: no sideways scroll")
                self.assertEqual(p.js("(function(){var r=document.querySelector('.ad').getBoundingClientRect();return r.left >= 0 && r.right <= window.innerWidth;})()"), True, width)
                small = p.js("[...document.querySelectorAll('.ad *')].filter(e => [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) && parseFloat(getComputedStyle(e).fontSize) < 13).map(e => e.className)")
                self.assertEqual(small, [], f"{width}: nothing under 13 px")
                p.js("document.querySelector('[data-cancel]').click()")
                p.until("!document.querySelector('[role=dialog]')", "closed")

    def test_the_box_adds_no_edit_part_to_the_published_page(self):
        self.assertNotIn("clark:add-section", (SRC / "clark" / "page" / "page-view.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
