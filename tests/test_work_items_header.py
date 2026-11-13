"""Release 1.0.3 UI Debt, the Work items header batch (rows 805, 808, 809, 812, 813, 807): browser tests.

Every test runs at 1400 and 900 px, in light and dark, in View and in Edit.

Run: python3 dev/run_tests.py test_work_items_header
Headless Chrome (required: fails, never skips, without it).
"""
import json
import unittest

from test_server import chrome
from test_work_board_page import Base
from test_work_filters import arm, click, hover, key, select_line, set_line
from test_filter_line_page import click_tab

CASES = [(w, s, e) for w in (1400, 900) for s in ("light", "dark") for e in (False, True)]


class Header(Base):
    def go(self, cdp, width, scheme, edit, **kw):
        sid = self.visit(cdp, width=width, edit=edit, **kw)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
        return sid

    def each(self, check, **kw):
        """Run check(cdp, sid, width) at 1400 and 900, light and dark, View and Edit."""
        for width, scheme, edit in CASES:
            with self.subTest(width=width, scheme=scheme, edit=edit), chrome() as cdp:
                check(cdp, self.go(cdp, width, scheme, edit, **kw), width)


    # ---- row 832 (the rows' text sits on the tinted page, no wrapping card): the text contrast is measured against the colour
    # really behind each text element, translucent layers composited, white at the bottom (the Movement audit does the same) ----
    ROW_CONTRAST = """(() => {
      function lum(m) { m = m.map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }); return 0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2]; }
      function behind(el) {
        var layers = [];
        for (; el; el = el.parentElement) { var m = getComputedStyle(el).backgroundColor.match(/[\\d.]+/g).map(Number); var al = m.length > 3 ? m[3] : 1; if (al > 0) { layers.push([m[0], m[1], m[2], al]); if (al === 1) break; } }
        var c = [255, 255, 255];
        for (var k = layers.length - 1; k >= 0; k--) { var l = layers[k]; c = [0, 1, 2].map(i => l[i] * l[3] + c[i] * (1 - l[3])); }
        return c;
      }
      var bad = [], n = 0;
      [...document.querySelectorAll('#work-list > *')].slice(0, 40).forEach(r => r.querySelectorAll('*').forEach(e => {
        if (!e.getClientRects().length || getComputedStyle(e).visibility === 'hidden') return;
        if (![].some.call(e.childNodes, x => x.nodeType === 3 && x.textContent.trim())) return;
        n++;
        var a = lum(getComputedStyle(e).color.match(/[\\d.]+/g).map(Number).slice(0, 3)), b = lum(behind(e)), hi = Math.max(a, b), lo = Math.min(a, b), ratio = (hi + 0.05) / (lo + 0.05);
        if (ratio < 4.5) bad.push((e.tagName + '.' + e.className).slice(0, 40) + ' ' + ratio.toFixed(2));
      }));
      return JSON.stringify({n: n, bad: bad});
    })()"""

    def test_row_832_the_rows_text_has_4_5_to_1_contrast_against_what_is_really_behind_it(self):
        import json

        def check(cdp, sid, width):
            got = json.loads(cdp.js(self.ROW_CONTRAST, sid))
            self.assertGreater(got["n"], 20, "the rows' text was measured")
            self.assertEqual(got["bad"], [], "row text contrast under 4.5:1")
        self.each(check)

    # ---- row 805 ----
    def test_row_805_no_intro_sentence_and_no_count_line_and_no_gap_left(self):
        def check(cdp, sid, width):
            self.assertFalse(cdp.js("!!document.querySelector('#work-intro')", sid), "no intro sentence")
            self.assertFalse(cdp.js("/Select an item to open it beside/.test(document.querySelector('#work').textContent)", sid))
            # the count line is not drawn: what is left of it is clipped to a pixel, for a screen reader
            h = cdp.js("document.querySelector('#work-count').getBoundingClientRect().height", sid)
            self.assertLessEqual(h, 2, "no count line is drawn")
            self.assertFalse(cdp.js("!!document.querySelector('#work-list > .factive')", sid), "no empty row is left for it")
            gap = cdp.js("(() => { const a = document.querySelector('.fline-wrap').getBoundingClientRect(); "
                         "const t = [...document.querySelectorAll('#work-list > *')].find(e => e.getBoundingClientRect().height > 2 && !e.classList.contains('sr')); "
                         "return Math.round(t.getBoundingClientRect().top - a.bottom); })()", sid)
            self.assertLessEqual(gap, 12, f"the list follows the filter line closely ({gap}px)")
        self.each(check)

    # ---- row 808 ----
    def open_list(self, cdp, sid):
        click(cdp, sid, "#fline-input")
        select_line(cdp, sid)
        key(cdp, sid, "Backspace")
        arm(cdp, sid)
        self.until(cdp, sid, "document.querySelector('#fline-list')", "the suggestion list")

    def floats(self, cdp, sid, board):
        if board:
            self.board(cdp, sid, "status")
            cdp.js("document.activeElement.blur()", sid)
            self.until(cdp, sid, "!document.querySelector('#fline-list')", "the list closed")
        else:
            click(cdp, sid, "#fline-input")
            select_line(cdp, sid)
            key(cdp, sid, "Backspace")
            cdp.js("document.activeElement.blur()", sid)
            self.until(cdp, sid, "!document.querySelector('#fline-list')", "the list closed")
        probe = "(() => { const a = document.querySelector('#work-list').getBoundingClientRect().top, b = document.querySelector('#work-list').getBoundingClientRect().height; return [Math.round(a), Math.round(b)]; })()"
        before = cdp.js(probe, sid)
        self.open_list(cdp, sid)
        self.assertEqual(cdp.js(probe, sid), before, "opening the list moves nothing and changes no height")
        got = cdp.js("(() => { const l = document.querySelector('#fline-list'), s = getComputedStyle(l), r = l.getBoundingClientRect(), b = document.querySelector('[data-fline]').getBoundingClientRect(), w = document.querySelector('#work-list').getBoundingClientRect();"
                     " return {pos: s.position, z: +s.zIndex, gap: Math.round(r.top - b.bottom), left: Math.round(r.left - b.left), over: r.bottom > w.top}; })()", sid)
        self.assertEqual(got["pos"], "absolute")
        self.assertGreater(got["z"], 25)
        self.assertLessEqual(got["gap"], 8)
        self.assertEqual(got["left"], 0)
        self.assertTrue(got["over"], "the list lies over the page below the box")

    def test_row_808_the_suggestion_list_floats_over_the_table_and_pushes_nothing(self):
        self.each(lambda cdp, sid, width: self.floats(cdp, sid, False))

    def test_row_808_the_suggestion_list_floats_over_the_board_and_pushes_nothing(self):
        self.each(lambda cdp, sid, width: self.floats(cdp, sid, True))

    # ---- row 809 ----
    def test_row_809_views_are_text_tabs_on_a_rule_the_same_for_made_and_user_views(self):
        mine = [{"id": "mine", "name": "My own", "line": "is:open type:risk"}]

        def check(cdp, sid, width):
            cdp.js("localStorage.setItem('clark.fviews', JSON.stringify({ABC: %s}))" % __import__("json").dumps(mine), sid)
            self.reload(cdp, sid)
            self.until(cdp, sid, "document.querySelector('.vtab[data-view-id=mine]')", "the made view")
            probe = ("(() => { const css = (e) => getComputedStyle(e), box = document.querySelector('.fvrow'), bb = box.getBoundingClientRect();"
                     " const one = (e) => { const c = css(e), r = e.getBoundingClientRect(); return {radius: c.borderTopLeftRadius, bg: c.backgroundColor, l: c.borderLeftWidth, t: c.borderTopWidth, b: c.borderBottomWidth, bc: c.borderBottomColor, color: c.color, w: c.fontWeight, gap: Math.round(r.bottom - bb.bottom)}; };"
                     " const tabs = [...document.querySelectorAll('.vtab')];"
                     " return {rule: css(box).borderBottomWidth, ruleColor: css(box).borderBottomColor, tabs: tabs.map((e) => [e.dataset.viewId, e.getAttribute('aria-pressed') === 'true', one(e)]),"
                     " badge: one(document.querySelector('.vtab em')), made: one(document.querySelector('.vtab[data-view-id=mine]')), neu: one(document.querySelector('#viewNew')),"
                     " scrolls: /auto|scroll/.test(css(document.querySelector('.vtabs')).overflowX), fits: document.documentElement.scrollWidth <= innerWidth}; })()")
            got = cdp.js(probe, sid)
            self.assertEqual(got["rule"], "1px", "a thin rule under the row")
            self.assertTrue(got["scrolls"], "the row scrolls inside its own box")
            self.assertTrue(got["fits"], "the page does not scroll sideways")
            for vid, on, st in got["tabs"] + [("new", False, got["neu"])]:
                self.assertEqual(st["radius"], "0px", f"{vid}: not a pill")
                self.assertEqual((st["l"], st["t"]), ("0px", "0px"), f"{vid}: no outline box")
                self.assertEqual(st["bg"], "rgba(0, 0, 0, 0)", f"{vid}: no fill")
                if on:
                    self.assertEqual(st["b"], "2px", "the open tab has the underline")
                    self.assertEqual(st["gap"], 0, "and it sits on the rule (its foot is the rule's foot)")
                    self.assertNotEqual(st["bc"], "rgba(0, 0, 0, 0)")
                else:
                    self.assertEqual(st["bc"], "rgba(0, 0, 0, 0)", f"{vid}: no underline")
            self.assertEqual([t[1] for t in got["tabs"]].count(True), 1, "one tab is open")
            self.assertEqual(got["made"]["radius"], got["tabs"][0][2]["radius"], "the made view looks like a predefined one")
            self.assertEqual(got["made"]["b"], got["tabs"][0][2]["b"])
            self.assertEqual(got["made"]["color"], got["neu"]["color"], "a view that is not open is drawn in the one muted colour")
            self.assertNotEqual(got["badge"]["radius"], "0px", "the count is in a round badge")
            self.assertNotEqual(got["badge"]["bg"], "rgba(0, 0, 0, 0)")
            # the made view can be opened, and then it is the one with the underline
            click_tab(cdp, sid, ".vtab[data-view-id=mine]")
            self.until(cdp, sid, "document.querySelector('.vtab[data-view-id=mine]').getAttribute('aria-pressed') === 'true'", "the made view is open")
            self.assertEqual(cdp.js("getComputedStyle(document.querySelector('.vtab[data-view-id=mine]')).borderBottomWidth", sid), "2px")
        self.each(check)

    # ---- row 844 ----
    CLICK_DIAG = """(() => { const t = document.querySelector('.vtab[data-view-id=risky]'), r = t.getBoundingClientRect(), e = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
      return JSON.stringify({tab: t.outerHTML.slice(0, 300), rect: [r.x, r.y, r.width, r.height], scroll: [scrollX, scrollY, document.querySelector('.vtabs').scrollLeft], at_point: e && e.outerHTML.slice(0, 200),
        vtabs: document.querySelector('.vtabs').innerHTML.slice(0, 1500), line: document.querySelector('[data-fline]').dataset.line}); })()"""

    def test_row_844_a_changed_view_keeps_its_tab_with_a_dot_and_save_view_and_discard_changes_act_on_it(self):
        saved = [{"id": "risky", "name": "Risky", "line": "is:open type:risk"}]

        def check(cdp, sid, width):
            cdp.js("localStorage.setItem('clark.fviews', JSON.stringify({ABC: %s}))" % __import__("json").dumps(saved), sid)
            self.reload(cdp, sid)
            self.until(cdp, sid, "document.querySelector('.vtab[data-view-id=risky]')", "the made view")
            # a fresh load: Open items is the chosen tab; a typed change leaves it chosen, with the dot and Discard changes (a core view cannot be saved over)
            self.until(cdp, sid, "document.querySelector('.vtab[data-view-id=core-open]').getAttribute('aria-pressed') === 'true'", "Open items is chosen")
            click(cdp, sid, "#fline-input")
            key(cdp, sid, "End")
            cdp.call("Input.insertText", {"text": " no:owner "}, sid)
            self.until(cdp, sid, "document.querySelector('.vtab[data-view-id=core-open] [data-dot]')", "the dot on Open items")
            self.assertEqual(cdp.js("document.querySelectorAll('.vtab[aria-pressed=true]').length", sid), 1, "a tab stays chosen")
            self.assertEqual(cdp.js("document.querySelector('.vtab[aria-pressed=true]').dataset.viewId", sid), "core-open")
            self.assertEqual(cdp.js("!!document.querySelector('#fvSave')", sid), False, "a core view cannot be saved over")
            self.assertEqual(cdp.js("document.querySelector('#fvRevert').textContent", sid), "Discard changes")
            self.assertTrue(cdp.js("document.documentElement.scrollWidth <= innerWidth", sid))
            click(cdp, sid, "#fvRevert")
            self.until(cdp, sid, "!document.querySelector('[data-dot]') && !document.querySelector('#fvRevert')", "discarded: no dot, no buttons")
            self.until(cdp, sid, "document.querySelector('[data-fline]').dataset.line.trim() === 'is:open'", "the saved line is back")
            # a made view: Save view writes the line into it
            click_tab(cdp, sid, ".vtab[data-view-id=risky]")
            self.until(cdp, sid, "document.querySelector('.vtab[data-view-id=risky]').getAttribute('aria-pressed') === 'true'", "the made view is open", why=lambda: cdp.js(self.CLICK_DIAG, sid))
            click(cdp, sid, "#fline-input")
            key(cdp, sid, "End")
            cdp.call("Input.insertText", {"text": " no:owner "}, sid)
            self.until(cdp, sid, "document.querySelector('.vtab[data-view-id=risky] [data-dot]')", "the dot on the made view")
            got = cdp.js("(() => { const b = document.querySelector('#fvSave'); return b ? [b.textContent, b.getBoundingClientRect().height] : null; })()", sid)
            self.assertEqual(got[0], "Save view")
            self.assertGreaterEqual(got[1], 24)
            click(cdp, sid, "#fvSave")
            self.until(cdp, sid, "!document.querySelector('[data-dot]') && !document.querySelector('#fvSave')", "saved: no dot")
            self.assertIn("no:owner", cdp.js("JSON.parse(localStorage.getItem('clark.fviews')).ABC.find((v) => v.id === 'risky').line", sid))
            self.assertTrue(cdp.js("document.documentElement.scrollWidth <= innerWidth", sid))
        self.each(check)

    def test_row_1032_discard_changes_does_not_overlap_new_view_after_group_by(self):
        """Issue 1032: after Group by the line is changed; the tabs, + New view, Save view and Discard changes each keep their own room."""
        probe = """(() => { const q = (s) => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom]; };
          return JSON.stringify({vnew: q('#viewNew'), rev: q('#fvRevert'), save: q('#fvSave'), grp: q('#viewMenu'), tabs: q('.vtabs'), row: q('.fvrow'), sw: document.documentElement.scrollWidth, iw: innerWidth}); })()"""

        def check(cdp, sid, width):
            click(cdp, sid, "#viewMenu")
            self.until(cdp, sid, "document.querySelector('#viewMenuList [data-kind=\"group:type\"]')", "the Group by menu")
            click(cdp, sid, "#viewMenuList [data-kind=\"group:type\"]")
            click(cdp, sid, "#fline-input")
            key(cdp, sid, "End")
            cdp.call("Input.insertText", {"text": " no:owner "}, sid)
            self.until(cdp, sid, "document.querySelector('#fvRevert')", "Discard changes shows")
            got = json.loads(cdp.js(probe, sid))
            a, b, t = got["vnew"], got["rev"], got["tabs"]
            self.assertGreaterEqual(a[0], t[1] - 3.5, "+ New view sits beside the tabs, not inside the scrolling row: %s" % got)
            self.assertTrue(a[1] <= b[0] + 0.5 or b[1] <= a[0] + 0.5 or a[3] <= b[2] or b[3] <= a[2], "Discard changes overlaps + New view: %s" % got)
        self.each(check)

    def test_row_844_the_saved_view_menu_opens_under_its_arrow_not_at_the_page_edge(self):
        saved = [{"id": "risky", "name": "Risky", "line": "is:open type:risk"}]
        probe = ("(() => { const a = document.querySelector('#viewTabMenu').getBoundingClientRect(), m = document.querySelector('#viewTabMenuList').getBoundingClientRect();"
                 " return {al: a.left, ab: a.bottom, ml: m.left, mt: m.top, mr: m.right}; })()")

        def check(cdp, sid, width):
            cdp.js("localStorage.setItem('clark.fviews', JSON.stringify({ABC: %s}))" % __import__("json").dumps(saved), sid)
            self.reload(cdp, sid)
            self.until(cdp, sid, "document.querySelector('.vtab[data-view-id=risky]')", "the made view")
            for tab in ("core-open", "risky"):         # the first tab (its arrow is near the page's left edge) and a later one
                click_tab(cdp, sid, f".vtab[data-view-id={tab}]")
                self.until(cdp, sid, f"document.querySelector('.vtab[data-view-id={tab}]').getAttribute('aria-pressed') === 'true' && document.querySelector('#viewTabMenu')", f"{tab} chosen")
                click(cdp, sid, "#viewTabMenu")
                self.until(cdp, sid, "document.querySelector('#viewTabMenuList')", "the menu")
                got = cdp.js(probe, sid)
                # the menu starts at its arrow, or is held 8 px inside the window's right edge when the arrow is too near it (row 1084: the tabs now have the whole row)
                self.assertLessEqual(abs(got["ml"] - min(got["al"], width - 8 - (got["mr"] - got["ml"]))), 2, f"{tab}: the menu starts at its arrow {got}")
                self.assertGreaterEqual(got["mt"], got["ab"], f"{tab}: below the arrow {got}")
                self.assertLessEqual(got["mr"], width, f"{tab}: inside the page {got}")
                key(cdp, sid, "Escape")
                self.until(cdp, sid, "!document.querySelector('#viewTabMenuList')", "closed")
        self.each(check)

    # ---- row 845 ----
    def test_row_845_accepted_filters_are_chips_each_with_its_own_remove_button(self):
        chips = "[...document.querySelectorAll('[data-fline] [data-chip]')].map((e) => e.dataset.chip)"
        line = "document.querySelector('[data-fline]').dataset.line"

        def check(cdp, sid, width):
            self.assertEqual(cdp.js(chips, sid), ["is:open"], "the starting line is a chip")
            self.assertEqual(cdp.js("document.querySelector('#fline-input').placeholder", sid), "", "no placeholder once a chip exists")
            self.assertEqual(cdp.js("document.querySelector('[data-chip] button').getAttribute('aria-label')", sid), "Remove the is:open filter")
            click(cdp, sid, "#fline-input")
            cdp.call("Input.insertText", {"text": "priority:High "}, sid)
            self.until(cdp, sid, f"JSON.stringify({chips}) === JSON.stringify(['is:open', 'priority:High'])", "the accepted word became a chip")
            self.assertEqual(cdp.js("document.querySelector('#fline-input').value", sid), "", "the box is empty again")
            self.assertEqual(cdp.js("document.querySelector('[data-chip=\"priority:High\"] button').getAttribute('aria-label')", sid), "Remove the Priority filter")
            self.assertGreaterEqual(cdp.js("document.querySelector('[data-chip] button').getBoundingClientRect().height", sid), 22)
            self.assertTrue(cdp.js("document.documentElement.scrollWidth <= innerWidth", sid))
            # a plain word stays in the box
            cdp.call("Input.insertText", {"text": "hello "}, sid)
            self.assertEqual(cdp.js(chips, sid), ["is:open", "priority:High"])
            self.assertEqual(cdp.js("document.querySelector('#fline-input').value", sid), "hello ")
            for _ in range(6):
                key(cdp, sid, "Backspace")
            self.until(cdp, sid, f"document.querySelector('#fline-input').value === ''", "the word is gone")
            # Backspace in an empty box takes the last chip away
            key(cdp, sid, "Backspace")
            self.until(cdp, sid, f"JSON.stringify({chips}) === JSON.stringify(['is:open'])", "the last chip is gone")
            self.until(cdp, sid, f"{line} === 'is:open'", "and the line follows")
            # the x on a chip removes only that chip and returns the focus to the box
            cdp.call("Input.insertText", {"text": "no:owner "}, sid)
            self.until(cdp, sid, f"JSON.stringify({chips}) === JSON.stringify(['is:open', 'no:owner'])", "a second chip")
            click(cdp, sid, "[data-chip='is:open'] button")
            self.until(cdp, sid, f"JSON.stringify({chips}) === JSON.stringify(['no:owner'])", "only that chip is gone")
            self.assertEqual(cdp.js("document.activeElement.id", sid), "fline-input")
            self.until(cdp, sid, f"{line} === 'no:owner'", "the line follows")
        self.each(check)

    # ---- row 846 ----
    def test_row_846_each_suggested_value_shows_how_many_items_it_leaves_and_an_unknown_field_lists_the_valid_ones(self):
        def check(cdp, sid, width):
            click(cdp, sid, "#fline-input")
            key(cdp, sid, "End")
            arm(cdp, sid)
            cdp.call("Input.insertText", {"text": " status:"}, sid)
            self.until(cdp, sid, "document.querySelector('#fline-list [data-ins^=\"status:\"]')", "the values")
            got = cdp.js("[...document.querySelectorAll('#fline-list [data-ins^=\"status:\"]')].map((o) => [o.dataset.ins, o.querySelector('.c') ? o.querySelector('.c').textContent : null])", sid)
            closing = [g for g in got if g[0] != "status:" and not g[0].startswith("-")]
            self.assertTrue(closing and all(g[1] is not None and g[1].isdigit() for g in closing), f"a count beside every value: {closing}")
            self.assertTrue(all(isinstance(g[1], str) for g in closing))
            # choosing a value leaves exactly that many items (the open chip still counts)
            pick = next(g for g in closing if g[0] == "status:Pending")
            click(cdp, sid, "#fline-list [data-ins='status:Pending']")
            self.until(cdp, sid, f"document.querySelector('#fline-count').textContent.startsWith('{pick[1]} of ')", "the count the list promised")
            # an unknown field turns the box red
            before = cdp.js("getComputedStyle(document.querySelector('.fline')).borderTopColor", sid)
            cdp.call("Input.insertText", {"text": "zzz:a "}, sid)
            self.until(cdp, sid, "document.querySelector('#fline-msg').textContent.startsWith('There is no')", "the message")
            said = cdp.js("document.querySelector('#fline-msg').textContent", sid)
            self.assertEqual(said, "There is no \u201czzz\u201d filter. You can filter by type:, status:, owner:, priority:, due:, workstream:, usecase:, milestone:, client: and is:, or type plain words to search titles.")
            self.assertTrue(cdp.js("document.querySelector('.fline').classList.contains('bad')", sid))
            self.assertNotEqual(cdp.js("getComputedStyle(document.querySelector('.fline')).borderTopColor", sid), before, "the box is red")
        self.each(check)

    def test_row_846_a_mistyped_field_names_the_nearest_one(self):
        def check(cdp, sid, width):
            click(cdp, sid, "#fline-input")
            key(cdp, sid, "End")
            cdp.call("Input.insertText", {"text": " stauts:a "}, sid)
            self.until(cdp, sid, "document.querySelector('#fline-msg').textContent.startsWith('There is no')", "the message")
            said = cdp.js("document.querySelector('#fline-msg').textContent", sid)
            self.assertTrue(said.startswith("There is no \u201cstauts\u201d filter. Did you mean status? You can filter by type:"), said)
        self.each(check)

    # ---- row 844: the toast ----
    def test_row_844_save_view_by_keyboard_hands_the_focus_to_the_open_tab(self):
        saved = [{"id": "risky", "name": "Risky", "line": "is:open type:risk"}]

        def check(cdp, sid, width):
            cdp.js("localStorage.setItem('clark.fviews', JSON.stringify({ABC: %s}))" % json.dumps(saved), sid)
            self.reload(cdp, sid)
            self.until(cdp, sid, "document.querySelector('.vtab[data-view-id=risky]')", "the made view")
            click_tab(cdp, sid, ".vtab[data-view-id=risky]")
            self.until(cdp, sid, "document.querySelector('.vtab[data-view-id=risky]').getAttribute('aria-pressed') === 'true'", "open")
            click(cdp, sid, "#fline-input")
            key(cdp, sid, "End")
            cdp.call("Input.insertText", {"text": " no:owner "}, sid)
            self.until(cdp, sid, "document.querySelector('#fvSave')", "Save view")
            cdp.js("document.querySelector('#fvSave').focus()", sid)
            self.until(cdp, sid, "document.activeElement.id === 'fvSave'", "Save view has the focus")
            key(cdp, sid, "Enter")
            self.until(cdp, sid, "!document.querySelector('#fvSave')", "saved: the button is gone")
            self.until(cdp, sid, "document.activeElement === document.querySelector('.vtab[aria-pressed=true]')", "the open tab has the focus",
                       why=lambda: cdp.js("document.activeElement && (document.activeElement.id || document.activeElement.tagName)", sid))
        self.each(check)

    def test_row_1073_save_as_a_new_view_announces_the_new_name(self):
        def check(cdp, sid, width):
            self.until(cdp, sid, "document.querySelector('#viewNew')", "+ New view")
            click(cdp, sid, "#viewNew")
            self.until(cdp, sid, "document.querySelector('#work-live').textContent.startsWith('Saved as View ')", "the announcement",
                       why=lambda: cdp.js("document.querySelector('#work-live').textContent", sid))
            self.assertIn("Use Rename view to change the name.", cdp.js("document.querySelector('#work-live').textContent", sid))
        self.each(check)

    def test_row_844_save_view_says_what_was_saved_in_the_toast(self):
        saved = [{"id": "risky", "name": "Risky", "line": "is:open type:risk"}]

        def check(cdp, sid, width):
            cdp.js("localStorage.setItem('clark.fviews', JSON.stringify({ABC: %s}))" % __import__("json").dumps(saved), sid)
            self.reload(cdp, sid)
            self.until(cdp, sid, "document.querySelector('.vtab[data-view-id=risky]')", "the made view")
            click_tab(cdp, sid, ".vtab[data-view-id=risky]")
            self.until(cdp, sid, "document.querySelector('.vtab[data-view-id=risky]').getAttribute('aria-pressed') === 'true'", "open")
            self.assertFalse(cdp.js("!!document.querySelector('.toast')", sid), "no message before")
            click(cdp, sid, "#fline-input")
            key(cdp, sid, "End")
            cdp.call("Input.insertText", {"text": " no:owner "}, sid)
            self.until(cdp, sid, "document.querySelector('#fvSave')", "Save view")
            click(cdp, sid, "#fvSave")
            self.until(cdp, sid, "document.querySelector('.toast .toast-text')", "the message")
            self.assertEqual(cdp.js("document.querySelector('.toast .toast-text').textContent", sid), "View saved: Risky")
            self.assertFalse(cdp.js("!!document.querySelector('.toast [data-undo]')", sid), "a saved view has no Undo to offer")
            self.assertTrue(cdp.js("(() => { const r = document.querySelector('.toast').getBoundingClientRect(); return r.height > 0 && r.bottom <= innerHeight && r.right <= innerWidth; })()", sid), "it is on the screen")
        self.each(check)

    # ---- row 845: a chip's meaning ----
    def test_row_845_a_chip_says_what_it_means_in_the_examples_line_on_hover_and_focus(self):
        gloss = "(() => { const g = document.querySelector('#fline-gloss'); const r = g.getBoundingClientRect(); const v = getComputedStyle(g.parentElement).visibility; return [g.textContent, r.height > 0, v]; })()"

        def check(cdp, sid, width):
            click(cdp, sid, "#fline-input")
            cdp.call("Input.insertText", {"text": "priority:High,Urgent -status:Closed "}, sid)
            self.until(cdp, sid, "document.querySelectorAll('[data-fline] [data-chip]').length === 3", "three chips")
            key(cdp, sid, "Escape")      # the suggestions close, so the examples line (where the meaning is said) shows
            self.until(cdp, sid, "document.querySelector('.fhints.on')", "the examples line")
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 2, "y": 2}, sid)      # the pointer is off the chips (the chips may have wrapped under it)
            self.assertFalse(cdp.js(gloss, sid)[1], "nothing is said until a chip is pointed at")
            hover(cdp, sid, "[data-chip='priority:High,Urgent']")
            self.until(cdp, sid, "document.querySelector('#fline-gloss').textContent !== ''", "the meaning on hover")
            self.assertEqual(cdp.js(gloss, sid), ["priority:High,Urgent: Priority is High or Urgent", True, "visible"])
            cdp.js("document.querySelector('[data-chip=\"-status:Closed\"] button').focus()", sid)
            self.until(cdp, sid, "document.querySelector('#fline-gloss').textContent.startsWith('-status:Closed')", "the meaning on focus")
            self.assertEqual(cdp.js("document.querySelector('#fline-gloss').textContent", sid), "-status:Closed: Status is not Closed")
            click(cdp, sid, "#fline-input")
            hover(cdp, sid, "#fline-input")
            self.until(cdp, sid, "document.querySelector('#fline-gloss').hidden", "the meaning goes when the pointer and focus leave")
        self.each(check)

    # ---- row 1072 ----
    def test_row_1072_group_by_is_one_icon_button_the_size_of_table_and_board(self):
        def check(cdp, sid, width):
            got = cdp.js("""(() => { const g = document.querySelector('#viewMenu'), t = document.querySelector('#work [data-lay=table]'), b = document.querySelector('#work [data-lay=board]');
              const r = (e) => { const q = e.getBoundingClientRect(); return [Math.round(q.width), Math.round(q.height)]; };
              g.focus(); const cs = getComputedStyle(g);
              return JSON.stringify({text: g.textContent.trim(), svg: g.querySelectorAll('svg').length, title: g.title, name: g.getAttribute('aria-label'), g: r(g), t: r(t), b: r(b),
                ring: cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) >= 2, popup: g.getAttribute('aria-haspopup')}); })()""", sid)
            got = json.loads(got)
            self.assertEqual(got["text"], "", "no words on the button")
            self.assertEqual(got["svg"], 1, "one icon, no chevron")
            self.assertEqual(got["title"], "Group by")
            self.assertTrue(got["name"].startswith("Group by"), got["name"])
            self.assertEqual(got["popup"], "menu")
            for other in ("t", "b"):
                self.assertLessEqual(abs(got["g"][0] - got[other][0]), 1, f"the same width as Table and Board: {got}")
                self.assertEqual(got["g"][1], got[other][1], f"the same height as Table and Board: {got}")
            self.assertTrue(got["ring"], "a focus ring shows")
            self.assertGreaterEqual(min(got["g"]), 24)
        self.each(check)

    def test_row_1072_the_group_by_menu_is_named_group_by_and_its_icon_is_two_bars(self):
        def check(cdp, sid, width):
            click(cdp, sid, "#viewMenu")
            self.until(cdp, sid, "document.querySelector('#viewMenuList')", "the View menu")
            self.assertEqual(cdp.js("document.querySelector('#viewMenuList').getAttribute('aria-label')", sid), "Group by")
            key(cdp, sid, "Escape")
            self.until(cdp, sid, "!document.querySelector('#viewMenuList')", "closed")
            bars = json.loads(cdp.js("JSON.stringify([...document.querySelectorAll('#viewMenu svg rect')].map(e => [+e.getAttribute('y'), +e.getAttribute('height')]))", sid))
            self.assertEqual(len(bars), 2, f"the Group by icon is two stacked bars: {bars}")
            self.assertGreaterEqual(bars[1][0] - (bars[0][0] + bars[0][1]), 4, f"a gap between the bars: {bars}")
        self.each(check)

    # ---- row 1072, hostile ----
    def test_row_1072_hostile_help_text_never_names_the_old_view_menu(self):
        import pathlib
        txt = (pathlib.Path(__file__).resolve().parent.parent / "src/clark/page/src/help/helpContent.json").read_text(encoding="utf-8")
        for stale in ("in the View menu", "the **View** menu", "View menu"):
            self.assertNotIn(stale, txt, f"help still names the removed View menu: {stale!r}")

    def test_row_1072_hostile_keyboard_opens_and_returns_focus_to_the_group_by_button(self):
        def check(cdp, sid, width):
            cdp.js("document.querySelector('#viewMenu').focus()", sid)
            key(cdp, sid, "Enter")
            self.until(cdp, sid, "document.querySelector('#viewMenuList')", "menu opens from the keyboard")
            self.assertEqual(cdp.js("document.querySelector('#viewMenu').getAttribute('aria-expanded')", sid), "true")
            key(cdp, sid, "Escape")
            self.until(cdp, sid, "!document.querySelector('#viewMenuList')", "closed")
            self.assertEqual(cdp.js("document.activeElement && document.activeElement.id", sid), "viewMenu", "focus returns to the icon button")
            self.assertEqual(cdp.js("document.querySelector('#viewMenu').getAttribute('aria-expanded')", sid), "false")
        self.each(check)

    def test_row_1072_hostile_board_label_has_no_view_word(self):
        def check(cdp, sid, width):
            click(cdp, sid, "#work [data-lay=board]")
            self.until(cdp, sid, "document.querySelector('#viewMenuList') === null && document.querySelector('#viewMenu').getAttribute('aria-label').startsWith('Group by')", "label")
            name = cdp.js("document.querySelector('#viewMenu').getAttribute('aria-label')", sid)
            self.assertNotIn("View", name)
            self.assertNotIn("board", name.lower(), name)
            self.assertEqual(cdp.js("document.querySelector('#viewMenu').title", sid), "Group by")
        self.each(check)

    def test_row_1072_hostile_icon_is_inside_the_viewport_with_contrast_light_and_dark(self):
        def check(cdp, sid, width):
            got = json.loads(cdp.js("""(() => { const g = document.querySelector('#viewMenu'), q = g.getBoundingClientRect(), s = g.querySelector('svg'), sc = getComputedStyle(s);
              const rgb = (c) => c.match(/[\\d.]+/g).map(Number);
              const L = (m) => { m = m.slice(0,3).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }); return 0.2126*m[0]+0.7152*m[1]+0.0722*m[2]; };
              let bg = null; for (let e = g; e && !bg; e = e.parentElement) { const m = rgb(getComputedStyle(e).backgroundColor); if ((m.length < 4 || m[3] === 1)) bg = m; }
              bg = bg || [255,255,255];
              const a = L(rgb(sc.color)), b = L(bg);
              return JSON.stringify({l: q.left, r: q.right, w: innerWidth, vis: sc.visibility, ratio: (Math.max(a,b)+.05)/(Math.min(a,b)+.05)}); })()""", sid))
            self.assertGreaterEqual(got["l"], 0, got)
            self.assertLessEqual(got["r"], got["w"], got)
            self.assertEqual(got["vis"], "visible")
            self.assertGreaterEqual(got["ratio"], 3.0, f"icon contrast (non-text 3:1): {got}")
        self.each(check)

    def test_row_1072_mut_group_by_has_the_switch_margin_and_box(self):
        def check(cdp, sid, width):
            got = json.loads(cdp.js("""(() => { const g = document.querySelector('#viewMenu'), sw = document.querySelector('#work .lsw'), cs = getComputedStyle(g);
              return JSON.stringify({gm: cs.marginBottom, sm: getComputedStyle(sw).marginBottom, display: cs.display, box: cs.boxSizing}); })()""", sid))
            self.assertEqual(got["gm"], got["sm"], f"the same bottom margin as the Table and Board switch: {got}")
            self.assertEqual(got["display"], "inline-grid", got)
            self.assertEqual(got["box"], "border-box", got)
        self.each(check)

    def test_row_1072_mut_help_never_names_the_view_menu_in_any_case(self):
        import pathlib, re
        txt = (pathlib.Path(__file__).resolve().parent.parent / "src/clark/page/src/help/helpContent.json").read_text(encoding="utf-8")
        hits = re.findall(r"\bView\*{0,2} menu", txt, flags=re.I)
        self.assertEqual(hits, [], "help still names the removed View menu")

    # ---- row 812 ----
    def test_row_812_table_and_board_are_a_two_icon_switch_and_group_by_stays_in_the_view_menu(self):
        def check(cdp, sid, width):
            pair = ("[...document.querySelectorAll('#work .fline [role=group][aria-label=Layout] button')].map(b => [b.dataset.lay, b.getAttribute('aria-label'), b.title, b.getAttribute('aria-pressed'), b.textContent, !!b.querySelector('svg'),"
                    " Math.round(b.getBoundingClientRect().width), Math.round(b.getBoundingClientRect().height)])")
            got = cdp.js(pair, sid)
            self.assertEqual([g[:6] for g in got], [["table", "List", "List", "true", "", True], ["board", "Board", "Board", "false", "", True]], "icons, not words, named List and Board")
            self.assertTrue(all(g[6] >= 32 and g[7] >= 28 for g in got), f"each icon is a target of a fair size: {got}")
            self.assertTrue(cdp.js("document.documentElement.scrollWidth <= innerWidth", sid), "the page does not scroll sideways")
            self.assertEqual(cdp.js("document.querySelectorAll('#work [aria-haspopup=menu]').length >= 1 && !document.querySelector('#work .fvrow [data-lay]')", sid), True)
            # the View menu keeps Group by (and no Layout); its words and button name are unchanged
            click(cdp, sid, "#viewMenu")
            self.until(cdp, sid, "document.querySelector('#viewMenuList')", "the View menu")
            self.assertEqual(cdp.js("[...document.querySelectorAll('#viewMenuList .lab')].map(l => l.textContent)", sid), ["Group by"])
            self.assertEqual(cdp.js("document.querySelector('#viewMenu').getAttribute('aria-label')", sid), "Group by: Workstream")
            key(cdp, sid, "Escape")
            self.until(cdp, sid, "!document.querySelector('#viewMenuList')", "closed")
            # pressing Board: the board draws, the switch follows, and the menu gains the swimlanes; Table brings the table back
            click(cdp, sid, "#work [data-lay=board]")
            self.until(cdp, sid, "document.querySelector('#work-board')", "the board")
            self.assertEqual(self.checked(cdp, sid, "layout:"), ["layout:board"])
            click(cdp, sid, "#viewMenu")
            self.until(cdp, sid, "document.querySelector('#viewMenuList')", "the View menu on the board")
            self.assertEqual(cdp.js("[...document.querySelectorAll('#viewMenuList .lab')].map(l => l.textContent)", sid), ["Group by", "Swimlanes"])
            key(cdp, sid, "Escape")
            cdp.js("document.querySelector('#work [data-lay=table]').focus()", sid)
            key(cdp, sid, "Enter")
            self.until(cdp, sid, "document.querySelector('table.items') && !document.querySelector('#work-board')", "the table from the keyboard")
            self.assertEqual(self.checked(cdp, sid, "layout:"), ["layout:table"])
        self.each(check)

    # ---- row 813 ----
    def test_row_813_no_freshness_pill_and_the_filter_is_still_there_by_typing_and_by_a_saved_view(self):
        saved = [{"id": "quiet", "name": "Gone quiet", "line": "is:open is:quiet"}]

        def check(cdp, sid, width):
            cdp.js("localStorage.setItem('clark.fviews', JSON.stringify({ABC: %s}))" % __import__("json").dumps(saved), sid)
            self.reload(cdp, sid)
            self.until(cdp, sid, "document.querySelector('.vtab[data-view-id=quiet]')", "the saved view")
            self.assertEqual(cdp.js("document.querySelectorAll('#freshMenu, #freshMenuList, [aria-label=Freshness]').length", sid), 0, "no Freshness pill")
            self.assertFalse(cdp.js("[...document.querySelectorAll('.fvrow .btn')].some(b => /Freshness/.test(b.textContent))", sid))
            self.assertEqual(cdp.js("[...document.querySelectorAll('.fvrow > *')].map(e => e.className.split(' ')[0])", sid)[-1:], ["vnew"], "row 1084: the layout switch and Group by left the row; the tabs are in it, and + New view sits beside them (row 1032)")
            # the saved view draws the word, the typed word filters, and the page does not scroll sideways
            click_tab(cdp, sid, ".vtab[data-view-id=quiet]")
            self.until(cdp, sid, "document.querySelector('[data-fline]').dataset.line === 'is:open is:quiet'", "the saved view's line")
            self.assertTrue(cdp.js("document.documentElement.scrollWidth <= innerWidth", sid))
            click(cdp, sid, "#fline-x")          # row 845: the saved line's filters are chips; Clear takes them away before the new word is typed
            select_line(cdp, sid)
            cdp.call("Input.insertText", {"text": "is:incomplete"}, sid)
            self.until(cdp, sid, "document.querySelector('[data-fline]').dataset.line === 'is:incomplete'", "typed")
            self.until(cdp, sid, "document.querySelector('.fhi .k-val')", "the typed word is a chip")
        self.each(check)

    # ---- row 807 ----
    def test_row_807_a_selected_card_and_a_selected_list_row_have_no_check_mark_but_still_show_it_is_selected(self):
        def check(cdp, sid, width):
            self.board(cdp, sid, "status")
            card = "#work-board article.bcard .bc-main"
            click(cdp, sid, card)
            self.until(cdp, sid, "document.querySelector('#work-board article.bcard.picked')", "a card is selected")
            got = cdp.js("(() => { const a = document.querySelector('#work-board article.bcard.picked'), c = getComputedStyle(a);"
                         " return {tick: !!a.querySelector('.tick'), svg: a.querySelectorAll('.bc-title svg').length, label: a.querySelector('.bc-main').getAttribute('aria-label'),"
                         " border: c.borderTopColor, shadow: c.boxShadow, other: getComputedStyle(document.querySelector('#work-board article.bcard:not(.picked)')).borderTopColor}; })()", sid)
            self.assertFalse(got["tick"], "no check mark on the selected card")
            self.assertEqual(got["svg"], 0)
            self.assertIn(", selected", got["label"], "a screen reader still hears it")
            self.assertNotEqual(got["border"], got["other"], "the border shows the selection")
            self.assertNotEqual(got["shadow"], "none")
            # a click opens the details panel (row 806), which covers the layout switch, so it is closed first
            key(cdp, sid, "Escape")
            self.until(cdp, sid, "!document.querySelector('#peek:not([hidden])') || document.querySelector('#peek').getBoundingClientRect().width === 0 || getComputedStyle(document.querySelector('#peek')).display === 'none'", "the details panel closed")
            # the list row has no check mark either (row 807): the tint, border and bar show it
            self.view_pick(cdp, sid, "layout:table")
            self.until(cdp, sid, "document.querySelector('table.items')", "the table")
            click(cdp, sid, "table.items tbody tr[data-id] .c-item .t")
            self.until(cdp, sid, "document.querySelector('table.items tbody tr.picked')", "a row is selected")
            got = cdp.js("(() => { const r = document.querySelector('table.items tbody tr.picked'), c = getComputedStyle(r);"
                         " return {tick: !!r.querySelector('.tick'), svg: r.querySelectorAll('.c-item svg').length, sel: r.getAttribute('aria-selected'),"
                         " shadow: c.boxShadow, other: getComputedStyle(document.querySelector('table.items tbody tr[data-id]:not(.picked)')).boxShadow}; })()", sid)
            self.assertFalse(got["tick"], "no check mark on the selected list row")
            self.assertEqual(got["svg"], 0, "no icon drawn in the item cell of the selected row")
            self.assertEqual(got["sel"], "true", "a screen reader still hears it")
            self.assertIn("inset", got["shadow"], "the border and the bar show the selection")
            self.assertNotEqual(got["shadow"], got["other"])
        self.each(check)

    def test_row_807_a_list_row_is_as_tall_selected_as_not_selected(self):
        from test_multi_select import MOD, tap

        def check(cdp, sid, width):
            self.until(cdp, sid, "document.querySelector('table.items tbody tr[data-id]')", "the table")
            rid = cdp.js("document.querySelector('table.items tbody tr[data-id]').dataset.id", sid)
            row = "#work-list tr[data-id='%s']" % rid
            h = "document.querySelector(\"%s\").getBoundingClientRect().height" % row
            self.until(cdp, sid, "document.getAnimations().length === 0", "animations finished")
            before = cdp.js(h, sid)
            tap(cdp, sid, row + " .c-item .t", MOD)
            self.until(cdp, sid, "document.querySelector(\"%s\").classList.contains('picked')" % row, "the row is selected")
            self.until(cdp, sid, "document.getAnimations().length === 0", "animations finished")
            self.assertFalse(cdp.js("!!document.querySelector('#peek')", sid), "a Ctrl or Cmd click selects without opening the peek, so the table keeps its width")
            self.assertEqual(cdp.js(h, sid), before, "the row's height is the same selected and not selected")
            self.assertGreater(before, 20, "the row was measured")
        self.each(check)

    # ---- row 833: the view and filter area is no taller than the prototype's (95 px from the tabs to the chips; first group at 305 px) ----
    PROTO_FIRST_GROUP = 305

    STACK = """(() => {
      const r = (s) => document.querySelector(s).getBoundingClientRect();
      const group = [...document.querySelectorAll('#work-list > *')].find(e => e.getBoundingClientRect().height > 2 && !e.classList.contains('sr'));
      const wrap = document.querySelector('.fline-wrap');
      return JSON.stringify({
        hints: getComputedStyle(document.querySelector('.fhints')).position, hintsOn: !!document.querySelector('.fhints.on'),
        wrap: r('.fline-wrap').height,
        inflow: [...wrap.children].filter(e => getComputedStyle(e).display !== 'none' && getComputedStyle(e).position !== 'absolute').reduce((a, e) => a + e.getBoundingClientRect().height + parseFloat(getComputedStyle(e).marginTop) + parseFloat(getComputedStyle(e).marginBottom), 0),
        group: group.getBoundingClientRect().top });
    })()"""

    def stack(self, cdp, sid):
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, sid)
        self.until(cdp, sid, "document.getAnimations().length === 0", "no animation running")
        return json.loads(cdp.js(self.STACK, sid))

    def test_row_833_the_hidden_examples_row_takes_no_room(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.go(cdp, width, "light", False)
                got = self.stack(cdp, sid)
                self.assertFalse(got["hintsOn"], "the line is not focused")
                self.assertEqual(got["hints"], "absolute", "the examples row is out of the flow")
                self.assertLessEqual(abs(got["wrap"] - got["inflow"]), 1, f"the filter area holds only what is drawn ({got})")

    def test_row_833_the_examples_show_over_the_page_without_moving_it(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.go(cdp, width, "light", False)
                before = self.stack(cdp, sid)
                click(cdp, sid, "#fline-input")
                self.until(cdp, sid, "document.querySelector('.fhints.on')", "the examples row")
                self.until(cdp, sid, "document.getAnimations().length === 0", "no animation running")
                after = json.loads(cdp.js(self.STACK, sid))
                self.assertEqual(after["group"], before["group"], "the first group does not move when the examples show")
                self.assertEqual(cdp.js("getComputedStyle(document.querySelector('.fhints')).visibility", sid), "visible")
                over = cdp.js("(() => { const h = document.querySelector('.fhints').getBoundingClientRect(); "
                              "const e = document.elementFromPoint(h.left + 20, h.top + h.height / 2); return !!e && !!e.closest('.fhints'); })()", sid)
                self.assertTrue(over, "the examples are on top of what is below, so they can be clicked")
                self.assertEqual(cdp.js("getComputedStyle(document.querySelector('.fhints')).zIndex", sid), "24", "over the sticky bars (20)")
                self.assertLess(24, int(cdp.js("(() => { const m = document.createElement('div'); m.className = 'ddmenu'; document.body.append(m); const z = getComputedStyle(m).zIndex; m.remove(); return z; })()", sid)), "under the drop-down menus, so an open menu is not covered")

    def test_row_833_the_examples_do_not_cover_the_filter_note(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.go(cdp, width, "light", False)
                self.stack(cdp, sid)                       # reduced motion pinned, no animation running
                set_line(cdp, sid, "is:open stat:Open")
                self.until(cdp, sid, "document.querySelector('#fline-msg').textContent.trim()", "the note")
                self.until(cdp, sid, "document.querySelector('.fhints.on')", "the examples row")
                self.until(cdp, sid, "document.getAnimations().length === 0", "no animation running")
                got = json.loads(cdp.js("(() => { const n = document.querySelector('#fline-msg').getBoundingClientRect(), h = document.querySelector('.fhints').getBoundingClientRect(), l = document.querySelector('.fline').getBoundingClientRect();"
                                        " return JSON.stringify({noteTop: n.top, noteBottom: n.bottom, hintsTop: h.top, lineBottom: l.bottom, noteH: n.height}); })()", sid))
                self.assertGreater(got["noteH"], 8, "the note is drawn")
                self.assertGreaterEqual(got["noteTop"], got["lineBottom"] - 1, "the note sits under the line")
                self.assertGreaterEqual(got["hintsTop"], got["noteBottom"] - 1, f"the examples start below the note, not over it ({got})")

    def test_row_833_the_first_group_starts_within_the_prototype_plus_one_step(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.go(cdp, width, "light", False)
                got = self.stack(cdp, sid)
                self.assertLessEqual(got["group"], self.PROTO_FIRST_GROUP, f"first group top {got['group']} at {width}")


if __name__ == "__main__":
    unittest.main()
