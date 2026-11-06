"""Item 660, editors throughout: every plain text box opens at three lines, grows as it is typed in with one blank line always under the
last, shrinks as text goes (down to three lines), has a corner handle, and keeps a height the person pulled by hand. The rich editor and
the Draft email body have the handle and the three-line floor from CSS. Edit only: the published page has no textarea and no useGrow.
Run: python3 dev/run_tests.py test_item_660_editors
"""
import json
import unittest

from _paths import ROOT
import _rich_page as rp
import build_page
import test_peek_latest as tpl
from test_ask_panel import Panel
from test_server import chrome, wait  # noqa: E402

SIZE = ("(e => { const c = getComputedStyle(e), l = parseFloat(c.lineHeight) || parseFloat(c.fontSize) * 1.2; "
        "return {h: e.getBoundingClientRect().height, line: l, content: e.scrollHeight, resize: c.resize, sized: !!e.dataset.sized, "
        "ow: document.documentElement.scrollWidth - document.documentElement.clientWidth}; })(%s)")
MANY = "\n".join(f"line {i}" for i in range(1, 11))


class Rules:
    """The checks every box shares; `get()` reads its size from the page, `type(text)` puts text in it, `clear()` empties it."""

    def check(self, get, put, clear, drag, width, label):
        a = get()
        self.assertGreaterEqual(a["h"], 3 * a["line"] - 1, f"{label}: opens at three lines")
        self.assertNotEqual(a["resize"], "none", f"{label}: a corner handle")
        put(MANY)
        b = get()
        self.assertGreater(b["h"], a["h"], f"{label}: grows as it is typed in")
        self.assertGreaterEqual(b["h"], 10 * b["line"] + b["line"] - 4, f"{label}: a blank line below the last")
        self.assertLessEqual(b["ow"], 20, f"{label}: no sideways scroll at {width}")
        clear()
        c = get()
        self.assertLessEqual(c["h"], a["h"] + 2, f"{label}: shrinks back to three lines")
        put(MANY)
        drag()
        d = get()
        self.assertTrue(d["sized"], f"{label}: pulling the handle marks it sized by hand")
        put(MANY + "\nmore\nmore\nmore")
        self.assertAlmostEqual(get()["h"], d["h"], delta=2, msg=f"{label}: a hand size is kept while typing")


class Boxes(unittest.TestCase, Rules):
    load = tpl.Browser.load
    fresh = tpl.Browser.fresh
    HOLD = tpl.Browser.HOLD

    def test_latest_update_in_the_peek(self):
        for width in (1400, 900):
            for dark in (False, True):
                with chrome() as cdp:
                    sent, sid = self.load(cdp, width, tpl.OVERDUE, dark=dark)
                    cdp.js("document.querySelector('[data-pk-latest-text]').click()", sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-latest-in]')", sid)))
                    sel = "document.querySelector('[data-pk-latest-in]')"
                    self.drive(cdp, sid, sel, width, f"latest {width} {dark}")

    def drive(self, cdp, sid, sel, width, label):
        def put(text):
            cdp.js(f"(e => {{ e.focus(); e.value = {json.dumps(text)}; e.dispatchEvent(new Event('input', {{bubbles: true}})); }})({sel})", sid)
        self.check(lambda: cdp.js(SIZE % sel, sid), put, lambda: put(""),
                   lambda: (cdp.js(f"(e => {{ e.style.height = (e.offsetHeight + 60) + 'px'; e.dispatchEvent(new Event('pointerup')); }})({sel})", sid)),
                   width, label)


class Ask(Panel):
    def test_ask_box(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                for theme in ("light", "dark"):
                    p.js(f"document.documentElement.dataset.theme = '{theme}'")
                    p.key("/", code="Slash", vk=191)
                    p.until("!!document.querySelector('#ask-panel')", "opened")
                    p.until("!document.querySelector('#ask-send').disabled", "ready")
                    sel = "document.querySelector('#ask-box')"
                    def put(text):
                        p.js(f"(e => {{ e.focus(); e.value = {json.dumps(text)}; e.dispatchEvent(new Event('input', {{bubbles: true}})); }})({sel})")
                    put("")
                    Rules.check(self, lambda: p.js(SIZE % sel), put, lambda: put(""),
                                lambda: p.js(f"(e => {{ e.style.height = (e.offsetHeight + 20) + 'px'; e.dispatchEvent(new Event('pointerup')); }})({sel})"),
                                width, f"ask {width} {theme}")
                    panel = p.js("(r => ({b: r.bottom, h: innerHeight}))(document.querySelector('#ask-panel').getBoundingClientRect())")
                    self.assertLessEqual(panel["b"], panel["h"] + 1, "the panel stays inside the window")
                    p.key("Escape", code="Escape", vk=27)
                    p.until("!document.querySelector('#ask-panel')", "closed")


for _n in dir(Panel):
    if _n.startswith("test_"):
        setattr(Ask, _n, None)                       # only this file's own test runs, not the panel's


class Rich(unittest.TestCase):
    def test_rich_editor_and_draft_email_body_have_a_floor_and_a_handle(self):
        with rp.Harness(chrome) as h:
            for width in (1400, 900):
                for theme in ("light", "dark"):
                    h.resize(width)
                    h.theme(theme)
                    h.ev("(() => { if (!document.getElementById('editcss')) { const s = document.createElement('style'); s.id = 'editcss'; s.textContent = %s; document.head.append(s); } })()" % json.dumps(build_page.EDIT_CSS.read_text(encoding="utf-8")))
                    h.mount("")
                    r = h.ev("(e => { const c = getComputedStyle(e), l = parseFloat(c.lineHeight) || 24; return {h: e.getBoundingClientRect().height, l, resize: c.resize, ov: c.overflowY}; })(document.querySelector('.rt-host'))")
                    self.assertGreaterEqual(r["h"], 3 * r["l"] - 1)
                    self.assertEqual((r["resize"], r["ov"]), ("vertical", "auto"))
                    self.assertGreater(h.ev("parseFloat(getComputedStyle(document.querySelector('.rt-host .ProseMirror')).paddingBottom)"), 10, "a blank line under the last")
                    for i in range(8):
                        h.type(f"line {i}")
                        h.key("Enter", code="Enter", vk=13)
                    r2 = h.ev("document.querySelector('.rt-host').getBoundingClientRect().height")
                    self.assertGreater(r2, r["h"], "it grows as it is typed in")
                    self.assertLessEqual(h.ev("document.documentElement.scrollWidth - document.documentElement.clientWidth"), 20)
                    h.ev("(() => { const d = document.createElement('div'); d.className = 'de-preview'; d.id = 'de'; document.body.append(d); })()")
                    de = h.ev("(e => { const c = getComputedStyle(e); return {h: e.getBoundingClientRect().height, l: parseFloat(c.lineHeight) || 24, resize: c.resize, max: c.maxHeight}; })(document.querySelector('#de'))")
                    self.assertGreaterEqual(de["h"], 3 * de["l"] - 1)
                    self.assertEqual(de["resize"], "vertical")
                    self.assertNotEqual(de["max"], "320px")
                    h.ev("document.querySelector('#de').remove()")


class Published(unittest.TestCase):
    def test_the_published_page_has_no_textarea_and_no_useGrow(self):
        view = (ROOT / "src/clark/page/page-view.html").read_text(encoding="utf-8")
        self.assertNotIn("<textarea", view)
        self.assertNotIn("useGrow", view)
        self.assertNotIn("fitGrow", view)


if __name__ == "__main__":
    unittest.main()
