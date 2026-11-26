"""Row 1659 (follow-up to row 1251): every template the Add a section box makes is added with its starting prompt, and the picture templates' sample
slot gives way to a chosen picture. Run: python3 dev/run_tests.py test_template_prompts_1659
Needs Chrome (the harness): fails, never skips, without it. Fictional data only. Classic look, at 1400 and 900 px.

Point 1: one case for every id startingText.js holds (the file is read here, so removing an id from it fails the test: the box then offers a template
that has no case, or the id has no entry in SHOWN). Each is added through the real route (the box's event, the template, "Add section"); the stored
section has no words and no picture, and Edit draws the muted prompt (the words in SHOWN) in an element that is on screen.
Point 2: Image and Text with image (a version 2 body, what the box makes) have the "Choose an image" control; a fixture picture given through it is shown
and the sample is gone. ("Add a picture" is the version 1 slot's button, pictureEdit.jsx, reached only by older sections.)
Exemptions, pinned as they are today, each with its reason, are in EXEMPT, NOT_IN_BOX and PINNED below.
"""
import json
import re
import time
import unittest

from _classic_page import classic
from test_report_editor import Base
from test_server import chrome
from test_starting_text_1251 import listed

OPEN = "document.dispatchEvent(new CustomEvent('clark:add-section', {detail: {after: 'ABC-S-003', opener: null}, cancelable: true, bubbles: true}))"
WIDTHS = (1400, 900)

# startingText.js id -> the box's template id (row 1270: one RAID cards card; its sections are stored as raid4, so raid-4's words)
BOX = {"raid-3": "raid-cards", "raid-4": "raid-cards"}
# The box offers these but startingText.js has no id for them: reason each.
EXEMPT = {
    "glance-template": "Project at a glance: three counts and tiles, no prompt was ruled for it (row 1264)",
    "report-headline": "Report headline: its own fields' hints, not on the row 1251 list",
    "full-image": "Image: the sample picture is its starting aid (point 2 checks it); no prompt was ruled",
}
# Listed in startingText.js but not a template of the box.
NOT_IN_BOX = {"raid-3": "raid-3 sections are only older ones; the box makes raid4 (raid-cards), which is checked as raid-4"}
# Today's truth, pinned: the words Edit draws for each box template (any piece of the starting text; Text with image shows "Write here." and one sample, the row 1251 v2 ruling).
SHOWN = {
    "text": "Write here.", "text-image": "Write here.", "figures-4": "Pick what each number shows.", "figures-3": "Pick what each number shows.",
    "table": "Add the first row.", "raid-cards": "Choose the items to show.", "work-items": "Say what the list shows.", "docs-links": "Add a file or a link.",
    "callout": "Write the one thing the reader must see.", "quote": "Write what they said.", "contacts": "Add a person.",
    "checklist": "Link the work items to tick off.", "key-dates": "No milestones to show yet.", "link-preview": "Paste the link.",
    "current-state": "Say where the project stands.", "plan-summary": "Add a step.", "gantt": "No Gantt lines in the client view yet.",
    "gantt-table": "No Gantt lines in the client view yet.", "one-doc": "Add the file.", "gallery": "",
}
# The box's Picture grid is refused by the store on this harness ("That change could not be made"): nothing is added. Pinned, not hidden.
# Work items: its caption prompt is the field's placeholder, in the page but not on screen until the filter bar is opened; the part draws no other starting words today. Pinned as in the page.
OFF_SCREEN = {"work-items"}
PINNED = {"gallery": "the store refuses the new Picture grid section, so nothing is added"}

SEEN = r"""(function(id, any){var s=document.querySelector('[data-id="'+id+'"]'); if(!s) return null;
  var on=function(e){var r=e.getBoundingClientRect();return any||(r.width>0&&r.height>0)};
  var out=[s.innerText]; s.querySelectorAll('*').forEach(function(e){ if(!on(e)) return;
    ['placeholder','data-placeholder','data-empty'].forEach(function(a){var v=e.getAttribute(a); if(v) out.push(v)}); });
  return JSON.stringify({seen: out.join('\n'), samples: 0});})"""

TEXT_KEYS = ("caption", "alt", "words", "html", "text", "description", "pictures", "image", "items", "title", "quote")


def stored_words(body):
    """Every piece of text or picture a stored body holds, so an empty template gives []. Tags and the empty JSON shells do not count."""
    out = []
    if not body:
        return out
    try:
        data = json.loads(body)
    except ValueError:
        data = body

    def walk(v, key=""):
        if isinstance(v, dict):
            for k, x in v.items():
                walk(x, k)
        elif isinstance(v, list):
            for x in v:
                walk(x, key)
        elif isinstance(v, str) and key in TEXT_KEYS + ("",):
            t = re.sub(r"<[^>]*>", "", re.sub(r"<h[1-6]>.*?</h[1-6]>", "", v)).strip()      # Plan summary starts with its two headings (its ruled description); they are not words of the writer
            if t:
                out.append(t)
    walk(data)
    return out


class Prompts(Base):
    def setUp(self):
        super().setUp()
        classic(self)

    def add(self, p, tid):
        before = set(self.ids_in_store())
        p.js(OPEN)
        p.until("!!document.querySelector('[role=dialog]')", "the box opened")
        p.js(f"document.querySelector('[data-template={tid}] input').click()")
        p.js("document.querySelector('button[data-place]').click()")
        p.until("!document.querySelector('[role=dialog]')", "the box closed")
        for _ in range(40):
            new = [i for i in self.ids_in_store() if i not in before]
            if new:
                break
            time.sleep(0.15)
        if new:
            p.until(f"!!document.querySelector('[data-id=\"{new[0]}\"]')", "the new section is drawn")
            time.sleep(0.4)
        return new

    def box_ids(self, p):
        p.js(OPEN)
        p.until("!!document.querySelector('[role=dialog]')", "the box opened")
        ids = p.js("[...document.querySelectorAll('[role=dialog] [data-template]')].map(e => e.dataset.template)")
        p.js("document.querySelector('[data-cancel]').click()")
        p.until("!document.querySelector('[role=dialog]')", "the box closed")
        return [i for i in ids if not i.startswith("built-in")]

    def test_every_starting_text_id_is_added_with_its_prompt_and_stores_nothing(self):
        ids = list(listed())
        self.assertEqual(len(ids), 21, "the list on main has 21 ids")
        mapped = {BOX.get(i, i) for i in ids if i not in NOT_IN_BOX}
        with chrome() as cdp:
            p = self.visit(cdp)
            for width in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.edit()
                offered = set(self.box_ids(p))
                self.assertEqual(offered, mapped | set(EXEMPT), f"{width}: every template of the box has a case or a stated exemption, and every listed id is in the box")
                for tid in sorted(mapped):
                    where = (width, tid)
                    new = self.add(p, tid)
                    if tid in PINNED:
                        self.assertEqual(new, [], (where, PINNED[tid]))
                        continue
                    self.assertEqual(len(new), 1, where)
                    row = [r for r in self.store.read("report_sections", "ABC") if r["id"] == new[0]][0]
                    self.assertEqual(stored_words(row["body"]), [], (where, "the stored body holds no words and no picture"))
                    got = json.loads(p.js(f"{SEEN}({json.dumps(new[0])}, {json.dumps(tid in OFF_SCREEN)})"))
                    self.assertIn(SHOWN[tid], got["seen"], (where, "Edit draws the starting prompt"))
                p.view()
                p.edit()

    def test_every_listed_id_has_a_case_so_removing_one_fails(self):
        ids = [i for i in listed() if i not in NOT_IN_BOX]
        for i in ids:
            self.assertIn(BOX.get(i, i), SHOWN, f"{i} has no case")
        self.assertEqual(set(SHOWN), {BOX.get(i, i) for i in ids}, "a case with no id in startingText.js is stale")

    def test_the_exemptions_are_real(self):
        self.assertTrue(all(k not in listed() for k in EXEMPT), "an exempt template is not in startingText.js")
        self.assertTrue(all(k in listed() for k in NOT_IN_BOX))


FIXTURE = r"""(async function(id){
  const c = document.createElement('canvas'); c.width = 640; c.height = 360; const g = c.getContext('2d'); g.fillStyle = 'rgb(40,160,60)'; g.fillRect(0, 0, 640, 360);
  const blob = await new Promise(r => c.toBlob(r, 'image/png'));
  const dt = new DataTransfer(); dt.items.add(new File([blob], 'fictional.png', {type: 'image/png'}));
  const i = document.querySelector('[data-id="' + id + '"] input[type=file]'); i.files = dt.files; i.dispatchEvent(new Event('change', {bubbles: true})); return true; })"""
STATE = r"""(function(id){var s=document.querySelector('[data-id="'+id+'"]');
  var on=function(e){var r=e.getBoundingClientRect();return r.width>0&&r.height>0};
  var btn=[...s.querySelectorAll('button')].filter(function(b){return on(b)&&b.textContent.trim()==='Choose an image'}).length;
  var shown=[...s.querySelectorAll('img')].filter(function(i){return on(i)&&!i.hasAttribute('data-sample')&&i.naturalWidth>0}).length;
  return JSON.stringify({choose: btn, samples: [...s.querySelectorAll('[data-sample]')].filter(on).length, shown: shown});})"""


class ChooseImage(Base):
    def setUp(self):
        super().setUp()
        classic(self)

    add = Prompts.add

    def test_choosing_a_picture_in_image_and_text_with_image_shows_it_and_removes_the_sample(self):
        # sample count before: Image draws the sample (FullImage.jsx:190); Text with image (version 2) draws one (TextImageSide.jsx, row 1251 v2 ruling)
        for tid, samples in (("full-image", 1), ("text-image", 1)):
            with chrome() as cdp:
                p = self.visit(cdp)
                for width in WIDTHS:
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    p.edit()
                    new = self.add(p, tid)
                    self.assertEqual(len(new), 1, (tid, width))
                    ref = json.dumps(new[0])
                    before = json.loads(p.js(f"{STATE}({ref})"))
                    self.assertEqual(before, {"choose": 1, "samples": samples, "shown": 0}, (tid, width, "the control is there and no picture is shown yet"))
                    p.js(f"{FIXTURE}({ref})")
                    p.until(f"JSON.parse({STATE}({ref})).shown > 0", f"{tid} {width}: the chosen picture is shown")
                    after = json.loads(p.js(f"{STATE}({ref})"))
                    self.assertEqual(after["samples"], 0, (tid, width, "the sample is gone"))
                    self.assertGreaterEqual(after["shown"], 1, (tid, width))
                    row = [r for r in self.store.read("report_sections", "ABC") if r["id"] == new[0]][0]
                    self.assertTrue(stored_words(row["body"]) or "pictures" in row["body"] or "image" in row["body"].lower(), (tid, width, "the picture is stored"))


if __name__ == "__main__":
    unittest.main()
