"""#131 motion: six of the ten mild motions whose screens exist today, each tested running and in its reduced form.

Run: python3 dev/run_tests.py test_motion
Built: 1 the placeholder fades out as the screen arrives (the issue's item 2), 2 a changed row glows then settles to the still
mark (item 3), 3 the health badge and reason settle when health changes (item 6), 4 the count line and counts fade when a filter
changes (item 9), 5 Publish shows a ring then draws a tick (item 1), 6 the drop line and outline ease in while a section is dragged
(item 5). Class More adds items 4, 7, 8 and 10 (the peek, the timeline and calendar swap, the handle's first-time hint, the Add a section preview). Part 1 reads the CSS: one Motion block, tokens only, nothing loops, no motion outside it. Part 2 runs the real
page in headless Chrome three ways: motion allowed (the effect runs), the computer asking for reduced motion, and clark's own
setting (<html data-motion="reduce">). In both reduced forms nothing animates and the still mark is all there is.
"""
import re
import sys
import time
import unittest

from _paths import SRC, TOOLS
import _testpage as testpage
import test_enrichments as te
import test_publish_dialog as tpd
import test_report_editor as tre
from test_server import Running, chrome

sys.path.insert(0, str(TOOLS))

from clark import page

CSS = te.CSS
_START = CSS.index("Motion:")
MOTION = CSS[_START:CSS.index("\n}\n", CSS.index("@media (prefers-reduced-motion: no-preference) {\n", _START)) + 3]     # the one block, not the rules after it
MODES = (("allowed", False, False), ("media", True, False), ("setting", False, True))
SECTION = {"allowed": "ABC-S-002", "media": "ABC-S-003", "setting": "ABC-S-004"}     # one each: a hidden section stays hidden
OWN = "document.documentElement.dataset.motion='reduce'"


class Rules(unittest.TestCase):
    def test_all_motion_is_in_one_block_gated_on_both_switches(self):
        self.assertEqual(CSS.count("@media (prefers-reduced-motion: no-preference) {\n"), 1)      # the one Motion block; an older one-line hover transition on table rows is not part of it
        self.assertIn(':root:not([data-motion="reduce"])', MOTION)
        outside = CSS[CSS.index("Loading placeholder:"):CSS.index("Motion:")]        # the rules this item added
        self.assertNotIn("animation", outside, "no animation anywhere but the Motion block")
        self.assertNotIn("@keyframes", outside)

    def test_only_tokens_set_a_time_or_an_easing_and_nothing_loops(self):
        # The one exception is the Publish ring, which turns only while the work is going on (the dialog says "Publishing…") and
        # is gone when it ends; the issue asks for it by name. Everything else runs once.
        self.assertEqual([x.strip() for x in re.findall(r"([^{}\s][^{}]*)\{[^}]*infinite", re.sub(r"/\*.*?\*/", "", MOTION, flags=re.S))], [".pub-spin"])
        for decl in re.findall(r"animation:([^;]+);", MOTION):
            if "infinite" in decl:
                self.assertRegex(decl, r"var\(--dur-[a-z]+\)")
                continue
            self.assertRegex(decl, r"var\(--dur-[a-z]+\)", decl)
            self.assertRegex(decl, r"var\(--ease-[a-z]+\)", decl)
            self.assertNotRegex(decl, r"(?<![-\w(])\d+(\.\d+)?m?s\b", "a literal time: " + decl)
            self.assertTrue(re.search(r"\b1\b|forwards", decl), "runs once: " + decl)

    def test_the_placeholder_overlay_never_takes_input(self):
        self.assertIn("pointer-events: none", re.search(r"\.skel-leave \{[^}]*\}", MOTION).group(0))

    def test_the_changed_mark_is_paint_only_and_adds_no_space(self):
        rules = re.findall(r"[^{}]*\.(?:is-changed|changed)\b[^{}]*\{[^}]*\}", CSS[:CSS.index("Motion:")])
        self.assertTrue(rules)
        for r in rules:
            self.assertIsNone(re.search(r"(?<![-\w])(margin|padding)[-\w]*\s*:|(?<![-\w])(border|width|height|top|left|transform)[-\w]*\s*:", r.split("{", 1)[1]), r)

    def test_the_still_forms_of_the_ring_and_the_tick_are_in_the_base_rules(self):
        base = CSS[:CSS.index("Motion:")]
        self.assertRegex(base, r"\.pub-spin \{[^}]*border-top-color")            # a still ring with one strong quarter
        self.assertRegex(base, r"\.pub-tick path \{[^}]*stroke-dashoffset: 0")   # the tick is fully drawn without motion
        self.assertIn("m-draw", MOTION)

    def test_the_words_are_unchanged_by_motion(self):
        self.assertIn('"Changed"', (SRC / "clark" / "page" / "src" / "stores" / "changed.js").read_text(encoding="utf-8").replace("'", '"'))


class Looks(tre.Base):
    def setUp(self):
        super().setUp()
        self.demo.action(description="Draft the cut-over plan", due_date="2026-11-01")
        done = self.demo.action(description="Book the training room")
        self.demo.update("actions", done, {"status": "Closed"})

    def go(self, cdp, hash_, mode):
        _, media, own = mode
        p = tre.Pg.at(self, cdp, self.s.port, hash_)
        if media:
            cdp.call("Emulation.setEmulatedMedia", {"features": te.REDUCE}, p.sid)
        p.ready() if hash_.startswith('#dashboard') else p.until("!!document.querySelector('#work-count')", 'the list drew')
        if own:
            p.js(OWN)
        return p

    def anim(self, p, sel):
        return p.js(f"(function(){{var e=document.querySelector({sel!r});return e?[getComputedStyle(e).animationName,e.getAnimations().length]:null;}})()")

    def test_a_changed_section_glows_once_then_holds_the_still_mark_and_stays_clickable(self):
        for mode in MODES:
            with self.subTest(mode=mode[0]), chrome() as cdp:
                p = self.go(cdp, "#dashboard&p=ABC", mode)
                p.edit()
                p.menu(SECTION[mode[0]], "hide")
                p.until("!!document.querySelector('.sec.is-changed')", "marked")
                name, running = self.anim(p, ".sec.is-changed")
                if mode[0] == "allowed":
                    self.assertEqual(name, "m-glow")
                    self.assertGreater(running, 0, "the glow is running")
                    self.assertEqual(p.js("getComputedStyle(document.querySelector('.sec.is-changed')).pointerEvents"), "auto", "input is not held up")
                    p.until("document.querySelector('.sec.is-changed').getAnimations().length === 0", "it ends by itself (it does not loop)", 3)
                else:
                    self.assertEqual((name, running), ("none", 0), "no movement")
                self.assertEqual(p.js("document.querySelector('.sec.is-changed .tag.chg').textContent"), "Changed", "the still mark is there either way")

    BOX = ("(function(s){var e=document.querySelector(s);var r=e.getBoundingClientRect();"
           "return [r.x,r.y,r.width,r.height].map(function(v){return Math.round(v*100)/100;});})")

    def shift(self, p, sel, cls, inner):
        """Box of the first match with the mark off, then on (after any glow has ended): returns both."""
        p.js(f"document.querySelector({sel!r}).dataset.t='1'")
        sel = "[data-t]"
        p.js(f"document.querySelector({sel!r}).classList.remove({cls!r})")
        off = p.js(f"{self.BOX}({sel!r})") + p.js(f"{self.BOX}({sel + ' ' + inner!r})")
        p.js(f"document.querySelector({sel!r}).classList.add({cls!r})")
        p.js(f"document.querySelector({sel!r}).getAnimations().forEach(function(a){{a.finish();}})")
        return off, p.js(f"{self.BOX}({sel!r})") + p.js(f"{self.BOX}({sel + ' ' + inner!r})")

    def test_the_changed_mark_moves_nothing_on_a_section_or_a_row(self):
        for mode in MODES:
            with self.subTest(mode=mode[0], what="section"), chrome() as cdp:
                p = self.go(cdp, "#dashboard&p=ABC", mode)
                p.edit()
                p.menu(SECTION[mode[0]], "hide")
                p.until("!!document.querySelector('.sec.is-changed')", "marked")
                off, on = self.shift(p, ".sec.is-changed", "is-changed", ".sec-h")
                self.assertEqual(off, on, "x, y, width and height of the section and of its heading are the same with and without the mark")
            with self.subTest(mode=mode[0], what="row"), chrome() as cdp:
                p = self.go(cdp, "#work&p=ABC", mode)
                p.js("document.querySelector('table.items tr[data-id]').classList.add('changed')")
                off, on = self.shift(p, "table.items tr.changed", "changed", "td:nth-child(2)")
                self.assertEqual(off, on, "the row and its text do not shift or resize")

    def test_the_health_badge_and_reason_settle_when_health_changes_and_not_on_the_first_draw(self):
        for mode in MODES:
            with self.subTest(mode=mode[0]), chrome() as cdp:
                p = self.go(cdp, "#dashboard&p=ABC", mode)
                p.until("!!document.querySelector('.hrow')", "the tile drew")
                self.assertEqual(p.js("document.querySelector('.hrow').classList.contains('settle')"), False, "not on the first draw")
                p.js("clarkPage.showHealth('At risk', 'Two things are late')")
                p.until("document.querySelector('.hreason') && document.querySelector('.hreason').textContent === 'Two things are late'", "health changed")
                if mode[0] == "allowed":
                    p.until("document.querySelector('.hrow').classList.contains('settle')", "it settles")
                    self.assertEqual(self.anim(p, ".hrow")[0], "m-settle")
                else:
                    self.assertFalse(p.js("document.querySelector('.hrow').classList.contains('settle')"), "no class, no movement")
                    self.assertEqual(self.anim(p, ".hrow")[0], "none")

    def test_the_count_line_fades_when_a_filter_changes_and_not_when_nothing_changed(self):
        for mode in MODES:
            with self.subTest(mode=mode[0]), chrome() as cdp:
                p = self.go(cdp, "#work&p=ABC", mode)
                p.until("!!document.querySelector('#work-count')", "the list drew")
                before = p.js("document.querySelector('#work-count').textContent")
                p.js("document.querySelector('[data-show=\"closed\"]').click()")
                p.until(f"document.querySelector('#work-count').textContent !== {before!r}", "the count changed")
                name, running = self.anim(p, "#work-count")
                if mode[0] == "allowed":
                    self.assertEqual(name, "m-in")
                    self.assertGreater(running, 0)
                    self.assertEqual(p.js("document.querySelector('[data-show=\"open\"]').disabled"), False, "the switches stay live")
                else:
                    self.assertEqual((name, running), ("none", 0))


    def test_the_drop_line_eases_in_while_a_section_is_dragged_and_is_still_in_either_reduced_form(self):
        for mode in MODES:
            with self.subTest(mode=mode[0]), chrome() as cdp:
                p = self.go(cdp, "#dashboard&p=ABC", mode)
                p.tall(cdp)
                p.edit()
                hx, hy, _ = p.box('[data-id="ABC-S-001"] [data-drag]')
                _, _, bottom = p.box('[data-id="ABC-S-003"]')
                ty = bottom - 3
                p.mouse("mousePressed", hx, hy, 1)
                for step in range(1, 9):
                    p.mouse("mouseMoved", hx, hy + (ty - hy) * step / 8, 1)
                p.until("!!document.querySelector('.sec.drop-before')", "a drop line while dragging")
                name, running = self.anim(p, ".sec.drop-before")
                if mode[0] == "allowed":
                    self.assertEqual(name, "m-line-top")
                    self.assertEqual(p.js("getComputedStyle(document.querySelector('.sec.drop-before')).pointerEvents"), "auto", "the page stays live")
                    p.until("document.querySelector('.sec.drop-before').getAnimations().length === 0", "it ends by itself", 3)
                else:
                    self.assertEqual((name, running), ("none", 0), "the line is simply there")
                self.assertNotEqual(p.js("getComputedStyle(document.querySelector('.sec.drop-before')).boxShadow"), "none", "the line is drawn")
                p.key("Escape", code="Escape", vk=27)          # cancel: nothing is dropped, so the next mode starts from the same order
                p.mouse("mouseReleased", hx, ty, 0)

    def test_the_half_width_outline_eases_in_and_is_still_when_reduced(self):
        for mode in MODES:
            with self.subTest(mode=mode[0]), chrome() as cdp:
                p = self.go(cdp, "#dashboard&p=ABC", mode)
                p.tall(cdp)
                p.edit()
                # add the class the page would give a half, so the outline is measured without needing two halves in the data
                p.js("document.querySelector('.secs > .sec').classList.add('drop-left')")
                got = p.js("(function(){var c=getComputedStyle(document.querySelector('.secs > .sec'),'::after');return [c.animationName,c.borderTopWidth];})()")
                self.assertEqual(got[1], "2px", "the outline is drawn")
                self.assertEqual(got[0], "m-outline" if mode[0] == "allowed" else "none")


class More(tre.Base):
    """The four motions on screens that are now built: the peek, the timeline and calendar swap, the handle's first-time hint and the
    Add a section preview. Each runs with motion allowed and is absent in both reduced forms."""

    def setUp(self):
        super().setUp()
        self.demo.action(description="Draft the cut-over plan", due_date="2026-11-01")
        self.demo.action(description="Book the training room")

    def go(self, cdp, hash_, mode):
        _, media, own = mode
        p = tre.Pg.at(self, cdp, self.s.port, hash_)
        if media:
            cdp.call("Emulation.setEmulatedMedia", {"features": te.REDUCE}, p.sid)
        if own:
            p.js(OWN)
        p.mode = mode
        return p

    def anim(self, p, sel):
        """Name and count of the running animations, after checking the motion setting under test is still in force."""
        _, media, own = p.mode
        if own:
            self.assertEqual(p.js("document.documentElement.dataset.motion"), "reduce", "the page's own setting is on")
        return p.js(f"(function(){{var e=document.querySelector({sel!r});return e?[getComputedStyle(e).animationName,e.getAnimations().length]:null;}})()")

    def test_the_peek_slides_in_and_its_body_fades_in_as_previous_and_next_step_on(self):
        for mode in MODES:
            with self.subTest(mode=mode[0]), chrome() as cdp:
                p = self.go(cdp, "#work&p=ABC", mode)
                p.until("!!document.querySelector('#work-count')", "the list drew")
                p.js("clarkPage.openPeek(document.querySelector('table.items tr[data-id]').dataset.id)")
                p.until("!!document.querySelector('#peek [data-pk-body]')", "the peek opened")
                panel = self.anim(p, "#peek")
                first = p.js("document.querySelector('#peek').dataset.peek")
                if mode[2]:
                    p.js(OWN)
                p.js("document.querySelector('#peek [data-pk-next]').click()")
                p.until(f"document.querySelector('#peek').dataset.peek !== {first!r}", "stepped to the next item")
                body = self.anim(p, "#peek [data-pk-body]")
                if mode[0] == "allowed":
                    self.assertEqual(body[0], "m-in")
                    self.assertGreater(body[1], 0, "the body fade is running")
                    self.assertEqual(p.js("document.querySelector('#peek [data-pk-prev]').disabled"), False, "Previous works at once")
                    self.assertEqual(p.js("getComputedStyle(document.querySelector('#peek')).pointerEvents"), "auto")
                else:
                    self.assertEqual(body, ["none", 0], "the body is simply there")
                    self.assertEqual(panel, ["none", 0], "the panel is simply there")
                self.assertGreater(p.js("document.querySelector('#peek [data-pk-body]').offsetHeight"), 0)
        with self.subTest(what="slide"), chrome() as cdp:
            p = self.go(cdp, "#work&p=ABC", MODES[0])
            p.until("!!document.querySelector('#work-count')", "the list drew")
            p.js("clarkPage.openPeek(document.querySelector('table.items tr[data-id]').dataset.id)")
            p.until("!!document.querySelector('#peek')", "the peek opened")
            self.assertTrue(p.js("document.getAnimations().some(function(a){return a.animationName === 'm-slide';})"), "the panel slides in")

    def test_the_timeline_and_calendar_swap_with_a_rise_and_a_fade(self):
        for mode in MODES:
            with self.subTest(mode=mode[0]), chrome() as cdp:
                p = self.go(cdp, "#milestones&p=ABC", mode)
                p.until("!!document.querySelector('[data-msvb=cal]')", "the switch drew")
                if mode[2]:
                    p.js(OWN)
                self.assertTrue(p.js("document.querySelector('.msv-swap').dataset.swap === 'line'"))
                p.js("document.querySelector('[data-msvb=cal]').click()")
                p.until("document.querySelector('.msv-swap').dataset.swap === 'cal'", "the calendar is shown")
                name, running = self.anim(p, ".msv-swap")
                if mode[0] == "allowed":
                    self.assertEqual(name, "m-rise")
                    self.assertGreater(running, 0)
                    self.assertEqual(p.js("document.querySelector('[data-msvb=line]').disabled"), False, "the switch stays live")
                else:
                    self.assertEqual((name, running), ("none", 0))

    def test_the_handle_pulses_once_the_first_time_in_edit_and_says_what_it_does(self):
        for mode in MODES:
            with self.subTest(mode=mode[0]), chrome() as cdp:
                p = self.go(cdp, "#dashboard&p=ABC", mode)
                p.ready()
                self.assertFalse(p.js("!!document.querySelector('.sec-hint')"), "not in View")
                p.edit()
                p.until("!!document.querySelector('.sec-ctl.hint')", "the hint shows the first time")
                self.assertEqual(p.js("document.querySelector('.sec-hint').textContent"), "Drag to move, + to add a template")
                name, running = self.anim(p, ".sec-ctl.hint .handle")
                if mode[0] == "allowed":
                    self.assertEqual(name, "m-pulse")
                    self.assertGreater(running, 0)
                    p.until("document.querySelector('.sec-ctl.hint .handle').getAnimations().length === 0", "the pulse ends by itself", 3)
                    self.assertEqual(p.js("document.querySelectorAll('.sec-ctl.hint').length"), 1, "one handle only")
                else:
                    self.assertEqual((name, running), ("none", 0), "the words show without a pulse")
                self.assertEqual(p.js("getComputedStyle(document.querySelector('.sec-hint')).pointerEvents"), "none", "it takes no input")
                p.js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'a'}))")
                p.until("!document.querySelector('.sec-hint')", "the next key press puts it away")
                p.view()
                p.edit()
                self.assertFalse(p.js("!!document.querySelector('.sec-hint')"), "only once")

    def test_the_add_a_section_preview_fades_as_the_selection_moves_and_cards_lift_on_hover(self):
        for mode in MODES:
            with self.subTest(mode=mode[0]), chrome() as cdp:
                p = self.go(cdp, "#dashboard&p=ABC", mode)
                p.ready()
                p.edit()
                p.js("document.querySelector('[data-id=\"ABC-S-001\"] [data-add]').click()")
                p.until("!!document.querySelector('.ad-prev h3')", "the dialog opened")
                if mode[2]:
                    p.js(OWN)
                p.js("document.querySelectorAll('.ad-tpl:not(.off) input')[1].click()")
                p.until("document.querySelector('.ad-prev h3').textContent === document.querySelectorAll('.ad-tpl:not(.off) .ad-tn')[1].textContent", "the preview moved")
                name, running = self.anim(p, ".ad-prev > h3")
                lift = p.js("getComputedStyle(document.querySelector('.ad-tpl')).transitionProperty")
                if mode[0] == "allowed":
                    self.assertEqual(name, "m-in")
                    self.assertGreater(running, 0)
                    self.assertIn("transform", lift, "cards lift on hover where there is a fine pointer")
                    self.assertEqual(p.js("document.querySelector('.ad [data-place]').disabled"), False, "the dialog stays usable")
                else:
                    self.assertEqual((name, running), ("none", 0))
                    self.assertNotIn("transform", lift)


class PublishLooks(tpd.Base):
    """The ring while Publish works and the tick when it is done. The reply is held in the page so the working state can be seen."""
    HOLD = """(function(){ var f = window.fetch.bind(window); window.__release = null;
      window.fetch = function(u, o){ if (String(u).indexOf('/api/publish') === 0 && o && o.method === 'POST') {
        return new Promise(function(res){ window.__release = function(){ res(f(u, o)); }; }); } return f(u, o); }; })()"""

    def test_a_ring_shows_while_it_works_then_a_tick_is_drawn_once(self):
        for mode in MODES:
            with self.subTest(mode=mode[0]), chrome() as cdp:
                p = self.page(cdp)
                _, media, own = mode
                if media:
                    cdp.call("Emulation.setEmulatedMedia", {"features": te.REDUCE}, p.sid)
                if own:
                    p.js(OWN)
                p.js(self.HOLD)
                p.open_publish()
                p.go()
                p.until("!!document.querySelector('.pub-spin')", "the ring is shown while it works")
                self.assertEqual(p.message(), "Publishing…")
                self.assertEqual(p.js("document.querySelector('[data-go]').disabled"), True, "no second publish while it works")
                spin = p.js("(function(){var e=document.querySelector('.pub-spin');return [getComputedStyle(e).animationName,e.getAnimations().length];})()")
                if mode[0] == "allowed":
                    self.assertEqual(spin[0], "m-spin")
                    self.assertGreater(spin[1], 0)
                else:
                    self.assertEqual(spin, ["none", 0], "a still ring")
                    self.assertGreater(p.js("document.querySelector('.pub-spin').offsetWidth"), 0, "and it is there")
                self.assertEqual(p.js("document.querySelector('[data-cancel]').disabled"), True)
                p.js("window.__release()")
                p.until("document.querySelector('[data-go]').innerText === 'Close'", "published")
                self.assertFalse(p.js("!!document.querySelector('.pub-spin')"), "the ring is gone when the work ends")
                self.assertTrue(p.js("!!document.querySelector('#pub-msg .pub-tick')"), "the tick is shown")
                self.assertTrue(p.message(), "and the words are still there")
                tick = p.js("(function(){var e=document.querySelector('.pub-tick path');var c=getComputedStyle(e);return [c.animationName,c.strokeDashoffset,e.getAnimations().length];})()")
                if mode[0] == "allowed":
                    self.assertEqual(tick[0], "m-draw", "drawn")
                    p.until("document.querySelector('.pub-tick path').getAnimations().every(function(a){return a.playState === 'finished';})", "it draws once and stops", 3)
                self.assertEqual(p.js("getComputedStyle(document.querySelector('.pub-tick path')).strokeDashoffset"), "0px", "fully drawn at the end, or at once when still")
                if mode[0] != "allowed":
                    self.assertEqual(tick[0], "none")
                self.assertTrue(p.js("document.querySelector('[data-go]').disabled === false"), "Close works")


class Fade(tre.Base):
    """The placeholder fades out over --dur-instant on top of the arriving screen; in either reduced form it is never drawn again."""
    WATCH = """(function(){ window.__fade = {seen: false, name: null, pe: null, aria: null};
      new MutationObserver(function(){ var k = document.querySelector('.skel-leave');
        if (k && !window.__fade.seen) { var c = getComputedStyle(k); window.__fade = {seen: true, name: c.animationName, pe: c.pointerEvents, aria: k.getAttribute('aria-hidden')}; }
      }).observe(document, {childList: true, subtree: true, attributes: true}); })()"""
    OWN_EARLY = "new MutationObserver(function(m,o){ if (document.documentElement) { document.documentElement.dataset.motion='reduce'; o.disconnect(); } }).observe(document,{childList:true}); if (document.documentElement) document.documentElement.dataset.motion='reduce';"

    def test_it_fades_out_once_the_data_arrives_and_is_not_drawn_in_either_reduced_form(self):
        gate = {"open": False}

        def data_for(code):
            end = time.time() + 20
            while not gate["open"] and time.time() < end:
                time.sleep(0.02)
            return self.store.data_for(code)
        s = Running(data_for=data_for, page_html=lambda: testpage.html())
        self.addCleanup(s.close)
        for mode in MODES:
            with self.subTest(mode=mode[0]), chrome() as cdp:
                gate["open"] = False
                sid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
                sid = cdp.call("Target.attachToTarget", {"targetId": sid, "flatten": True})["sessionId"]
                cdp.call("Page.enable", {}, sid)
                cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": self.WATCH + (self.OWN_EARLY if mode[2] else "")}, sid)
                if mode[1]:
                    cdp.call("Emulation.setEmulatedMedia", {"features": te.REDUCE}, sid)
                cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#work&p=ABC"}, sid)
                p = tre.Pg(self, cdp, sid)
                p.until("!!document.querySelector('.skel-frame')", "the placeholder appeared")
                gate["open"] = True
                p.until("!!document.querySelector('main h1:not(.sr)') && !document.querySelector('.skel-frame:not(.skel-leave)')", "the screen replaced it")
                if mode[0] == "allowed":
                    p.until("window.__fade.seen", "it was kept to fade out")
                    f = p.js("window.__fade")
                    self.assertEqual((f["name"], f["pe"], f["aria"]), ("m-out", "none", "true"))
                    p.until("!document.querySelector('.skel-leave')", "it is gone when the fade ends", 3)
                else:
                    time.sleep(0.4)
                    self.assertFalse(p.js("window.__fade.seen"), "never drawn when the page may not move")
                    self.assertFalse(p.js("!!document.querySelector('.skel-leave')"))


if __name__ == "__main__":
    unittest.main()
