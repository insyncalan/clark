"""#214 (the look of the ask panel): the panel's look in a real browser, and every string it shows.

Run: python3 dev/run_tests.py test_ask_look
Headless Chrome through the shared harness, the real page with fictional demo data, the server's `ask` a stub (as in
test_ask_panel). At 1400 and 900 px, light and dark: no sideways scroll, every control at least 24 px (the grip's hit area too),
no text under 12 px, the panel's text at least 4.5:1 against what is behind it (the glow worst case counted), the suggestions in
ONE row that scrolls sideways, the working line in their place with the box where it was, the chat announced. A second class reads
every string the panel shows in its four states (ready, working, off, not set up) and fails on jargon, a sentence that starts with
the product's name, and a name or a date.
"""
import json
import re
import sqlite3
import unittest

from _paths import ROOT
from test_report_editor import Base
from test_ask_panel import Stub
from test_server import chrome

WORDS = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "askWords.js").read_text(encoding="utf-8")

# Reads the colours in the page itself: rgb() and color(srgb ...) both, a stack of backgrounds up to the panel, and the panel's glow
# (the brand blue at its strongest, 24%) laid over whatever is not on a solid background of its own.
MEASURE = r"""(function () {
  var panel = document.getElementById('ask-panel');
  function parse(c) {
    var m = /^rgba?\(([^)]+)\)$/.exec(c);
    if (m) { var p = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; }
    m = /^color\(srgb ([^)]+)\)$/.exec(c);
    if (m) { var q = m[1].split(/[ \/]+/).filter(Boolean).map(Number); return { r: q[0] * 255, g: q[1] * 255, b: q[2] * 255, a: q.length > 3 ? q[3] : 1 }; }
    return null;
  }
  function hex(h) { h = h.trim(); if (h[0] !== '#') return parse(h); var n = parseInt(h.slice(1), 16); return { r: n >> 16, g: (n >> 8) & 255, b: n & 255, a: 1 }; }
  function lin(v) { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }
  function lum(c) { return .2126 * lin(c.r) + .7152 * lin(c.g) + .0722 * lin(c.b); }
  function ratio(a, b) { var x = lum(a), y = lum(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); }
  function over(f, b) { return { r: f.r * f.a + b.r * (1 - f.a), g: f.g * f.a + b.g * (1 - f.a), b: f.b * f.a + b.b * (1 - f.a), a: 1 }; }
  var blue = hex(getComputedStyle(document.documentElement).getPropertyValue('--brand-blue'));
  function behind(el) {
    var stack = [], solid = false, e = el;
    while (e && e.nodeType === 1) {
      var c = parse(getComputedStyle(e).backgroundColor);
      if (c && c.a > 0) { stack.push(c); if (c.a >= .99) { solid = e !== panel; break; } }
      if (e === panel) break;
      e = e.parentElement;
    }
    var base = stack.length ? stack[stack.length - 1] : { r: 255, g: 255, b: 255, a: 1 };
    if (base.a < 1) base = over(base, { r: 255, g: 255, b: 255, a: 1 });
    var plain = base;
    for (var i = stack.length - 2; i >= 0; i--) plain = over(stack[i], plain);
    var worst = plain;
    if (!solid) { var glow = over({ r: blue.r, g: blue.g, b: blue.b, a: .24 }, base); worst = glow; for (var j = stack.length - 2; j >= 0; j--) worst = over(stack[j], worst); }
    return { plain: plain, worst: worst };
  }
  function shown(el) { var r = el.getBoundingClientRect(), cs = getComputedStyle(el); return r.width > 2 && r.height > 2 && cs.visibility !== 'hidden' && cs.display !== 'none'; }
  var out = { vw: document.documentElement.clientWidth, docW: document.documentElement.scrollWidth, panelW: panel.scrollWidth, panelClient: panel.clientWidth,
              small: [], low: [], short: [], checked: 0, controls: 0 };
  var all = [panel].concat([].slice.call(panel.querySelectorAll('*')));
  all.forEach(function (el) {
    if (!shown(el)) return;
    var own = [].some.call(el.childNodes, function (n) { return n.nodeType === 3 && n.textContent.trim(); });
    var cs = getComputedStyle(el), name = (el.id ? '#' + el.id : '') + '.' + String(el.className).split(' ')[0] + ' "' + el.textContent.trim().slice(0, 24) + '"';
    if (own) {
      var fs = parseFloat(cs.fontSize);
      if (fs < 12) out.small.push(name + ' ' + fs + 'px');
      var fg = parse(cs.color), bg = behind(el);
      if (fg) {
        var f1 = over(fg, bg.plain), f2 = over(fg, bg.worst), r = Math.min(ratio(f1, bg.plain), ratio(f2, bg.worst));
        out.checked++;
        if (r < 4.5) out.low.push(name + ' ' + r.toFixed(2));
      }
    }
    if (el.matches('button, a[href], textarea, [role=separator][tabindex]')) {
      var b = el.getBoundingClientRect();
      out.controls++;
      if (b.width < 24 || b.height < 24) out.short.push(name + ' ' + Math.round(b.width) + 'x' + Math.round(b.height));
    }
  });
  return JSON.stringify(out);
})()"""

# What every string on the panel is checked for.
JARGON = re.compile(r"\b(path|request|JSON|API|token|tag|attribute|stylesheet|CSS)s?\b", re.I)
DATE = re.compile(r"\b\d{4}-\d{1,2}-\d{1,2}\b|\b\d{1,2}[/.]\d{1,2}[/.]\d{2,4}\b|\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? \d{1,2}\b|\b\d{1,2} (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b|\b(Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day\b|\b(19|20)\d\d\b")
PRODUCT = re.compile(r"^(ask )?clark\b", re.I)
TITLE = "ask clark"                      # row 820: the one string allowed to start with the product's name
# A capital letter inside a sentence is a name unless it is a word the panel is known to use.
KNOWN = {"Claude", "Anthropic", "Settings", "Ask", "Apply", "Undo", "Stop", "Wi", "Fi", "HDMI", "IT"}

SETTLE = "document.querySelector('#ask-box') && !document.querySelector('#ask-send').disabled"


class Look(Base):
    def setUp(self):
        super().setUp()
        self.stub = Stub()
        self.s.httpd.ask = self.stub

    def open_panel(self, cdp, width=1400, theme="light", ready=True):
        p = self.visit(cdp)
        # reduced motion, as a person can ask for: no entrance movement and no fading, so a colour or a position read mid-way is neither
        # the old nor the new one (and the panel is checked to work that way too)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, p.sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.js(f"document.documentElement.dataset.theme = '{theme}'")
        p.key("/", code="Slash", vk=191)
        p.until("!!document.querySelector('#ask-panel')", "the panel opened on /")
        if ready:
            p.until(SETTLE, "the panel is ready to take a question")
        return p

    def ask(self, p, text):
        p.js("document.querySelector('#ask-box').focus()")
        p.type(text)
        p.js("document.querySelector('#ask-send').click()")

    def measure(self, p):
        return json.loads(p.js(MEASURE))

    def check_measures(self, p, what):
        m = self.measure(p)
        self.assertLessEqual(m["docW"], m["vw"], f"{what}: the page scrolls sideways")
        self.assertLessEqual(m["panelW"], m["panelClient"] + 1, f"{what}: the panel scrolls sideways")
        self.assertGreater(m["checked"], 3, f"{what}: the text was read")
        self.assertGreater(m["controls"], 3, f"{what}: the controls were read")
        self.assertEqual(m["short"], [], f"{what}: controls under 24 px")
        self.assertEqual(m["small"], [], f"{what}: text under 12 px")
        self.assertEqual(m["low"], [], f"{what}: text under 4.5:1")

    def test_laptop_widths_light_and_dark_empty_and_with_an_answer(self):
        with chrome() as cdp:
            p = self.open_panel(cdp)
            for width in (1400, 900):
                for theme in ("light", "dark"):
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    p.js(f"document.documentElement.dataset.theme = '{theme}'")
                    self.check_measures(p, f"{width} {theme} empty")
        with chrome() as cdp:
            p = self.open_panel(cdp)
            self.ask(p, "When is go-live?")
            p.until("document.querySelectorAll('.ask-turn').length === 2", "the answer")
            for width in (1400, 900):
                for theme in ("light", "dark"):
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    p.js(f"document.documentElement.dataset.theme = '{theme}'")
                    self.check_measures(p, f"{width} {theme} answered")

    def test_off_and_not_set_up_at_both_widths_light_and_dark(self):
        for state in ("off", "signed-out"):
            self.stub.enabled, self.stub.connected = state != "off", False
            with chrome() as cdp:
                p = self.open_panel(cdp, ready=False)
                p.until(f"!!document.querySelector('#ask-{state}')", f"the {state} line")
                for width in (1400, 900):
                    for theme in ("light", "dark"):
                        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                        p.js(f"document.documentElement.dataset.theme = '{theme}'")
                        self.check_measures(p, f"{width} {theme} {state}")
                        if state == "off":                  # row 795: asking off keeps the greeting and the suggestions, disabled
                            self.assertEqual(p.js("document.querySelector('#ask-status').textContent.trim()"), "Ready. Ask about this project.")
                            self.assertEqual(p.js("document.querySelectorAll('#ask-pills button').length"), 6)
                            self.assertTrue(p.js("[...document.querySelectorAll('#ask-pills button')].every(b => b.disabled)"), f"{width} {theme}: pills disabled")
                            self.assertEqual(p.js("document.querySelector('#ask-pills').scrollWidth > 0 && document.documentElement.scrollWidth <= document.documentElement.clientWidth"), True)
                        else:
                            self.assertEqual(p.js("document.querySelector('#ask-pills')"), None, "no suggestions while it is not set up")

    def test_row_1097_the_open_settings_link_in_the_not_set_up_line_is_seen_and_readable(self):
        self.stub.enabled, self.stub.connected = True, False
        with chrome() as cdp:
            p = self.open_panel(cdp, ready=False)
            p.until("!!document.querySelector('#ask-signed-out a')", "the not set up line with its link")
            for width in (1400, 900):
                for theme in ("light", "dark"):
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    p.js(f"document.documentElement.dataset.theme = '{theme}'")
                    what = f"{width} {theme}"
                    got = json.loads(p.js("JSON.stringify((function(){var l=document.querySelector('#ask-signed-out'),a=l.querySelector('a'),r=a.getBoundingClientRect(),q=l.getBoundingClientRect(),pn=document.querySelector('#ask-panel').getBoundingClientRect();"
                                          "return {txt:a.textContent.trim(),w:r.width,h:r.height,inside:r.left>=pn.left&&r.right<=pn.right&&r.top>=q.top-1&&r.bottom<=q.bottom+1,fs:parseFloat(getComputedStyle(a).fontSize),ul:getComputedStyle(a).textDecorationLine,col:getComputedStyle(a).color,line:getComputedStyle(l).color};})())"))
                    self.assertEqual(got["txt"], "Open Settings", what)
                    self.assertTrue(got["inside"], f"{what}: the link sits inside the line and the panel")
                    self.assertGreaterEqual(got["fs"], 12, f"{what}: text under 12 px")
                    self.assertGreaterEqual(got["h"], 14, what)
                    self.assertTrue(got["ul"] != "none" or got["col"] != got["line"], f"{what}: the link looks different from the words around it")
                    self.check_measures(p, f"{what} not set up link")

    def test_row_1093_the_suggestions_follow_the_page_and_the_last_question(self):
        pills = "[...document.querySelectorAll('#ask-pills button')].map(b => b.textContent).join('|')"
        with chrome() as cdp:
            for width in (1400, 900):
                for theme in ("light", "dark"):
                    p = self.open_panel(cdp, width, theme)
                    first = p.js(pills)
                    p.js("location.hash = location.hash.replace(/^#[a-z]+/, '#milestones')")
                    p.until("!document.querySelector('#ask-panel')", "a move to another page closes the panel")
                    p.key("/", code="Slash", vk=191)
                    p.until(SETTLE, "the panel is ready again")
                    p.until(f"({pills}).indexOf('milestones are') > -1", f"{width} {theme}: milestone suggestions on the Milestones page")
                    self.assertNotEqual(p.js(pills), first)
                    p.js("location.hash = location.hash.replace(/^#[a-z]+/, '#work')")
                    p.until("!document.querySelector('#ask-panel')", "a move to another page closes the panel")
                    p.key("/", code="Slash", vk=191)
                    p.until(SETTLE, "the panel is ready again")
                    p.until(f"({pills}).indexOf('work items') > -1", f"{width} {theme}: work item suggestions on the Work items page")
                    self.assertEqual(p.js("document.querySelectorAll('#ask-pills button').length"), 6)
                    self.ask(p, "Which risks are red?")
                    p.until("document.querySelectorAll('.ask-turn').length === 2", "the answer")
                    p.until(f"({pills}).indexOf('risks') > -1", f"{width} {theme}: risk suggestions after a question about risks")
                    self.check_measures(p, f"{width} {theme} page suggestions")

    def test_row_1093_each_page_has_its_exact_list_and_a_page_without_one_has_the_generic_list(self):
        def listed(block_start, line_start):
            block = WORDS[WORDS.index(block_start):]
            line = next(l for l in block.splitlines() if l.strip().startswith(line_start))
            return re.findall(r'"([^"]+)"', line.split("[", 1)[1])
        generic = re.findall(r'^  "(.+)",$', WORDS[WORDS.index("export const SUGGESTIONS = ["):].split("\n];")[0], re.M)
        by = {"usecases": ["Which use cases need attention?", "Which use cases are not started?", "Which use cases have open risks?", "Which use cases are done?",
                           "What changed in the use cases this week?", "Which use cases have no owner?"],
              "gantt": ["What is the next milestone?", "Which work items are running late?", "What is on the critical path?", "Which work items start next week?",
                        "Which milestones are at risk?", "What ends this month?"]}
        for k, v in by.items():
            self.assertEqual(listed("export const PILLS_BY_SUBJECT", k + ":"), v, f"{k}: the words file and this test agree")
        self.assertEqual(len(generic), 6)
        pills = "JSON.stringify([...document.querySelectorAll('#ask-pills button')].map(b => b.textContent))"
        # Dashboard has no list of its own (PILLS_PAGE names work, milestones, usecases and gantt only): it, Settings and a published file show the generic one
        expected = {"usecases": by["usecases"], "gantt": by["gantt"], "settings": generic, "dashboard": generic}
        con = sqlite3.connect(str(self.store.path))      # the Gantt page is offered only where the project's setting says so
        con.execute("UPDATE projects SET show_gantt_editor = 1")
        con.commit()
        con.close()
        with chrome() as cdp:
            for width in (1400, 900):
                for page, want in expected.items():
                    p = self.open_panel(cdp, width)
                    if page != "dashboard":              # the page opens on the Dashboard
                        p.js(f"location.hash = location.hash.replace(/^#[a-z]+/, '#{page}')")
                        p.until("!document.querySelector('#ask-panel')", f"a move to {page} closes the panel ({p.js('location.hash')})")
                        p.key("/", code="Slash", vk=191)
                        p.until(SETTLE, "the panel is ready again")
                    self.assertEqual(p.js("location.hash.split('&')[0]"), "#" + page)
                    p.until(f"({pills}) === {json.dumps(json.dumps(want, separators=(",", ":")))}", f"{width} {page}: its suggestion list")
                    self.assertEqual(json.loads(p.js(pills)), want, f"{width} {page}")

    def test_the_suggestions_are_one_row_that_scrolls_sideways(self):
        with chrome() as cdp:
            for width in (1400, 900):
                p = self.open_panel(cdp, width)
                row = p.js("(function(){var b=[].slice.call(document.querySelectorAll('#ask-pills button'));"
                           "var r=document.querySelector('#ask-pills');var cs=getComputedStyle(r);"
                           "return {n:b.length, tops:b.map(function(x){return Math.round(x.getBoundingClientRect().top)}), wrap:cs.flexWrap, ox:cs.overflowX,"
                           "sw:r.scrollWidth, cw:r.clientWidth, role:r.getAttribute('role')};})()")
                self.assertGreaterEqual(row["n"], 5)
                self.assertEqual(len(set(row["tops"])), 1, f"{width}: one row")
                self.assertEqual(row["wrap"], "nowrap")
                self.assertIn(row["ox"], ("auto", "scroll"))
                self.assertGreater(row["sw"], row["cw"], f"{width}: more pills than fit, so the row scrolls sideways")
                p.js("document.querySelector('#ask-pills').scrollLeft = 120")
                self.assertGreater(p.js("document.querySelector('#ask-pills').scrollLeft"), 0)
                self.assertEqual(p.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), True)
                p.key("Escape", code="Escape", vk=27)
                p.until("document.querySelector('#ask-panel') === null", "closed")

    def test_the_box_is_one_line_the_suggestions_go_while_typing_and_the_send_is_a_round_arrow(self):
        with chrome() as cdp:
            p = self.open_panel(cdp)
            for width in (1400, 900):
                for theme in ("light", "dark"):
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    p.js(f"document.documentElement.dataset.theme = '{theme}'")
                    what = f"{width} {theme}"
                    p.js("(function(){var b=document.querySelector('#ask-box');b.focus();b.value='';b.dispatchEvent(new Event('input',{bubbles:true}));})()")
                    p.until("!!document.querySelector('#ask-pills')", f"{what}: suggestions with an empty box")
                    box = json.loads(p.js("JSON.stringify((function(){var r=document.querySelector('#ask-box').getBoundingClientRect();var s=document.querySelector('#ask-send').getBoundingClientRect();"
                                          "var cs=getComputedStyle(document.querySelector('#ask-send'));"
                                          "return {h:r.height,w:s.width,sh:s.height,left:s.left,boxRight:r.right,radius:cs.borderRadius,txt:document.querySelector('#ask-send').textContent.trim(),"
                                          "title:document.querySelector('#ask-send').title,label:document.querySelector('#ask-send').getAttribute('aria-label'),svg:!!document.querySelector('#ask-send svg'),"
                                          "bg:cs.backgroundColor,op:cs.opacity};})())"))
                    self.assertLessEqual(box["h"], 44, f"{what}: one line high")
                    self.assertGreaterEqual(min(box["w"], box["sh"]), 24, f"{what}: 24 px hit box")
                    self.assertEqual(box["txt"], "", f"{what}: no word on the button")
                    self.assertEqual((box["title"], box["label"]), ("Ask", "Ask"))
                    self.assertTrue(box["svg"])
                    self.assertGreaterEqual(box["left"], box["boxRight"] - 1, f"{what}: beside the field")
                    self.assertLess(float(box["op"]), 1, f"{what}: looks disabled while empty")
                    # row 1096: a round arrow in the brand colour (the pill token), not a grey square
                    self.assertGreaterEqual(float(box["radius"].split()[0].rstrip("px%")) * (box["sh"] / 100 if box["radius"].endswith("%") else 1), box["sh"] / 2 - 0.5, f"{what}: the send button is round ({box['radius']})")
                    token = p.js("(function(){var d=document.createElement('div');d.style.backgroundColor='var(--pill-color)';document.body.appendChild(d);var c=getComputedStyle(d).backgroundColor;d.remove();return c;})()")
                    self.assertEqual(box["bg"], token, f"{what}: the send button is the brand colour")
                    chans = [float(x) for x in re.findall(r"[\d.]+", box["bg"])[:3]]
                    self.assertGreater(max(chans) - min(chans), 40, f"{what}: the brand colour, not grey ({box['bg']})")
                    p.js("(function(){var b=document.querySelector('#ask-box');b.value='a very long question '.repeat(20);b.dispatchEvent(new Event('input',{bubbles:true}));})()")
                    p.until("!document.querySelector('#ask-pills')", f"{what}: suggestions gone while typing")
                    self.assertLessEqual(p.js("document.querySelector('#ask-box').getBoundingClientRect().height"), 44, f"{what}: a long question stays one line")
                    self.assertEqual(float(p.js("getComputedStyle(document.querySelector('#ask-send')).opacity")), 1.0, f"{what}: looks enabled with text")
            p.js("(function(){var b=document.querySelector('#ask-box');b.value='';b.dispatchEvent(new Event('input',{bubbles:true}));})()")
            p.until("!!document.querySelector('#ask-pills')", "suggestions back when the box is emptied")

    def test_a_suggestion_asks_its_words_and_leaves_the_box_alone(self):
        with chrome() as cdp:
            p = self.open_panel(cdp)
            p.js("document.querySelector('#ask-box').focus()")
            first = p.js("document.querySelector('#ask-pills button').textContent")
            p.js("document.querySelector('#ask-pills button').click()")
            p.until("document.querySelectorAll('.ask-turn').length === 2", "the answer")
            sent = [c[1] for c in self.stub.calls if c[0] == "ask"]
            self.assertEqual(sent[0]["question"], first)
            self.assertEqual(p.js("document.querySelector('#ask-box').value"), "")
            self.assertEqual(p.js("document.activeElement.id"), "ask-box", "the keyboard's place is kept")

    def test_the_working_line_takes_the_suggestions_place_and_the_box_stays_put(self):
        self.stub.hold.clear()
        with chrome() as cdp:
            p = self.open_panel(cdp)
            before = p.js("(function(){var r=document.querySelector('.ask-form').getBoundingClientRect();return [r.top, r.height];})()")
            row_top = p.js("document.querySelector('#ask-pills').getBoundingClientRect().top")
            self.ask(p, "Summarise the risks")
            p.until("!!document.querySelector('#ask-work') && !!document.querySelector('#ask-quip')", "the working line")
            self.assertEqual(p.js("document.querySelector('#ask-pills')"), None, "the suggestions went while it works")
            self.assertEqual(p.js("document.querySelector('#ask-log #ask-work')"), None, "the working line is not in the chat")
            self.assertAlmostEqual(p.js("document.querySelector('#ask-work').getBoundingClientRect().top"), row_top, delta=1)
            self.assertEqual(p.js("(function(){var r=document.querySelector('.ask-form').getBoundingClientRect();return [r.top, r.height];})()"), before)
            self.assertIsNone(p.js("document.querySelector('#ask-work').getAttribute('role')"), "the working line is not a live region of its own: the status line announces the work once (read below)")
            self.assertEqual(p.js("document.querySelector('#ask-quip').getAttribute('aria-hidden')"), "true", "the changing quip is not read out each time")
            self.assertEqual(p.js("document.querySelector('#ask-status').textContent.trim()"), "Working", "the status line says the work is going on")
            self.assertEqual(p.js("document.querySelector('#ask-status').getAttribute('role')"), "status")
            self.assertEqual(p.js("document.querySelector('#ask-status').getAttribute('aria-live')"), "polite")
            self.assertEqual(p.js("!!document.querySelector('#ask-work').closest('[role=status], [role=log], [role=alert], [aria-live]')"), False, "the working line is in no live region")
            self.assertEqual(p.js("[].filter.call(document.querySelectorAll('#ask-panel [role=status], #ask-panel [role=log], #ask-panel [aria-live]'), "
                                  "function(e){return /Working/.test(e.textContent);}).map(function(e){return e.id;})"), ["ask-status"],
                             "exactly one live region announces the work, once")
            for width in (1400, 900):
                for theme in ("light", "dark"):
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    p.js(f"document.documentElement.dataset.theme = '{theme}'")
                    self.check_measures(p, f"{width} {theme} working")
            self.stub.hold.set()
            p.until("!document.querySelector('#ask-work') && !!document.querySelector('#ask-pills')", "the suggestions came back with the answer")

    def test_the_chat_is_announced_and_has_a_name(self):
        with chrome() as cdp:
            p = self.open_panel(cdp)
            self.assertEqual(p.js("document.querySelector('#ask-log').getAttribute('role')"), "log")
            self.assertEqual(p.js("document.querySelector('#ask-log').getAttribute('aria-live')"), "polite")
            self.assertTrue(p.js("!!document.querySelector('#ask-log').getAttribute('aria-label')"))

    def test_the_grip_is_24_px_to_take_hold_of_and_a_thin_line_to_see(self):
        with chrome() as cdp:
            for width in (1400, 900):
                p = self.open_panel(cdp, width)
                g = p.js("(function(){var e=document.querySelector('#ask-grip');var r=e.getBoundingClientRect();var l=getComputedStyle(e,'::after');"
                         "return {w:r.width,h:r.height,line:parseFloat(l.width)};})()")
                self.assertGreaterEqual(g["w"], 24)
                self.assertLessEqual(g["line"], 4, "the line you see stays thin")
                self.assertEqual(g["h"], 900)
                self.assertTrue(p.js("document.querySelector('#ask-grip').tabIndex === 0"), "the grip can be reached with the keyboard")
                p.key("Escape", code="Escape", vk=27)
                p.until("document.querySelector('#ask-panel') === null", "closed")

    def test_the_off_line_keeps_its_words_and_the_link_goes_to_the_card(self):
        self.stub.enabled = False
        with chrome() as cdp:
            p = self.open_panel(cdp, ready=False)
            p.until("!!document.querySelector('#ask-off')", "the off line")
            self.assertEqual(p.js("document.querySelector('#ask-off').firstChild.textContent.trim()"), "Asking is off. Turn it on in Settings.")
            p.js("document.querySelector('#ask-off a').click()")
            p.until("document.querySelector('#ask-panel') === null && !!document.querySelector('#ask-settings')", "Settings, with the Asking card")
            p.until("!!document.activeElement && document.activeElement.tagName === 'H2' && !!document.activeElement.closest('#ask-settings')", "focus on the Asking card's heading")


class Strings(Base):
    """Every string the panel shows, read from the page in each of its states, and every one in the words file."""

    def setUp(self):
        super().setUp()
        self.stub = Stub()
        self.s.httpd.ask = self.stub

    def read(self, p):
        return p.js("""(function(){var out=[];var panel=document.getElementById('ask-panel');
          [panel].concat([].slice.call(panel.querySelectorAll('*'))).forEach(function(e){
            ['aria-label','placeholder','title'].forEach(function(a){var v=e.getAttribute(a);if(v)out.push(v);});
            [].forEach.call(e.childNodes,function(n){if(n.nodeType===3&&n.textContent.trim())out.push(n.textContent.trim());});});
          return out;})()""")

    def sentences(self, strings):
        found = []
        for s in strings:
            found += [x.strip() for x in re.split(r"(?<=[.?…])\s+", s) if x.strip()]
        return found

    def judge(self, strings, where):
        sentences = self.sentences(strings)
        self.assertGreater(len(sentences), 2, where)
        for s in sentences:
            self.assertIsNone(JARGON.search(s), f"{where}: jargon in {s!r}")
            # row 820: the panel TITLE is the product's own name by the row's exact words; every other sentence still must not start with it
            self.assertIsNone(PRODUCT.match(s) if s != TITLE else None, f"{where}: starts with the product's name: {s!r}")
            self.assertIsNone(DATE.search(s), f"{where}: a date in {s!r}")
            inside = re.findall(r"(?<=[a-z,;] )([A-Z][a-z]+)", s)
            for w in inside:
                self.assertIn(w, KNOWN, f"{where}: a name in {s!r}")
            self.assertNotIn("!", s, f"{where}: {s!r}")

    def test_every_string_in_each_state(self):
        seen = {}
        with chrome() as cdp:
            p = Look.open_panel(self, cdp)
            seen["ready"] = self.read(p)
            self.stub.hold.clear()
            Look.ask(self, p, "Summarise the risks")
            p.until("!!document.querySelector('#ask-quip') && document.querySelector('#ask-quip').textContent !== ''", "working")
            seen["working"] = self.read(p)
            p.js("document.querySelector('#ask-stop').click()")
            p.until("document.querySelectorAll('.ask-turn').length === 2", "stopped")
            seen["stopped"] = self.read(p)
        self.stub.hold.set()
        self.stub.enabled = False
        with chrome() as cdp:
            p = Look.open_panel(self, cdp, ready=False)
            p.until("!!document.querySelector('#ask-off')", "off")
            seen["off"] = self.read(p)
        self.stub.enabled, self.stub.connected = True, False
        with chrome() as cdp:
            p = Look.open_panel(self, cdp, ready=False)
            p.until("!!document.querySelector('#ask-signed-out')", "not set up")
            seen["not set up"] = self.read(p)
        for where, strings in seen.items():
            self.judge(strings, where)
        self.assertTrue(any("Asking is off. Turn it on in Settings." in s for s in seen["off"]))

    def test_every_suggestion_and_quip_in_the_words_file(self):
        def listed(name):
            block = WORDS[WORDS.index(f"export const {name} = ["):]
            return re.findall(r'^  "(.+)",$', block[:block.index("\n];")], re.M)
        suggestions, quips = listed("SUGGESTIONS"), listed("QUIPS")
        self.assertGreaterEqual(len(suggestions), 5)
        self.assertGreaterEqual(len(quips), 20)
        self.assertEqual(len(set(quips)), len(quips), "no quip twice in the list")
        self.judge(suggestions + quips + [WORDS_FOR_JUDGE], "words file")

    def test_the_judge_catches_what_it_should(self):
        for bad in ("The request failed.", "Open the API.", "Clark is ready.", "Ask clark is off.", "Ready since 2026-10-31.", "Ready on Friday.",
                    "Ask Sarah about this."):
            with self.assertRaises(AssertionError, msg=bad):
                self.judge([bad, "Ask a question.", "Ready."], "bad")


# The words file's own single sentences are judged in test_ask_panel; here the one line that names where words go is added to the pool.
WORDS_FOR_JUDGE = "Your question and the passages it needs go to Claude, which Anthropic runs."


if __name__ == "__main__":
    unittest.main()
