"""Row 1225 AP3 and AP4: one real page with one section made from each template, read in Edit and in View (shared by the two tests).

The sections are made the way the Add a section box makes them (the template's type, title and starting body) through the real
change route. The page-side readers run in the page: what a View section draws as controls, what text it shows, and each
visible text's colour against what it sits on (alpha and opacity composited down the ancestors).
"""
import json
import subprocess

from _demo import USER
from _paths import SRC
from clark import changes
from test_work_items import bundled

PAGE_SRC = SRC / "clark" / "page" / "src"


def templates():
    """TEMPLATES from the page's own list, read under node (id, type, title, start, body)."""
    code = bundled(PAGE_SRC / "logic" / "templates.js", "T")
    done = subprocess.run(["node", "-"], input=code + ";console.log(JSON.stringify(T.TEMPLATES.map(t=>({id:t.id,type:t.type,title:t.title,start:t.start||null,body:t.body||null}))))",
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def add_all(test):
    """{template id: section ref}. The filled sections are the ones test_tpl_all_published makes (one per store type, with a body);
    the types that have no body there (text, Gantt, Gantt table) are made the way the Add a section box makes them."""
    refs = {}
    with test.store.step("dashboard", USER) as st:      # the Gantt sections draw only the lines put on the page (show = 1)
        for n, (kind, name) in enumerate((("phase", "Fictional phase"), ("task", "Fictional task"))):
            st.create("gantt_lines", {"project": "ABC", "type": kind, "name": name, "start": "2030-01-07", "end": "2030-02-%02d" % (10 + n), "show": 1, "sort_order": n})
    for t in templates():
        if t["type"] in test.refs and t["id"] not in refs:
            refs[t["id"]] = test.refs[t["type"]]
            continue
        values = {"type": t["type"], "title": t["title"]}
        if t["start"] or t["body"]:
            values["body"] = t["start"] or t["body"]
        status, got = test.real_change({"project": "ABC", "kind": "report_sections", "op": changes.NEW, "values": values, "after": None})
        test.assertEqual(status, 200, (t["id"], got))
        refs[t["id"]] = got["ref"]
    return refs


# What a person can operate: anything in this list inside a section is a control.
CONTROLS = ("button, input, select, textarea, summary, [contenteditable]:not([contenteditable=false]), [role=button], [role=menuitem], "
            "[role=switch], [role=checkbox], [role=slider], [draggable=true], [data-act], [data-drag], .sec-ctl, .ico-btn")

READ_JS = """(ref) => {
  const sec = document.querySelector('.sec[data-id="' + ref + '"]');
  if (!sec) return null;
  const shown = (e) => { for (let n = e; n && n !== document; n = n.parentElement) { const s = getComputedStyle(n); if (s.display === 'none' || s.visibility === 'hidden') return false; } return true; };
  const label = (e) => e.tagName.toLowerCase() + (e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\\s+/).join('.') : '');
  const controls = [...sec.querySelectorAll(%s)].filter(shown).map(label);
  const words = []; const w = document.createTreeWalker(sec, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) { const t = n.textContent.replace(/\\s+/g, ' ').trim(); if (t && n.parentElement && shown(n.parentElement) && !n.parentElement.closest('script,style')) words.push(t); }
  return { controls, words, type: sec.dataset.type || null, cls: sec.className };
}""" % json.dumps(CONTROLS)

CONTRAST_JS = """(ref) => {
  const sec = document.querySelector('.sec[data-id="' + ref + '"]');
  if (!sec) return null;
  const parse = (c) => { const m = c.match(/rgba?\\(([^)]+)\\)/); if (!m) return null; const p = m[1].split(/[ ,\\/]+/).filter(Boolean).map(Number); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; };
  const over = (top, bot) => ({ r: top.r * top.a + bot.r * (1 - top.a), g: top.g * top.a + bot.g * (1 - top.a), b: top.b * top.a + bot.b * (1 - top.a), a: 1 });
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const shown = (e) => { for (let n = e; n && n !== document; n = n.parentElement) { const s = getComputedStyle(n); if (s.display === 'none' || s.visibility === 'hidden') return false; } return true; };
  const ground = (el) => { const chain = []; for (let n = el; n; n = n.parentElement) chain.push(n); let bg = { r: 255, g: 255, b: 255, a: 1 }, image = false;
    for (let i = chain.length - 1; i >= 0; i--) { const s = getComputedStyle(chain[i]); const c = parse(s.backgroundColor); if (c && c.a > 0) bg = over(c, bg); if (s.backgroundImage !== 'none') image = true; }
    return { bg, image }; };
  const opacity = (el) => { let o = 1; for (let n = el; n; n = n.parentElement) o *= parseFloat(getComputedStyle(n).opacity); return o; };
  const out = [];
  const w = document.createTreeWalker(sec, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    const text = n.textContent.replace(/\\s+/g, ' ').trim(); const el = n.parentElement;
    if (!text || !el || !shown(el) || el.closest('script,style')) continue;
    if (el.closest(':disabled,[aria-disabled="true"]') || opacity(el) < 0.1) continue;      // an inactive control is exempt (1.4.3); a label at opacity 0 is not drawn
    const r = document.createRange(); r.selectNodeContents(n); const b = r.getBoundingClientRect(); if (b.width < 1 || b.height < 1) continue;
    const g = ground(el); const fg = parse(getComputedStyle(el).color); const o = opacity(el);
    const fgc = over({ r: fg.r, g: fg.g, b: fg.b, a: fg.a * o }, g.bg);
    const l1 = lum(fgc), l2 = lum(g.bg); const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    out.push({ text: text.slice(0, 40), ratio: Math.round(ratio * 100) / 100, image: g.image, tag: el.tagName.toLowerCase() + (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\\s+/).join('.') : '') });
  }
  return out;
}"""


import test_tpl_all_published as _all      # noqa: E402  (the module, so its own tests are not collected here)


class Family(_all.AllTemplates):
    """One section per template (filled, as test_tpl_all_published fills them) on the served page; the inherited tests are not run again."""
    test_the_file_holds_every_template_and_only_what_the_rules_allow = None
    test_the_local_view_shows_what_the_file_shows = None

    def read(self, width, dark, js, modes=("edit", "view")):
        """{mode: {template id: what `js` (a function of the section ref) returns}} on the page at `width`, light or dark."""
        from test_server import chrome
        if not hasattr(self, "family_refs"):
            self.family_refs = add_all(self)
        refs = self.family_refs
        got = {}
        with chrome() as cdp:
            p = self.visit(cdp)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
            p.js("document.documentElement.dataset.theme = %s" % json.dumps("dark" if dark else "light"))
            for mode in modes:
                getattr(p, mode)()
                got[mode] = {tid: p.js("(%s)(%s)" % (js, json.dumps(ref))) for tid, ref in refs.items()}
        return got
