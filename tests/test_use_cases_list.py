"""#157 step 2, part A: the Use cases page in the editor (the list, the filters, the search, the sort, the eye), in a real browser.

Run: python3 dev/run_tests.py test_use_cases_list
The page is the committed one, served by a real server whose change and undo routes are the real clark.changes over a real store in a
temporary folder (fictional data), so the eye changes the store and its Undo puts it back. Laptop widths only: 1400 and 900 px, light
and dark. A published file never has the tab, the route or the page: that is checked on a real published file and on the bytes of
page-view.html. The page for one use case is another part (components/UseCaseDetail.jsx); here only its address is checked.
"""
import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from _demo import USER
from _paths import SRC
from _new_page import reload_to_new_page
from test_report_editor import EMPTY_BRANDING, Base, Pg, tearDownModule  # noqa: F401
from test_server import chrome, wait

from clark import publish

PAGE = SRC / "clark" / "page"
KEYS = {"Enter": 13, " ": 32, "Escape": 27, "ArrowDown": 40, "ArrowUp": 38, "ArrowLeft": 37, "ArrowRight": 39, "Home": 36, "End": 35, "Tab": 9}
LATE = "2020-01-01"
OFF = "Not on the dashboard"
ON = "On the dashboard"


def plant(self):
    """Four use cases of project ABC: 1.1 and 1.2 on the dashboard, 1.10 and 2.1 not; work items and milestones linked to them."""
    d = self.demo
    self.uc1 = d.use_case
    with self.store.step("dashboard", USER) as st:
        st.update("use_cases", self.uc1, {"ref": "1.1", "headline": "Matching is live for two suppliers", "standing": "<p>Live for two suppliers.</p>"})
        self.uc2 = st.create("use_cases", {"project": "ABC", "title": "Payment runs", "status": "Flag", "ref": "1.2", "sort_order": 2,
                                           "headline": "One supplier file still fails", "standing": "<p>Two of three files load.</p>", "source": "demo"})
        self.uc3 = st.create("use_cases", {"project": "ABC", "title": "Supplier portal", "status": "High risk", "ref": "1.10", "sort_order": 3,
                                           "headline": "No login for the smallest suppliers", "standing": "<p>Design is not agreed.</p>", "client_visible": 0, "source": "demo"})
        self.uc4 = st.create("use_cases", {"project": "ABC", "title": "Month end close", "status": "On track", "ref": "2.1", "sort_order": 4,
                                           "headline": "Done in two days since the autumn", "standing": "<p>Zebra checklist signed off.</p>", "client_visible": 0, "source": "demo"})
        self.m2 = st.create("milestones", {"project": "ABC", "name": "Supplier go-live", "baseline_date": "2030-06-01", "source": "demo"})
    d.action(description="Match the first batch", owner="Pat Demo", due_date=LATE, use_case=self.uc1, milestone=d.milestone)
    d.action(description="Match the second batch", owner="Pat Demo", status="Closed", use_case=self.uc1, milestone=d.milestone)
    d.action(description="Fix the failing file", owner="Sam Demo", due_date=LATE, use_case=self.uc2, milestone=self.m2)
    d.action(description="Agree the run dates", owner="Sam Demo", due_date=LATE, use_case=self.uc2)
    d.action(description="Check the bank format", owner="Lee Demo", due_date=LATE, use_case=self.uc2)
    d.action(description="Write the close checklist", owner="Lee Demo", due_date=LATE, use_case=self.uc4, milestone=self.m2)


def contrast_script(selectors):
    return """(() => {
      const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
      const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
      const ratio = (a, b) => { const x = lum(rgb(a)), y = lum(rgb(b)); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
      const out = [];
      for (const sel of %s) {
        for (const el of document.querySelectorAll(sel)) {
          let bg = el, back = 'rgba(0, 0, 0, 0)';
          while (bg && /rgba\\(.*, 0\\)|transparent/.test(back)) { back = getComputedStyle(bg).backgroundColor; bg = bg.parentElement; }
          out.push([sel, ratio(getComputedStyle(el).color, back), getComputedStyle(el).fontSize]);
        }
      }
      return out;
    })()""" % json.dumps(selectors)


class Setup(Base):
    def setUp(self):
        super().setUp()
        plant(self)

    def show(self, cdp, width=1400, dark=False, edit=False, hash_="#usecases&p=ABC"):
        p = Pg.at(self, cdp, self.s.port, hash_)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, p.sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        if dark:
            p.js("document.documentElement.dataset.theme = 'dark'")
        if hash_ == "#usecases&p=ABC":
            p.until("document.querySelectorAll('#usecases .ucl-row[data-uc]').length > 0 || !!document.querySelector('#usecases [data-empty]')", "the list drew")
        if hash_.startswith("#dashboard"):
            p.until("document.querySelectorAll('[data-mode]').length === 3", "the Dashboard drew its whole View | Edit switch (row 804)")
            self.assertEqual(p.js("document.querySelectorAll('[data-mode]').length"), 3, "the View | Edit switch is on the Dashboard")      # row 804: the Dashboard has it, so the page must have drawn before anything is read (a race on a slow runner)
        else:
            self.assertEqual(p.js("document.querySelectorAll('[data-mode]').length"), 0, "no View | Edit switch off the Dashboard: the page is always editable")
        if edit:
            p.until("!!document.querySelector('#usecases [data-eye]')", "the page shows the eyes")
        return p

    def refs(self, p):
        return p.js("[...document.querySelectorAll('#usecases .ucl-list .ucl-row')].map(r => r.querySelector('.ucl-ref').textContent)")

    def count(self, p):
        return p.js("document.querySelector('#ucl-count').textContent")

    def row(self, ref):
        return {r["ref"]: r for r in self.store.read("use_cases", "ABC")}[ref]

    def eye(self, ref):
        return self.row(ref)["client_visible"]

    def press(self, p, name):
        for kind in ("keyDown", "keyUp"):
            p.cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": name, "code": {" ": "Space"}.get(name, name), "windowsVirtualKeyCode": KEYS[name],
                                                   **({"text": "\r" if name == "Enter" else " "} if name in ("Enter", " ") and kind == "keyDown" else {})}, p.sid)

    def type_in(self, p, selector, text):
        p.js(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); e.focus(); e.select(); }})()")
        p.cdp.call("Input.insertText", {"text": text}, p.sid)

    def reload(self, p):
        """Reload and wait for the NEW document (a bare wait could still see the old one)."""
        reload_to_new_page(p.js, "document.querySelectorAll('#usecases .ucl-row').length > 0")

    def click(self, p, selector):
        p.js(f"document.querySelector({json.dumps(selector)}).scrollIntoView({{block: 'center'}})")
        x, y, _ = p.box(selector)
        p.mouse("mouseMoved", x, y)
        p.mouse("mousePressed", x, y, 1)
        p.mouse("mouseReleased", x, y)


class Tab(Setup):
    def test_the_tab_sits_beside_milestones_in_the_editor_and_opens_the_page(self):
        with chrome() as cdp:
            p = self.show(cdp, hash_="#dashboard&p=ABC")
            p.ready()
            self.assertEqual(p.js("[...document.querySelectorAll('.tabs .tab')].map(t => t.innerText)"), ["Dashboard", "Work items", "Milestones", "Use cases"])      # row 976: no Settings tab
            p.js("document.querySelector('[data-view=usecases]').click()")
            p.until("location.hash === '#usecases&p=ABC' && !!document.querySelector('#usecases .ucl-row')", "the tab opened the page at its own address")
            self.assertEqual(p.js("document.querySelector('.tab[aria-selected=true]').textContent"), "Use cases")
            self.assertEqual(p.js("document.querySelector('#usecases h1').textContent"), "Use cases")

    def test_back_and_forward_step_through_the_page_and_a_use_case(self):
        with chrome() as cdp:
            p = self.show(cdp, hash_="#dashboard&p=ABC")
            p.ready()
            p.js("document.querySelector('[data-view=usecases]').click()")
            p.until("!!document.querySelector('#usecases .ucl-row')", "the list")
            p.js("document.querySelector('[data-uc=\"%s\"] .ucl-go').click()" % self.uc2)
            p.until("location.hash === '#usecases&p=ABC&uc=1.2' && !!document.querySelector('[data-ucd]')", "a use case has its own address and page")
            self.assertIn("1.2", p.js("document.querySelector('[data-ucd] .ucd-crumb').textContent"))
            self.assertEqual(p.js("document.querySelectorAll('#usecases .ucl-row').length"), 0)
            p.js("history.back()")
            p.until("location.hash === '#usecases&p=ABC' && !!document.querySelector('#usecases .ucl-row')", "Back to the list")
            p.until("!!document.activeElement.closest && !!document.activeElement.closest('.ucl-row') && document.activeElement.closest('.ucl-row').dataset.uc === '%s'" % self.uc2, "the row it came from takes the focus")
            p.js("history.back()")
            p.until("location.hash === '#dashboard&p=ABC'", "Back to the dashboard")
            p.js("history.forward()")
            p.until("location.hash === '#usecases&p=ABC' && !!document.querySelector('#usecases .ucl-row')", "Forward to the list")
            p.js("history.forward()")
            p.until("location.hash === '#usecases&p=ABC&uc=1.2' && !!document.querySelector('[data-ucd]')", "Forward to the use case")

    def test_a_typed_address_opens_a_use_case_and_an_unknown_one_opens_the_list(self):
        with chrome() as cdp:
            p = self.show(cdp, hash_="#usecases&p=ABC&uc=1.10")          # a reference with a dot, typed
            p.until("!!document.querySelector('[data-ucd]')", "the page of use case 1.10")
            self.assertIn("Supplier portal", p.js("document.querySelector('[data-ucd] h1').textContent"))
        with chrome() as cdp:
            p = self.show(cdp, hash_="#usecases&p=ABC&uc=" + self.uc4)       # its id also names it
            p.until("!!document.querySelector('[data-ucd]')", "the page of use case 2.1 by its id")
        with chrome() as cdp:
            p = self.show(cdp, hash_="#usecases&p=ABC&uc=9.9")
            p.until("location.hash === '#usecases&p=ABC' && !!document.querySelector('#usecases .ucl-row')", "an unknown use case: the list, the entry rewritten")

    def test_the_other_pages_do_not_read_a_use_case_key(self):
        with chrome() as cdp:
            p = self.show(cdp, hash_="#work&p=ABC&uc=1.1")
            p.until("!!document.querySelector('#work')", "work")
            self.assertEqual(p.js("location.hash"), "#work&p=ABC&uc=1.1", "the address is left as typed; the page ignores the key")
            self.assertEqual(p.js("document.querySelectorAll('#usecases, #usecase').length"), 0)


class Published(Setup):
    def publish(self):
        out = tempfile.mkdtemp(prefix="clark-157a-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        return Path(publish.publish(self.store, "ABC", out, by_user=USER, now="2026-10-28", branding=EMPTY_BRANDING)["path"])

    def draw(self, cdp, path, hash_=""):
        tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": path.as_uri() + hash_}, sid)
        p = Pg(self, cdp, sid)
        p.until("document.documentElement.dataset.ready === '1' && !!document.querySelector('h1')", "the file drew")
        return p

    def test_a_published_file_has_a_view_only_tab_and_no_route_and_no_editor_page_and_keeps_the_selected_use_cases(self):
        path = self.publish()
        for hash_ in ("", "#usecases&p=ABC", "#usecases&p=ABC&uc=1.1"):
            with self.subTest(hash=hash_), chrome() as cdp:
                p = self.draw(cdp, path, hash_)
                self.assertEqual(p.js("[...document.querySelectorAll('.tabs .tab')].map(t => t.textContent)"), ["Dashboard", "Work items", "Milestones", "Use cases"])
                self.assertEqual(p.js("document.querySelectorAll('#usecases, #usecase, .ucl-row, [data-uc-more], .ucmore').length"), 0)
                if hash_:
                    self.assertEqual(p.js("document.querySelector('.tab[aria-selected=true]').textContent"), "Use cases", "an address of the Use cases page opens the file's own tab")
                    continue
                self.assertEqual(p.js("document.querySelector('.tab[aria-selected=true]').textContent"), "Dashboard")
                self.assertEqual(p.js("document.querySelector('.uctotal').textContent"), "2 use cases", "the file shows the selected use cases only")
                self.assertNotIn("Supplier portal", p.js("document.body.innerText"))

    def test_the_view_build_holds_no_part_of_the_page(self):
        text = (PAGE / "page-view.html").read_text(encoding="utf-8")
        for mine in ("ucl-row", "ucl-bar", "ucl-eye", "UseCaseDetail", "Not on the dashboard", "On the dashboard", "Narrow the list", "Showing ", "/api/change"):
            self.assertNotIn(mine, text, mine)
        live = (PAGE / "page.html").read_text(encoding="utf-8")
        for mine in ("ucl-row", "ucl-eye", "Not on the dashboard"):
            self.assertIn(mine, live, mine)


class Dashboard(Setup):
    def test_the_summary_shows_only_the_selected_and_says_how_many_more_are_on_the_page(self):
        with chrome() as cdp:
            p = self.show(cdp, hash_="#dashboard&p=ABC")
            p.until("!!document.querySelector('.uc')", "the summary drew")
            self.assertEqual(p.js("document.querySelector('.uctotal').textContent"), "2 use cases")
            self.assertEqual(p.js("[...document.querySelectorAll('.ucrow .ucref')].map(e => e.textContent)"), ["1.1", "1.2"])
            self.assertEqual(p.js("document.querySelector('[data-uc-more]').textContent"), "2 more on the Use cases page")
            p.js("document.querySelector('[data-uc-more]').click()")
            p.until("location.hash === '#usecases&p=ABC' && !!document.querySelector('#usecases .ucl-row')", "the line links to the page")
            p.js("history.back()")
            p.until("location.hash === '#dashboard&p=ABC' && !!document.querySelector('.uc')", "Back")

    def test_with_every_use_case_selected_there_is_no_line(self):
        self.store.con.execute("UPDATE use_cases SET client_visible = 1")
        self.store.con.commit()
        with chrome() as cdp:
            p = self.show(cdp, hash_="#dashboard&p=ABC")
            p.until("!!document.querySelector('.uc')", "the summary drew")
            self.assertEqual(p.js("document.querySelector('.uctotal').textContent"), "4 use cases")
            self.assertEqual(p.js("document.querySelectorAll('[data-uc-more]').length"), 0)

    def test_with_none_selected_it_says_so_and_still_links(self):
        self.store.con.execute("UPDATE use_cases SET client_visible = 0")
        self.store.con.commit()
        with chrome() as cdp:
            p = self.show(cdp, hash_="#dashboard&p=ABC")
            p.until("!!document.querySelector('[data-nouc]')", "the empty summary drew")
            self.assertEqual(p.js("document.querySelector('[data-nouc]').textContent"), "No use cases are on the dashboard.")
            self.assertEqual(p.js("document.querySelector('[data-uc-more]').textContent"), "4 more on the Use cases page")


class List(Setup):
    def test_every_use_case_is_listed_selected_or_not_with_all_its_parts(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width, dark)
                    self.assertEqual(self.refs(p), ["UC 1.1", "UC 1.2", "UC 1.10", "UC 2.1"], "all four, in reference order (1.2 before 1.10)")
                    rows = {r["ref"]: r for r in p.js("""[...document.querySelectorAll('#usecases .ucl-list .ucl-row')].map(r => ({
                        ref: r.querySelector('.ucl-ref').textContent, name: r.querySelector('.ucl-go').textContent, head: r.querySelector('.ucl-name small').textContent,
                        status: r.querySelector('.ucl-st .pill').textContent, dot: getComputedStyle(r.querySelector('.ucl-st .pill'), '::before').content,
                        work: r.querySelector('.ucl-wi').innerText.replace(/\\s+/g, ' '), ms: r.querySelector('.ucl-ms-s') ? r.querySelector('.ucl-ms-s').textContent : '',
                        eye: r.querySelector('.ucl-eye').title, label: r.querySelector('.ucl-go').getAttribute('aria-label') }))""")}
                    self.assertEqual(rows["UC 1.1"]["name"], "Invoice matching")
                    self.assertEqual(rows["UC 1.1"]["head"], "Matching is live for two suppliers")
                    self.assertEqual(rows["UC 1.1"]["status"], "On track")
                    self.assertEqual(rows["UC 1.1"]["dot"], '""', "the status has its dot as well as its word")
                    self.assertEqual(rows["UC 1.1"]["work"], "2 linked 1 open")
                    self.assertEqual(rows["UC 1.2"]["work"], "3 linked 3 open")
                    self.assertEqual(rows["UC 1.10"]["work"], "None linked")
                    self.assertEqual(rows["UC 1.1"]["eye"], ON)
                    self.assertEqual(rows["UC 1.10"]["eye"], OFF)
                    self.assertEqual(rows["UC 2.1"]["eye"], OFF)
                    self.assertEqual(rows["UC 1.1"]["label"], f"UC 1.1, Invoice matching, On track, 1 of 2 work items open, {ON}")
                    self.assertEqual(rows["UC 1.10"]["label"], f"UC 1.10, Supplier portal, High risk, No work items, {OFF}")
                    self.assertEqual(rows["UC 1.2"]["status"], "Flag")
                    self.assertEqual(rows["UC 1.10"]["status"], "High risk")
                    ms = p.js("[...document.querySelectorAll('#usecases .ucl-list .ucl-ms')].map(e => e.textContent)")
                    self.assertEqual(ms, ["Pilot live", "Supplier go-live", "None", "Supplier go-live"], "the milestones its work items point at")
                    self.assertEqual(self.count(p), "Showing 4 of 4 · 2 on the dashboard")
                    self.assertFalse(p.js("[...document.querySelectorAll('#usecases .ucl-list .ucl-row')].some(r => r.querySelector('.ucl-ref').textContent === 'UC 9')"))

    def test_the_page_is_laid_out_without_sideways_scroll_and_every_control_is_big_enough(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width, dark, edit=True)
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")
                    self.assertEqual(p.js("[...document.querySelectorAll('#usecases, #usecases *')].filter(e => e.scrollWidth > e.clientWidth + 1 && /auto|scroll/.test(getComputedStyle(e).overflowX)).length"), 0)
                    small = p.js("""[...document.querySelectorAll('#usecases button, #usecases input:not([type=checkbox]), #usecases a, #usecases [tabindex]')].map(e => {
                        const r = e.getBoundingClientRect(); return [e.className || e.id || e.tagName, Math.round(r.width), Math.round(r.height)]; }).filter(x => x[1] < 24 || x[2] < 24)""")
                    self.assertEqual(small, [], "every control is at least 24 px each way")
                    p.js("document.querySelector('#ucl-group').click()")
                    p.until("!!document.querySelector('.ddmenu [role=menuitemradio]')", "the Group by menu opened")
                    small = p.js("""[...document.querySelectorAll('.ddmenu [role=menuitemradio]')].map(e => { const r = e.getBoundingClientRect(); return [e.className || e.tagName, Math.round(r.width), Math.round(r.height)]; }).filter(x => x[1] < 24 || x[2] < 24)""")
                    self.assertEqual(small, [], "the Group by choices are big enough")
                    self.assertTrue(p.js("[...document.querySelectorAll('.ddmenu')].every(e => e.getBoundingClientRect().right <= window.innerWidth)"), "the menu stays in the window")
                    sizes = p.js("[...document.querySelectorAll('#usecases *')].filter(e => e.childNodes.length && [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())).map(e => parseFloat(getComputedStyle(e).fontSize))")
                    self.assertGreaterEqual(min(sizes), 13, "no text under 13 px")

    def test_text_contrast_is_at_least_4_5_to_1_in_light_and_dark(self):
        sels = ["#usecases h1", ".ucl-sub", ".ucl-ref", ".ucl-go", ".ucl-name small", ".ucl-head", ".ucl-ms", ".ucl-wi", ".ucl-wi small", ".ucl-st .pill",
                ".ucl-eye", ".ucl-row.off .ucl-eye", ".ucl-count", ".ucl-hd span", ".vtab", ".vtab em", "#ucl-group", ".ucl-hd .ucl-sort", "#ucl-q-count"]
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width, dark, edit=True)
                    got = p.js(contrast_script(sels))
                    seen = {s for s, _, _ in got}
                    for sel in ("#usecases h1", ".ucl-go", ".ucl-st .pill", ".ucl-eye", ".ucl-count"):
                        self.assertIn(sel, seen, sel)
                    for sel, r, size in got:
                        if size == "0px":
                            continue
                        self.assertGreaterEqual(r, 4.5, f"{sel} at {width}px {'dark' if dark else 'light'}")

    def test_view_shows_the_eye_alone_and_edit_makes_it_a_switch(self):
        """Row 819: the list is live, so the eye is a button in View as in Edit, and one click in View is one change with a toast and Undo."""
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertEqual(p.js("document.querySelectorAll('#usecases [data-eye]').length"), 4, "a button in View")
            self.assertEqual(p.js("[...document.querySelectorAll('#usecases [data-eye]')].map(e => e.title)"), [ON, ON, OFF, OFF])
            sel = f"[data-uc=\"{self.uc3}\"] [data-eye]"
            self.click(p, sel)
            p.saved()
            self.assertEqual(self.eye("1.10"), 1, "one click in View turned it on")
            self.assertEqual(p.toast(), "UC 1.10 is on the dashboard.")
            p.js("document.querySelector('[data-undo]').click()")
            p.until(f"document.querySelector('{sel}').title === '{OFF}'", "Undo put it back")
            self.assertEqual(self.eye("1.10"), 0)
            self.assertEqual(p.js("document.querySelectorAll('[data-mode]').length"), 0, "no View | Edit switch off the Dashboard: the page is always editable")
            p.until("document.querySelectorAll('#usecases [data-eye]').length === 4", "each eye is still a button")

    def test_the_eye_is_an_icon_alone_with_a_tooltip_and_never_meets_the_commitment_chip(self):
        """Issue 753: no heading and no words for 'show on report': the eye, a title on hover, the same words as the aria-label."""
        self.store.con.execute("UPDATE use_cases SET commitment = 'Committed'")
        self.store.con.commit()
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width, dark, edit=True)
                    self.assertNotIn("home dashboard", p.js("document.querySelector('#usecases .ucl-list').innerText").lower(), "no heading over the eye")
                    self.assertEqual(p.js("document.querySelector('#usecases .ucl-hd').textContent.toLowerCase().includes('dashboard')"), False)
                    got = p.js("""[...document.querySelectorAll('#usecases .ucl-row[data-uc]')].map(r => { const e = r.querySelector('.ucl-eye'), o = [r.querySelector('.ucl-st .pill'), r.querySelector('.cchip')];
                        const b = e.getBoundingClientRect(), rr = r.getBoundingClientRect();
                        return { words: e.textContent.trim(), shown: e.innerText.trim(), title: e.title, label: e.getAttribute('aria-label'), svg: e.querySelectorAll('svg').length,
                          chip: !!o[1], inside: b.left >= rr.left && b.right <= rr.right && b.right <= innerWidth, small: Math.min(b.width, b.height),
                          clash: o.filter(Boolean).some(x => { const c = x.getBoundingClientRect(); return b.left < c.right && c.left < b.right && b.top < c.bottom && c.top < b.bottom; }) }; })""")
                    self.assertEqual(len(got), 4)
                    for g in got:
                        self.assertEqual((g["words"], g["shown"]), ("", ""), "no words beside the eye")
                        self.assertEqual(g["svg"], 1)
                        self.assertIn(g["title"], (ON, OFF))
                        self.assertIn(g["title"], g["label"], "the aria-label keeps the same words")
                        self.assertTrue(g["chip"] and g["inside"] and not g["clash"], g)
                        self.assertGreaterEqual(g["small"], 24, "a target a finger can hit")
                    self.assertEqual(sorted(g["title"] for g in got), [OFF, OFF, ON, ON])

    def test_the_eye_toggles_with_a_click_enter_and_space_and_shows_a_focus_ring(self):
        with chrome() as cdp:
            p = self.show(cdp, edit=True)
            sel = f"[data-uc=\"{self.uc3}\"] .ucl-eye"
            self.assertEqual(p.js(f"document.querySelector('{sel}').title"), OFF)
            p.js(f"document.querySelector('{sel}').focus()")
            self.press(p, "Enter")
            p.until(f"document.querySelector('{sel}') && document.querySelector('{sel}').title === '{ON}'", "Enter turned it on")
            self.assertEqual(self.eye("1.10"), 1)
            p.js(f"document.querySelector('{sel}').focus()")
            self.press(p, " ")
            p.until(f"document.querySelector('{sel}') && document.querySelector('{sel}').title === '{OFF}'", "Space turned it off")
            self.assertEqual(self.eye("1.10"), 0)
            p.js(f"document.querySelector('{sel}').focus()")
            self.assertNotEqual(p.js(f"getComputedStyle(document.querySelector('{sel}')).outlineStyle"), "none", "a focus ring")
            self.assertEqual(p.js("document.querySelectorAll('#usecases [data-eye]').length"), 4)

    def test_view_has_the_eye_as_an_icon_with_a_tooltip_and_no_words_and_no_control(self):
        """Row 819 (name kept): in View the eye is an icon and a tooltip, no words beside it, and now a button."""
        with chrome() as cdp:
            p = self.show(cdp)
            got = p.js("[...document.querySelectorAll('#usecases [data-eye]')].map(e => [e.textContent.trim(), e.title, e.tagName, e.querySelectorAll('svg').length])")
            self.assertEqual(got, [["", ON, "BUTTON", 1], ["", ON, "BUTTON", 1], ["", OFF, "BUTTON", 1], ["", OFF, "BUTTON", 1]])

    def test_an_empty_project_says_so_in_plain_words(self):
        for table in ("actions",):
            self.store.con.execute(f"DELETE FROM {table}")
        self.store.con.execute("UPDATE use_cases SET archived = 1")
        self.store.con.commit()
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertEqual(p.js("document.querySelector('#usecases [data-empty]').textContent"), "No use cases yet.")
            self.assertEqual(p.js("document.querySelectorAll('#ucl-q, .ucl-row').length"), 0, "nothing to search or sort")


class Eye(Setup):
    def test_the_eye_changes_the_store_syncs_with_the_dashboard_and_undoes(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.store.con.execute("UPDATE use_cases SET client_visible = CASE ref WHEN '1.1' THEN 1 WHEN '1.2' THEN 1 ELSE 0 END")
                self.store.con.commit()
                p = self.show(cdp, width, edit=True)
                before = self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]
                self.click(p, f"[data-uc=\"{self.uc3}\"] [data-eye]")                    # put 1.10 on the dashboard
                p.saved()
                self.assertEqual(self.eye("1.10"), 1)
                self.assertEqual(p.toast(), "UC 1.10 is on the dashboard.")
                self.assertEqual(self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0], before + 1, "one change is one step")
                self.assertEqual(p.js(f"document.querySelector('[data-uc=\"{self.uc3}\"] .ucl-eye').title"), ON)
                self.assertEqual(self.count(p), "Showing 4 of 4 · 3 on the dashboard")
                self.assertEqual(p.js(f"document.activeElement === document.querySelector('[data-uc=\"{self.uc3}\"] .ucl-eye')"), True, "the eye keeps the focus")
                p.js("document.querySelector('[data-view=dashboard]').click()")
                p.until("!!document.querySelector('.uc')", "the dashboard")
                self.assertEqual(p.js("document.querySelector('.uctotal').textContent"), "3 use cases", "the dashboard follows")
                self.assertEqual(p.js("document.querySelector('[data-uc-more]').textContent"), "1 more on the Use cases page")
                p.js("history.back()")
                p.until("!!document.querySelector('#usecases .ucl-row')", "back to the list")
                p.js("document.querySelector('[data-undo]') && document.querySelector('[data-undo]').click()")
                p.until("!!document.querySelector('[data-uc=\"%s\"] .ucl-eye') && document.querySelector('[data-uc=\"%s\"] .ucl-eye').title === '%s'" % (self.uc3, self.uc3, OFF), "the undo put it back")
                self.assertEqual(self.eye("1.10"), 0)
                self.click(p, f"[data-uc=\"{self.uc1}\"] [data-eye]")                    # take 1.1 off
                p.until("document.querySelector('.toast-text') && document.querySelector('.toast-text').textContent === 'UC 1.1 is no longer on the dashboard.'", "said")
                self.assertEqual(self.eye("1.1"), 0)
                self.assertEqual(self.count(p), "Showing 4 of 4 · 1 on the dashboard")

    def test_the_eye_keeps_its_row_when_the_switch_is_narrowed_and_the_focus_moves_on(self):
        with chrome() as cdp:
            p = self.show(cdp, edit=True)
            self.click(p, "[data-tab=on]")
            p.until("document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 2", "only those on the dashboard")
            self.click(p, f"[data-uc=\"{self.uc1}\"] [data-eye]")
            p.until(f"!document.querySelector('[data-uc=\"{self.uc1}\"]')", "it left the narrowed list")
            p.until("document.activeElement && !!document.activeElement.closest('.ucl-row')", "the focus moved to a neighbouring row, not lost")
            self.assertEqual(self.refs(p), ["UC 1.2"])

    def test_a_refused_change_says_so_and_changes_nothing(self):
        self.failure = lambda req: (400, {"ok": False, "message": "Server text that a person must never read"})
        with chrome() as cdp:
            p = self.show(cdp, edit=True)
            self.click(p, f"[data-uc=\"{self.uc3}\"] [data-eye]")
            p.until("!!document.querySelector('.toast.problem')", "the toast")
            self.assertNotIn("Server text", p.toast())
            self.assertEqual(self.eye("1.10"), 0)
            self.assertEqual(p.js(f"document.querySelector('[data-uc=\"{self.uc3}\"] .ucl-eye').title"), OFF)


class Narrowing(Setup):
    def test_search_finds_a_reference_a_name_a_headline_the_text_and_a_milestone(self):
        with chrome() as cdp:
            p = self.show(cdp)
            for text, refs in (("1.2", ["UC 1.2"]), ("payment", ["UC 1.2"]), ("smallest suppliers", ["UC 1.10"]), ("zebra", ["UC 2.1"]),
                               ("pilot live", ["UC 1.1"]), ("SUPPLIER GO-LIVE", ["UC 1.2", "UC 2.1"]),
                               ("uc 2", ["UC 1.2", "UC 2.1"]), ('"uc 2"', ["UC 2.1"])):      # row 1085: each plain word is its own search, as on Work items; quotes make a phrase
                self.type_in(p, "#ucl-q", text)
                p.until(f"{json.dumps(refs)}.join() === [...document.querySelectorAll('#usecases .ucl-list .ucl-row .ucl-ref')].map(e => e.textContent).join()", f"search {text!r}")
            self.type_in(p, "#ucl-q", "nothing like this")
            p.until("!!document.querySelector('#usecases [data-empty]')", "the empty state")
            self.assertEqual(p.js("document.querySelector('#usecases [data-empty] p').textContent"), "No use cases match “nothing like this”.")
            self.assertEqual(self.count(p), "Showing 0 of 4 · 2 on the dashboard")
            self.click(p, "[data-clear-all]")
            p.until("document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 4", "Clear the filters brings them all back")
            self.assertEqual(p.js("document.querySelector('#ucl-q').value"), "")

    def test_the_status_field_takes_any_number_of_words_and_the_x_clears_it(self):
        """Row 1085: the Status choice is the line's status: field (the popup went with the switch): one word, a list, or -status: to leave one out."""
        with chrome() as cdp:
            p = self.show(cdp)
            self.type_in(p, "#ucl-q", "status:Flag ")
            p.until("document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 1", "one is Flag")
            self.assertEqual(p.js("document.querySelectorAll('#ucl-status, .ucl-pop, #usecases .seg, #ucl-sort').length"), 0, "no Status popup, switch or Sort menu beside the line")
            self.click(p, "#ucl-q-x")
            self.type_in(p, "#ucl-q", 'status:Flag,"High risk" ')
            p.until("document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 2", "Flag and High risk")
            self.assertEqual(self.refs(p), ["UC 1.2", "UC 1.10"])
            self.assertEqual(self.count(p), "Showing 2 of 4 · 2 on the dashboard")
            self.assertEqual(p.js("[...document.querySelectorAll('#usecases [data-chip]')].map(e => e.dataset.chip)"), ['status:Flag,"High risk"'])
            self.click(p, "#ucl-q-x")
            p.until("document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 4", "the x clears it")
            self.assertEqual(p.js("document.activeElement.id"), "ucl-q", "and the box keeps the focus")
            self.type_in(p, "#ucl-q", "-status:Flag ")
            p.until("document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 3", "all but Flag")
            self.assertEqual(self.refs(p), ["UC 1.1", "UC 1.10", "UC 2.1"])

    def test_done_has_its_word_in_a_blue_chip_its_own_filter_and_sorts_last(self):
        """#412 and row 1085: a Done use case says Done in a blue tinted dot chip (the approved colours), status:Done finds it, and sorting by status puts it last."""
        with self.store.step("dashboard", USER) as st:
            st.update("use_cases", self.uc3, {"status": "Done"})          # 1.10 was High risk: the worst, now finished
        with chrome() as cdp:
            p = self.show(cdp)
            pill = "document.querySelector('#usecases .ucl-row[data-uc=\"%s\"] [data-status]')" % self.uc3
            self.assertEqual(p.js(pill + ".textContent"), "Done")
            self.assertEqual(p.js(pill + ".className"), "pill b")
            self.assertEqual(p.js("getComputedStyle(" + pill + ", '::before').content"), '""', "the dot")
            self.click(p, ".ucl-hd [data-sort=status]")
            p.until("document.querySelector('.ucl-hd [data-sort=status]').getAttribute('aria-pressed') === 'true'", "sorted")
            self.assertEqual(self.refs(p), ["UC 1.2", "UC 1.1", "UC 2.1", "UC 1.10"], "Flag, then On track, then Done")
            self.type_in(p, "#ucl-q", "status:")
            self.press(p, "ArrowDown")
            p.until("!!document.querySelector('#ucl-q-list')", "the status values")
            self.assertEqual(p.js("[...document.querySelectorAll('#ucl-q-list .fopt')].find(o => o.dataset.ins === 'status:Done').querySelector('.fdv').dataset.tone"), "b", "Done is blue in the line's offer too")
            p.js("[...document.querySelectorAll('#ucl-q-list .fopt')].find(o => o.dataset.ins === 'status:Done').click()")
            p.until("document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 1", "one is Done")
            self.assertEqual(self.refs(p), ["UC 1.10"])

    def test_the_tabs_counts_follow_the_line_and_narrow_the_list(self):
        """Row 1085: the four fixed tabs (All use cases, On the dashboard, Committed, At risk) replace the switch; their counts follow the filter line."""
        with self.store.step("dashboard", USER) as st:
            st.update("use_cases", self.uc4, {"commitment": "Committed"})
        with chrome() as cdp:
            p = self.show(cdp)
            nums = "[...document.querySelectorAll('#usecases .vtab')].map(b => b.querySelector('span').textContent + ' ' + b.querySelector('em').textContent)"
            self.assertEqual(p.js(nums), ["All use cases 4", f"{ON} 2", "Committed 1", "At risk 2"])
            self.assertEqual(p.js("[...document.querySelectorAll('#usecases .vtab')].map(b => b.getAttribute('aria-pressed'))"), ["true", "false", "false", "false"])
            self.click(p, "[data-tab=risk]")
            p.until("document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 2", "at risk: Flag or High risk")
            self.assertEqual(self.refs(p), ["UC 1.2", "UC 1.10"])
            self.assertEqual(p.js("document.querySelector('[data-tab=risk]').getAttribute('aria-pressed')"), "true")
            self.assertEqual(self.count(p), "Showing 2 of 4 · 2 on the dashboard")
            self.click(p, "[data-tab=committed]")
            p.until("document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 1", "committed")
            self.assertEqual(self.refs(p), ["UC 2.1"])
            self.click(p, "[data-tab=on]")
            p.until("document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 2", "on the dashboard")
            self.type_in(p, "#ucl-q", 'status:"On track" ')
            p.until("document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 1", "on the dashboard and On track")
            self.assertEqual(p.js(nums), ["All use cases 2", f"{ON} 1", "Committed 1", "At risk 0"], "the counts follow the line, never the tab")
            self.assertEqual(self.refs(p), ["UC 1.1"])
            self.type_in(p, "#ucl-q", "portal")
            p.until("!!document.querySelector('#usecases [data-empty]')", "nothing is On track, on the dashboard and a portal")
            self.assertEqual(p.js("document.querySelector('#usecases [data-empty] p').textContent"), "No use cases match “portal” with these filters.")
            self.click(p, "[data-clear-all]")
            p.until("document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 4", "Clear the filters: the line and the tab")
            self.assertEqual(p.js("document.querySelector('[data-tab=all]').getAttribute('aria-pressed')"), "true")

    def test_not_on_the_dashboard_is_the_line_s_on_no(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.type_in(p, "#ucl-q", "on:no ")
            p.until("document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 2", "not on the dashboard")
            self.assertEqual(self.refs(p), ["UC 1.10", "UC 2.1"])
            self.assertEqual(self.count(p), "Showing 2 of 4 · 2 on the dashboard")

    def test_add_use_case_sits_on_the_tabs_row_and_import_and_export_do_not(self):
        with chrome() as cdp:
            p = self.show(cdp)
            got = p.js("[...document.querySelectorAll('#usecases .fvrow .ucl-tools button')].map(b => [b.id, b.getAttribute('aria-label')])")
            self.assertEqual(got, [["ucl-group", "Group by: Nothing"], ["ucAddPage", "Add use case"]], "Group by, then the + with the Work items word, at the right end of the tabs row")
            self.assertEqual(p.js("document.querySelectorAll('#usecases .head button, #usecases #impBtn, #usecases #expBtn, #usecases .bib').length"), 0, "nothing is left in the head; no Import or Export icon on this page (the ruling)")
            self.assertGreater(p.js("document.querySelector('#ucAddPage').getBoundingClientRect().left"), p.js("document.querySelector('[data-tab=risk]').getBoundingClientRect().right"), "to the right of the last tab")
            self.assertLess(p.js("document.querySelector('#ucAddPage').getBoundingClientRect().bottom"), p.js("document.querySelector('#usecases [data-fline]').getBoundingClientRect().top") + 1, "above the line")
            self.click(p, "#ucAddPage")
            p.until("!!document.querySelector('#ucF')", "Add use case opens the box")

    def test_sort_by_reference_status_and_open_work_items_on_the_column_names(self):
        """Row 1085: the sort is on the column names (Ref, Status, Work items), the current one pressed and marked; the Sort menu went."""
        with chrome() as cdp:
            p = self.show(cdp)
            heads = "[...document.querySelectorAll('#usecases .ucl-hd .ucl-sort')].map(b => [b.dataset.sort, b.getAttribute('aria-label'), b.getAttribute('aria-pressed'), b.querySelectorAll('svg').length])"
            self.assertEqual(p.js(heads), [["ref", "Sort by Reference", "true", 1], ["status", "Sort by Status", "false", 0], ["open", "Sort by Open work items", "false", 0]], "Reference to start, marked")
            self.assertEqual(p.js("[...document.querySelectorAll('#usecases .ucl-hd > *')].map(e => e.textContent.trim())"), ["Ref", "Use case", "Where it stands", "Status", "Work items", "Milestones", ""], "the column names read as before")
            for key, word, refs in (("status", "Status", ["UC 1.10", "UC 1.2", "UC 1.1", "UC 2.1"]), ("open", "Open work items", ["UC 1.2", "UC 1.1", "UC 2.1", "UC 1.10"]),
                                    ("ref", "Reference", ["UC 1.1", "UC 1.2", "UC 1.10", "UC 2.1"])):
                self.click(p, f".ucl-hd [data-sort={key}]")
                p.until(f"{json.dumps(refs)}.join() === [...document.querySelectorAll('#usecases .ucl-list .ucl-row .ucl-ref')].map(e => e.textContent).join()", f"sorted by {word}")
                self.assertEqual(p.js(f"document.querySelector('.ucl-hd [data-sort={key}]').getAttribute('aria-pressed')"), "true")
                self.assertEqual(p.js(f"document.querySelector('.ucl-hd [data-sort={key}]').title"), f"Sort by {word}")
                self.assertEqual(p.js("document.querySelectorAll('#usecases .ucl-hd [aria-pressed=true]').length"), 1, "one column marked")
            self.assertEqual(p.js("document.querySelectorAll('#ucl-sort').length"), 0)

    def test_what_was_chosen_is_remembered_for_each_project_and_adds_no_back_entry(self):
        with chrome() as cdp:
            p = self.show(cdp)
            before = p.js("history.length")
            self.type_in(p, "#ucl-q", "payment")
            p.until("document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 1", "the line applied (about 400 ms after the last key, as on Work items)")
            self.click(p, "[data-tab=on]")
            self.click(p, ".ucl-hd [data-sort=status]")
            p.until("document.querySelector('.ucl-hd [data-sort=status]').getAttribute('aria-pressed') === 'true'", "sorted")
            self.assertEqual(p.js("history.length"), before, "a filter, a search and a sort add no entry")
            self.assertEqual(p.js("location.hash"), "#usecases&p=ABC", "and are not in the address")
            self.reload(p)
            self.assertEqual(p.js("document.querySelector('#ucl-q').value"), "payment")
            self.assertEqual(p.js("document.querySelector('[data-tab=on]').getAttribute('aria-pressed')"), "true")
            self.assertEqual(p.js("document.querySelector('.ucl-hd [data-sort=status]').getAttribute('aria-pressed')"), "true")
            self.assertEqual(self.refs(p), ["UC 1.2"])
            saved = json.loads(p.js("localStorage.getItem('clark.ucPage')"))
            self.assertEqual(sorted(saved), ["ABC"], "kept under the project's code")
            self.assertEqual(saved["ABC"], {"line": "payment", "tab": "on", "group": "nothing", "sort": "status"}, "row 1085: the search and the Status choice are one line, the switch a tab")
            p.js("localStorage.setItem('clark.ucPage', JSON.stringify({ABC: {st: ['Flag'], on: 'nonsense', sort: 'nonsense', q: 5}, OTHER: {q: 'x'}}))")
            self.reload(p)
            self.assertEqual(p.js("document.querySelector('#ucl-q').value"), "", "a saved value that makes no sense falls back")
            self.assertEqual(p.js("[...document.querySelectorAll('#usecases [data-chip]')].map(e => e.dataset.chip)"), ["status:Flag"])
            self.assertEqual(p.js("document.querySelector('.ucl-hd [data-sort=ref]').getAttribute('aria-pressed')"), "true")
            self.assertEqual(p.js("document.querySelector('[data-tab=all]').getAttribute('aria-pressed')"), "true")


class Line(Setup):
    """Row 1085: the Use cases page has a filter line of its own (the Work items box, drawn by the same code, reading only this page's
    fields: status, commitment, milestone and plain words), kept apart from the Work items line. The Status choice and the switch stay beside it."""
    FIELDS_SAID = "There is no “owner” filter. You can filter by status:, commitment:, milestone: and on:, or type plain words to search titles."

    def chips(self, p):
        return p.js("[...document.querySelectorAll('#usecases [data-chip]')].map(e => e.dataset.chip)")

    def line(self, p):
        return p.js("document.querySelector('#usecases [data-fline]').dataset.line")

    def clear(self, p):
        self.click(p, "#ucl-q-x")
        p.until("document.querySelector('#usecases [data-fline]').dataset.line === '' && document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 4", "the x cleared the line")

    def test_a_misspelt_field_word_says_which_of_this_pages_fields_it_is_nearest_to(self):
        """Mutation sweep of row 1085: the unknown-field sentence names the near miss among this page's own fields (status for statsu), as the Work items one does."""
        with chrome() as cdp:
            p = self.show(cdp)
            self.type_in(p, "#ucl-q", "statsu:Flag ")
            p.until("document.querySelector('#ucl-q-msg').textContent !== ''", "the message")
            self.assertEqual(p.js("document.querySelector('#ucl-q-msg').textContent"),
                             "There is no “statsu” filter. Did you mean status? You can filter by status:, commitment:, milestone: and on:, or type plain words to search titles.")

    def test_the_suggestions_carry_no_work_items_notes_narrow_by_the_typed_part_and_leave_out_a_value_already_taken(self):
        """Mutation sweep of row 1085: has: and no: keep no Work items note (it names owner and date), a typed part narrows the values, a value already in the chip is not offered again, and a chip has no gloss here."""
        with chrome() as cdp:
            p = self.show(cdp)
            values = "[...document.querySelectorAll('#ucl-q-list .fopt.value .fl1')].map(e => e.textContent)"
            p.js("document.querySelector('#ucl-q').focus()")
            self.press(p, "ArrowDown")
            p.until("!!document.querySelector('#ucl-q-list')", "the list opened on an empty box")
            self.assertEqual(p.js("document.querySelectorAll('#ucl-q-list .fopt .fl2').length"), 0, "no field row (has: and no: too) carries a Work items note")
            self.press(p, "Escape")
            self.type_in(p, "#ucl-q", "status:fl")
            self.press(p, "ArrowDown")
            p.until("!!document.querySelector('#ucl-q-list')", "the values")
            self.assertEqual(p.js(values), ["Flag"], "the typed part narrows the values")
            self.press(p, "Escape")
            self.type_in(p, "#ucl-q", "status:Flag,")
            self.press(p, "ArrowDown")
            p.until("!!document.querySelector('#ucl-q-list')", "the values after the comma")
            self.assertEqual(p.js(values), ["On track", "High risk", "Done"], "Flag is taken: not offered again")
            self.press(p, "Escape")
            self.type_in(p, "#ucl-q", "status:flag")
            p.until("!!document.querySelector('#usecases [data-tok=val]')", "the value as it is typed")
            self.assertTrue(p.js("document.querySelector('#usecases [data-tok=val]').classList.contains('a')"), "a status word typed in lower case has its tint")
            self.press(p, "Escape")
            self.type_in(p, "#ucl-q", "status:Flag ")
            p.until("document.querySelectorAll('#usecases [data-chip]').length === 1", "the chip")
            self.assertFalse(p.js("document.querySelector('#usecases [data-chip]').hasAttribute('data-gloss')"), "this page's chips have no gloss")

    def test_the_line_stands_where_the_search_box_was_with_the_work_items_words_and_no_examples(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertEqual(p.js("document.querySelectorAll('#usecases [data-fline]').length"), 1, "one line box on the page")
            self.assertEqual(p.js("document.querySelector('#ucl-q').placeholder"), "Filter by keyword or by field", "the Work items placeholder, no new words")
            self.assertEqual(p.js("document.querySelector('#ucl-q').getAttribute('aria-label')"), "Search use cases", "the old box's name, said by a screen reader")
            self.assertEqual(p.js("document.querySelectorAll('#usecases .fhints, #usecases .ucl-search, #fline-input').length"), 0, "no Try row (approved), no old search box, not the Work items line")
            self.assertEqual(p.js("document.querySelector('#ucl-q-count').textContent"), "4 of 4", "the count sits in the box")
            self.assertEqual(self.line(p), "")
            self.assertEqual(p.js("[...document.querySelectorAll('#usecases .vtab span:first-child')].map(e => e.textContent)"), ["All use cases", ON, "Committed", "At risk"], "the four tabs over the line")
            self.assertEqual(p.js("document.querySelectorAll('#usecases .seg, #usecases .vtabmenu, #viewNew').length"), 0, "no switch; fixed tabs have no menu and no New view")

    def test_a_status_field_narrows_the_list_and_the_status_choice_and_the_line_follow_each_other(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.type_in(p, "#ucl-q", "status:Flag ")
            p.until("document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 1", "one is Flag")
            self.assertEqual(self.refs(p), ["UC 1.2"])
            self.assertEqual(self.chips(p), ["status:Flag"], "the complete filter became a chip")
            self.assertEqual(p.js("document.querySelector('#ucl-q').value"), "", "and left the box")
            self.assertEqual(p.js("document.querySelector('#ucl-q-count').textContent"), "1 of 4")
            self.assertEqual(self.count(p), "Showing 1 of 4 · 2 on the dashboard")
            self.assertEqual(self.line(p), "status:Flag")
            self.assertEqual(json.loads(p.js("localStorage.getItem('clark.ucPage')"))["ABC"]["line"], "status:Flag", "remembered as the line")
            self.click(p, "[data-fx]")
            p.until("document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 4", "the chip's own x takes it away")
            self.assertEqual((self.chips(p), self.line(p)), ([], ""))
            self.assertEqual(json.loads(p.js("localStorage.getItem('clark.ucPage')"))["ABC"]["line"], "")

    def test_commitment_milestone_no_and_plain_words_and_a_field_this_page_does_not_have(self):
        with self.store.step("dashboard", USER) as st:
            st.update("use_cases", self.uc2, {"commitment": "Committed"})
        with chrome() as cdp:
            p = self.show(cdp)
            for text, refs in (("commitment:Committed ", ["UC 1.2"]), ('milestone:"Supplier go-live" ', ["UC 1.2", "UC 2.1"]), ("no:milestone ", ["UC 1.10"]),
                               ("zebra", ["UC 2.1"]), ("-status:Flag payment", [])):
                self.type_in(p, "#ucl-q", text)
                p.until(f"{json.dumps(refs)}.join() === [...document.querySelectorAll('#usecases .ucl-list .ucl-row .ucl-ref')].map(e => e.textContent).join()", f"line {text!r}")
                if text == "zebra":
                    self.assertEqual((self.chips(p), p.js("document.querySelector('#ucl-q').value")), ([], "zebra"), "a plain word stays in the box")
                if not refs:
                    self.assertEqual(p.js("document.querySelector('#usecases [data-empty] p').textContent"), "No use cases match “payment” with these filters.")
                self.clear(p)
            self.type_in(p, "#ucl-q", "owner:pat ")
            p.until("document.querySelector('#ucl-q-msg').textContent !== ''", "the message")
            self.assertEqual(p.js("document.querySelector('#ucl-q-msg').textContent"), self.FIELDS_SAID, "the message names this page's fields, not the Work items ones")
            self.assertEqual(p.js("document.querySelectorAll('#usecases [data-tok=err]').length"), 1, "the word is underlined")
            self.assertEqual(self.refs(p), ["UC 1.1", "UC 1.2", "UC 1.10", "UC 2.1"], "a word that cannot be used narrows nothing")
            self.assertEqual(self.chips(p), [])

    def test_the_suggestions_list_this_page_s_fields_and_their_values(self):
        with chrome() as cdp:
            p = self.show(cdp)
            labels = "[...document.querySelectorAll('#ucl-q-list .fopt .fl1')].map(e => e.textContent)"
            p.js("document.querySelector('#ucl-q').focus()")
            self.press(p, "ArrowDown")
            p.until("!!document.querySelector('#ucl-q-list')", "the list opened on an empty box")
            self.assertEqual(p.js(labels), ["status:", "commitment:", "milestone:", "on:", "has:", "no:"], "this page's fields: no is:, no type:, no owner:")
            self.assertEqual(p.js("document.querySelector('#ucl-q').getAttribute('aria-activedescendant')"), "ucl-qo-0", "its own option ids")
            self.press(p, "Escape")
            self.type_in(p, "#ucl-q", "status:")
            self.press(p, "ArrowDown")
            p.until("document.querySelectorAll('#ucl-q-list .fopt').length === 7", "the status values")
            self.assertEqual(p.js(labels), ["No Status", "Has Status", "Exclude Status", "On track", "Flag", "High risk", "Done"])
            self.assertEqual(p.js("[...document.querySelectorAll('#ucl-q-list .fopt .c')].map(e => e.textContent)"), ["0", "4", "2", "1", "1", "0"], "each value with how many it would show")
            p.js("[...document.querySelectorAll('#ucl-q-list .fopt')].find(o => o.dataset.ins === 'status:\"High risk\"').click()")
            p.until("document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 1", "the choice applied")
            self.assertEqual(self.chips(p), ['status:"High risk"'])
            self.assertEqual(p.js("document.querySelector('#usecases [data-tok=val], #usecases [data-chip]') !== null"), True)

    def test_an_older_search_that_starts_with_a_minus_and_a_field_word_stays_a_plain_word(self):
        """Mutation sweep of row 1085: an old search "-status:Flag" would read as a left-out status if it were not quoted; it was plain text, so it stays plain text."""
        with chrome() as cdp:
            p = self.show(cdp)
            p.js("localStorage.setItem('clark.ucPage', JSON.stringify({ABC: {q: '-status:Flag zebra'}}))")
            reload_to_new_page(p.js, "!!document.querySelector('#usecases [data-fline]') && !!document.querySelector('#usecases [data-empty]')")
            self.assertEqual(self.line(p), '"-status:Flag" zebra', "a leading minus before a field word is quoted too")
            self.assertEqual(self.refs(p), [], "no row has those words, and the line did not turn into a left-out status")

    def test_an_older_remembered_state_is_read_as_one_line_and_written_back_in_the_new_shape(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.js("localStorage.setItem('clark.ucPage', JSON.stringify({ABC: {st: ['Done', 'Flag'], on: 'on', sort: 'status', q: 'payment runs'}}))")
            self.reload(p)
            self.assertEqual(self.line(p), "status:Flag,Done payment runs", "the Status choice and the search are one line, the status first in its own order")
            self.assertEqual(self.chips(p), ["status:Flag,Done"])
            self.assertEqual(p.js("document.querySelector('#ucl-q').value"), "payment runs")
            self.assertEqual(p.js("document.querySelector('[data-tab=on]').getAttribute('aria-pressed')"), "true", "the switch's On the dashboard is the tab of that name")
            self.assertEqual(p.js("document.querySelector('.ucl-hd [data-sort=status]').getAttribute('aria-pressed')"), "true", "the sort is kept as it was")
            self.assertEqual(self.refs(p), ["UC 1.2"])
            self.click(p, "[data-tab=all]")
            p.until("document.querySelector('[data-tab=all]').getAttribute('aria-pressed') === 'true'", "all")
            self.assertEqual(json.loads(p.js("localStorage.getItem('clark.ucPage')"))["ABC"], {"line": "status:Flag,Done payment runs", "tab": "all", "group": "nothing", "sort": "status"}, "written back in the new shape")
            p.js("localStorage.setItem('clark.ucPage', JSON.stringify({ABC: {q: 'a:b  zebra', on: 'off'}}))")
            reload_to_new_page(p.js, "!!document.querySelector('#usecases [data-fline]') && !!document.querySelector('#usecases [data-empty]')")   # no row matches: the empty state
            self.assertEqual(self.line(p), 'on:no "a:b" zebra', "the switch's Not on the dashboard (no tab) is on:no; a search word that would read as a field is quoted, so it stays a plain word")
            self.assertEqual(self.refs(p), [], "the old search was plain text: it does not become a filter")
            self.assertEqual(p.js("document.querySelector('#usecases [data-empty] p').textContent"), "No use cases match “a:b zebra” with these filters.")
            p.js("localStorage.setItem('clark.ucPage', JSON.stringify({ABC: {line: 'status:Flag', tab: 'all', sort: 'ref'}}))")
            self.reload(p)
            self.assertEqual((self.line(p), self.refs(p)), ("status:Flag", ["UC 1.2"]), "the new shape reads as it is")
            p.js("localStorage.setItem('clark.ucPage', JSON.stringify({ABC: {line: 7, st: ['Flag']}}))")
            self.reload(p)
            self.assertEqual(self.line(p), "", "a line that is not text falls back to the start, and the old keys beside it are not read")

    def test_the_use_cases_line_leaves_the_work_items_line_alone(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertIsNone(p.js("sessionStorage.getItem('clark.fline')"))
            self.type_in(p, "#ucl-q", "status:Flag ")
            p.until("document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 1", "narrowed")
            self.assertIsNone(p.js("sessionStorage.getItem('clark.fline')"), "the Work items line's memory is not written")
            self.assertEqual(json.loads(p.js("localStorage.getItem('clark.ucPage')"))["ABC"]["line"], "status:Flag", "the Use cases line has its own memory")
            p.js("document.querySelector('[data-view=work]').click()")
            p.until("!!document.querySelector('#fline-input') && !document.querySelector('#usecases')", "the Work items page and its own line")
            self.assertNotIn("status:Flag", p.js("[...document.querySelectorAll('[data-chip]')].map(e => e.dataset.chip)"), "the Work items line did not take the use case filter")
            self.assertEqual(p.js("document.querySelectorAll('.fhints').length"), 1, "the Work items line keeps its Try row")
            p.js("document.querySelector('[data-view=usecases]').click()")
            p.until("!!document.querySelector('#usecases [data-fline]')", "back")
            self.assertEqual((self.line(p), self.refs(p)), ("status:Flag", ["UC 1.2"]), "the Use cases line is as it was left")


class GroupBy(Setup):
    """Row 1085: Group by (Status, Commitment, On the dashboard, Nothing; Nothing to start) on the tabs row: each group a bordered card with a heading
    bar (the name, the count, open and shut) and its own column names, as the Work items groups are drawn. Remembered with the rest."""

    def groups(self, p):
        return p.js("[...document.querySelectorAll('#usecases .ucl-group')].map(g => [g.querySelector('.gl').textContent, g.querySelector('.gc').textContent, [...g.querySelectorAll('.ucl-row[data-uc] .ucl-ref')].map(e => e.textContent)])")

    def pick(self, p, word):
        self.click(p, "#ucl-group")
        p.until("!!document.querySelector('.ddmenu [role=menuitemradio]')", "the Group by menu")
        p.js(f"[...document.querySelectorAll('.ddmenu [role=menuitemradio]')].find(b => b.textContent.replace('✓', '').trim() === {json.dumps(word)}).click()")
        p.until(f"document.querySelector('#ucl-group').getAttribute('aria-label') === {json.dumps('Group by: ' + word)}", f"grouped by {word}")

    def test_group_by_status_commitment_and_the_dashboard_draws_bordered_groups_with_a_heading_and_a_count(self):
        with self.store.step("dashboard", USER) as st:
            st.update("use_cases", self.uc2, {"commitment": "Committed"})
            st.update("use_cases", self.uc4, {"commitment": "Planned 2026"})
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertEqual(p.js("document.querySelectorAll('#usecases .ucl-group').length"), 0, "Nothing to start: one plain list")
            self.assertEqual(p.js("document.querySelector('#ucl-group').textContent.trim()"), "Group by")
            self.assertEqual(p.js("document.querySelector('#ucl-group').getAttribute('aria-label')"), "Group by: Nothing")
            self.assertTrue(p.js("document.querySelector('#ucl-group').getBoundingClientRect().right <= document.querySelector('#ucAddPage').getBoundingClientRect().left"), "on the tabs row, before the +")
            self.click(p, "#ucl-group")
            p.until("!!document.querySelector('.ddmenu [role=menuitemradio]')", "the menu")
            self.assertEqual(p.js("[...document.querySelectorAll('.ddmenu [role=menuitemradio]')].map(b => [b.textContent.replace('✓', '').trim(), b.getAttribute('aria-checked')])"),
                             [["Status", "false"], ["Commitment", "false"], [ON, "false"], ["Nothing", "true"]])
            self.press(p, "Escape")
            self.pick(p, "Status")
            self.assertEqual(self.groups(p), [["On track", "2 use cases", ["UC 1.1", "UC 2.1"]], ["Flag", "1 use case", ["UC 1.2"]], ["High risk", "1 use case", ["UC 1.10"]]], "the status words in their order; a group with no row is not drawn")
            self.assertEqual(p.js("document.querySelectorAll('#usecases .ucl-group .ucl-hd').length"), 3, "each group has its own column names")
            self.assertEqual(p.js("getComputedStyle(document.querySelector('#usecases .ucl-group')).borderTopStyle"), "solid", "a bordered card")
            self.assertEqual(p.js("[...document.querySelectorAll('#usecases .grp-b')].map(b => b.getAttribute('aria-expanded'))"), ["true", "true", "true"])
            self.assertEqual(self.count(p), "Showing 4 of 4 · 2 on the dashboard")
            self.pick(p, "Commitment")
            self.assertEqual(self.groups(p), [["Planned 2026", "1 use case", ["UC 2.1"]], ["Committed", "1 use case", ["UC 1.2"]], ["None", "2 use cases", ["UC 1.1", "UC 1.10"]]], "the server's words in its order, then None")
            self.pick(p, ON)
            self.assertEqual(self.groups(p), [[ON, "2 use cases", ["UC 1.1", "UC 1.2"]], [OFF, "2 use cases", ["UC 1.10", "UC 2.1"]]])
            self.type_in(p, "#ucl-q", "status:Flag ")
            p.until("document.querySelectorAll('#usecases .ucl-row[data-uc]').length === 1", "the line narrows the groups")
            self.assertEqual(self.groups(p), [[ON, "1 use case", ["UC 1.2"]]], "an emptied group is not drawn")
            self.assertEqual(json.loads(p.js("localStorage.getItem('clark.ucPage')"))["ABC"]["group"], "on", "remembered")
            self.reload(p)
            self.assertEqual(self.groups(p), [[ON, "1 use case", ["UC 1.2"]]])
            self.pick(p, "Nothing")
            self.assertEqual(p.js("document.querySelectorAll('#usecases .ucl-group, #usecases .grp-b').length"), 0)
            self.assertEqual(self.refs(p), ["UC 1.2"])

    def test_the_status_groups_keep_the_status_words_order_whatever_order_the_rows_come_in(self):
        """Mutation sweep of row 1085: the groups follow the four status words (On track, Flag, High risk, Done), not the order the rows first show them in."""
        with self.store.step("dashboard", USER) as st:
            st.update("use_cases", self.uc1, {"status": "Done"})            # 1.1 first by reference, but Done is the last group
            st.update("use_cases", self.uc4, {"status": "High risk"})       # 2.1 after it, but High risk comes before Done
        with chrome() as cdp:
            p = self.show(cdp)
            self.pick(p, "Status")
            self.assertEqual([g[0] for g in self.groups(p)], ["Flag", "High risk", "Done"], "the status words' order, not the rows'")
            self.assertEqual(self.groups(p)[1][2], ["UC 1.10", "UC 2.1"])

    def test_a_group_shuts_and_opens_for_the_visit_and_the_keys_cross_the_groups(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.pick(p, "Status")
            ids = p.js("[...document.querySelectorAll('#usecases .ucl-row[data-uc]')].map(r => r.dataset.uc)")
            self.assertEqual(len(ids), 4)
            self.assertEqual(p.js("[...document.querySelectorAll('#usecases .ucl-list *')].filter(e => e.tabIndex >= 0).map(e => e.closest('.ucl-row').dataset.uc)"), [ids[0]], "one tab stop across the groups")
            p.js("document.querySelector('#usecases .ucl-go').focus()")
            self.press(p, "ArrowDown")
            self.press(p, "ArrowDown")
            self.assertEqual(p.js("document.activeElement.closest('.ucl-row').dataset.uc"), ids[2], "Down crosses into the next group")
            self.press(p, "End")
            self.assertEqual(p.js("document.activeElement.closest('.ucl-row').dataset.uc"), ids[3])
            self.press(p, "Home")
            self.assertEqual(p.js("document.activeElement.closest('.ucl-row').dataset.uc"), ids[0])
            self.click(p, "#usecases .ucl-group .grp-b")
            p.until("document.querySelector('#usecases .grp-b').getAttribute('aria-expanded') === 'false'", "shut")
            self.assertEqual(p.js("document.querySelectorAll('#usecases .ucl-row[data-uc]').length"), 2, "its rows are away; the heading stays")
            self.assertEqual(p.js("document.querySelector('#usecases .ucl-group .gc').textContent"), "2 use cases", "the count still says how many it holds")
            self.assertEqual(p.js("[...document.querySelectorAll('#usecases .ucl-list *')].filter(e => e.tabIndex >= 0).map(e => e.closest('.ucl-row').dataset.uc)"), [ids[2]], "the tab stop moves to a row that shows")
            self.click(p, "#usecases .ucl-group .grp-b")
            p.until("document.querySelectorAll('#usecases .ucl-row[data-uc]').length === 4", "open again")
            self.assertEqual(json.loads(p.js("localStorage.getItem('clark.ucPage')"))["ABC"].get("shut"), None, "open or shut is for the visit, not remembered")


class Keys(Setup):
    def stops(self, p):
        return p.js("[...document.querySelectorAll('#usecases .ucl-list *')].filter(e => e.tabIndex >= 0 && !e.disabled).map(e => e.closest('.ucl-row').dataset.uc + ':' + e.className)")

    def focused(self, p):
        return p.js("(() => { const e = document.activeElement; const r = e.closest && e.closest('.ucl-row'); return r ? r.dataset.uc + ':' + e.className : e.tagName; })()")

    def test_the_list_is_one_tab_stop_and_the_arrows_move_inside_it(self):
        for edit in (True, False):
            with self.subTest(edit=edit), chrome() as cdp:
                p = self.show(cdp, edit=edit)
                ids = p.js("[...document.querySelectorAll('#usecases .ucl-list .ucl-row')].map(r => r.dataset.uc)")
                self.assertEqual(len(ids), 4)
                self.assertEqual(self.stops(p), [f"{ids[0]}:ucl-go"], "one tab stop: the first row's name")
                p.js("document.querySelector('#usecases .ucl-go').focus()")
                self.press(p, "ArrowDown")
                self.assertEqual(self.focused(p), f"{ids[1]}:ucl-go")
                self.assertEqual(self.stops(p), [f"{ids[1]}:ucl-go"], "the tab stop follows the focus")
                self.press(p, "End")
                self.assertEqual(self.focused(p), f"{ids[-1]}:ucl-go")
                self.press(p, "ArrowDown")
                self.assertEqual(self.focused(p), f"{ids[-1]}:ucl-go", "Down on the last row stays")
                self.press(p, "Home")
                self.assertEqual(self.focused(p), f"{ids[0]}:ucl-go")
                self.press(p, "ArrowUp")
                self.assertEqual(self.focused(p), f"{ids[0]}:ucl-go", "Up on the first row stays")
                self.press(p, "ArrowRight")
                self.assertEqual(self.focused(p), f"{ids[0]}:ucl-eye", "Right goes to the eye, in View as in Edit (row 819)")
                self.press(p, "ArrowDown")
                self.assertEqual(self.focused(p), f"{ids[1]}:ucl-eye", "Down from an eye goes to the next eye")
                self.press(p, "ArrowLeft")
                self.assertEqual(self.focused(p), f"{ids[1]}:ucl-go", "Left comes back to the name")
                self.assertEqual(self.stops(p), [f"{ids[1]}:ucl-go"])
                self.press(p, "Enter")
                p.until("!!document.querySelector('[data-ucd]')", "Enter opens the use case")

    def test_enter_and_space_work_the_eye_and_the_keys_leave_the_search_box_alone(self):
        with chrome() as cdp:
            p = self.show(cdp, edit=True)
            p.js("document.querySelector('#usecases .ucl-go').focus()")
            self.press(p, "ArrowRight")
            self.press(p, " ")
            p.until("!!document.querySelector('[data-undo]')", "Space worked the eye")
            self.assertEqual(self.eye("1.1"), 0)
            self.press(p, "Enter")
            p.until("document.querySelector('.toast-text').textContent === 'UC 1.1 is on the dashboard.'", "Enter worked it again")
            self.assertEqual(self.eye("1.1"), 1)
            p.until("document.getAnimations().length === 0", "the eye's blink is over")
            time.sleep(0.3)                  # the eye's change hands the focus back to it a moment (60 ms) after the server answers: let that pass first
            p.js("document.querySelector('#ucl-q').focus()")
            p.until("document.activeElement.id === 'ucl-q'", "the box has the focus")
            self.press(p, "ArrowDown")
            self.press(p, "Home")
            self.assertEqual(p.js("document.activeElement.id"), "ucl-q", "the arrows are taken only on a row")

    def test_the_names_and_controls_have_names_a_screen_reader_can_say(self):
        with chrome() as cdp:
            p = self.show(cdp, edit=True)
            self.assertEqual(p.js("[...document.querySelectorAll('#usecases button, #usecases input')].filter(e => !(e.getAttribute('aria-label') || e.textContent.trim() || e.labels && e.labels.length)).length"), 0)
            self.assertEqual(p.js("document.querySelector('#usecases .ucl-list').getAttribute('aria-label')"), "Use cases")
            # row 1085: the column names carry the sort, so the header row is not hidden from a screen reader any more; each sort button says what it does
            self.assertIsNone(p.js("document.querySelector('#usecases .ucl-hd').getAttribute('aria-hidden')"))
            self.assertEqual(p.js("[...document.querySelectorAll('#usecases .ucl-hd button')].map(b => b.getAttribute('aria-label'))"), ["Sort by Reference", "Sort by Status", "Sort by Open work items"])
            self.assertEqual(p.js("document.querySelectorAll('#usecases .ucl-hd [tabindex=\"-1\"]').length"), 0, "a keyboard reaches each one")
            self.assertEqual(p.js("document.querySelector('[data-eye]').getAttribute('aria-label')"),
                             f"UC 1.1 Invoice matching: {ON}. Take it off the dashboard")
            self.assertEqual(p.js("document.querySelector('#ucl-count').getAttribute('role')"), "status")


if __name__ == "__main__":
    unittest.main()
