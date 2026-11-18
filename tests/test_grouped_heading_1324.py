"""Row 1324 (Grouped view, Option A), Work items (commit a-b): the group name is a heading line on the page, as Chrome computes it, at 1400 and 900 px, light and dark.

Run: python3 dev/run_tests.py test_grouped_heading_1324
The approved mock-up is clark-plan mockups/1324-grouped-view-template/. Cards and Classic: no tile (no border, no corners, no fill, nothing that clips), the heading
Montserrat 600 15 px in the heading colour with one 1 px hairline under it, 18 px above each group, the count 13 px and muted, the column names drawn once on top
and lined up with the rows of every group, the flat list ("Group by: Nothing") still a card, and the collapse button keeping a visible focus ring and a contrast of
at least 4.5 to 1. A published Work items list draws the same. Behaviour is not changed here: the collapse tests of the other files stay.
"""
import json
import unittest

from _grouped_1324 import LiveBase, NAME, SIZES, RATIO, RING, contrast_ok, chrome, wait, tearDownModule  # noqa: F401
import test_use_cases_list as T


class Live(LiveBase):
    def test_work_items_groups_are_heading_lines_not_tiles(self):
        for scheme in ("light", "dark"):
            for width in SIZES:
                for theme in (None, NAME):
                    with self.subTest(scheme=scheme, width=width, theme=theme), chrome() as cdp:
                        sid = self.work(cdp, width, scheme, theme)
                        f = self.facts(cdp, sid, "#work", ".wgroup:has(table.grouped)", "tr.grp th")
                        self.line(f"work {theme} {scheme} {width}", f, f["heading"], f["muted"])

    def test_work_items_column_names_once_on_top_and_the_columns_line_up(self):
        for width in SIZES:
            for theme in (None, NAME):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.work(cdp, width, "light", theme)
                    got = json.loads(cdp.js("""(() => {
                      const hs = [...document.querySelectorAll('#work tr.colh')], first = document.querySelector('#work tbody tr[data-id]');
                      const heads = hs.length ? [...hs[0].querySelectorAll('th')] : [];
                      const gs = [...document.querySelectorAll('#work .wgroup:has(table.grouped)')];
                      const leftsOf = (cells) => cells.map((c) => Math.round(c.getBoundingClientRect().left));
                      const rows = gs.map((w) => { const r = w.querySelector('tbody tr[data-id]'); return r ? leftsOf([...r.children]) : null; }).filter(Boolean);
                      const top = hs.length && gs.length ? hs[0].getBoundingClientRect().bottom <= gs[0].getBoundingClientRect().top + 1 : false;
                      return JSON.stringify({ colh: hs.length, inGroup: document.querySelectorAll('#work .wgroup tr.colh').length, groups: gs.length, heads: leftsOf(heads), rows, top,
                        grips: hs.length ? hs[0].querySelectorAll('[data-cgrip]').length : 0, ths: heads.filter((h) => !h.classList.contains('c-eye')).length, pickers: document.querySelectorAll('#work .cols-btn:not(.cols-kbd)').length,
                        kbd: document.querySelectorAll('#work .cols-btn.cols-kbd').length, tabs: [...document.querySelectorAll('#work table.items *')].filter(e => e.tabIndex >= 0 && !e.disabled && !e.closest('tr.grp')).length }); })()""", sid))
                    tag = f"{theme} {width}"
                    self.assertEqual(got["colh"], 1, tag + ": the column names are drawn once")
                    self.assertEqual(got["inGroup"], 0, tag + ": none inside a group")
                    self.assertGreater(got["groups"], 1, tag + ": several groups")
                    self.assertTrue(got["top"], tag + ": the one header is above the first group")
                    self.assertEqual(got["grips"], got["ths"], tag + ": a resize handle on every column")
                    self.assertEqual(got["pickers"], 1, tag + ": one column picker")
                    self.assertEqual(got["kbd"], 1, tag + ": one keyboard way into the picker")
                    self.assertGreater(len(got["rows"]), 1)
                    for n, r in enumerate(got["rows"]):
                        self.assertEqual(len(r), len(got["heads"]), f"{tag}: group {n} has the header's columns")
                        self.assertTrue(all(abs(a - b) <= 1 for a, b in zip(r, got["heads"])), f"{tag}: group {n} rows start where the header columns start (within the 1 px of rounding): {r} against {got['heads']}")

    def test_alt_arrow_on_a_row_of_any_group_resizes_the_column_of_the_one_header(self):
        """Row 1104's keyboard way (Alt with Right Arrow, from a row) still works now that the column names are one table above the groups."""
        with chrome() as cdp:
            sid = self.work(cdp, 1400, "light", None)
            probe = "JSON.stringify([...document.querySelectorAll('#work table.items')].slice(0, 3).map((t) => Math.round(t.querySelector('col.c-status').getBoundingClientRect().width)))"
            before = json.loads(cdp.js(probe, sid))
            cdp.js("(() => { const r = document.querySelectorAll('#work .wgroup')[1].querySelector('tbody tr[data-id]'); r.focus(); })()", sid)
            for kind in ("rawKeyDown", "keyUp"):
                cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "ArrowRight", "code": "ArrowRight", "windowsVirtualKeyCode": 39, "modifiers": 1}, sid)
            self.assertTrue(wait(lambda: json.loads(cdp.js(probe, sid))[0] > before[0]), f"the status column got wider: {before} then {cdp.js(probe, sid)}")
            after = json.loads(cdp.js(probe, sid))
            self.assertEqual(after[0], after[1], "the header and the groups share the widths")
            self.assertEqual(after[1], after[2])

    def test_work_items_flat_list_keeps_its_card_and_extra_columns_still_scroll(self):
        with chrome() as cdp:
            sid = self.work(cdp, 1400, "light", None)
            cdp.js("document.querySelector('#viewMenu').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.ddmenu [data-kind=\"group:nothing\"]')", sid)))
            cdp.js("document.querySelector('.ddmenu [data-kind=\"group:nothing\"]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!document.querySelector('tr.grp')", sid)))
            card = json.loads(cdp.js("JSON.stringify((() => { const s = getComputedStyle(document.querySelector('#work .wgroup')); return [s.borderTopWidth, s.borderTopLeftRadius, s.overflowX, s.overflowY]; })())", sid))
            self.assertEqual(card[0], "1px", "the flat list is still a bordered card")
            self.assertNotEqual(card[1], "0px", "with rounded corners")
            self.assertIn(card[2], ("hidden", "auto"))
            # a Work items table with an extra column (row 1195) still scrolls sideways inside its box
            cdp.js("(() => { const d = document.createElement('div'); d.className = 'wgroup'; d.id = 'probe'; d.innerHTML = '<table class=\"items\"><tbody><tr><td class=\"c-x\">x</td></tr></tbody></table>'; document.body.appendChild(d); })()", sid)
            self.assertEqual(cdp.js("getComputedStyle(document.querySelector('#probe')).overflowX", sid), "auto")

    # ---- K-e: the control ----
    def test_the_collapse_button_keeps_a_focus_ring_that_is_not_clipped_and_every_text_is_4_5_to_1(self):
        for scheme in ("light", "dark"):
            for width in SIZES:
                for theme in (None, NAME):
                    with self.subTest(scheme=scheme, width=width, theme=theme), chrome() as cdp:
                        sid = self.work(cdp, width, scheme, theme)
                        ring = json.loads(cdp.js("JSON.stringify(%s('#work .wgroup .grp-b'))" % RING, sid))
                        self.assertEqual((ring["clipped"], ring["style"], ring["width"], ring["focused"]), (False, "solid", "2px", True), f"work {scheme} {width} {theme}")
                        low = contrast_ok(json.loads(cdp.js("JSON.stringify(%s(['#work .grp-b .gl', '#work .grp-b .gc']))" % RATIO, sid)))
                        self.assertEqual(low, [], f"work heading and count contrast {scheme} {width} {theme}")
                        # hover: the heading takes the brand colour, still 4.5 to 1
                        x, y = json.loads(cdp.js("(() => { const r = document.querySelector('#work .grp-b .gl').getBoundingClientRect(); return JSON.stringify([r.left + r.width / 2, r.top + r.height / 2]); })()", sid))
                        cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, sid)
                        self.assertTrue(wait(lambda: cdp.js("document.querySelector('#work .grp-b').matches(':hover')", sid)))
                        hov = cdp.js("getComputedStyle(document.querySelector('#work .grp-b')).color", sid)
                        rest = cdp.js("(() => { const p = document.createElement('i'); document.body.appendChild(p); p.style.color = 'var(--heading)'; return getComputedStyle(p).color; })()", sid)
                        self.assertNotEqual(hov, rest, f"{scheme} {width} {theme}: hover changes the heading colour")
                        low = contrast_ok(json.loads(cdp.js("JSON.stringify(%s(['#work .grp-b']))" % RATIO, sid)))
                        self.assertEqual(low, [], f"work hovered heading contrast {scheme} {width} {theme}")



class Published(T.Published):
    """The published file (the setup of test_use_cases_list.Published, without its tests)."""


for _n in [n for n in dir(Published) if n.startswith("test")]:
    setattr(Published, _n, None)


class PublishedWork(Published):
    def test_a_published_work_items_list_has_one_column_header_and_no_tile(self):
        path = self.publish()
        for scheme in ("light", "dark"):
            for width in SIZES:
                with self.subTest(scheme=scheme, width=width), chrome() as cdp:
                    p = self.draw(cdp, path, "")
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    p.js("document.documentElement.dataset.theme = %s" % json.dumps(scheme))
                    p.js("[...document.querySelectorAll('.tabs .tab')].find(t => t.textContent === 'Work items').click()")
                    p.until("document.querySelectorAll('table.items tbody tr[data-id]').length > 0", "Work items")
                    got = json.loads(p.js("JSON.stringify({ colh: document.querySelectorAll('table.items tr.colh').length, tiles: [...document.querySelectorAll('.wgroup:has(table.grouped)')].map(w => getComputedStyle(w).borderTopWidth + getComputedStyle(w).borderTopLeftRadius), line: [...document.querySelectorAll('tr.grp th')].map(h => getComputedStyle(h).borderBottomWidth + getComputedStyle(h).backgroundColor) })"))
                    self.assertEqual(got["colh"], 1, f"published Work items: one column header {scheme} {width}")
                    self.assertTrue(got["tiles"] and set(got["tiles"]) == {"0px0px"}, f"published Work items: no tile {scheme} {width}: {got}")
                    self.assertEqual(set(got["line"]), {"1pxrgba(0, 0, 0, 0)"}, f"published Work items: a hairline and no band {scheme} {width}")


if __name__ == "__main__":
    unittest.main()
