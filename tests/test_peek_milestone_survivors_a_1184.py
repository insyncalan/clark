"""Item 1184, killing tests for survivors S1, S2 and S3 of the mutation report (scratch-v11/WO-M4030-stark.md) against MilestonePeek.jsx.
S1  useRoam drops e.stopPropagation(): a key the popover's choices act on must not also reach the page behind it.
S2  StatePop / ProgressPop pick calls close() and not close(true): the focus must come back to the chip that opened the popover.
S3  ProgressPop aria-pressed `was >= n` as `was > n`: the block equal to the progress must read pressed.
Real browser at 1400 and 900 px, real key events (CDP Input.dispatchKeyEvent), the Milestones page (always Edit), the fictional demo project (ABC).
Run: python3 dev/run_tests.py test_peek_milestone_survivors_a_1184
"""
import json
import unittest

from _demo import USER

import test_peek_milestone_1184 as base  # noqa: E402  (the module, so its tests are not collected twice)
from test_server import chrome  # noqa: E402

PILOT = base.PILOT
CHIP_BUTTON = "#peek .pk-chips [data-row={field}] button"
# Listeners on the document and on the window, in the bubbling phase (where the peek and the page behind it listen): they record the keys that get there.
WATCH = ("(() => { window.__seen = []; const f = (e) => window.__seen.push(e.key);"
         " document.addEventListener('keydown', f); window.addEventListener('keydown', f); return true; })()")


class Survivors(base.Milestone):

    def real_key_char(self, cdp, p, ch):
        for kind in ("keyDown", "keyUp"):
            cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": ch, "code": "Key" + ch.upper(), "windowsVirtualKeyCode": ord(ch.upper()), **({"text": ch} if kind == "keyDown" else {})}, p.sid)

    # ---- S1 -----------------------------------------------------------------------------------------------------------------------------------------

    def test_s1_the_keys_the_state_and_progress_choices_act_on_do_not_reach_the_page_behind(self):
        for width in (1400, 900):
            for field, attr, keys in (("state", "msState", ("ArrowDown", "ArrowUp", "ArrowRight", "ArrowLeft", "Home", "End")),
                                      ("progress", "msBlock", ("ArrowRight", "ArrowDown", "Home", "ArrowLeft", "ArrowUp", "End"))):
                with self.subTest(width=width, field=field), chrome() as cdp:
                    self.setUp()
                    p = self.visit(cdp, width=width)
                    self.chip(p, field)
                    p.until(f"document.activeElement && !!document.activeElement.dataset.{attr}", "focus is on a choice as the popover opens")
                    self.assertEqual(p.js(WATCH), True)
                    moved = []
                    for key in keys:
                        before = self.at(p)
                        self.real_key(cdp, p, key)
                        moved.append(self.at(p) != before)
                    self.assertEqual(moved, [True] * len(keys), f"each of the {len(keys)} keys moved the focus (the popover handled it)")
                    self.assertEqual(p.js("window.__seen"), [], "no arrow, Home or End got past the popover to the document or the window")
                    # the control: a key the popover does not act on does bubble, so the listeners do hear the page
                    self.real_key_char(cdp, p, "x")
                    self.assertEqual(p.js("window.__seen"), ["x", "x"], "a letter reaches the document and the window (one each): the watch works")

    # ---- S2 -----------------------------------------------------------------------------------------------------------------------------------------

    def test_s2_a_pick_gives_the_focus_back_to_the_chip_by_click_and_by_real_enter(self):
        for width in (1400, 900):
            for field, choice, how, saved in (("state", "At risk", "click", ("state", "At risk")), ("state", "Slipped", "enter", ("state", "Slipped")),
                                              ("progress", "30", "click", ("percent_complete", 30)), ("progress", "70", "enter", ("percent_complete", 70))):
                with self.subTest(width=width, field=field, how=how), chrome() as cdp:
                    self.setUp()
                    p = self.visit(cdp, width=width)
                    self.chip(p, field)
                    attr = "msState" if field == "state" else "msBlock"
                    sel = f"[data-pop] [data-ms-state='{choice}']" if field == "state" else f"[data-pop] [data-ms-block='{choice}']"
                    if how == "click":
                        self.click(p, sel)
                    else:
                        p.until(f"!!document.activeElement && !!document.activeElement.dataset.{attr}", "focus is on a choice")
                        p.js(f"document.querySelector({json.dumps(sel)}).focus()")
                        p.until(f"document.activeElement.dataset.{attr} === {json.dumps(choice)}", "the choice has the focus")
                        self.real_key(cdp, p, "Enter")
                    self.saved(*saved)
                    p.until("!document.querySelector('[data-pop]')", "the popover closed")
                    p.until(f"document.activeElement === document.querySelector({json.dumps(CHIP_BUTTON.format(field=field))})",
                            f"the focus is back on the {field} chip button, not lost to the page")

    # ---- S3 -----------------------------------------------------------------------------------------------------------------------------------------

    def test_s3_the_block_equal_to_the_progress_reads_pressed_and_the_ones_above_do_not(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.setUp()
                with self.store.step("dashboard", USER) as st:
                    st.update("milestones", PILOT, {"percent_complete": 40})
                p = self.visit(cdp, width=width)
                self.chip(p, "progress")
                p.until("document.activeElement && document.activeElement.dataset.msBlock === '40'", "the current block has the focus")
                got = p.js("[...document.querySelectorAll('[data-pop] [data-ms-block]')].map(b => [Number(b.dataset.msBlock), b.getAttribute('aria-pressed')])")
                self.assertEqual(got, [[n, "true" if n <= 40 else "false"] for n in range(10, 101, 10)], "blocks 10 to 40 pressed (4 of them, 40 itself included), 50 to 100 not")


for _name in dir(base.Milestone):          # the tests the parent class brings along belong to its own file: run only the ones above
    if _name.startswith("test_") and _name not in Survivors.__dict__:
        setattr(Survivors, _name, None)


if __name__ == "__main__":
    unittest.main()
