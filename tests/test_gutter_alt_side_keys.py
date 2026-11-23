"""Row 1214: Alt+Right on a section's move button puts the section beside the next one, Alt+Left makes it full width; one change,
one Undo; on the last section, or on one that is already beside another, Alt+Right changes nothing; Help says so. In the real page
at 1400 and 900."""
import json
import unittest

from _paths import SRC
from test_report_editor import Base, IDS, ALT, wait

HELP = json.loads((SRC / "clark" / "page" / "src" / "help" / "helpContent.json").read_text(encoding="utf-8"))
LINE = "Alt+Right puts the section beside the next one, Alt+Left makes it full width"
GRIP = "document.querySelector('[data-id=\"%s\"] [data-drag]')"
ON_GRIP = "document.activeElement === " + GRIP


class AltSideKeys(Base):
    def at(self, cdp, width):
        p = self.visit(cdp)
        p.edit()
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        return p

    def right(self, p):
        p.key("ArrowRight", ALT, code="ArrowRight", vk=39)

    def left(self, p):
        p.key("ArrowLeft", ALT, code="ArrowLeft", vk=37)

    def one_undo_each(self, width):
        from test_server import chrome
        if True:
            with chrome() as cdp:
                p = self.at(cdp, width)
                before = dict(self.beside_flags())
                self.assertEqual(before["ABC-S-002"], 0)
                p.js(GRIP % "ABC-S-002" + ".focus()")
                n = len(self.sent)
                self.right(p)
                p.until("document.querySelector('[data-id=\"ABC-S-002\"]').classList.contains('slot-left')", "beside the next, on the left")
                p.saved()
                self.assertEqual(self.beside_flags()["ABC-S-002"], 1)
                self.assertEqual(self.ids_in_store(), IDS)
                self.assertEqual(len(self.sent) - n, 1, "one request")
                self.assertEqual(self.sent[-1][1]["place"], "report")
                self.assertTrue(wait(lambda: p.js(ON_GRIP % "ABC-S-002"), 5), "focus stays on the grip")
                self.assertEqual(p.js(GRIP % "ABC-S-002" + ".getAttribute('aria-keyshortcuts')"), "Alt+ArrowUp Alt+ArrowDown Alt+ArrowRight Alt+ArrowLeft")
                self.left(p)
                p.until("!document.querySelector('[data-id=\"ABC-S-002\"]').classList.contains('slot-left')", "full width again")
                self.assertTrue(wait(lambda: self.beside_flags() == before, 10), "the store is back")
                self.assertTrue(wait(lambda: p.js(ON_GRIP % "ABC-S-002"), 5))
                p.js("document.querySelector('[data-undo]').click()")
                self.assertTrue(wait(lambda: self.beside_flags()["ABC-S-002"] == 1, 10), "one Undo takes back the Alt+Left only")

    def nothing_harmful(self, width):
        from test_server import chrome
        if True:
            with chrome() as cdp:
                p = self.at(cdp, width)
                before = dict(self.beside_flags())
                p.js(GRIP % IDS[-1] + ".focus()")
                n = len(self.sent)
                self.right(p)
                self.assertTrue(wait(lambda: p.js("(document.querySelector('.toast-text') || {}).textContent || ''") != "", 5), "it says why")
                self.assertEqual(len(self.sent), n, "nothing was sent")
                self.assertEqual(self.beside_flags(), before)
                self.assertEqual(self.ids_in_store(), IDS)
                self.assertTrue(p.js(ON_GRIP % IDS[-1]))
                p.clear_toast()
                p.js(GRIP % "ABC-S-002" + ".focus()")
                self.right(p)
                p.saved()
                p.clear_toast()
                n = len(self.sent)
                flags = dict(self.beside_flags())
                self.right(p)                                # already beside the next: nothing to do
                self.assertEqual(len(self.sent), n)
                self.assertEqual(self.beside_flags(), flags)
                p.js(GRIP % "ABC-S-009" + ".focus()")
                self.left(p)                                 # already full width: nothing to do
                self.assertEqual(len(self.sent), n)
                self.assertEqual(self.beside_flags(), flags)

    def drawn(self, p):
        """Returns after the page has drawn twice, so a message the last key asked for would be on screen by now."""
        p.cdp.call("Runtime.evaluate", {"expression": "new Promise(function (r) { requestAnimationFrame(function () { requestAnimationFrame(r); }); })",
                                        "awaitPromise": True, "returnByValue": True}, p.sid)

    def paired_says_nothing(self, width):
        from test_server import chrome
        with chrome() as cdp:
            p = self.at(cdp, width)
            p.js(GRIP % "ABC-S-002" + ".focus()")
            self.right(p)
            p.saved()
            p.clear_toast()
            n = len(self.sent)
            flags = dict(self.beside_flags())
            for sid in ("ABC-S-002", "ABC-S-003"):       # both halves of the pair
                p.js(GRIP % sid + ".focus()")
                self.right(p)
                self.drawn(p)
                self.assertEqual(p.js("document.querySelectorAll('.toast').length"), 0, sid + ": no message")
                self.assertEqual(len(self.sent), n)
                self.assertEqual(self.beside_flags(), flags)

    def shift_does_nothing(self, width):
        from test_server import chrome
        with chrome() as cdp:
            p = self.at(cdp, width)
            before = dict(self.beside_flags())
            n = len(self.sent)
            p.js(GRIP % "ABC-S-002" + ".focus()")
            p.key("ArrowRight", ALT | 8, code="ArrowRight", vk=39)
            self.drawn(p)
            self.assertEqual(len(self.sent), n, "Shift+Alt+Right sent nothing")
            self.assertEqual(self.beside_flags(), before)
            self.assertEqual(p.js("document.querySelectorAll('.toast').length"), 0)
            self.right(p)
            p.saved()
            n = len(self.sent)
            flags = dict(self.beside_flags())
            p.key("ArrowLeft", ALT | 8, code="ArrowLeft", vk=37)
            self.drawn(p)
            self.assertEqual(len(self.sent), n, "Shift+Alt+Left sent nothing")
            self.assertEqual(self.beside_flags(), flags)
            self.assertEqual(p.js("document.querySelector('[data-id=\"ABC-S-002\"]').classList.contains('slot-left')"), True)

    def shift_up_down_still_move(self, width):
        from test_server import chrome
        with chrome() as cdp:
            p = self.at(cdp, width)
            p.js(GRIP % "ABC-S-003" + ".focus()")
            n = len(self.sent)
            p.key("ArrowUp", ALT | 8, code="ArrowUp", vk=38)
            p.order_is(["ABC-S-001", "ABC-S-003", "ABC-S-002"] + IDS[3:], "Shift+Alt+Up")
            p.saved()
            self.assertEqual(len(self.sent) - n, 1, "one change")
            n = len(self.sent)
            p.key("ArrowDown", ALT | 8, code="ArrowDown", vk=40)
            p.order_is(IDS, "Shift+Alt+Down")
            self.assertTrue(wait(lambda: self.ids_in_store() == IDS, 10))
            self.assertEqual(len(self.sent) - n, 1, "one change")

    def full_width_alt_left_says_nothing(self, width):
        from test_server import chrome
        with chrome() as cdp:
            p = self.at(cdp, width)
            n = len(self.sent)
            before = dict(self.beside_flags())
            p.js(GRIP % "ABC-S-009" + ".focus()")
            self.left(p)
            self.drawn(p)
            self.assertEqual(p.js("document.querySelectorAll('.toast').length"), 0, "no message")
            self.assertEqual(len(self.sent), n)
            self.assertEqual(self.beside_flags(), before)

    def test_shift_with_alt_up_or_down_still_moves_at_1400(self):
        self.shift_up_down_still_move(1400)

    def test_shift_with_alt_up_or_down_still_moves_at_900(self):
        self.shift_up_down_still_move(900)

    def test_alt_left_on_a_full_width_section_shows_no_message_at_1400(self):
        self.full_width_alt_left_says_nothing(1400)

    def test_alt_left_on_a_full_width_section_shows_no_message_at_900(self):
        self.full_width_alt_left_says_nothing(900)

    def test_alt_right_on_either_half_of_a_pair_shows_no_message_at_1400(self):
        self.paired_says_nothing(1400)

    def test_alt_right_on_either_half_of_a_pair_shows_no_message_at_900(self):
        self.paired_says_nothing(900)

    def test_shift_with_alt_and_an_arrow_does_nothing_at_1400(self):
        self.shift_does_nothing(1400)

    def test_shift_with_alt_and_an_arrow_does_nothing_at_900(self):
        self.shift_does_nothing(900)

    def test_alt_right_and_alt_left_with_one_undo_each_at_1400(self):
        self.one_undo_each(1400)

    def test_alt_right_and_alt_left_with_one_undo_each_at_900(self):
        self.one_undo_each(900)

    def test_alt_right_on_the_last_or_a_paired_section_changes_nothing_at_1400(self):
        self.nothing_harmful(1400)

    def test_alt_right_on_the_last_or_a_paired_section_changes_nothing_at_900(self):
        self.nothing_harmful(900)

    def test_help_says_what_alt_right_and_alt_left_do(self):
        text = json.dumps(HELP, ensure_ascii=False)
        said = LINE.replace("Alt+Right", "[[Alt+Right]]").replace("Alt+Left", "[[Alt+Left]]")
        self.assertEqual(text.count(said), 2, "in the arrange steps and in the keys table")
        keys = [r for r in HELP["reference"]["keys"] if r[0] == "[[Alt+Up]] [[Alt+Down]]"]
        self.assertEqual(len(keys), 1)
        self.assertIn(said, keys[0][1])

    def test_the_keys_are_read_from_the_handle_source(self):
        src = (SRC / "clark" / "page" / "src" / "edit" / "Gutter.jsx").read_text(encoding="utf-8")
        self.assertIn('Alt+ArrowUp Alt+ArrowDown Alt+ArrowRight Alt+ArrowLeft', src)
        self.assertIn("besideNext(section.id, \"report\", \"handle\")", src)
        self.assertIn("fullWidth(section.id, \"report\", \"handle\")", src)


if __name__ == "__main__":
    unittest.main()
