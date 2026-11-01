"""#72 slice 8: each AI option's flow end to end, with a fake provider and no sign-in.

Run: python3 dev/run_tests.py test_ai_flows
The real AiCard and aiClient on a bare page (tests/_ai_page.py), not the editor bubble. For every option: the card asks once, the fake
provider is given the text, the option and (for Ask...) the one line, and nothing else; nothing changes before Accept; Accept hands over the
cleaned suggestion once. Also Discard, Try again and Show changes (word by word, the exact words). Everything runs at 1400 and 900 px in
light and dark. The Python side of the same rule (the whole prompt) is checked against a recording provider.
Flows that need the editor itself (selection offsets, Cmd+Z, the Ask... box, the key check) are skipped stubs until those parts land.
"""
import json
import re
import unittest

from _ai_page import AiHarness
from clark import ai_menu
from test_server import chrome

TEXT = "The supplier confirmed the delivery for Friday and asked us to keep the room booked until then."
NOTES = "Supplier called about Friday\nRoom stays booked until then\nNeed a name for the delivery desk"
LINE = "Say it more kindly and keep the Friday date"
CANARY = "Falcon Harbour"           # stands for a project name, a person, an ID or a tool: on the page, but not in the selection
ANSWERS = {                           # what the fake provider says for each option
    "rewrite": "The supplier confirmed delivery on Friday and asked us to keep the room until then.",
    "shorter": "The supplier confirmed Friday delivery.",
    "longer": "The supplier confirmed the delivery for Friday. They also asked us to keep the room booked until then.",
    "executive": "Delivery is confirmed for Friday; the room stays booked until then.",
    "format": "<h3>Delivery</h3><ul><li>Confirmed for Friday</li><li>Room booked until then</li></ul>",
    "checklist": "<ul><li>Keep the room booked until Friday</li><li>Name the delivery desk</li></ul>",
    "summary": "<p>Delivery is on Friday.</p><p>" + TEXT + "</p>",
    "notes": "<h3>Supplier</h3><ul><li>Called about Friday</li><li>Room stays booked until then</li></ul>",
    "formal": "The supplier has confirmed delivery for Friday and requests that the room remain booked until then.",
    "warmer": "Good news: the supplier confirmed Friday, and kindly asked us to keep the room until then.",
    "custom": "The supplier kindly confirmed the delivery for Friday and asked us to keep the room booked until then.",
}
# the flows: (place, option, the text sent). Improve, Structure, Tone, Format notes and Ask...
FLOWS = (
    [("current", o, TEXT) for o in ("rewrite", "shorter", "longer", "executive")]               # Improve
    + [("current", "format", TEXT), ("current", "summary", TEXT), ("notes", "checklist", TEXT)]    # Structure
    + [("email", "formal", TEXT), ("email", "warmer", TEXT)]                                        # Tone
    + [("notes", "notes", NOTES)]                                                                   # Format notes
    + [("current", "custom", TEXT)]                                                                 # Ask...
)
LOOKS = [(w, t) for t in ("light", "dark") for w in (1400, 900)]


def plain(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", html)).strip()


def button(name):
    return f"[...document.querySelectorAll('.aic button')].find(b=>b.textContent.trim()==={name!r})"


class Flows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = AiHarness(chrome).__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.h.__exit__(None, None, None)

    def setUp(self):
        h = self.h
        h.ev("window.unmount()")
        h.ev("for (const k of Object.keys(window.opts)) delete window.opts[k]; window.client.calls.length = 0; "
             "window.applied.length = 0; window.exits.length = 0; window.returned.length = 0; window.useEditor = false")
        h.ev(f"window.answers = {json.dumps(ANSWERS)}; window.opts.reply = (req) => {{ const a = window.answers[req.option]; "
             "return a.startsWith('<') ? {html: a, text: a.replace(/<[^>]*>/g, ' ')} : {text: a}; }")
        h.ev(f"document.getElementById('stand').textContent = {CANARY!r} + ' standup, run by Maria Lindqvist, item AC-104'")
        h.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "no-preference"}]}, h.sid)

    def look(self, width, theme):
        self.h.ev("window.unmount()")
        self.h.resize(width)
        self.h.theme(theme)
        self.h.ev("window.applied.length = 0; window.exits.length = 0; window.client.calls.length = 0")

    def open_flow(self, place, option, text, instruction=""):
        h = self.h
        h.card(place=place, option=option, text=text, instruction=instruction)
        self.assertTrue(h.until("document.querySelector('.aic').dataset.state === 'ready'"), h.state())
        self.assertTrue(h.until("document.activeElement === document.querySelector('.aic-h')"))

    def request(self, n=0):
        return self.h.ev(f"window.client.calls[{n}]")

    # ---- each option's flow, accepted
    def test_every_option_asks_once_sends_only_its_own_things_and_changes_nothing_before_accept(self):
        for width, theme in LOOKS:
            for place, option, text in FLOWS:
                instruction = LINE if option == "custom" else ""
                with self.subTest(width=width, theme=theme, place=place, option=option):
                    self.look(width, theme)
                    self.open_flow(place, option, text, instruction)
                    self.assertEqual(self.h.ev("window.client.calls.length"), 1)
                    self.assertEqual(self.request(), {"option": option, "place": place, "text": text, "instruction": instruction})
                    self.assertNotRegex(json.dumps(self.request()), r"Falcon|Harbour|Lindqvist|AC-104|tool")
                    self.assertEqual(self.h.ev("window.applied.length"), 0)                      # shown, not applied
                    self.assertEqual(self.h.say(), "Suggestion ready")
                    self.assertEqual(self.h.ev("document.querySelector('.aic-text').textContent.replace(/\\s+/g, ' ').trim()"),
                                     plain(ANSWERS[option]))
                    self.h.ev(button("Accept") + ".click()")
                    self.assertEqual(self.h.ev("window.applied.length"), 1)
                    self.assertEqual(plain(self.h.ev("window.applied[0]")), plain(ANSWERS[option]))
                    self.assertEqual(self.h.ev("window.exits"), ["accept"])
                    self.assertEqual(self.h.active(), "stand")
                    self.assertEqual(self.h.ev("window.client.calls.length"), 1)                  # Accept asks nothing more

    def test_ask_sends_its_one_line_and_names_the_card_with_it(self):
        self.open_flow("current", "custom", TEXT, LINE)
        self.assertEqual(self.request()["instruction"], LINE)
        self.assertEqual(self.h.ev("document.querySelector('.aic-h').textContent"), LINE)

    # ---- Make into
    def test_make_into_is_not_an_ai_option_and_asks_nothing(self):
        h = self.h
        for place in ("current", "notes"):
            made = h.ev(f"window.menuOf({place!r}).make_into.map(m => m.id)")
            self.assertEqual(made, ["action", "risk", "decision"])
            for m in made:
                self.assertNotIn(m, h.ev(f"window.placeOptions[{place!r}]"))          # no request can name it
        for place in ("plain", "email", "client_message"):
            self.assertEqual(h.ev(f"window.menuOf({place!r}).make_into"), [])
        for m in ("action", "risk", "decision"):                                       # even sent by mistake, the server refuses it
            with self.assertRaises(ai_menu.Refused):
                ai_menu.check_request(m, TEXT, "current")
        for width, theme in LOOKS:
            self.look(width, theme)
            self.assertEqual(h.ev("document.querySelectorAll('.aic').length"), 0)
            self.assertEqual(h.ev("window.client.calls.length"), 0)                   # the fake provider was never asked

    # ---- Discard, Try again, Show changes
    def test_discard_keeps_the_text_and_applies_nothing(self):
        for width, theme in LOOKS:
            with self.subTest(width=width, theme=theme):
                self.look(width, theme)
                self.open_flow("current", "shorter", TEXT)
                self.h.ev(button("Discard") + ".click()")
                self.assertEqual(self.h.ev("window.applied.length"), 0)
                self.assertEqual(self.h.ev("window.exits"), ["discard"])
                self.assertEqual(self.h.ev("document.querySelectorAll('.aic').length"), 0)
                self.assertEqual(self.h.active(), "stand")
                self.assertEqual(self.h.ev("window.client.calls.length"), 1)

    def test_try_again_sends_the_same_request_again_and_only_the_card_on_screen_can_be_accepted(self):
        for width, theme in LOOKS:
            with self.subTest(width=width, theme=theme):
                self.look(width, theme)
                self.h.ev("window.opts.reply = () => ({text: 'First answer for Friday.'})")
                self.open_flow("current", "rewrite", TEXT)
                self.assertEqual(self.h.ev("document.querySelector('.aic-text').textContent.trim()"), "First answer for Friday.")
                self.h.ev("window.opts.reply = () => ({text: 'Second answer for Friday.'})")
                self.h.ev(button("Try again") + ".click()")
                self.assertTrue(self.h.until("document.querySelector('.aic-text') && "
                                             "document.querySelector('.aic-text').textContent.trim() === 'Second answer for Friday.'"))
                self.assertEqual(self.h.ev("window.client.calls.length"), 2)
                self.assertEqual(self.request(0), self.request(1))                      # the same question, nothing added
                self.assertEqual(self.h.ev("window.applied.length"), 0)                  # the first card was never applied
                self.h.ev(button("Accept") + ".click()")
                self.assertEqual(self.h.ev("window.applied.length"), 1)
                self.assertIn("Second answer", self.h.ev("window.applied[0]"))
                self.assertNotIn("First answer", self.h.ev("window.applied[0]"))

    def test_try_again_after_a_failure_asks_again(self):
        self.h.ev("window.opts.fail = true")
        self.h.card(place="current", option="shorter", text=TEXT)
        self.assertTrue(self.h.until("document.querySelector('.aic').dataset.state === 'failed'"))
        self.h.ev("window.opts.fail = false")
        self.h.ev(button("Try again") + ".click()")
        self.assertTrue(self.h.until("document.querySelector('.aic').dataset.state === 'ready'"))
        self.assertEqual(self.h.ev("window.client.calls.length"), 2)

    def diff(self):
        return self.h.ev("[...document.querySelectorAll('.aic-diff > *')].map(e => [e.tagName.toLowerCase(), e.textContent.trim()])")

    def test_show_changes_lists_the_exact_words_that_go_and_come(self):
        for width, theme in LOOKS:
            with self.subTest(width=width, theme=theme):
                self.look(width, theme)
                self.h.ev("window.opts.reply = () => ({text: 'The supplier confirmed delivery on Friday and asked us to keep the room booked.'})")
                self.open_flow("current", "rewrite", TEXT)
                self.assertEqual(self.diff(), [])                                       # closed until asked for
                self.h.ev(button("Show changes") + ".click()")
                self.assertEqual(self.diff(), [["span", "The supplier confirmed"], ["del", "the"], ["span", "delivery"],
                                               ["del", "for"], ["ins", "on"], ["span", "Friday and asked us to keep the room"],
                                               ["del", "booked until then."], ["ins", "booked."]])
                self.assertEqual(self.h.ev("window.applied.length"), 0)                  # looking at changes applies nothing
                self.h.ev(button("Hide changes") + ".click()")
                self.assertEqual(self.diff(), [])

    def test_show_changes_for_a_reply_that_is_the_same_words(self):
        self.h.ev("window.opts.reply = (r) => ({text: r.text, changes: []})")
        self.open_flow("current", "rewrite", TEXT)
        self.h.ev(button("Show changes") + ".click()")
        self.assertEqual(self.h.ev("document.querySelector('.aic-diff').textContent.trim()"), "The suggestion is the same words as the text.")

    def test_each_flow_card_stays_inside_the_window(self):
        for width, theme in LOOKS:
            with self.subTest(width=width, theme=theme):
                self.look(width, theme)
                self.open_flow("current", "custom", TEXT, LINE + ", and keep it brief about the room as well please")
                self.h.ev(button("Show changes") + ".click()")
                box = self.h.ev("(()=>{const r=document.querySelector('.aic').getBoundingClientRect();"
                                "return [r.left, r.right, innerWidth, document.documentElement.scrollWidth];})()")
                self.assertGreaterEqual(box[0], 0)
                self.assertLessEqual(box[1], box[2])
                self.assertLessEqual(box[3], box[2])

    # ---- what reaches the provider, from the server's side (the same rule, on the whole prompt)
    def test_the_whole_prompt_holds_the_text_the_fixed_instruction_and_the_one_line_and_no_tools(self):
        for place, option, text in FLOWS:
            with self.subTest(place=place, option=option):
                seen = []

                class Fake(ai_menu.Provider):
                    def status(self):
                        return "ready"

                    def ask(self, prompt, tools=()):
                        seen.append((prompt, tuple(tools)))
                        return "<<<SUGGESTION\n" + plain(ANSWERS[option]) + "\nSUGGESTION>>>"

                line = LINE if option == "custom" else ""
                ai_menu.suggest(Fake(), option, text, place, line)
                self.assertEqual(len(seen), 1)
                prompt, tools = seen[0]
                self.assertEqual(tools, ())
                self.assertIn(text, prompt)
                if option == "custom":
                    self.assertIn(LINE, prompt)
                else:
                    self.assertIn(ai_menu.OPTIONS[option][2], prompt)
                for other in ("Falcon", "Harbour", "Lindqvist", "AC-104"):
                    self.assertNotIn(other, prompt)

    def test_make_into_options_never_reach_a_provider(self):
        seen = []

        class Fake(ai_menu.Provider):
            def status(self):
                return "ready"

            def ask(self, prompt, tools=()):
                seen.append(prompt)
                return "x"

        for m in ("action", "risk", "decision"):
            out = ai_menu.suggest(Fake(), m, TEXT, "current")
            self.assertFalse(out["ok"])
        self.assertEqual(seen, [])

    # ---- stubs for the parts the editor owns
    @unittest.skip("needs slice 3's editor hook")
    def test_editor_accept_replaces_only_the_selected_range(self):
        """Select a middle sentence, run Improve, Accept: the words around it stay, and one Cmd+Z puts the sentence back."""

    @unittest.skip("needs slice 3's editor hook")
    def test_editor_alt_slash_on_the_whole_field_with_no_selection(self):
        """With nothing selected, Alt+/ then Enter on Improve sends the whole field, and Accept replaces the whole field."""

    @unittest.skip("needs slice 3's editor hook")
    def test_editor_make_into_makes_one_item_in_one_step_with_undo(self):
        """Select a line in Current state, choose Make this an action: one new item, Cmd+Z removes it, and the fake provider got nothing."""

    @unittest.skip("needs slice 3's Ask... box and slice 5's key check")
    def test_ask_with_a_pasted_key_is_refused_before_anything_is_sent(self):
        """Paste an sk-ant-... key into the Ask... box and press Enter: a plain refusal, and the fake provider got nothing."""


if __name__ == "__main__":
    unittest.main()
