"""Item 1184: the Milestone peek on the shared peek frame (item 1180), Layout A of the approved mockup (peek-milestone.png). The old header line
(State, Owner, Progress), the State button row and the Visible to client row go; in their place a chip row of four (State, Owner, Progress,
Forecast date), each with its popover. State has five pickable values with their own icons (Forecast dashed) and an Overdue that is worked out
and not pickable. Progress is ten blocks. The Forecast date chip says "overdue N days" in red. Details run Description, Agreed date, Achieved on
(only when Achieved), Workstream, Use case (a picker), Client wording, then the Client visible line; Client wording is greyed while Client is
not visible; Enter in Description is a new line and Cmd/Ctrl+Enter saves. The Latest update box needs the store change (own ticket) and is
pinned only as a skipped expectation.

Run: python3 dev/run_tests.py test_peek_milestone_1184

Without a browser: the sources. With headless Chrome (fails, never skips, without it): the Milestones page in Edit, at 1400 and 900 px.
Chips are `#peek .pk-chips > [data-row]` (state, owner, progress, forecast); the second line of a chip is `.pk-chip-sub`. Milestones:
ABC-M-001 (Pilot live, planned, far ahead) and ABC-M-002 (Go live, long overdue) from test_movement_page.
"""
import json
import re
import unittest

from _demo import USER
from _paths import ROOT

from test_movement_page import GO_LIVE, PILOT  # noqa: E402
import test_milestone_peek_1078 as m1078  # noqa: E402      # the module, not its classes: a class imported by name would be collected and run again here
PAGE_SRC = m1078.PAGE_SRC
from test_movement_page import Base  # noqa: E402
from test_server import chrome  # noqa: E402

CHIP_ORDER = ["state", "owner", "progress", "forecast"]
ICONS = {"state": "half", "owner": "user", "progress": "bars", "forecast": "cal"}
STATES = ["Forecast", "On track", "At risk", "Slipped", "Achieved"]
STATE_ICONS = {"Forecast": "sForecast", "On track": "sTrack", "At risk": "sRisk", "Slipped": "sSlip", "Achieved": "sClosed"}
ROWS = ["Description", "Agreed date", "Workstream", "Use case", "Client wording"]
ROWS_DONE = ["Description", "Agreed date", "Achieved on", "Workstream", "Use case", "Client wording"]
OLD = ("Visible to client", "Forecast date", "Use cases")      # row labels that leave the Details

CHIPS = """(() => { const p = document.querySelector('#peek'); if (!p) return null;
  const row = p.querySelector('.pk-chips'); const out = {};
  if (row) for (const c of row.children) { const k = c.dataset.row; if (!k) continue; const r = c.getBoundingClientRect(); const sub = c.querySelector('.pk-chip-sub');
    out[k] = { text: c.innerText.replace(/\\s+/g, ' ').trim(), tag: c.tagName, t: Math.round(r.top), h: r.height, l: r.left, r: r.right,
      icons: [...c.querySelectorAll('svg[data-icn]')].map(s => s.dataset.icn), sub: sub ? sub.textContent.trim() : null,
      subColour: sub ? getComputedStyle(sub).color : null, haspopup: (c.querySelector('button') || c).getAttribute('aria-haspopup') }; }
  const probe = (name) => { const e = document.createElement('i'); e.style.color = 'var(' + name + ')'; document.body.appendChild(e); const c = getComputedStyle(e).color; e.remove(); return c; };
  return { order: Object.keys(out), chips: out, red: probe('--status-red-text'), peekR: p.getBoundingClientRect().right, side: p.scrollWidth - p.clientWidth,
    oldHead: p.querySelectorAll('[data-ms-head], [data-ms-states], .pk-ms-head, .pk-ms-states').length }; })()"""
LABELS = "[...document.querySelectorAll('#peek .pk-fields dt')].map(d => d.textContent.trim())"
POP_ITEMS = """[...document.querySelectorAll('[data-pop] [role=menuitemradio], [data-pop] [role=option], [data-pop] [role=menuitem]')].map(b => ({
  text: b.textContent.replace(/\\s+/g, ' ').trim(), disabled: b.disabled || b.getAttribute('aria-disabled') === 'true', checked: b.getAttribute('aria-checked'),
  icons: [...b.querySelectorAll('svg[data-icn]')].map(s => s.dataset.icn) }))"""


class Sources(unittest.TestCase):
    def test_the_old_header_line_the_state_buttons_and_the_visible_row_are_gone_from_the_milestone_peek(self):
        edit = (PAGE_SRC / "components" / "PeekMilestoneBody.jsx").read_text(encoding="utf-8")
        body = edit[edit.index("export function MilestoneBody"):]
        self.assertNotIn("<MsHead", body)
        self.assertNotIn("<States", body)
        self.assertNotIn('<Row name="Forecast date"', body)
        self.assertNotIn('<Row name="Visible to client"', body)
        self.assertNotIn('<Row name="Use cases"', body)
        self.assertEqual([m.group(1) for m in re.finditer(r'<Row name="([^"]+)"', body)],
                         ["Description", "Agreed date", "Achieved on", "Workstream", "Use case", "Client wording"], "the ticket's order")

    def test_the_peek_draws_a_milestone_chip_row_on_the_generic_chips(self):
        src = (PAGE_SRC / "components" / "Peek.jsx").read_text(encoding="utf-8")
        self.assertIn("MilestoneChips", src)
        src = (PAGE_SRC / "components" / "PeekMilestoneChips.jsx").read_text(encoding="utf-8")
        chips = src[src.index("function MilestoneChips"):]
        chips = chips[:chips.index("\n}\n")]
        self.assertEqual(re.findall(r'field="(\w+)"', chips), CHIP_ORDER, "State, Owner, Progress, Forecast date")
        self.assertIn("PeekChip", chips)

    def test_the_new_state_glyphs_exist_in_the_icon_set(self):
        src = (PAGE_SRC / "components" / "Icon.jsx").read_text(encoding="utf-8")
        for name in ("sForecast", "sTrack", "sRisk", "sSlip", "sDelayed"):
            self.assertRegex(src, r"\b%s\b" % name, name)
        self.assertRegex(src, r"sForecast[^\n]*stroke-dasharray|stroke-dasharray[^\n]*3[ ,]3\.6", "Forecast is a plain dashed circle")

    def test_the_forecast_chip_has_no_forecast_tag_and_the_use_case_is_a_picker(self):
        src = (PAGE_SRC / "components" / "PeekMilestoneChips.jsx").read_text(encoding="utf-8")      # MilestoneChips lives here, Peek.jsx only imports it
        self.assertNotRegex(src[src.index("function MilestoneChips"):][:1500], r'sub=\{?["\']forecast', "the 'forecast' tag was removed (Alan 14-11)")
        edit = (PAGE_SRC / "components" / "PeekMilestoneBody.jsx").read_text(encoding="utf-8")      # the editor's body moved here; MilestonePeek.jsx re-exports it
        self.assertIn("Select use case", edit)


class Peek(Base):
    """The Milestones page, Edit, at both widths. The helpers of Fields (row 1078) are borrowed; its tests are not run again here."""
    cur = PILOT
    click = m1078.Fields.click
    until_store = m1078.Fields.until_store
    saved = m1078.Fields.saved

    def visit(self, cdp, ms=PILOT, width=1400):
        from test_report_editor import Pg
        self.cur = ms
        p = Pg.at(self, cdp, self.s.port, f"#milestones&p=ABC&ms={ms}")
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.until("!!document.querySelector('#peek .pk-chips [data-row=state]')", "the peek drew its chip row")
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, p.sid)
        p.until("document.getAnimations().length === 0", "no animation running")
        return p

    def open_chip(self, p, k):
        sel = f"#peek .pk-chips [data-row={k}] button"
        self.click(p, sel)
        p.until("!!document.querySelector('[data-pop]')", f"{k}: a popover opens")

    def test_four_chips_in_order_each_icon_value_chevron_in_one_flat_row_at_both_widths(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp, width=width)
                got = p.js(CHIPS)
                self.assertEqual(got["order"], CHIP_ORDER)
                self.assertEqual(got["oldHead"], 0, "no old header line or state button row")
                self.assertLessEqual(len({c["t"] for c in got["chips"].values()}), 2, "one flat row (it may wrap once at 900)")
                for k, c in got["chips"].items():
                    if k == "state":
                        self.assertIn(c["icons"][0], list(STATE_ICONS.values()) + ["sDelayed"], "a state glyph")
                    else:
                        self.assertEqual(c["icons"][0], ICONS[k], k)
                    self.assertEqual(c["icons"][-1], "chevdown", f"{k}: the small chevron last")
                    self.assertEqual(c["tag"], "SPAN")
                    self.assertTrue(c["text"], k)
                    self.assertGreaterEqual(c["h"], 24, f"{k}: a 24 px target")
                    self.assertLessEqual(c["r"], got["peekR"] + 0.5, f"{k}: inside the peek")
                    self.assertEqual(c["haspopup"] is not None, True, f"{k}: opens a popover")
                self.assertLessEqual(got["side"], 1, "no sideways scroll")
                self.assertEqual(got["chips"]["owner"]["text"].replace("Change", "").strip().split(" ")[0:2], ["Sam", "Example"])
                self.assertTrue(got["chips"]["state"]["text"].startswith("On track"))

    def test_the_forecast_chip_is_the_date_with_no_forecast_tag(self):
        self.demo.update("milestones", PILOT, {"forecast_date": "2030-03-15"})     # the demo milestone has only an agreed date
        with chrome() as cdp:
            p = self.visit(cdp)
            text = p.js(CHIPS)["chips"]["forecast"]["text"]
            self.assertRegex(text, r"\d\d-\d\d-\d{4}")
            self.assertNotRegex(text.lower(), r"forecast", "the 'forecast' tag was removed on Alan's word, 14-11")

    def test_the_state_popover_has_five_pickable_values_with_their_own_icons_forecast_dashed(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp, width=width)
                self.open_chip(p, "state")
                items = p.js(POP_ITEMS)
                pickable = [i for i in items if not i["disabled"]]
                self.assertEqual([i["text"] for i in pickable], STATES)
                for i in pickable:
                    self.assertEqual(i["icons"][0], STATE_ICONS[i["text"]], i["text"])
                self.assertEqual(sum(1 for i in items if i["checked"] == "true"), 1, "the current one is marked")
                self.assertEqual([i["text"] for i in items if i["checked"] == "true"], ["On track"])

    def test_picking_a_state_saves_it_with_a_toast_and_achieved_sets_100(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.open_chip(p, "state")
            p.js("[...document.querySelectorAll('[data-pop] [role=menuitemradio], [data-pop] [role=option], [data-pop] [role=menuitem]')].find(b => b.textContent.includes('Achieved')).click()")
            self.saved(p, "status", "Done")
            row = self.row(self.cur)
            self.assertEqual((row["state"], row["percent_complete"]), ("Achieved", 100))
            p.until("(document.querySelector('.toast .toast-text') || {}).textContent === 'State of ABC-M-001 changed to Achieved.'", "the toast")
            p.until("/Achieved/.test(document.querySelector('#peek .pk-chips [data-row=state]').innerText)", "the chip follows")
            p.js("document.querySelector('.toast [data-undo]').click()")
            self.saved(p, "status", "Planned")

    def test_an_overdue_milestone_shows_overdue_in_red_with_the_delayed_glyph_and_it_is_not_pickable(self):
        with chrome() as cdp:
            p = self.visit(cdp, ms=GO_LIVE)
            state = p.js(CHIPS)["chips"]["state"]
            self.assertIn("Overdue", state["text"])
            self.assertEqual(state["icons"][0], "sDelayed", "the Delayed glyph")
            self.open_chip(p, "state")
            items = p.js(POP_ITEMS)
            over = [i for i in items if i["text"].startswith("Overdue")]
            self.assertEqual(len(over), 1, "Overdue is listed so it can be read")
            self.assertTrue(over[0]["disabled"], "but it is not pickable")
            self.assertEqual(over[0]["icons"][0], "sDelayed")
            self.assertEqual([i["text"] for i in items if not i["disabled"]], STATES)

    def test_the_forecast_chip_of_an_overdue_milestone_says_overdue_n_days_in_red(self):
        with chrome() as cdp:
            p = self.visit(cdp, ms=GO_LIVE)
            due = p.js(CHIPS)
            self.assertRegex(due["chips"]["forecast"]["sub"], r"^overdue \d+ days$")
            self.assertEqual(due["chips"]["forecast"]["subColour"], due["red"], "the sub-line is in the red token")
        with chrome() as cdp:
            p = self.visit(cdp, ms=PILOT)
            self.assertIsNone(p.js(CHIPS)["chips"]["forecast"]["sub"], "a date ahead has no sub-line")

    def test_the_forecast_chip_opens_the_calendar_and_picking_a_day_saves_it(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.open_chip(p, "forecast")
            p.until("!!document.querySelector('[data-pop] [role=grid], [data-pop] input[type=date], [data-pop] [data-day]')", "a calendar")
            p.js("document.querySelector('[data-pop] [data-day]:not([disabled])').click()")
            self.assertTrue(self.until_store(lambda: self.sent and "forecast_date" in self.sent[-1][1]["changes"]), "forecast_date was sent")
            self.assertEqual(self.sent[-1][1]["place"], "peek")

    def test_the_progress_popover_is_ten_blocks_and_a_click_sets_the_percentage(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp, width=width)
                self.assertRegex(p.js(CHIPS)["chips"]["progress"]["text"], r"^(\d+%|—|-)", "bars icon and the percentage")
                self.open_chip(p, "progress")
                blocks = p.js("[...document.querySelectorAll('[data-pop] [data-block]')].map(b => b.dataset.block)")
                self.assertEqual(blocks, [str(n) for n in range(10, 101, 10)], "ten blocks, 10% to 100%")
                p.js("document.querySelector('[data-pop] [data-block=\"40\"]').click()")
                self.saved(p, "percent_complete", 40)
                self.assertEqual(self.sent[-1][1]["changes"], {"percent_complete": 40})
                p.until("/40%/.test(document.querySelector('#peek .pk-chips [data-row=progress]').innerText)", "the chip says 40%")

    def test_the_owner_chip_changes_the_owner(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.open_chip(p, "owner")
            p.until("[...document.querySelectorAll('[data-pop] button')].some(x => /Priya Example/.test(x.textContent))", "the people list is read after the box opens")
            p.js("""(() => { const b = [...document.querySelectorAll('[data-pop] [role=menuitemradio], [data-pop] [role=option], [data-pop] button')]
                     .find(x => /Priya Example/.test(x.textContent)); b.click(); })()""")
            self.saved(p, "owner", "Priya Example")
            p.until("/Priya/.test(document.querySelector('#peek .pk-chips [data-row=owner]').innerText)", "the chip follows")

    def test_each_chip_closes_on_esc_with_focus_back_on_the_chip(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for k in CHIP_ORDER:
                with self.subTest(k):
                    self.open_chip(p, k)
                    p.key("Escape", code="Escape", vk=27)
                    p.until("!document.querySelector('[data-pop]')", f"{k}: Esc closes it")
                    p.until(f"document.activeElement === document.querySelector('#peek .pk-chips [data-row={k}] button')", f"{k}: focus returns to the chip")
                    self.assertEqual(p.js("!!document.querySelector('#peek')"), True, "the first Esc leaves the peek open")

    def test_details_rows_are_in_the_ticket_order_and_the_old_rows_are_gone(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp, width=width)
                p.js("(() => { const d = document.querySelector('[data-pk-details] .pk-details-h'); if (d && d.getAttribute('aria-expanded') !== 'true') d.click(); })()")      # the section has no aria-expanded: its button does
                self.assertEqual(p.js(LABELS), ROWS)
                for old in OLD:
                    self.assertNotIn(old, p.js(LABELS))
                self.assertEqual(p.js("document.querySelectorAll('#peek [data-pk-client-row] button[aria-pressed]').length"), 1, "the Client visible line follows the rows")
                self.assertEqual(p.js("(() => { const rows = [...document.querySelectorAll('#peek .pk-fields > .pk-row')]; const last = rows[rows.length - 1]; const a = rows[rows.length - 2].getBoundingClientRect().bottom; return last.hasAttribute('data-pk-client-row') && last.getBoundingClientRect().top >= a - 1; })()"), True)      # the line sits inside the list, as its last row

    def test_achieved_on_row_comes_with_the_achieved_state_after_agreed_date(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.js("(() => { const d = document.querySelector('[data-pk-details] .pk-details-h'); if (d && d.getAttribute('aria-expanded') !== 'true') d.click(); })()")      # the section has no aria-expanded: its button does
            self.open_chip(p, "state")
            p.js("[...document.querySelectorAll('[data-pop] [role=menuitemradio], [data-pop] [role=option], [data-pop] [role=menuitem]')].find(b => b.textContent.includes('Achieved')).click()")
            self.saved(p, "status", "Done")
            p.until("document.querySelectorAll('#peek [data-ms-field=actual_date]').length === 1", "the Achieved on row")
            self.assertEqual(p.js(LABELS), ROWS_DONE)

    def test_use_case_picks_and_clears(self):
        from clark import store as sm
        with self.store.step("dashboard", USER) as st:
            st.create("use_cases", {"project": "ABC", "title": "A new feature", "status": "On track", "source": "demo"})
            st.create("use_cases", {"project": "ABC", "title": "Badge printing", "status": "On track", "source": "demo"})
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp, width=width)
                p.js("(() => { const d = document.querySelector('[data-pk-details] .pk-details-h'); if (d && d.getAttribute('aria-expanded') !== 'true') d.click(); })()")      # the section has no aria-expanded: its button does
                row = "#peek [data-ms-row=use_cases]"
                self.assertIn("Select use case", p.js(f"document.querySelector('{row}').textContent"), "empty: the prompt")
                self.click(p, f"{row} button")
                p.until("!!document.querySelector('[data-pop]')", "the use case list")
                items = [i["text"] for i in p.js(POP_ITEMS)]
                self.assertEqual(items[0].lower().startswith(("none", "no use case")), True, "none first")
                self.assertTrue(any("A new feature" in t for t in items) and any("Badge printing" in t for t in items), items)
                p.js("[...document.querySelectorAll('[data-pop] [role=menuitemradio], [data-pop] [role=option], [data-pop] [role=menuitem]')].find(b => b.textContent.includes('A new feature')).click()")
                p.until(f"/A new feature/.test(document.querySelector('{row}').textContent)", "the row shows the pick")
                self.assertTrue(self.until_store(lambda: "msadd" in json.dumps(self.sent[-1][1])), "linked with msadd")
                self.click(p, f"{row} button")
                p.until("!!document.querySelector('[data-pop]')", "the list again")
                p.js("[...document.querySelectorAll('[data-pop] [role=menuitemradio], [data-pop] [role=option], [data-pop] [role=menuitem]')].find(b => /^(none|no use case)/i.test(b.textContent.trim())).click()")
                p.until(f"/Select use case/.test(document.querySelector('{row}').textContent)", "cleared: the prompt is back")
                self.assertTrue(self.until_store(lambda: "msremove" in json.dumps(self.sent[-1][1])), "unlinked with msremove")
            self.reset_links()

    def reset_links(self):
        """Each width starts with no link: a link left by the first width would show in the second."""
        with self.store.step("dashboard", USER) as st:
            for r in st.rows("uc_milestones") if hasattr(st, "rows") else []:
                st.delete("uc_milestones", r["id"])

    def test_client_wording_is_greyed_and_not_clickable_while_client_is_not_visible(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.js("(() => { const d = document.querySelector('[data-pk-details] .pk-details-h'); if (d && d.getAttribute('aria-expanded') !== 'true') d.click(); })()")      # the section has no aria-expanded: its button does
            line = "#peek [data-pk-client-row] button[aria-pressed]"
            row = "#peek [data-ms-row=client_message]"
            state = lambda: p.js(f"document.querySelector({json.dumps(line)}).getAttribute('aria-pressed')")
            if state() == "true":
                self.click(p, line)
                p.until(f"document.querySelector({json.dumps(line)}).getAttribute('aria-pressed') === 'false'", "Client not visible")
            self.assertIn("Client not visible", p.js(f"document.querySelector({json.dumps(line)}).textContent"))
            self.assertEqual(p.js(f"document.querySelector({json.dumps(row)}).querySelector('[data-rich]').getAttribute('aria-disabled') === 'true' || document.querySelector({json.dumps(row)}).classList.contains('off')"), True, "greyed")
            self.assertEqual(p.js(f"document.querySelector({json.dumps(row)}).textContent.includes('Add client wording')"), False, "no prompt text")
            p.js(f"document.querySelector({json.dumps(row)} + ' [data-rich]').click()")
            self.assertEqual(p.js("!!document.querySelector('#peek .ProseMirror')"), False, "not clickable")
            self.click(p, line)
            p.until(f"document.querySelector({json.dumps(line)}).getAttribute('aria-pressed') === 'true'", "Client visible")
            self.assertIn("Client visible", p.js(f"document.querySelector({json.dumps(line)}).textContent"))
            self.click(p, row + " [data-rich]")
            p.until("!!document.querySelector('#peek .ProseMirror')", "now it opens")

    def test_enter_in_description_is_a_new_line_and_ctrl_or_cmd_enter_saves_it(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.js("(() => { const d = document.querySelector('[data-pk-details] .pk-details-h'); if (d && d.getAttribute('aria-expanded') !== 'true') d.click(); })()")      # the section has no aria-expanded: its button does
            self.click(p, "#peek [data-ms-row=description] [data-rich=description]")
            p.until("!!document.querySelector('#peek .ProseMirror') && document.activeElement.classList.contains('ProseMirror')", "the editor opened with the focus")
            p.js("document.querySelector('#peek .ProseMirror').cxed.editor.commands.insertContent('First line'); true")
            p.key("Enter", code="Enter", vk=13)
            p.js("document.querySelector('#peek .ProseMirror').cxed.editor.commands.insertContent('Second line'); true")
            self.assertGreaterEqual(p.js("document.querySelectorAll('#peek .ProseMirror p').length"), 2, "a plain Enter is a new line")
            self.assertEqual(self.sent, [], "a plain Enter saves nothing")
            p.key("Enter", modifiers=4 if p.js("/Mac/.test(navigator.platform)") else 2, code="Enter", vk=13)
            self.saved(p, "description", "<p>First line</p><p>Second line</p>")
            self.assertEqual(len(self.sent), 1, "the key saves once")

    def test_the_title_rides_the_shared_frame_with_the_id_line_and_the_toolbar(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertEqual(p.js("document.querySelectorAll('#peek [role=toolbar].pk-bar').length"), 1)
            self.assertEqual(p.js("document.querySelectorAll('#peek h2.pk-title').length"), 1)
            self.assertRegex(p.js("document.querySelector('#peek').innerText"), r"ABC-M-001")

    @unittest.skip("Latest update and Draft with AI need the store change (own ticket): enable when milestones carry latest_update")
    def test_the_latest_update_box_saves_with_ctrl_or_cmd_enter_and_draft_with_ai_is_beside_the_heading(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertEqual(p.js("!!document.querySelector('#peek [data-pk-latest]')"), True)
            self.assertIn("Draft with AI", p.js("document.querySelector('#peek [data-pk-latest]').innerText"))
            self.assertRegex(p.js("document.querySelector('#peek [data-pk-hint]').textContent"), r"(Ctrl|Cmd|⌘).{0,3}Enter")


class ReadOnly(Base):
    """A client's peek (the Dashboard in View): the same four chips, no control."""

    def test_the_dashboard_in_view_shows_the_chips_without_controls_and_no_use_case_or_client_visible_line(self):
        with chrome() as cdp:
            from test_report_editor import Pg
            p = Pg.at(self, cdp, self.s.port, f"#dashboard&p=ABC&ms={PILOT}&view=1")
            p.until("!!document.querySelector('#peek .pk-chips')", "the peek drew its chips")
            got = p.js(CHIPS)
            self.assertEqual(got["order"][0:1], ["state"])
            self.assertEqual(p.js("document.querySelectorAll('#peek .pk-chips button').length"), 0, "no control")
            self.assertEqual(p.js("document.querySelectorAll('#peek [data-pk-client-row]').length"), 0, "the Client visible line is the editor's")
            self.assertNotIn("Use case", p.js(LABELS))


if __name__ == "__main__":
    unittest.main()
