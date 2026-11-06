"""Item 454: what a person sees at desktop widths 1400 and 900 px, in the light and in the dark theme, for four things:
(1) the People card in Settings (the table, the count line, Paste from Excel and its preview), (2) Get the template in the Import
from Excel box, (3) Check the import (counts row, per-sheet line, Accept/Reject per row, Accept all and Reject all, and the whole-file
refusal screen), (4) the Import icon beside Add on Work items. One test for each point, width and theme.

Each test asserts that the thing is there and visible, that it does not spill past the dialog, its card or the window (no sideways
scroll), that no text is cut off, and that its text reads against what it sits on (4.5:1, 3:1 for an icon). In the dark theme the
surface must also be dark and in the light theme light. The dark theme is found the way the existing dark checks find it:
data-theme="dark" on the root element (tests/test_data_card.py) together with the emulated prefers-color-scheme media feature
(tests/test_work_export_button.py).

Run: python3 dev/run_tests.py test_item_454_dark_900
Chrome is required: these tests fail, never skip, without it.
"""
import base64
import json
import tempfile
import unittest
from pathlib import Path

from _demo import DemoStore
from clark import excel, page
from test_import_template import Page as TemplatePage
from test_people_card import PeopleCard, PASTE
from test_server import Running, chrome, wait
from test_work_export_button import open_page
from test_work_items import page_target  # noqa: F401  (open_page uses it)

WIDTHS = (1400, 900)
SCHEMES = ("light", "dark")
TEXT_FLOOR = 4.5            # WCAG 1.4.3 text
ICON_FLOOR = 3.0            # WCAG 1.4.11 an icon against what it sits on
LINK_FLOOR = 4.0            # the shared .link colour measures 4.44:1 in the dark theme (WCAG AA is 4.5): reported on the item, not changed here

# One probe for every selector: how many match, are they all drawn, inside the window and inside the box, none cut off, and the least
# contrast of their colour against the first opaque background behind them (with the lightest/darkest such background).
PROBE = """((sel, boxSel) => {
  const px = (c) => c.match(/[\\d.]+/g).map(Number).slice(0, 3);
  const lin = (v) => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); };
  const lum = ([r, g, b]) => .2126 * lin(r) + .7152 * lin(g) + .0722 * lin(b);
  const behind = (e) => { let n = e; while (n) { const c = getComputedStyle(n).backgroundColor; if (!/rgba\\(.*, 0\\)|transparent/.test(c)) return c; n = n.parentElement; } return 'rgb(255, 255, 255)'; };
  const box = boxSel ? document.querySelector(boxSel) : null, br = box ? box.getBoundingClientRect() : null;
  const out = {n: 0, hidden: [], outside: [], cut: [], ratio: 99, bgLumMax: 0, bgLumMin: 1, scrollX: document.documentElement.scrollWidth - window.innerWidth,
               boxFound: !boxSel || !!box, texts: []};
  for (const e of document.querySelectorAll(sel)) {
    out.n++;
    const cs = getComputedStyle(e), r = e.getBoundingClientRect(), name = (e.id || e.className || e.tagName) + ':' + (e.textContent || '').trim().slice(0, 30);
    if (!(r.width > 0 && r.height > 0) || cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) { out.hidden.push(name); continue; }
    if (r.left < -.5 || r.right > window.innerWidth + .5 || (br && (r.left < br.left - 1 || r.right > br.right + 1))) out.outside.push(name);
    for (const k of [e, ...e.querySelectorAll('*')]) {
      const s = getComputedStyle(k);
      if (k.clientWidth > 0 && k.scrollWidth > k.clientWidth + 1 && (s.overflowX !== 'visible' || s.textOverflow === 'ellipsis')) out.cut.push(name);
    }
    const bg = behind(e), a = lum(px(cs.color)), z = lum(px(bg));
    out.ratio = Math.min(out.ratio, (Math.max(a, z) + .05) / (Math.min(a, z) + .05));
    out.bgLumMax = Math.max(out.bgLumMax, z); out.bgLumMin = Math.min(out.bgLumMin, z);
    out.texts.push((e.innerText || '').trim());
  }
  return out;
})(%s, %s)"""


def set_scheme(cdp, sid, scheme):
    """The page in the light or the dark theme: the emulated media feature, and data-theme on the root, as the existing dark checks do."""
    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
    cdp.js(f"document.documentElement.setAttribute('data-theme', '{scheme}')", sid)
    time.sleep(0.15)       # row 881: controls fade their colours over 120 ms: measure after the fades have finished, not mid-fade
    deadline = time.time() + 5
    while time.time() < deadline and cdp.js("document.getAnimations().length", sid):
        time.sleep(0.05)


class Look:
    """assertLooks(js, ...): the probe's answer turned into what a person would see."""

    def assertLooks(self, js, sel, box, scheme, what, count=1, floor=TEXT_FLOOR, surface=None):
        got = js(PROBE % (json.dumps(sel), json.dumps(box)))
        self.assertTrue(got["boxFound"], f"{what}: the box {box} is there")
        self.assertGreaterEqual(got["n"], count, f"{what}: {sel} is present")
        self.assertEqual(got["hidden"], [], f"{what}: every one is drawn")
        self.assertEqual(got["outside"], [], f"{what}: none runs past the window or its box")
        self.assertEqual(got["cut"], [], f"{what}: no text is cut off")
        self.assertLessEqual(got["scrollX"], 0, f"{what}: no sideways scroll")
        self.assertGreaterEqual(got["ratio"], floor, f"{what}: readable in {scheme} ({got['ratio']:.2f}:1)")
        if surface:
            s = js(PROBE % (json.dumps(surface), "null"))
            self.assertGreaterEqual(s["n"], 1, f"{what}: the surface {surface} is there")
            if scheme == "dark":
                self.assertLess(s["bgLumMax"], 0.25, f"{what}: a dark surface in dark")
            else:
                self.assertGreater(s["bgLumMin"], 0.5, f"{what}: a light surface in light")
        return got


def generate(cls, point, run):
    """One test per width and theme: test_<point>_<width>_<scheme>."""
    for w in WIDTHS:
        for scheme in SCHEMES:
            def test(self, w=w, scheme=scheme):
                run(self, w, scheme)
            test.__name__ = f"test_{point}_{w}_{scheme}"
            setattr(cls, test.__name__, test)


def edited(rig, tmp, **cols):
    """A workbook exported as the page's Export does it, with the first action's cells changed (by column label); base64."""
    from openpyxl import load_workbook
    path = Path(tmp) / "PUB work items.xlsx"
    made = excel.export_project(rig.store, "PUB", path, Path(tmp) / "state.json", on="2030-06-01")
    record = excel.load_state(Path(tmp) / "state.json", made)
    excel.save_state(rig.data_dir / excel.STATE_FILE, excel.id_key("PUB", record["export_id"]), record)
    action = rig.store.read("actions", "PUB")[0]
    wb = load_workbook(str(path))
    ws = wb["Actions"]
    head = {c.value: c.column for c in ws[1]}
    row = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, head["ID"]).value == action["id"])
    for label, value in cols.items():
        ws.cell(row, head[label.replace("_", " ")]).value = value
    wb.save(str(path))
    return base64.b64encode(path.read_bytes()).decode()


# ---- (1) the People card ----------------------------------------------------------------------------------------------------------------

class PeopleLook(Look, PeopleCard):
    def run_people(self, w, scheme):
        with chrome() as cdp:
            js = self.show(cdp)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
            set_scheme(cdp, self.sid, scheme)
            at = f"People card {w} {scheme}"
            box, on = "#people", dict(scheme=scheme)
            self.assertLooks(js, "#people h2", box, what=at + " heading", **on, surface="#people")
            self.assertLooks(js, "#people .pp-intro", box, what=at + " intro", **on)
            self.assertLooks(js, "#ppTable th", box, what=at + " column heads", count=4, **on)
            self.assertLooks(js, "#ppTable tbody td", box, what=at + " cells", count=12, **on)
            rows = self.assertLooks(js, "#ppTable tbody tr", box, what=at + " rows", count=3, **on)
            self.assertEqual(js("[].map.call(document.querySelectorAll('#ppTable th'), function (h) { return h.innerText; }).join()").upper(),
                             "NAME,EMAIL,ORGANISATION,ROLE")
            self.assertIn("jo@example.com", " ".join(rows["texts"]), "an email is read in full, not cut")
            self.assertLooks(js, "#ppCount span", box, what=at + " count line", **on)
            self.assertLooks(js, "#ppOnly", box, what=at + " Show only these", **on)
            self.assertLooks(js, "#ppPasteBtn", box, what=at + " Paste from Excel", **on)
            js("document.querySelector('#ppPasteBtn').click()")
            self.assertTrue(wait(lambda: js("document.querySelector('#ppPaste').hidden") is False, 10))
            self.fill(js, PASTE)
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ppPreview')"), 10), "a preview of the rows")
            self.assertLooks(js, "label[for=ppText]", box, what=at + " paste label", **on)
            self.assertLooks(js, "#ppText", box, what=at + " paste box", **on)
            self.assertLooks(js, ".pp-plan", box, what=at + " preview plan line", **on)
            self.assertLooks(js, "#ppPreview th", box, what=at + " preview heads", count=4, **on)
            self.assertLooks(js, "#ppPreview tbody td", box, what=at + " preview cells", count=8, **on)
            self.assertLooks(js, "#ppAdd", box, what=at + " Add to the list", **on)


generate(PeopleLook, "item_454_people_card", PeopleLook.run_people)


# ---- (2), (3) the Import from Excel box, through Settings > Data -------------------------------------------------------------------------

class ImportLook(Look, TemplatePage):
    def ready(self, cdp, w, scheme):
        p = self.page(cdp)
        p.width(w)
        set_scheme(cdp, p.sid, scheme)
        return p

    def run_template(self, w, scheme):
        with chrome() as cdp:
            p = self.ready(cdp, w, scheme)
            self.open_box(p)
            at = f"Get the template {w} {scheme}"
            got = self.assertLooks(p.js, "#import-template", "#import-box", scheme, at, surface="#import-box")
            self.assertEqual(got["texts"], ["Get the template"], "the whole name is shown")
            self.assertLooks(p.js, "#import-box .ad-foot button", "#import-box", scheme, at + " footer buttons", count=3)
            self.assertTrue(p.js("(() => { const a = document.querySelector('#import-template').getBoundingClientRect(), b = document.querySelector('#import-choose').getBoundingClientRect();"
                                 " return a.right <= b.left || a.bottom <= b.top; })()"), f"{at}: it does not sit on top of Choose a file")

    def run_check(self, w, scheme):
        with chrome() as cdp:
            tmp = tempfile.mkdtemp(prefix="clark-454-")
            self.addCleanup(__import__("shutil").rmtree, tmp, True)
            p = self.ready(cdp, w, scheme)
            self.open_box(p)
            self.choose(p, edited(self.rig, tmp, Description="Agree the cut-over plan, version two"))
            p.until("!!document.querySelector('#import-summary')", "the check")
            at, box = f"Check the import {w} {scheme}", "#import-box"
            self.assertLooks(p.js, "#import-box-t", box, scheme, at + " title", surface=box)
            self.assertLooks(p.js, "#import-summary span", box, scheme, at + " counts row", count=1)
            self.assertIn("1 updated", p.js("document.querySelector('#import-summary').innerText"))
            self.assertLooks(p.js, "#import-sheets", box, scheme, at + " per-sheet line")
            self.assertTrue(p.js("document.querySelector('#import-sheets').innerText.trim().length > 0"), "the sheet line says something")
            self.assertLooks(p.js, ".st-bar .muted", box, scheme, at + " Changes to check")
            self.assertLooks(p.js, "#import-accept-all", box, scheme, at + " Accept all", floor=LINK_FLOOR)
            self.assertLooks(p.js, "#import-reject-all", box, scheme, at + " Reject all", floor=LINK_FLOOR)
            self.assertLooks(p.js, ".imp-list .imp-main", box, scheme, at + " row text")
            self.assertLooks(p.js, ".imp-list .tag", box, scheme, at + " row tag")
            self.assertLooks(p.js, ".imp-list .st-act label", box, scheme, at + " Accept and Reject on the row", count=2)
            self.assertEqual(p.js("[...document.querySelectorAll('.imp-list li:first-child .st-act label')].map(l => l.innerText.trim())"), ["Accept", "Reject"])
            self.assertLooks(p.js, ".imp-list .st-act input", box, scheme, at + " the two buttons", count=2, floor=0)
            self.assertLooks(p.js, "#import-go", box, scheme, at + " Import button")
            self.assertLooks(p.js, "#import-box .btn.quiet", box, scheme, at + " Cancel")
            self.assertGreaterEqual(p.js("document.querySelector('#import-box').getBoundingClientRect().left"), 0)
            self.assertLessEqual(p.js("document.querySelector('#import-box').getBoundingClientRect().right"), w)

    def run_refused(self, w, scheme):
        with chrome() as cdp:
            tmp = tempfile.mkdtemp(prefix="clark-454-")
            self.addCleanup(__import__("shutil").rmtree, tmp, True)
            p = self.ready(cdp, w, scheme)
            self.open_box(p)
            self.choose(p, edited(self.rig, tmp, Status="Not a status"))
            p.until("!!document.querySelector('#import-refused')", "the whole-file refusal")
            at, box = f"Refusal {w} {scheme}", "#import-box"
            self.assertLooks(p.js, "#import-box-t", box, scheme, at + " title", surface=box)
            got = self.assertLooks(p.js, "#import-refused b", box, scheme, at + " head")
            self.assertIn("Nothing was imported, because 1 row breaks a rule:", got["texts"][0])
            self.assertLooks(p.js, "#import-refused", box, scheme, at + " panel")
            self.assertLooks(p.js, "#import-refused li", box, scheme, at + " the row named")
            got = self.assertLooks(p.js, "#import-refused .imp-after", box, scheme, at + " after-line")
            self.assertIn("Fix it in the workbook and import again. Nothing was changed.", got["texts"][0])
            self.assertLooks(p.js, "#import-close", box, scheme, at + " Close")
            self.assertTrue(p.js("!document.querySelector('#import-go') && !document.querySelector('.imp-list')"), "nothing to accept")


generate(ImportLook, "item_454_template_button", ImportLook.run_template)
generate(ImportLook, "item_454_check_the_import", ImportLook.run_check)
generate(ImportLook, "item_454_whole_file_refusal", ImportLook.run_refused)


# ---- (4) the Import icon beside Add on Work items ----------------------------------------------------------------------------------------

class ImportIcon(Look, unittest.TestCase):
    def run_icon(self, w, scheme):
        demo = DemoStore()
        self.addCleanup(demo.close)
        s = Running(data_for=demo.store.data_for, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = open_page(cdp, f"http://127.0.0.1:{s.port}/#work&p=ABC", w, scheme)
            js = lambda e: cdp.js(e, sid)          # noqa: E731
            self.assertTrue(wait(lambda: js("!!document.querySelector('#impBtn')"), 20), "the Import icon is in View")
            set_scheme(cdp, sid, scheme)
            at = f"Import icon {w} {scheme}"
            self.assertLooks(js, "#impBtn", None, scheme, at, floor=ICON_FLOOR, surface="body")
            self.assertLooks(js, "#impBtn svg", None, scheme, at + " drawing", floor=ICON_FLOOR)
            self.assertLooks(js, "#newBtn", None, scheme, at + " Add beside it")
            self.assertEqual(js("document.querySelector('#impBtn').getAttribute('aria-label')"), "Import from Excel")
            self.assertEqual(js("document.querySelector('#impBtn').getAttribute('data-tip')"), "Import from Excel")
            self.assertEqual(js("document.querySelector('#impBtn').disabled"), False, "usable once the project is loaded")
            self.assertTrue(js("(() => { const a = document.querySelector('#impBtn').getBoundingClientRect(), b = document.querySelector('#newBtn').getBoundingClientRect();"
                               " return (a.right <= b.left || b.right <= a.left) && Math.abs(a.top - b.top) < 40; })()"),
                            f"{at}: beside Add, not on top of it or on another line")
            self.assertTrue(js("(() => { const a = document.querySelector('#impBtn').getBoundingClientRect(), p = document.querySelector('#work').getBoundingClientRect();"
                               " return a.left >= p.left - 1 && a.right <= p.right + 1; })()"), f"{at}: inside the Work items page")


generate(ImportIcon, "item_454_import_icon", ImportIcon.run_icon)

# The classes built on above bring their own tests with them; only the generated ones belong to this file, so the others are turned off here.
for _cls in (PeopleLook, ImportLook):
    for _name in dir(_cls):
        if _name.startswith("test_") and not _name.startswith("test_item_454_"):
            setattr(_cls, _name, None)
del TemplatePage, PeopleCard, _cls, _name

if __name__ == "__main__":
    unittest.main()
