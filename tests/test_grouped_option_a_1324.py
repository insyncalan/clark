"""Row 1324-A: Group by on the Use cases page (the editor's list and the published tab) drawn as Option A of the approved mock-up
(mock-up 1324-grouped-view-template, ruling 18-11-2026 18:03): the group name is a bold 15 px heading on the page with its count and one
hairline under it (no tile, no band, no rounded corners, no border), the column names are drawn once on top and not per group, and
18 px of space above each group replaces the container. Work items (rows 1324-B and 1324-C) are not touched here.

Run: python3 dev/run_tests.py test_grouped_option_a_1324
The Static class never starts Chrome. The other classes drive Chrome at 1400 and 900 px, light and dark (fictional data): the editor
page through the real server (as test_use_cases_list) and a real published file (as test_publish_uc_list_1114).

Page words: none new. The count words stay "use case" and "use cases"; the column names are the editor's own four, now also over the published list
(~/ag/1324-A-words.md).
"""
import json
import re
import tempfile
import unittest
from pathlib import Path

from _paths import SRC
from test_server import chrome, wait

import test_publish_uc_list_1114 as pub
import test_use_cases_list as ucl

PAGE = SRC / "clark" / "page"
SHELL = (PAGE / "shell.css").read_text(encoding="utf-8")
RULES = (SRC / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")      # the Classic look; shell.css and edit.css hold none of it (Cards is unchanged)
TAB = (PAGE / "src" / "components" / "UseCasesTab.jsx").read_text(encoding="utf-8")
LIST = (PAGE / "src" / "edit" / "UseCasesPage.jsx").read_text(encoding="utf-8")
LONG = "Committed for the second quarter of the coming year once the supplier file format and the bank sign-off are agreed"


def rules(css, selector):
    """The declaration text of every rule whose selector list holds exactly `selector` (comments dropped)."""
    out = []
    for sel, body in re.findall(r"(?m)^([^{}@/\n][^{}\n]*)\{([^}]*)\}", re.sub(r"/\*.*?\*/", "", css, flags=re.S)):
        if selector in [s.strip() for s in sel.split(",")]:
            out.append(body)
    return out


# One probe for both pages. `pre` is the page's group class prefix (ucl or ucp), `root` its container, `row` its row, `cols` its column names.
PROBE = """((pre, root, row, cols) => { const q = (s, r) => (r || document).querySelector(s), qa = (s, r) => [...(r || document).querySelectorAll(s)], g = (e, p) => getComputedStyle(e)[p];
  const groups = qa(root + ' .' + pre + '-group'), hdr = qa(root + (pre === 'ucl' ? ' .ucl-table.hdr' : ' .ucp-cols')), top = (e) => e.getBoundingClientRect().top, left = (e) => Math.round(e.getBoundingClientRect().left);
  const c = hdr[0] ? (pre === 'ucl' ? ['item', 'where', 'status', 'steps'].map((k) => q('th.c-' + k, hdr[0])) : [...hdr[0].children]) : [];
  const cell = (r) => pre === 'ucl' ? [q('td.c-item', r), q('td.c-where', r), q('td.c-status', r), q('td.c-steps', r)] : [q('.ucref', r), q('.ucp-headline', r), q('.ucstc', r), q('.ucsteps', r)];
  const heads = [c[0], c[1], c[2], c[3]];
  return { n: groups.length, cols: hdr.length,
    tile: groups.map((e) => [g(e, 'borderTopWidth'), g(e, 'borderBottomWidth'), g(e, 'borderTopLeftRadius'), g(e, 'backgroundColor'), g(e, 'overflow'), g(e, 'marginBottom')]),
    band: groups.map((e) => { const b = q('.' + pre + '-grp', e); return [g(b, 'backgroundColor'), g(b, 'paddingLeft'), g(b, 'borderTopWidth'), g(b, 'borderBottomWidth'), g(b, 'borderBottomStyle')]; }),
    btn: groups.map((e) => { const b = q('.grp-b', e); return [g(b, 'fontWeight'), g(b, 'fontSize'), g(b, 'color'), g(b, 'fontFamily').split(',')[0]]; }),
    words: groups.map((e) => [q('.gl', e).textContent, q('.gc', e).textContent, qa(row, e).length, q('.grp-b', e).getAttribute('aria-expanded')]),
    heading: tok('var(--heading)', 'color'), line: tok('var(--grey-200)', 'borderBottomColor'),
    lineOf: groups.map((e) => g(q('.' + pre + '-grp', e), 'borderBottomColor')),
    hdrTop: hdr[0] ? top(hdr[0]) : null, firstGroupTop: groups[0] ? top(groups[0]) : null,
    gaps: groups.map((e, i) => i ? Math.round(top(e) - groups[i - 1].getBoundingClientRect().bottom) : (hdr[0] ? Math.round(top(e) - hdr[0].getBoundingClientRect().bottom) : null)),
    align: groups.filter((e) => qa(row, e)[0]).map((e) => cell(qa(row, e)[0]).map((x, i) => x && heads[i] ? left(x) - left(heads[i]) : null)),
    wide: document.documentElement.scrollWidth <= window.innerWidth,
    inside: groups.map((e) => { const b = q('.grp-b', e).getBoundingClientRect(); return [Math.round(b.height), Math.round(q('.gc', e).getBoundingClientRect().right)]; }) };
  function tok(v, p) { const i = document.createElement('i'); i.style[p] = v; if (p === 'borderBottomColor') i.style.borderBottomStyle = 'solid'; document.body.appendChild(i); const r = getComputedStyle(i)[p]; i.remove(); return r; } })"""


class Look:
    """The assertions that hold on both pages. Subclasses give `pre`, `root`, `row` and `got`, the probe's answer."""

    def check(self, got, width, scheme, ctx):
        n = got["n"]
        self.assertGreaterEqual(n, 3, f"{ctx}: the sample has three groups")
        self.assertEqual(got["tile"], [["0px", "0px", "0px", "rgba(0, 0, 0, 0)", "visible", "0px"]] * n, f"{ctx}: K1 no tile (no border, no round corners, no fill, no clipping, no card gap)")
        self.assertEqual([b[0] for b in got["band"]], ["rgba(0, 0, 0, 0)"] * n, f"{ctx}: K2 no band behind the heading")
        self.assertEqual([b[1] for b in got["band"]], ["0px"] * n, f"{ctx}: K2 the heading starts at the page edge")
        self.assertEqual([b[2:] for b in got["band"]], [["0px", "1px", "solid"]] * n, f"{ctx}: K4 one hairline under the heading, none over it")
        self.assertEqual(got["lineOf"], [got["line"]] * n, f"{ctx}: K4 the hairline is the grey-200 token")
        for b in got["btn"]:
            self.assertEqual(b[:2], ["600", "15px"], f"{ctx}: K3 the heading is 600 weight, 15 px")
            self.assertEqual(b[2], got["heading"], f"{ctx}: K3 the heading colour is the --heading token")
            self.assertEqual(b[3], "Montserrat", f"{ctx}: K3 the heading face is the heading font")
        for w in got["words"]:
            self.assertRegex(w[1], r"^\d+ use cases?$", f"{ctx}: K3 the count words are unchanged")
            self.assertEqual(w[1], "1 use case" if w[2] == 1 else f"{w[2]} use cases", f"{ctx}: K10 and K16 the count is the number of rows drawn")
        self.assertEqual(got["cols"], 1, f"{ctx}: K5 the column names are drawn once")
        self.assertLess(got["hdrTop"], got["firstGroupTop"], f"{ctx}: K6 the column names are on top")
        self.assertEqual(got["gaps"][0], 14, f"{ctx}: K8 14 px from the column names to the first group")
        self.assertEqual(got["gaps"][1:], [18] * (n - 1), f"{ctx}: K8 18 px above each later group")
        self.assertEqual([a for row in got["align"] for a in row], [0] * (4 * len(got["align"])), f"{ctx}: K7 each group's first row lines up under the column names")
        self.assertTrue(got["wide"], f"{ctx}: no sideways scroll")


class Static(unittest.TestCase):
    """No Chrome. These fail on origin/main (the groups are cards with a grey band there)."""

    def test_k19_the_use_case_group_is_not_a_card(self):
        for css, sel in ((RULES, ".wgroup.ucl-group"), (RULES, ".wgroup.ucp-group")):
            body = " ".join(rules(css, sel))
            self.assertTrue(body, f"{sel} has its own rule over the shared .wgroup card")
            for need in ("border: 0", "border-radius: 0", "overflow: visible", "background: none", "margin: 18px 0 0"):
                self.assertIn(need, body, f"{sel}: {need}")
        for css, sel in ((RULES, ".ucl-grp"), (RULES, ".ucp-grp")):
            body = " ".join(rules(css, sel))
            self.assertNotIn("grey-50", body, f"{sel} keeps no band")
            self.assertIn("border-bottom: 1px solid var(--grey-200)", body, f"{sel} has the hairline")
            self.assertIn("padding: 0 0 6px", body, f"{sel}: the heading sits on the hairline")

    def test_k19_the_wgroup_card_is_still_work_items(self):
        body = " ".join(rules(SHELL, ".wgroup"))
        for keep in ("border: 1px solid var(--grey-200)", "border-radius: var(--radius-lg)", "overflow: hidden"):
            self.assertIn(keep, body, f"rows 1324-B and C own the Work items card: {keep} stays")

    def test_k3_the_heading_look_is_scoped_to_the_use_case_groups(self):
        body = " ".join(rules(RULES, ".ucl-group .grp-b") + rules(RULES, ".ucp-group .grp-b"))
        for need in ("font-weight: var(--weight-medium)", "font-size: 15px", "var(--font-head)", "color: var(--heading)"):
            self.assertIn(need, body, need)
        self.assertNotIn("font-size", " ".join(rules(SHELL, ".grp-b")), "the Work items heading is not changed by this row")

    def test_k13_k12_hover_is_the_brand_colour_and_the_ring_stays(self):
        self.assertIn("color: var(--brand-blue)", " ".join(rules(RULES, ".ucl-group .grp-b:hover") + rules(RULES, ".ucp-group .grp-b:hover")))
        self.assertIn("outline: 2px solid var(--brand-blue)", " ".join(rules(SHELL, ".grp-b:focus-visible")))

    def test_k5_the_column_names_come_before_the_groups_and_once(self):
        self.assertEqual(TAB.count('class="ucp-cols"'), 1, "one column-names row in the published tab")
        self.assertLess(TAB.index('class="ucp-cols"'), TAB.index("groups.map"), "drawn before the groups, not inside them")
        grouped = LIST[LIST.index("{table(true, null"):LIST.index("</section>")]
        self.assertLess(grouped.index("table(true, null"), grouped.index("groups.map"), "the Classic grouped list draws the header table above the groups")
        self.assertEqual(grouped.count("table(true"), 1, "the header is drawn once")
        self.assertIn("table(false", grouped[grouped.index("groups.map"):], "the group tables have no header")

    def test_k9_a_shut_group_draws_no_rows(self):
        self.assertIn("g.shut ? null", TAB)
        self.assertIn("g.shut ? null", LIST)

    def test_the_published_header_uses_the_rows_columns(self):
        head = " ".join(rules(RULES, ".ucp-cols"))
        self.assertIn("grid-template-columns: minmax(64px, max-content) minmax(0, 1fr) minmax(0, 1.5fr) 124px 112px", head)
        self.assertIn("minmax(64px, max-content)", " ".join(rules(RULES, ".ucp > summary.ucp-bar")))


class App(ucl.Setup):
    THEME = "prototype-2.0"
    """The editor's Use cases page, grouped by Status (three groups in the sample), then by Commitment with one long name."""

    def pick(self, p, word):
        self.click(p, "#ucl-group")
        p.until("!!document.querySelector('.ddmenu [role=menuitemradio]')", "the Group by menu")
        p.js(f"[...document.querySelectorAll('.ddmenu [role=menuitemradio]')].find(b => b.textContent.replace('✓', '').trim() === {json.dumps(word)}).click()")
        p.until(f"document.querySelector('#ucl-group').getAttribute('aria-label') === {json.dumps('Group by: ' + word)}", f"grouped by {word}")

    def probe(self, p):
        return p.js(f"({PROBE})('ucl', '#usecases', 'tr.ucr[data-uc]', '.ucl-table.hdr')")

    def test_option_a_at_1400_and_900_in_light_and_dark(self):
        for scheme in ("light", "dark"):
            for width in (1400, 900):
                with self.subTest(scheme=scheme, width=width), chrome() as cdp:
                    p = self.show(cdp, width=width, dark=scheme == "dark")
                    self.pick(p, "Status")
                    got = self.probe(p)
                    Look.check(self, got, width, scheme, f"{scheme} {width}")
                    self.assertTrue(any(w[2] == 1 for w in got["words"]), "the sample has a one-use-case group (K16)")
                    ratios = p.js(ucl.contrast_script([".ucl-group .grp-b .gl", ".ucl-group .grp-b .gc"]))
                    self.assertTrue(ratios and all(r[1] >= 4.5 for r in ratios), f"K14 {scheme} {width}: the heading and the count read at 4.5 to 1: {ratios}")

    def test_collapse_keeps_one_header_and_the_counts_and_hover_goes_brand(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.pick(p, "Status")
            before = self.probe(p)["words"]
            self.click(p, "#usecases .ucl-group .grp-b")
            p.until("document.querySelector('#usecases .ucl-group .grp-b').getAttribute('aria-expanded') === 'false'", "shut")
            got = self.probe(p)
            self.assertEqual(got["cols"], 1, "K5/K6 the header stays with the first group shut")
            self.assertEqual(got["words"][0][2:], [0, "false"], "K9 a shut group draws no rows")
            self.assertEqual(got["words"][0][1], before[0][1], "K9 the count still says how many it holds")
            self.assertEqual(got["words"][1:], before[1:])
            x, y = p.js("(() => { const r = document.querySelectorAll('#usecases .ucl-group .grp-b')[1].getBoundingClientRect(); return [Math.round(r.left + 8), Math.round(r.top + r.height / 2)]; })()")
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, p.sid)
            brand = p.js("(() => { const i = document.createElement('i'); i.style.color = 'var(--brand-blue)'; document.body.appendChild(i); const c = getComputedStyle(i).color; i.remove(); return c; })()")
            self.assertTrue(wait(lambda: p.js("getComputedStyle(document.querySelectorAll('#usecases .ucl-group .grp-b')[1]).color") == brand), "K13 hover: the brand colour")

    def test_a_long_name_wraps_at_900_and_the_count_stays_on_the_page(self):
        self.store.con.execute("UPDATE use_cases SET commitment = ? WHERE id = ?", (LONG, self.uc2))   # the store's own check lets only the listed words in; a long group name is what a stray one would look like
        self.store.con.commit()
        with chrome() as cdp:
            p = self.show(cdp, width=900)
            self.pick(p, "Commitment")
            got = self.probe(p)
            self.assertTrue(any(h > 30 for h, _ in got["inside"]), f"K15 the long name wraps onto more than one line: {got['inside']}")
            self.assertTrue(all(r <= 900 for _, r in got["inside"]), "K15 the count stays inside the window")
            # the long word is made a group name by hand (the store allows only its listed commitments), so its chip in each row, which is not this row's, also runs wide: the heading is what this checks
            self.assertEqual(p.js("[...document.querySelectorAll('#usecases .ucl-grp, #usecases .ucl-grp *')].filter(e => e.getBoundingClientRect().right > innerWidth).length"), 0, "K15 no heading runs past the window")

    def test_ungrouped_is_unchanged(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertEqual(p.js("document.querySelectorAll('#usecases .ucl-group, #usecases .grp-b').length"), 0)
            self.assertEqual(p.js("document.querySelectorAll('#usecases .ucl-table thead').length"), 1, "K18 one column-names row")


class Published(unittest.TestCase):
    """The published Use cases tab, grouped by Status."""

    go = pub.RealBrowser.go

    def grouped(self, cdp, width, scheme):
        tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        sid = self.go(cdp, pub.made(), tmp)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
        js = lambda s: cdp.js(s, sid)  # noqa: E731
        js("document.querySelector('#ucp-group, [aria-label^=\"Group by\"]').click()")
        self.assertTrue(wait(lambda: js("!![...document.querySelectorAll('[role^=menuitem]')].find(e => e.textContent.trim() === 'Status')")))
        js("[...document.querySelectorAll('[role^=menuitem]')].find(e => e.textContent.trim() === 'Status').click()")
        self.assertTrue(wait(lambda: js("document.querySelectorAll('.ucp-group').length") >= 2))
        return sid, js

    def test_option_a_at_1400_and_900_in_light_and_dark(self):
        for scheme in ("light", "dark"):
            for width in (1400, 900):
                with self.subTest(scheme=scheme, width=width), chrome() as cdp:
                    sid, js = self.grouped(cdp, width, scheme)
                    got = js(f"({PROBE})('ucp', '#usecases-file', '.ucp', '.ucp-cols')")
                    self.assertEqual(got["tile"], [["0px", "0px", "0px", "rgba(0, 0, 0, 0)", "visible", "0px"]] * 2, f"{scheme} {width}: K1 no tile")
                    self.assertEqual([b[0] for b in got["band"]], ["rgba(0, 0, 0, 0)"] * 2, f"{scheme} {width}: K2/M22 no band")
                    self.assertEqual([b[1] for b in got["band"]], ["0px"] * 2, f"{scheme} {width}: the heading starts at the page edge")
                    self.assertEqual([b[2:] for b in got["band"]], [["0px", "1px", "solid"]] * 2, f"{scheme} {width}: K4 hairline")
                    self.assertEqual(got["lineOf"], [got["line"]] * 2, f"{scheme} {width}: K4 the grey-200 token")
                    for b in got["btn"]:
                        self.assertEqual(b[:2], ["600", "15px"], f"{scheme} {width}: K3")
                        self.assertEqual(b[2], got["heading"], f"{scheme} {width}: K3 heading token")
                    for w in got["words"]:
                        self.assertEqual(w[1], "1 use case", f"{scheme} {width}: K16 one each")
                    self.assertEqual(got["cols"], 1, f"{scheme} {width}: K5 the column names are drawn once")
                    self.assertLess(got["hdrTop"], got["firstGroupTop"], f"{scheme} {width}: K6")
                    self.assertEqual(got["gaps"], [14, 18], f"{scheme} {width}: K8")
                    self.assertEqual([a for r in got["align"] for a in r], [0] * 8, f"{scheme} {width}: K7 the columns line up under the names")
                    self.assertTrue(got["wide"])
                    self.assertEqual(js("[...document.querySelectorAll('#usecases-file .ucp-cols > span')].map(e => e.textContent).join('|')"), "Use case|Where it stands|Status|Next steps|")
                    ratios = js(ucl.contrast_script([".ucp-group .grp-b .gl", ".ucp-group .grp-b .gc"]))
                    self.assertTrue(ratios and all(r[1] >= 4.5 for r in ratios), f"K14 {scheme} {width}: {ratios}")

    def test_a_shut_group_keeps_the_header_once(self):
        with chrome() as cdp:
            sid, js = self.grouped(cdp, 1400, "light")
            js("document.querySelector('.ucp-group .grp-b').click()")
            self.assertTrue(wait(lambda: js("document.querySelector('.ucp-group .grp-b').getAttribute('aria-expanded')") == "false"))
            self.assertEqual(js("document.querySelectorAll('#usecases-file .ucp-cols').length"), 1)
            self.assertEqual(js("document.querySelector('.ucp-group').querySelectorAll('.ucp').length"), 0)


if __name__ == "__main__":
    unittest.main()
