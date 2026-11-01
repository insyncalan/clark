"""The AI in the editor, against a FAKE provider (nothing is sent anywhere, nobody is signed in).

Run: python3 dev/run_tests.py test_ai_editor
The real RichText (src/clark/page/src/edit/RichText.jsx) with the AI attached (edit/editorAi.jsx) on a bare page in headless Chrome
(tests/_ai_editor_page.py). Checked against the AI menu design note (docs/handoff, keyboard and focus section) and the Done-when list for the editor:
the bubble's AI zone on any chosen text, the toolbar's AI button and Alt+/ opening the same list (on the whole field when nothing is
chosen), one test per key (Alt+/, arrows, Enter, Esc, Tab), the bubble and the list inside the window at 1400 and 900 px in light and
dark, nothing changed before Accept, Accept as ONE editor step (Cmd+Z undoes it), and Make into: one new item in one step with Undo,
no AI call. Make into's request is also run through the real change code on a real (temporary) store.
"""
import json
import unittest

from _ai_editor_page import AiEditorHarness
from _demo import USER, DemoStore
from clark import changes
from test_server import chrome

TEXT = "The supplier confirmed the delivery for Friday and asked us to keep the room booked until then."
SHORT = "The supplier confirmed the delivery for."          # the fake provider's default reply to TEXT
TWO = "<p>First note about the room.</p><p>Second note about the supplier.</p>"
CURRENT_NAMES = ["Rewrite clearly", "Shorter", "Longer", "Make it executive", "Add headings and bold", "Summarise at the top"]
MAKE_NAMES = ["Make this an action", "Make this a risk", "Make this a decision"]
NOT_SIGNED_IN = "Connect Claude in Settings to use this."

CONTRAST = """(()=>{
  const lum=(c)=>{const m=c.match(/[\\d.]+/g).map(Number).slice(0,3).map(v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4);});return .2126*m[0]+.7152*m[1]+.0722*m[2];};
  const e=document.querySelector(%s), fg=getComputedStyle(e).color, bg=getComputedStyle(document.querySelector('.rt-ai-list')).backgroundColor;
  const a=lum(fg), b=lum(bg); return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
})()"""
INSIDE = """(()=>{const e=document.querySelector(%s); if(!e) return false; const r=e.getBoundingClientRect();
  return r.left>=0 && r.top>=0 && r.right<=window.innerWidth && r.bottom<=window.innerHeight;})()"""
EDITOR = "document.querySelector('.rt .ProseMirror')"


class EditorTests:
    """Every test below runs four times: 1400 and 900 px wide, light and dark (the classes made after this one)."""
    WIDTH = 1400
    THEME = "light"

    @classmethod
    def setUpClass(cls):
        cls.h = AiEditorHarness(chrome).__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.h.__exit__(None, None, None)

    def setUp(self):
        h = self.h
        h.ev("window.unmount()")
        h.ev("for (const k of Object.keys(window.opts)) delete window.opts[k]; window.client.calls.length = 0")
        h.resize(self.WIDTH)
        h.theme(self.THEME)

    # ---- helpers
    def names(self):
        return self.h.ev("[...document.querySelectorAll('.rt-ai-list [role=menuitem]')].map(b=>b.textContent)")

    def text(self):
        return self.h.ev(EDITOR + ".textContent")

    def in_editor(self):
        return self.h.ev("document.activeElement === " + EDITOR)

    def focused(self):
        return self.h.ev("document.activeElement.textContent")

    def enter(self):
        h = self.h
        for kind in ("keyDown", "keyUp"):
            h.cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13,
                                                  "text": "\r" if kind == "keyDown" else ""}, h.sid)

    def alt_slash(self):
        self.h.key("/", 1, "Slash", 191)

    def open_list_by_key(self, value=f"<p>{TEXT}</p>", **cfg):
        self.h.open(value, **cfg)
        self.h.select(5, 23)                                           # "supplier confirmed"
        self.alt_slash()
        self.assertTrue(self.h.until("!!document.querySelector('.rt-ai-list')"), "Alt+/ did not open the list")

    def card_ready(self):
        self.assertTrue(self.h.until("!!document.querySelector('.aic[data-state=ready]')"), self.h.ev("(document.querySelector('.aic')||{dataset:{}}).dataset.state"))
        self.assertTrue(self.h.until("document.activeElement === document.querySelector('.aic-h')"))

    def click(self, label):
        self.h.ev(f"[...document.querySelectorAll('.aic button')].find(b=>b.textContent==={json.dumps(label)}).click()")

    # ---- the bubble's AI zone
    def test_the_bubble_has_an_ai_zone_on_any_chosen_text_and_only_then(self):
        h = self.h
        h.open(f"<p>{TEXT}</p>")
        self.assertFalse(h.ev("!!document.querySelector('.rt-bubble')"))
        h.select(5, 6)                                                # one letter is enough
        self.assertTrue(h.until("!!document.querySelector('.rt-bubble .rt-ai-zone .rt-ai')"))
        self.assertEqual(h.ev("document.querySelector('.rt-ai-zone').getAttribute('aria-label')"), "AI")
        h.select(6, 6)
        self.assertTrue(h.until("!document.querySelector('.rt-bubble')"))

    def test_the_bubble_button_opens_the_list_on_the_chosen_text(self):
        h = self.h
        h.open(f"<p>{TEXT}</p>")
        h.select(5, 23)
        self.assertTrue(h.until("!!document.querySelector('.rt-bubble .rt-ai')"))
        h.ev("document.querySelector('.rt-bubble .rt-ai').click()")
        self.assertTrue(h.until("!!document.querySelector('.rt-ai-list')"))
        self.assertEqual(self.names(), CURRENT_NAMES + MAKE_NAMES + ["Ask…"])
        h.ev("document.querySelector('[data-ai=shorter]').click()")
        self.card_ready()
        self.assertEqual(h.ev("window.client.calls[0].text"), "supplier confirmed")

    # ---- the toolbar's AI button
    def test_the_toolbar_button_acts_on_the_whole_field_when_nothing_is_chosen(self):
        h = self.h
        h.open(f"<p>{TEXT}</p>")
        h.ev("document.querySelector('.rt-bar .rt-ai').click()")
        self.assertTrue(h.until("!!document.querySelector('.rt-ai-list')"))
        self.assertEqual(self.names(), CURRENT_NAMES + ["Ask…"])      # no Make into without a chosen passage
        h.ev("document.querySelector('[data-ai=shorter]').click()")
        self.card_ready()
        self.assertEqual(h.ev("window.client.calls.length"), 1)
        self.assertEqual(h.ev("window.client.calls[0].text"), TEXT)
        self.assertEqual(h.ev("JSON.stringify(Object.keys(window.client.calls[0]).sort())"), '["instruction","option","place","text"]')

    def test_the_bar_alt_slash_and_bubble_show_the_same_list(self):
        h = self.h
        h.open(f"<p>{TEXT}</p>")
        h.select(5, 23)
        self.assertTrue(h.until("!!document.querySelector('.rt-bubble .rt-ai')"))
        h.ev("document.querySelector('.rt-bubble .rt-ai').click()")
        self.assertTrue(h.until("!!document.querySelector('.rt-ai-list')"))
        from_bubble = self.names()
        h.key("Escape", 0, "Escape", 27)
        self.assertTrue(h.until("!document.querySelector('.rt-ai-list')"))
        h.ev("document.querySelector('.rt-bar .rt-ai').click()")
        self.assertTrue(h.until("!!document.querySelector('.rt-ai-list')"))
        from_bar = self.names()
        h.key("Escape", 0, "Escape", 27)
        self.assertTrue(h.until("!document.querySelector('.rt-ai-list')"))
        self.alt_slash()
        self.assertTrue(h.until("!!document.querySelector('.rt-ai-list')"))
        self.assertEqual(from_bubble, from_bar)
        self.assertEqual(from_bar, self.names())

    def test_format_notes_is_offered_for_several_paragraphs_only(self):
        h = self.h
        h.open(TWO)
        h.select_all()
        self.alt_slash()
        self.assertTrue(h.until("!!document.querySelector('.rt-ai-list')"))
        self.assertIn("Format notes", self.names())
        h.key("Escape", 0, "Escape", 27)
        h.select(2, 6)
        self.alt_slash()
        self.assertTrue(h.until("!!document.querySelector('.rt-ai-list')"))
        self.assertNotIn("Format notes", self.names())

    def test_places_set_the_options(self):
        h = self.h
        h.open(f"<p>{TEXT}</p>", place="plain")
        h.select(5, 23)
        self.alt_slash()
        self.assertTrue(h.until("!!document.querySelector('.rt-ai-list')"))
        self.assertEqual(self.names(), ["Rewrite clearly", "Shorter", "Make it executive", "Ask…"])    # no Make into in a plain place
        h.open(f"<p>{TEXT}</p>", place=None)                         # no place: no AI at all
        h.select(5, 23)
        self.assertTrue(h.until("!!document.querySelector('.rt-bubble')"))
        self.assertFalse(h.ev("!!document.querySelector('.rt-ai, .rt-ai-zone')"))
        self.alt_slash()
        self.assertFalse(h.ev("!!document.querySelector('.rt-ai-list')"))

    # ---- one test per key
    def test_key_alt_slash_opens_the_list_with_focus_on_the_first_item(self):
        self.open_list_by_key()
        self.assertEqual(self.names()[0], "Rewrite clearly")
        self.assertTrue(self.h.until("document.activeElement.textContent === 'Rewrite clearly'"))
        self.assertEqual(self.h.ev("document.querySelector('.rt-ai-list').getAttribute('role')"), "menu")
        self.assertEqual(self.h.ev("window.client.calls.length"), 0)        # opening asks nothing
        self.assertEqual(self.h.ev("window.ended"), 0)

    def test_key_arrows_move_and_wrap(self):
        h = self.h
        self.open_list_by_key()
        h.key("ArrowDown", 0, "ArrowDown", 40)
        self.assertEqual(self.focused(), "Shorter")
        h.key("ArrowDown", 0, "ArrowDown", 40)
        self.assertEqual(self.focused(), "Longer")
        h.key("ArrowUp", 0, "ArrowUp", 38)
        self.assertEqual(self.focused(), "Shorter")
        h.key("ArrowUp", 0, "ArrowUp", 38)
        h.key("ArrowUp", 0, "ArrowUp", 38)                              # from the first, up goes to the last
        self.assertEqual(self.focused(), "Ask…")

    def test_key_enter_chooses_the_focused_item(self):
        h = self.h
        self.open_list_by_key()
        h.key("ArrowDown", 0, "ArrowDown", 40)
        self.enter()
        self.assertTrue(h.until("!document.querySelector('.rt-ai-list')"))
        self.card_ready()
        self.assertEqual(h.ev("window.client.calls[0].option"), "shorter")
        self.assertEqual(h.ev("document.querySelector('.aic-h').textContent"), "Shorter")

    def test_key_esc_closes_the_list_and_returns_to_the_editor_without_closing_the_field(self):
        h = self.h
        self.open_list_by_key()
        h.key("Escape", 0, "Escape", 27)
        self.assertTrue(h.until("!document.querySelector('.rt-ai-list')"))
        self.assertTrue(self.in_editor())
        self.assertEqual(h.ev("window.ended"), 0)
        self.assertEqual(h.ev("window.client.calls.length"), 0)
        self.assertEqual(self.text(), TEXT)

    def test_key_tab_closes_the_list_and_does_not_trap(self):
        h = self.h
        self.open_list_by_key()
        h.key("Tab", 0, "Tab", 9)
        self.assertTrue(h.until("!document.querySelector('.rt-ai-list')"))
        self.assertTrue(self.in_editor())
        self.assertEqual(h.ev("window.ended"), 0)                       # still in the field, nothing saved or lost
        self.assertEqual(h.ev("window.client.calls.length"), 0)

    # ---- Ask…
    def test_ask_takes_one_line_and_enter_sends_it(self):
        h = self.h
        self.open_list_by_key()
        h.ev("document.querySelector('[data-ai=custom]').click()")
        self.assertTrue(h.until("document.activeElement.classList.contains('rt-ai-ask')"))
        self.enter()                                                    # empty: nothing is sent
        self.assertEqual(h.ev("window.client.calls.length"), 0)
        h.type("Say it more kindly")
        self.enter()
        self.card_ready()
        self.assertEqual(h.ev("window.client.calls[0].option"), "custom")
        self.assertEqual(h.ev("window.client.calls[0].instruction"), "Say it more kindly")
        self.assertEqual(h.ev("document.querySelector('.aic-h').textContent"), "Say it more kindly")

    def test_esc_in_ask_closes_it_and_returns_to_the_editor(self):
        h = self.h
        self.open_list_by_key()
        h.ev("document.querySelector('[data-ai=custom]').click()")
        self.assertTrue(h.until("document.activeElement.classList.contains('rt-ai-ask')"))
        h.key("Escape", 0, "Escape", 27)
        self.assertTrue(h.until("!document.querySelector('.rt-ai-list')"))
        self.assertTrue(self.in_editor())
        self.assertEqual(h.ev("window.ended"), 0)

    # ---- nothing changes before Accept; Accept is one step
    def test_nothing_changes_before_accept_and_discard_and_esc_leave_the_text(self):
        h = self.h
        for how in ("discard", "esc"):
            with self.subTest(how=how):
                h.ev("window.unmount()")
                self.open_list_by_key()
                h.ev("document.querySelector('[data-ai=shorter]').click()")
                self.card_ready()
                self.assertEqual(self.text(), TEXT)                       # the suggestion is shown; the field is not changed
                self.assertEqual(h.ev("document.querySelector('.rt').contains(document.querySelector('.aic'))"), True)
                if how == "discard":
                    self.click("Discard")
                else:
                    h.key("Escape", 0, "Escape", 27)
                self.assertTrue(h.until("!document.querySelector('.aic')"))
                self.assertEqual(self.text(), TEXT)
                self.assertTrue(self.in_editor())
                self.assertEqual(h.ev("window.ended"), 0)

    def test_accept_is_one_editor_step_and_cmd_z_undoes_it(self):
        h = self.h
        h.open(f"<p>{TEXT}</p>")
        h.type(" Typed after.")
        typed = TEXT + " Typed after."
        self.assertEqual(self.text(), typed)
        h.select_all()
        self.alt_slash()
        self.assertTrue(h.until("!!document.querySelector('.rt-ai-list')"))
        h.ev("document.querySelector('[data-ai=shorter]').click()")
        self.card_ready()
        self.assertEqual(self.text(), typed)
        self.click("Accept")
        self.assertTrue(h.until(f"{EDITOR}.textContent === {json.dumps(SHORT)}"), self.text())
        self.assertTrue(self.in_editor(), "focus returns to the editor")
        self.assertFalse(h.ev("!!document.querySelector('.aic')"))
        h.key("z", h.mod, "KeyZ", 90)                                  # one Undo: the typing before it is still there
        self.assertTrue(h.until(f"{EDITOR}.textContent === {json.dumps(typed)}"), self.text())
        h.key("z", h.mod, "KeyZ", 90)                                  # a second Undo takes the typing back
        self.assertTrue(h.until(f"{EDITOR}.textContent === {json.dumps(TEXT)}"), self.text())

    def test_accept_on_a_few_words_stays_inside_the_paragraph_and_one_undo_puts_them_back(self):
        h = self.h
        self.open_list_by_key()
        h.ev("window.opts.reply = () => ({text: 'the vendor'})")
        h.ev("document.querySelector('[data-ai=rewrite]').click()")
        self.card_ready()
        self.click("Accept")
        self.assertTrue(h.until(f"{EDITOR}.textContent === {json.dumps(TEXT.replace('supplier confirmed', 'the vendor'))}"), self.text())
        self.assertEqual(h.ev(f"{EDITOR}.querySelectorAll('p').length"), 1)
        h.key("z", h.mod, "KeyZ", 90)
        self.assertTrue(h.until(f"{EDITOR}.textContent === {json.dumps(TEXT)}"), self.text())
        self.assertEqual(h.ev(f"{EDITOR}.querySelectorAll('p').length"), 1)

    def test_accept_by_keyboard_and_a_reply_is_cleaned_before_it_is_used(self):
        h = self.h
        h.open(f"<p>{TEXT}</p>")
        h.select_all()
        self.alt_slash()
        h.ev("window.opts.reply = () => ({html: '<p>Short <strong>one</strong></p><script>window.hacked=1</script><img src=x onerror=window.hacked=2>'})")
        self.enter()                                                   # first item: Rewrite clearly
        self.card_ready()
        h.key("Tab", 0, "Tab", 9)
        self.assertEqual(self.focused(), "Accept")
        self.enter()
        self.assertTrue(h.until(f"{EDITOR}.textContent === 'Short one'"), self.text())
        self.assertEqual(h.ev(f"{EDITOR}.querySelectorAll('script, img').length"), 0)
        self.assertEqual(h.ev("window.hacked"), None)
        self.assertTrue(self.in_editor())

    def test_accept_refuses_when_the_text_changed_while_waiting(self):
        h = self.h
        self.open_list_by_key()
        h.ev("document.querySelector('[data-ai=rewrite]').click()")
        self.card_ready()
        h.ev(f"{EDITOR}.cxed.editor.chain().insertContentAt(1, 'Oh. ').run()")        # the text under the question changes
        before = self.text()
        self.click("Accept")
        self.assertTrue(h.until("!document.querySelector('.aic')"))
        self.assertEqual(self.text(), before)
        self.assertEqual(h.ev("document.querySelector('.rt-problem').textContent"), "The text changed while you waited. Try again.")

    # ---- the card's live region, once
    def test_one_polite_live_region(self):
        h = self.h
        self.open_list_by_key()
        h.ev("window.opts.hold = true")
        h.ev("document.querySelector('[data-ai=shorter]').click()")
        self.assertTrue(h.until("!!document.querySelector('.aic[data-state=working]')"))
        self.assertEqual(h.ev("document.querySelectorAll('.rt [aria-live], .rt [role=status]').length"), 1)
        self.assertEqual(h.ev("document.querySelector('.rt [aria-live]').getAttribute('aria-live')"), "polite")
        self.assertEqual(h.ev("document.querySelector('.aic-say').textContent.trim()"), "Working on it")

    # ---- off: the menu shows, greyed, and nothing is asked
    def test_when_ai_is_not_available_the_list_says_so_and_asks_nothing(self):
        h = self.h
        for state, line in (("not_signed_in", NOT_SIGNED_IN), ("off", "AI is switched off in Settings.")):
            with self.subTest(state=state):
                h.ev("window.unmount()")
                h.ev(f"window.opts.state = {state!r}")
                self.open_list_by_key()
                self.assertEqual(h.ev("document.querySelector('.rt-ai-line').textContent"), line)
                self.assertEqual(h.ev("document.querySelectorAll('.rt-ai-list [role=menuitem][aria-disabled=true]').length"), len(CURRENT_NAMES) + 1)
                h.ev("document.querySelector('[data-ai=shorter]').click()")
                h.ev("document.querySelector('[data-ai=custom]').click()")
                self.assertTrue(h.ev("!!document.querySelector('.rt-ai-list')"), "a greyed item does not close the list")
                self.assertFalse(h.ev("!!document.querySelector('.aic')"))
                self.assertEqual(h.ev("window.client.calls.length"), 0)
                h.ev("document.querySelector('[data-ai=make-action]').click()")             # Make into needs no AI
                self.assertEqual(h.ev("window.made.length"), 1)

    def test_the_greyed_state_is_text_at_4_5_to_1(self):
        h = self.h
        h.ev("window.opts.state = 'not_signed_in'")
        self.open_list_by_key()
        self.assertGreaterEqual(h.ev(CONTRAST % "'.rt-ai-line'"), 4.5)
        self.assertGreaterEqual(h.ev(CONTRAST % "'[data-ai=shorter]'"), 4.5)
        self.assertGreaterEqual(h.ev(CONTRAST % "'.rt-ai-h'"), 4.5)

    # ---- Make into
    def test_make_into_makes_one_item_with_no_ai_call(self):
        h = self.h
        for place in ("current", "notes"):
            for name, kind in zip(MAKE_NAMES, ("action", "risk", "decision")):
                with self.subTest(place=place, kind=kind):
                    h.ev("window.unmount(); window.client.calls.length = 0")
                    self.open_list_by_key(place=place)
                    h.ev(f"[...document.querySelectorAll('.rt-ai-list [role=menuitem]')].find(b=>b.textContent==={json.dumps(name)}).click()")
                    self.assertEqual(h.ev("window.made"), [[kind, "supplier confirmed"]])
                    self.assertFalse(h.ev("!!document.querySelector('.rt-ai-list, .aic')"))
                    self.assertEqual(h.ev("window.client.calls.length"), 0)
                    self.assertTrue(self.in_editor())
                    self.assertEqual(self.text(), TEXT)                                      # the field is not changed

    def test_make_into_is_only_for_a_chosen_passage_in_a_rich_place_that_can_make_one(self):
        h = self.h
        h.open(f"<p>{TEXT}</p>")
        h.ev("document.querySelector('.rt-bar .rt-ai').click()")
        self.assertTrue(h.until("!!document.querySelector('.rt-ai-list')"))
        self.assertFalse(any(n.startswith("Make this") for n in self.names()))
        h.key("Escape", 0, "Escape", 27)
        self.open_list_by_key(noMake=True)
        self.assertFalse(any(n.startswith("Make this") for n in self.names()))

    # ---- sharing Esc with the ask panel
    def test_esc_closes_only_the_list_when_the_ask_panel_is_shut(self):
        h = self.h
        self.open_list_by_key()
        self.assertFalse(h.ev("window.ask.isOpen()"))
        h.key("Escape", 0, "Escape", 27)
        self.assertTrue(h.until("!document.querySelector('.rt-ai-list')"))
        self.assertTrue(self.in_editor(), "focus is back in the editor")
        self.assertEqual(h.ev("window.ended"), 0, "the field stays open")
        self.assertFalse(h.ev("window.ask.isOpen()"), "Esc did not open or touch the panel")

    def test_esc_closes_only_the_panel_when_focus_is_in_the_panel(self):
        h = self.h
        h.open(f"<p>{TEXT}</p>")
        h.ev("window.ask.open()")
        self.assertTrue(h.until("!!document.querySelector('#ask-panel') && document.querySelector('#ask-panel').contains(document.activeElement)"))
        ended = h.ev("window.ended")                                  # a field closes by itself when focus goes to the panel
        h.key("Escape", 0, "Escape", 27)
        self.assertTrue(h.until("!document.querySelector('#ask-panel')"))
        self.assertFalse(h.ev("window.ask.isOpen()"))
        self.assertEqual(h.ev("window.ended"), ended, "Esc in the panel did not end the field a second time")
        self.assertFalse(h.ev("!!document.querySelector('.rt-ai-list')"))

    # ---- inside the window
    def test_the_bubble_and_the_list_stay_inside_the_window(self):
        h = self.h
        long = "".join(f"<p>{TEXT} {TEXT}</p>" for _ in range(6))
        h.open(long)
        for a, b in ((1, 12), (5, 60)):
            h.select(a, b)
            self.assertTrue(h.until("!!document.querySelector('.rt-bubble .rt-ai')"))
            self.assertTrue(h.ev(INSIDE % "'.rt-bubble'"), "the bubble is inside the window")
            h.ev("document.querySelector('.rt-bubble .rt-ai').click()")
            self.assertTrue(h.until("!!document.querySelector('.rt-ai-list')"))
            self.assertTrue(h.ev(INSIDE % "'.rt-ai-list'"), "the list is inside the window")
            h.key("Escape", 0, "Escape", 27)
        h.ev("document.querySelector('.rt-bar .rt-ai').click()")
        self.assertTrue(h.until("!!document.querySelector('.rt-ai-list')"))
        self.assertTrue(h.ev(INSIDE % "'.rt-ai-list'"), "the list opened from the toolbar is inside the window")
        h.key("Escape", 0, "Escape", 27)
        h.select(1, 30)
        self.alt_slash()
        self.assertTrue(h.until("!!document.querySelector('.rt-ai-list')"))
        self.assertTrue(h.ev(INSIDE % "'.rt-ai-list'"))
        h.ev("document.querySelector('[data-ai=custom]').click()")
        self.assertTrue(h.until("!!document.querySelector('.rt-ai-ask')"))
        self.assertTrue(h.ev(INSIDE % "'.rt-ai-list'"))
        h.key("Escape", 0, "Escape", 27)


for _theme in ("light", "dark"):
    for _width in (1400, 900):
        _name = f"Editor{_width}{_theme.title()}"
        globals()[_name] = type(_name, (EditorTests, unittest.TestCase), {"WIDTH": _width, "THEME": _theme})


class MakeIntoRequest(unittest.TestCase):
    """The request Make into sends is the report's own add-a-row change: one new item, one step, one Undo."""

    @classmethod
    def setUpClass(cls):
        cls.h = AiEditorHarness(chrome).__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.h.__exit__(None, None, None)

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.change = changes.make_change(self.demo.store.path, [], USER)
        self.undo = changes.make_undo(self.demo.store.path, [], USER)

    def request(self, kind, text):
        return self.h.ev(f"JSON.stringify(window.MI.makeIntoRequest({json.dumps(kind)}, {json.dumps(text)}))")

    def test_each_kind_makes_one_item_and_undo_takes_it_back(self):
        for kind, table in (("action", "actions"), ("risk", "raid"), ("decision", "decisions")):
            with self.subTest(kind=kind):
                req = json.loads(self.request(kind, "  The supplier   confirmed\nthe delivery.  "))
                self.assertEqual(req["kind"], table)
                self.assertEqual(req["op"], "new")
                before = len(self.demo.store.read(table, "ABC"))
                status, body = self.change({"project": "ABC", **req})
                self.assertEqual((status, body.get("message")), (200, None), body)
                self.assertTrue(body["apply_id"])
                rows = self.demo.store.read(table, "ABC")
                self.assertEqual(len(rows), before + 1)
                made = next(r for r in rows if r["id"] == body["ref"])
                self.assertEqual(made.get("description") or made.get("decision"), "The supplier confirmed the delivery.")
                status, body = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
                self.assertEqual(status, 200, body)
                self.assertEqual(len(self.demo.store.read(table, "ABC")), before)

    def test_a_long_passage_is_cut_to_what_the_store_takes_and_nothing_else_is_made(self):
        req = json.loads(self.request("action", "word " * 100))
        self.assertLessEqual(len(req["values"]["description"]), 200)
        status, body = self.change({"project": "ABC", **req})
        self.assertEqual(status, 200, body)
        self.assertIsNone(self.h.ev("window.MI.makeIntoRequest('nothing', 'x')"))
        self.assertIsNone(self.h.ev("window.MI.makeIntoRequest('action', '   ')"))
        self.assertIsNone(self.h.ev("window.MI.makeIntoRequest('__proto__', 'x')"))


if __name__ == "__main__":
    unittest.main()
