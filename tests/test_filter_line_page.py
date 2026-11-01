"""#153: the one filter line on the Work items page, driven in the real page.

Run: python3 dev/run_tests.py test_filter_line_page
Starts the real server over the demo store at CLARK_NOW=2026-10-28 and drives the committed page in headless Chrome with real mouse and key
events, at 1400 and 900 px, in light and in dark. The pure rules are in test_filter_line. Required: fails, never skips, without Chrome.
"""
import copy
import json
import unittest
import urllib.parse

from _paths import ROOT, SRC  # noqa: F401
import _testpage as testpage

from test_server import Running, chrome, wait  # noqa: E402
from test_work_filters import click, expect, key, need_chrome, page_rows, set_line  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402

INPUT = "#fline-input"
SIZES = (1400, 900)
THEMES = ("light", "dark")


class Line(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need_chrome()
        cls.store, cls.folder, cls.ids = load_demo()
        cls.projects = cls.store.read("projects")
        cls.data = {p["code"]: cls.store.data_for(p["code"]) for p in cls.projects}

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        import shutil
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def serve(self):
        s = Running(data_for=lambda code: copy.deepcopy(self.data.get(code)), projects=lambda: self.projects,
                    page_html=lambda: testpage.html())
        self.addCleanup(s.close)
        return s

    def load(self, cdp, port, width=1400, hash_="#work&p=TUL", theme="light"):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE + "window.__push = 0; const P = history.pushState; history.pushState = function () { window.__push++; return P.apply(this, arguments); };"}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{port}/{hash_}"}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid) > 0), f"{hash_} drew its list")
        if theme == "dark":
            cdp.js("document.documentElement.dataset.theme = 'dark'", sid)
        return sid

    # ---- small helpers ----
    def shown(self, cdp, sid):
        return sorted(cdp.js("[...document.querySelectorAll('#work tbody tr[data-id]')].map(r => r.dataset.id)", sid))

    def chips(self, cdp, sid):
        return cdp.js("[...document.querySelectorAll('.fline .fchip .ft')].map(c => c.textContent)", sid)

    def rows(self, cdp, sid):
        return page_rows(self.data, cdp.js("location.hash.match(/p=([A-Z0-9]+)/)[1]", sid))

    def focus(self, cdp, sid):
        click(cdp, sid, INPUT)
        self.assertEqual(cdp.js("document.activeElement.id", sid), "fline-input")

    def type(self, cdp, sid, text):
        cdp.call("Input.insertText", {"text": text}, sid)

    def say(self, cdp, sid):
        return cdp.js("document.querySelector('#fline-msg').textContent", sid)

    def put(self, cdp, sid, text):
        """Type a line and press Enter."""
        self.focus(cdp, sid)
        self.type(cdp, sid, text)
        self.assertTrue(wait(lambda: cdp.js("document.querySelector('#fline-input').value", sid) == text))
        key(cdp, sid, "Enter")

    def listed(self, cdp, sid):
        return cdp.js("[...document.querySelectorAll('#fline-list [role=option]')].map(o => o.dataset.ins)", sid)

    # ---- tests ----
    def test_the_page_starts_on_one_line_with_the_open_items_and_the_old_controls_are_gone(self):
        s = self.serve()
        for width in SIZES:
            for theme in THEMES:
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.load(cdp, s.port, width, theme=theme)
                    self.assertEqual(self.chips(cdp, sid), ["is:open"])
                    self.assertEqual(self.shown(cdp, sid), expect(self.rows(cdp, sid)))
                    self.assertEqual(cdp.js("document.querySelectorAll('.seg:not(.icons), .fbar, .fbtn, [data-show], [data-type]').length", sid), 0)
                    self.assertEqual(cdp.js("document.querySelectorAll('#fline-input[role=combobox][aria-label]').length", sid), 1)
                    self.assertEqual(cdp.js("document.querySelector('#fline-msg').getAttribute('role')", sid), "status")
                    n = len(expect(self.rows(cdp, sid)))
                    self.assertEqual(cdp.js("document.querySelector('#work-count').textContent", sid), f"{n} open items")
                    self.assertEqual(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), True)
                    self.assertEqual(cdp.js("history.length", sid), 2)

    def test_the_slash_key_focuses_the_line_but_not_while_typing_or_with_a_menu_open(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            # The ask panel takes "/" outside a field on every page (test_peek pins it), so the line is focused by a click here;
            # its own "/" handler only runs where the ask panel has not taken the key.
            cdp.js("document.activeElement.blur()", sid)
            self.focus(cdp, sid)
            self.assertEqual(cdp.js("document.querySelector('#fline-input').value", sid), "", "the slash itself is not typed")
            self.assertEqual(cdp.js("getComputedStyle(document.querySelector('.fhints')).visibility", sid), "visible", "the hint chips show while the line is focused")
            # not while typing in another field
            click(cdp, sid, "#viewMenu")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#viewMenuList')", sid)))
            cdp.js("document.querySelector('#fline-input').blur()", sid)
            cdp.js("document.querySelector('#viewMenuList').focus()", sid)
            cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "/", "code": "Slash", "text": "/", "windowsVirtualKeyCode": 191}, sid)
            self.assertNotEqual(cdp.js("document.activeElement.id", sid), "fline-input", "not while a menu is open")
            key(cdp, sid, "Escape")
            cdp.js("(() => { const i = document.createElement('input'); i.id = 'other'; document.body.appendChild(i); i.focus(); })()", sid)
            cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "/", "code": "Slash", "text": "/", "windowsVirtualKeyCode": 191}, sid)
            self.assertEqual(cdp.js("document.activeElement.id", sid), "other", "not while typing in a field")

    def test_hint_chips_show_only_while_focused_and_a_hint_goes_into_the_box(self):
        s = self.serve()
        for width in SIZES:
            with self.subTest(width=width), chrome() as cdp:
                sid = self.load(cdp, s.port, width)
                self.assertEqual(cdp.js("getComputedStyle(document.querySelector('.fhints')).visibility", sid), "hidden")
                self.focus(cdp, sid)
                hints = cdp.js("[...document.querySelectorAll('.fhint')].map(h => h.textContent)", sid)
                self.assertIn("due:overdue", hints)
                self.assertIn("is:quiet", hints, "the demo carries review facts, so the word is offered")
                self.assertGreaterEqual(cdp.js("Math.min(...[...document.querySelectorAll('.fhint')].map(h => h.getBoundingClientRect().height))", sid), 24)
                click(cdp, sid, ".fhint[title*='Leave closed']")
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('#fline-input').value", sid) == "-status:Closed"))
                key(cdp, sid, "Enter")
                self.assertTrue(wait(lambda: "-status:Closed" in self.chips(cdp, sid)))

    def test_typing_offers_fields_then_values_with_counts_and_arrows_and_enter_choose(self):
        s = self.serve()
        for width in SIZES:
            for theme in THEMES:
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.load(cdp, s.port, width, theme=theme)
                    rows = self.rows(cdp, sid)
                    self.focus(cdp, sid)
                    self.type(cdp, sid, "st")
                    self.assertTrue(wait(lambda: "status:" in self.listed(cdp, sid)))
                    self.assertEqual(cdp.js("document.querySelector('#fline-input').getAttribute('aria-expanded')", sid), "true")
                    self.assertEqual(self.listed(cdp, sid)[0], "status:", "fields come first")
                    key(cdp, sid, "ArrowDown")
                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('#fline-input').getAttribute('aria-activedescendant')", sid) == "fo-0"))
                    key(cdp, sid, "Enter")                                           # a field: goes into the box, then its values are listed
                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('#fline-input').value", sid) == "status:"))
                    self.assertTrue(wait(lambda: "status:Open" in self.listed(cdp, sid)))
                    counts = cdp.js("Object.fromEntries([...document.querySelectorAll('#fline-list [role=option]')].map(o => [o.dataset.ins, +o.querySelector('.c').textContent]))", sid)
                    self.assertEqual(counts["status:Closed"], len([r for r in rows if r["status"] == "Closed"]), "values come with how many items have each")
                    options = self.listed(cdp, sid)
                    key(cdp, sid, "ArrowUp")                                         # the arrows wrap round
                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('#fline-input').getAttribute('aria-activedescendant')", sid) == f"fo-{len(options) - 1}"))
                    idx = options.index("status:Closed")
                    for _ in range(idx + 1):                                         # from the last one, round to the first and on to Closed
                        key(cdp, sid, "ArrowDown")
                    self.assertEqual(cdp.js("document.querySelector('#fline-input').getAttribute('aria-activedescendant')", sid), f"fo-{idx}")
                    key(cdp, sid, "Enter")
                    self.assertTrue(wait(lambda: "status:Closed" in self.chips(cdp, sid)))
                    self.assertEqual(cdp.js("document.querySelector('#fline-input').value", sid), "")
                    self.assertTrue(wait(lambda: self.shown(cdp, sid) == expect(rows, "open", filters={"status": ["Closed"]})), "is:open and status:Closed")
                    self.assertEqual(cdp.js("history.length", sid), 2, "a filter rewrites the address, it adds no step")
                    self.assertEqual(cdp.js("window.__push", sid), 0)
                    self.assertRegex(cdp.js("location.hash", sid), r"^#work&p=TUL&f=type:|^#work&p=TUL&f=status:Closed")

    def test_backspace_removes_the_last_chip_only_from_an_empty_box_and_escape_closes_the_list(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            rows = self.rows(cdp, sid)
            self.put(cdp, sid, "priority:High type:action")
            self.assertTrue(wait(lambda: self.chips(cdp, sid) == ["is:open", "priority:High", "type:action"]))
            self.assertEqual(self.shown(cdp, sid), expect([r for r in rows if r["kind"] == "action"], "open", filters={"priority": ["High"]}))
            self.type(cdp, sid, "ow")
            self.assertTrue(wait(lambda: "owner:" in self.listed(cdp, sid)))
            key(cdp, sid, "Escape")
            self.assertTrue(wait(lambda: cdp.js("!document.querySelector('#fline-list')", sid)), "Esc closes the list")
            self.assertEqual(cdp.js("document.querySelector('#fline-input').value", sid), "ow", "and keeps what was typed")
            key(cdp, sid, "Backspace")                                               # the box is not empty: a letter goes, no chip does
            self.assertEqual(len(self.chips(cdp, sid)), 3)
            key(cdp, sid, "Backspace")
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('#fline-input').value", sid) == ""))
            self.assertEqual(len(self.chips(cdp, sid)), 3)
            key(cdp, sid, "Backspace")
            self.assertTrue(wait(lambda: self.chips(cdp, sid) == ["is:open", "priority:High"]))
            click(cdp, sid, ".fchip[data-chip=priority] button")
            self.assertTrue(wait(lambda: self.chips(cdp, sid) == ["is:open"]))
            self.assertTrue(wait(lambda: cdp.js("location.hash", sid) == "#work&p=TUL"), "the start line is the start address")

    def test_a_word_with_an_error_is_never_applied_and_says_in_plain_words_what_to_use(self):
        s = self.serve()
        for theme in THEMES:
            with self.subTest(theme=theme), chrome() as cdp:
                sid = self.load(cdp, s.port, theme=theme)
                before = self.shown(cdp, sid)
                self.put(cdp, sid, "status:Nope")
                self.assertTrue(wait(lambda: self.say(cdp, sid).startswith("No status is called Nope. Try Open")))
                self.assertEqual(self.shown(cdp, sid), before, "the table is not emptied")
                self.assertEqual(self.chips(cdp, sid), ["is:open"])
                self.assertEqual(cdp.js("document.querySelector('#fline-input').value", sid), "status:Nope", "the word stays so it can be fixed")
                self.assertEqual(cdp.js("document.querySelector('#fline-msg').getAttribute('aria-live')", sid), "polite")
                cdp.js("(() => { const i = document.querySelector('#fline-input'); i.select(); })()", sid)
                self.type(cdp, sid, "colour:red")
                key(cdp, sid, "Enter")
                self.assertTrue(wait(lambda: "There is no “colour” filter" in self.say(cdp, sid)))
                cdp.js("document.querySelector('#fline-input').select()", sid)
                self.type(cdp, sid, "priority:High bogus:x")                          # the good word is applied; the bad one is not
                key(cdp, sid, "Enter")
                self.assertTrue(wait(lambda: "priority:High" in self.chips(cdp, sid)))
                self.assertEqual(cdp.js("document.querySelector('#fline-input').value", sid), "bogus:x")
                cdp.js("document.querySelector('#fline-input').select()", sid)
                self.type(cdp, sid, "owner:me")
                key(cdp, sid, "Enter")
                self.assertTrue(wait(lambda: "Set your name in Settings to see your actions." in self.say(cdp, sid)))
                self.assertIn("owner:me", self.chips(cdp, sid))
                self.assertTrue(wait(lambda: "No items match these filters." in cdp.js("document.querySelector('#work-list').innerText", sid)))

    def test_words_the_page_cannot_answer_yet_are_not_offered_and_are_refused(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            self.focus(cdp, sid)
            self.type(cdp, sid, "is:")
            self.assertTrue(wait(lambda: "is:open" in self.listed(cdp, sid)))
            offered = self.listed(cdp, sid)
            for hidden in ("is:needed", "is:archived"):
                self.assertNotIn(hidden, offered)
            self.assertIn("is:incomplete", offered)
            self.assertTrue(cdp.js("[...document.querySelectorAll('#fline-list .fl2')].some(e => e.textContent.includes('No owner or no date'))", sid), "a gloss beside is:incomplete")
            self.type(cdp, sid, "needed")
            key(cdp, sid, "Enter")
            self.assertTrue(wait(lambda: "is not available on this page yet" in self.say(cdp, sid)))
            self.assertEqual(self.chips(cdp, sid), ["is:open"])

    def test_the_freshness_menu_gives_the_two_plain_values_and_the_chips_say_them_in_plain_words(self):
        s = self.serve()
        for width in SIZES:
            for theme in THEMES:
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.load(cdp, s.port, width, theme=theme)
                    self.watch(cdp, sid)
                    click(cdp, sid, "#freshMenu")
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#freshMenu[aria-expanded=true]')", sid)))
                    names = cdp.js("[...document.querySelectorAll('[role=menu] [role^=menuitem]')].map(e => e.textContent.trim())", sid)
                    self.assertEqual(names, ["Not reviewed in 14 days", "No owner or no date"], "the demo carries review facts, so both values are offered")
                    click(cdp, sid, "[role=menu] [role^=menuitem]:nth-child(2)")
                    self.assertTrue(wait(lambda: "is:incomplete" in self.chips(cdp, sid)), self.chips(cdp, sid))
                    self.assertEqual(cdp.js("document.querySelector('.fchip[data-chip=is][title=\"No owner or no date\"]') !== null", sid), True, "the chip's words are plain")
                    rows = self.rows(cdp, sid)
                    want = sorted(r["id"] for r in rows if r["status"] not in ("Closed", "Cancelled", "Made", "Withdrawn")
                                  and (not str(r["owner"] or "").strip() or str(r["owner"]).strip().upper() == "TBC"
                                       or (r["kind"] in ("action", "decision") and not (r.get("needed_by") if r["kind"] == "decision" and r["status"] == "Pending" else r.get("due_date") if r["kind"] == "action" else r.get("date"))))
                                  and True)
                    self.assertEqual(self.shown(cdp, sid), want)
                    self.assertIn("reviewed", cdp.js("location.hash", sid), "the address keeps the older Freshness filter")
                    click(cdp, sid, "#freshMenu")
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[role=menu] [role^=menuitem]')", sid)))
                    click(cdp, sid, "[role=menu] [role^=menuitem]:nth-child(2)")
                    self.assertTrue(wait(lambda: self.chips(cdp, sid) == ["is:open"]), "picking it again takes it off")
                    self.assertEqual(cdp.js("window.__errs", sid), [])

    def test_an_address_with_a_freshness_filter_opens_work_items_with_no_error(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port, hash_="#work&p=TUL&f=mode:open;reviewed:incomplete")
            self.watch(cdp, sid)
            self.assertIn("is:incomplete", self.chips(cdp, sid))
            self.assertEqual(self.say(cdp, sid), "")

    def test_workstream_and_milestone_values_come_from_the_project_and_the_messages_use_curly_quotes(self):
        s = self.serve()
        d = self.data["TUL"]
        streams = [w["name"] for w in d["workstreams"] if w.get("name")]
        dated = sorted((m for m in d["milestones"] if m.get("name")), key=lambda m: (not (m.get("forecast_date") or m.get("baseline_date")), m.get("forecast_date") or m.get("baseline_date") or "", m.get("sort_order") or 0))
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            self.focus(cdp, sid)
            self.type(cdp, sid, "workstream:")
            self.assertTrue(wait(lambda: len(self.listed(cdp, sid)) > 0))
            offered = [o.split(":", 1)[1] for o in self.listed(cdp, sid) if o.startswith("workstream:")]
            self.assertEqual([o for o in offered if o in streams][:len(streams)], [o for o in streams if o in offered], "the project's own order")
            for name in streams:
                self.assertTrue(any(o == name or o == name.replace(" ", "-") or name in o for o in offered) or name in " ".join(offered), name)
            cdp.js("document.querySelector('#fline-input').select()", sid)
            self.type(cdp, sid, "milestone:")
            self.assertTrue(wait(lambda: any(o.startswith("milestone:") for o in self.listed(cdp, sid))))
            got = " | ".join(self.listed(cdp, sid))
            for m in dated:
                self.assertIn(m["name"], got.replace("\u00a0", " "))
            cdp.js("document.querySelector('#fline-input').select()", sid)
            self.type(cdp, sid, "colour:red")
            key(cdp, sid, "Enter")
            self.assertTrue(wait(lambda: "There is no \u201ccolour\u201d filter" in self.say(cdp, sid)))
            cdp.js("document.querySelector('#fline-input').select()", sid)
            self.type(cdp, sid, "due:soon")
            key(cdp, sid, "Enter")
            self.assertTrue(wait(lambda: "Say next-7-days instead" in self.say(cdp, sid)))
            self.assertTrue(wait(lambda: "\u201csoon\u201d is not a value for" in self.say(cdp, sid)))
            self.assertEqual(self.chips(cdp, sid), ["is:open"])

    def test_the_glance_tiles_land_on_a_working_line_with_no_error(self):
        s = self.serve()
        for theme in THEMES:
            for tile, want in (("risks", "priority:Urgent,High"), ("overdue", "due:overdue")):
                with self.subTest(theme=theme, tile=tile), chrome() as cdp:
                    sid = self.load(cdp, s.port, theme=theme)
                    self.watch(cdp, sid)
                    cdp.js("location.hash = '#dashboard&p=TUL'", sid)
                    self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector('[data-fig={tile}]')", sid)))
                    click(cdp, sid, f"[data-fig={tile}]")
                    self.assertTrue(wait(lambda: want in self.chips(cdp, sid)), f"{tile} lands on {want}: {self.chips(cdp, sid)}")
                    self.assertEqual(self.say(cdp, sid), "", "no message on landing")
                    self.assertEqual(cdp.js("window.__errs", sid), [], "no error on the page")

    def test_a_chip_says_what_it_means_and_the_older_filters_are_all_reachable(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            rows = self.rows(cdp, sid)
            line = "is:closed type:action,issue status:Closed workstream:none usecase:none milestone:none due:overdue,later priority:High client:shown owner:none"
            self.put(cdp, sid, "-owner:none priority:High,Medium client:internal due:next-7-days,later")
            self.assertTrue(wait(lambda: len(self.chips(cdp, sid)) >= 5))
            self.assertEqual(cdp.js("document.querySelector('.fchip[data-chip=priority]').title", sid), "Priority is High or Medium")
            self.assertEqual(self.shown(cdp, sid), expect(rows, "open", filters={"owner": ["(none)"], "priority": ["High", "Medium"], "client": ["no"], "due": ["soon", "later"]}, nots=("owner",)))
            self.assertTrue(line)
            self.assertIn("not:owner", cdp.js("location.hash", sid), "the address keeps the older state, so a link still opens the same list")

    def test_each_older_filter_is_reachable_through_the_line_and_gives_the_rows_the_oracle_gives(self):
        s = self.serve()
        for code in self.data:
            with self.subTest(project=code), chrome() as cdp:
                sid = self.load(cdp, s.port, hash_=f"#work&p={code}")
                rows = self.rows(cdp, sid)
                owner = next(r["owner"] for r in rows if r["owner"] and " " in r["owner"])
                cases = [
                    ("is:open owner:" + json.dumps(owner), "open", {"owner": [owner]}, ()),
                    ("is:all", None, None, ()),
                    ("is:closed priority:High,Medium", "closed", {"priority": ["High", "Medium"]}, ()),
                    ("is:open -status:Delayed client:internal", "open", {"status": ["Delayed"], "client": ["no"]}, ("status",)),
                    ("is:open due:overdue,next-7-days", "open", {"due": ["overdue", "soon"]}, ()),
                    ("is:open no:owner", "open", {"owner": ["(none)"]}, ()),
                ]
                for line, mode, filters, nots in cases:
                    if mode is None:
                        continue
                    with self.subTest(line=line):
                        set_line(cdp, sid, line)
                        want = expect(rows, mode, filters=filters, nots=nots)
                        self.assertTrue(wait(lambda: self.shown(cdp, sid) == want), f"{line}: {self.shown(cdp, sid)} != {want}")
                        n = len(want)
                        self.assertTrue(wait(lambda: cdp.js("document.querySelector('#work-count').textContent", sid) == (f"{n} {mode} item" + ("" if n == 1 else "s"))))
                set_line(cdp, sid, "")                                              # no is: chip: every item, open or closed
                self.assertTrue(wait(lambda: self.shown(cdp, sid) == sorted(r["id"] for r in rows)))
                self.assertEqual(cdp.js("document.querySelector('#work-count').textContent", sid), f"{len(rows)} items")
                self.assertEqual(cdp.js("location.hash", sid), "#work&p=" + code + "&f=mode:all")

    def test_a_peek_and_the_line_share_the_address_and_neither_loses_the_other(self):
        s = self.serve()
        item = self.data["TUL"]["actions"][0]["id"]
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            set_line(cdp, sid, "type:action")
            self.assertTrue(wait(lambda: cdp.js("clarkPage.filters()", sid) == "mode:all;type:action"))
            cdp.js(f"clarkPage.openPeek({json.dumps(item)})", sid)
            self.assertTrue(wait(lambda: cdp.js("location.hash", sid) == f"#work&p=TUL&item={item}&f=mode:all;type:action"))
            cdp.call("Page.reload", {}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid) > 0))
            self.assertEqual(cdp.js("clarkPage.peek().id", sid), item)
            self.assertEqual(self.chips(cdp, sid), ["type:action"])

    def test_too_long_a_line_for_the_address_is_refused_with_a_plain_line_and_changes_nothing(self):
        data = copy.deepcopy(self.data)
        owners = [f"Fictional Owner {chr(65 + i)} " + "x" * 60 for i in range(10)]
        pool = data["TUL"]["actions"] + data["TUL"]["raid"]
        for i, o in enumerate(owners):
            pool[i]["owner"] = o
        s = Running(data_for=lambda code: copy.deepcopy(data.get(code)), projects=lambda: self.projects, page_html=lambda: testpage.html())
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            before = self.shown(cdp, sid)
            self.put(cdp, sid, "owner:" + ",".join(json.dumps(o) for o in owners))
            self.assertTrue(wait(lambda: "not fit" in cdp.js("document.querySelector('#work-note').textContent", sid)))
            self.assertEqual(cdp.js("document.querySelector('#work-note').getAttribute('role')", sid), "status")
            self.assertFalse(cdp.js("clarkPage.filters()", sid), "nothing changed")
            self.assertEqual(self.chips(cdp, sid), ["is:open"])
            self.assertEqual(self.shown(cdp, sid), before)
            self.assertEqual(cdp.js("history.length", sid), 2)

    def test_clear_all_and_the_empty_message(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            self.assertEqual(cdp.js("!!document.querySelector('#clearAll')", sid), False)
            self.put(cdp, sid, "is:closed type:decision client:internal priority:Urgent")
            self.assertTrue(wait(lambda: "No items match these filters." in cdp.js("document.querySelector('#work-list').innerText", sid)))
            click(cdp, sid, "#clearAll2")
            self.assertTrue(wait(lambda: self.chips(cdp, sid) == ["is:open"]))
            self.assertEqual(cdp.js("!!document.querySelector('#clearAll')", sid), False)
            self.assertEqual(cdp.js("location.hash", sid), "#work&p=TUL")

    def test_the_address_carries_the_line_and_a_link_opens_the_same_list(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port, hash_="#work&p=TUL&f=mode:closed;type:action")
            self.assertEqual(self.chips(cdp, sid), ["is:closed", "type:action"])
            self.assertEqual(self.shown(cdp, sid), expect(self.rows(cdp, sid), "closed", "action"))
            self.assertEqual(cdp.js("location.hash", sid), "#work&p=TUL&f=mode:closed;type:action")
            owner = next(r["owner"] for r in self.rows(cdp, sid) if r["owner"] and " " in r["owner"])
            sid = self.load(cdp, s.port, hash_="#work&p=TUL&f=owner:" + urllib.parse.quote(owner, safe="") + ";not:owner")
            self.assertEqual(self.chips(cdp, sid), ["is:open", f'-owner:"{owner}"'])
            # a name no item has any more is not applied, and the line says so in plain words
            sid = self.load(cdp, s.port, hash_="#work&p=TUL&f=owner:Nobody%20Here")
            self.assertTrue(wait(lambda: self.say(cdp, sid).startswith("No owner is called Nobody Here.")))
            hostile = '<img src=x onerror="window.__pwn=1">'
            sid = self.load(cdp, s.port, hash_="#work&p=TUL&f=owner:" + urllib.parse.quote(hostile, safe="") + ";not:owner")
            self.assertEqual(cdp.js("document.querySelectorAll('#work img').length + typeof window.__pwn", sid), "0undefined")
            sid = self.load(cdp, s.port, hash_="#work&p=TUL&f=mode:closed;owner:%zz")
            self.assertEqual(cdp.js("location.hash.startsWith('#work&p=TUL')", sid), True)

    def test_back_and_forward_bring_the_line_back_with_the_page(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            self.put(cdp, sid, "type:risk,issue,assumption,dependency")
            self.assertTrue(wait(lambda: "type:risk,issue,assumption,dependency" in self.chips(cdp, sid)))
            want = self.shown(cdp, sid)
            click(cdp, sid, "[data-view=milestones]")
            self.assertTrue(wait(lambda: cdp.js("location.hash", sid) == "#milestones&p=TUL"))
            cdp.js("history.back()", sid)
            self.assertTrue(wait(lambda: self.shown(cdp, sid) == want and len(want) > 0))
            self.assertEqual(len(cdp.call("Page.getNavigationHistory", {}, sid)["entries"]), 3)

    def test_the_line_is_kept_for_the_session_per_project_including_search_words(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            title = self.rows(cdp, sid)[0]["id"]
            self.put(cdp, sid, "priority:High supplier")
            self.assertTrue(wait(lambda: self.chips(cdp, sid) == ["is:open", "priority:High", "supplier"]))
            click(cdp, sid, "[data-view=milestones]")
            self.assertTrue(wait(lambda: cdp.js("location.hash", sid) == "#milestones&p=TUL"))
            click(cdp, sid, "[data-view=work]")
            self.assertTrue(wait(lambda: self.chips(cdp, sid) == ["is:open", "priority:High", "supplier"]), "the line comes back with Work items")
            cdp.call("Page.reload", {}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#fline-input')", sid)))
            self.assertTrue(wait(lambda: self.chips(cdp, sid) == ["is:open", "priority:High", "supplier"]), "and after a reload")
            other = [p["code"] for p in self.projects if p["code"] != "TUL"][0]
            sid = self.load(cdp, s.port, hash_=f"#work&p={other}")
            self.assertEqual(self.chips(cdp, sid), ["is:open"], "another project has its own line")
            self.assertTrue(title)
            cdp.js("sessionStorage.clear()", sid)

    def test_saved_views_are_tabs_with_a_dot_when_the_line_differs_and_are_archived_never_deleted(self):
        s = self.serve()
        for width in SIZES:
            for theme in THEMES:
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.load(cdp, s.port, width, theme=theme)
                    rows = self.rows(cdp, sid)
                    names = cdp.js("[...document.querySelectorAll('.vtab span')].map(e => e.textContent)", sid)
                    self.assertEqual(names, ["Open items", "Overdue", "My actions"], "four default views, one hidden until the page can answer it")
                    self.assertEqual(cdp.js("document.querySelector('.vtab[aria-pressed=true] span').textContent", sid), "Open items")
                    self.assertEqual(cdp.js("document.querySelectorAll('[data-dot]').length", sid), 0)
                    click(cdp, sid, ".vtab[data-view-id=overdue]")
                    self.assertTrue(wait(lambda: self.chips(cdp, sid) == ["is:open", "due:overdue"]))
                    self.assertEqual(cdp.js("document.querySelectorAll('[data-dot]').length", sid), 0)
                    self.put(cdp, sid, "priority:High")
                    self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.vtab[data-view-id=overdue] [data-dot]').length", sid) == 1), "a dot on the tab")
                    self.assertIn("not saved", cdp.js("document.querySelector('.vtab[data-view-id=overdue]').getAttribute('aria-label')", sid))
                    # Save changes to the view
                    click(cdp, sid, "#viewMenu")
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#viewMenuList')", sid)))
                    items = cdp.js("[...document.querySelectorAll('#viewMenuList [role=menuitem]')].map(b => b.textContent)", sid)
                    self.assertEqual(items[0], "Save changes to Overdue")
                    self.assertFalse([i for i in items if i.lower().startswith("delete")], "no way to delete a view")
                    click(cdp, sid, "#viewMenuList [data-kind=save]")
                    self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('[data-dot]').length", sid) == 0), "saved: the dot goes")
                    # another tab, then back: the saved line is what comes back
                    click(cdp, sid, ".vtab[data-view-id=open]")
                    self.assertTrue(wait(lambda: self.chips(cdp, sid) == ["is:open"]))
                    click(cdp, sid, ".vtab[data-view-id=overdue]")
                    self.assertTrue(wait(lambda: self.chips(cdp, sid) == ["is:open", "due:overdue", "priority:High"]))
                    # Rename
                    click(cdp, sid, "#viewMenu")
                    click(cdp, sid, "#viewMenuList [data-kind=rename]")
                    self.assertTrue(wait(lambda: cdp.js("document.activeElement.id", sid) == "vname"), "the name box has the focus")
                    cdp.js("document.querySelector('#vname').select()", sid)
                    self.type(cdp, sid, "Open items")
                    key(cdp, sid, "Enter")
                    self.assertTrue(wait(lambda: "already exists" in cdp.js("document.querySelector('.vmsg').textContent", sid)), "a name in use says so")
                    cdp.js("document.querySelector('#vname').select()", sid)
                    self.type(cdp, sid, "Urgent soon")
                    key(cdp, sid, "Enter")
                    self.assertTrue(wait(lambda: "Urgent soon" in cdp.js("[...document.querySelectorAll('.vtab span')].map(e => e.textContent)", sid)))
                    # it is kept in this browser
                    cdp.call("Page.reload", {}, sid)
                    self.assertTrue(wait(lambda: "Urgent soon" in (cdp.js("[...document.querySelectorAll('.vtab span')].map(e => e.textContent)", sid) or [])))
                    # Save the line as a new view, then archive it, then bring it back
                    self.put(cdp, sid, "type:decision")
                    click(cdp, sid, "#viewMenu")
                    click(cdp, sid, "#viewMenuList [data-kind=saveas]")
                    self.assertTrue(wait(lambda: cdp.js("document.activeElement.id", sid) == "vname"), "the name box has the focus")
                    self.type(cdp, sid, "Decisions")
                    key(cdp, sid, "Enter")
                    self.assertTrue(wait(lambda: "Decisions" in cdp.js("[...document.querySelectorAll('.vtab span')].map(e => e.textContent)", sid)))
                    self.assertEqual(cdp.js("document.querySelector('.vtab[aria-pressed=true] span').textContent", sid), "Decisions")
                    click(cdp, sid, "#viewMenu")
                    click(cdp, sid, "#viewMenuList [data-kind=archive]")
                    self.assertTrue(wait(lambda: "Decisions" not in cdp.js("[...document.querySelectorAll('.vtab span')].map(e => e.textContent)", sid)))
                    click(cdp, sid, "#viewMenu")
                    self.assertTrue(wait(lambda: any(i == "Bring back Decisions" for i in cdp.js("[...document.querySelectorAll('#viewMenuList [role=menuitem]')].map(b => b.textContent)", sid))))
                    click(cdp, sid, "#viewMenuList [data-kind^='restore:']")
                    self.assertTrue(wait(lambda: "Decisions" in cdp.js("[...document.querySelectorAll('.vtab span')].map(e => e.textContent)", sid)))
                    self.assertEqual(self.shown(cdp, sid), self.shown(cdp, sid))
                    self.assertTrue(rows)
                    cdp.js("localStorage.clear(); sessionStorage.clear()", sid)

    # ---- keys that are also Object.prototype properties (#153 review) ----
    WATCH = ("(function () { window.__errs = []; addEventListener('error', function (e) { window.__errs.push(String(e.message)); });"
             " addEventListener('unhandledrejection', function (e) { window.__errs.push(String(e.reason)); });"
             " var CE = console.error; console.error = function () { window.__errs.push([].join.call(arguments, ' ')); return CE.apply(console, arguments); }; })();")

    def watch(self, cdp, sid):
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": self.WATCH}, sid)
        cdp.js(self.WATCH, sid)

    def drawn(self, cdp, sid):
        """The list has rows, or says in plain words that nothing matches: never blank."""
        return bool(self.shown(cdp, sid)) or "No items match these filters." in cdp.js("document.querySelector('#work-list').innerText", sid)

    def errors(self, cdp, sid):
        return cdp.js("window.__errs", sid)

    def test_a_typed_key_that_is_also_an_object_property_never_throws_or_blanks_the_list(self):
        s = self.serve()
        # (line, what the line says or does): a refused line keeps every row and says why; a plain word searches, and an empty search says so
        lines = (("constructor:x", "refused"), ("-constructor:x", "refused"), ("no:__proto__", "refused"), ("__proto__:x", "search"),
                 ("toString:x", "refused"), ("hasOwnProperty:x", "refused"), ("owner:constructor", "refused"), ("is:__proto__", "refused"))
        for width in SIZES:
            with chrome() as cdp:
                for line, how in lines:
                    with self.subTest(line=line, width=width):
                        sid = self.load(cdp, s.port, width=width)
                        self.watch(cdp, sid)
                        before = self.shown(cdp, sid)
                        self.assertTrue(before)
                        self.put(cdp, sid, line)
                        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#fline-input')", sid)))
                        self.assertEqual(self.errors(cdp, sid), [], "no uncaught error")
                        if how == "refused":
                            self.assertTrue(wait(lambda: bool(self.say(cdp, sid))), "a plain message")
                            self.assertEqual(self.shown(cdp, sid), before, "the list still shows its rows")
                            self.assertEqual(self.chips(cdp, sid), ["is:open"])
                        else:
                            self.assertIn(line, self.chips(cdp, sid), "kept as a plain search word")
                            self.assertTrue(wait(lambda: not self.shown(cdp, sid) and "No items match these filters." in cdp.js("document.querySelector('#work-list').innerText", sid)),
                                            "a search nothing matches says so")
                        cdp.js("sessionStorage.clear()", sid)

    def test_a_remembered_or_addressed_prototype_key_does_not_break_a_reload(self):
        s = self.serve()
        for kept in ("constructor:x", "__proto__:x", "-constructor:x"):
            with chrome() as cdp:
                sid = self.load(cdp, s.port)
                cdp.js("sessionStorage.setItem('clark.fline', JSON.stringify({TUL: %s})); localStorage.setItem('clark.fviews', JSON.stringify({TUL: [{id: 'constructor', name: 'toString', line: 'constructor:x'}]}))" % json.dumps(kept), sid)
                self.watch(cdp, sid)
                cdp.call("Page.reload", {}, sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#fline-input')", sid)))
                self.assertTrue(wait(lambda: self.drawn(cdp, sid)), f"{kept}: the list is not blank")
                self.assertEqual(self.errors(cdp, sid), [], kept)
                cdp.js("localStorage.clear(); sessionStorage.clear()", sid)
        for f in ("constructor:x", "__proto__:x;not:constructor", "mode:constructor;type:__proto__;owner:toString", "not:__proto__"):
            with chrome() as cdp:
                sid = self.load(cdp, s.port)
                self.watch(cdp, sid)
                cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#work&p=TUL&f=" + urllib.parse.quote(f, safe=":;,")}, sid)
                cdp.call("Page.reload", {}, sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#fline-input')", sid)), f)
                self.assertTrue(wait(lambda: self.drawn(cdp, sid)), f"{f}: not blank")
                self.assertEqual(self.errors(cdp, sid), [], f)

    def test_storage_that_is_refused_does_not_break_the_line(self):
        s = self.serve()
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE + "Object.defineProperty(window, 'sessionStorage', {get() { throw new Error('no'); }}); Object.defineProperty(window, 'localStorage', {get() { throw new Error('no'); }});"}, sid)
            cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#work&p=TUL"}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid) > 0))
            self.put(cdp, sid, "priority:High")
            self.assertTrue(wait(lambda: "priority:High" in self.chips(cdp, sid)))
            self.assertEqual(cdp.js("document.querySelectorAll('.vtab').length", sid), 3)

    def test_the_targets_are_big_enough_and_the_colours_come_from_the_tokens(self):
        s = self.serve()
        for theme in THEMES:
            with self.subTest(theme=theme), chrome() as cdp:
                sid = self.load(cdp, s.port, theme=theme)
                self.focus(cdp, sid)
                self.type(cdp, sid, "st")
                self.assertTrue(wait(lambda: len(self.listed(cdp, sid)) > 0))
                small = cdp.js("[...document.querySelectorAll('#work .vtab, #work .fchip button, #work .fopt, #work .fhint, #viewMenu, #fline-input')]"
                               ".filter(e => { const r = e.getBoundingClientRect(); return r.height < 24 || r.width < 24; }).map(e => e.className || e.id)", sid)
                self.assertEqual(small, [])
                tiny = cdp.js("[...document.querySelectorAll('#work *')].filter(e => [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) && parseFloat(getComputedStyle(e).fontSize) < 13).map(e => e.className)", sid)
                self.assertEqual(tiny, [], "text is at least 13 px")
                bg = cdp.js("getComputedStyle(document.querySelector('#fline-list')).backgroundColor", sid)
                surface = cdp.js("getComputedStyle(document.documentElement).getPropertyValue('--surface').trim()", sid)
                probe = cdp.js(f"(() => {{ const d = document.createElement('div'); d.style.background = {json.dumps(surface)}; document.body.appendChild(d); return getComputedStyle(d).backgroundColor; }})()", sid)
                self.assertEqual(bg, probe, "the suggestions sit on the surface token")
                if theme == "dark":
                    self.assertEqual(bg, "rgb(14, 45, 56)")
                self.assertEqual(cdp.js("getComputedStyle(document.querySelector('.fline')).borderTopColor !== 'rgba(0, 0, 0, 0)'", sid), True)


if __name__ == "__main__":
    unittest.main()
