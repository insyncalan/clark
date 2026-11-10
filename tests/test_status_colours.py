"""Row 1021, final status colours: Red, Amber, Green, Blue, a dark maroon Urgent tile and a neutral grey, in the app, the published file and the Word/Excel copies.

Run: python3 dev/run_tests.py test_status_colours
Red = Overdue / Red; Amber = Due soon / Amber / Blocked; Green = On track / Open / In progress; Blue = Completed, Decision made, Closed;
a dark maroon solid tile with a white letter = Urgent (also when overdue: the due column and the tooltip say overdue); grey = Cancelled and Not rated.
Widths 1400 and 900 only. A real browser, a real server, fictional rows.
"""
import json
import re
import sys
import unittest

from _demo import USER
from _paths import ROOT, TOOLS

sys.path.insert(0, str(TOOLS))
from clark import docx_build, excel_colours, publish  # noqa: E402
from test_item_one_line import Base, ROWS, width, fill_more  # noqa: E402
from test_item_rows import AS_AT  # noqa: E402
from test_report_editor import Pg  # noqa: E402
from test_server import chrome, wait  # noqa: E402

TOKENS_CSS = ROOT / "src" / "clark" / "brand" / "tokens.css"
LIGHT = {"red": ("B3392F", "F4DEDB"), "amber": ("8A5A12", "FBF0D2"), "green": ("2F6E57", "DFF1EA"), "blue": ("2456A8", "E1EBFA")}
MAROON = "6B1D2A"


def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4 for x in c]
    return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]


def contrast(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + .05) / (lo + .05)


def rgb_hex(css):
    return "".join(f"{int(n):02X}" for n in re.findall(r"\d+", css)[:3])


PROBE = """(() => { const out = {}; for (const c of ['r', 'a', 'g', 'b', 'n', 'u']) {
  const e = document.createElement('span'); e.className = 'ico ' + c; e.textContent = 'A'; document.body.appendChild(e);
  const s = getComputedStyle(e); out[c] = [s.backgroundColor, s.color]; e.remove(); }
  const w = document.createElement('span'); document.body.appendChild(w); return out; })()"""


class Tokens(unittest.TestCase):
    def test_the_light_values_are_the_final_ones(self):
        for name, (text, tint) in LIGHT.items():
            self.assertEqual(excel_colours.COLOURS[name][1] and excel_colours.TOKENS[excel_colours.COLOURS[name][0]], tint, name)
            self.assertEqual(excel_colours.TOKENS[excel_colours.COLOURS[name][1]], text, name)
        grey_fill, grey_text = (excel_colours.TOKENS[t] for t in excel_colours.COLOURS["grey"])
        self.assertGreaterEqual(contrast(grey_fill, grey_text), 4.5, "grey passes AA")
        self.assertEqual(excel_colours.TOKENS["tone-urgent"], MAROON)

    def test_every_pair_passes_AA_in_light_and_the_urgent_tile_has_a_white_letter(self):
        for name, (text, tint) in LIGHT.items():
            self.assertGreaterEqual(contrast(text, tint), 4.5, name)
        self.assertGreaterEqual(contrast("FFFFFF", MAROON), 7)

    def test_dark_pairs_are_readable_in_both_dark_copies(self):
        css = TOKENS_CSS.read_text(encoding="utf-8")
        blocks = re.findall(r":root\[data-theme=(?:dark|auto)\]\s*\{(.*?)\n\s*\}", css, re.S)
        self.assertEqual(len(blocks), 2)
        for b in blocks:
            v = {n: h.upper() for n, h in re.findall(r"(--tone-[\w-]+):\s*#([0-9A-Fa-f]{6})", b)}
            for tone in ("red", "amber", "green", "blue", "grey"):
                self.assertGreaterEqual(contrast(v[f"--tone-{tone}-text"], v[f"--tone-{tone}-tint"]), 4.5, tone)
            self.assertGreaterEqual(contrast("FFFFFF", v["--tone-urgent"]), 4.5)
            self.assertGreaterEqual(contrast(v["--tone-urgent"], "0E2D38"), 2, "the maroon tile is seen on the dark card")


class Tiles(Base):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            st.create("actions", {"project": "ABC", "description": "Urgent and late", "owner": "Sara Khan", "due_date": "2026-10-01", "priority": "Urgent",
                                  "raised": "2026-09-01", "client_message": "Urgent and late", "source": "demo"})

    def colours(self, p, theme):
        p.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}")
        return {k: [rgb_hex(x) for x in v] for k, v in p.js(PROBE).items()}

    def test_page_tiles_at_1400_and_900_in_light_and_dark(self):
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.served().port)
            p.ready()
            for w in (1400, 900):
                width(cdp, p.sid, w)
                light = self.colours(p, "light")
                for k, name in (("r", "red"), ("a", "amber"), ("g", "green"), ("b", "blue")):
                    self.assertEqual(light[k], [LIGHT[name][1], LIGHT[name][0]], f"{k} at {w}")
                self.assertEqual(light["u"], [MAROON, "FFFFFF"], f"urgent: maroon tile, white letter at {w}")
                self.assertGreaterEqual(contrast(*light["n"]), 4.5, "grey passes AA")
                self.assertNotEqual(light["n"][0], light["b"][0])
                dark = self.colours(p, "dark")
                for k in "ragbnu":
                    self.assertGreaterEqual(contrast(*dark[k]), 4.5, f"{k} readable in dark at {w}")
                self.assertNotEqual(dark["u"][0], dark["r"][0])

    def test_rows_urgent_keeps_maroon_overdue_in_due_column_and_tooltip(self):
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.served().port)
            p.ready()
            for w in (1400, 900):
                width(cdp, p.sid, w)
                actions = {r["id"]: r for r in p.js(ROWS % "actions")}
                urgent = next(r for r in actions.values() if r["title"] == "Urgent and late")
                self.assertIn("u", urgent["cls"].split())
                self.assertIn("Urgent", urgent["tip"])
                self.assertIn("Overdue", urgent["tip"])
                self.assertRegex(urgent["late"], r"^\d+ d late$")
                raid = p.js(ROWS % "raid")
                self.assertIn("u", raid[0]["cls"].split(), "the Urgent risk")
                self.assertNotIn("u", raid[1]["cls"].split())
                decisions = p.js(ROWS % "decisions")
                self.assertIn("g", decisions[0]["cls"].split(), "a pending decision is open: green")
                self.assertNotIn("b", decisions[0]["cls"].split())


class Copies(Base):
    def test_the_word_copy_draws_status_cells_in_the_final_hexes(self):
        import test_docx_build as t
        text = t.every_text(docx_build.build(publish.select(publish.read_inputs(self.store, "ABC", AS_AT)))).upper()
        for want in ("B3392F", "F4DEDB"):
            self.assertIn(want, text)
        for old in ("A3301F", "F6E0DD"):
            self.assertNotIn(old, text, "the old red is gone from the Word copy")


class ExcelStatus(unittest.TestCase):
    def test_open_is_green_closed_is_blue_cancelled_is_grey(self):
        self.assertEqual(excel_colours.ACTION_STATUS, {"Open": "green", "Delayed": "amber", "Closed": "blue", "Cancelled": "grey"})
        self.assertEqual(excel_colours.RAID_STATUS, {"Open": "green", "Closed": "blue", "Cancelled": "grey"})


class WordUrgent(Base):
    def test_an_urgent_item_has_a_maroon_status_cell_with_white_bold_words_and_overdue_stays_in_the_due_column(self):
        with self.store.step("dashboard", USER) as st:
            st.create("actions", {"project": "ABC", "description": "Urgent late", "owner": "Sara Khan", "due_date": "2026-10-01", "priority": "Urgent",
                                  "raised": "2026-09-01", "client_message": "Urgent late", "source": "demo"})
        import test_docx_build as t
        data = docx_build.build(publish.select(publish.read_inputs(self.store, "ABC", AS_AT)))
        doc = t.parts(data)["word/document.xml"].decode("utf-8")
        cells = re.findall(r"<w:tc>(?:(?!</w:tc>).)*</w:tc>", doc, re.S)
        maroon = [c for c in cells if MAROON in c]
        self.assertTrue(maroon)
        status = next(c for c in maroon if "Overdue" in c)      # the Urgent late action keeps its status word on the maroon cell
        self.assertIn('w:fill="6B1D2A"', status)
        self.assertIn("FFFFFF", status, "white words on the maroon")
        self.assertIn("<w:b/>", status)
        self.assertIn("(overdue)", doc, "overdue is also in the due column")


if __name__ == "__main__":
    unittest.main()
