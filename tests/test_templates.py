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
FIRST_SLICE_DESCRIPTIONS = [
    {"id": "text-image", "description": "A story with a picture: a site visit, a design, a screenshot of the new system."},
    {"id": "figures-4", "description": "Three or four numbers with labels and a change since last week."},
    {"id": "figures-3", "description": "Three numbers with labels, in wider cards, so a short note fits under the change."},
    {"id": "raid-3", "description": "The risks, actions, issues or decisions you want the reader to see, as cards."},
    {"id": "raid-4", "description": "Four shorter cards: good for “this week’s actions” or “decisions needed”."},
    {"id": "work-items", "description": "Live rows from Work items, chosen by a filter: open actions due soon, red risks, decisions needed."},
    {"id": "docs-links", "description": "The papers that go with this week’s report."},
    {"id": "callout", "description": "One thing the reader must see."},
    {"id": "key-dates", "description": "What’s coming, from the milestones."},
    {"id": "needs", "description": "What the project needs from the client: decisions, information and dates, each with who it is from and when it is needed by."},
    {"id": "link-preview", "description": "A web page shown as a card you write: a dashboard, a news item, a recording."},
    {"id": "one-doc", "description": "A single file to read."},
    {"id": "text", "description": "Words under a heading, written in clark’s one editor."},
]
FIRST_SLICE = ["text", "text-image", "figures-4", "figures-3", "raid-3", "raid-4", "work-items", "docs-links", "callout", "key-dates", "needs",
               "link-preview", "one-doc"]      # the box's templates: the first slice, Needs from you (#121) and the two files and links ones moved in (#96 G7); every one built


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
        self.assertEqual(by["key-dates"]["fit"], ["half", "full"], "the prototype says Half or full")
        self.assertEqual(by["raid-3"]["fit"], by["raid-4"]["fit"], ["full"])
        self.assertEqual(set(by["work-items"]["fit"]), {"full", "half"})

    def test_the_box_and_help_describe_every_template_in_the_same_words(self):
        """The Add a section box and Help's table of section templates say the same thing for each template the box offers."""
        help_ = json.loads((SRC / "clark" / "page" / "src" / "help" / "helpContent.json").read_text(encoding="utf-8"))
        rows = {}

        def walk(o):
            if isinstance(o, dict):
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                if len(o) == 3 and all(isinstance(x, str) for x in o):
                    rows[o[0]] = o[1]
                for v in o:
                    walk(v)
        walk(help_)
        for t in self.t("TEMPLATES"):
            self.assertIn(t["name"], rows, f"Help has a row for {t['name']}")
            self.assertEqual(rows[t["name"]], t["description"], f"{t['name']}: the box and Help use the same words")

    def test_descriptions_and_what_each_holds_are_the_prototypes(self):
        """The review table: the words and parts are the prototype's (system/prototype/views.js), so Help's table can match them."""
        got = {x["id"]: (x["description"], x["holds"], x["fit"]) for x in self.t("TEMPLATES")}
        self.assertEqual(got, {
            "text": ("Words under a heading, written in clark’s one editor.", ["Heading", "Text"], ["full", "half"]),
            "text-image": ("A story with a picture: a site visit, a design, a screenshot of the new system.", ["Heading", "Text", "Image", "Caption"], ["full", "half"]),
            "figures-3": ("Three numbers with labels, in wider cards, so a short note fits under the change.", ["Heading", "Figure · live", "Figure · live", "Figure · typed"], ["full", "half"]),
            "figures-4": ("Three or four numbers with labels and a change since last week.", ["Heading", "Figure · live", "Figure · live", "Figure · typed", "Figure · typed", "Caption"], ["full", "half"]),
            "raid-3": ("The risks, actions, issues or decisions you want the reader to see, as cards.", ["Heading", "RAID card ×3", "Text source", "Text"], ["full"]),
            "raid-4": ("Four shorter cards: good for “this week’s actions” or “decisions needed”.", ["Heading", "RAID card ×4"], ["full"]),
            "work-items": ("Live rows from Work items, chosen by a filter: open actions due soon, red risks, decisions needed.", ["Heading", "Filter (set in Edit)", "Work item list · live", "Caption (optional)"], ["full", "half"]),
            "docs-links": ("The papers that go with this week’s report.", ["Heading", "File (one or more)", "Link list"], ["full", "half"]),
            "callout": ("One thing the reader must see.", ["Heading", "Callout · decision"], ["half", "full"]),
            "key-dates": ("What’s coming, from the milestones.", ["Heading", "Date (from milestones)"], ["half", "full"]),
            "needs": ("What the project needs from the client: decisions, information and dates, each with who it is from and when it is needed by.", ["Heading", "Row: what is needed", "From", "By"], ["full", "half"]),
            "link-preview": ("A web page shown as a card you write: a dashboard, a news item, a recording.", ["Heading", "Link", "Card text"], ["full"]),
            "one-doc": ("A single file to read.", ["Heading", "File", "Text"], ["half", "full"]),
        })

    def test_a_stub_type_is_placeable_only_when_ready(self):
        """#96 R0: the store takes every template's type (the real change route makes one); a template is placeable only when its
        catalogue entry is ready. Every template in the box is built and ready now (tests/test_section_registry.py ties ready to the
        section_kinds module and the page part); with ready off, none is placeable. ACCEPTS is the store's real answer: text, needs
        (#121) and every template type."""
        from clark import changes, store
        self.assertEqual(self.t("ACCEPTS")["types"][:2], ["text", "needs"])
        self.assertEqual(changes.CHANGE_KINDS["report_sections"][changes.NEW], ("type", "title"), "new still takes a type and a title only")
        for x in self.t("TEMPLATES"):
            self.assertIn(x["type"], store.SECTION_TYPES, x["id"])
            self.assertIn(x["type"], changes.NEW_SECTION_TYPES, x["id"])
            self.assertIn(x["type"], self.t("ACCEPTS")["types"], x["id"])
            self.assertIs(x["ready"], True, x["id"])
        self.assertEqual(self.t("TEMPLATES.filter(T.templates.available).map(x => x.id)"), FIRST_SLICE)
        self.assertEqual(self.t("TEMPLATES.map(x => ({...x, ready: false})).filter(T.templates.available).map(x => x.id)"), [],
                         "with ready off, none is placeable")
        self.assertEqual(self.t("TEMPLATES.map(x => ({...x, ready: true})).filter(T.templates.available).map(x => x.id)"), FIRST_SLICE,
                         "ready is the one switch")

    # ── search, kinds, counts, recently used ─────────────────────────────────

    def test_search_and_kinds_and_counts(self):
        self.assertEqual(len(self.t("list()")), 13)
        self.assertEqual([x["id"] for x in self.t('list({query: "figures"})')], ["figures-4", "figures-3"])
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

    def test_beside_is_offered_only_to_half_width_templates_for_a_section_on_its_own_row(self):
        st = lambda after, tid: self.t(f"besideState({lit(S)}, {lit(after)}, T.templates.find({lit(tid)}))")
        self.assertEqual(st("a", "text"), {"ok": True, "with": "Summary"}, "the section above is alone, and it is named")
        self.assertEqual(st("e", "text"), {"ok": True, "with": "Decisions"}, "the last section can have a partner")
        self.assertEqual(st("c", "text"), {"ok": False, "message": "That section already shares its row. Place it on its own row."}, "the left half of a pair")
        self.assertEqual(st("d", "text"), {"ok": False, "message": "That section already shares its row. Place it on its own row."}, "the right half of a pair")
        self.assertEqual(st("a", "raid-3"), {"ok": False, "message": "This template needs the full width. Place it on its own row."})
        self.assertEqual(st("a", "key-dates"), {"ok": True, "with": "Summary"})
        self.assertEqual(st(None, "text"), {"ok": False, "message": "There is no section yet to sit beside."})
        self.assertEqual(st("zz", "text"), {"ok": False, "message": "That section isn't in the report any more. Reload the page."})

    def test_nothing_shown_says_why_by_cause(self):
        nm = lambda **kw: self.t(f"noMatch({lit(kw)})")
        self.assertEqual(nm(query="zzz", kind="all"), "No template matches that search. Try another word.")
        self.assertEqual(nm(query="zzz", kind="work"), "Nothing in Work items matches that search. Try another word, or choose All templates.")
        self.assertEqual(nm(query="zzz", kind="recent"), "Nothing in Recently used matches that search. Try another word, or choose All templates.")
        self.assertEqual(nm(query="", kind="recent"), "There is nothing in Recently used yet. Choose All templates.")
        self.assertEqual(nm(query="  ", kind="all"), "There are no templates to show.")
        for k in ("all", "work", "recent"):
            self.assertNotIn("Clear the search", nm(query="", kind=k))

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

    def test_beside_is_one_new_request_that_carries_beside(self):
        p = self.t(f"plan({lit(S)}, 'text', 'a', true)")
        self.assertEqual(p["requests"], [{"op": "new", "values": {"type": "text", "title": "New section"}, "after": "a", "beside": 1, "place": "report"}])
        self.assertEqual(p["words"], "Text added, beside the section above.")
        last = self.t(f"plan({lit(S)}, 'text', 'e', true)")
        self.assertEqual([r["after"] for r in last["requests"]], ["e"], "beside the last section")
        self.assertEqual(len(last["requests"]), 1)
        for after in ("c", "d"):
            bad = self.t(f"plan({lit(S)}, 'text', {lit(after)}, true)")
            self.assertEqual((bad["ok"], bad["message"]), (False, "That section already shares its row. Place it on its own row."), after)
        stale = [sec("a", "Summary"), sec("z", "Last", beside=1)]
        self.assertEqual(len(self.t(f"plan({lit(stale)}, 'text', 'z', true)")["requests"]), 1, "beside needs no clearing: clark sets the pairing")

    def test_a_plain_add_below_a_last_section_with_a_stale_flag_is_one_request(self):
        """clark clears the stale flag in the same step (#244), so the page sends the one `new` and nothing else."""
        for sections, after in (([sec("a", "Summary"), sec("z", "Last", beside=1)], "'z'"),
                                ([sec("a", "Summary"), sec("b", "Decisions", type="decisions", beside=1)], "null")):
            p = self.t(f"plan({lit(sections)}, 'text', {after}, false)")
            self.assertEqual(p["requests"], [{"op": "new", "values": {"type": "text", "title": "New section"}, "after": None if after == "null" else "z", "place": "report"}])
            self.assertNotIn("partial", p)

    def test_the_event_name_is_written_once_in_the_page_code(self):
        """The add-section event name is written once, in addSection.js (the gutter); addDialog.js re-exports it."""
        import re
        literal = re.compile(r"""["']clark:add-section["']""")
        hits = [f.name for f in (SRC / "clark" / "page" / "src" / "edit").glob("*.js*") if literal.search(f.read_text(encoding="utf-8"))]
        self.assertEqual(hits, ["addSection.js"])
        self.assertIn("ADD_SECTION_EVENT = ADD_EVENT", (SRC / "clark" / "page" / "src" / "edit" / "addDialog.js").read_text(encoding="utf-8"))

    def test_the_box_code_escapes_the_selector_and_does_not_touch_state_after_closing(self):
        src = (SRC / "clark" / "page" / "src" / "edit" / "AddDialog.jsx").read_text(encoding="utf-8")
        self.assertIn("CSS.escape(after)", src, "the id is escaped before it goes into a selector")
        self.assertNotIn("setRecent", src, "nothing sets state on a box that has already closed")

    def test_a_template_the_store_cannot_make_yet_sends_nothing(self):
        """Every template in the box sends the one new request the store takes; one not in the box (LATER) sends nothing."""
        by = {x["id"]: x for x in self.t("TEMPLATES")}
        for tid in FIRST_SLICE[1:]:
            p = self.t(f"plan({lit(S)}, {lit(tid)}, 'a', false)")
            self.assertEqual(p["requests"], [{"op": "new", "values": {"type": by[tid]["type"], "title": by[tid]["title"]}, "after": "a", "place": "report"}], tid)
        for x in self.t("LATER"):
            p = self.t(f"plan({lit(S)}, {lit(x['id'])}, 'a', false)")
            self.assertEqual((p["ok"], p["message"]), (False, "That template isn't in the list."), x["id"])
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
            self.assertEqual(p.js("document.querySelectorAll('[data-template]').length"), 13)
            self.assertEqual(p.js("[...document.querySelectorAll('.ad-kind')].map(b => b.textContent)"),
                             ["All templates13", "Text and pictures2", "Figures2", "Work items3", "Files and links3", "People and dates2", "Notes1"])
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

    def test_after_a_click_inside_or_outside_the_box_escape_and_tab_still_work(self):
        """A click on text that cannot take focus must not drop focus to the page: Esc still closes and Tab stays inside.
        A click on the backdrop closes the box and gives focus back to what opened it."""
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.open_box(p, "ABC-S-003", focus='[data-id="ABC-S-003"] [data-drag]')
            inside = "document.activeElement.closest('[role=dialog]') ? 'in' : 'out'"
            for target in (".ad-prev h3", ".ad-prev .muted", ".ad-head h2"):
                x, y, _ = p.box(target)
                p.mouse("mousePressed", x, y, 1)
                p.mouse("mouseReleased", x, y, 0)
                self.assertEqual(p.js(inside), "in", f"focus stays in the box after a click on {target}")
                p.key("Tab", code="Tab", vk=9)
                self.assertEqual(p.js(inside), "in", f"Tab stays in the box after a click on {target}")
            x, y, _ = p.box(".ad-prev h3")
            p.mouse("mousePressed", x, y, 1)
            p.mouse("mouseReleased", x, y, 0)
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('[role=dialog]')", "Esc closed it after a click on the preview")
            self.assertTrue(wait(lambda: p.js("document.activeElement.matches('[data-id=\"ABC-S-003\"] [data-drag]')"), 5), "focus went back to the opener")
            self.open_box(p, "ABC-S-004", focus='[data-id="ABC-S-004"] [data-options]')
            p.mouse("mousePressed", 5, 5, 1)
            p.mouse("mouseReleased", 5, 5, 0)
            p.until("!document.querySelector('[role=dialog]')", "a click on the backdrop closed it")
            self.assertTrue(wait(lambda: p.js("document.activeElement.matches('[data-options]')"), 5), "focus is back on the opener")
            self.assertEqual(self.sent, [], "nothing was placed")

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
            self.assertTrue(p.js("document.activeElement.matches('input[name=template]:checked') && document.activeElement.value === 'figures-4'"),
                            "a template that cannot be placed yet can still be reached and chosen, so Down goes to it")
            p.js("var s = document.querySelector('input[type=search]'); s.value = ''; s.dispatchEvent(new Event('input', {bubbles: true}))")
            p.type("text")
            p.until("document.querySelectorAll('[data-template]').length > 2 && !!document.querySelector('input[name=template]:checked')", "a search for text")
            p.key("ArrowDown", code="ArrowDown", vk=40)
            self.assertTrue(p.js("document.activeElement.matches('input[name=template]:checked')"), "Down goes from the search to the chosen template")
            p.js("var s = document.querySelector('input[type=search]'); s.focus(); s.value = ''; s.dispatchEvent(new Event('input', {bubbles: true}))")
            p.type("zzz")
            p.until("document.querySelectorAll('[data-template]').length === 0", "nothing matches")
            self.assertEqual(p.js("document.querySelector('.ad-none').textContent"), "No template matches that search. Try another word.")
            self.assertTrue(p.js("document.querySelector('button[data-place]').disabled"), "nothing chosen: Place it is off")
            p.js("document.querySelector('[data-kind=work]').click()")
            p.js("var s = document.querySelector('input[type=search]'); s.value = ''; s.dispatchEvent(new Event('input', {bubbles: true}))")
            p.until("document.querySelectorAll('[data-template]').length === 3", "Work items shows three")
            self.assertEqual(p.js("document.querySelector('.ad-kind[aria-pressed=true]').dataset.kind"), "work")
            p.js("var s = document.querySelector('input[type=search]'); s.value = 'zzz'; s.dispatchEvent(new Event('input', {bubbles: true}))")
            p.until("document.querySelectorAll('[data-template]').length === 0", "nothing in Work items matches")
            self.assertEqual(p.js("document.querySelector('.ad-none').textContent"), "Nothing in Work items matches that search. Try another word, or choose All templates.", "worded by cause: a kind is chosen")

    def test_a_template_not_made_yet_is_read_and_reached_but_cannot_be_placed(self):
        """Every template in the box is built now: each keeps its description, can be reached with the arrow keys, previewed and
        placed, and none says it comes later. (With its ready flag off a template is refused in words: the logic tests above.)"""
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.open_box(p, "ABC-S-003")
            self.assertEqual(p.js("document.querySelectorAll('input[name=template]:not([disabled])').length"), 13, "every template can be focused")
            self.assertEqual(p.js("document.querySelector('button[data-place]').disabled"), False, "Text is chosen and can be placed")
            cat = {x["id"]: x["description"] for x in FIRST_SLICE_DESCRIPTIONS}
            for tid, desc in cat.items():
                row = p.js(f"document.querySelector('[data-template={tid}]').textContent")
                self.assertIn(desc, row, f"{tid}: its own description is readable")
                self.assertNotIn("Coming with a later release.", row, tid)
            # the arrow keys walk through all thirteen, and the preview follows; each one can be placed
            p.js("document.querySelector('input[name=template]:checked').focus()")
            seen = [p.js("document.activeElement.value")]
            for _ in range(len(FIRST_SLICE) - 1):
                p.key("ArrowDown", code="ArrowDown", vk=40)
                seen.append(p.js("document.activeElement.value"))
                self.assertFalse(p.js("document.querySelector('button[data-place]').disabled"), seen[-1])
                self.assertIsNone(p.js("document.activeElement.getAttribute('aria-disabled')"), seen[-1])
            self.assertEqual(seen, FIRST_SLICE, "the arrow keys reach every template, in order")
            self.assertEqual(p.js("document.querySelector('.ad-prev h3').textContent"), "One document")
            self.assertIn("A single file to read.", p.js("document.querySelector('.ad-prev').textContent"))
            self.assertFalse(p.js("!!document.getElementById('ad-later-prev')"), "no reason to give: it can be placed")
            self.assertIsNone(p.js("document.querySelector('button[data-place]').getAttribute('aria-describedby')"))
            self.assertEqual(self.sent, [], "reading and moving send nothing")
            p.js("document.querySelector('[data-kind=notes]').click()")
            p.until("document.querySelectorAll('[data-template]').length === 1", "Notes")
            self.assertEqual(p.js("document.querySelector('.ad-prev h3').textContent"), "Callout", "the preview shows it")
            self.assertEqual(p.js("document.querySelector('.ad-prev .ad-lbl').textContent"), "Holds")
            self.assertEqual(p.js("[...document.querySelectorAll('.ad-prev li')].map(l => l.textContent)"), ["Heading", "Callout · decision"])

    def test_the_two_help_links_open_help_at_their_entries(self):
        """'About section templates' opens the how-to and 'See every template explained in Help' the reference table. Each closes the
        box first, then opens Help over the page at that entry. No 'later release' text is left."""
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            for label, entry in (("About section templates", "howto-add-a-section-from-a-template"), ("See every template explained in Help", "ref-section-templates")):
                self.open_box(p, "ABC-S-003")
                self.assertEqual(p.js("[...document.querySelectorAll('[data-help]')].map(b => b.textContent)"),
                                 ["See every template explained in Help", "About section templates"])
                self.assertEqual(p.js("document.body.textContent.includes('Help comes in a later release')"), False)
                p.js("[...document.querySelectorAll('[data-help]')].find(b => b.textContent === %s).click()" % json.dumps(label))
                p.until("!document.querySelector('[role=dialog][aria-labelledby=ad-title]') && !!document.querySelector('#help')", "the box closed and Help opened")
                p.until("!!document.querySelector('#hp-%s.hp-found')" % entry, "Help is at " + entry)
                p.js("window.clarkPage.help.close()")
                p.until("!document.querySelector('#help')", "Help closed")
            self.assertEqual(self.sent, [])

    def test_the_button_says_add_section_and_beside_names_the_section(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.open_box(p, "ABC-S-005")                                  # Summary is alone
            self.assertEqual(p.js("document.querySelector('button[data-place]').textContent"), "Add section", "the prototype's word")
            self.assertEqual(p.js("document.querySelector('.ad-where legend').textContent"), "Where it goes", "one name for the step: the heading is Where it goes, the button is Add section")
            self.assertEqual(p.js("document.querySelector('input[name=where][value=beside]').parentElement.textContent.trim()"), "Beside “Summary” (half width)")
            p.js("document.querySelector('[data-cancel]').click()")
            p.until("!document.querySelector('[role=dialog]')", "closed")
            p.js("document.querySelector('[data-cancel]').click()")
            p.until("!document.querySelector('[role=dialog]')", "closed")
            self.open_box(p, "ABC-S-006")                                  # the left half of a pair: nothing to name
            self.assertEqual(p.js("document.querySelector('input[name=where][value=beside]').parentElement.textContent.trim()"), "Beside the section above (half width)")

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
            p.js("document.querySelector('button[data-place]').click()")
            p.until("document.querySelectorAll('.sec').length === 12", "added")
            new = [i for i in p.ids() if i not in IDS][0]
            self.assertEqual(p.ids().index(new), 7, "below Next week, after the pair")
            self.assertEqual(self.sent[-1][1]["after"], "ABC-S-007")
            self.assertEqual(self.beside_flags()["ABC-S-006"], 1, "the pair is still a pair")
            self.assertEqual(self.beside_flags()[new], 0)

    def place_beside(self, p, after="ABC-S-005"):
        self.open_box(p, after)                                        # Summary is alone
        self.assertFalse(p.js("document.querySelector('input[name=where][value=beside]').disabled"))
        p.js("document.querySelector('input[name=where][value=beside]').click()")
        p.js("document.querySelector('button[data-place]').click()")

    def test_place_it_beside_the_section_above_is_one_request_and_the_rows_are_right(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.place_beside(p)
            p.until("document.querySelectorAll('.sec').length === 12 && document.querySelectorAll('.sec.slot-left').length === 2 && !!document.querySelector('[data-undo]')", "added beside")
            new = [i for i in p.ids() if i not in IDS][0]
            self.assertEqual(p.ids()[5], new, "just below Summary")
            self.assertEqual([r[0] for r in self.sent], ["change"], "one request")
            self.assertEqual(self.sent[-1][1], {"project": "ABC", "kind": "report_sections", "op": "new", "values": {"type": "text", "title": "New section"},
                                                "after": "ABC-S-005", "beside": 1, "place": "report"})
            self.assertEqual(self.beside_flags()["ABC-S-005"], 1, "Summary is the first half")
            self.assertEqual(self.beside_flags()[new], 0)
            self.assertEqual(p.js(f"document.querySelector('[data-id=\"ABC-S-005\"]').classList.contains('slot-left') && document.querySelector('[data-id=\"{new}\"]').classList.contains('slot-right')"), True)
            self.assertEqual(p.toast(), "Text added, beside the section above.")

    def test_one_undo_takes_back_the_section_and_the_pairing(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            flags = self.beside_flags()
            self.place_beside(p)
            p.until("document.querySelectorAll('.sec').length === 12 && !!document.querySelector('[data-undo]')", "added beside")
            self.assertEqual(p.js("document.querySelectorAll('[data-undo]').length"), 1)
            p.js("document.querySelector('[data-undo]').click()")
            p.until("document.querySelectorAll('.sec').length === 11", "the section is gone after one click")
            self.assertEqual([r[0] for r in self.sent], ["change", "undo"], "one undo")
            self.assertEqual(self.ids_in_store(), IDS)
            self.assertEqual(self.beside_flags(), flags, "Summary is on its own row again")
            self.assertEqual(p.js("document.querySelectorAll('.sec.slot-left').length"), 1, "only the first pair is left")
            self.assertEqual(p.toast(), "Undone.")
            self.assertEqual(p.js("document.querySelectorAll('[data-undo]').length"), 0, "nothing more to undo")

    def test_the_last_section_can_have_the_new_one_beside_it(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.place_beside(p, "ABC-S-011")
            p.until("document.querySelectorAll('.sec').length === 12 && !!document.querySelector('[data-undo]')", "added beside the last")
            new = [i for i in p.ids() if i not in IDS][0]
            self.assertEqual(p.ids()[-1], new)
            self.assertEqual([r[0] for r in self.sent], ["change"])
            self.assertEqual(self.beside_flags()["ABC-S-011"], 1)
            self.assertEqual(p.js(f"document.querySelector('[data-id=\"ABC-S-011\"]').classList.contains('slot-left') && document.querySelector('[data-id=\"{new}\"]').classList.contains('slot-right')"), True)
            p.js("document.querySelector('[data-undo]').click()")
            p.until("document.querySelectorAll('.sec').length === 11", "one Undo")
            self.assertEqual(self.beside_flags()["ABC-S-011"], 0)

    def test_beside_is_unavailable_with_the_reason_for_a_section_that_has_a_partner(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            for after in ("ABC-S-006", "ABC-S-007"):                       # either half of This week | Next week
                self.open_box(p, after)
                self.assertTrue(p.js("document.querySelector('input[name=where][value=beside]').disabled"))
                self.assertEqual(p.js("document.getElementById('ad-w-why').textContent"), "That section already shares its row. Place it on its own row.")
                self.assertEqual(p.js("document.querySelector('input[name=where][value=beside]').getAttribute('aria-describedby')"), "ad-w-why")
                p.js("document.querySelector('[data-cancel]').click()")
                p.until("!document.querySelector('[role=dialog]')", "closed")
            self.open_box(p, "ABC-S-011")                                  # the last section: allowed, so no reason
            self.assertFalse(p.js("document.querySelector('input[name=where][value=beside]').disabled"))
            self.assertEqual(p.js("document.getElementById('ad-w-why').textContent"), "")
            p.js("document.querySelector('button[data-place]').click()")
            p.until("document.querySelectorAll('.sec').length === 12", "alone at the end")
            self.assertEqual(p.ids()[-1] not in IDS, True)
            self.assertEqual([r[0] for r in self.sent], ["change"])
            self.assertEqual(self.sent[-1][1].get("beside"), None, "alone: no beside")

    def stale_flag_on_the_last_section(self):
        """A leftover pairing flag on the last section (the page ignores it)."""
        code, _ = self.real_change({"project": "ABC", "kind": "report_sections", "op": "update", "id": "ABC-S-011", "changes": {"beside": 1}, "place": "report"})
        self.assertEqual(code, 200)

    def test_a_plain_add_below_a_stale_flag_is_one_request_and_one_undo(self):
        self.stale_flag_on_the_last_section()
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.open_box(p, "ABC-S-011")
            p.js("document.querySelector('button[data-place]').click()")
            p.until("document.querySelectorAll('.sec').length === 12 && !!document.querySelector('[data-undo]')", "added")
            new = [i for i in p.ids() if i not in IDS][0]
            self.assertEqual([r[1]["op"] for r in self.sent], ["new"], "one request")
            self.assertEqual(self.beside_flags()["ABC-S-011"], 0)
            self.assertEqual(p.js(f"document.querySelector('[data-id=\"{new}\"]').classList.contains('slot-full')"), True, "on its own row")
            self.assertEqual(p.js("document.querySelectorAll('[data-undo]').length"), 1)
            p.js("document.querySelector('[data-undo]').click()")
            p.until("document.querySelectorAll('.sec').length === 11", "the section is gone after one click")
            self.assertEqual([r[0] for r in self.sent].count("undo"), 1, "one undo")
            self.assertEqual(self.ids_in_store(), IDS)
            self.assertEqual(self.beside_flags()["ABC-S-011"], 1, "the flag is as it was")
            self.assertEqual(p.toast(), "Undone.")

    def test_a_stale_beside_add_that_clark_refuses_reads_the_page_again(self):
        """The page was out of date (a section was added elsewhere); clark refuses the beside add, and the page shows what clark holds."""
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()

            def refuse_after_a_change_elsewhere(req):
                if req.get("op") == "new":
                    self.real_change({"project": "ABC", "kind": "report_sections", "op": "new", "values": {"type": "text", "title": "Added elsewhere"},
                                      "after": "ABC-S-003", "place": "report"})
                    return 400, {"ok": False, "message": "x", "code": "refused"}
                return self.real_change(req)
            self.failure = refuse_after_a_change_elsewhere
            self.place_beside(p, "ABC-S-011")
            p.until("!!document.querySelector('.toast.problem')", "the toast says it failed")
            p.until("document.querySelectorAll('.sec').length === 12", "the page was read again and shows the section added elsewhere")

    def test_the_plain_add_is_one_step_and_one_undo(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.open_box(p, "ABC-S-003")
            p.js("document.querySelector('button[data-place]').click()")
            p.until("document.querySelectorAll('.sec').length === 12 && !!document.querySelector('[data-undo]')", "added")
            self.assertEqual([r[0] for r in self.sent], ["change"], "one request")
            p.js("document.querySelector('[data-undo]').click()")
            p.until("document.querySelectorAll('.sec').length === 11", "Undo took it away")
            self.assertEqual([r[0] for r in self.sent], ["change", "undo"], "one undo")
            self.assertEqual(self.ids_in_store(), IDS)

    def test_a_refusal_from_clark_is_in_the_toast_and_focus_goes_back(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.failure = lambda req: (409, {"ok": False, "error": "x"})
            self.open_box(p, "ABC-S-003", focus='[data-id="ABC-S-003"] [data-drag]')
            p.js("document.querySelector('button[data-place]').click()")
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

    def test_at_900_wide_the_placing_choice_is_in_view_without_scrolling_the_template_list(self):
        """At 900 px the box is one column; the choice between its own row and beside the next must not sit below all ten templates."""
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 900, "height": 700, "deviceScaleFactor": 1, "mobile": False}, p.sid)
            self.open_box(p, "ABC-S-003")
            self.assertEqual(p.js("document.querySelector('.ad-main').scrollTop"), 0, "nothing scrolled")
            seen = p.js("""(function(){var m=document.querySelector('.ad-main').getBoundingClientRect(), w=document.querySelector('.ad-where').getBoundingClientRect(),
                l=document.querySelector('.ad-list').getBoundingClientRect(), b=document.querySelector('button[data-place]').getBoundingClientRect();
                return {inView: w.top >= m.top && w.bottom <= m.bottom, aboveList: w.bottom <= l.top + 1, buttonInView: b.bottom <= window.innerHeight};})()""")
            self.assertEqual(seen, {"inView": True, "aboveList": True, "buttonInView": True})
            p.js("document.querySelector('[data-cancel]').click()")

    def test_the_dom_and_tab_order_is_kinds_choice_list_preview_at_900_and_desktop(self):
        """The same order in the markup, not a CSS reorder: kinds, the placing choice, the list, the preview; the preview is a real box."""
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            for width in (900, 1400):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                self.open_box(p, "ABC-S-003")
                order = p.js("""(function(){var q=function(s){return document.querySelector(s);}, ks=[q('.ad-kinds'), q('.ad-where'), q('.ad-list'), q('.ad-prev')], ok=true;
                    for (var i=0;i<3;i++) ok = ok && !!(ks[i].compareDocumentPosition(ks[i+1]) & Node.DOCUMENT_POSITION_FOLLOWING);
                    return {ok: ok, prevDisplay: getComputedStyle(q('.ad-prev')).display, prevBox: q('.ad-prev').getBoundingClientRect().width > 0,
                      label: q('.ad-prev').getAttribute('aria-label'), live: q('.ad-prev').getAttribute('aria-live'),
                      announced: [...document.querySelectorAll('.ad-prev [aria-live]')].map(e => e.tagName)};})()""")
                self.assertEqual(order, {"ok": True, "prevDisplay": "block", "prevBox": True, "label": "About this template", "live": None, "announced": ["H3", "P"]},
                                 f"{width}: only the heading and the description are announced when the choice changes, not the whole preview")
                seq = []
                for _ in range(16):
                    p.key("Tab", code="Tab", vk=9)
                    seq.append(p.js("""(function(){var a=document.activeElement;
                        return a.closest('.ad-where') ? 'choice' : a.closest('.ad-kinds') ? 'kinds' : a.closest('.ad-list') ? 'list' : a.closest('.ad-prev') ? 'preview' : a.closest('.ad-head') ? 'search' : 'foot';})()"""))
                first = {k: seq.index(k) for k in ("kinds", "choice", "list") if k in seq}
                self.assertTrue(first["kinds"] < first["choice"] < first["list"], f"{width}: Tab goes kinds, choice, list: {seq}")
                if "preview" in seq:
                    self.assertTrue(first["list"] < seq.index("preview"), f"{width}: then the preview: {seq}")
                p.js("document.querySelector('[data-cancel]').click()")
                p.until("!document.querySelector('[role=dialog]')", "closed")

    def test_the_focus_ring_is_the_brand_blue_in_light_and_dark_and_the_scrim_is_a_token(self):
        """Every focus ring in the box is --brand-blue (the cyan --focus is 1.8:1 on white); the scrim names no raw colour."""
        css = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
        block = [ln for ln in css.splitlines() if ln.startswith((".ad", ".pk-btn"))]
        self.assertFalse([ln for ln in block if "var(--focus)" in ln and ".ad" in ln], "no ring in the box uses the cyan focus colour")
        self.assertFalse([ln for ln in css.splitlines() if ln.startswith(".ad-scrim") and "rgba(" in ln], "the scrim is made from a token")
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            probe = ("(function(){var d=document.createElement('i');d.style.color='var(--brand-blue)';document.body.appendChild(d);"
                     "var c=getComputedStyle(d).color;d.remove();return c;})()")
            for theme in ("light", "dark"):
                p.js(f"document.documentElement.setAttribute('data-theme', {json.dumps(theme)})")
                self.open_box(p, "ABC-S-003")
                want = p.js(probe)
                for sel in ("input[type=search]", ".ad-kind", "input[name=template]", "input[name=where]", "button[data-place]", "[data-cancel]"):
                    p.js(f"document.querySelector({json.dumps(sel)}).focus()")
                    got = p.js(f"(function(){{var e=document.querySelector({json.dumps(sel)});return e.matches(':focus-visible') ? getComputedStyle(e).outlineColor : 'not visible';}})()")
                    self.assertIn(got, (want, "not visible"), f"{theme}: {sel}")
                    if got == "not visible":
                        p.key("Tab", code="Tab", vk=9)
                        p.key("Tab", 8, code="Tab", vk=9)
                        got = p.js("getComputedStyle(document.activeElement).outlineColor")
                        self.assertEqual(got, want, f"{theme}: {sel} ring is the brand blue")
                p.js("document.querySelector('[data-cancel]').click()")
                p.until("!document.querySelector('[role=dialog]')", "closed")

    def test_the_box_adds_no_edit_part_to_the_published_page(self):
        self.assertNotIn("clark:add-section", (SRC / "clark" / "page" / "page-view.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
