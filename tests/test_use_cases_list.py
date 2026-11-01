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
import unittest
from pathlib import Path

from _demo import USER
from _paths import SRC
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
        if edit:
            p.js("document.querySelector('[data-mode=edit]').click()")
            p.until("!!document.querySelector('#usecases [data-eye]')", "Edit shows the eyes")
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
        p.js("window.__old_document = true")
        p.js("location.reload()")
        p.until("window.__old_document === undefined && document.readyState === 'complete' && document.querySelectorAll('#usecases .ucl-row').length > 0", "the page reloaded")

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
            self.assertEqual(p.js("[...document.querySelectorAll('.tabs .tab')].map(t => t.textContent)"), ["Dashboard", "Work items", "Milestones", "Use cases", "Settings"])
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

    def test_a_published_file_has_no_tab_no_route_and_no_page_and_keeps_the_selected_use_cases(self):
        path = self.publish()
        for hash_ in ("", "#usecases&p=ABC", "#usecases&p=ABC&uc=1.1"):
            with self.subTest(hash=hash_), chrome() as cdp:
                p = self.draw(cdp, path, hash_)
                self.assertEqual(p.js("[...document.querySelectorAll('.tabs .tab')].map(t => t.textContent)"), ["Dashboard", "Work items", "Milestones"])
                self.assertEqual(p.js("document.querySelectorAll('#usecases, #usecase, .ucl-row, [data-uc-more], .ucmore').length"), 0)
                self.assertEqual(p.js("document.querySelector('.tab[aria-selected=true]').textContent"), "Dashboard", "an address of the Use cases page opens the first tab")
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
                        eye: r.querySelector('.ucl-eye').textContent, label: r.querySelector('.ucl-go').getAttribute('aria-label') }))""")}
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
                    p.js("document.querySelector('#ucl-status').click()")
                    p.until("!!document.querySelector('.ucl-pop')", "the status choices opened")
                    small = p.js("""[...document.querySelectorAll('.ucl-pop label, .ucl-pop button')].map(e => { const r = e.getBoundingClientRect(); return [e.className || e.tagName, Math.round(r.width), Math.round(r.height)]; }).filter(x => x[1] < 24 || x[2] < 24)""")
                    self.assertEqual(small, [], "the status choices are big enough")
                    self.assertTrue(p.js("[...document.querySelectorAll('.ucl-pop')].every(e => e.getBoundingClientRect().right <= window.innerWidth)"), "the choices stay in the window")
                    sizes = p.js("[...document.querySelectorAll('#usecases *')].filter(e => e.childNodes.length && [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())).map(e => parseFloat(getComputedStyle(e).fontSize))")
                    self.assertGreaterEqual(min(sizes), 13, "no text under 13 px")

    def test_text_contrast_is_at_least_4_5_to_1_in_light_and_dark(self):
        sels = ["#usecases h1", ".ucl-sub", ".ucl-ref", ".ucl-go", ".ucl-name small", ".ucl-head", ".ucl-ms", ".ucl-wi", ".ucl-wi small", ".ucl-st .pill",
                ".ucl-eye", ".ucl-row.off .ucl-eye", ".ucl-count", ".ucl-hd span", ".seg button", ".ucl-pill", "#ucl-sort", ".ucl-search input"]
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

    def test_view_shows_the_eye_in_words_only_and_edit_makes_it_a_switch(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertEqual(p.js("document.querySelectorAll('#usecases [data-eye]').length"), 0)
            self.assertEqual(p.js("[...document.querySelectorAll('#usecases [data-eye-words]')].map(e => e.textContent)"), [ON, ON, OFF, OFF])
            p.js("document.querySelector('[data-mode=edit]').click()")
            p.until("document.querySelectorAll('#usecases [data-eye]').length === 4", "Edit makes each eye a button")
            self.assertEqual(p.js("document.querySelectorAll('#usecases [data-eye-words]').length"), 0)

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
                self.assertEqual(p.js(f"document.querySelector('[data-uc=\"{self.uc3}\"] .ucl-eye').textContent"), ON)
                self.assertEqual(self.count(p), "Showing 4 of 4 · 3 on the dashboard")
                self.assertEqual(p.js(f"document.activeElement === document.querySelector('[data-uc=\"{self.uc3}\"] .ucl-eye')"), True, "the eye keeps the focus")
                p.js("document.querySelector('[data-view=dashboard]').click()")
                p.until("!!document.querySelector('.uc')", "the dashboard")
                self.assertEqual(p.js("document.querySelector('.uctotal').textContent"), "3 use cases", "the dashboard follows")
                self.assertEqual(p.js("document.querySelector('[data-uc-more]').textContent"), "1 more on the Use cases page")
                p.js("history.back()")
                p.until("!!document.querySelector('#usecases .ucl-row')", "back to the list")
                p.js("document.querySelector('[data-undo]') && document.querySelector('[data-undo]').click()")
                p.until("!!document.querySelector('[data-uc=\"%s\"] .ucl-eye') && document.querySelector('[data-uc=\"%s\"] .ucl-eye').textContent === '%s'" % (self.uc3, self.uc3, OFF), "the undo put it back")
                self.assertEqual(self.eye("1.10"), 0)
                self.click(p, f"[data-uc=\"{self.uc1}\"] [data-eye]")                    # take 1.1 off
                p.until("document.querySelector('.toast-text') && document.querySelector('.toast-text').textContent === 'UC 1.1 is no longer on the dashboard.'", "said")
                self.assertEqual(self.eye("1.1"), 0)
                self.assertEqual(self.count(p), "Showing 4 of 4 · 1 on the dashboard")

    def test_the_eye_keeps_its_row_when_the_switch_is_narrowed_and_the_focus_moves_on(self):
        with chrome() as cdp:
            p = self.show(cdp, edit=True)
            self.click(p, "[data-on=on]")
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
            self.assertEqual(p.js(f"document.querySelector('[data-uc=\"{self.uc3}\"] .ucl-eye').textContent"), OFF)


class Narrowing(Setup):
    def test_search_finds_a_reference_a_name_a_headline_the_text_and_a_milestone(self):
        with chrome() as cdp:
            p = self.show(cdp)
            for text, refs in (("1.2", ["UC 1.2"]), ("payment", ["UC 1.2"]), ("smallest suppliers", ["UC 1.10"]), ("zebra", ["UC 2.1"]),
                               ("pilot live", ["UC 1.1"]), ("SUPPLIER GO-LIVE", ["UC 1.2", "UC 2.1"]), ("uc 2", ["UC 2.1"])):
                self.type_in(p, "#ucl-q", text)
                p.until(f"{json.dumps(refs)}.join() === [...document.querySelectorAll('#usecases .ucl-list .ucl-row .ucl-ref')].map(e => e.textContent).join()", f"search {text!r}")
            self.type_in(p, "#ucl-q", "nothing like this")
            p.until("!!document.querySelector('#usecases [data-empty]')", "the empty state")
            self.assertEqual(p.js("document.querySelector('#usecases [data-empty] p').textContent"), "No use cases match “nothing like this”.")
            self.assertEqual(self.count(p), "Showing 0 of 4 · 2 on the dashboard")
            self.click(p, "[data-clear-all]")
            p.until("document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 4", "Clear the filters brings them all back")
            self.assertEqual(p.js("document.querySelector('#ucl-q').value"), "")

    def test_the_status_choice_takes_any_number_and_clears(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.click(p, "#ucl-status")
            p.until("!!document.querySelector('.ucl-pop')", "open")
            p.until("document.activeElement.value === 'On track'", "the first choice takes the focus")
            self.assertEqual(p.js("[...document.querySelectorAll('.ucl-pop label')].map(e => e.textContent)"), ["On track", "Flag", "High risk"])
            self.click(p, ".ucl-pop input[value=Flag]")
            p.until("document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 1", "one is Flag")
            self.assertEqual(p.js("document.querySelector('#ucl-status').textContent.trim()"), "Status: Flag")
            self.click(p, ".ucl-pop input[value='High risk']")
            p.until("document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 2", "Flag and High risk")
            self.assertEqual(self.refs(p), ["UC 1.2", "UC 1.10"])
            self.assertEqual(self.count(p), "Showing 2 of 4 · 2 on the dashboard")
            self.press(p, "Escape")
            p.until("!document.querySelector('.ucl-pop') && document.activeElement.id === 'ucl-status'", "Esc closes it and the focus returns")
            self.assertEqual(p.js("document.querySelector('#ucl-status').textContent.trim()"), "Status: Flag, High risk")
            self.click(p, "#ucl-status")
            self.click(p, ".ucl-pop [data-clear]")
            p.until("document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 4", "Clear")
            self.click(p, "h1")
            p.until("!document.querySelector('.ucl-pop')", "a click away closes it")

    def test_the_switch_counts_follow_the_other_filters_and_narrow_the_list(self):
        with chrome() as cdp:
            p = self.show(cdp)
            nums = "[...document.querySelectorAll('#usecases .seg button')].map(b => b.textContent.replace(/\\s+/g, ' ').trim())"
            self.assertEqual(p.js(nums), ["All 4", f"{ON} 2", f"{OFF} 2"])
            self.click(p, "[data-on=off]")
            p.until("document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 2", "not on the dashboard")
            self.assertEqual(self.refs(p), ["UC 1.10", "UC 2.1"])
            self.assertEqual(p.js("document.querySelector('[data-on=off]').getAttribute('aria-pressed')"), "true")
            self.assertEqual(self.count(p), "Showing 2 of 4 · 2 on the dashboard")
            self.click(p, "#ucl-status")
            self.click(p, ".ucl-pop input[value='On track']")
            p.until("document.querySelectorAll('#usecases .ucl-list .ucl-row').length === 1", "not on the dashboard and On track")
            self.assertEqual(p.js(nums), ["All 2", f"{ON} 1", f"{OFF} 1"], "the counts follow the Status choice")
            self.assertEqual(self.refs(p), ["UC 2.1"])
            self.type_in(p, "#ucl-q", "portal")
            p.until("!!document.querySelector('#usecases [data-empty]')", "nothing is On track, not on the dashboard and a portal")
            self.assertEqual(p.js("document.querySelector('#usecases [data-empty] p').textContent"), "No use cases match “portal” with these filters.")

    def test_sort_by_reference_status_and_open_work_items(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertEqual(p.js("document.querySelector('#ucl-sort').textContent.trim()"), "Sort: Reference")
            for word, refs in (("Status", ["UC 1.10", "UC 1.2", "UC 1.1", "UC 2.1"]), ("Open work items", ["UC 1.2", "UC 1.1", "UC 2.1", "UC 1.10"]),
                               ("Reference", ["UC 1.1", "UC 1.2", "UC 1.10", "UC 2.1"])):
                self.click(p, "#ucl-sort")
                p.until("!!document.querySelector('.ddmenu [role=menuitemradio]')", "the sort menu")
                self.assertEqual(p.js("[...document.querySelectorAll('.ddmenu [role=menuitemradio]')].map(b => b.textContent.replace('✓', '').trim())"), ["Reference", "Status", "Open work items"])
                p.js(f"[...document.querySelectorAll('.ddmenu [role=menuitemradio]')].find(b => b.textContent.includes({json.dumps(word)})).click()")
                p.until(f"{json.dumps(refs)}.join() === [...document.querySelectorAll('#usecases .ucl-list .ucl-row .ucl-ref')].map(e => e.textContent).join()", f"sorted by {word}")
                self.assertEqual(p.js("document.querySelector('#ucl-sort').textContent.trim()"), f"Sort: {word}")

    def test_what_was_chosen_is_remembered_for_each_project_and_adds_no_back_entry(self):
        with chrome() as cdp:
            p = self.show(cdp)
            before = p.js("history.length")
            self.type_in(p, "#ucl-q", "payment")
            self.click(p, "[data-on=on]")
            self.click(p, "#ucl-sort")
            p.js("[...document.querySelectorAll('.ddmenu [role=menuitemradio]')].find(b => b.textContent.includes('Status')).click()")
            p.until("document.querySelector('#ucl-sort').textContent.trim() === 'Sort: Status'", "sorted")
            self.assertEqual(p.js("history.length"), before, "a filter, a search and a sort add no entry")
            self.assertEqual(p.js("location.hash"), "#usecases&p=ABC", "and are not in the address")
            self.reload(p)
            self.assertEqual(p.js("document.querySelector('#ucl-q').value"), "payment")
            self.assertEqual(p.js("document.querySelector('[data-on=on]').getAttribute('aria-pressed')"), "true")
            self.assertEqual(p.js("document.querySelector('#ucl-sort').textContent.trim()"), "Sort: Status")
            self.assertEqual(self.refs(p), ["UC 1.2"])
            saved = json.loads(p.js("localStorage.getItem('clark.ucPage')"))
            self.assertEqual(sorted(saved), ["ABC"], "kept under the project's code")
            self.assertEqual(saved["ABC"], {"st": [], "on": "on", "sort": "status", "q": "payment"})
            p.js("localStorage.setItem('clark.ucPage', JSON.stringify({ABC: {st: ['Flag'], on: 'nonsense', sort: 'nonsense', q: 5}, OTHER: {q: 'x'}}))")
            self.reload(p)
            self.assertEqual(p.js("document.querySelector('#ucl-q').value"), "", "a saved value that makes no sense falls back")
            self.assertEqual(p.js("document.querySelector('#ucl-status').textContent.trim()"), "Status: Flag")
            self.assertEqual(p.js("document.querySelector('#ucl-sort').textContent.trim()"), "Sort: Reference")
            self.assertEqual(p.js("document.querySelector('[data-on=all]').getAttribute('aria-pressed')"), "true")


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
                if edit:
                    self.assertEqual(self.focused(p), f"{ids[0]}:ucl-eye", "Right goes to the eye")
                    self.press(p, "ArrowDown")
                    self.assertEqual(self.focused(p), f"{ids[1]}:ucl-eye", "Down from an eye goes to the next eye")
                    self.press(p, "ArrowLeft")
                    self.assertEqual(self.focused(p), f"{ids[1]}:ucl-go", "Left comes back to the name")
                    self.assertEqual(self.stops(p), [f"{ids[1]}:ucl-go"])
                else:
                    self.assertEqual(self.focused(p), f"{ids[0]}:ucl-go", "no eye to go to in View")
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
            p.js("document.querySelector('#ucl-q').focus()")
            self.press(p, "ArrowDown")
            self.press(p, "Home")
            self.assertEqual(p.js("document.activeElement.id"), "ucl-q", "the arrows are taken only on a row")

    def test_the_names_and_controls_have_names_a_screen_reader_can_say(self):
        with chrome() as cdp:
            p = self.show(cdp, edit=True)
            self.assertEqual(p.js("[...document.querySelectorAll('#usecases button, #usecases input')].filter(e => !(e.getAttribute('aria-label') || e.textContent.trim() || e.labels && e.labels.length)).length"), 0)
            self.assertEqual(p.js("document.querySelector('#usecases .ucl-list').getAttribute('aria-label')"), "Use cases")
            self.assertEqual(p.js("document.querySelector('#usecases .ucl-hd').getAttribute('aria-hidden')"), "true")
            self.assertEqual(p.js("document.querySelector('[data-eye]').getAttribute('aria-label')"),
                             f"UC 1.1 Invoice matching: {ON}. Take it off the dashboard")
            self.assertEqual(p.js("document.querySelector('#ucl-count').getAttribute('role')"), "status")


if __name__ == "__main__":
    unittest.main()
