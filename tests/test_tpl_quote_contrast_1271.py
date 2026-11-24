"""Row 1579 (check 8 of row 1271, Quote template): the quote's colour pairs keep the contrast floors in light and in dark, and the Edit field edges
use the control-edge token and not grey-300.

The pairs are read from the page the person gets (the Classic theme layered over the brand tokens): each colour is the computed value of the
token or of the drawn element, so a change in either token file, or a rule that points an element at another token, moves the number.
Floors: 4.5 for text, 3 for interface parts, and not below the mock-up's own figures (role on the panel 6.85 light and 9.45 dark; field edge on the
surface 3.70 light and 5.29 dark). Widths 1400 and 900. Fictional data only.
Run: python3 dev/run_tests.py test_tpl_quote_contrast_1271    Needs Chrome (the item 33 harness).
"""
import json
import re
import tempfile
import unittest

from _paths import ROOT
from clark import page
from test_dark_contrast import ratio
from test_report_editor import Base as PageBase, real_server
from test_server import chrome
import _tpl_notes as n

Q = lambda t, by="", role="": {"quote": t, "by": by, "role": role}
TEXT, UI = 4.5, 3.0
# the mock-up's figures (mockups/1271-quote-template NOTES.md, Contrast), light and dark
MOCK_ROLE = {"light": 6.85, "dark": 9.45}
MOCK_EDGE = {"light": 3.70, "dark": 5.29}


def hexed(rgb):
    """'rgb(r, g, b)' as '#RRGGBB' (the form test_dark_contrast.ratio takes)."""
    r, g, b = (int(v) for v in re.findall(r"\d+", rgb)[:3])
    return f"#{r:02X}{g:02X}{b:02X}"


class Contrast(PageBase):
    make = n.PageChecks.make
    body_of = n.PageChecks.body_of
    TYPE = "quote"

    def setUp(self):
        super().setUp()
        self.s.close()
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.page_html(tempfile.mkdtemp(), theme="prototype-2.0"), seam=self.seam)
        self.addCleanup(self.s.close)

    def _probe(self, p, scheme, width, cdp):
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.js(f"document.documentElement.setAttribute('data-theme', {json.dumps(scheme)})")
        return ("(v, prop) => { const i = document.createElement('i'); i.style[prop] = v; document.body.append(i);"
                " const c = getComputedStyle(i)[prop]; i.remove(); return c; }")

    def test_the_quote_pairs_keep_the_floor_in_light_and_dark(self):
        ref = self.make({"v": 1, "quotes": [Q("Fictional first.", "Sam Example", "Fictional sponsor"), Q("Fictional second.")]})
        sec = f"document.querySelector('[data-id={json.dumps(ref)}]')"
        for scheme in ("light", "dark"):
            for width in (1400, 900):
                with self.subTest(scheme=scheme, width=width), chrome() as cdp:
                    p = self.visit(cdp)
                    tok = self._probe(p, scheme, width, cdp)
                    # Edit counts the quotes (the count line sits on the Edit surface); the drawn colours are read in View and in Edit.
                    view = p.js(f"(() => {{ const tok = {tok}, s = {sec}, one = s.querySelector('.tpl-quote'), by = s.querySelector('.tpl-quote-by');"
                                f" return {{panel: getComputedStyle(one).backgroundColor, name: getComputedStyle(s.querySelector('.tpl-quote-name')).color,"
                                f" role: getComputedStyle(s.querySelector('.tpl-quote-role')).color, mark: getComputedStyle(one, '::before').color,"
                                f" rule: getComputedStyle(by, '::before').backgroundColor}}; }})()")
                    p.edit()
                    p.until(f"!!{sec}.querySelector('[data-tq-count]')", "the quote in Edit")
                    edit = p.js(f"(() => {{ const tok = {tok}, s = {sec}, f = s.querySelector('.tpl-field.tq-words'), g = s.querySelector('.tpl-field.tq-f');"
                                f" return {{count: getComputedStyle(s.querySelector('[data-tq-count]')).color, remove: getComputedStyle(s.querySelector('.tq-rm')).color,"
                                f" surface: tok('var(--surface, var(--white))', 'backgroundColor'), page: getComputedStyle(document.body).backgroundColor,"
                                f" fieldBg: getComputedStyle(f).backgroundColor, fieldEdge: getComputedStyle(f).borderTopColor, nameEdge: getComputedStyle(g).borderTopColor,"
                                f" controlEdge: tok('var(--control-edge)', 'borderTopColor'), grey300: tok('var(--grey-300)', 'borderTopColor')}}; }})()")
                    panel = hexed(view["panel"])
                    r = {
                        "name on panel": (ratio(hexed(view["name"]), panel), TEXT),
                        "role on panel": (ratio(hexed(view["role"]), panel), max(TEXT, MOCK_ROLE[scheme])),
                        "mark on panel": (ratio(hexed(view["mark"]), panel), UI),
                        "rule on panel": (ratio(hexed(view["rule"]), panel), UI),
                    }
                    # the field sits on its own fill when it has one, else on the Edit surface
                    fill = hexed(edit["fieldBg"]) if not edit["fieldBg"].endswith(", 0)") else hexed(edit["surface"])
                    r["count on surface"] = (ratio(hexed(edit["count"]), fill), TEXT)
                    r["Remove or Add link on panel"] = (ratio(hexed(edit["remove"]), fill), TEXT)
                    r["words field edge"] = (ratio(hexed(edit["fieldEdge"]), fill), max(UI, MOCK_EDGE[scheme]))
                    r["name field edge"] = (ratio(hexed(edit["nameEdge"]), fill), max(UI, MOCK_EDGE[scheme]))
                    for what, (got, floor) in r.items():
                        print(f"1579 {scheme} {width} {what}: {got:.2f}:1 (floor {floor})")
                    low = [f"{what}: {got:.2f} under {floor}" for what, (got, floor) in r.items() if round(got, 2) < floor]
                    self.assertEqual(low, [], f"{view} {edit}")
                    self.assertEqual(edit["fieldEdge"], edit["controlEdge"], "the words box edge is the control-edge token")
                    self.assertEqual(edit["nameEdge"], edit["controlEdge"], "the name and role box edge is the control-edge token")
                    self.assertNotEqual(edit["fieldEdge"], edit["grey300"])
                    self.assertLess(ratio(hexed(edit["grey300"]), fill), UI, "grey-300 on the surface is under 3, so a revert to it fails")

    CSS = (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules-2.css").read_text(encoding="utf-8")

    def test_the_edit_field_edges_use_the_control_edge_token_and_not_grey_300(self):
        """The words box and the name and role boxes set border-color from the control-edge token in the Classic rules, and never from grey-300."""
        for selector in (".tpl-quote-pe .tpl-field.tq-words", ".tpl-quote-pe .tpl-field.tq-f"):
            m = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", self.CSS)
            self.assertTrue(m, selector)
            self.assertIn("border-color: var(--control-edge)", m.group(1), selector)
            self.assertNotIn("grey-300", m.group(1), selector)


if __name__ == "__main__":
    unittest.main()
