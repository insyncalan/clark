"""Row 1021: Risks and issues, Open actions and Decisions, one line per item with one tinted letter icon.

Run: python3 dev/run_tests.py test_item_one_line
The owner's defect (too much white space): each item is ONE line, [icon] Title | Owner | Review by or Due | Priority or 'N d late' | Id,
the same columns in both cards, the header row once per card. The icon is a small tinted square: its LETTER is the kind (R risk,
I issue, A action, D decision), its COLOUR the status (red, amber, green). The status pill is gone. In the app the icon says the status
in a tooltip (hover and keyboard focus) and in its accessible name ('Action, Overdue'). The ruling: the published file, the PDF
(printed from that file) and the Word copy NEVER leave the status as a tooltip: the file shows the status as a small WORD beside the
icon, and the Word copy carries it as a word in its Status column. A real browser, a real server, fictional rows.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from _paths import TOOLS

sys.path.insert(0, str(TOOLS))
from clark import page, publish  # noqa: E402
from test_item_rows import AS_AT, fill  # noqa: E402
from test_report_editor import EMPTY_BRANDING, Pg  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402

LONG = "Confirm the full migration approach with every supplier and every site lead before the freeze window opens " * 3
SOON = "Send the supplier pack"                      # due 30-10-2026: two days after the publish date, so Due soon in the file


def fill_more(store):
    with store.step("dashboard", USER) as st:
        st.create("actions", {"project": "ABC", "description": LONG.strip(), "owner": "Omar Reid", "due_date": "2026-11-20",
                              "raised": "2026-10-01", "client_message": LONG.strip(), "source": "demo"})
        st.create("actions", {"project": "ABC", "description": SOON, "owner": "Sara Khan", "due_date": "2026-10-30",
                              "raised": "2026-10-01", "client_message": SOON, "source": "demo"})


# One row's parts, as drawn: the text and the box of each column.
ROWS = r"""[...document.querySelectorAll('[data-type=%s] .wl-row')].map(r => {
  const q = (s) => r.querySelector(s), box = (e) => { if (!e) return null; const b = e.getBoundingClientRect(); return {x: b.x, w: b.width, h: b.height}; };
  const ico = q('.ico'), title = q('.wl-title'), nm = q('.c-owner .nm'), prio = q('.c-prio'), id = q('.c-id');
  return {id: r.dataset.id, h: r.getBoundingClientRect().height, letter: ico && ico.textContent.trim(), cls: ico && ico.className, aria: ico && ico.getAttribute('aria-label'),
    tip: (ico && ico.dataset.tip) || (q('[data-tip]') && q('[data-tip]').dataset.tip), tab: ico && ico.tabIndex, word: (q('.ico-w') || {}).textContent || '',
    pills: r.querySelectorAll('.pill').length, title: title && title.textContent.trim(), titleAttr: title && title.getAttribute('title'),
    cut: title && title.scrollWidth > title.clientWidth + 1, tov: title && getComputedStyle(title).textOverflow, tws: title && getComputedStyle(title).whiteSpace,
    boxes: [ico, title, q('.c-owner'), q('.c-date'), prio, id].map(box), nameShown: !!nm && nm.getBoundingClientRect().width > 3 && getComputedStyle(nm).clip !== 'rect(0px, 0px, 0px, 0px)',
    avatar: !!q('.c-owner .av'), prioShown: !!prio && prio.getBoundingClientRect().width > 3 && getComputedStyle(prio).visibility !== 'hidden' && getComputedStyle(prio).display !== 'none',
    idWs: id && getComputedStyle(id).whiteSpace, idH: id && id.getBoundingClientRect().height, late: (q('.c-prio') || {}).textContent || ''};
})"""
HEADS = "[...document.querySelectorAll('[data-type=%s] .wl-head')].map(h => [...h.children].map(c => c.textContent.trim()))"
WORD_SHOWN = r"""(() => { const e = document.querySelector('.wl-row[data-id="' + %s + '"] .ico-w'); if (!e) return false; const b = e.getBoundingClientRect(), c = getComputedStyle(e);
  return b.width > 4 && b.height > 4 && c.display !== 'none' && c.visibility === 'visible'; })()"""
LISTS_FIT = "[...document.querySelectorAll('.irows')].every(u => u.scrollWidth <= u.clientWidth + 1 && [...u.children].every(r => r.getBoundingClientRect().right <= innerWidth + 1))"
FITS = "document.documentElement.scrollWidth <= document.documentElement.clientWidth"


def width(cdp, sid, w):
    cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        fill(self.store)
        fill_more(self.store)

    def served(self):
        s = Running(data_for=self.store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.addCleanup(s.close)
        return s

    def published(self):
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        return Path(publish.publish(self.store, "ABC", folder, by_user=USER, now=AS_AT, branding=EMPTY_BRANDING)["path"])


class OneLineInView(Base):
    def test_one_line_a_tinted_letter_for_the_kind_and_a_colour_for_the_status(self):
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.served().port)
            p.ready()
            width(cdp, p.sid, 1400)
            actions, raid, decisions = (p.js(ROWS % t) for t in ("actions", "raid", "decisions"))
            for rows in (actions, raid, decisions):
                for r in rows:
                    self.assertLess(r["h"], 46, f"{r['id']} is ONE line, not a stack: {r['h']} px")
                    self.assertEqual(r["pills"], 0, "the status pill is gone")
                    xs = [b["x"] for b in r["boxes"]]
                    self.assertEqual(xs, sorted(xs), f"{r['id']}: icon, title, owner, date, priority, id run left to right")
            self.assertEqual({r["letter"] for r in actions}, {"A"})
            self.assertEqual([r["letter"] for r in raid], ["R", "I"])
            self.assertEqual([r["letter"] for r in decisions], ["D"])
            first = actions[0]
            self.assertIn("r", first["cls"].split(), "an Overdue action is red")
            self.assertEqual(first["aria"], "Action, Overdue")
            self.assertEqual(first["tip"], "Action · Overdue")
            self.assertEqual(first["tab"], 0, "the icon takes keyboard focus, so the tooltip shows on focus too")
            self.assertEqual((raid[0]["aria"], raid[0]["tip"]), ("Risk, Red, Urgent, Overdue", "Risk · Red · Urgent · Overdue"))
            self.assertIn("r", raid[0]["cls"].split())
            self.assertEqual(raid[1]["aria"], "Issue, Green")
            self.assertIn("g", raid[1]["cls"].split())
            self.assertEqual(decisions[0]["aria"], "Decision, Pending")
            self.assertRegex(first["late"], r"^\d+ d late$", "the priority column says 'N d late' on a late action")
            self.assertIn("Urgent", raid[0]["late"])

    def test_both_cards_have_the_same_columns_and_one_header_row_each(self):
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.served().port)
            p.ready()
            width(cdp, p.sid, 1400)
            heads = {t: p.js(HEADS % t) for t in ("raid", "actions")}
            self.assertEqual(heads["raid"], [["Status", "Title", "Owner", "Review by", "Priority", "Id"]])
            self.assertEqual(heads["actions"], [["Status", "Title", "Owner", "Due", "Priority", "Id"]])
            xs = {t: [b["x"] for b in p.js(ROWS % t)[0]["boxes"]] for t in ("raid", "actions")}
            self.assertEqual(xs["raid"][1:], xs["actions"][1:], "the same columns in both cards, at the same places")

    def test_a_long_title_is_cut_with_dots_and_its_title_attribute_holds_all_of_it(self):
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.served().port)
            p.ready()
            width(cdp, p.sid, 1400)
            row = next(r for r in p.js(ROWS % "actions") if r["title"].startswith("Confirm the full"))
            self.assertTrue(row["cut"], "a title too long for its column is cut")
            self.assertEqual((row["tov"], row["tws"]), ("ellipsis", "nowrap"))
            self.assertEqual(row["titleAttr"], LONG.strip())
            self.assertLess(row["h"], 46)
            p.js("document.querySelector('[data-type=actions] .wl-row[data-kind=action] .wl-title').click()")
            self.assertTrue(wait(lambda: p.js("!!document.querySelector('.peek, [data-peek]')")), "a click opens the peek")

    def test_narrow_the_owner_name_drops_to_the_avatar_first_then_the_priority_and_the_id_and_title_never_wrap(self):
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.served().port)
            p.ready()
            for w, name, prio in ((1400, True, True), (900, False, True)):
                width(cdp, p.sid, w)
                for t in ("raid", "actions"):
                    for r in p.js(ROWS % t):
                        self.assertEqual((r["nameShown"], r["prioShown"]), (name, prio), f"{r['id']} at {w}")
                        self.assertTrue(r["avatar"], f"{r['id']} keeps the avatar at {w}")
                        self.assertEqual((r["tws"], r["idWs"]), ("nowrap", "nowrap"), f"id and title never wrap at {w}")
                        self.assertLess(r["idH"], 30, f"{r['id']} id on one line at {w}")
                        self.assertLess(r["h"], 46, f"{r['id']} one line at {w}")
                self.assertTrue(wait(lambda: p.js(FITS)), f"nothing pushes the page sideways at {w}")


class OneLineInEdit(Base):
    def test_edit_keeps_every_part_editable_on_one_line(self):
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.served().port)
            p.ready()
            width(cdp, p.sid, 1400)
            p.edit()
            for t in ("raid", "actions"):
                rows = p.js(ROWS % t)
                self.assertTrue(all(r["h"] < 52 for r in rows), f"{t}: one line in Edit: {[r['h'] for r in rows]}")
                self.assertTrue(all(r["pills"] == 0 for r in rows))
            cells = "[...document.querySelectorAll('[data-type=actions] .wl-row[data-id]')][0].querySelectorAll('.cell-pick')"
            self.assertEqual(p.js(f"[...{cells}].map(c => c.dataset.cell.split(':')[1])"), ["status", "owner", "due"])
            self.assertEqual(p.js(f"{cells}[0].querySelectorAll('.ico').length"), 1, "the icon IS the status control")
            self.assertTrue(p.js(f"/Action · Overdue/.test({cells}[0].dataset.tip)"), "and it carries the tooltip in Edit too")
            self.assertEqual(p.js("document.querySelectorAll('[data-type=actions] .wl-row [data-ce]').length > 0"), True, "the wording is still editable")
            self.assertEqual(p.js("[...document.querySelectorAll('[data-type=raid] .wl-row')][0].querySelectorAll('.cell-pick').length"), 4, "status, owner, date and priority")
            self.assertEqual(p.js("document.querySelectorAll('[data-type=actions] .wl-head').length"), 1)
            p.js(f"{cells}[0].click()")
            self.assertTrue(wait(lambda: p.js("!!document.querySelector('.menu, [role=menu]')")), "a click on the icon opens the status picker")


class PublishedFileCarriesTheWord(Base):
    def test_the_published_file_shows_the_status_as_a_word_beside_the_icon_never_a_tooltip_alone(self):
        path = self.published()
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("ZQ-HIDDEN", text)
        with chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.wl-row').length > 0", sid)))
            for w in (1400, 900):
                width(cdp, sid, w)
                words = {}
                for t in ("actions", "raid", "decisions"):
                    for r in cdp.js(ROWS % t, sid):
                        words[r["id"]] = r["word"]
                        shown = cdp.js(WORD_SHOWN % json.dumps(r["id"]), sid)
                        self.assertTrue(shown, f"{r['id']}: the status word is visible text at {w}, not a tooltip")
                        self.assertLess(r["h"], 60, f"{r['id']} stays compact at {w}")
                    self.assertEqual(cdp.js(HEADS % t, sid)[0][0], "Status", "the file's header names the icon column")
                self.assertEqual(sorted(set(words.values())), ["Due soon", "Green", "On track", "Overdue", "Pending", "Red"], words)
                self.assertTrue(cdp.js(LISTS_FIT, sid), f"the lists fit their cards at {w}")    
            rows = {r["id"]: r for t in ("actions", "raid") for r in cdp.js(ROWS % t, sid)}
            by_text = {r["title"]: r for r in rows.values()}
            self.assertEqual(by_text["Cut-over plan to be agreed"]["word"], "Overdue")
            self.assertIn("r", by_text["Cut-over plan to be agreed"]["cls"].split())
            self.assertEqual(by_text[SOON]["word"], "Due soon")
            self.assertIn("a", by_text[SOON]["cls"].split())
            self.assertEqual(by_text["Training room booked for November"]["word"], "On track")
            self.assertIn("g", by_text["Training room booked for November"]["cls"].split())
            self.assertEqual(by_text["Supplier delivery may slip"]["word"], "Red")
            self.assertEqual(by_text["Cut-over plan to be agreed"]["aria"], "Action, Overdue", "and the accessible name is kept")
            self.assertEqual(cdp.js("document.querySelectorAll('[data-type=actions] .pill, [data-type=raid] .pill').length", sid), 0)
            self.assertEqual(cdp.js("document.querySelectorAll('.wl-id').length", sid), 0, "a file draws no item number")
            self.assertNotRegex(cdp.js("document.querySelector('[data-type=actions]').innerText", sid), r"days? late|\d d late", "a file shows dates, not a count read on the publish day")


PUB_ROWS = r"""[...document.querySelectorAll('[data-type=actions] .wl-row, [data-type=raid] .wl-row')].map(r => ({id: r.dataset.id, text: r.innerText.replace(/\s+/g, ' ').trim(),
  title: r.querySelector('.wl-title').textContent.trim(), word: ((r.querySelector('.ico-w') || {}).textContent || '').trim()}))"""
EXPECT = {"Cut-over plan to be agreed": "Overdue", SOON: "Due soon", "Training room booked for November": "On track",
          "Supplier delivery may slip": "Red", "Mid-rated supplier risk": "Amber", "Some test data is missing": "Green", "Urgent site risk": "Red"}


class StatusWordInTheFileThePdfAndWord(Base):
    """Row 1021 reader: the word itself, as visible text, in the published file, in the page the PDF is printed from, and the same word in the Word copy."""

    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            st.create("raid", {"project": "ABC", "type": "Risk", "description": "Mid", "owner": "Mia Hale", "due_date": "2026-11-20",
                               "impact": "Medium", "likelihood": "Medium", "raised": "2026-10-01", "client_message": "Mid-rated supplier risk", "source": "demo"})
            st.create("raid", {"project": "ABC", "type": "Risk", "description": "Urgent", "owner": "Mia Hale", "due_date": "2026-11-20",
                               "priority": "Urgent", "impact": "High", "likelihood": "High", "raised": "2026-10-01", "client_message": "Urgent site risk", "source": "demo"})

    def rows_in(self, printing):
        path = self.published()
        with chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.wl-row').length > 0", sid)))
            if printing:      # as the browser prints it: print media, and the beforeprint event Ctrl+P sends
                cdp.call("Emulation.setEmulatedMedia", {"media": "print"}, sid)
                cdp.js("window.dispatchEvent(new Event('beforeprint'))", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.print-tab')", sid)))
            rows = cdp.js(PUB_ROWS, sid)
        return {r["title"]: r for r in rows }, rows

    def check(self, printing):
        by_title, _ = self.rows_in(printing)
        for title, word in EXPECT.items():
            self.assertIn(title, by_title, title)
            r = by_title[title]
            self.assertIn(f" {word} ", f" {r['text']} ", f"{title}: the row's visible text carries {word}: {r['text']}")
            self.assertEqual(r["word"], word, title)
        return by_title

    def test_the_published_file_text_has_the_word_next_to_each_item(self):
        self.check(False)

    def test_the_page_the_pdf_is_printed_from_has_the_word_next_to_each_item(self):
        self.check(True)

    def test_the_word_copy_says_the_same_word_for_the_same_item(self):
        from clark import docx_build
        import test_docx_build as t
        by_title = self.check(False)
        blocks = t.blocks(docx_build.build(publish.select(publish.read_inputs(self.store, "ABC", AS_AT))))
        word = {}
        for b in blocks:
            if b["kind"] == "table" and b["rows"] and b["rows"][0][0] == "ID" and b["rows"][0][-1] == "Status":
                word.update({r[0]: r[-1] for r in b["rows"][1:]})
        ids = {title: r["id"] for title, r in by_title.items()}
        for title, expected in EXPECT.items():
            self.assertEqual(word.get(ids[title]), expected, f"{title}: the Word copy's word is the page's word")


class WordCopyCarriesTheWord(unittest.TestCase):
    def test_the_word_copy_says_the_status_in_words_in_its_tables(self):
        import test_docx_build as t
        plant = t.fx.load()
        plant["as_at"] = "2026-12-01"
        blocks = t.blocks(t.docx_build.build(t.published(plant)))
        tables = {tuple(b["rows"][0]): b["rows"][1:] for b in blocks if b["kind"] == "table" and b["rows"]}
        actions = next(v for k, v in tables.items() if k[:2] == ("ID", "Action"))
        raid = next(v for k, v in tables.items() if k[:2] == ("ID", "Type"))
        self.assertTrue(actions and raid)
        for row in actions:
            self.assertTrue(row[-1].strip(), "an action's Status is a word in the Word copy")
            self.assertIn("(overdue)", row[4], "a late action says overdue in words")
        for row in raid:
            self.assertTrue(row[-1].strip() and row[4].strip(), "a risk's Status and Priority are words in the Word copy")


if __name__ == "__main__":
    unittest.main()
