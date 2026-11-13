"""Prototype parity A-D5: the rows of Risks and issues, Open actions and Decisions, in View, in Edit and in a published file.

Run: python3 dev/run_tests.py test_item_rows
A real browser (tests/test_server.py chrome()) against a real server over a real store of fictional rows. The file test publishes
with the real builder and opens the file from disk, where nothing may ask a server. Rows an item's flag keeps from a client are
absent from the file, so it can never draw them.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from _paths import TOOLS

sys.path.insert(0, str(TOOLS))
from clark import changes, page, publish  # noqa: E402
from test_report_editor import EMPTY_BRANDING, Pg  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402

AS_AT = "2026-10-28"
HIDDEN = "Internal-only wording ZQ-HIDDEN"
NO_WORDING = "Team-only description ZQ-NOWORDING"      # shown to the client, but with no client wording: it is listed under its own title (row 851)
RESPONSE = "Team-only response ZQ-RESPONSE"            # a risk's working note (response_action): never in a report


def fill(store):
    with store.step("dashboard", USER) as st:
        st.create("actions", {"project": "ABC", "description": "Agree the cut-over plan", "owner": "Sara Khan", "due_date": "2026-10-20",
                              "raised": "2026-10-01", "client_message": "Cut-over plan to be agreed", "source": "demo"})
        st.create("actions", {"project": "ABC", "description": "Book the training room", "owner": "Omar Reid", "due_date": "2026-11-05",
                              "raised": "2026-10-01", "client_message": "Training room booked for November", "source": "demo"})
        st.create("actions", {"project": "ABC", "description": HIDDEN, "owner": "Omar Reid", "due_date": "2026-11-06",
                              "raised": "2026-10-01", "client_visible": 0, "source": "demo"})
        st.create("actions", {"project": "ABC", "description": "Closed one", "owner": "Omar Reid", "status": "Closed", "due_date": "2026-10-02",
                              "raised": "2026-10-01", "source": "demo"})
        st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier may deliver late", "owner": "Mia Hale",
                           "due_date": "2026-11-01", "impact": "High", "likelihood": "High", "raised": "2026-10-01",
                           "response_action": RESPONSE, "client_message": "Supplier delivery may slip", "source": "demo"})
        st.create("raid", {"project": "ABC", "type": "Issue", "description": "Test data is incomplete", "owner": "Mia Hale",
                           "due_date": "2026-11-02", "impact": "Low", "likelihood": "Low", "raised": "2026-10-01",
                           "client_message": "Some test data is missing", "source": "demo"})
        st.create("decisions", {"project": "ABC", "decision": "Choose the hosting region", "made_by": "Steering group",
                                "needed_by": "2026-11-03", "status": "Pending", "client_message": "Hosting region to be chosen", "source": "demo"})


def fill_unworded(store):
    """Items marked for the client (the default) that carry no client wording of their own."""
    with store.step("dashboard", USER) as st:
        st.create("actions", {"project": "ABC", "description": NO_WORDING, "owner": "Omar Reid", "due_date": "2026-11-07",
                              "raised": "2026-10-01", "source": "demo"})
        st.create("raid", {"project": "ABC", "type": "Risk", "description": NO_WORDING + " risk", "owner": "Mia Hale",
                           "due_date": "2026-11-04", "impact": "High", "likelihood": "High", "raised": "2026-10-01", "source": "demo"})
        st.create("decisions", {"project": "ABC", "decision": NO_WORDING + " decision", "made_by": "Steering group",
                                "needed_by": "2026-11-04", "status": "Pending", "source": "demo"})


# Row 1021: the status pill is gone; the icon says the status (its aria-label 'Action, Overdue', or in Edit the button's tooltip, or in a file the small word).
# A row reads id|status word|title|owner date priority (the kind letter is checked in test_item_one_line).
ROWS = ("[...document.querySelectorAll('[data-type=%s] .wl-row')].map(r => { const i = r.querySelector('.ico'), b = r.querySelector('[data-tip]');"
        " const st = (r.querySelector('.ico-w') || {}).textContent || (i && i.getAttribute('aria-label') || '').split(', ')[1] || (b && b.dataset.tip || '').split(' · ')[1];"
        " return r.dataset.id + '|' + st + '|' + r.querySelector('.wl-title').textContent.trim() + '|' + ['.c-owner', '.c-date', '.c-prio'].map(c => r.querySelector(c).textContent.trim()).join(' ') + '|' + r.dataset.kind; })")


class ItemRows(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        fill(self.store)

    def check_rows(self, js, where, own=False):
        """own: View reads each item's own description (row 1099); Edit and the file read the client's wording."""
        W = {"Cut-over plan to be agreed": "Agree the cut-over plan", "Training room booked for November": "Book the training room",
             "Supplier delivery may slip": "Supplier may deliver late", "Hosting region to be chosen": "Choose the hosting region"} if own else {}
        w = lambda t: W.get(t, t)
        actions = js(ROWS % "actions")
        self.assertEqual(len(actions), 2, f"{where}: two open client-visible actions (closed and hidden ones left out): {actions}")
        self.assertIn(w("Cut-over plan to be agreed"), actions[0], where)
        self.assertIn("Sara Khan", actions[0], where)
        self.assertIn("20-10-2026", actions[0], "dates read DD-MM-YYYY")
        self.assertIn(w("Training room booked for November"), actions[1], "the client's own wording is shown when there is one")
        raid = js(ROWS % "raid")
        self.assertEqual(len(raid), 2, where)
        self.assertTrue(raid[0].split("|")[1] == "Urgent" and raid[0].endswith("|risk") and w("Supplier delivery may slip") in raid[0], raid[0])
        self.assertIn("Urgent", raid[0].split("|")[3], "the pill is the status colour; the priority word is in the line (prototype views.js:378)")
        self.assertIn("01-11-2026", raid[0])
        self.assertTrue(raid[1].split("|")[1] == "Green" and raid[1].endswith("|issue") and "Low" in raid[1].split("|")[3], raid[1])
        decisions = js(ROWS % "decisions")
        self.assertEqual(len(decisions), 1, where)
        self.assertIn("Needed by 03-11-2026", decisions[0], where)
        self.assertIn(w("Hosting region to be chosen"), decisions[0], where)
        self.assertNotIn(HIDDEN, js("document.body.innerText"), where)
        self.assertNotIn("ZQ-RESPONSE", js("document.body.innerText"), f"{where}: a risk's working note (response action) is never drawn")
        self.assertEqual(actions[0].split("|")[1], "Overdue", f"{where}: a late action reads Overdue (prototype core.js:202-212)")
        self.assertIn(actions[1].split("|")[1], ("Overdue", "Due soon", "On track"), f"{where}: the other action reads Overdue, Due soon or On track (was Open), by the date it is read on (its date is near the real today and passes)")
        self.assertEqual(decisions[0].split("|")[1], "Pending", f"{where}: a pending decision reads Pending")

    def test_the_served_page_draws_the_rows_in_view_and_in_edit_and_the_file_draws_them_alone(self):
        s = Running(data_for=self.store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.addCleanup(s.close)
        with chrome() as cdp:
            p = Pg.at(self, cdp, s.port)
            p.ready()
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                self.check_rows(p.js, f"View at {w}", own=True)
                self.assertGreater(p.js("document.querySelectorAll('.wl-id').length"), 0, "the team's View keeps the item number")
                fits = "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
                self.assertTrue(wait(lambda: p.js(fits)), f"nothing pushes the page sideways at {w}")
            p.edit()
            self.check_rows(p.js, "Edit")
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        done = publish.publish(self.store, "ABC", folder, by_user=USER, now=AS_AT, branding=EMPTY_BRANDING)
        text = Path(done["path"]).read_text(encoding="utf-8")
        self.assertNotIn(HIDDEN, text)
        with chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Page.navigate", {"url": Path(done["path"]).as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.wl-row').length > 0", sid)), "the file drew its rows")
            self.check_rows(lambda e: cdp.js(e, sid), "the file")
            self.assertEqual(cdp.js("document.querySelectorAll('.wl-id').length", sid), 0, "a file draws no item number")
            first = cdp.js(ROWS % "actions", sid)[0]
            self.assertIn("20-10-2026", first)
            self.assertNotRegex(first, r"days? late|Today|Tomorrow|Yesterday|In \d+ days?", "a file shows the date only: it is read later, not on the publish date")
            self.assertEqual(cdp.js("document.querySelectorAll('[contenteditable],input,button.eye').length", sid), 0)

    def test_a_section_with_nothing_to_show_says_so_on_the_page_and_is_left_out_of_the_file(self):
        empty = DemoStore()
        self.addCleanup(empty.close)
        s = Running(data_for=empty.store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.addCleanup(s.close)
        with chrome() as cdp:
            p = Pg.at(self, cdp, s.port)
            p.ready()
            self.assertEqual(p.js("document.querySelector('[data-type=raid] .quiet').textContent"), "Nothing to show.")
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        done = publish.publish(empty.store, "ABC", folder, by_user=USER, now=AS_AT, branding=EMPTY_BRANDING)
        with chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Page.navigate", {"url": Path(done["path"]).as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#report')", sid)))
            self.assertEqual(cdp.js("document.querySelectorAll('[data-type=raid],[data-type=actions],[data-type=decisions]').length", sid), 0)

    def test_an_empty_section_says_so_in_view_and_edit_and_the_published_file_leaves_it_out_heading_and_all(self):
        """A client's published file never shows an empty section: no heading and no 'Nothing to show.' for it. View keeps each
        heading with that line (prototype views.js), and Edit says it with the add line and the count."""
        empty = DemoStore()
        self.addCleanup(empty.close)
        s = Running(data_for=empty.store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.addCleanup(s.close)
        secs = "[...document.querySelectorAll('[data-type=raid],[data-type=actions],[data-type=decisions]')].map(e => e.querySelector('.sec-h').textContent + '|' + (e.querySelector('[data-nothing]') || {}).textContent)"
        want = ["Risks and issues|Nothing to show.", "Open actions|Nothing to show.", "Decisions|Nothing to show."]
        with chrome() as cdp:
            p = Pg.at(self, cdp, s.port)
            p.ready()
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                self.assertEqual(p.js(secs), want, f"View at {w} keeps each heading and says there is nothing (prototype views.js)")
            p.edit()
            self.assertEqual(p.js("document.querySelectorAll('[data-nothing]').length"), 0, "Edit says it with the add line and the count instead")
            self.assertEqual(p.js("[...document.querySelectorAll('[data-showing]')].map(e => e.textContent.slice(0, 15))"), ["Showing 0 of 0."] * 3)
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        done = publish.publish(empty.store, "ABC", folder, by_user=USER, now=AS_AT, branding=EMPTY_BRANDING)
        with chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Page.navigate", {"url": Path(done["path"]).as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.sec')", sid)), "the file drew its other sections")
            self.assertEqual(cdp.js(secs, sid), [], "the published file leaves each empty section out")
            headings = cdp.js("[...document.querySelectorAll('.sec-h')].map(e => e.textContent)", sid)
            for h in ("Risks and issues", "Open actions", "Decisions"):
                self.assertNotIn(h, headings, f"no heading for an empty {h} in the file")
            self.assertNotIn("Nothing to show.", cdp.js("document.body.innerText", sid), "the file never says Nothing to show.")
            self.assertEqual(cdp.js("document.querySelectorAll('[data-nothing]').length", sid), 0)


DASH = "[data-type=%s]"


class UnwordedRows(unittest.TestCase):
    """Row 851: the sections list the items marked for the client (the eye is the control), with the item's own title when it has no
    client wording, and 'Showing N of M' counts every open item of the kind."""

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        fill_unworded(self.store)
        with self.store.step("dashboard", USER) as st:
            st.create("actions", {"project": "ABC", "description": HIDDEN, "owner": "Omar Reid", "due_date": "2026-11-06",
                                  "raised": "2026-10-01", "client_visible": 0, "source": "demo"})

    def measure(self, p, where):
        for kind, mark in (("actions", NO_WORDING), ("raid", NO_WORDING + " risk"), ("decisions", NO_WORDING + " decision")):
            self.assertEqual(p.js("[...document.querySelectorAll(%r)].map(r => r.querySelector('.wl-title').textContent.trim().replace(/^(Risk|Issue) /, ''))" % (DASH % kind + " .wl-row")),
                             [mark], f"{where}: {kind} lists the marked item under its own title")
        self.assertNotIn("Internal-only", p.js("document.querySelector('#report').innerText"), f"{where}: an item not marked for the client is not listed")

    def test_marked_items_with_no_wording_are_listed_in_view_and_edit_with_n_of_m(self):
        s = Running(data_for=self.store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.addCleanup(s.close)
        with chrome() as cdp:
            p = Pg.at(self, cdp, s.port)
            p.ready()
            for theme in ("light", "dark"):
                p.js("document.documentElement.setAttribute('data-theme', %r)" % theme)
                for w in (1400, 900):
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    self.measure(p, f"View {theme} {w}")
            p.edit()
            for theme in ("light", "dark"):
                p.js("document.documentElement.setAttribute('data-theme', %r)" % theme)
                for w in (1400, 900):
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    self.measure(p, f"Edit {theme} {w}")
                    self.assertTrue(p.js("document.querySelector('[data-item-rows=raid] [data-showing]').textContent").startswith("Showing 1 of 1."))
                    self.assertTrue(p.js("document.querySelector('[data-item-rows=decisions] [data-showing]').textContent").startswith("Showing 1 of 1."))
                    self.assertTrue(p.js("document.querySelector('[data-item-rows=actions] [data-showing]').textContent").startswith("Showing 1 of 2."),
                                    "the action not marked for the client counts in M")
                    self.assertEqual(p.js("document.querySelector('[data-addfrom=actions]').textContent"), "+ Add from your project record (1)",
                                     "and is offered by the add control")
                    self.assertFalse(p.js("!!document.querySelector('[data-addfrom=raid]')"))

    def test_the_published_file_lists_the_marked_items_too(self):
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        done = publish.publish(self.store, "ABC", folder, by_user=USER, now=AS_AT, branding=EMPTY_BRANDING)
        with chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Page.navigate", {"url": Path(done["path"]).as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.wl-row').length > 0", sid)), "the file drew its rows")
            self.assertEqual(cdp.js("document.querySelectorAll('.wl-row').length", sid), 3)
            self.assertNotIn("Internal-only", cdp.js("document.body.innerText", sid))


class CurrentStateInEdit(unittest.TestCase):
    """Row 850: the Current state text stays on the page in Edit (it was replaced by a quiet line there)."""

    def test_the_text_is_drawn_in_view_and_in_edit_in_both_themes_at_both_widths(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        demo.update("projects", "ABC", {"current_state": "<p>Scanning is <strong>two thirds</strong> done ZQ-NOW</p>"})
        s = Running(data_for=demo.store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.addCleanup(s.close)
        body = "(document.querySelector('[data-type=current] .sec-body') || {}).textContent || ''"
        with chrome() as cdp:
            p = Pg.at(self, cdp, s.port)
            p.ready()
            for mode in ("view", "edit"):
                if mode == "edit":
                    p.edit()
                for theme in ("light", "dark"):
                    p.js("document.documentElement.setAttribute('data-theme', %r)" % theme)
                    for w in (1400, 900):
                        cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                        where = f"{mode} {theme} {w}"
                        self.assertIn("two thirds", p.js(body), f"{where}: the Current state text is drawn")
                        self.assertNotIn("Not shown on this page yet", p.js("document.querySelector('[data-type=current]').textContent"), where)
                        self.assertGreater(p.js("document.querySelector('[data-type=current] .sec-body').getBoundingClientRect().height"), 10, where)


def edit_server(test, store):
    """The page clark serves over a real store, with the real change and undo routes."""
    s = Running(data_for=store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING),
                change=changes.make_change(store.path, [], USER), undo=changes.make_undo(store.path, [], USER))
    test.addCleanup(s.close)
    return s


def id_of(store, text):
    return next(r["id"] for t in ("actions", "raid", "decisions") for r in store.read(t, "ABC") if r["client_message"] == text)


class EditRows(unittest.TestCase):
    """Edit: every part of a row changes in place; + Add; Add from your project record; the eye; Showing N of M."""

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        fill(self.store)
        self.s = edit_server(self, self.store)

    def page(self, cdp):
        p = Pg.at(self, cdp, self.s.port)
        p.ready()
        p.edit()
        return p

    def type_into(self, p, selector, text, ending="Enter"):
        p.js(f"(function(){{var el=document.querySelector({selector!r}); el.focus(); if (el.select) {{ el.select(); }} else {{ var r=document.createRange(); r.selectNodeContents(el); var s=getSelection(); s.removeAllRanges(); s.addRange(r); }}}})()")
        if text:
            p.type(text)
        else:
            p.key("Backspace", code="Backspace", vk=8)
        p.key(ending, code=ending, vk=13 if ending == "Enter" else 27)

    def type_words(self, p, row, text):
        """Item 1005: a row's wording is the one editor on one line: a click opens it, Enter saves."""
        p.js(f"document.querySelector({row!r} + ' [data-rich=client_message]').click()")
        p.until("document.activeElement.classList.contains('ProseMirror')", "the editor opens with the focus in it")
        p.js(f"(() => {{ const e = document.activeElement.cxed.editor; e.commands.selectAll(); if ({json.dumps(text)}) e.commands.insertContent({json.dumps(text)}); else e.commands.deleteSelection(); }})()")
        p.key("Enter", code="Enter", vk=13)

    def click(self, p, click, done, what):
        """Click, and wait for `done`; a click made in the first moments of a busy page may be lost to the page still starting, so
        it is made again (up to six times). A handler that is not there at all still fails."""
        for _ in range(6):
            p.js(click)
            if wait(lambda: p.js(done), 3):
                return
        self.fail(what)

    def add_line(self, p, selector, text, table, field, value):
        """Type a line and press Enter, and wait for the row to reach the store. An Enter pressed in the first moments of a busy page, or
        while the page draws again, can be lost: the line then still holds the text, and only then is it typed again (a line the page
        took is empty, so a slow store is never given the row twice)."""
        for _ in range(4):
            self.type_into(p, selector, text)
            if wait(lambda: any(r[field] == value for r in self.store.read(table, "ABC")), 8):
                break
            if not p.js(f"document.querySelector({selector!r}).value"):
                wait(lambda: any(r[field] == value for r in self.store.read(table, "ABC")), 15)
                break
        return self.stored(table, field, value)

    def stored(self, table, field, value):
        """Wait until the store has a row of `table` whose `field` is `value` (a toast from an earlier change must not be taken for this one)."""
        found = []
        wait(lambda: found.append(1) or any(r[field] == value for r in self.store.read(table, "ABC")), 15)
        return next(r for r in self.store.read(table, "ABC") if r[field] == value)

    def test_every_part_of_a_row_edits_in_place_and_the_pill_is_the_prototypes(self):
        with chrome() as cdp:
            p = self.page(cdp)
            row = "[data-type=raid] .wl-row[data-id=%r]" % id_of(self.store, "Supplier delivery may slip")
            self.assertEqual(p.js(f"[...document.querySelectorAll({row!r} + ' [data-cell]')].map(e => e.dataset.cell.split(':')[1])"), ["status", "owner", "due", "priority"],
                             "status, owner, date and priority change in place (a risk's priority through its impact and likelihood, item 210)")
            self.assertEqual(p.js(f"document.querySelectorAll({row!r} + ' [data-fixed$=\":priority\"]').length"), 0,
                             "a risk's priority is no longer a fixed cell: its rating picker sets the impact and likelihood it is worked out from")
            self.assertEqual(p.js(f"document.querySelector({row!r} + ' [data-cell$=\":status\"]').dataset.tip"), "Risk · Urgent · Overdue", "the icon says Red, Amber or Green on a risk, and Urgent instead (never Red as well) with Overdue on an Urgent one (row 1021: the pill is gone)")
            act = "[data-type=actions] .wl-row[data-id=%r]" % id_of(self.store, "Cut-over plan to be agreed")
            self.assertEqual(p.js(f"document.querySelector({act!r} + ' [data-cell$=\":status\"]').dataset.tip"), "Action · Overdue")
            # the client's wording, in place
            self.type_words(p, row, "Supplier delivery may slip by a week")
            mine = self.stored("raid", "client_message", "Supplier delivery may slip by a week")
            self.assertEqual(mine["description"], "Supplier may deliver late", "the team's own text is untouched")
            # the store has it before the page has read it again: wait for the row to draw what clark saved
            p.until(f"document.querySelector({row!r} + ' [data-rich=client_message]').textContent.trim() === 'Supplier delivery may slip by a week'", "the row draws the saved wording")
            self.type_words(p, row, "")                  # a blank wording clears it (row 893; test_clear_wording_in_place)
            p.until(f"document.querySelector({row!r} + ' [data-rich=client_message]').textContent.trim() === 'Supplier may deliver late'", "a cleared wording falls back to the item's title")
            # the owner, through its own picker
            p.js(f"document.querySelector({act!r} + ' [data-cell$=\":owner\"]').click()")
            p.until("!!document.querySelector('.menu, .cp, [role=dialog]')", "the owner picker opened")
            p.key("Escape", code="Escape", vk=27)

    def test_the_add_line_adds_a_row_with_its_wording_and_the_count_follows(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.assertEqual(p.js("document.querySelector('[data-add-line=actions]').placeholder"), "+ Add an action: type \u201cOwner: what it is\u201d, then Enter")
            self.assertEqual(p.js("document.querySelector('[data-add-line=raid]').placeholder"), "+ Add a risk: type \u201cOwner: what it is\u201d, then Enter")
            before = p.js("document.querySelector('[data-item-rows=actions] [data-showing]').textContent")
            self.assertTrue(before.startswith("Showing 2 of 3."), before)   # the third is the one not marked for the client
            row = self.add_line(p, "[data-add-line=actions]", "Mia Hale: Send the plan", "actions", "description", "Send the plan")
            self.assertEqual((row["owner"], row["client_message"], row["client_visible"]), ("Mia Hale", "Send the plan", 1))
            p.until("document.querySelectorAll('[data-item-rows=actions] .wl-row').length === 3", "the new row is drawn")
            self.assertTrue(p.js("document.querySelector('[data-item-rows=actions] [data-showing]').textContent").startswith("Showing 3 of 4."))
            self.assertEqual(p.js("document.querySelector('[data-add-line=actions]').value"), "", "the line is empty again")
            risk = self.add_line(p, "[data-add-line=raid]", "Omar Reid: Licence may lapse", "raid", "description", "Licence may lapse")
            self.assertEqual((risk["type"], risk["owner"], risk["priority"], risk["client_message"]), ("Risk", "Omar Reid", "Medium", "Licence may lapse"))
            made = self.add_line(p, "[data-add-line=decisions]", "Steering group: Pick the vendor", "decisions", "decision", "Pick the vendor")
            self.assertEqual(made["made_by"], "Steering group")
            p.until("document.querySelectorAll('[data-item-rows=decisions] .wl-row').length === 2", "the new decision is drawn")
            self.click(p, "document.querySelector('.toast [data-undo]') && document.querySelector('.toast [data-undo]').click()",
                       "document.querySelectorAll('[data-item-rows=decisions] .wl-row').length === 1", "Undo took the decision back off the page")

    def test_escape_in_the_add_from_picker_gives_the_focus_back_to_its_button(self):
        gone = id_of(self.store, "Supplier delivery may slip")
        with chrome() as cdp:
            p = self.page(cdp)
            self.click(p, f"document.querySelector('[data-id={gone}] [data-eye]').click()", f"!document.querySelector('[data-item-rows=raid] [data-id={gone}]')", "the row left the page")
            p.js("document.querySelector('[data-addfrom=raid]').click()")
            p.until("!!document.querySelector('.picker')", "the picker opened")
            p.until("!!document.activeElement && !!document.activeElement.closest('.picker')", "the search box has the focus")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('.picker')", "the picker closed")
            p.until("document.activeElement && document.activeElement.getAttribute('data-addfrom') === 'raid'", "the focus is on the Add from button")

    def test_the_eye_takes_a_row_off_and_add_from_your_project_record_puts_it_back(self):
        gone = id_of(self.store, "Supplier delivery may slip")
        with chrome() as cdp:
            p = self.page(cdp)
            self.assertFalse(p.js("!!document.querySelector('[data-addfrom=raid]')"), "nothing is off the page yet: no link")
            self.click(p, f"document.querySelector('[data-id={gone}] [data-eye]').click()", f"!document.querySelector('[data-item-rows=raid] [data-id={gone}]')", "the row left the page")
            self.assertEqual([r["item_id"] for r in self.store.read("report_hidden", "ABC")], [gone])
            self.assertTrue(p.js("document.querySelector('[data-item-rows=raid] [data-showing]').textContent").startswith("Showing 1 of 2."))
            self.assertEqual(p.js("document.querySelector('[data-addfrom=raid]').textContent"), "+ Add from your project record (1)")
            p.js("document.querySelector('[data-addfrom=raid]').click()")
            p.until("!!document.querySelector('.picker')", "the picker opened")
            self.assertEqual(p.js("[...document.querySelectorAll('.picker .pick label')].map(e => e.textContent).length"), 1, "only this section's kind, only what is off")
            self.assertIn("Supplier delivery may slip", p.js("document.querySelector('.picker .pick label').textContent"), "the client's wording, not the team's text")
            self.assertNotIn("Supplier may deliver late", p.js("document.querySelector('.picker').textContent"))
            p.js("document.querySelector('.picker .pick input').click()")
            p.js("document.querySelector('.picker .pk-btn.pri').click()")
            p.until(f"!!document.querySelector('[data-item-rows=raid] [data-id={gone}]')", "the row is back on the page")
            self.assertEqual(self.store.read("report_hidden", "ABC"), [])
            self.assertFalse(p.js("!!document.querySelector('[data-addfrom=raid]')"))
            # View: the eye is gone from the page it leaves; a row taken off is not drawn
            p.js(f"document.querySelector('[data-id={gone}] [data-eye]').click()")
            p.until(f"!document.querySelector('[data-item-rows=raid] [data-id={gone}]')", "off again")
            p.view()
            self.assertFalse(p.js(f"!!document.querySelector('[data-id={gone}]')"), "View does not draw a row taken off the page")
            self.assertEqual(p.js("document.querySelectorAll('[data-eye],.add-in,[data-add-line],[data-addfrom],[data-showing],[contenteditable],[data-cell]').length"), 0, "View has no Edit control")

    def test_the_id_opens_the_item_and_the_row_is_clickable_in_view_only_in_the_page_clark_serves(self):
        first = id_of(self.store, "Supplier delivery may slip")
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.s.port)
            p.ready()
            self.click(p, f"document.querySelector('[data-type=raid] [data-id={first}] .idl').click()", f"location.hash.includes('item={first}')", "the item opened beside the page")
            p.js("history.back()")
            p.until("!location.hash.includes('item=')", "Back closed it")
            self.click(p, f"document.querySelector('[data-type=raid] [data-id={first}] .wl-title').click()", f"location.hash.includes('item={first}')", "a click on the row opens the item too")
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        done = publish.publish(self.store, "ABC", folder, by_user=USER, now=AS_AT, branding=EMPTY_BRANDING)
        with chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Page.navigate", {"url": Path(done["path"]).as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.wl-row').length > 0", sid)))
            self.assertEqual(cdp.js("document.querySelectorAll('.idl,.wl-open,[data-eye],.add-in,[data-showing]').length", sid), 0, "the file has no button, no click and no Edit control")

    def test_in_dark_the_rows_the_pill_the_in_place_parts_and_the_eye_are_readable_and_use_the_dark_tokens_at_1400_and_900(self):
        """Done-when 6: in dark (data-theme dark), at 1400 and 900 px, in View and in Edit, each part of these rows reads at 4.5:1
        or more on what is behind it, and its colour is the dark token it is drawn with (not a light value left over)."""
        token = "(n) => { const e = document.createElement('span'); e.style.color = `var(${n})`; document.body.appendChild(e); const c = getComputedStyle(e).color; e.remove(); return c; }"
        parts = {
            "view": [("[data-type=raid] .wl-row .c-ico .ico", None), ("[data-type=raid] .wl-row .wl-title", "--text"),
                     ("[data-type=raid] .wl-row .c-date", None), ("[data-type=raid] .wl-row .idl", "--status-blue-text")],
            "edit": [("[data-item-rows=raid] .wl-row [data-cell$=':status'] .ico", None), ("[data-item-rows=raid] .wl-row [data-rich=client_message]", "--text"),
                     ("[data-item-rows=raid] .wl-row [data-cell$=':owner']", None), ("[data-item-rows=raid] .wl-row [data-eye]", None),
                     ("[data-item-rows=raid] .wl-row .idl", "--status-blue-text"), ("[data-item-rows=raid] [data-showing]", "--text-muted")],
        }
        check = """((parts, token) => {
          const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
          const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
          const back = (el) => { let b = 'rgba(0, 0, 0, 0)'; while (el && /rgba\\(.*, 0\\)|transparent/.test(b)) { b = getComputedStyle(el).backgroundColor; el = el.parentElement; } return b; };
          return parts.map(([sel, tok]) => { const el = document.querySelector(sel); if (!el) return [sel, null];
            const fg = getComputedStyle(el).color, bg = back(el), x = lum(rgb(fg)), y = lum(rgb(bg));
            return [sel, (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05), fg, tok ? token(tok) : fg, lum(rgb(back(el.closest('.sec'))))]; });
        })(%s, %s)"""
        for w in (1400, 900):
            with self.subTest(width=w), chrome() as cdp:
                p = Pg.at(self, cdp, self.s.port)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.ready()
                p.js("document.documentElement.dataset.theme = 'dark'")       # after the page drew: its own Appearance setting is set on load
                for mode in ("view", "edit"):
                    if mode == "edit":
                        p.edit()
                        p.until("!!document.querySelector('[data-item-rows=raid] [data-eye]')", "Edit drew the rows")
                    self.assertEqual(p.js("document.documentElement.dataset.theme"), "dark")
                    for sel, ratio, fg, want, card in p.js(check % (json.dumps(parts[mode]), token)):
                        self.assertIsNotNone(ratio, f"{mode} at {w}: {sel} is drawn")
                        self.assertGreaterEqual(ratio, 4.5, f"{mode} at {w}: {sel} reads {ratio:.2f}:1 in dark")
                        self.assertEqual(fg, want, f"{mode} at {w}: {sel} is drawn in its dark token")
                        self.assertLess(card, 0.1, f"{mode} at {w}: the section behind {sel} is the dark surface")

    def test_what_a_client_reads_has_no_edit_control_and_nothing_internal(self):
        """Client safety: the published file and the served View carry no Edit part of these rows, and none of the team's own text."""
        edit_only = ("[...document.querySelectorAll('[data-eye],.add-in,[data-add-line],[data-addfrom],[data-showing],[data-edit-only],[data-cell],"
                     ".item-rows-edit,.wl-add,.add-from,[contenteditable],input,textarea,select')].filter((e) => !e.closest('#report-bar')).length")   # the bar above the page (served only) keeps its Week ending box in View
        words = "document.querySelector('#report').innerText"
        internal = (HIDDEN, RESPONSE, NO_WORDING)
        ours = ("Add from your project record", "Take off the page", "Showing ", "Add a risk", "Add an action", "Add a decision", "Select any part to change it")
        def check(js, where):
            self.assertEqual(js(edit_only), 0, f"{where}: no Edit control among the rows")
            text = js(words)
            for bad in internal + ours:
                self.assertNotIn(bad, text, f"{where}: {bad!r} is not for a client")
        s = Running(data_for=self.store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.addCleanup(s.close)
        with chrome() as cdp:
            p = Pg.at(self, cdp, s.port)
            p.ready()
            check(p.js, "View")
            p.edit()
            p.view()
            check(p.js, "View after Edit")
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        done = publish.publish(self.store, "ABC", folder, by_user=USER, now=AS_AT, branding=EMPTY_BRANDING)
        source = Path(done["path"]).read_text(encoding="utf-8")
        for bad in (HIDDEN, RESPONSE, "data-add-line", "Add from your project record"):
            self.assertNotIn(bad, source, f"the file's own source does not hold {bad!r}")
        with chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Page.navigate", {"url": Path(done["path"]).as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.wl-row').length > 0", sid)))
            check(lambda e: cdp.js(e, sid), "the file")


if __name__ == "__main__":
    unittest.main()
