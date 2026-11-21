"""Row 1298 (DRAFT, NOT RUN): the Feedback tag as drawn, in headless Chrome. Run: python3 dev/run_tests.py test_feedback_tag_browser_1298
Where the tag shows (Help, Settings but not Version and updates), the dialog, the keyboard, the slide, the offset beside a peek, light and dark, at 1400 and 900 px only
(no phone width). Real page over the fictional demo data. Required: fails, never skips, without Chrome. The names of the Settings and Help addresses (#settings&p=TUL&s=...)
and of the Help peek are read from the code, not yet run; selectors marked ASSUMED must be checked on the first run."""
import json
import unittest

import test_filter_line_keys as K
import _testpage as testpage
from test_filter_line_keys import tearDownModule  # noqa: F401
from test_server import chrome, wait
from test_work_items import page_target

WIDTHS = (1400, 900)
THEMES = ("light", "dark")
SETTINGS_PAGES = ("projects", "people", "profile", "folder", "brand", "appearance", "reports", "backups", "data", "claude", "logs")
BAR = "document.querySelector('#feedback-tag')"
DLG = "document.querySelector('#feedback-tag-dialog')"
CLIP = "window.__clip"


class FeedbackTagBrowser(unittest.TestCase):
    def setUp(self):
        K.Keys.setUp(self)
        self.s.httpd.page_html = lambda: testpage.html()      # the served page has no window.clarkPage; the test page adds it (as test_bulk_bar does)
    read = K.Keys.read

    def open_page(self, cdp, width):
        """The keys test's open_page does not hand back its session, so attach once more to the same page and keep it as self.sid."""
        K.Keys.open_page(self, cdp, width)
        self.sid = page_target(cdp)
        return self.sid
    press = K.Keys.press
    who = K.Keys.who

    def look(self, cdp, sid, theme, reduce=True):
        feats = [{"name": "prefers-color-scheme", "value": theme}, {"name": "prefers-reduced-motion", "value": "reduce" if reduce else "no-preference"}]
        cdp.call("Emulation.setEmulatedMedia", {"features": feats}, sid)

    def go(self, cdp, sid, hash_):
        cdp.js(f"location.hash = {json.dumps(hash_)}", sid)

    def has_tag(self, cdp, sid):
        return cdp.js(f"!!{BAR} && {BAR}.getClientRects().length > 0", sid)

    def open_help(self, cdp, sid):
        cdp.js("window.clarkPage.help.open()", sid)   # the one door (helpStore.openHelp); "?" on Work opens the Help peek, not Help
        self.assertTrue(wait(lambda: self.has_tag(cdp, sid)), "Help drew the tag")

    def each(self):
        """(cdp, sid, where) for width x theme."""
        with chrome() as cdp:
            for width in WIDTHS:
                for theme in THEMES:
                    self.open_page(cdp, width)
                    sid = self.sid
                    self.look(cdp, sid, theme)
                    yield cdp, sid, f"{width} px {theme}"

    # ---- per view
    def test_tag_in_help(self):
        for cdp, sid, where in self.each():
            self.open_help(cdp, sid)
            self.assertEqual(cdp.js(f"{BAR}.textContent", sid), "Feedback", where)
            self.assertEqual(cdp.js(f"{BAR}.getAttribute('aria-label')", sid), "Give feedback", where)
            self.assertEqual(cdp.js(f"{BAR}.getAttribute('aria-expanded')", sid), "false", where)

    def test_tag_in_each_settings_page_but_version(self):
        for cdp, sid, where in self.each():
            for page in SETTINGS_PAGES:
                self.go(cdp, sid, f"#settings&p=TUL&s={page}")
                self.assertTrue(wait(lambda: self.has_tag(cdp, sid)), f"{where}: tag on Settings {page}")
            self.go(cdp, sid, "#settings&p=TUL&s=version")
            self.assertTrue(wait(lambda: not self.has_tag(cdp, sid)), f"{where}: no tag on Version and updates")

    def test_no_tag_on_work_milestones_dashboard_usecases(self):
        for cdp, sid, where in self.each():
            for view in ("work", "milestones", "dashboard", "usecases"):
                self.go(cdp, sid, f"#{view}&p=TUL")
                self.assertTrue(wait(lambda: not self.has_tag(cdp, sid)), f"{where}: no tag on {view}")

    def test_tag_position_right_edge_below_middle(self):
        for cdp, sid, where in self.each():
            self.open_help(cdp, sid)
            r = json.loads(cdp.js(f"JSON.stringify({BAR}.getBoundingClientRect())", sid))
            self.assertEqual(round(r["right"]), cdp.js("document.documentElement.clientWidth", sid), where)   # a vertical scrollbar takes its width off the fixed edge
            self.assertGreater(r["top"] + r["height"] / 2, 450 * .5, where)
            self.assertLessEqual(r["bottom"], 900, where)

    # ---- dialog
    def test_click_opens_dialog_and_focuses_message(self):
        for cdp, sid, where in self.each():
            self.open_help(cdp, sid)
            cdp.js(f"{BAR}.click()", sid)
            self.assertTrue(wait(lambda: cdp.js(f"!!{DLG}", sid)), where)
            self.assertEqual(cdp.js(f"{DLG}.getAttribute('role')", sid), "dialog", where)
            self.assertTrue(wait(lambda: cdp.js("document.activeElement.id", sid) == "fbt-message"), f"{where}: the message box has the focus, not {cdp.js('document.activeElement.id', sid)!r}")
            self.assertEqual(cdp.js(f"{BAR}.getAttribute('aria-expanded')", sid), "true", where)

    def test_kinds_default_problem_and_click_changes(self):
        for cdp, sid, where in self.each():
            self.open_help(cdp, sid)
            cdp.js(f"{BAR}.click()", sid)
            on = "JSON.stringify([...document.querySelectorAll('[data-fbt-kind]')].filter(b => b.getAttribute('aria-checked') === 'true').map(b => b.dataset.fbtKind))"
            self.assertEqual(json.loads(cdp.js(on, sid)), ["Problem"], where)
            cdp.js("document.querySelector('[data-fbt-kind=Idea]').click()", sid)
            self.assertEqual(json.loads(cdp.js(on, sid)), ["Idea"], where)

    def test_mail_link_href_only_with_words_and_empty_press_shows_the_error(self):
        for cdp, sid, where in self.each():
            self.open_help(cdp, sid)
            cdp.js(f"{BAR}.click()", sid)
            self.assertFalse(cdp.js("document.querySelector('[data-fbt-mail]').hasAttribute('href')", sid), where)     # row 1342: shown always, no address until there are words
            self.assertFalse(cdp.js("document.querySelector('[data-fbt-copy]').disabled", sid), where)
            cdp.js("(() => { const t = document.querySelector('#fbt-message'); t.focus(); document.execCommand('insertText', false, 'The page is slow'); })()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-fbt-mail]').hasAttribute('href')", sid)), where)
            self.assertTrue(cdp.js("document.querySelector('[data-fbt-mail]').href.startsWith('mailto:')", sid), where)
            self.assertFalse(cdp.js("document.querySelector('[data-fbt-copy]').disabled", sid), where)

    def test_copy_refused_shows_the_text(self):
        for cdp, sid, where in self.each():
            cdp.js("navigator.clipboard.writeText = () => Promise.reject(new Error('no'))", sid)
            self.open_help(cdp, sid)
            cdp.js(f"{BAR}.click()", sid)
            cdp.js("(() => { const t = document.querySelector('#fbt-message'); t.focus(); document.execCommand('insertText', false, 'Words'); })()", sid)
            cdp.js("document.querySelector('[data-fbt-copy]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#fbt-shown')", sid)), where)
            self.assertTrue(cdp.js("document.querySelector('#fbt-shown').value.startsWith('To:')", sid), where)

    # ---- keyboard
    def test_enter_opens_escape_closes_and_help_stays(self):
        for cdp, sid, where in self.each():
            self.open_help(cdp, sid)
            self.assertTrue(wait(lambda: (cdp.js(f"{BAR}.focus()", sid), cdp.js("document.activeElement.id", sid) == "feedback-tag")[1]), where + ": the tag takes the focus (Help may move it to its search box first)")
            self.press(cdp, sid, "Enter")
            self.assertTrue(wait(lambda: cdp.js(f"!!{DLG}", sid)), where + ": Enter opens")
            self.assertTrue(wait(lambda: cdp.js("document.activeElement.id", sid) == "fbt-message"), where + ": the dialog has taken the focus (its listeners are in)")
            self.press(cdp, sid, "Escape")
            self.assertTrue(wait(lambda: cdp.js(f"!{DLG}", sid)), where + ": Esc closes")
            self.assertEqual(cdp.js("document.activeElement.id", sid), "feedback-tag", where + ": focus back on the tag")
            self.assertTrue(self.has_tag(cdp, sid), where + ": Help is still open (first Esc closed only the dialog)")

    def test_close_button_returns_focus_to_tag(self):
        for cdp, sid, where in self.each():
            self.open_help(cdp, sid)
            cdp.js(f"{BAR}.click()", sid)
            cdp.js("document.querySelector('[data-fbt-close]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js(f"!{DLG}", sid)), where)
            self.assertEqual(cdp.js("document.activeElement.id", sid), "feedback-tag", where)

    def test_every_control_in_the_dialog_has_a_name_and_no_positive_tab_stop(self):
        for cdp, sid, where in self.each():
            self.open_help(cdp, sid)
            cdp.js(f"{BAR}.click()", sid)
            bad = cdp.js(f"JSON.stringify([...{DLG}.querySelectorAll('button, a, textarea')].filter(e => !(e.getAttribute('aria-label') || e.textContent || '').trim() && e.id !== 'fbt-message' || e.tabIndex > 0).map(e => e.outerHTML.slice(0, 60)))", sid)
            self.assertEqual(json.loads(bad), [], where)

    # ---- slide and offset
    def test_slide_in_from_the_right_and_tag_moves_beside_it(self):
        with chrome() as cdp:
            for width in WIDTHS:
                for theme in THEMES:
                    self.open_page(cdp, width)
                    sid = self.sid
                    self.look(cdp, sid, theme, reduce=False)
                    self.open_help(cdp, sid)
                    cdp.js(f"{BAR}.click()", sid)
                    self.assertTrue(wait(lambda: cdp.js(f"!!{DLG}", sid)))
                    self.assertEqual(cdp.js(f"getComputedStyle({DLG}).animationName", sid), "fbt-in", f"{width} {theme}")
                    self.assertTrue(wait(lambda: cdp.js(f"{DLG}.getAnimations().every(a => a.playState === 'finished')", sid)), "slide finished")
                    width = cdp.js("document.documentElement.clientWidth", sid)      # the scrollbar's width is off the fixed edge
                    self.assertEqual(round(cdp.js(f"{DLG}.getBoundingClientRect().right", sid)), width)
                    self.assertEqual(round(cdp.js(f"{DLG}.getBoundingClientRect().width", sid)), 360)
                    self.assertTrue(wait(lambda: round(cdp.js(f"{BAR}.getBoundingClientRect().right", sid)) == width - 360), "tag beside the dialog")

    def test_slide_in_easing_and_distance_are_pinned(self):
        """Row 1298 follow-up: the dialog's slide is 0.4 s on cubic-bezier(.22, 1, .36, 1), translateX(100%) to 0 (pins the CSS values, not just the animation's name)."""
        with chrome() as cdp:
            for width in WIDTHS:
                self.open_page(cdp, width)
                sid = self.sid
                self.look(cdp, sid, "light", reduce=False)
                self.open_help(cdp, sid)
                cdp.js(f"{BAR}.click()", sid)
                self.assertTrue(wait(lambda: cdp.js(f"!!{DLG}", sid)))
                where = f"{width} px"
                self.assertEqual(cdp.js(f"getComputedStyle({DLG}).animationDuration", sid), "0.4s", where)
                self.assertEqual(cdp.js(f"getComputedStyle({DLG}).animationTimingFunction", sid), "cubic-bezier(0.22, 1, 0.36, 1)", where)
                frames = cdp.js(f"{DLG}.getAnimations()[0].effect.getKeyframes().map(k => k.transform)", sid)
                self.assertEqual(frames, ["translateX(100%)", "translateX(0px)"], where)

    def test_tag_pulls_out_five_px_on_hover_and_on_focus(self):
        """Row 1298 follow-up: the tag's padding-right is 7 px at rest and 12 px (+5) on hover and on keyboard focus; the transition is 0.15 s (padding) and 0.3 s (right)."""
        pad = f"parseFloat(getComputedStyle({BAR}).paddingRight)"
        with chrome() as cdp:
            for width in WIDTHS:
                self.open_page(cdp, width)
                sid = self.sid
                self.look(cdp, sid, "light", reduce=False)
                self.open_help(cdp, sid)
                where = f"{width} px"
                self.assertEqual(cdp.js(pad, sid), 7, where + ": at rest")
                self.assertEqual(cdp.js(f"getComputedStyle({BAR}).transitionProperty", sid), "padding-right, right", where)
                self.assertEqual(cdp.js(f"getComputedStyle({BAR}).transitionDuration", sid), "0.15s, 0.3s", where)
                self.assertEqual(cdp.js(f"getComputedStyle({BAR}).transitionTimingFunction", sid), "cubic-bezier(0.25, 1, 0.5, 1), cubic-bezier(0.22, 1, 0.36, 1)", where)
                box = cdp.js(f"(() => {{ const r = {BAR}.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }})()", sid)
                cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": box[0], "y": box[1]}, sid)
                self.assertTrue(wait(lambda: cdp.js(f"{BAR}.matches(':hover') && {pad} === 12", sid)), where + ": hover pulls out +5 px")
                cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 2, "y": 2}, sid)
                self.assertTrue(wait(lambda: cdp.js(pad, sid) == 7), where + ": back at rest")
                self.press(cdp, sid, "Tab")
                self.press(cdp, sid, "Tab", shift=True)
                cdp.js(f"{BAR}.focus()", sid)
                self.assertTrue(wait(lambda: cdp.js(f"{BAR}.matches(':focus-visible') && {pad} === 12", sid)), where + ": focus pulls out +5 px")

    def test_approved_words_exactly(self):
        """Row 1298 follow-up: the dialog's lead line and the tag's aria-label are exactly the approved words."""
        for cdp, sid, where in self.each():
            self.open_help(cdp, sid)
            self.assertEqual(cdp.js(f"{BAR}.getAttribute('aria-label')", sid), "Give feedback", where)
            cdp.js(f"{BAR}.click()", sid)
            self.assertTrue(wait(lambda: cdp.js(f"!!{DLG}", sid)), where)
            self.assertEqual(cdp.js(f"{DLG}.querySelector('.fbt-head + p').textContent", sid), "Tell us what is wrong or what you would like to see.", where)

    def test_reduced_motion_has_no_slide(self):
        for cdp, sid, where in self.each():
            self.open_help(cdp, sid)
            cdp.js(f"{BAR}.click()", sid)
            self.assertTrue(wait(lambda: cdp.js(f"!!{DLG}", sid)), where)
            self.assertEqual(cdp.js(f"getComputedStyle({DLG}).animationName", sid), "none", where)

    def test_tag_beside_the_help_peek_and_back(self):
        """On a Settings page the Help peek opens through the test page's own door (the tag is not drawn on Work, where the peek mostly is)."""
        for cdp, sid, where in self.each():
            self.go(cdp, sid, "#settings&p=TUL&s=profile")
            self.assertTrue(wait(lambda: self.has_tag(cdp, sid)), where)
            self.assertTrue(cdp.js("window.clarkPage.help.peek.open()", sid), where + ": the peek opened")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#help-peek') && document.getAnimations().every(a => a.playState === 'finished')", sid)), where + ": the peek is open and still")
            edge = "document.querySelector('#help-peek').getBoundingClientRect().left"
            self.assertTrue(wait(lambda: round(cdp.js(f"{BAR}.getBoundingClientRect().right", sid)) == round(cdp.js(edge, sid))), where + ": the tag sits at the peek's left edge")
            cdp.js("window.clarkPage.help.peek.close()", sid)
            self.assertTrue(wait(lambda: round(cdp.js(f"{BAR}.getBoundingClientRect().right", sid)) == cdp.js("document.documentElement.clientWidth", sid)), where + ": back at the edge")

    def test_enter_in_the_dialog_does_not_close_it(self):
        """Only Esc closes: Enter in the message box is a new line, and the dialog stays (kills Escape -> Enter in the dialog's key handler)."""
        for cdp, sid, where in self.each():
            self.open_help(cdp, sid)
            cdp.js(f"{BAR}.click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.activeElement.id", sid) == "fbt-message"), where)
            cdp.js("document.execCommand('insertText', false, 'One')", sid)
            self.press(cdp, sid, "Enter")
            cdp.js("document.execCommand('insertText', false, 'Two')", sid)
            self.assertTrue(cdp.js(f"!!{DLG}", sid), where + ": still open after Enter")
            self.assertEqual(cdp.js("document.querySelector('#fbt-message').value", sid).replace("\r", ""), "One\nTwo", where + ": Enter made a new line")

    def test_tag_beside_the_item_peek_at_its_own_width(self):
        """The item peek is dragged (and can span the screen): the tag follows its real left edge, not a fixed 420 px (Help opens over an open item peek)."""
        for cdp, sid, where in self.each():
            rid = cdp.js("[...document.querySelectorAll('#work-list tr[data-id]')].map(r => r.dataset.id)[0]", sid)
            cdp.js(f"clarkPage.openPeek({json.dumps(rid)}, 'item')", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek')", sid)), where)
            self.open_help(cdp, sid)
            edge = "document.querySelector('#peek').getBoundingClientRect().left"
            still = "document.getAnimations().every(a => a.playState === 'finished')"
            self.assertTrue(wait(lambda: cdp.js(still, sid) and round(cdp.js(f"{BAR}.getBoundingClientRect().right", sid)) == round(cdp.js(edge, sid))), where + ": at the peek's left edge")
            if cdp.js("document.documentElement.clientWidth", sid) >= 1000:      # under 1000 px the peek spans the window and cannot be dragged
                first = round(cdp.js(edge, sid))
                cdp.js("(e => { e.focus(); e.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowLeft', bubbles: true})); })(document.querySelector('.pk-edge'))", sid)
                self.assertTrue(wait(lambda: round(cdp.js(edge, sid)) < first), where + ": the peek widened")
                self.assertTrue(wait(lambda: cdp.js(still, sid) and round(cdp.js(f"{BAR}.getBoundingClientRect().right", sid)) == round(cdp.js(edge, sid))), where + ": the tag followed")
            cdp.js("clarkPage.closePeek()", sid)
            self.assertTrue(wait(lambda: round(cdp.js(f"{BAR}.getBoundingClientRect().right", sid)) == cdp.js("document.documentElement.clientWidth", sid)), where + ": back at the edge")

    def test_dialog_is_over_the_tag_and_fits_the_window(self):
        for cdp, sid, where in self.each():
            self.open_help(cdp, sid)
            cdp.js(f"{BAR}.click()", sid)
            r = json.loads(cdp.js(f"JSON.stringify({DLG}.getBoundingClientRect())", sid))
            self.assertLessEqual(r["bottom"], 900, where)
            self.assertGreaterEqual(r["left"], 0, where)
            self.assertGreater(int(cdp.js(f"getComputedStyle({DLG}).zIndex", sid)), int(cdp.js(f"getComputedStyle({BAR}).zIndex", sid)), where)

    # ---- contrast
    def test_text_contrast_4_5_to_1_in_both_themes(self):
        lum = """(() => { const L = c => { const [r, g, b] = c.map(v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }); return .2126 * r + .7152 * g + .0722 * b; };
          const rgb = s => (s.match(/[\\d.]+/g) || [0, 0, 0, 1]).map(Number);
          const back = el => { for (let e = el; e; e = e.parentElement) { const c = rgb(getComputedStyle(e).backgroundColor); if (c.length < 4 || c[3] > 0) return c.slice(0, 3); } return [255, 255, 255]; };
          const low = [];
          for (const el of document.querySelectorAll('#feedback-tag, #feedback-tag-dialog h2, #feedback-tag-dialog label, #feedback-tag-dialog button, #feedback-tag-dialog p, #fbt-added, #fbt-added li')) {
            if (!el.getClientRects().length || !el.textContent.trim()) continue;
            const a = L(rgb(getComputedStyle(el).color).slice(0, 3)), b = L(back(el)), ratio = (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
            if (ratio < 4.5) low.push([el.id || el.className || el.tagName, el.textContent.slice(0, 20), ratio.toFixed(2)]); }
          return JSON.stringify(low); })()"""
        for cdp, sid, where in self.each():
            self.open_help(cdp, sid)
            cdp.js(f"{BAR}.click()", sid)
            self.assertEqual(json.loads(cdp.js(lum, sid)), [], where)

    def test_the_tag_shows_a_focus_ring_by_keyboard(self):
        for cdp, sid, where in self.each():
            self.open_help(cdp, sid)
            self.press(cdp, sid, "Tab")
            self.press(cdp, sid, "Tab", shift=True)
            cdp.js(f"{BAR}.focus()", sid)
            self.assertTrue(cdp.js(f"{BAR}.matches(':focus-visible') && parseFloat(getComputedStyle({BAR}).outlineWidth) >= 2", sid), where)

    def test_no_tag_while_the_search_shows_the_feedback_card(self):
        """Row 1298 point 4: Settings search shows every matching card; with the Feedback card among them the tag stands aside, and returns when it is gone."""
        def type_q(cdp, sid, q):
            cdp.js("var b = document.getElementById('set-search-box'); b.focus(); b.value = %s; b.dispatchEvent(new Event('input', { bubbles: true }))" % json.dumps(q), sid)
        card = "(function(){var h = document.getElementById('feedback-h'); var c = h && h.closest('section, .setting'); return !!c && !c.hidden && c.getClientRects().length > 0;})()"
        for cdp, sid, where in self.each():
            self.go(cdp, sid, "#settings&p=TUL&s=profile")
            self.assertTrue(wait(lambda: self.has_tag(cdp, sid)), where)
            type_q(cdp, sid, "feedback")
            self.assertTrue(wait(lambda: cdp.js(card, sid)), where + ": search shows the Feedback card")
            self.assertTrue(wait(lambda: not self.has_tag(cdp, sid)), where + ": so no tag")
            type_q(cdp, sid, "name")
            self.assertTrue(wait(lambda: not cdp.js(card, sid)), where + ": a search without the card")
            self.assertTrue(wait(lambda: self.has_tag(cdp, sid)), where + ": the tag is back")
            type_q(cdp, sid, "")
            self.assertTrue(wait(lambda: self.has_tag(cdp, sid)), where + ": cleared")

    # ---- leaving
    def test_the_dialog_closes_on_leaving_help_or_settings(self):
        for cdp, sid, where in self.each():
            self.go(cdp, sid, "#settings&p=TUL&s=profile")
            self.assertTrue(wait(lambda: self.has_tag(cdp, sid)), where)
            cdp.js(f"{BAR}.click()", sid)
            self.assertTrue(wait(lambda: cdp.js(f"!!{DLG}", sid)), where)
            self.go(cdp, sid, "#work&p=TUL&f=mode:all")
            self.assertTrue(wait(lambda: cdp.js(f"!{DLG} && !{BAR}", sid)), where)

    # ---- row 1298: the mail button uses the open-mail route (row 1297), as Settings, Feedback does
    def test_mail_click_goes_through_mailClick(self):
        note = "No mail app opened. Use Copy as text and paste it into your mail."
        stub = ("window.__posts = []; window.fetch = (u, i) => { window.__posts.push([String(u), i && i.body]); "
                "return Promise.resolve(new Response(JSON.stringify(%s), {status: %d})); }")
        notes = "document.querySelectorAll('[data-mail-note]').length"
        # The stub keeps EVERY fetch the page makes; the page's own heartbeat (every 10 s) is one too, and on a slow runner it lands between the
        # stub and the click, so the count is of calls to the route only, and the failure text lists what was recorded.
        route = "window.__posts.filter((p) => p[0] === '/api/open-mail')"
        for cdp, sid, where in self.each():
            self.open_help(cdp, sid)
            cdp.js(f"{BAR}.click()", sid)
            cdp.js("(() => { const t = document.querySelector('#fbt-message'); t.focus(); document.execCommand('insertText', false, 'The page is slow'); })()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-fbt-mail]').hasAttribute('href')", sid)), where)
            href = cdp.js("document.querySelector('[data-fbt-mail]').getAttribute('href')", sid)
            hash_ = cdp.js("location.hash", sid)
            cdp.js(stub % ('{"ok": true}', 200), sid)
            cdp.js("document.querySelector('[data-fbt-mail]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js(route + ".length", sid) == 1),
                            where + ": one call to the route; recorded " + str(cdp.js("JSON.stringify(window.__posts.map((p) => p[0]))", sid)))
            url, body = json.loads(cdp.js("JSON.stringify(" + route + "[0])", sid))
            self.assertEqual(url, "/api/open-mail", where)
            self.assertEqual(json.loads(body), {"link": href}, where)
            self.assertEqual(cdp.js(notes, sid), 0, where + ": no note on success")
            self.assertEqual(cdp.js("location.hash", sid), hash_, where + ": no navigation to the mailto: link")
            cdp.js(stub % ('{"ok": false, "code": "not_opened", "message": "The mail app could not be opened."}', 503), sid)
            cdp.js("document.querySelector('[data-fbt-mail]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js(notes, sid) == 1), where + ": the note shows on a refusal")
            self.assertEqual(cdp.js("document.querySelector('[data-mail-note]').textContent", sid), note, where)
            cdp.js("(() => { const t = document.querySelector('#fbt-message'); t.focus(); document.execCommand('insertText', false, ' x'); })()", sid)
            self.assertTrue(wait(lambda: cdp.js(notes, sid) == 0), where + ": typing clears the note")


if __name__ == "__main__":
    unittest.main()
