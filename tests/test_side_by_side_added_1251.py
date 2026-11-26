"""Row 1251 (PM ruling 26-11):Text and Image Side by Side, as the Add menu adds it today (a body of version 2), draws the sample picture in Edit
(Classic only, 1400 and 900), shows the chooser word "Choose an image" and the approved prompts, has no "replace this sample" line, and loses
the sample when a picture is chosen. View and Cards never draw it.
Run: python3 dev/run_tests.py test_side_by_side_added_1251
Needs Chrome (the harness): the page tests fail, never skip, without it. Fictional data only.
"""
import json
import re
import unittest

from _classic_page import classic
from _paths import SRC
from test_report_editor import Base
from test_server import chrome

OPEN = "document.dispatchEvent(new CustomEvent('clark:add-section', {detail: {after: null, opener: document.activeElement}, cancelable: true, bubbles: true}))"
SEC = "(function(){var l=[...document.querySelectorAll('.sec')].filter(function(s){return s.querySelector('.tpl-sbs-edit')});return l.length?l[l.length-1]:null})()"
SAMPLES = "(function(){var s=%s;if(!s)return -1;return [...s.querySelectorAll('[data-sample]')].filter(function(e){var r=e.getBoundingClientRect();return r.height>40&&r.width>40}).length})()" % SEC
TEXT = "(function(){var s=%s;if(!s)return null;var t=s.innerText+'\\n';s.querySelectorAll('[placeholder]').forEach(function(e){t+=e.getAttribute('placeholder')+'\\n'});return t})()" % SEC
PICK = "(function(){var s=%s;var b=s&&s.querySelector('button[data-act=pick]');return b?b.textContent:null})()" % SEC
CHOOSE = """(async function(){var c=document.createElement('canvas');c.width=64;c.height=36;var g=c.getContext('2d');g.fillStyle='rgb(40,160,60)';g.fillRect(0,0,64,36);
  var b=await new Promise(function(r){c.toBlob(r,'image/png')});var dt=new DataTransfer();dt.items.add(new File([b],'fictional.png',{type:'image/png'}));
  var i=document.querySelector('input[type=file]');i.files=dt.files;i.dispatchEvent(new Event('change',{bubbles:true}));return true})()"""


def add(p):
    p.edit()
    p.js(OPEN)
    p.until("!!document.querySelector('[role=dialog]')", "the Add box opened")
    p.js("document.querySelector('[data-template=text-image]').click()")
    p.js("document.querySelector('button[data-place]').click()")
    p.until(f"!!{SEC}", "Text and Image Side by Side was added")


def size(cdp, p, width):
    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)


class Classic(Base):
    def setUp(self):
        super().setUp()
        classic(self)

    def test_added_from_the_menu_it_draws_one_sample_the_chooser_word_and_the_approved_prompts_at_both_widths(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            size(cdp, p, 1400)
            add(p)
            for width in (1400, 900):
                size(cdp, p, width)
                p.until(f"{SAMPLES} === 1", f"one sample at {width}")
                text = p.js(TEXT)
                self.assertEqual(p.js(PICK), "Choose an image", width)
                self.assertIn("Write here.", text, width)
                self.assertIn("Say what the picture shows.", text, width)

    def test_no_replace_this_sample_line_is_anywhere(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            add(p)
            for width in (1400, 900):
                size(cdp, p, width)
                p.until(f"{SAMPLES} === 1", "the sample")
                text = p.js(TEXT).lower()
                self.assertNotIn("replace", text, width)
                self.assertNotIn("sample", text, width)

    def test_choosing_a_picture_takes_the_sample_away(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            add(p)
            p.until(f"{SAMPLES} === 1", "the sample")
            p.js(CHOOSE)
            p.until(f"{SAMPLES} === 0 && !!{SEC}.querySelector('.tpl-sbs-edit-frame img')", "the picture replaced the sample")

    def test_view_has_no_sample_and_no_prompt(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            add(p)
            p.until(f"{SAMPLES} === 1", "the sample")
            for width in (1400, 900):
                size(cdp, p, width)
                p.view()
                self.assertEqual(p.js("document.querySelectorAll('[data-sample]').length"), 0, width)
                body = p.js("document.body.innerText")
                for w in ("Choose an image", "Say what the picture shows."):
                    self.assertNotIn(w, body, f"View shows {w!r} at {width}")
                p.edit()


DATA = (SRC / "clark" / "page" / "src" / "edit" / "startingText.js").read_text(encoding="utf-8")
PROMPTS = sorted(set(re.findall(r'"([^"]{8,})"', DATA[DATA.index("export const STARTING_TEXT"):DATA.index("};", DATA.index("export const STARTING_TEXT"))])))
IDS = "[...document.querySelectorAll('input[name=template]')].map(function(i){return i.value})"
WITH = "(function(s){if(!s)return '';var t=s.innerText+'\\n';s.querySelectorAll('[placeholder]').forEach(function(e){t+=e.getAttribute('placeholder')+'\\n'});return t})"


class NeverAddedEmpty(Base):
    """AP (1): every template on the Add menu is stored without a prompt word and without a picture (the prompt and the sample are drawn in
    Edit, never saved), and the templates with a prompt show it in Edit, at 1400 and 900."""

    def setUp(self):
        super().setUp()
        classic(self)

    def test_each_added_template_stores_no_prompt_and_no_picture_and_shows_its_prompt(self):
        self.assertGreater(len(PROMPTS), 15)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.js(OPEN)
            p.until("!!document.querySelector('[role=dialog]')", "the Add box opened")
            ids = p.js(IDS)
            p.js("document.querySelector('[data-cancel]').click()")
            self.assertGreaterEqual(len(ids), 20)
            before = {r["id"] for r in self.store.read("report_sections", "ABC")}
            for tid in ids:
                p.js(OPEN)
                p.until("!!document.querySelector('[role=dialog]')", f"the box opened for {tid}")
                p.js(f"document.querySelector('[data-template={tid}]').click()")
                p.js("document.querySelector('button[data-place]').click()")
                p.until("!document.querySelector('[role=dialog]')", f"{tid} placed")
            rows = [r for r in self.store.read("report_sections", "ABC") if r["id"] not in before]
            self.assertGreaterEqual(len(rows), 20, "a section per template (a template the page already holds once is refused)")
            for r in rows:
                body = r.get("body") or ""
                self.assertNotIn("data:image", body, r["title"])
                for w in PROMPTS:
                    self.assertNotIn(w, body, f"{r['title']} stores the prompt {w!r}")
                self.assertTrue((r.get("title") or "").strip(), "a title is filled in")
            for width in (1400, 900):
                size(cdp, p, width)
                p.until(f"document.querySelectorAll('.sec').length >= {len(rows)}", "the sections are drawn")
                count = ("(function(ids,ws){return ids.filter(function(id){var t=" + WITH + "(document.querySelector('[data-id=\"'+id+'\"]'));return ws.some(function(w){return t.indexOf(w)>=0})}).length})("
                         + json.dumps([r["id"] for r in rows]) + "," + json.dumps(PROMPTS) + ")")
                p.until(f"{count} >= 15", f"at least 15 added templates draw a prompt at {width}")


class Cards(Base):
    def test_cards_has_no_sample(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertFalse(p.js("!!document.getElementById('theme')"), "this is a Cards page")
            add(p)
            for width in (1400, 900):
                size(cdp, p, width)
                p.until(f"!!{SEC}", "the section")
                self.assertEqual(p.js(f"{SEC}.querySelectorAll('[data-sample]').length"), 0, width)
                self.assertNotIn("Say what the picture shows.", p.js(TEXT), width)


if __name__ == "__main__":
    unittest.main()
