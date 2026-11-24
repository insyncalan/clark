"""Row 1479 (the 20-11 decision: the use case page a client sees is the editor's page, read only; Owner shown, Last change not, no History).

Run: python3 dev/run_tests.py test_uc_published_same_1479
Test names are the ticket's (AP1 to AP8). At 1400 and 900: 900 is its own subTest; test_server.PAUSED_900 (the one switch) is None, so it runs.
Part 1 (source): the layout is ONE component, UseCaseLayout.jsx; the editor's page and the published file's page both draw it and neither writes
its own cards, so the two cannot drift apart again (rule 1 of the ticket). A reference that already starts with UC is not given a second UC.
Part 2 (a real page): the editor's component read only and the file's component, both mounted on the same use case, have the same cards in the
same order with the same text and the same classes (the editor's History and its Details-only rows apart), at 1400 px, light and dark;
the reference is "UC 1.1" once on both.
Part 3 (the published bytes, Local and To client): hidden work items, a team note on a work item and on the use case, and the history are not in
the file; to_client.check_copy (the To client scan of the same bytes) finds none of them, and finds them when they are put in.
"""
import copy
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC, TOOLS
from _real_server import real_server
import sys

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402

from clark import __main__ as launcher, page, publish, server as sv, theme as themes, to_client, use_cases_read  # noqa: E402
from clark.store import open_store  # noqa: E402
from test_inline_edits import EMPTY_BRANDING, need_chrome  # noqa: E402,F401
from test_server import chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402
from test_publish_usecases import MARKERS, made, planted  # noqa: E402

COMP = SRC / "clark" / "page" / "src" / "components"
UC = "TUL-U-001"
ENTRY = """import { render } from "preact";
import { boot } from "./boot.jsx";
import { EDIT } from "./edit/index.js";
import { startApp } from "./app.js";
import { data, fromFile } from "./stores/report.js";
import { UseCaseDetail } from "./components/UseCaseDetail.jsx";
import { UseCaseFilePage } from "./components/UseCaseFilePage.jsx";

boot(EDIT);
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", startApp); else startApp();
// which: "editor" (the editor's component, read only) or "file" (the published file's page); both on the same data, the use case given an owner and a reference
window.clarkMountOne = (id, which, ref, owner, bare) => {
  let host = document.getElementById("uc-test");
  if (!host) {
    host = document.createElement("main");
    host.id = "uc-test";
    document.getElementById("main").style.display = "none";
    document.getElementById("main").after(host);
  }
  const d = bare ? { ...data.value, milestones: [], uc_milestones: [] } : data.value;     // bare: no milestone anywhere
  const via = (d.actions || []).concat(d.raid || [], d.decisions || []).filter((r) => r.use_case === id);
  const ms = (d.milestones || []).filter((m) => via.some((r) => r.milestone === m.id) || (d.uc_milestones || []).some((l) => l.use_case === id && l.milestone === m.id)).map((m) => ({ id: m.id, direct: (d.uc_milestones || []).some((l) => l.use_case === id && l.milestone === m.id) }));
  data.value = { ...d, use_cases: d.use_cases.map((u) => (u.id === id ? { ...u, ref, owner } : u)), use_case_pages: [{ id, next_steps: via.map((r) => r.id), milestones: ms }] };
  fromFile.value = which === "file" || which === "editor";
  render(which === "file" ? <UseCaseFilePage id={id} /> : <UseCaseDetail id={id} ed={null} />, host);
};
"""
SHAPE = """(() => {
  const root = document.querySelector('[data-ucd],[data-ucf]'), n = (c) => String(c).replace(/\\buc[df]-/g, 'uc-');
  const noted = !!root.querySelector('[data-ms-note]'), nums = root.querySelectorAll('[data-ms]').length;
  const histAny = [...root.querySelectorAll('h2')].some((h) => /History/.test(h.textContent));
  const how1 = root.querySelector('[data-ms-how]'), name1 = how1 && how1.parentElement.querySelector('[data-ms-open]');
  const howcss = how1 ? { basis: getComputedStyle(how1).flexBasis, fs: parseFloat(getComputedStyle(how1).fontSize), nameFs: parseFloat(getComputedStyle(name1).fontSize), under: how1.getBoundingClientRect().top >= name1.getBoundingClientRect().bottom - 1 } : null;
  const hist = root.querySelector('[aria-labelledby=ucd-h-hist]'); if (hist) hist.remove();
  const note = root.querySelector('[data-ms-note]'); if (note) note.remove();
  const txt = (e) => e ? e.textContent.replace(/\\s+/g, ' ').trim() : null;
  const classes = new Set(); root.querySelectorAll('*').forEach((e) => e.classList.forEach((c) => classes.add(n(c))));
  const sec = (e) => e.matches('section') ? (e.querySelector('h2') ? txt(e.querySelector('h2').firstElementChild || e.querySelector('h2')) : '') : '';
  return {
    crumb: txt(root.querySelector('nav')), h1: txt(root.querySelector('h1')), sub: txt(root.querySelector('[class$=-sub]')), line: txt(root.querySelector('[class$=-line]')),
    cards: [...root.querySelectorAll('section')].map(sec), std: txt(root.querySelector('section')),
    items: [...root.querySelectorAll('[data-item]')].map((b) => b.dataset.item).sort(),
    ms: [...root.querySelectorAll('[data-ms]')].map((li) => [li.dataset.ms, txt(li.querySelector('[data-ms-open]')), txt(li.querySelector('[data-ms-state]')), txt(li.querySelector('.num'))]).sort(),
    body: txt(root), acts: [...root.querySelectorAll('button,input,select,textarea,[role=menu],[contenteditable]')].filter((b) => !b.matches('[data-item],[data-ms-open],[data-open-all]')).length,
    lum: (() => { const lum = (c) => { const m = c.match(/[\\d.]+/g).map(Number); return (0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2]) / 255; };
      let bg = null, e = root.querySelector('section'); while (e && !bg) { const c = getComputedStyle(e).backgroundColor; if (!/rgba?\\(.*, 0\\)$/.test(c) && c !== 'transparent') bg = c; e = e.parentElement; }
      return { bg: lum(bg || getComputedStyle(document.body).backgroundColor), fg: lum(getComputedStyle(root.querySelector('h1')).color) }; })(),
    dts: [...root.querySelectorAll('dt')].map(txt), hist: !!hist, histAny, howcss,
    how: [...root.querySelectorAll('[data-ms-how]')].map(txt), noted, nums, owner: txt(root.querySelector('[data-uc-owner]')), word: txt(root.querySelector('[data-word]')),
    classes: [...classes].sort(), landmarks: [...root.querySelectorAll('nav,h1,h2,section,dl,ul')].map((e) => e.tagName + (e.getAttribute('aria-labelledby') ? '' : '')),
  };
})()"""


def tearDownModule():
    shutil.rmtree(EMPTY_BRANDING, ignore_errors=True)


class OneComponent(unittest.TestCase):
    """Part 1: by source."""

    def text(self, name):
        return (COMP / name).read_text(encoding="utf-8")

    def test_both_pages_draw_the_one_layout_and_write_no_cards_of_their_own(self):
        for name, prefix in (("UseCaseDetail.jsx", "ucd"), ("UseCaseFilePage.jsx", "ucf")):
            src = self.text(name)
            self.assertIn('import { UseCaseLayout, Crumb } from "./UseCaseLayout.jsx"', src, name)
            self.assertRegex(src, rf'<UseCaseLayout p="{prefix}"', name)
            code = re.sub(r"//[^\n]*", "", src)
            for own in (f"{prefix}-grid", f"{prefix}-items", f"{prefix}-ms ", "data-ms-open", "data-open-all", "<h1 class", "Where it stands</span>"):
                self.assertTrue(own not in code, f"{name} writes its own {own}")
            # the editor's History is its one own card (a slot of the layout); the file's page has none
            self.assertEqual(code.count(f"{prefix}-card"), 1 if prefix == "ucd" else 0, name)
            if prefix == "ucf":
                # AP2 and AP4 by source: the file's page gives the layout no slot that draws a control, a hint, an add row, a note or the History card, and writes no control of its own
                for slot in ("acts=", "top=", "stdHint=", "addWork=", "addMilestoneRow=", "msNote=", "after="):
                    self.assertNotIn(slot, code, f"{name} gives the layout a {slot} slot: a control or a History card")
                for tag in ("<button", "<input", "<textarea", "<select", "contenteditable", "History"):
                    self.assertNotIn(tag, code, f"{name} writes {tag}")
            else:
                self.assertIn("after={(", code, "the editor's History card is the layout's after slot")
        lay = self.text("UseCaseLayout.jsx")
        for need in ("Where it stands", "Work items", "Details", "Milestones", "data-open-all", "data-ms-open", "data-item"):
            self.assertIn(need, lay)
        self.assertNotIn("Last change", lay)
        self.assertNotIn("History", re.sub(r"//[^\n]*", "", lay), "no History in the shared part: the editor adds it as a slot")

    def test_ap6_source_a_reference_that_starts_with_uc_is_not_given_a_second_uc(self):
        src = (SRC / "clark/page/src/logic/useCasesList.js").read_text(encoding="utf-8")
        self.assertIn("const prefixed = ", src)
        self.assertIn("refOf = (u) => (u.ref ? prefixed(u.ref)", src)
        self.assertIn("refBox = (ref) => (refText(ref) ? prefixed(refText(ref))", src)


class SamePage(unittest.TestCase):
    """Part 2: the editor's component (read only) and the file's page, on the same use case."""

    @classmethod
    def setUpClass(cls):
        need_chrome()
        cls.tmp = tempfile.mkdtemp(prefix="clark-uc1479-")
        cls.src = Path(cls.tmp) / "src"
        shutil.copytree(SRC / "clark" / "page" / "src", cls.src, ignore=shutil.ignore_patterns("shown"))
        (cls.src / "main.jsx").write_text(ENTRY, encoding="utf-8")
        with mock.patch.object(build_page, "SRC", cls.src):
            cls.built = page.layer_theme(build_page.build(), themes.css("prototype-2.0"))   # row 1479: the label rule is Classic's (rules-2.css), so the page is read in Classic

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        need_chrome()
        self.store, self.folder, _ = load_demo()
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.addCleanup(self.store.close)
        self.path = self.folder / "clark.db"
        self.s = real_server(self.path, self.read, projects=lambda archived=False: [{"code": "TUL", "name": "Tulip"}], page_html=lambda: page.layer_theme(self.built, themes.css("prototype-2.0")))
        self.s.httpd.use_cases = use_cases_read.make_read(self.read, lambda code: set(), launcher.use_case_history(mock.Mock(path=self.path)))
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def read(self, code, archived="hide"):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return st.data_for(code, archived=archived)
        finally:
            st.close()

    def shape(self, which, width, scheme, ref="UC 1.1", bare=False):
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
            cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/#usecases&p=TUL"}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#usecases')", sid)), "the page drew")
            cdp.js(f"window.clarkMountOne({json.dumps(UC)}, {json.dumps(which)}, {json.dumps(ref)}, 'ZQ Owner Name', {json.dumps(bare)})", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-ucd],[data-ucf]')", sid)))
            self.assertTrue(wait(lambda: cdp.js("!/Loading the use case/.test(document.querySelector('[data-ucd],[data-ucf]').innerText)", sid)))
            got = cdp.js(SHAPE, sid)
            got["wide"] = cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid)
            got["controls"] = cdp.js("document.querySelectorAll('[data-ucd] textarea, [data-ucd] input, [data-ucf] textarea, [data-ucf] input, [data-eye], [data-restore], .ucd-acts, .ucx-addrow').length", sid)
            return got

    def test_published_and_editor_pages_have_the_same_cards_in_the_same_order(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme):
                    ed, fi = self.shape("editor", width, scheme), self.shape("file", width, scheme)
                    self.assertEqual(fi["cards"], ["Where it stands", "Work items", "Details", "Milestones"])
                    self.assertEqual(ed["cards"], fi["cards"], "the same cards in the same order (the editor's History apart)")
                    for k in ("crumb", "h1", "sub", "line", "std", "items", "ms", "owner", "word", "landmarks", "classes"):
                        self.assertEqual(ed[k], fi[k], k)
                    for got in (ed, fi):
                        self.assertTrue(got["wide"] and got["controls"] == 0, "no sideways scroll, no control")
                    self.assertTrue(fi["items"], "the use case has work items")
                    self.assertTrue(ed["nums"] and ed["noted"], "the editor's page explains the two ways when it has milestones")
                    self.assertTrue(fi["nums"] and not fi["noted"], "the file's page has the label and no explanation line")
                    for which in ("editor", "file"):
                        bare = self.shape(which, width, scheme, bare=True)
                        self.assertEqual((bare["nums"], bare["noted"]), (0, False), f"{which}: no milestones, no explanation line")

    def test_details_shows_owner_and_not_last_change(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme):
                    fi = self.shape("file", width, scheme)
                    self.assertEqual(fi["owner"], "ZQ Owner Name", "Owner is shown, as plain text")
                    self.assertEqual(fi["dts"][0], "Owner")
                    self.assertNotIn("Last change", fi["dts"])
                    self.assertNotIn("Last change", fi["body"])
                    self.assertNotIn("Add an owner", fi["body"])
                    self.assertEqual(self.shape("file", width, scheme)["acts"], 0, "the owner is not a field")

    def test_no_history_card(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme):
                    fi = self.shape("file", width, scheme)
                    self.assertFalse(fi["hist"], "no History card in the published page")
                    self.assertFalse(fi["histAny"], "no card or heading called History, whatever its id")
                    self.assertTrue(self.shape("editor", width, scheme)["histAny"], "the editor's page keeps its History card (the layout's after slot)")
                    self.assertNotIn("History", fi["cards"])
                    self.assertNotIn("Show all", fi["body"])
                    self.assertNotIn("took it off the dashboard", fi["body"])

    def test_reference_is_not_doubled_on_either_page(self):
        for width in (1400, 900):
            for ref, once in (("UC 1.1", "UC 1.1"), ("1.1", "UC 1.1"), ("uc 1.1", "uc 1.1")):
                with self.subTest(width=width, ref=ref):
                    for which in ("editor", "file"):
                        got = self.shape(which, width, "light", ref=ref)
                        self.assertEqual(got["crumb"], "Use cases › " + once, which)
                        self.assertTrue(got["h1"].startswith(once + " ·"), got["h1"])
                        for text in (got["crumb"], got["h1"], got["sub"]):
                            self.assertNotRegex(text, r"(?i)\buc uc\b", which)

    def test_milestones_carry_the_label_and_no_explanation_line(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme):
                    fi = self.shape("file", width, scheme)
                    self.assertTrue(fi["how"], "the file's page has a milestone label")
                    self.assertLessEqual(set(fi["how"]), {"Through work items", "Directly"}, "only the two published labels")
                    self.assertEqual(fi["nums"], len(fi["how"]), "one label for each milestone")
                    self.assertFalse(fi["noted"], "no explanation line")
                    self.assertNotIn("means", " ".join(fi["how"]))
                    if width == 1400:
                        # rules-2.css row 1479: `.ucf-ms .ucf-mshow { flex-basis: 100%; font-size: var(--size-small) }`, the label on its own line under the milestone name, smaller than the name
                        c = fi["howcss"]
                        self.assertEqual(c["basis"], "100%", "the label takes the whole line")
                        self.assertTrue(c["under"], "the label is under the milestone name")
                        self.assertLessEqual(c["fs"], c["nameFs"], "the label is no larger than the name (Classic: both 14)")

    def test_no_control_word_and_no_changing_element(self):
        gone = ("Change status", "On the dashboard", "Click the text to change it", "Add an owner", "Add a next step", "Link an existing work item", "Add a milestone", "...")
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme):
                    fi = self.shape("file", width, scheme)
                    self.assertEqual(fi["acts"], 0, "no button, input, menu or editable text")
                    for words in gone:
                        self.assertNotIn(words, fi["body"], words)

    def test_dark_theme_matches_the_editor_page_at_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                dark, light = self.shape("file", width, "dark"), self.shape("file", width, "light")
                ed, edl = self.shape("editor", width, "dark"), self.shape("editor", width, "light")
                self.assertLess(dark["lum"]["bg"], 0.35, "dark: the page behind the cards is dark")
                self.assertGreater(dark["lum"]["fg"], 0.6, "dark: the heading is light")
                self.assertGreater(light["lum"]["bg"], 0.6, "light: the page behind the cards is light")
                self.assertEqual(dark["lum"], ed["lum"], "the file's page and the editor's page have the same colours in dark")
                self.assertEqual(dark["cards"], ed["cards"])
                self.assertEqual(dark["landmarks"], ed["landmarks"], "heading and landmark order as the editor's page in dark")
                self.assertEqual(dark["classes"], ed["classes"], "the same shared classes")
                self.assertEqual(light["cards"], edl["cards"], "the light case of AP1 still holds")
                for k in ("cards", "landmarks", "h1", "owner", "how"):
                    self.assertEqual(dark[k], light[k], f"{k}: dark changes colours only")
                self.assertTrue(dark["wide"])


class NothingTeamOnly(unittest.TestCase):
    """Part 3: Local and To client are the same bytes (publish.render, then to_client.check_copy on them)."""

    HIDDEN = ("ZQ-OFF-STEP", "ZQ-SENSITIVE-STEP", "ZQ-STEP-INTERNAL-NOTE", "ZQ-USECASE-HISTORY", "ZQ-HIDDEN-USECASE-MILESTONE", "ZQ-UC-TEAM-NOTE-1479")

    @staticmethod
    def plant(plant):
        planted(plant)
        plant["data"]["use_cases"][0]["internal_note"] = "ZQ-UC-TEAM-NOTE-1479"
        plant["data"]["use_cases"][0]["owner"] = "ZQ-OWNER-1479"

    def test_hidden_items_and_team_notes_are_absent_in_both_modes(self):
        plant, pub, text = made(self.plant)
        body = text.encode("utf-8")
        self.assertEqual(body, publish.render(pub, page.page_html(EMPTY_BRANDING), plant["as_at"], pub["data"]["project"]["name"]).encode("utf-8"), "Local and To client are the same bytes, made once")
        for marker in self.HIDDEN:
            self.assertEqual(to_client.markers_found(body, [marker]), [], marker)
        self.assertEqual(to_client.check_copy(body, markers=self.HIDDEN, folder=None), [], "To client's scan of the bytes finds nothing")
        d = pub["data"]
        shown = {r["id"] for r in d["actions"] + d["raid"] + d["decisions"]}
        self.assertTrue({"PUB-A-020", "PUB-A-021"}.isdisjoint(shown), "the hidden work items are not rows of the file")
        self.assertTrue({"PUB-A-020", "PUB-A-021"}.isdisjoint(set(d["use_case_pages"][0]["next_steps"])))
        self.assertNotIn("internal_note", d["use_cases"][0])
        self.assertEqual(d["use_cases"][0]["owner"], "ZQ-OWNER-1479", "Owner is shown (the 20-11 decision)")

    def test_the_scan_is_live_it_finds_each_when_put_in(self):
        _, _, text = made(self.plant)
        for marker in self.HIDDEN:
            self.assertTrue(to_client.check_copy((text + f"<p>{marker}</p>").encode("utf-8"), markers=self.HIDDEN, folder=None), marker)


if __name__ == "__main__":
    unittest.main()
