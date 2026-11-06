"""Row 765: the project form (New project and Edit) draws every field with a visible 1 px border, the labels stacked above them, the fields flush
with the heading, at 1400 and 900 px, light and dark. The form is a Settings box, so it exists in Edit mode only; a published (View) page has none.

Run: python3 dev/run_tests.py test_project_form_look
"""
import base64
import os
import tempfile
import unittest

from _paths import SRC

from clark import page
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

SHOTS = os.environ.get("CLARK_SHOTS_765", "")          # a folder: each case saves a screenshot into it

MEASURE = """(() => {
  const f = document.querySelector('#project-form'), q = (s) => document.querySelector(s);
  const r = (el) => el.getBoundingClientRect();
  const fields = ['#pN', '#pC', '#pCl', '#pW'].map((s) => { const e = q(s), c = getComputedStyle(e);
    return {id: s, bw: [c.borderTopWidth, c.borderRightWidth, c.borderBottomWidth, c.borderLeftWidth], bs: c.borderTopStyle, bc: c.borderTopColor, left: r(e).left, right: r(e).right}; });
  const labels = ['pN', 'pC', 'pCl', 'pW'].map((id) => { const l = r(q('label[for=' + id + ']')), e = r(q('#' + id));
    return {left: l.right <= e.left + 1, sameRow: l.top < e.bottom && l.bottom > e.top, labelX: l.left, order: l.top}; });
  const form = q('#project-form .dlg-form'), fc = getComputedStyle(form);
  return {fields, labels, headLeft: r(q('#project-form-t')).left, formPad: fc.paddingLeft + '/' + fc.paddingTop,
          boxTop: r(f).top, boxBottom: r(f).bottom, boxLeft: r(f).left, boxRight: r(f).right, vw: document.documentElement.clientWidth, vh: innerHeight, fieldLeft: Math.min(...fields.map((x) => x.left)), topbar: r(q('.top')).bottom, surface: getComputedStyle(q('#pN')).backgroundColor, boxBg: getComputedStyle(f).backgroundColor};
})()"""


def lum(css):
    nums = [float(x) for x in css[css.index("(") + 1:css.index(")")].replace("/", ",").replace(" ", ",").split(",") if x][:3]
    ch = [(v / 255) / 12.92 if v / 255 <= 0.03928 else (((v / 255) + 0.055) / 1.055) ** 2.4 for v in nums]
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]


def contrast(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


class Look(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        import shutil
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def serve(self):
        names = {p["code"]: p["name"] for p in self.store.read("projects")}
        data = {c: self.store.data_for(c) for c in names}
        s = Running(data_for=lambda code, **kw: data.get(code),
                    projects=lambda archived=False: [] if archived else [{"code": c, "name": n} for c, n in sorted(names.items())],
                    page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        return s

    def open_form(self, cdp, port, width, scheme, opener):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{port}/#settings&p=TUL"}, sid)
        self.assertTrue(wait(lambda: bool(cdp.js("!!document.querySelector('#projects-table tbody tr')", sid)), 30), "the projects table")
        cdp.js("document.querySelector('%s').click()" % opener, sid)
        self.assertTrue(wait(lambda: bool(cdp.js("!!document.querySelector('#project-form')", sid)), 30), "the project form")
        self.assertTrue(wait(lambda: bool(cdp.js("document.getAnimations().length === 0", sid)), 30), "the box has finished easing in (row 877: it starts 12 px lower and a little smaller)")
        return sid

    def cases(self):
        out, s = [], self.serve()
        for kind, opener in (("new", "#npBtn"), ("edit", "tr[data-project=MOSS] [data-edit]")):
            for width in (1400, 900):
                for scheme in ("light", "dark"):
                    with chrome() as cdp:
                        sid = self.open_form(cdp, s.port, width, scheme, opener)
                        m = cdp.js(MEASURE, sid)
                        if SHOTS:
                            shot = cdp.call("Page.captureScreenshot", {"format": "png"}, sid)
                            with open(os.path.join(SHOTS, f"projectform-{kind}-{scheme}-{width}.png"), "wb") as fh:
                                fh.write(base64.b64decode(shot["data"]))
                        out.append((kind, width, scheme, m))
        return out

    def test_every_field_has_a_visible_one_pixel_border_in_light_and_dark(self):
        for kind, width, scheme, m in self.cases():
            for f in m["fields"]:
                self.assertEqual(f["bw"], ["1px"] * 4, (kind, width, scheme, f["id"]))
                self.assertEqual(f["bs"], "solid", (kind, width, scheme, f["id"]))
                for bg in (m["surface"], m["boxBg"]):
                    self.assertGreaterEqual(contrast(f["bc"], bg), 1.5, (kind, width, scheme, f["id"], "the border is seen against the field and the box"))

    def test_each_label_is_left_of_its_field_on_one_row_in_two_columns(self):
        for kind, width, scheme, m in self.cases():
            self.assertTrue(all(x["left"] and x["sameRow"] for x in m["labels"]), (kind, width, scheme, "labels left of their fields"))
            self.assertEqual(m["formPad"], "0px/0px", (kind, width, scheme, "no second indent"))
            self.assertEqual(len({round(x["labelX"]) for x in m["labels"]}), 1, (kind, width, scheme, "one label column"))
            self.assertEqual(len({round(f["left"]) for f in m["fields"]}), 1, (kind, width, scheme, "one field column"))
            self.assertEqual([x["order"] for x in m["labels"]], sorted(x["order"] for x in m["labels"]), (kind, width, scheme, "order kept"))

    def test_the_box_is_centred_across_and_in_the_space_below_the_top_bar(self):
        for kind, width, scheme, m in self.cases():
            self.assertAlmostEqual(m["boxLeft"], m["vw"] - m["boxRight"], delta=2, msg=(kind, width, scheme, "centred across"))
            self.assertAlmostEqual(m["boxTop"] - m["topbar"] - 32, m["vh"] - m["boxBottom"] - 32, delta=2, msg=(kind, width, scheme, "centred down"))
            self.assertGreater(m["boxTop"] - m["topbar"], 40, (kind, width, scheme, "not pinned to the top"))

    def test_the_box_still_starts_below_the_top_bar(self):            # row 758 kept
        for kind, width, scheme, m in self.cases():
            self.assertGreaterEqual(m["boxTop"], m["topbar"], (kind, width, scheme))


if __name__ == "__main__":
    unittest.main()
