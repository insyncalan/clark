"""Settings › Personal › Spacing (item 1025, PR 1 of 8): the two picture cards, Compact and Comfortable (a drawing, the name, one line), in a
real browser at 1400 and 900 px, light and dark. Run: python3 dev/run_tests.py test_section_style_cards

What is asserted: two cards, each with a drawing and one real radio, in a radio group named Spacing; the arrow keys move the choice, which
applies to the page at once (html[data-density]) and survives a reload under the one key clark.density; Compact is the default for a
person who has chosen nothing, and an unknown stored word is as no choice; the old key clark.section-style is never read or written;
the chosen card shows a 2 px edge in the brand blue and a tick, and no other card does; the focus ring is 2 px in the brand blue; the
card text is at least 13 px and 4.5:1, the edge and ring 3:1; the two cards sit in one row at both widths with no sideways scroll; and
the bridge to the guarded publish code (which still speaks the old section words, see the plan on item 1025): Compact publishes as
"card" and Comfortable as "slim", and a file carrying "slim" opens Comfortable while any other word opens Compact.
Chrome is required: these tests fail, never skip, without it.
"""
import json
import re
import time
import unittest

from _paths import SRC
from test_publish_dialog import Base
from test_server import chrome

WIDTHS = (1400, 900)
LOOKS = ("light", "dark")
NAMES = ["Compact", "Comfortable"]
IDS = ["compact", "comfortable"]
NOTE = "These are for you, on this computer. Your spacing choice is used on the published report too; Light or Dark is yours alone."

# Colour maths, in the page: a computed colour is rgb(...) or rgba(...); a clear one is looked through to what is behind it.
JS_HELPERS = """
window.__rgb = (c) => (c.match(/[\\d.]+/g) || []).slice(0, 3).map(Number);
window.__lum = (c) => { const [r, g, b] = __rgb(c).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
window.__ratio = (a, b) => { const x = __lum(a), y = __lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
window.__behind = (el) => { for (let e = el; e; e = e.parentElement) { const c = getComputedStyle(e).backgroundColor; if (!/rgba\\(.*, 0\\)|transparent/.test(c)) return c; } return 'rgb(255, 255, 255)'; };
window.__token = (name) => { const s = document.createElement('i'); s.style.color = 'var(' + name + ')'; document.body.appendChild(s); const c = getComputedStyle(s).color; s.remove(); return c; };
"""
GROUP = "document.querySelector('#personal [data-density-pick]')"
CARDS = "[...document.querySelectorAll('#personal [data-density-pick] .secpick')]"


def stable(p, expr, seconds=2.0, every=0.05):
    """Sample a page expression until two samples in a row are equal (a colour eased by a transition has arrived), at most `seconds`;
    returns the last sample, so an assertion on it fails with the real value."""
    last = p.js(expr)
    end = time.time() + seconds
    while time.time() < end:
        time.sleep(every)
        now = p.js(expr)
        if now == last:
            return now
        last = now
    return last


def settled(p, expr, what, seconds=15):
    """p.until, but a page that is navigating (a reload in flight) is waited out: Chrome says 'Inspected target navigated or closed'
    to a call made in that gap, and the next poll sees the new page. Any other error still fails."""
    def ask():
        try:
            return p.js(expr)
        except RuntimeError as e:
            if "navigated or closed" in str(e):
                return False
            raise
    end = time.time() + seconds
    while time.time() < end:
        if ask():
            return
        time.sleep(0.1)
    p.t.fail(what)


class Cards(Base):
    def open_settings(self, p, look="light"):
        p.js("document.querySelector('#profile-btn').click()")
        p.until("!!document.querySelector('#profile-menu')", "the menu opened")
        p.js("document.querySelector('#profile-menu [data-kind=settings], #profile-menu [data-kind=who]').click()")
        p.until("!!document.querySelector('#personal')", "Settings › Personal drew")
        p.js(f"document.querySelector('#personal [data-appearance] button[data-theme-pick={look}]').click()")
        p.until("document.documentElement.dataset.theme === 'dark'" if look == "dark" else "!document.documentElement.dataset.theme", f"{look} is on")
        p.js(JS_HELPERS)
        p.until("document.body.offsetHeight > 0 && getComputedStyle(document.querySelector('.secpick:not(:hover) input:not(:checked) + .secpick-card')).borderTopColor === __token('--grey-700')",
                "the cards have taken the look")

    def each_look(self, check):
        """check(p, w, look) in a fresh browser for each width and look."""
        for w in WIDTHS:
            for look in LOOKS:
                with self.subTest(width=w, look=look), chrome() as cdp:
                    p = self.page(cdp)
                    p.width(w)
                    self.open_settings(p, look)
                    check(p, w, look)

    def chosen(self, p):
        return p.js("[...document.querySelectorAll('input[name=density]')].filter(i => i.checked).map(i => i.value)")

    def test_C_two_cards_each_with_a_drawing_and_one_real_radio_in_a_named_group(self):
        def check(p, w, look):
            self.assertEqual(p.js(f"{GROUP}.getAttribute('role')"), "radiogroup")
            self.assertEqual(p.js(f"{GROUP}.querySelector('legend').textContent"), "Spacing", "the group's name")
            self.assertEqual(p.js(f"{CARDS}.map(c => c.querySelector('b').textContent)"), NAMES)
            self.assertEqual(p.js(f"{CARDS}.map(c => c.querySelectorAll('input[type=radio]').length)"), [1, 1], "one real radio per card")
            self.assertEqual(p.js(f"{CARDS}.map(c => c.querySelector('input').value)"), IDS)
            self.assertEqual(p.js(f"{CARDS}.map(c => c.querySelector('input').name)"), ["density"] * 2, "one group of radios")
            self.assertEqual(p.js(f"{CARDS}.map(c => c.querySelector('small').textContent.length > 10)"), [True] * 2, "a line each")
            self.assertEqual(p.js(f"{CARDS}.map(c => c.querySelector('.secpick-pic').getAttribute('aria-hidden'))"), ["true"] * 2, "the drawing is not read out")
            self.assertEqual(p.js(f"{CARDS}.map(c => [...c.querySelectorAll('.secpick-pic i')].filter(i => i.getBoundingClientRect().height > 4).length)"), [3, 3], "each drawing shows three parts")
            self.assertEqual(p.js("document.querySelectorAll('#personal img, #personal [src], #personal [style*=url]').length"), 0, "no picture files")
            self.assertEqual(p.js(f"{CARDS}.map(c => c.querySelector('input').getBoundingClientRect().height >= 24)"), [True] * 2, "targets are at least 24 px")
            self.assertEqual(self.chosen(p), ["compact"], "Compact is the default for a person who has chosen nothing")
            self.assertEqual(p.js("document.documentElement.dataset.density"), "compact")
            self.assertEqual(p.js("localStorage.getItem('clark.density')"), None, "the default is not written down as a choice")

        self.each_look(check)

    def test_C_a_stored_choice_is_kept_and_a_missing_or_unknown_one_gets_compact(self):
        for stored, want in (("comfortable", "comfortable"), ("compact", "compact"), ("card", "compact"), ("slim", "compact"), ("wide", "compact"), (None, "compact")):
            with self.subTest(stored=stored), chrome() as cdp:
                p = self.page(cdp)
                p.js("localStorage.removeItem('clark.density')" if stored is None else f"localStorage.setItem('clark.density', '{stored}')")
                p.js("window.__before = 1; location.reload()")
                settled(p, "window.__before === undefined && !!document.querySelector('#profile-btn')", "reloaded")
                settled(p, f"document.documentElement.dataset.density === '{want}'", f"the page is {want}")
                p.js("document.querySelector('#profile-btn').click()")
                p.until("!!document.querySelector('#profile-menu')", "the menu opened")
                p.js("document.querySelector('#profile-menu [data-kind=settings], #profile-menu [data-kind=who]').click()")
                p.until("!!document.querySelector('#personal')", "Settings › Personal drew")
                self.assertEqual(self.chosen(p), [want], "the card marked is the one in force")
                self.assertEqual(p.js("localStorage.getItem('clark.density')"), stored, "a stored choice is not changed by opening the page")

    def test_C_the_old_key_is_neither_read_nor_written(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.js("localStorage.setItem('clark.section-style', 'slim')")
            p.js("window.__before = 1; location.reload()")
            settled(p, "window.__before === undefined && !!document.querySelector('#profile-btn')", "reloaded")
            self.assertEqual(p.js("document.documentElement.dataset.density"), "compact", "the old key does not choose")
            self.open_settings(p)
            p.js("document.querySelector('input[name=density][value=comfortable]').closest('label').click()")
            p.until("document.documentElement.dataset.density === 'comfortable'", "chosen")
            self.assertEqual(p.js("localStorage.getItem('clark.section-style')"), "slim", "the old key is left as it was")
        src = SRC / "clark" / "page" / "src"
        self.assertEqual([f.name for f in sorted(src.rglob("*.js*")) if "clark.section-style" in f.read_text(encoding="utf-8")], [], "no source names the old key")
        self.assertEqual([f.name for f in sorted(src.rglob("*.js*")) if "clark.density" in f.read_text(encoding="utf-8")], ["density.js"],
                         "the choice is kept in the browser only, under one key")

    def test_C_layout_one_row_with_no_sideways_scroll(self):
        def check(p, w, look):
            self.assertEqual(p.js(f"new Set({CARDS}.map(c => Math.round(c.getBoundingClientRect().top))).size"), 1, "two across")
            self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")
            self.assertTrue(p.js(f"{CARDS}.every(c => {{ const r = c.getBoundingClientRect(); return r.left >= 0 && r.right <= window.innerWidth; }})"), "every card is on the screen")

        self.each_look(check)

    def test_C_arrows_move_the_choice_it_applies_at_once_and_survives_a_reload(self):
        def check(p, w, look):
            p.js("document.querySelector('input[name=density]:checked').focus()")
            for key, want in (("ArrowRight", "comfortable"), ("ArrowLeft", "compact"), ("ArrowRight", "comfortable")):
                p.key(key, code=key, vk=39 if key == "ArrowRight" else 37)
                p.until(f"document.documentElement.dataset.density === '{want}'", f"{key} chose {want}, applied at once")
                self.assertEqual(self.chosen(p), [want], "one choice")
                self.assertEqual(p.js("document.activeElement.value"), want, "focus went with it")
            self.assertEqual(p.js("localStorage.getItem('clark.density')"), "comfortable")
            p.js("window.__before = 1; location.reload()")
            settled(p, "window.__before === undefined && !!document.querySelector('#profile-btn')", "reloaded")
            self.assertEqual(p.js("document.documentElement.dataset.density"), "comfortable", "kept for the page")
            p.js("document.querySelector('#profile-btn').click()")
            p.until("!!document.querySelector('#profile-menu [data-kind=settings], #profile-menu [data-kind=who]')", "menu")
            p.js("document.querySelector('#profile-menu [data-kind=settings], #profile-menu [data-kind=who]').click()")
            p.until("!!document.querySelector('#personal [data-density-pick]')", "Personal again")
            self.assertEqual(self.chosen(p), ["comfortable"], "and kept for the Settings card")

        self.each_look(check)

    def test_C_the_drawings_differ_and_can_be_seen(self):
        def check(p, w, look):
            shapes = p.js(f"{CARDS}.map(c => [...c.querySelectorAll('.secpick-pic i')].map(i => {{ const r = i.getBoundingClientRect(), t = c.querySelector('.secpick-pic').getBoundingClientRect().top; const s = getComputedStyle(i); return [Math.round(r.top - t), Math.round(r.height), s.backgroundImage !== 'none']; }}).join('|'))")
            self.assertEqual(len(set(shapes)), 2, "two different drawings")
            # the drawing's header bar and its block edges stand out from the picture they sit on (3:1)
            seen = p.js(f"{CARDS}.map(c => {{ const pic = c.querySelector('.secpick-pic'), bg = getComputedStyle(pic).backgroundColor, is = pic.querySelectorAll('i'); "
                        "return [__ratio(getComputedStyle(is[0]).backgroundColor, bg), __ratio(getComputedStyle(is[1]).borderTopColor, bg)]; })")
            for bar, edge in seen:
                self.assertGreaterEqual(bar, 3, "the header bar reads on the picture")
                self.assertGreaterEqual(edge, 3, "the block edges read on the picture")
            self.assertEqual(p.js(f"{CARDS}.map(c => [...c.querySelectorAll('.secpick-pic i')].map(i => i.style.cssText).join(''))"), [""] * 2, "tokens in the sheet only")

        self.each_look(check)

    def test_C_the_choice_shows_on_the_dashboard(self):
        # Chosen in Settings with the real cards, then read on the Dashboard: Compact runs the sections on in one flat page (no shadow, square),
        # Comfortable makes each section its own card (a shadow, round corners), which is what the Settings and Help lines say.
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            look = {}
            for value in ("comfortable", "compact"):
                p.js(f"document.querySelector('input[name=density][value={value}]').closest('label').click()")
                p.until(f"document.documentElement.dataset.density === '{value}'", value)
                p.js("location.hash = '#dashboard&p=PUB'")
                p.until("!!document.querySelector('.secs .sec')", "dashboard")
                look[value] = p.js("(() => { const s = getComputedStyle(document.querySelector('.secs .sec')); return [s.boxShadow === 'none', s.backgroundColor, s.borderTopLeftRadius]; })()")
                p.js("document.querySelector('#profile-btn').click()")
                p.until("!!document.querySelector('#profile-menu [data-kind=settings], #profile-menu [data-kind=who]')", "menu")
                p.js("document.querySelector('#profile-menu [data-kind=settings], #profile-menu [data-kind=who]').click()")
                p.until("!!document.querySelector('#personal [data-density-pick]')", "Personal")
            self.assertEqual(look["compact"][0], True, "Compact sections have no card shadow")
            self.assertEqual(look["compact"][2], "0px", "Compact sections are flat")
            self.assertEqual(look["comfortable"][0], False, "Comfortable sections are cards with a shadow")
            self.assertNotEqual(look["comfortable"][2], "0px", "Comfortable sections have round corners")
            self.assertNotEqual(look["comfortable"][1], look["compact"][1], "the two do not look the same")

    def test_C_selected_is_an_edge_and_a_tick_not_colour_alone(self):
        def check(p, w, look):
            for pick in IDS:
                p.js(f"document.querySelector('input[name=density][value={pick}]').closest('label').click()")
                p.until(f"document.querySelector('input[name=density][value={pick}]').checked && document.documentElement.dataset.density === '{pick}'", f"{pick} chosen")
                # the edge eases from one colour to the other, so it is read once it has arrived
                p.until(f"{CARDS}.every(c => (getComputedStyle(c.querySelector('.secpick-card')).borderTopColor === __token('--brand-blue')) === c.querySelector('input').checked && (getComputedStyle(c.querySelector('.secpick-card')).boxShadow === 'none') === !c.querySelector('input').checked && (!c.querySelector('input').checked || getComputedStyle(c.querySelector('.secpick-card')).boxShadow.includes(__token('--brand-blue'))))", "the edges settled")
                got = stable(p, f"{CARDS}.map(c => {{ const k = c.querySelector('.secpick-card'), s = getComputedStyle(k), t = getComputedStyle(c.querySelector('.secpick-tick')), r = c.querySelector('.secpick-tick').getBoundingClientRect(); "
                           "return {on: c.querySelector('input').checked, edge: s.borderTopColor, ring: s.boxShadow, tick: t.display !== 'none' && r.width > 10 && r.height > 10, "
                           "tickBg: t.backgroundColor, tickFg: t.color, blue: __token('--brand-blue')}; })")
                self.assertEqual([g["on"] for g in got], [i == pick for i in IDS])
                for g in got:
                    if g["on"]:
                        self.assertEqual(g["edge"], g["blue"], "the edge is the brand blue")
                        self.assertIn(g["blue"], g["ring"], "doubled to 2 px")
                        self.assertTrue(g["tick"], "a tick is drawn")
                        self.assertEqual(g["tickBg"], g["blue"])
                    else:
                        self.assertFalse(g["tick"], "no tick on the others")
                        self.assertNotEqual(g["edge"], g["blue"])
                        self.assertEqual(g["ring"], "none")
                self.assertGreaterEqual(p.js(f"__ratio({json.dumps(got[0]['tickFg'])}, {json.dumps(got[0]['tickBg'])})"), 4.5, "the tick shows on its disc")

        self.each_look(check)

    def test_C_focus_has_a_two_pixel_blue_ring(self):
        def check(p, w, look):
            p.js("document.querySelector('input[name=density]:checked').focus()")
            p.key("ArrowRight", code="ArrowRight", vk=39)           # a key makes the focus show as a keyboard one
            p.until("document.documentElement.dataset.density === 'comfortable'", "moved")
            ringed = 'document.querySelector("input[name=density]:focus-visible + .secpick-card")'
            p.until(f"{ringed} !== null && getComputedStyle({ringed}).outlineStyle === 'solid'", "the focused card shows a ring")      # a bounded wait on the focus state, not one read
            ring = p.js("(() => { const k = document.querySelector('input[name=density]:focus-visible + .secpick-card'); if (!k) return null; const s = getComputedStyle(k); "
                        "return {w: parseFloat(s.outlineWidth), style: s.outlineStyle, c: s.outlineColor, blue: __token('--brand-blue'), bg: __behind(k.parentElement)}; })()")
            self.assertIsNotNone(ring, "the focused card shows a ring")
            self.assertEqual((ring["w"], ring["style"], ring["c"]), (2.0, "solid", ring["blue"]))
            self.assertGreaterEqual(p.js(f"__ratio({json.dumps(ring['c'])}, {json.dumps(ring['bg'])})"), 3, "the ring is 3:1 on the page")

        self.each_look(check)

    def test_C_hover_changes_the_edge(self):
        def check(p, w, look):
            p.js(f"{CARDS}[1].scrollIntoView({{block: 'center'}})")       # the cards sit below the first screen: the pointer must be over one
            before = p.js(f"getComputedStyle({CARDS}[1].querySelector('.secpick-card')).borderTopColor")
            box = p.js(f"(() => {{ const r = {CARDS}[1].getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }})()")
            p.cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": box[0], "y": box[1]}, p.sid)
            p.until(f"getComputedStyle({CARDS}[1].querySelector('.secpick-card')).borderTopColor !== {json.dumps(before)}", "hover changed the edge")

        self.each_look(check)

    def test_C_text_and_edges_are_readable_in_light_and_dark(self):
        def check(p, w, look):
            got = p.js(f"{CARDS}.map(c => {{ const k = c.querySelector('.secpick-card'), bg = getComputedStyle(k).backgroundColor, b = c.querySelector('b'), s = c.querySelector('small'); "
                       "return {name: __ratio(getComputedStyle(b).color, bg), line: __ratio(getComputedStyle(s).color, bg), nameSize: parseFloat(getComputedStyle(b).fontSize), lineSize: parseFloat(getComputedStyle(s).fontSize), "
                       "edge: __ratio(getComputedStyle(k).borderTopColor, __behind(c))}; })")
            for g in got:
                self.assertGreaterEqual(g["name"], 4.5, "the name is 4.5:1")
                self.assertGreaterEqual(g["line"], 4.5, "the line is 4.5:1")
                self.assertGreaterEqual(g["nameSize"], 13)
                self.assertGreaterEqual(g["lineSize"], 13)
                self.assertGreaterEqual(g["edge"], 3, "the card's edge is 3:1 on the page")
            self.assertEqual(p.js("__lum(__behind(document.querySelector('.secpick'))) > 0.5"), look == "light", "the page is really in the look asked for")

        self.each_look(check)

    def test_C_the_note_the_order_and_the_words(self):
        def check(p, w, look):
            self.assertEqual(p.js("document.querySelector('#personal > p.muted').textContent"), NOTE)

        self.each_look(check)
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.assertEqual(p.js("[...document.querySelectorAll('#personal > fieldset legend')].map(l => l.textContent).slice(0, 3)"), ["Spacing", "Appearance", "Keys"])
            self.assertEqual(p.js(f"{CARDS}.map(c => c.querySelector('small').textContent)"), [
                "The Dashboard sections run on in one flat page, with thin lines between them, so more fits on the screen.", "Each Dashboard section is its own card, with room between them."])

    def test_C_the_choice_goes_to_publish_as_the_word_the_guarded_code_knows(self):
        # The bridge: Compact is "card", Comfortable is "slim" (publish.STYLES). Nothing else is ever sent.
        for pick, word in (("compact", "card"), ("comfortable", "slim")):
            with self.subTest(pick=pick), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p)
                p.js(f"document.querySelector('#personal input[name=density][value={pick}]').click()")
                p.until(f"document.documentElement.dataset.density === '{pick}'", "the choice applied")
                self.assertEqual(p.js("document.documentElement.dataset.secstyle"), word, "the Dashboard section rules still key on the old word")
                self.rig.save_to = self.rig.local / f"{pick}.html"
                p.open_publish()
                p.go()
                p.until("document.querySelector('[data-go]').classList.contains('ok')", "published")
                text = (self.rig.local / f"{pick}.html").read_text(encoding="utf-8")
                got = json.loads(re.search(r'id="clark-data">(.*?)</script>', text, re.S).group(1))
                self.assertEqual(got["style"], word)
                p.js("document.querySelector('[data-go]').click()")

    def test_the_reading_of_a_files_word_is_slim_for_comfortable_and_compact_for_the_rest(self):
        src = (SRC / "clark" / "page" / "src" / "stores" / "density.js").read_text(encoding="utf-8")
        self.assertIn('densityOfWord = (w) => (w === "slim" ? "comfortable" : DEFAULT_DENSITY)', src)
        self.assertIn('sectionWord = (d) => (d === "comfortable" ? "slim" : "card")', src)

    def test_the_guarded_code_is_unchanged_it_refuses_a_word_it_does_not_know_and_defaults_to_slim(self):
        for body in ({"section_style": "wide"}, {"section_style": 3}):
            self.rig.save_to = self.rig.local / "x.html"
            if self.rig.save_to.exists():
                self.rig.save_to.unlink()
            status, got = self.rig.publish(**body)
            self.assertEqual((status, got["ok"]), (400, False), body)
            self.assertFalse(self.rig.save_to.exists(), body)
        self.rig.save_to = self.rig.local / "x.html"
        status, got = self.rig.publish()
        self.assertEqual((status, got["ok"]), (200, True))
        self.assertIn('"style":"slim"', self.rig.save_to.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
