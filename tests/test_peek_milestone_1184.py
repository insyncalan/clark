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

    refuse = ()      # the ops of change requests the server refuses in a test (a real refusal's shape)

    def seam(self, real, which):
        base = super().seam(real, which)

        def call(req):
            if which == "change" and req.get("op") in self.refuse:
                self.sent.append(("refused", req))
                return 400, {"ok": False, "message": "That use case can't be changed just now.", "code": "refused"}
            return base(req)
        return call

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
        from _rich_page import wait_for
        return wait_for(test, seconds) or test()

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
                self.assertEqual(p.js("document.querySelectorAll('#peek .pk-ms-states, #peek [data-ms-head], #peek [data-ms-range]').length"), 0, "the editor has no header line, no States row, no slider")

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
                self.assertEqual(p.js("[...document.querySelectorAll('[data-pop] [data-ms-state]')].map(b => b.dataset.msState)"), ["Forecast", "On track", "At risk", "Slipped", "Achieved"], "five values: Overdue is not an option")
                self.assertEqual(p.js("document.querySelectorAll('[data-pop] [data-ms-state=Overdue]').length"), 0)
                self.assertEqual(p.js("document.querySelectorAll('[data-pop] [data-ms-state][disabled]').length"), 0)
                self.assertEqual(self.sent, [])
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
            p.js("window.__drawn = 0; requestAnimationFrame(() => requestAnimationFrame(() => { window.__drawn = 1; }))")
            p.until("window.__drawn === 1", "the page drew the typed text")
            p.js("document.querySelector('.cowner input.cp-in').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true, cancelable: true}))")
            self.saved("owner", "Zed Example")
            p.until("document.querySelector('#peek .pk-chips [data-row=owner]').innerText.includes('Zed Example')", "the chip shows it")


    def test_the_block_that_equals_the_progress_sets_it_back_to_0_by_mouse_and_by_keyboard(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.setUp()
                with self.store.step("dashboard", USER) as st:
                    st.update("milestones", PILOT, {"percent_complete": 40})
                p = self.visit(cdp, width=width)
                self.chip(p, "progress")
                self.click(p, "[data-pop] [data-ms-block='40']")
                self.saved("percent_complete", 0)
                p.until("document.querySelector('#peek .pk-chips [data-row=progress]').innerText.trim() === '0%'", "the chip says 0%")
                # keyboard: set 40 again, then Enter on the focused 40 block clears; Space does the same
                for key, vk, text in (("Enter", 13, "\r"), (" ", 32, " ")):
                    self.chip(p, "progress")
                    self.click(p, "[data-pop] [data-ms-block='40']")
                    self.saved("percent_complete", 40)
                    p.until("document.querySelector('#peek .pk-chips [data-row=progress]').innerText.trim() === '40%'", "the chip says 40%")
                    self.chip(p, "progress")
                    p.js("document.querySelector('[data-pop] [data-ms-block=\"40\"]').focus()")
                    for kind in ("keyDown", "keyUp"):
                        cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": "Enter" if key == "Enter" else "Space", "windowsVirtualKeyCode": vk, **({"text": text} if kind == "keyDown" else {})}, p.sid)
                    self.saved("percent_complete", 0)
                    p.until("document.querySelector('#peek .pk-chips [data-row=progress]').innerText.trim() === '0%'", "the chip says 0%")

    def test_pressing_achieved_again_reopens_and_another_state_on_a_done_milestone_clears_the_achieved_date(self):
        done = {"status": "Done", "state": "Achieved", "state_set": 1, "actual_date": "2026-03-04", "percent_complete": 100}
        with chrome() as cdp:
            with self.store.step("dashboard", USER) as st:
                st.update("milestones", PILOT, done)
            p = self.visit(cdp)
            self.chip(p, "state")
            self.assertEqual(p.js("document.querySelector('[data-pop] [data-ms-state=Achieved]').getAttribute('aria-pressed')"), "true")
            self.click(p, "[data-pop] [data-ms-state=Achieved]")
            self.saved("status", "Planned")
            row = self.row(PILOT)
            self.assertEqual((row["state"], row["state_set"], row["actual_date"]), (None, 0, None), "reopened: the dates decide again")
        with chrome() as cdp:
            self.setUp()
            with self.store.step("dashboard", USER) as st:
                st.update("milestones", PILOT, done)
            p = self.visit(cdp)
            self.chip(p, "state")
            self.click(p, "[data-pop] [data-ms-state=Slipped]")
            self.saved("status", "Planned")
            row = self.row(PILOT)
            self.assertEqual((row["state"], row["state_set"], row["actual_date"]), ("Slipped", 1, None))
            p.until("document.querySelectorAll('#peek [data-ms-row=actual]').length === 0", "the Achieved on row goes")

    def test_an_unchanged_value_sends_nothing_and_clearing_says_cleared(self):
        with chrome() as cdp:
            with self.store.step("dashboard", USER) as st:
                st.update("milestones", GO_LIVE, {"workstream": "Build"})
            p = self.visit(cdp, ms=GO_LIVE)
            self.assertEqual(self.sent, [])
            # the same owner: nothing sent
            self.chip(p, "owner")
            self.click(p, ".cowner input.cp-in")
            p.js("document.querySelector('.cowner input.cp-in').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true, cancelable: true}))")
            p.until("!document.querySelector('[data-pop]')", "the popover closed")
            # the same workstream: nothing sent
            self.click(p, "#peek [data-ms-field=workstream]")
            self.click(p, "[data-pop] [role=menuitemradio][data-value=Build]")
            p.until("!document.querySelector('[data-pop]')", "the menu closed")
            self.assertEqual(self.sent, [], "an unchanged value sends nothing")
            # No workstream clears with the cleared toast
            self.click(p, "#peek [data-ms-field=workstream]")
            self.click(p, "[data-pop] [role=menuitemradio][data-value='']")
            self.saved("workstream", None)
            p.until(f"(document.querySelector('.toast .toast-text') || {{}}).textContent === 'Workstream of {GO_LIVE} cleared.'", "the cleared toast")
            # No date clears the forecast
            self.chip(p, "forecast")
            self.click(p, ".cdate [data-quick='']") if p.js("!!document.querySelector(\".cdate [data-quick='']\")") else p.js("[...document.querySelectorAll('.cdate [data-quick]')].find(b => /No date/.test(b.textContent)).click()")
            self.saved("forecast_date", None)
            p.until(f"(document.querySelector('.toast .toast-text') || {{}}).textContent === 'Forecast date of {GO_LIVE} cleared.'", "the cleared toast")
            # a blank owner clears with the cleared toast
            self.chip(p, "owner")
            self.click(p, ".cowner input.cp-in")
            p.js("(() => { const i = document.querySelector('.cowner input.cp-in'); i.value = ''; i.dispatchEvent(new Event('input', {bubbles: true})); })()")
            p.js("window.__drawn = 0; requestAnimationFrame(() => requestAnimationFrame(() => { window.__drawn = 1; }))")
            p.until("window.__drawn === 1", "the page drew the typed text")
            p.js("document.querySelector('.cowner input.cp-in').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true, cancelable: true}))")
            self.saved("owner", None)
            p.until(f"(document.querySelector('.toast .toast-text') || {{}}).textContent === 'Owner of {GO_LIVE} cleared.'", "the cleared toast")

    def test_a_milestone_that_is_not_client_visible_has_a_disabled_line_and_a_greyed_wording(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.setUp()
                with self.store.step("dashboard", USER) as st:
                    st.update("milestones", PILOT, {"client_visible": 0, "client_message": "<p>Internal words</p>"})
                p = self.visit(cdp, width=width)
                line = p.js("(() => { const b = document.querySelector('#peek [data-pk-client]'); return { text: b.textContent.trim(), off: b.disabled, pressed: b.getAttribute('aria-pressed') }; })()")
                self.assertEqual(line, {"text": "Client not visible", "off": True, "pressed": "false"})
                self.assertEqual(p.js("document.querySelectorAll('#peek [data-ms-wording-off]').length"), 1)
                self.assertIn("Internal words", p.js("document.querySelector('#peek [data-ms-wording-off]').textContent"), "the wording is shown, greyed")
                n = len(self.sent)
                p.js("document.querySelector('#peek [data-pk-client]').click()")
                self.assertEqual(len(self.sent), n, "the disabled line sends nothing")

    def test_the_agreed_date_is_shown_as_dd_mm_yyyy(self):
        with chrome() as cdp:
            p = self.visit(cdp, ms=GO_LIVE)
            self.assertIn("10-01-2020", p.js("document.querySelector('#peek [data-ms-row=baseline] dd').textContent"))


    def test_the_four_chips_are_on_one_line_at_both_widths_with_and_without_overdue_words(self):
        for width in (1400, 900):
            for ms in (PILOT, GO_LIVE):
                with self.subTest(width=width, ms=ms), chrome() as cdp:
                    if ms == GO_LIVE:      # a late forecast of a few days, as the screenshot has: "overdue 12 days"
                        import datetime
                        late = (datetime.date.today() - datetime.timedelta(days=12)).isoformat()
                        with self.store.step("dashboard", USER) as st:
                            st.update("milestones", GO_LIVE, {"forecast_date": late})
                    p = self.visit(cdp, ms=ms, width=width)
                    got = p.js("[...document.querySelectorAll('#peek .pk-chips > [data-row]')].map(e => { const r = e.getBoundingClientRect(); const v = e.querySelector('.pkc-v'); return [Math.round(r.top), Math.round(r.right), v.scrollWidth <= v.clientWidth + 1]; })")
                    self.assertEqual(len({g[0] for g in got}), 1, f"all four chip tops are equal: {got}")
                    pr = p.js("document.querySelector('#peek').getBoundingClientRect().right")
                    self.assertLessEqual(max(g[1] for g in got), pr, "inside the peek")
                    if ms == PILOT:
                        self.assertTrue(all(g[2] for g in got), f"no value is cut short: {got}")
                    self.assertTrue(got[3][2], f"the forecast date and its overdue words are never cut: {got}")

    def test_esc_closes_the_open_popover_first_and_not_the_peek(self):
        for field in ("state", "owner", "progress", "forecast"):
            with self.subTest(field=field), chrome() as cdp:
                p = self.visit(cdp)
                self.chip(p, field)
                p.js("(() => { const e = document.activeElement; ((e && e !== document.body ? e : document.body)).dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true})); })()")
                p.until("!document.querySelector('[data-pop]')", f"Esc closed the {field} popover")
                self.assertEqual(p.js("!!document.querySelector('#peek')"), True, "the peek is still open")
                self.assertEqual(self.sent, [], "Esc sent nothing")

    # ---- real keys in the State and Progress popovers (the browser's own key events, CDP Input.dispatchKeyEvent) -------------------------------------

    KEYS = {"ArrowDown": (40, ""), "ArrowUp": (38, ""), "ArrowRight": (39, ""), "ArrowLeft": (37, ""), "Home": (36, ""), "End": (35, ""), "Enter": (13, "\r"), " ": (32, " "), "Escape": (27, "")}

    def real_key(self, cdp, p, key):
        vk, text = self.KEYS[key]
        code = {" ": "Space"}.get(key, key)
        for kind in ("keyDown", "keyUp"):
            cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": code, "windowsVirtualKeyCode": vk, **({"text": text} if kind == "keyDown" and text else {})}, p.sid)

    def at(self, p):
        return p.js("(() => { const a = document.activeElement; return a && (a.dataset.msState || a.dataset.msBlock) || null; })()")

    def test_the_state_options_are_reached_by_real_arrows_home_end_and_enter_picks(self):
        order = ["Forecast", "On track", "At risk", "Slipped", "Achieved"]
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.setUp()
                p = self.visit(cdp, width=width)
                self.chip(p, "state")
                p.until("document.activeElement && !!document.activeElement.dataset.msState", "focus is on a state option as the popover opens")
                self.assertEqual(self.at(p), "On track", "the current state has the focus")
                walk = []
                for key in ("ArrowDown", "ArrowDown", "ArrowDown", "ArrowDown", "ArrowUp", "ArrowRight", "ArrowLeft", "Home", "End"):
                    self.real_key(cdp, p, key)
                    walk.append(self.at(p))
                self.assertEqual(walk, ["At risk", "Slipped", "Achieved", "Forecast", "Achieved", "Forecast", "Achieved", "Forecast", "Achieved"], "Down/Right next, Up/Left previous (wrapping), Home first, End last")
                self.assertEqual(p.js("!!document.querySelector('[data-pop]')"), True)
                self.real_key(cdp, p, "ArrowUp")
                self.real_key(cdp, p, "Enter")
                self.saved("state", "Slipped")
                p.until("!document.querySelector('[data-pop]')", "Enter picked and closed")

    def test_real_esc_in_the_state_popover_closes_it_and_not_the_peek(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.chip(p, "state")
            p.until("!!document.activeElement.dataset.msState", "focus inside")
            self.real_key(cdp, p, "ArrowDown")
            self.real_key(cdp, p, "Escape")
            p.until("!document.querySelector('[data-pop]')", "Esc closed the popover")
            self.assertEqual(p.js("!!document.querySelector('#peek')"), True, "the peek is still open")
            self.assertEqual(self.sent, [])
            self.real_key(cdp, p, "Escape")
            p.until("!document.querySelector('#peek')", "a second Esc closes the peek")

    def test_the_progress_blocks_are_reached_by_real_arrows_home_end_and_enter_or_space_sets(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.setUp()
                p = self.visit(cdp, width=width)
                self.chip(p, "progress")
                p.until("document.activeElement && !!document.activeElement.dataset.msBlock", "focus is on a block as the popover opens")
                self.assertEqual(self.at(p), "10", "no progress: the first block has the focus")
                walk = []
                for key in ("ArrowRight", "ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp", "End", "ArrowDown", "End", "Home", "ArrowUp"):
                    self.real_key(cdp, p, key)
                    walk.append(self.at(p))
                self.assertEqual(walk, ["20", "30", "40", "30", "20", "100", "10", "100", "10", "100"])
                self.real_key(cdp, p, "ArrowUp")
                self.real_key(cdp, p, "Enter")
                self.saved("percent_complete", 90)
                p.until("!document.querySelector('[data-pop]')", "Enter set it and closed")
                p.until("document.querySelector('#peek .pk-chips [data-row=progress]').innerText.trim() === '90%'", "the chip says 90%, so the peek has the new progress before the popover opens again")
                self.chip(p, "progress")
                p.until("document.activeElement && document.activeElement.dataset.msBlock === '90'", "the block of the current progress has the focus")
                self.real_key(cdp, p, "ArrowLeft")
                self.real_key(cdp, p, " ")
                self.saved("percent_complete", 80)

    def test_real_esc_in_the_progress_popover_closes_it_and_not_the_peek(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.chip(p, "progress")
            p.until("!!document.activeElement.dataset.msBlock", "focus inside")
            self.real_key(cdp, p, "Escape")
            p.until("!document.querySelector('[data-pop]')", "Esc closed the popover")
            self.assertEqual(p.js("!!document.querySelector('#peek')"), True, "the peek is still open")

    def test_real_enter_on_the_block_equal_to_the_progress_sets_0(self):
        with chrome() as cdp:
            self.setUp()
            with self.store.step("dashboard", USER) as st:
                st.update("milestones", PILOT, {"percent_complete": 40})
            p = self.visit(cdp)
            self.chip(p, "progress")
            p.until("document.activeElement && document.activeElement.dataset.msBlock === '40'", "the current block has the focus")
            self.real_key(cdp, p, "Enter")
            self.saved("percent_complete", 0)

    def test_esc_still_closes_the_picker_first_for_the_other_chips_by_real_key(self):
        for field in ("owner", "forecast"):
            with self.subTest(field=field), chrome() as cdp:
                p = self.visit(cdp)
                self.chip(p, field)
                self.real_key(cdp, p, "Escape")
                p.until("!document.querySelector('[data-pop]')", f"Esc closed the {field} popover")
                self.assertEqual(p.js("!!document.querySelector('#peek')"), True, "the peek is still open")

    def test_the_state_pick_has_a_pickable_guard(self):
        src = (PAGE_SRC / "edit" / "MilestonePeek.jsx").read_text(encoding="utf-8")
        pick = src[src.index("function StatePop"):src.index("function OwnerPop")]
        self.assertIn("if (!PICKABLE.includes(s)) return;", pick)
        self.assertNotIn("ALL_STATES", pick)

    def test_every_value_in_the_details_rows_is_one_font_size(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp, ms=GO_LIVE, width=width)
                sizes = p.js("[...document.querySelectorAll('#peek [data-ms-edit] .pk-row dd')].map(d => [d.parentElement.dataset.msRow, [...new Set([d, ...d.querySelectorAll('button, span, p, .rf-empty, [data-rich]')].filter(e => e.textContent.trim()).map(e => getComputedStyle(e).fontSize))]])")
                allsizes = {x for _, ss in sizes for x in ss}
                self.assertEqual(len(allsizes), 1, f"one font size in the Details values: {sizes}")

    def test_filled_and_empty_progress_blocks_read_apart_in_both_themes(self):
        for theme in ("light", "dark"):
            with self.subTest(theme=theme), chrome() as cdp:
                with self.store.step("dashboard", USER) as st:
                    st.update("milestones", PILOT, {"percent_complete": 30})
                p = self.visit(cdp)
                p.js(f"document.documentElement.dataset.theme = '{theme}'")
                self.chip(p, "progress")
                lum = ("(c => { const v = c.match(/[\\d.]+/g).slice(0, 3).map(Number).map(x => { x /= 255; return x <= .03928 ? x / 12.92 : Math.pow((x + .055) / 1.055, 2.4); });"
                       " return .2126 * v[0] + .7152 * v[1] + .0722 * v[2]; })")
                a, b = p.js(f"[...document.querySelectorAll('[data-pop] [data-ms-block]')].slice(0, 4).map(e => {lum}(getComputedStyle(e).backgroundColor))"), None
                filled, empty = a[0], a[3]
                ratio = (max(filled, empty) + .05) / (min(filled, empty) + .05)
                self.assertGreaterEqual(ratio, 1.5, f"{theme}: filled {filled:.3f} against empty {empty:.3f}")

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
                self.assertRegex(p.js("document.querySelector('#peek [data-pk-latest] [data-rich] .quiet').textContent"), r"^Created( by .+)?, \d{2}-\d{2}-\d{4} \d{2}:\d{2}")      # row 1470: a milestone never updated shows its Created entry (the issue lists Milestone among the peeks)

    def test_the_latest_update_saves_with_cmd_or_ctrl_enter_once_with_one_undo_and_the_unsaved_bar_guards_closing(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.click(p, "#peek [data-pk-latest] [data-rich=latest_update]")
            p.until("!!document.querySelector('#peek [data-pk-latest] .ProseMirror')", "the editor opened")
            p.js("document.querySelector('#peek .ProseMirror').cxed.editor.commands.insertContent('Waiting on the vendor'); true")
            p.until("!!document.querySelector('[data-pk-latest-hint]')", "the hint")
            self.assertIn("to save", p.js("document.querySelector('[data-pk-latest-hint]').textContent"))
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
                self.assertIn(a, values), self.assertIn(b, values)
                self.assertNotIn("", values, "nothing linked: there is no link for None to end, so it is not offered")
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

    def test_a_refused_end_of_the_old_link_puts_the_made_add_back_and_a_refused_add_keeps_the_old_link(self):
        for what, refused in (("the end of the old link", "msremove"), ("the add", "msadd")):
            with self.subTest(refused=what), chrome() as cdp:
                self.setUp()
                a, b = self.two_use_cases()
                with self.store.step("dashboard", USER) as st:
                    sm.link_use_case_milestone(st, a, PILOT)
                self.refuse = (refused,)
                p = self.visit(cdp)
                self.assertEqual(self.links(), [a])
                self.click(p, "#peek [data-ms-row=use_cases] [data-ms-ucs]")
                self.click(p, f"[data-pop] [role=menuitemradio][data-value='{b}']")
                p.until("!!document.querySelector('.toast .toast-text')", "a message")
                self.assertEqual(p.js("document.querySelector('.toast .toast-text').textContent"), "That change could not be made, and nothing was changed. Reload the page and try again.", "the page's words for a refused change")
                p.until("document.querySelector('#peek [data-ms-ucs]').textContent.includes('Invoice matching')", "the row still shows the old link")
                self.assertTrue(self.until_store(lambda: self.links() == [a]), f"the old link is the only one: nothing half-made is left: {self.links()}")
                ops = [r["op"] for w, r in self.sent if w in ("change", "refused") and r.get("kind") == "use_cases"]
                if refused == "msremove":
                    self.assertEqual(ops, ["msadd", "msremove"], "the add was made, then the end was refused")
                    self.assertTrue(self.until_store(lambda: self.links() == [a]))
                    self.assertEqual(p.js("!!document.querySelector('.toast [data-undo]')"), False, "no Undo is left for a change that was put back")
                else:
                    self.assertEqual(ops, ["msadd"], "a refused add stops before the old link is touched")

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
                cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, p.sid)      # the editor ignores a blur while document.hasFocus() is false (RichText away); a headless page on macOS is not focused
                p.until("document.hasFocus()", "the page has the focus")
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
                # Wait for the typed text, then move the focus straight to another field (one step, so the box sees where the focus goes). A blur with no
                # target while the browser window is not focused is read as 'the person left the window', which keeps the box open (RichText away()): on a
                # busy CI machine the window is not always focused, so the test says outright that the window has the focus and does not depend on it.
                p.until("document.querySelector('#peek .ProseMirror').textContent.includes('Third')", "the typed text is in the box")
                self.assertTrue(p.js("document.hasFocus()"), "the page has the focus before the focus moves")
                # The leave-save runs from a focusout (RichText away(), checked one tick later); if that one focus move did not register on a busy runner (a CI shard at 900),
                # nothing retries it and the old text stays. So: move the focus, wait for the box to close, and if it is still open put the focus back in the text and move it again.
                from _rich_page import wait_for
                gone = lambda: p.js("!document.querySelector('#peek .ProseMirror')")
                for _ in range(3):
                    p.js("document.querySelector('#peek .pk-title').focus(); true")
                    if wait_for(gone, 4):
                        break
                    p.js("(() => { const e = document.querySelector('#peek .ProseMirror'); if (e) e.focus(); return true; })()")
                self.saved("description", "<p>First</p><p>Second Third</p>")

    # ---- View and the file's chips ----------------------------------------------------------------------------------------------------------------

    def test_the_dashboard_in_view_keeps_the_header_line_and_has_no_chip_row(self):
        """Row 1184 changes the editor's peek only: View (and a published file) keep the read only header line of row 1078, with the client's state word."""
        with self.store.step("dashboard", USER) as st:
            st.update("milestones", PILOT, {"state": "At risk", "state_set": 1, "percent_complete": 40})
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                from test_report_editor import Pg
                p = Pg.at(self, cdp, self.s.port, f"#dashboard&p=ABC&ms={PILOT}")
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.until("!!document.querySelector('#peek [data-ms-head]')", "the header line")
                self.assertEqual(p.js("document.querySelectorAll('#peek .pk-chips, #peek [data-ms-block]').length"), 0, "no chip row in View")
                self.assertEqual(p.js("document.querySelector('#peek [data-ms-head=state]').textContent.trim()"), "At risk")
                self.assertEqual(p.js("document.querySelectorAll('#peek [data-ms-head] button').length"), 0, "read only")

    def test_the_published_chip_word_is_the_clients_state_word(self):
        src = (PAGE_SRC / "components" / "Peek.jsx").read_text(encoding="utf-8")
        self.assertIn("m.state_word", src[src.index("export function MsState"):src.index("export const MsSep")], "a file's state is the client's word (publish.py state_word)")


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
        self.assertIn("progressChange(was, String(n === was ? 0 : n))", block)
        self.assertNotIn("Achieved", block)
        self.assertNotIn("stateChange", block)


if __name__ == "__main__":
    unittest.main()
