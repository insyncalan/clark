"""Row 1270: what the approved mock-up gives for a RAID card that opens the Peek. The label over the description, the whole card as the click
target, the hover / focus / selected states, light and dark contrast of the edge, band and ink, focus returning to the card, and a read-only Peek
in the published file. Words are the mock-up's own (The risk, The issue, The action, The decision needed, The decision; "Open <ID> details").

Run: python3 dev/run_tests.py test_raid_cards_states_1270
Fictional rows. Opened in headless Chrome at 1400 and 900 (the only widths checked).
"""
import json
import unittest

from _demo import USER
from _publish import PublishedFile
import test_glance_page as glance
from test_server import chrome, wait

CARDS = """(() => [...document.querySelectorAll('.raid-card')].map(c => { const b = c.querySelector('.raid-id'), l = c.querySelector('.raid-part');
  return { id: b.textContent, label: l ? l.textContent : null, aria: b.getAttribute('aria-label'), popup: b.getAttribute('aria-haspopup'), cls: c.className }; }))()"""
STATE = """(() => { const p = document.querySelector('#peek'); const a = document.activeElement;
  return { open: !!p && !p.hidden && p.getBoundingClientRect().width > 0, active: a ? a.className + ':' + a.textContent : '',
           editable: p ? p.querySelectorAll('input, textarea, select, [contenteditable=true], .pk-ce, .pk-title-in').length : -1 }; })()"""
ESC = "document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))"
# relative luminance and contrast of two css colours as the browser computes them
LUM = """const lum = (s) => { const m = s.match(/[\\d.]+/g).map(Number); const f = (v) => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); };
  return .2126 * f(m[0]) + .7152 * f(m[1]) + .0722 * f(m[2]); };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };"""
PAIRS = "(() => { " + LUM + """ return [...document.querySelectorAll('.raid-card')].map(c => { const cs = getComputedStyle(c), top = getComputedStyle(c.querySelector('.raid-top')), surf = cs.backgroundColor;
  const kind = c.querySelector('.raid-kind');
  return { cls: c.className, edge: ratio(cs.borderTopColor, surf), ink: ratio(top.color, top.backgroundColor), edgeColour: cs.borderTopColor, band: top.backgroundColor }; }); })()"""


class RaidCardStates(PublishedFile, glance.Setup):
    def seed(self):
        self.demo.plant_builtin_sections()      # the cards are drawn beside the built-in sections (row 1193)
        ids = []
        with self.store.step("dashboard", USER) as st:
            ids.append(st.create("raid", {"project": "ABC", "type": "Risk", "description": "Kiln roof may leak", "raised": "2026-10-01", "source": "demo", "priority": "High", "impact": "High", "likelihood": "High", "owner": "Pat"}))
            ids.append(st.create("raid", {"project": "ABC", "type": "Issue", "description": "Crane down", "raised": "2026-10-01", "source": "demo", "priority": "Medium", "impact": "Low", "likelihood": "Low"}))
            ids.append(st.create("raid", {"project": "ABC", "type": "Risk", "description": "Tide table", "raised": "2026-10-01", "source": "demo", "priority": "Low"}))
            ids.append(st.create("raid", {"project": "ABC", "type": "Risk", "description": "No rating here", "raised": "2026-10-01", "source": "demo"}))
            ids.append(st.create("actions", {"project": "ABC", "description": "Book the crane", "owner": "Pat", "due_date": "2026-12-01", "raised": "2026-10-01", "source": "demo"}))
            ids.append(st.create("decisions", {"project": "ABC", "decision": "Pick the kiln supplier", "source": "demo", "status": "Pending", "needed_by": "2026-12-01", "made_by": "Pat"}))
            ids.append(st.create("decisions", {"project": "ABC", "decision": "Use the north gate", "source": "demo", "status": "Made", "date": "2026-10-02", "made_by": "Pat"}))
            ref = st.create("report_sections", {"project": "ABC", "type": "raid4", "title": "Fictional cards", "sort_order": 993})
            st.update("report_sections", ref, {"body": json.dumps({"v": 2, "across": 4, "cards": [{"id": i} for i in ids]})})
        return ids

    def test_the_label_over_the_description_and_the_open_button_words(self):
        ids = self.seed()
        path = self.publish()
        with chrome() as cdp:
            for w in (1400, 900):
                cs = self.draw(cdp, path, width=w).js(CARDS)
                self.assertEqual([c["label"] for c in cs], ["The risk", "The issue", "The risk", "The risk", "The action", "The decision needed", "The decision"], w)
                self.assertEqual([c["aria"] for c in cs], ["Open %s details" % i for i in ids], w)
                self.assertEqual({c["popup"] for c in cs}, {"dialog"}, w)

    def test_the_whole_card_is_the_click_target_and_the_states_are_drawn(self):
        ids = self.seed()
        path = self.publish()
        with chrome() as cdp:
            for w in (1400, 900):
                p = self.draw(cdp, path, width=w)
                # a point inside the card, away from the ID, reaches the ID button (its stretched ::after)
                p.js("document.querySelector('.raid-card').scrollIntoView({block: 'center'})")
                hit = p.js("""(() => { const c = document.querySelector('.raid-card'), r = c.getBoundingClientRect(); const e = document.elementFromPoint(r.left + r.width / 2, r.top + r.height - 8);
                  return e ? e.closest('.raid-id') ? 'id' : e.className : 'none'; })()""")
                self.assertEqual(hit, "id", "the card body is the ID button at %d" % w)
                rest = p.js("(() => { const s = getComputedStyle(document.querySelector('.raid-card')); return { shadow: s.boxShadow, outline: s.outlineStyle, left: s.borderLeftColor }; })()")
                self.assertEqual(rest["outline"], "none", "no ring at rest")
                # keyboard focus on the ID button: a 2 px ring on the whole card, offset 2 px, none on the button
                p.js("document.querySelector('.raid-card .raid-id').focus()")
                f = p.js("""(() => { const c = document.querySelector('.raid-card'), s = getComputedStyle(c), b = getComputedStyle(c.querySelector('.raid-id')); const root = getComputedStyle(document.documentElement);
                  return { w: s.outlineWidth, st: s.outlineStyle, off: s.outlineOffset, col: s.outlineColor, btn: b.outlineStyle, focus: root.getPropertyValue('--focus').trim(), probe: (() => { const d = document.createElement('i'); d.style.color = 'var(--focus)'; document.body.append(d); const c2 = getComputedStyle(d).color; d.remove(); return c2; })() }; })()""")
                self.assertEqual((f["w"], f["st"], f["off"], f["btn"]), ("2px", "solid", "2px", "none"), f)
                self.assertEqual(f["col"], f["probe"], "the ring is the focus colour")
                # press the card away from its ID: the Peek opens and that card is the selected one, a 2 px brand-blue ring
                p.js("document.querySelector('.raid-card .raid-id').blur()")
                p.js("document.querySelector('.raid-card .raid-id').click()")
                self.assertTrue(wait(lambda: p.js(STATE)["open"]), "the peek opens at %d" % w)
                sel = p.js("""(() => { const probe = (() => { const d = document.createElement('i'); d.style.color = 'var(--brand-blue)'; document.body.append(d); const c = getComputedStyle(d).color; d.remove(); return c; })();
                  return { sel: [...document.querySelectorAll('.raid-card')].map(c => c.classList.contains('rc-sel')), shadow: getComputedStyle(document.querySelector('.raid-card.rc-sel')).boxShadow, probe }; })()""")
                self.assertEqual(sel["sel"], [True] + [False] * (len(ids) - 1), w)
                self.assertIn("0px 0px 0px 2px", sel["shadow"]); self.assertIn(sel["probe"], sel["shadow"], "brand blue")

    def test_hover_shadow_edge_and_underline(self):
        self.seed()
        path = self.publish()
        with chrome() as cdp:
            p = self.draw(cdp, path, width=1400)
            p.js("document.querySelector('.raid-card').scrollIntoView({block: 'center'})")
            r = p.js("(() => { const r = document.querySelector('.raid-card').getBoundingClientRect(); return [r.left + 20, r.top + r.height - 10]; })()")
            before = p.js("(() => { const s = getComputedStyle(document.querySelector('.raid-card')); return { sh: s.boxShadow, top: s.borderTopColor, left: s.borderLeftColor }; })()")
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": r[0], "y": r[1]}, p.sid)
            self.assertTrue(wait(lambda: p.js("getComputedStyle(document.querySelector('.raid-card')).boxShadow") != before["sh"]), "a shadow on hover")
            after = p.js("""(() => { const s = getComputedStyle(document.querySelector('.raid-card')); const g = (() => { const d = document.createElement('i'); d.style.color = 'var(--grey-500)'; document.body.append(d); const c = getComputedStyle(d).color; d.remove(); return c; })();
              return { top: s.borderTopColor, left: s.borderLeftColor, bottom: s.borderBottomColor, grey: g, ul: getComputedStyle(document.querySelector('.raid-card .raid-id')).textDecorationLine }; })()""")
            self.assertEqual((after["left"], after["bottom"]), (after["grey"], after["grey"]), "the plain edges go grey-500")
            self.assertEqual(after["top"], before["top"], "the rating edge stays")
            self.assertEqual(after["ul"], "underline", "the ID is underlined")

    def test_focus_hover_and_selected_states_are_drawn_in_dark_at_both_widths(self):
        ids = self.seed()
        path = self.publish()
        PROBE = """(v) => { const d = document.createElement('i'); d.style.color = 'var(' + v + ')'; document.body.append(d); const c = getComputedStyle(d).color; d.remove(); return c; }"""
        with chrome() as cdp:
            for w in (1400, 900):
                p = self.draw(cdp, path, width=w, dark=True)
                p.js("document.querySelector('.raid-card').scrollIntoView({block: 'center'})")
                rest = p.js("(() => { const s = getComputedStyle(document.querySelector('.raid-card')); return { sh: s.boxShadow, left: s.borderLeftColor, out: s.outlineStyle }; })()")
                self.assertEqual(rest["out"], "none", "no ring at rest")
                p.js("document.querySelector('.raid-card .raid-id').focus()")
                f = p.js("(() => { const probe = %s; const s = getComputedStyle(document.querySelector('.raid-card')); return { w: s.outlineWidth, st: s.outlineStyle, off: s.outlineOffset, col: s.outlineColor, focus: probe('--focus') }; })()" % PROBE)
                self.assertEqual((f["w"], f["st"], f["off"]), ("2px", "solid", "2px"), f)
                self.assertEqual(f["col"], f["focus"], "dark: the ring is the focus colour")
                p.js("document.querySelector('.raid-card .raid-id').blur()")
                r = p.js("(() => { const r = document.querySelector('.raid-card').getBoundingClientRect(); return [r.left + 20, r.top + r.height - 10]; })()")
                cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": r[0], "y": r[1]}, p.sid)
                self.assertTrue(wait(lambda: p.js("getComputedStyle(document.querySelector('.raid-card')).boxShadow") != rest["sh"]), "dark: a shadow on hover at %d" % w)
                hov = p.js("(() => { const probe = %s; const s = getComputedStyle(document.querySelector('.raid-card')); return { left: s.borderLeftColor, grey: probe('--grey-500'), ul: getComputedStyle(document.querySelector('.raid-card .raid-id')).textDecorationLine }; })()" % PROBE)
                self.assertEqual(hov["left"], hov["grey"], "dark: the plain edges go grey-500")
                self.assertEqual(hov["ul"], "underline", "dark: the ID is underlined")
                cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 2, "y": 2}, p.sid)
                p.js("document.querySelector('.raid-card .raid-id').focus()")      # a pointer press leaves the button focused
                p.js("document.querySelector('.raid-card .raid-id').click()")
                self.assertTrue(wait(lambda: p.js(STATE)["open"]), "the peek opens at %d" % w)
                sel = p.js("(() => { const probe = %s; return { sel: [...document.querySelectorAll('.raid-card')].map(c => c.classList.contains('rc-sel')), shadow: getComputedStyle(document.querySelector('.raid-card.rc-sel')).boxShadow, blue: probe('--brand-blue') }; })()" % PROBE)
                self.assertEqual(sel["sel"], [True] + [False] * (len(ids) - 1), w)
                self.assertIn("0px 0px 0px 2px", sel["shadow"]); self.assertIn(sel["blue"], sel["shadow"], "dark: brand blue ring")
                p.js(ESC)
                self.assertTrue(wait(lambda: not p.js(STATE)["open"]), "Esc closes it at %d" % w)
                self.assertTrue(wait(lambda: p.js(STATE)["active"].startswith("idl raid-id:")), "dark: focus is back on the card's ID button at %d" % w)

    def test_edge_band_and_ink_contrast_light_and_dark(self):
        self.seed()
        path = self.publish()
        with chrome() as cdp:
            seen = {}
            for dark in (False, True):
                for w in (1400, 900):
                    p = self.draw(cdp, path, width=w, dark=dark)
                    rows = p.js(PAIRS)
                    seen.setdefault(dark, rows)
                    for r in rows:
                        self.assertGreaterEqual(r["edge"], 3, "edge against the card, dark=%s %s: %s" % (dark, w, r))
                        self.assertGreaterEqual(r["ink"], 4.5, "band text, dark=%s %s: %s" % (dark, w, r))
            self.assertNotEqual([r["edgeColour"] for r in seen[False]], [r["edgeColour"] for r in seen[True]], "dark has its own edge colours")
            self.assertNotEqual([r["band"] for r in seen[False]], [r["band"] for r in seen[True]], "dark has its own bands")

    def test_text_and_focus_contrast_light_and_dark_match_the_mock_up_tokens(self):
        """The mock-up's pairs (NOTES.md, Contrast): the title is heading, the label, kind and foot are text-muted, the description and update are text, all on
        the card surface at 4.5; the focus ring on the surface at 3. The live colours are read from the browser."""
        self.seed()
        with self.store.step("dashboard", USER) as st:
            for r in self.store.read("raid", "ABC"):
                st.update("raid", r["id"], {"latest_update": "Survey booked.", "client_message": "Words."})
        path = self.publish()
        read = "(() => { " + LUM + """ const tok = (v) => { const d = document.createElement('i'); d.style.color = 'var(' + v + ')'; document.body.append(d); const c = getComputedStyle(d).color; d.remove(); return c; };
          const c = document.querySelector('.raid-card'), surf = getComputedStyle(c).backgroundColor, col = (s) => getComputedStyle(c.querySelector(s)).color;
          return { surf, surfTok: tok('--surface'), pairs: { title: [col('.raid-title'), tok('--heading')], label: [col('.raid-label'), tok('--text-muted')], foot: [col('.raid-meta'), tok('--text-muted')],
            latest: [col('.raid-latest'), tok('--text')] }, ratios: { title: ratio(col('.raid-title'), surf), label: ratio(col('.raid-label'), surf), foot: ratio(col('.raid-meta'), surf), latest: ratio(col('.raid-latest'), surf), focus: ratio(tok('--focus'), surf) } }; })()"""
        with chrome() as cdp:
            for w, dark in ((1400, False), (900, False), (1400, True), (900, True)):
                got = self.draw(cdp, path, width=w, dark=dark).js(read)
                self.assertEqual(got["surf"], got["surfTok"], "the card is on the surface token")
                for name, (live, token) in got["pairs"].items():
                    self.assertEqual(live, token, "%s uses the mock-up token at %d dark=%s" % (name, w, dark))
                    self.assertGreaterEqual(got["ratios"][name], 4.5, "%s on the card at %d dark=%s: %s" % (name, w, dark, got["ratios"]))
                self.assertGreaterEqual(got["ratios"]["focus"], 3, "the focus ring on the card at %d dark=%s" % (w, dark))

    def test_esc_returns_focus_to_the_card_and_the_file_peek_is_read_only(self):
        self.seed()
        path = self.publish()
        with chrome() as cdp:
            for w in (1400, 900):
                p = self.draw(cdp, path, width=w)
                p.js("document.querySelector('.raid-card .raid-id').focus()")      # a pointer press or Enter leaves the button focused
                p.js("document.querySelector('.raid-card .raid-id').click()")
                self.assertTrue(wait(lambda: p.js(STATE)["open"]), "the peek opens at %d" % w)
                self.assertEqual(p.js(STATE)["editable"], 0, "nothing in a published file's peek can be edited at %d" % w)
                p.js(ESC)
                self.assertTrue(wait(lambda: not p.js(STATE)["open"]), "Esc closes it at %d" % w)
                self.assertTrue(wait(lambda: p.js(STATE)["active"].startswith("idl raid-id:")), "focus is back on the card's ID button at %d: %s" % (w, p.js(STATE)))
