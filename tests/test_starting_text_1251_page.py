"""Row 1251, slice 1: Edit draws the starting text of an empty template part; View never does.
Run: python3 dev/run_tests.py test_starting_text_1251_page
Needs Chrome (the harness): the page tests fail, never skip, without it. Fictional data only.
"""
import json
import unittest

from _classic_page import classic
from _demo import USER
from _pictures import GOOD
from test_report_editor import Base
from test_server import chrome

# type, title, the words Edit shows somewhere in the section (text, placeholder or a field's empty line)
CASES = [
    ("text", "Fictional plain", ["Write here."]),
    ("text", "Header", ["Say where the project stands."]),
    ("textimage", "Fictional ti", ["Write here.", "Add a picture.", "Say what the picture shows."]),
    ("gallery", "Fictional gal", ["Add a picture.", None]),
    ("imagecap", "Fictional cap", ["Add a picture.", None]),
    ("quote", "Fictional quote", ["Write what they said.", "Say who said it."]),
    ("callout", "Fictional callout", ["Write the one thing the reader must see."]),
    ("contacts", "Fictional contacts", ["Add a person."]),
    ("onedoc", "Fictional doc", ["Add the file."]),
    ("reportheadline", "Fictional headline", ["Add the headline: the one thing the reader should take away."]),
    # slice 2
    ("figures4", "Fictional fig4", ["Pick what each number shows."]),
    ("figures3", "Fictional fig3", ["Pick what each number shows."]),
    ("table", "Fictional table", ["Add the first row."]),
    ("raid3", "Fictional raid3", ["Choose the items to show."]),
    ("raid4", "Fictional raid4", ["Choose the items to show."]),
    ("workitems", "Fictional wi", ["Set a filter to choose the rows.", "Say what the list shows."]),
    ("doclinks", "Fictional dl", ["Add a file or a link."]),
    ("checklist", "Fictional check", ["Link the work items to tick off."]),
    ("linkcard", "Fictional link", ["Paste the link.", "Write what the reader will find there."]),
    ("keydates", "Fictional kd", ["No milestones to show yet."]),
    ("gantt", "Fictional gantt", ["No Gantt lines in the client view yet."]),
    ("gantttable", "Fictional gt", ["No Gantt lines in the client view yet."]),
]
FULL_PICTURE = "Add a picture: replace this sample with your own."
FULL_CAPTION = "Add a caption: what the picture shows."
ALL = sorted({w for _, _, ws in CASES for w in ws if w})
SEEN = "(function(sel){var s=document.querySelector(sel);if(!s)return null;var t=s.innerText+'\\n';s.querySelectorAll('[placeholder]').forEach(function(e){t+=e.getAttribute('placeholder')+'\\n'});return t})"


class Page(Base):
    def setUp(self):
        super().setUp()
        classic(self)          # the starting text is a Classic look (Cards keeps its old words, see Cards below)

    def make_one(self, typ, title, body=None):
        with self.store.step("dashboard", USER) as st:
            row = {"project": "ABC", "type": typ, "title": title, "sort_order": 999 + len(title)}
            if body:
                row["body"] = body
            return st.create("report_sections", row)

    def make(self, typ, title):
        with self.store.step("dashboard", USER) as st:
            return st.create("report_sections", {"project": "ABC", "type": typ, "title": title, "sort_order": 999 + len(title)})

    def test_edit_draws_the_words_and_view_draws_none_of_them(self):
        refs = [(self.make(t, ti), ws) for t, ti, ws in CASES]
        with chrome() as cdp:
            p = self.visit(cdp)
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.edit()
                for ref, ws in refs:
                    sel = f"[data-id={json.dumps(ref)}]"
                    p.until(f"!!document.querySelector({json.dumps(sel)})", "the section is drawn")
                    text = p.js(f"{SEEN}({json.dumps(sel)})")
                    for w in ws:
                        if w:
                            self.assertIn(w, text, f"{ref}: {w} at {width}")
                p.view()
            p.view()
            body = p.js("document.body.innerText + [...document.querySelectorAll('[placeholder]')].map(e => e.placeholder).join('\\n')")
            for w in ALL:
                self.assertNotIn(w, body, f"View shows {w!r}")

    def test_gallery_caption_prompt_shows_only_under_a_picture(self):
        # an empty Gallery has no caption field, so its caption words are not drawn; the picture prompt is
        ref = self.make("gallery", "Fictional gal empty")
        sel = f"[data-id={json.dumps(ref)}]"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector({json.dumps(sel)})", "the section is drawn")
            text = p.js(f"{SEEN}({json.dumps(sel)})")
            self.assertIn("Add a picture.", text)
            self.assertNotIn("Say what the picture shows.", text)

    def test_full_image_draws_the_picture_prompt_and_the_caption_prompt_in_edit_only(self):
        # each width does all its checks inside its own pass, so a paused width never hides the other one's checks
        ref = self.make_one("imagecap", "Fictional full image", json.dumps({"v": 2}))
        sel = f"[data-id={json.dumps(ref)}]"
        pic_sel = f"[data-id={json.dumps(self.make_one('imagecap', 'Fictional full image with picture', json.dumps({'v': 2, 'pictures': {'original': GOOD}})))}]"      # the caption is offered once a picture is in
        with chrome() as cdp:
            p = self.visit(cdp)
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.edit()
                p.until(f"!!document.querySelector({json.dumps(sel)})", "the section is drawn")
                self.assertEqual(p.js(f"document.querySelector({json.dumps(sel)} + ' [data-start=image]').textContent"), FULL_PICTURE, f"at {width}")
                p.until(f"!!document.querySelector({json.dumps(pic_sel)} + ' [data-act=caption-add]')", "the picture is in")
                p.js(f"document.querySelector({json.dumps(pic_sel)} + ' [data-act=caption-add]').click()")
                p.until(f"!!document.querySelector({json.dumps(pic_sel)} + ' .tpl-pic-field')", "the caption field")
                self.assertIn(FULL_CAPTION, p.js(f"{SEEN}({json.dumps(pic_sel)})"), f"the caption prompt at {width}")
                p.view()
                body = p.js("document.body.innerText + [...document.querySelectorAll('[placeholder]')].map(e => e.placeholder).join('\\n')")
                for w in (FULL_PICTURE, FULL_CAPTION):
                    self.assertNotIn(w, body, f"View shows {w!r} at {width}")

    def test_at_a_glance_has_no_starting_text(self):
        ref = self.make_one("glancetemplate", "Fictional glance")
        sel = f"[data-id={json.dumps(ref)}]"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector({json.dumps(sel)})", "the section is drawn")
            self.assertFalse(p.js(f"!!document.querySelector({json.dumps(sel)} + ' [data-tpl-prompt], ' + {json.dumps(sel)} + ' [data-start]')"))
            self.assertNotIn("Add a", p.js(f"{SEEN}({json.dumps(sel)})").replace("Add a tile", ""))

    def test_plan_summary_prompts_sit_under_the_empty_paragraph_and_list_item(self):
        with self.store.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": "text", "title": "Plan summary", "sort_order": 1999,
                                                "body": "<h2>Where we are</h2><p></p><h2>What is next</h2><ul><li></li></ul>"})
        sel = f"[data-id={json.dumps(ref)}]"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector({json.dumps(sel)})", "the section is drawn")
            got = p.js("(function(s){var r=document.querySelector(s);return JSON.stringify([...r.querySelectorAll('[data-tpl-prompt]')].map(function(e){return [e.tagName,e.getAttribute('data-tpl-prompt'),e.textContent]}))})(" + json.dumps(sel) + ")")
            self.assertEqual(json.loads(got), [["P", "paragraph", "Write here."], ["LI", "item", "Add a step."]])
            p.view()
            body = p.js("document.body.innerText")
            self.assertNotIn("Add a step.", body)


class Cards(Base):
    """Cards is frozen: its Edit draws none of the starting text and no prompt, at 1400 and 900 (its old words stay)."""

    def test_cards_edit_draws_none_of_the_words_and_no_prompt(self):
        refs = [self.make_one(t, ti) for t, ti, _ in CASES]
        refs.append(self.make_one("text", "Plan summary", "<h2>Where we are</h2><p></p><ul><li></li></ul>"))
        refs.append(self.make_one("imagecap", "Fictional full image", json.dumps({"v": 2})))      # the full image: its picture prompt is Classic only
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertFalse(p.js("!!document.getElementById('theme')"), "this is a Cards page")
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.edit()
                for ref in refs:
                    sel = f"[data-id={json.dumps(ref)}]"
                    p.until(f"!!document.querySelector({json.dumps(sel)})", "the section is drawn")
                    text = p.js(f"{SEEN}({json.dumps(sel)})")
                    self.assertFalse(p.js(f"!!document.querySelector({json.dumps(sel)} + ' [data-tpl-prompt]')"), f"{ref}: a prompt in Cards at {width}")
                    for w in [w for w in ALL if w != "Add a picture."] + ["Add a step.", FULL_PICTURE, FULL_CAPTION]:          # "Add a picture." is also the old Image with caption hint
                        self.assertNotIn(w, text, f"{ref}: {w!r} in Cards at {width}")
                p.view()

    def test_cards_full_image_draws_no_picture_prompt_and_no_caption_prompt(self):
        empty = self.make_one("imagecap", "Fictional full image", json.dumps({"v": 2}))
        pic = self.make_one("imagecap", "Fictional full image with picture", json.dumps({"v": 2, "pictures": {"original": GOOD}}))
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertFalse(p.js("!!document.getElementById('theme')"), "this is a Cards page")
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.edit()
                e, c = f"[data-id={json.dumps(empty)}]", f"[data-id={json.dumps(pic)}]"
                p.until(f"!!document.querySelector({json.dumps(e)})", "the empty full image is drawn")
                self.assertFalse(p.js(f"!!document.querySelector({json.dumps(e)} + ' [data-start]')"), f"a picture prompt in Cards at {width}")
                self.assertNotIn(FULL_PICTURE, p.js(f"{SEEN}({json.dumps(e)})"), f"the picture prompt in Cards at {width}")
                p.until(f"!!document.querySelector({json.dumps(c)} + ' [data-act=caption-add]')", "the picture is in")
                p.js(f"document.querySelector({json.dumps(c)} + ' [data-act=caption-add]').click()")
                p.until(f"!!document.querySelector({json.dumps(c)} + ' .tpl-pic-field')", "the caption field")
                self.assertNotIn(FULL_CAPTION, p.js(f"{SEEN}({json.dumps(c)})"), f"the caption prompt in Cards at {width}")
                p.view()

    def make_one(self, typ, title, body=None):
        with self.store.step("dashboard", USER) as st:
            row = {"project": "ABC", "type": typ, "title": title, "sort_order": 999 + len(title)}
            if body:
                row["body"] = body
            return st.create("report_sections", row)


if __name__ == "__main__":
    unittest.main()
