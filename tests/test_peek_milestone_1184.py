"""Item 1184: what is particular to the Milestone peek (Layout A of the approved mockup). The shared frame is item 1180 (its own tests) and the model is the
Action peek (test_peek_action_1181). This file covers the four chips and their popovers (State with its five icons, Owner, Progress with ten blocks, Forecast
date), the Latest update above Details, and the Details rows of a milestone (Use case picker, Client wording greyed while the milestone is not shown to the client).
Run: python3 dev/run_tests.py test_peek_milestone_1184

Real browser at 1400 and 900 px on the fictional demo project (ABC), the Milestones page (always Edit). ABC-M-002 "Go live" has an agreed date long past (so it
reads Overdue by the dates), ABC-M-001 "Pilot live" is far ahead (On track by the dates). Hooks: .pk-chips [data-row=state|owner|progress|forecast],
[data-pop], [data-ms-state], [data-ms-block], [data-ms-row=...], [data-ms-ucs], [data-ms-wording-off], [data-pk-client], [data-pk-latest], [data-pk-details].
"""
import json
import re
import time
import unittest

from _demo import USER
from _paths import SRC

from test_movement_page import GO_LIVE, PILOT, Base  # noqa: E402
from test_server import chrome  # noqa: E402
from clark import store as sm  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
CHIPS = "#peek .pk-chips"
ICONS = {"Forecast": "sForecast", "On track": "sTrack", "At risk": "sRisk", "Slipped": "sSlip", "Achieved": "sClosed"}
RED = "(() => { const e = document.createElement('i'); e.style.color = 'var(--status-red-text)'; document.body.appendChild(e); const c = getComputedStyle(e).color; e.remove(); return c; })()"


class Milestone(Base):
    cur = PILOT

    def visit(self, cdp, ms=PILOT, width=1400, view="milestones"):
        from test_report_editor import Pg
        self.cur = ms
        p = Pg.at(self, cdp, self.s.port, f"#{view}&p=ABC&ms={ms}")
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.until("!!document.querySelector('#peek .pk-chips')", "the peek drew its chip row")
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, p.sid)
        p.until("document.getAnimations().length === 0", "no animation running")
        return p

    def click(self, p, sel):
        p.until(f"!!document.querySelector({json.dumps(sel)})", sel)
        p.js(f"document.querySelector({json.dumps(sel)}).click()")

    def until_store(self, test, seconds=10):
        end = time.time() + seconds
        while time.time() < end:
            if test():
                return True
            time.sleep(0.1)
        return test()

    def saved(self, field, value):
        self.assertTrue(self.until_store(lambda: self.row(self.cur)[field] == value), f"{field} was not saved as {value!r}: {self.row(self.cur)[field]!r}")

    def chip(self, p, field):
        self.click(p, f"{CHIPS} [data-row={field}] button")
        p.until("!!document.querySelector('[data-pop]')", f"the {field} popover opened")

    def chips(self, p):
        return p.js("(() => { const out = {}; for (const c of document.querySelectorAll('#peek .pk-chips > [data-row]')) { const s = c.querySelector('.pk-chip-sub'); const b = c.querySelector('button') || c;"
                    " out[c.dataset.row] = { text: c.innerText.replace(/\\s+/g, ' ').trim(), icons: [...c.querySelectorAll('svg[data-icn]')].map(i => i.dataset.icn),"
                    " sub: s ? s.textContent.trim() : null, tag: b.tagName, h: b.getBoundingClientRect().height }; } return out; })()")

    def links(self, ms=None):
        return sm.milestone_use_case_ids(self.store.con, ms or self.cur)

    def two_use_cases(self):
        with self.store.step("dashboard", USER) as st:
            a = st.create("use_cases", {"project": "ABC", "title": "Invoice matching", "status": "On track", "source": "demo"})
            b = st.create("use_cases", {"project": "ABC", "title": "Badge printing", "status": "On track", "source": "demo"})
        return a, b

    def undo(self, p):
        p.until("!!document.querySelector('.toast [data-undo]')", "the Undo button")
        p.js("document.querySelector('.toast [data-undo]').click()")

    # ---- the chip row -------------------------------------------------------------------------------------------------------------------------------

    def test_four_chips_in_the_ticket_order_with_their_icons(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp, width=width)
                got = self.chips(p)
                self.assertEqual(list(got), ["state", "owner", "progress", "forecast"], "State, Owner, Progress, Forecast date")
                for key, icon in (("state", "sTrack"), ("owner", "user"), ("progress", "bars"), ("forecast", "cal")):
                    self.assertEqual(got[key]["icons"][0], icon, key)
                    self.assertEqual(got[key]["tag"], "BUTTON", f"{key}: a control in Edit")
                    self.assertGreaterEqual(got[key]["h"], 24, f"{key}: a 24 px target")
                self.assertEqual(p.js("document.querySelectorAll('#peek .pk-ms-states, #peek [data-ms-head], #peek [data-ms-range]').length"), 0, "no old header line, no States row, no slider")

    def test_the_state_popover_shows_five_icons_and_the_forecast_one_is_dashed(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp, width=width)
                self.chip(p, "state")
                got = p.js("Object.fromEntries([...document.querySelectorAll('[data-pop] [data-ms-state]')].map(b => [b.dataset.msState, { icon: (b.querySelector('svg') || {dataset: {}}).dataset.icn, off: b.disabled,"
                           " dash: !!b.querySelector('svg [stroke-dasharray]') }]))")
                self.assertEqual({k: v["icon"] for k, v in got.items() if not v["off"]}, ICONS, "five pickable states, five icons")
                self.assertTrue(got["Forecast"]["dash"], "Forecast is the dashed circle")
                self.assertEqual([k for k, v in got.items() if v["dash"]], ["Forecast"], "no other state is dashed")

    def test_overdue_is_computed_red_and_not_pickable(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp, ms=GO_LIVE, width=width)           # the agreed date is long past and no state is set by hand
                got = self.chips(p)["state"]
                self.assertEqual((got["text"], got["icons"][0]), ("Overdue", "sOver"))
                self.assertEqual(p.js("getComputedStyle(document.querySelector('#peek .pk-chips [data-row=state] .pkc-ic')).color"),
                                 p.js("(() => { const e = document.createElement('i'); e.className = 'ic-r'; document.body.appendChild(e); const c = getComputedStyle(e).color; e.remove(); return c; })()"), "the icon is the red one")
                self.chip(p, "state")
                self.assertEqual(p.js("document.querySelector('[data-pop] [data-ms-state=Overdue]').disabled"), True, "not a choice")
                n = len(self.sent)
                p.js("document.querySelector('[data-pop] [data-ms-state=Overdue]').click()")
                self.assertEqual(len(self.sent), n, "pressing it sends nothing")
                self.assertEqual(self.row(GO_LIVE)["state"], None)

    def test_picking_a_state_is_one_change_with_one_undo(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.chip(p, "state")
            self.click(p, "[data-pop] [data-ms-state='At risk']")
            self.saved("state", "At risk")
            p.until(f"/^State of {PILOT} changed to At risk\\.$/.test((document.querySelector('.toast .toast-text') || {{}}).textContent || '')", "the toast")
            p.until("document.querySelector('#peek .pk-chips [data-row=state]').innerText.trim() === 'At risk'", "the chip shows it")
            self.assertEqual(self.chips(p)["state"]["icons"][0], "sRisk")
            self.undo(p)
            self.saved("state", None)

    def test_progress_blocks_set_the_percentage_and_100_does_not_set_achieved(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.setUp()
                p = self.visit(cdp, width=width)
                self.chip(p, "progress")
                got = p.js("[...document.querySelectorAll('[data-pop] [data-ms-block]')].map(b => [b.dataset.msBlock, b.title, b.getAttribute('aria-label'), b.getBoundingClientRect().height])")
                self.assertEqual([g[0] for g in got], [str(n) for n in range(10, 101, 10)], "ten blocks, 10 to 100")
                self.assertEqual([g[1] for g in got], [f"{n}%" for n in range(10, 101, 10)])
                self.assertEqual([g[2] for g in got], [f"{n} percent" for n in range(10, 101, 10)])
                self.assertTrue(all(g[3] >= 24 for g in got), "24 px targets")
                self.click(p, "[data-pop] [data-ms-block='40']")
                self.saved("percent_complete", 40)
                self.assertEqual(self.sent[-1][1]["changes"], {"percent_complete": 40})
                p.until("document.querySelector('#peek .pk-chips [data-row=progress]').innerText.trim() === '40%'", "the chip says 40%")
                self.chip(p, "progress")
                tones = p.js("[...document.querySelectorAll('[data-pop] [data-ms-block]')].map(b => getComputedStyle(b).backgroundColor)")
                self.assertEqual(len(set(tones[:4])), 4, "each filled block is stronger than the one before")
                self.assertEqual(tones[4], tones[9], "the blocks past 40% are the unfilled colour")
                self.assertNotEqual(tones[3], tones[4])
                self.click(p, "[data-pop] [data-ms-block='100']")
                self.saved("percent_complete", 100)
                row = self.row(self.cur)
                self.assertEqual((row["status"], row["state"], row["actual_date"]), ("Planned", None, None), "100% does not set Achieved")
                self.assertEqual(self.chips(p)["state"]["text"], "On track")
                self.undo(p)
                self.saved("percent_complete", 40)

    def test_the_forecast_chip_opens_the_calendar_and_a_past_date_says_overdue_in_red(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.setUp()
                with self.store.step("dashboard", USER) as st:
                    st.update("milestones", PILOT, {"forecast_date": "2026-01-05"})
                p = self.visit(cdp, width=width)
                got = self.chips(p)["forecast"]
                self.assertTrue(re.fullmatch(r"overdue \d+ days?", got["sub"] or ""), got)
                self.assertIn("05-01-2026", got["text"])
                self.assertEqual(p.js("getComputedStyle(document.querySelector('#peek .pk-chips [data-row=forecast] .pk-chip-sub')).color"), p.js(RED))
                self.chip(p, "forecast")
                text = p.js("document.querySelector('[data-pop]').innerText.replace(/\\s+/g, ' ')")
                for word in ("Today", "Tomorrow", "Friday", "Next week", "No date"):
                    self.assertIn(word, text)
                self.assertTrue(p.js("document.querySelectorAll('.cdate button[data-day]').length >= 28"), "a month of days")
                self.click(p, ".cdate [data-quick]")
                self.assertTrue(self.until_store(lambda: self.row(PILOT)["forecast_date"] != "2026-01-05"), "the forecast moved")
                self.undo(p)
                self.saved("forecast_date", "2026-01-05")

    def test_the_owner_chip_is_a_searchable_list_and_a_pick_saves_the_owner(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.chip(p, "owner")
            self.assertTrue(p.js("!!document.querySelector('.cowner input.cp-in')"), "a search box")
            self.click(p, ".cowner input.cp-in")
            p.js("(() => { const i = document.querySelector('.cowner input.cp-in'); i.value = 'Zed Example'; i.dispatchEvent(new Event('input', {bubbles: true})); })()")
            time.sleep(0.4)
            p.js("document.querySelector('.cowner input.cp-in').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true, cancelable: true}))")
            self.saved("owner", "Zed Example")
            p.until("document.querySelector('#peek .pk-chips [data-row=owner]').innerText.includes('Zed Example')", "the chip shows it")

    # ---- Latest update above Details --------------------------------------------------------------------------------------------------------------

    def test_the_latest_update_box_is_above_details_and_has_no_row(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp, width=width)
                tops = p.js("['#peek .pk-chips', '#peek [data-pk-latest]', '#peek [data-pk-details]'].map(s => { const e = document.querySelector(s); return e ? e.getBoundingClientRect().top : null; })")
                self.assertNotIn(None, tops)
                self.assertLess(tops[0], tops[1], "the chips are above the Latest update")
                self.assertLess(tops[1], tops[2], "the Latest update is above Details")
                self.assertEqual(p.js("document.querySelectorAll('#peek [data-ms-row=latest_update]').length"), 0, "no Latest update row in the Details")
                self.assertEqual(p.js("document.querySelector('#peek [data-pk-latest] [data-rich] .quiet').textContent"), "What changed? Add the latest update…")

    def test_the_latest_update_saves_with_cmd_or_ctrl_enter_once_with_one_undo_and_the_unsaved_bar_guards_closing(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.click(p, "#peek [data-pk-latest] [data-rich=latest_update]")
            p.until("!!document.querySelector('#peek [data-pk-latest] .ProseMirror')", "the editor opened")
            p.js("document.querySelector('#peek .ProseMirror').cxed.editor.commands.insertContent('Waiting on the vendor'); true")
            p.until("!!document.querySelector('[data-pk-latest-hint]')", "the hint")
            self.assertIn("saves", p.js("document.querySelector('[data-pk-latest-hint]').textContent"))
            p.key("Enter", modifiers=4 if p.js("/Mac/.test(navigator.platform)") else 2, code="Enter", vk=13)
            self.saved("latest_update", "<p>Waiting on the vendor</p>")
            self.assertEqual(len([s for s in self.sent if "latest_update" in s[1].get("changes", {})]), 1, "saved once")
            self.assertEqual(self.sent[-1][1]["place"], "peek")
            p.until("!!document.querySelector('#peek [data-pk-last]')", "the stamp")
            self.assertTrue(re.search(r"Last updated\s+\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}", p.js("document.querySelector('#peek [data-pk-last]').innerText")))
            self.undo(p)
            self.saved("latest_update", None)
        with chrome() as cdp:
            self.setUp()
            p = self.visit(cdp)
            self.click(p, "#peek [data-pk-latest] [data-rich=latest_update]")
            p.until("!!document.querySelector('#peek [data-pk-latest] .ProseMirror')", "the editor opened")
            p.js("document.querySelector('#peek .ProseMirror').cxed.editor.commands.insertContent('Not saved yet'); true")
            p.js("document.querySelector('#peek [data-pk-close]').click()")
            p.until("!!document.querySelector('[data-pk-unsaved]')", "the unsaved-update bar")
            self.assertEqual([s for s in self.sent if "latest_update" in s[1].get("changes", {})], [])

    # ---- Details rows -----------------------------------------------------------------------------------------------------------------------------

    def test_the_details_rows_are_in_the_ruled_order_with_icons_and_the_client_line_last(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp, width=width)
                rows = p.js("[...document.querySelectorAll('#peek [data-ms-edit] .pk-row')].map(r => r.querySelector('dt') ? r.querySelector('dt').textContent.trim() : 'CLIENT-LINE')")
                self.assertEqual(rows, ["Description", "Agreed date", "Workstream", "Use case", "Client wording", "CLIENT-LINE"])
                for gone in ("Priority", "Milestone", "Raised", "Forecast date", "Visible to client", "Latest update"):
                    self.assertNotIn(gone, rows)
                self.assertEqual(p.js("[...document.querySelectorAll('#peek [data-ms-edit] dt .pk-rowic svg')].map(i => i.dataset.icn)"), ["doc", "cal", "board", "flag", "doc"], "row icons as the Action peek's")
                agreed = p.js("(() => { const r = document.querySelector('#peek [data-ms-row=baseline]'); return { text: r.innerText.replace(/\\s+/g, ' '), controls: r.querySelectorAll('button, input, [contenteditable]').length }; })()")
                self.assertIn("read only", agreed["text"])
                self.assertEqual(agreed["controls"], 0, "Agreed date is read only")
                self.assertEqual(p.js("document.querySelector('[data-pk-client]').textContent.trim()"), "Client visible")

    def test_achieved_on_is_a_row_only_when_the_state_is_achieved(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertEqual(p.js("document.querySelectorAll('#peek [data-ms-row=actual]').length"), 0)
            self.chip(p, "state")
            self.click(p, "[data-pop] [data-ms-state=Achieved]")
            p.until("document.querySelectorAll('#peek [data-ms-row=actual]').length === 1", "Achieved on appears")
            self.assertEqual(p.js("[...document.querySelectorAll('#peek [data-ms-edit] dt')].map(d => d.textContent.trim()).slice(0, 3)"), ["Description", "Agreed date", "Achieved on"])

    def test_the_empty_rows_say_the_approved_words(self):
        with chrome() as cdp:
            p = self.visit(cdp, ms=GO_LIVE)
            got = p.js("({ d: document.querySelector('#peek [data-ms-row=description] [data-rich] .quiet').textContent, w: document.querySelector('#peek [data-ms-field=workstream]').textContent,"
                       " u: document.querySelector('#peek [data-ms-ucs]').textContent, c: document.querySelector('#peek [data-ms-row=client_message] [data-rich] .quiet').textContent })")
            self.assertEqual(got, {"d": "Add description", "w": "Add workstream", "u": "Select use case", "c": "Add client wording"})

    def test_the_use_case_picker_adds_changes_and_clears_one_link(self):
        a, b = self.two_use_cases()
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                for ms_id in (a, b):
                    with self.store.step("dashboard", USER) as st:
                        sm.unlink_use_case_milestone(st, ms_id, PILOT)
                p = self.visit(cdp, width=width)
                self.assertEqual(self.links(), [])
                self.click(p, "#peek [data-ms-row=use_cases] [data-ms-ucs]")
                p.until("!!document.querySelector('[data-pop][role=menu]')", "the menu opened")
                values = p.js("[...document.querySelectorAll('[data-pop] [role=menuitemradio]')].map(e => e.dataset.value)")
                self.assertIn(a, values), self.assertIn(b, values), self.assertEqual(values[-1], "", "None is the last choice")
                # add
                self.click(p, f"[data-pop] [role=menuitemradio][data-value='{a}']")
                self.assertTrue(self.until_store(lambda: self.links() == [a]), "linked")
                self.assertEqual((self.sent[-1][1]["kind"], self.sent[-1][1]["op"], self.sent[-1][1]["id"], self.sent[-1][1]["ids"]), ("use_cases", "msadd", a, [PILOT]))
                p.until("document.querySelector('#peek [data-ms-ucs]').textContent.includes('Invoice matching')", "the row shows it")
                # change: the shown link is replaced
                self.click(p, "#peek [data-ms-row=use_cases] [data-ms-ucs]")
                self.click(p, f"[data-pop] [role=menuitemradio][data-value='{b}']")
                self.assertTrue(self.until_store(lambda: self.links() == [b]), f"changed: {self.links()}")
                p.until("document.querySelector('#peek [data-ms-ucs]').textContent.includes('Badge printing')", "the row shows the new one")
                # none
                self.click(p, "#peek [data-ms-row=use_cases] [data-ms-ucs]")
                self.click(p, "[data-pop] [role=menuitemradio][data-value='']")
                self.assertTrue(self.until_store(lambda: self.links() == []), "cleared")
                p.until("document.querySelector('#peek [data-ms-ucs]').textContent === 'Select use case'", "the row is empty again")
                self.assertEqual(self.sent[-1][1]["op"], "msremove")
                self.undo(p)
                self.assertTrue(self.until_store(lambda: self.links() == [b]), "one Undo puts the link back")

    def test_the_use_case_picker_needs_no_store_change(self):
        ch = (SRC / "clark" / "changes.py").read_text(encoding="utf-8")
        self.assertNotIn("use_case", ch[ch.index("MILESTONE_PEEK_FIELDS"):ch.index("MILESTONE_PEEK_FIELDS") + 200], "a milestone has no use_case field: the link table is used")
        src = (PAGE_SRC / "edit" / "MilestonePeek.jsx").read_text(encoding="utf-8")
        self.assertIn('"msadd"', src)
        self.assertIn('"msremove"', src)

    def test_client_wording_is_greyed_and_not_clickable_while_not_client_visible_and_live_when_visible(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.setUp()
                p = self.visit(cdp, width=width)
                self.assertEqual(p.js("document.querySelectorAll('#peek [data-ms-wording-off]').length"), 0)
                self.assertEqual(p.js("document.querySelectorAll('#peek [data-ms-row=client_message] [data-rich=client_message]').length"), 1, "visible: the editor")
                self.click(p, "#peek [data-pk-client]")                                   # Client not visible
                p.until("document.querySelector('#peek [data-pk-client]').textContent.trim() === 'Client not visible'", "the line says so")
                p.until("!!document.querySelector('#peek [data-ms-wording-off]')", "the wording is greyed")
                off = p.js("(() => { const e = document.querySelector('#peek [data-ms-wording-off]'), r = e.closest('.pk-row'); return { aria: e.getAttribute('aria-disabled'), title: e.title,"
                           " hint: r.querySelector('[data-ms-wording-hint]').textContent.trim(), editors: r.querySelectorAll('[data-rich], button, input, [contenteditable]').length,"
                           " muted: getComputedStyle(e).color === getComputedStyle(document.querySelector('#peek .muted') || e).color }; })()")
                self.assertEqual((off["aria"], off["title"], off["hint"], off["editors"]), ("true", "Turn on Client visible to edit", "not shown to the client", 0))
                p.js("document.querySelector('#peek [data-ms-wording-off]').click()")
                self.assertEqual(p.js("document.querySelectorAll('#peek .ProseMirror').length"), 0, "a click opens nothing")
                self.click(p, "#peek [data-pk-client]")                                   # Client visible again
                p.until("!!document.querySelector('#peek [data-ms-row=client_message] [data-rich=client_message]')", "the editor is back")
                self.click(p, "#peek [data-ms-row=client_message] [data-rich=client_message]")
                p.until("!!document.querySelector('#peek .ProseMirror')", "clickable")

    # ---- the Description editor -------------------------------------------------------------------------------------------------------------------

    def test_description_enter_is_a_new_line_cmd_or_ctrl_enter_or_leaving_saves_and_esc_cancels(self):
        mod = "/Mac/.test(navigator.platform)"
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.setUp()
                p = self.visit(cdp, ms=GO_LIVE, width=width)
                row = "#peek [data-ms-row=description] [data-rich=description]"
                # Enter is a new line, nothing is sent; Cmd or Ctrl and Enter saves
                self.click(p, row)
                p.until("!!document.querySelector('#peek .ProseMirror') && document.activeElement.classList.contains('ProseMirror')", "the editor opened")
                p.js("document.querySelector('#peek .ProseMirror').cxed.editor.commands.insertContent('First'); true")
                p.key("Enter", code="Enter", vk=13)
                p.js("document.querySelector('#peek .ProseMirror').cxed.editor.commands.insertContent('Second'); true")
                self.assertEqual(self.sent, [], "a plain Enter only adds a line")
                p.key("Enter", modifiers=4 if p.js(mod) else 2, code="Enter", vk=13)
                self.saved("description", "<p>First</p><p>Second</p>")
                p.until("!document.querySelector('#peek .ProseMirror')", "closed after the save")
                # Esc cancels
                n = len(self.sent)
                self.click(p, row)
                p.until("!!document.querySelector('#peek .ProseMirror') && document.activeElement.classList.contains('ProseMirror')", "the editor opened again")
                p.js("document.querySelector('#peek .ProseMirror').cxed.editor.commands.insertContent(' dropped'); true")
                p.key("Escape", code="Escape", vk=27)
                p.until("!document.querySelector('#peek .ProseMirror')", "Esc closed it")
                self.assertEqual(len(self.sent), n, "Esc sent nothing")
                self.assertEqual(self.row(GO_LIVE)["description"], "<p>First</p><p>Second</p>")
                # leaving saves
                self.click(p, row)
                p.until("!!document.querySelector('#peek .ProseMirror') && document.activeElement.classList.contains('ProseMirror')", "the editor opened a third time")
                p.js("document.querySelector('#peek .ProseMirror').cxed.editor.commands.insertContent(' Third'); true")
                p.js("document.activeElement.blur(); document.querySelector('#peek .pk-title').focus(); true")
                self.saved("description", "<p>First</p><p>Second Third</p>")

    # ---- View and the file's chips ----------------------------------------------------------------------------------------------------------------

    def test_the_dashboard_in_view_draws_the_same_chips_read_only_with_the_state_icon(self):
        with self.store.step("dashboard", USER) as st:
            st.update("milestones", PILOT, {"state": "At risk", "state_set": 1, "percent_complete": 40})
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp, width=width, view="dashboard")
                got = self.chips(p)
                self.assertEqual(list(got), ["state", "owner", "progress", "forecast"])
                self.assertEqual((got["state"]["text"], got["state"]["icons"][0], got["progress"]["text"]), ("At risk", "sRisk", "40%"))
                self.assertEqual(p.js("document.querySelectorAll('#peek .pk-chips button').length"), 0, "no tools in View")


class Source(unittest.TestCase):
    def test_the_state_icons_are_the_peeks_own_and_the_milestones_page_look_is_unchanged(self):
        icons = (PAGE_SRC / "components" / "Icon.jsx").read_text(encoding="utf-8")
        for name in ("sForecast", "sTrack", "sRisk", "sSlip", "sOver", "sClosed"):
            self.assertIn(f"{name}:", icons)
        self.assertIn('stroke-dasharray="3 3.6"', icons)
        logic = (PAGE_SRC / "logic" / "milestones.js").read_text(encoding="utf-8")
        self.assertIn('"On track": ["green", "dot"', logic, "LOOK is the Milestones page's and the client peek's: unchanged")
        self.assertIn('Slipped: ["red", "diamond"', logic)

    def test_progress_at_100_does_not_set_the_state(self):
        src = (PAGE_SRC / "edit" / "MilestonePeek.jsx").read_text(encoding="utf-8")
        block = src[src.index("function ProgressPop"):src.index("function ForecastPop")]
        self.assertIn("progressChange(was, String(n))", block)
        self.assertNotIn("Achieved", block)
        self.assertNotIn("stateChange", block)


if __name__ == "__main__":
    unittest.main()
