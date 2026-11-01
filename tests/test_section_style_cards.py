"""Settings › Personal › Dashboard sections: the four picture cards (a drawing, the name, one line), in a real browser at 1400 and
900 px, light and dark. Run: python3 dev/run_tests.py test_section_style_cards

What is asserted: four cards, each with a drawing and one real radio, in a radio group named Dashboard sections; the arrow keys move
the choice, which applies to the page at once and survives a reload; the chosen card shows a 2 px edge in the brand blue and a tick,
and no other card does; the keyboard focus ring is 2 px in the brand blue; the card text is at least 13 px and 4.5:1, the card edge and
the ring 3:1; the drawing is made of the tokens and can be seen in light and dark; the four cards sit in one row at 1400 and wrap at
900 with no sideways scroll; and the note under Personal says only what is true: the file a publish makes carries the style (a word in
its data block), but nothing yet gives it the choice made here (it is kept in the browser), so the published page is Slim gaps.
Chrome is required: these tests fail, never skip, without it.
"""
import json
import re
import time
import unittest

from _paths import SRC
from test_glance import ON, RULES, data, sections
from test_publish_dialog import Base
from test_server import chrome

from clark import publish

WIDTHS = (1400, 900)
LOOKS = ("light", "dark")
NAMES = ["Slim gaps", "Roomy gaps", "Grey headers", "One card"]
IDS = ["slim", "roomy", "grey", "card"]
NOTE = "These are for you, on this computer. The section style is used on the published report too; Light or Dark is yours alone."

# Colour maths, in the page: a computed colour is rgb(...) or rgba(...); a clear one is looked through to what is behind it.
JS_HELPERS = """
window.__rgb = (c) => (c.match(/[\\d.]+/g) || []).slice(0, 3).map(Number);
window.__lum = (c) => { const [r, g, b] = __rgb(c).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
window.__ratio = (a, b) => { const x = __lum(a), y = __lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
window.__behind = (el) => { for (let e = el; e; e = e.parentElement) { const c = getComputedStyle(e).backgroundColor; if (!/rgba\\(.*, 0\\)|transparent/.test(c)) return c; } return 'rgb(255, 255, 255)'; };
window.__token = (name) => { const s = document.createElement('i'); s.style.color = 'var(' + name + ')'; document.body.appendChild(s); const c = getComputedStyle(s).color; s.remove(); return c; };
"""
GROUP = "document.querySelector('#personal [data-secstyles]')"
CARDS = "[...document.querySelectorAll('#personal [data-secstyles] .secpick')]"


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
        p.js("document.querySelector('#profile-menu [data-kind=settings]').click()")
        p.until("!!document.querySelector('#personal')", "Settings › Personal drew")
        p.js(f"document.querySelector('#personal [data-appearance] input[value={look}]').click()")
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
        return p.js("[...document.querySelectorAll('input[name=secstyle]')].filter(i => i.checked).map(i => i.value)")

    def test_C_four_cards_each_with_a_drawing_and_one_real_radio_in_a_named_group(self):
        def check(p, w, look):
            self.assertEqual(p.js(f"{GROUP}.getAttribute('role')"), "radiogroup")
            self.assertEqual(p.js(f"{GROUP}.querySelector('legend').textContent"), "Dashboard sections", "the group's name")
            self.assertEqual(p.js(f"{CARDS}.length"), 4)
            self.assertEqual(p.js(f"{CARDS}.map(c => c.querySelector('b').textContent)"), NAMES)
            self.assertEqual(p.js(f"{CARDS}.map(c => c.querySelectorAll('input[type=radio]').length)"), [1, 1, 1, 1], "one real radio per card")
            self.assertEqual(p.js(f"{CARDS}.map(c => c.querySelector('input').value)"), IDS)
            self.assertEqual(p.js(f"{CARDS}.map(c => c.querySelector('input').name)"), ["secstyle"] * 4, "one group of radios")
            self.assertEqual(p.js(f"{CARDS}.map(c => c.querySelector('small').textContent.length > 10)"), [True] * 4, "a line each")
            self.assertEqual(p.js(f"{CARDS}.map(c => c.querySelector('.secpick-pic').getAttribute('aria-hidden'))"), ["true"] * 4, "the drawing is not read out")
            self.assertEqual(p.js(f"{CARDS}.map(c => [...c.querySelectorAll('.secpick-pic i')].filter(i => i.getBoundingClientRect().height > 4).length)"),
                             [3, 3, 3, 3], "each drawing shows three parts")
            self.assertEqual(p.js("document.querySelectorAll('#personal img, #personal [src], #personal [style*=url]').length"), 0, "no picture files")
            self.assertEqual(p.js(f"{CARDS}.map(c => c.querySelector('input').getBoundingClientRect().height >= 24)"), [True] * 4, "targets are at least 24 px")
            self.assertEqual(self.chosen(p), ["slim"], "Slim gaps is the default")

        self.each_look(check)

    def test_C_the_drawings_differ_and_can_be_seen(self):
        def check(p, w, look):
            shapes = p.js(f"{CARDS}.map(c => [...c.querySelectorAll('.secpick-pic i')].map(i => {{ const r = i.getBoundingClientRect(), t = c.querySelector('.secpick-pic').getBoundingClientRect().top; const s = getComputedStyle(i); return [Math.round(r.top - t), Math.round(r.height), s.backgroundImage !== 'none']; }}).join('|'))")
            self.assertEqual(len(set(shapes)), 4, "four different drawings")
            # the drawing's header bar and its block edges stand out from the picture they sit on (3:1)
            seen = p.js(f"{CARDS}.map(c => {{ const pic = c.querySelector('.secpick-pic'), bg = getComputedStyle(pic).backgroundColor, is = pic.querySelectorAll('i'); "
                        "return [__ratio(getComputedStyle(is[0]).backgroundColor, bg), __ratio(getComputedStyle(is[1]).borderTopColor, bg)]; })")
            for bar, edge in seen:
                self.assertGreaterEqual(bar, 3, "the header bar reads on the picture")
                self.assertGreaterEqual(edge, 3, "the block edges read on the picture")
            self.assertEqual(p.js(f"{CARDS}.map(c => [...c.querySelectorAll('.secpick-pic i')].map(i => i.style.cssText).join(''))"), [""] * 4, "tokens in the sheet only")

        self.each_look(check)

    def test_C_layout_one_row_at_1400_and_wraps_at_900_with_no_sideways_scroll(self):
        def check(p, w, look):
            rows = p.js(f"new Set({CARDS}.map(c => Math.round(c.getBoundingClientRect().top))).size")
            if w == 1400:
                self.assertEqual(rows, 1, "four across")
            else:
                self.assertGreater(rows, 1, "wrapped")
                tops = p.js(f"{CARDS}.map(c => Math.round(c.getBoundingClientRect().top))")
                self.assertEqual([tops.count(t) for t in sorted(set(tops))], [3, 1], "three and one")
            self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")
            self.assertTrue(p.js(f"{CARDS}.every(c => {{ const r = c.getBoundingClientRect(); return r.left >= 0 && r.right <= window.innerWidth; }})"), "every card is on the screen")

        self.each_look(check)

    def test_C_arrows_move_the_choice_it_applies_at_once_and_survives_a_reload(self):
        def check(p, w, look):
            p.js("document.querySelector('input[name=secstyle]:checked').focus()")
            for key, want in (("ArrowRight", "roomy"), ("ArrowRight", "grey"), ("ArrowRight", "card"), ("ArrowLeft", "grey")):
                p.key(key, code=key, vk=39 if key == "ArrowRight" else 37)
                p.until(f"document.documentElement.dataset.secstyle === '{want}'", f"{key} chose {want}, applied at once")
                self.assertEqual(self.chosen(p), [want], "one choice")
                self.assertEqual(p.js("document.activeElement.value"), want, "focus went with it")
            p.js("document.querySelector('input[name=secstyle][value=card]').closest('label').click()")
            p.until("document.documentElement.dataset.secstyle === 'card'", "a click on the card chooses it")
            self.assertEqual(self.chosen(p), ["card"])
            p.js("window.__before = 1; location.reload()")
            settled(p, "window.__before === undefined && !!document.querySelector('#profile-btn')", "reloaded")
            self.assertEqual(p.js("document.documentElement.dataset.secstyle"), "card", "kept for the page")
            p.js("document.querySelector('#profile-btn').click()")
            p.until("!!document.querySelector('#profile-menu [data-kind=settings]')", "menu")
            p.js("document.querySelector('#profile-menu [data-kind=settings]').click()")
            p.until("!!document.querySelector('#personal [data-secstyles]')", "Personal again")
            self.assertEqual(self.chosen(p), ["card"], "and kept for the Settings card")

        self.each_look(check)

    def test_C_the_choice_shows_on_the_dashboard(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            gap = []
            for value in ("slim", "roomy"):
                p.js(f"document.querySelector('input[name=secstyle][value={value}]').closest('label').click()")
                p.until(f"document.documentElement.dataset.secstyle === '{value}'", value)
                p.js("location.hash = '#dashboard&p=PUB'")
                p.until("!!document.querySelector('.secs')", "dashboard")
                gap.append(p.js("parseFloat(getComputedStyle(document.querySelector('.secs')).rowGap)"))
                p.js("document.querySelector('#profile-btn').click()")
                p.until("!!document.querySelector('#profile-menu [data-kind=settings]')", "menu")
                p.js("document.querySelector('#profile-menu [data-kind=settings]').click()")
                p.until("!!document.querySelector('#personal [data-secstyles]')", "Personal")
            self.assertGreater(gap[1], gap[0], "Roomy gaps are roomier than Slim gaps")

    def test_C_selected_is_an_edge_and_a_tick_not_colour_alone(self):
        def check(p, w, look):
            for pick in IDS:
                p.js(f"document.querySelector('input[name=secstyle][value={pick}]').closest('label').click()")
                p.until(f"document.querySelector('input[name=secstyle][value={pick}]').checked && document.documentElement.dataset.secstyle === '{pick}'", f"{pick} chosen")
                # the edge eases from one colour to the other, so it is read once it has arrived
                p.until(f"{CARDS}.every(c => (getComputedStyle(c.querySelector('.secpick-card')).borderTopColor === __token('--brand-blue')) === c.querySelector('input').checked && (getComputedStyle(c.querySelector('.secpick-card')).boxShadow === 'none') === !c.querySelector('input').checked && (!c.querySelector('input').checked || getComputedStyle(c.querySelector('.secpick-card')).boxShadow.includes(__token('--brand-blue'))))", "the edges settled")
                got = stable(p, f"{CARDS}.map(c => {{ const k = c.querySelector('.secpick-card'), s = getComputedStyle(k), t = getComputedStyle(c.querySelector('.secpick-tick')), r = c.querySelector('.secpick-tick').getBoundingClientRect(); "
                           "return {on: c.querySelector('input').checked, edge: s.borderTopColor, edgeW: parseFloat(s.borderTopWidth), ring: s.boxShadow, tick: t.display !== 'none' && r.width > 10 && r.height > 10, "
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

    def test_C_hover_changes_the_edge_and_focus_has_a_two_pixel_blue_ring(self):
        def check(p, w, look):
            p.js("document.querySelector('input[name=secstyle]:checked').focus()")
            p.key("ArrowRight", code="ArrowRight", vk=39)           # a key makes the focus show as a keyboard one
            p.until("document.documentElement.dataset.secstyle === 'roomy'", "moved")
            ring = p.js("(() => { const k = document.querySelector('input[name=secstyle]:focus-visible + .secpick-card'); if (!k) return null; const s = getComputedStyle(k); "
                        "return {w: parseFloat(s.outlineWidth), style: s.outlineStyle, c: s.outlineColor, blue: __token('--brand-blue'), bg: __behind(k.parentElement)}; })()")
            self.assertIsNotNone(ring, "the focused card shows a ring")
            self.assertEqual((ring["w"], ring["style"], ring["c"]), (2.0, "solid", ring["blue"]))
            self.assertGreaterEqual(p.js(f"__ratio({json.dumps(ring['c'])}, {json.dumps(ring['bg'])})"), 3, "the ring is 3:1 on the page")
            p.js("document.activeElement.blur()")
            before = p.js(f"getComputedStyle({CARDS}[2].querySelector('.secpick-card')).borderTopColor")
            box = p.js(f"(() => {{ const r = {CARDS}[2].getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }})()")
            p.cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": box[0], "y": box[1]}, p.sid)
            p.until(f"getComputedStyle({CARDS}[2].querySelector('.secpick-card')).borderTopColor !== {json.dumps(before)}", "hover changed the edge")

        self.each_look(check)

    def test_C_text_and_edges_are_readable_in_light_and_dark(self):
        def check(p, w, look):
            got = p.js(f"{CARDS}.map(c => {{ const k = c.querySelector('.secpick-card'), bg = getComputedStyle(k).backgroundColor, b = c.querySelector('b'), s = c.querySelector('small'); "
                       "return {name: __ratio(getComputedStyle(b).color, bg), line: __ratio(getComputedStyle(s).color, bg), nameSize: parseFloat(getComputedStyle(b).fontSize), lineSize: parseFloat(getComputedStyle(s).fontSize), "
                       "edge: __ratio(getComputedStyle(k).borderTopColor, __behind(c)), row: Math.round(c.getBoundingClientRect().top), h: Math.round(k.getBoundingClientRect().height)}; })")
            for g in got:
                self.assertGreaterEqual(g["name"], 4.5, "the name is 4.5:1")
                self.assertGreaterEqual(g["line"], 4.5, "the line is 4.5:1")
                self.assertGreaterEqual(g["nameSize"], 13)
                self.assertGreaterEqual(g["lineSize"], 13)
                self.assertGreaterEqual(g["edge"], 3, "the card's edge is 3:1 on the page")
            for row in {g["row"] for g in got}:
                self.assertEqual(len({g["h"] for g in got if g["row"] == row}), 1, "the cards in a row are one height")
            page_light = p.js("__lum(__behind(document.querySelector('.secpick'))) > 0.5")
            self.assertEqual(page_light, look == "light", "the page is really in the look asked for")

        self.each_look(check)

    def test_C_the_note_and_the_order_match_the_prototype(self):
        def check(p, w, look):
            self.assertEqual(p.js("document.querySelector('#personal > p.muted').textContent"), NOTE)

        self.each_look(check)
        # The group comes first, before Appearance, and its lines are the prototype's.
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.assertEqual(p.js("[...document.querySelectorAll('#personal > fieldset legend')].map(l => l.textContent).slice(0, 3)"),
                             ["Dashboard sections", "Appearance", "About you"])
            self.assertEqual(p.js(f"{CARDS}.map(c => c.querySelector('small').textContent)"), [
                "Each section is its own card, with a slim gap that shows the page picture.", "The same, with more space between the sections.",
                "Slim gaps, and each section title in a grey band, like the Work items groups.", "All the sections in one long card."])
        # What the note claims: the file carries a style word (its data block), slim unless one of the four is given.
        for name in publish.STYLES:
            self.assertEqual(self.block({"section_style": name})["style"], name, "the file can carry any of the four")
        self.assertEqual(self.block({})["style"], "slim", "with no style given, the file is Slim gaps")
        self.assertEqual(self.block({"section_style": "wide"})["style"], "slim")
        kept = [f.name for f in sorted((SRC / "clark" / "page" / "src").rglob("*.js*")) if "clark.section-style" in f.read_text(encoding="utf-8")]
        self.assertEqual(kept, ["style.js"], "the choice is kept in the browser only")

    def test_C_the_chosen_card_is_in_the_published_file_and_the_preview(self):
        # The page sends the chosen style with Publish; the file's own data block carries it (the published page has no route and no Settings).
        for pick in IDS:
            with self.subTest(pick=pick), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p)
                p.js(f"document.querySelector('#personal input[name=secstyle][value={pick}]').click()")
                p.until(f"document.documentElement.dataset.secstyle === '{pick}'", "the choice applied")
                self.rig.save_to = self.rig.local / f"{pick}.html"
                p.open_publish()
                p.go()
                p.until("document.querySelector('[data-go]').innerText === 'Close'", "published")
                text = (self.rig.local / f"{pick}.html").read_text(encoding="utf-8")
                got = json.loads(re.search(r'id="clark-data">(.*?)</script>', text, re.S).group(1))
                self.assertEqual(got["style"], pick)
                p.js("document.querySelector('[data-go]').click()")
        status, got = self.rig.publish(section_style="roomy")
        self.assertEqual((status, got["ok"]), (200, True))
        status, got = self.rig.call("POST", "/api/preview", {"project": "PUB", "section_style": "grey"})
        self.assertEqual(status, 200)
        shown = self.rig.call("GET", got["url"])[1]
        self.assertIn(b'"style":"grey"', shown)

    def test_a_word_that_is_not_a_style_publishes_slim_and_none_publishes_slim(self):
        for body in ({"section_style": "wide"}, {"section_style": 3}, {}):
            self.rig.save_to = self.rig.local / "x.html"
            if self.rig.save_to.exists():
                self.rig.save_to.unlink()
            status, got = self.rig.publish(**body)
            self.assertEqual((status, got["ok"]), (200, True), body)
            self.assertIn('"style":"slim"', self.rig.save_to.read_text(encoding="utf-8"), body)

    def block(self, extra):
        d = data()
        i = {"data": d, "hidden": [], "sections": sections(), "label_rules": RULES, "as_at": ON, "glance_tiles": [], **extra}
        text = publish.data_block(publish.add_glance(publish.select(i), i), ON)
        return json.loads(re.search(r">(.*)</script>", text, re.S).group(1))


if __name__ == "__main__":
    unittest.main()
