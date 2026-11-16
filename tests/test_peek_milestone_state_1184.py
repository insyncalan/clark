"""Row 1184: the State chip of the Milestone peek (the approved redesign, peek-milestone.png). The shared frame is item 1180 and the Action's chips are item 1181
(test_peek_action_1181.py, whose structure this file copies); this file covers the State chip alone: its five pickable values with their own icons, Forecast
the plain dashed circle, Overdue worked out from the dates, drawn red and not a choice, and a pick setting the state in one change with one Undo.
Written ahead of the build: it is the State half of the milestone peek's browser tests and is merged with the builder's branch later.
Run: python3 dev/run_tests.py test_peek_milestone_state_1184

Real browser at 1400 and 900 px on the fictional demo project, Edit mode. ABC-M-001 (PILOT) is Planned and far ahead, so the dates say On track;
ABC-M-002 (GO_LIVE) has an agreed date long past, so the dates say Overdue. Hooks used (the 1180 frame and the build's own): #peek .pk-chips [data-row=state],
svg[data-icn], [data-pop], [data-ms-state=<word>] (a button of the popover), aria-pressed on the state shown.
"""
import json
import time
import unittest

from _demo import USER
from _paths import SRC

from test_movement_page import GO_LIVE, PILOT, Base  # noqa: E402
from test_server import chrome  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
CHIP = "#peek .pk-chips [data-row=state]"
PICKABLE = ["Forecast", "On track", "At risk", "Slipped", "Achieved"]
ORDER = ["Forecast", "On track", "At risk", "Slipped", "Overdue", "Achieved"]       # the popover's order: the five and Overdue (drawn, not a choice)
ICON = {"Forecast": "sForecast", "On track": "sTrack", "At risk": "sRisk", "Slipped": "sSlip", "Overdue": "sOver", "Achieved": "sClosed"}
TONE = {"Forecast": "ic-n", "On track": "ic-g", "At risk": "ic-a", "Slipped": "ic-r", "Overdue": "ic-r", "Achieved": "ic-g"}      # grey, green, amber, red, red, green
COLOUR_OF = "((cls) => { const e = document.createElement('i'); e.className = cls; document.body.appendChild(e); const c = getComputedStyle(e).color; e.remove(); return c; })"
CHIP_STATE = ("(() => { const c = document.querySelector('%s'); const b = c.querySelector('button') || c; const s = c.querySelector('svg[data-icn]'); const w = c.querySelector('.pkc-ic');"
              " const k = c.cloneNode(true); k.querySelectorAll('[data-pop]').forEach(x => x.remove());"
              " return { text: k.innerText.replace(/\\s+/g, ' ').trim(), icon: s ? s.dataset.icn : null, colour: w ? getComputedStyle(w).color : null, tag: b.tagName, h: b.getBoundingClientRect().height,"
              " w: b.getBoundingClientRect().width }; })()" % CHIP)
POP_STATES = ("Object.fromEntries([...document.querySelectorAll('[data-pop] [data-ms-state]')].map(b => [b.dataset.msState, { icon: (b.querySelector('svg') || {dataset: {}}).dataset.icn,"
              " off: b.disabled, pressed: b.getAttribute('aria-pressed'), h: b.getBoundingClientRect().height, dash: !!b.querySelector('svg [stroke-dasharray]'),"
              " colour: b.querySelector('.pkc-ic') ? getComputedStyle(b.querySelector('.pkc-ic')).color : null,"
              " dasharray: b.querySelector('svg [stroke-dasharray]') ? getComputedStyle(b.querySelector('svg [stroke-dasharray]')).strokeDasharray : null }]))")
POP_ORDER = "[...document.querySelectorAll('[data-pop] [data-ms-state]')].map(b => b.dataset.msState)"
POP_BOX = "(() => { const r = document.querySelector('[data-pop]').getBoundingClientRect(); return { l: r.left, t: r.top, r: r.right, b: r.bottom, w: innerWidth, h: innerHeight }; })()"


class State(Base):
    cur = PILOT

    def visit(self, cdp, ms=PILOT, width=1400):
        from test_report_editor import Pg
        self.cur = ms
        p = Pg.at(self, cdp, self.s.port, f"#milestones&p=ABC&ms={ms}")
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.until("!!document.querySelector('#peek .pk-chips [data-row=state]')", "the peek drew its State chip")
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

    def saved(self, field, value, ms=None):
        ms = ms or self.cur
        self.assertTrue(self.until_store(lambda: self.row(ms)[field] == value), f"{field} was not saved as {value!r}: {self.row(ms)[field]!r}")

    def real_click(self, cdp, p, sel):
        """A press with the mouse, as a person makes it (a disabled button takes no press; a script's own click event is not that)."""
        box = p.js(f"(() => {{ const r = document.querySelector({json.dumps(sel)}).getBoundingClientRect(); return {{ x: r.left + r.width / 2, y: r.top + r.height / 2 }}; }})()")
        for kind in ("mouseMoved", "mousePressed", "mouseReleased"):
            cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": box["x"], "y": box["y"], "button": "left", "buttons": 1 if kind == "mousePressed" else 0, "clickCount": 1}, p.sid)

    def open_state(self, p):
        self.click(p, f"{CHIP} button")
        p.until("!!document.querySelector('[data-pop] [data-ms-state]')", "the State popover opened")

    def chip(self, p):
        return p.js(CHIP_STATE)

    def states_sent(self):
        return [r for which, r in self.sent if "state" in (r.get("changes") or {})]

    def undo(self, p):
        p.until("!!document.querySelector('.toast [data-undo]')", "the Undo button")
        p.js("document.querySelector('.toast [data-undo]').click()")

    def test_the_state_chip_is_the_first_chip_a_control_with_its_own_icon(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp, width=width)
                self.assertEqual(p.js("document.querySelector('#peek .pk-chips > [data-row]').dataset.row"), "state", "State comes first")
                got = self.chip(p)
                self.assertEqual((got["text"], got["icon"], got["tag"]), ("On track", "sTrack", "BUTTON"), "the dates say On track: its word and its own icon, a control in Edit")
                self.assertGreaterEqual(got["h"], 24, "a 24 px target")
                self.assertIn("State", p.js("(document.querySelector('%s button') || document.querySelector('%s')).getAttribute('aria-label') || ''" % (CHIP, CHIP)), "the chip is named State")

    def test_the_popover_offers_five_pickable_values_and_overdue_in_the_one_order(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp, width=width)
                self.open_state(p)
                self.assertEqual(p.js(POP_ORDER), ORDER)
                got = p.js(POP_STATES)
                self.assertEqual([k for k, v in got.items() if not v["off"]], PICKABLE, "five values can be picked")
                self.assertEqual([k for k, v in got.items() if v["off"]], ["Overdue"], "Overdue is the only one that cannot")
                for word, v in got.items():
                    self.assertGreaterEqual(v["h"], 24, f"{word}: a 24 px target")

    def test_each_value_has_its_own_icon_and_no_two_are_alike(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp, width=width)
                self.open_state(p)
                got = p.js(POP_STATES)
                self.assertEqual({k: v["icon"] for k, v in got.items()}, ICON)
                self.assertEqual(len(set(v["icon"] for v in got.values())), 6, "six icons, none shared")

    def test_forecast_is_the_plain_dashed_circle_and_no_other_value_is_dashed(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp, width=width)
                self.open_state(p)
                got = p.js(POP_STATES)
                self.assertTrue(got["Forecast"]["dash"], "Forecast carries a dash pattern")
                self.assertEqual([k for k, v in got.items() if v["dash"]], ["Forecast"], "the others are drawn solid")
                self.assertNotIn(got["Forecast"]["dasharray"], (None, "none"), "the dashes are drawn, not only written")
                self.assertEqual(p.js("document.querySelectorAll('[data-pop] [data-ms-state=Forecast] svg circle').length"), 1, "a circle")
                self.assertEqual(p.js("document.querySelectorAll('[data-pop] [data-ms-state=Forecast] svg *:not(circle)').length"), 0, "plain: nothing inside it")

    def test_the_icon_colours_are_grey_green_amber_red_red_green(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.open_state(p)
            got = p.js(POP_STATES)
            for word, tone in TONE.items():
                self.assertEqual(got[word]["colour"], p.js(f"{COLOUR_OF}({json.dumps(tone)})"), f"{word}: {tone}")
            self.assertNotEqual(got["Forecast"]["colour"], p.js(f"{COLOUR_OF}('ic-b')"), "Forecast is grey, not the Milestones page's blue")
            self.assertEqual(len({got["On track"]["colour"], got["At risk"]["colour"], got["Slipped"]["colour"], got["Forecast"]["colour"]}), 4, "four colours tell the four apart")

    def test_the_value_shown_is_marked_pressed_and_only_that_one(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.open_state(p)
            got = p.js(POP_STATES)
            self.assertEqual([k for k, v in got.items() if v["pressed"] == "true"], ["On track"])

    def test_the_popover_sits_inside_the_window(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp, width=width)
                self.open_state(p)
                box = p.js(POP_BOX)
                self.assertGreaterEqual(box["l"], 0)
                self.assertGreaterEqual(box["t"], 0)
                self.assertLessEqual(box["r"], box["w"])
                self.assertLessEqual(box["b"], box["h"])
                self.assertEqual(p.js("document.documentElement.scrollWidth <= innerWidth"), True, "no sideways scroll")

    def test_picking_each_of_the_five_sets_the_state_and_the_chip_shows_it(self):
        for width in (1400, 900):
            for word in PICKABLE:
                with self.subTest(width=width, state=word), chrome() as cdp:
                    ms = PILOT
                    p = self.visit(cdp, ms=ms, width=width)
                    self.open_state(p)
                    n = len(self.sent)
                    self.click(p, f"[data-pop] [data-ms-state={json.dumps(word)}]".replace('"', "'"))
                    self.saved("state", word)
                    self.assertEqual(len(self.sent) - n, 1, "one request")
                    sent = self.sent[-1][1]
                    self.assertEqual(sent["changes"]["state"], word)
                    self.assertEqual(sent["changes"]["state_set"], 1)
                    p.until(f"document.querySelector('{CHIP}').innerText.trim() === {json.dumps(word)}", f"the chip says {word}: " + str(self.chip(p)))
                    got = self.chip(p)
                    self.assertEqual(got["icon"], ICON[word], "and carries its icon")
                    self.assertEqual(got["colour"], p.js(f"{COLOUR_OF}({json.dumps(TONE[word])})"), "in its colour")
                    p.until("!document.querySelector('[data-pop]')", "a pick closes the popover")
                    row = self.row(ms)
                    if word == "Achieved":
                        self.assertEqual((row["status"], row["percent_complete"]), ("Done", 100), "Achieved is Done at 100%")
                    else:
                        self.assertEqual(row["status"], "Planned", "any other value leaves it open")

    def test_a_pick_is_one_change_with_one_undo_and_says_so_in_a_toast(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.open_state(p)
            self.click(p, "[data-pop] [data-ms-state='At risk']")
            self.saved("state", "At risk")
            p.until(f"/^State of {PILOT} changed to At risk\\.$/.test((document.querySelector('.toast .toast-text') || {{}}).textContent || '')", "the toast")
            self.undo(p)
            self.saved("state", None)
            self.assertEqual(self.row(PILOT)["state_set"], 0, "back to what the dates say")
            p.until(f"document.querySelector('{CHIP}').innerText.trim() === 'On track'", "the chip is back to On track")

    def test_pressing_a_value_set_by_hand_again_hands_the_state_back_to_the_dates(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.open_state(p)
            self.click(p, "[data-pop] [data-ms-state='At risk']")
            self.saved("state", "At risk")
            p.until("!document.querySelector('[data-pop]')", "closed")
            self.open_state(p)
            self.click(p, "[data-pop] [data-ms-state='At risk']")          # the value set by hand, pressed again: the dates decide again (msPeek.js stateChange)
            self.saved("state", None)
            p.until(f"document.querySelector('{CHIP}').innerText.trim() === 'On track'", "the dates decide again")

    def test_leaving_the_popover_without_a_pick_changes_nothing(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            was = dict(self.row(PILOT))
            self.open_state(p)
            n = len(self.sent)
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('[data-pop]')", "Esc closed the popover")
            self.assertEqual(len(self.sent), n, "nothing was sent")
            row = self.row(PILOT)
            self.assertEqual((row["state"], row["state_set"], row["status"]), (was["state"], was["state_set"], was["status"]))

    def test_overdue_is_worked_out_from_the_dates_shown_red_with_its_own_icon(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp, ms=GO_LIVE, width=width)        # the agreed date is long past and no state was set by hand
                self.assertEqual(self.row(GO_LIVE)["state"], None, "nothing is stored: it is worked out")
                got = self.chip(p)
                self.assertEqual((got["text"], got["icon"]), ("Overdue", "sOver"))
                self.assertEqual(got["colour"], p.js(f"{COLOUR_OF}('ic-r')"), "red")
                self.open_state(p)
                pop = p.js(POP_STATES)
                self.assertEqual(pop["Overdue"]["pressed"], "true", "the popover marks Overdue as the one shown")
                self.assertEqual(pop["Overdue"]["icon"], "sOver")
                self.assertEqual(pop["Overdue"]["colour"], p.js(f"{COLOUR_OF}('ic-r')"))

    def test_overdue_cannot_be_picked_and_pressing_it_changes_nothing(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp, ms=GO_LIVE, width=width)
                self.open_state(p)
                self.assertEqual(p.js("document.querySelector('[data-pop] [data-ms-state=Overdue]').disabled"), True)
                n = len(self.sent)
                self.real_click(cdp, p, "[data-pop] [data-ms-state=Overdue]")
                p.js("document.querySelector('[data-pop] [data-ms-state=Overdue]').click()")
                time.sleep(0.5)
                self.assertEqual(p.js("!!document.querySelector('[data-pop]')"), True, "the press did not close the popover either")
                self.assertEqual(len(self.sent), n, "nothing was sent")
                self.assertEqual(self.row(GO_LIVE)["state"], None)
                self.assertEqual(self.chip(p)["text"], "Overdue")
                self.assertEqual(self.states_sent(), [])

    def test_a_milestone_that_is_on_track_by_the_dates_does_not_offer_overdue_as_its_state(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.open_state(p)
            got = p.js(POP_STATES)
            self.assertEqual(got["Overdue"]["pressed"], "false")
            self.assertEqual(self.chip(p)["icon"], "sTrack")

    def test_forecast_picked_on_an_overdue_milestone_replaces_overdue_and_undo_gives_it_back(self):
        """Forecast and Achieved need no reason (store.check_milestone), so they are the two picks that always save on an Overdue milestone."""
        with chrome() as cdp:
            p = self.visit(cdp, ms=GO_LIVE)
            self.open_state(p)
            self.click(p, "[data-pop] [data-ms-state=Forecast]")
            self.saved("state", "Forecast", ms=GO_LIVE)
            p.until(f"document.querySelector('{CHIP}').innerText.trim() === 'Forecast'", "Forecast is shown instead of Overdue")
            self.assertEqual(self.chip(p)["icon"], "sForecast")
            self.undo(p)
            self.saved("state", None, ms=GO_LIVE)
            p.until(f"document.querySelector('{CHIP}').innerText.trim() === 'Overdue'", "Overdue is worked out again")

    def test_a_pick_better_than_the_dates_on_an_overdue_milestone_is_refused_in_words_and_nothing_changes(self):
        """clark's own rule (store.check_milestone, changes.STATE_NEEDS_REASON): On track, At risk or Slipped on an Overdue milestone needs a one-line reason.
        The chip's popover has no place for one, so the pick is refused (a problem toast), the state stays Overdue and no Undo is offered. The toast's sentence is not asserted: today it is the generic
        'could not be made' one, not STATE_NEEDS_REASON (see the findings file)."""
        for word in ("On track", "At risk", "Slipped"):
            with self.subTest(state=word), chrome() as cdp:
                p = self.visit(cdp, ms=GO_LIVE)
                self.open_state(p)
                self.click(p, f"[data-pop] [data-ms-state='{word}']")
                p.until("!!document.querySelector('.toast[data-kind=problem]')", "the refusal is said in a problem toast: " + word)
                self.assertEqual((self.row(GO_LIVE)["state"], self.row(GO_LIVE)["state_set"]), (None, 0), "nothing was stored")
                self.assertEqual(p.js("!!document.querySelector('.toast [data-undo]')"), False, "nothing to undo")
                p.until(f"document.querySelector('{CHIP}').innerText.trim() === 'Overdue'", "the chip still says Overdue")

    def test_the_chip_row_in_view_shows_the_state_with_its_icon_and_no_control(self):
        with self.store.step("dashboard", USER) as st:
            st.update("milestones", PILOT, {"state": "At risk", "state_set": 1})
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                from test_report_editor import Pg
                p = Pg.at(self, cdp, self.s.port, f"#dashboard&p=ABC&ms={PILOT}")
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.until("!!document.querySelector('#peek .pk-chips [data-row=state]')", "the chip")
                got = self.chip(p)
                self.assertEqual((got["text"], got["icon"]), ("At risk", "sRisk"), "the word and its icon")
                self.assertEqual(p.js("document.querySelectorAll('#peek .pk-chips button').length"), 0, "drawn and not a control")


class Source(unittest.TestCase):
    def test_the_five_state_icons_and_overdue_are_in_the_icon_sprite_with_forecast_dashed(self):
        icons = (PAGE_SRC / "components" / "Icon.jsx").read_text(encoding="utf-8")
        for name in ICON.values():
            self.assertIn(f"{name}:", icons, name)
        line = next(l for l in icons.splitlines() if l.strip().startswith("sForecast:"))
        self.assertIn("stroke-dasharray", line)
        for name in ("sTrack", "sRisk", "sSlip", "sOver", "sClosed"):
            self.assertNotIn("stroke-dasharray", next(l for l in icons.splitlines() if l.strip().startswith(f"{name}:")), name)

    def test_overdue_is_not_in_the_list_of_pickable_values(self):
        src = (PAGE_SRC / "edit" / "msPeek.js").read_text(encoding="utf-8")
        line = next(l for l in src.splitlines() if l.startswith("export const PICKABLE"))
        self.assertNotIn("Overdue", line)
        for word in PICKABLE:
            self.assertIn(f'"{word}"', line)


if __name__ == "__main__":
    unittest.main()
