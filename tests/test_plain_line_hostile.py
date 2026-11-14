"""Row 1005, hostile words: plainLine.js and the two places that save its result (the Movement form's Who agreed it, Reason and
Source, and a RAID card's Own words).

Run: python3 dev/run_tests.py test_plain_line_hostile
Chrome is required: these tests fail, never skip, without it (the repo has no Node, so the logic runs in headless Chrome, as
test_safety_logic.py does). Fixture data is made up. Page tests run at 1400 and 900 pixels wide, in light and dark.
"""
import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from _paths import SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import esbuild  # noqa: E402

from test_movement_page import Base as MovementBase, GO_LIVE  # noqa: E402
from test_server import chrome, wait  # noqa: E402
from test_tpl_raid3 import PageSide  # noqa: E402
from test_report_editor import Base as ReportBase  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
_CACHE = {}


def logic_url():
    if "url" not in _CACHE:
        with tempfile.TemporaryDirectory() as tmp:
            entry = Path(tmp) / "entry.js"
            entry.write_text('import { plainLine } from %s;\nwindow.plainLine = plainLine;\n' % json.dumps(str(PAGE_SRC / "logic" / "plainLine.js")), encoding="utf-8")
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}", str(entry), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        html = f'<!doctype html><html><head><meta charset="utf-8"><title>t</title></head><body><script>{script}</script></body></html>'
        _CACHE["url"] = "data:text/html;base64," + base64.b64encode(html.encode("utf-8")).decode("ascii")
    return _CACHE["url"]


class PlainLine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = chrome()
        cls.cdp = cls.ctx.__enter__()
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Page.navigate", {"url": logic_url()}, cls.sid)
        assert wait(lambda: cls.cdp.js("typeof window.plainLine === 'function'", cls.sid)), "the bundle ran"

    @classmethod
    def tearDownClass(cls):
        cls.ctx.__exit__(None, None, None)

    def pl(self, value):
        got = self.cdp.js("JSON.stringify(window.plainLine(%s))" % json.dumps(value), self.sid)
        return json.loads(got)

    def test_a_script_tag_in_the_html_is_dropped_as_a_tag_and_never_kept_as_one(self):
        got = self.pl("<p>hi <script>alert(1)</script>there</p>")
        self.assertEqual(got, "hi alert(1)there")
        self.assertNotIn("<", got)

    def test_an_escaped_script_tag_stays_text_and_is_not_decoded_twice(self):
        self.assertEqual(self.pl("<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>"), "<script>alert(1)</script>")
        self.assertEqual(self.pl("<p>&amp;lt;b&amp;gt;</p>"), "&lt;b&gt;", "one level of escaping is undone, never two")

    def test_a_tag_split_to_get_past_a_cleaner_leaves_no_whole_script_tag(self):
        got = self.pl("<p><scr<script>ipt>alert(1)</scr</script>ipt></p>")
        self.assertNotIn("<script", got.lower())
        self.assertNotIn("</script", got.lower())

    def test_an_attribute_laden_tag_is_dropped_whole(self):
        self.assertEqual(self.pl('<p onclick="x()">a</p><img src=x onerror=alert(1)><p>b</p>'), "a b")

    def test_a_huge_string_is_kept_whole_and_quickly(self):
        big = "w" * 1000000
        t0 = self.cdp.js("performance.now()", self.sid)
        n = self.cdp.js("window.plainLine(%s).length" % json.dumps("<p>" + big + "</p>"), self.sid)
        t1 = self.cdp.js("performance.now()", self.sid)
        self.assertEqual(n, 1000000)
        self.assertLess(t1 - t0, 5000)

    def test_a_huge_run_of_spaces_and_tags_does_not_hang(self):
        n = self.cdp.js("window.plainLine('<p>' + ' '.repeat(300000) + '</p>'.repeat(1) + '<p></p>'.repeat(50000) + '<p>x</p>').length", self.sid)
        self.assertEqual(n, 1)

    def test_only_whitespace_becomes_nothing_in_every_shape(self):
        for v in ("", "   ", "\n\t \r\n", "<p></p>", "<p> </p><p> </p>", "<p>&nbsp;</p>", "<p><br></p>", "<p> 　 </p>", "<ul><li></li></ul>"):
            self.assertEqual(self.pl(v), "", repr(v))

    def test_paragraphs_lists_breaks_and_headings_are_joined_by_one_space(self):
        self.assertEqual(self.pl("<p>one</p><p>two</p><p>three</p>"), "one two three")
        self.assertEqual(self.pl("<p>one</p>\n\n\n<p>two</p>"), "one two")
        self.assertEqual(self.pl("<ul><li>a</li><li>b</li></ul><h2>c</h2><blockquote>d</blockquote>"), "a b c d")
        self.assertEqual(self.pl("<p>a<br>b<br/>c</p>"), "a b c")
        self.assertEqual(self.pl("<p>a</p><p></p><p></p><p>b</p>"), "a b")

    def test_an_old_plain_text_with_line_breaks_is_one_line_too(self):
        self.assertEqual(self.pl("first\r\nsecond\n\n\nthird\tfourth"), "first second third fourth")
        self.assertEqual(self.pl("1 < 2 and 3 > 2"), "1 < 2 and 3 > 2", "a bare angle bracket in an old text is kept")
        self.assertEqual(self.pl("a <b>bold</b> old text"), "a <b>bold</b> old text", "old plain text is not read as markup")

    def test_no_space_is_left_at_either_end_of_an_old_text_or_of_html(self):
        for v in ("x  ", "  x", "\n x \t\n", "x\u00a0", "\u00a0x", "<p>x</p>  ", "  <p>x</p>\n"):
            self.assertEqual(self.pl(v), "x", repr(v))

    def test_entities_are_undone_once_and_the_spaces_made_single(self):
        self.assertEqual(self.pl("<p>Fish &amp; chips&nbsp;&nbsp;and   more</p>"), "Fish & chips and more")
        self.assertEqual(self.pl("<p>&quot;q&quot; &#39;s&#39; &copy;</p>"), "&quot;q&quot; &#39;s&#39; &copy;", "only the entities the editor writes are undone")

    def test_emoji_and_joined_emoji_are_kept_whole(self):
        fam = "\U0001F468‍\U0001F469‍\U0001F467"
        got = self.pl("<p>ok %s \U0001F680 é́ שלום</p>" % fam)
        self.assertEqual(got, "ok %s \U0001F680 é́ שלום" % fam)
        self.assertEqual(self.cdp.js("Array.from(window.plainLine(%s)).length" % json.dumps("<p>" + "\U0001F680" * 400 + "</p>"), self.sid), 400)

    def test_400_and_401_characters_come_back_at_exactly_their_length(self):
        for n in (399, 400, 401):
            got = self.pl("<p>" + "x" * n + "</p>")
            self.assertEqual(len(got), n)
        self.assertEqual(self.cdp.js("Array.from(window.plainLine(%s)).length" % json.dumps("<p>" + "\U0001F600" * 401 + "</p>"), self.sid), 401,
                         "counted in characters, not in UTF-16 units")

    def test_paragraph_joins_that_cross_the_limit_count_the_joining_space(self):
        got = self.pl("<p>" + "a" * 200 + "</p><p>" + "b" * 200 + "</p>")
        self.assertEqual(len(got), 401)

    def test_nothing_and_not_text_give_nothing_or_their_text(self):
        self.assertEqual(self.pl(None), "")
        self.assertEqual(self.cdp.js("window.plainLine(undefined)", self.sid), "")
        self.assertEqual(self.cdp.js("window.plainLine(42)", self.sid), "42")
        self.assertEqual(self.cdp.js("window.plainLine({toString(){return '<p>x</p><p>y</p>'}})", self.sid), "x y")

    def test_the_result_is_stable_when_run_again(self):
        for v in ("<p>a</p><p>b &amp; c</p>", "  x\n y ", "<p>x</p><p>y</p>"):
            once = self.pl(v)
            self.assertEqual(self.pl(once), once, v)

    def test_a_leading_blank_before_the_first_tag_is_still_read_as_the_editors_html(self):
        self.assertEqual(self.pl("\n  <p>a</p><p>b</p>"), "a b")


class MovementHostile(MovementBase):
    def fill_html(self, p, k, html):
        box = ".mvm-f[data-f=%s] .ProseMirror" % json.dumps(k)
        p.js("document.getElementById(%s).click()" % json.dumps("mv-" + k))
        p.until("!!document.querySelector(%s)" % json.dumps(box), "the editor opened")
        p.js("document.querySelector(%s).cxed.editor.commands.setContent(%s)" % (json.dumps(box), json.dumps(html)))
        try:
            p.until("(function(){var b = document.querySelector(%s); if (b) { var h = document.getElementById('mv-form-h'); h.tabIndex = -1; h.focus(); } return !b;})()" % json.dumps(box), "the editor closed", 20)
        except AssertionError:
            self.fail("editor %s stayed open: %s" % (k, p.js("JSON.stringify([document.activeElement.className, document.querySelectorAll('.ProseMirror').length, [...document.querySelectorAll('.mvm-f')].map(f => f.dataset.f + ':' + (f.querySelector('.ProseMirror') ? 'open' : 'view')), (document.querySelector('.mvm-problems')||{}).textContent])")))

    def set_date(self, p, text):
        p.js("(function(){var e = document.getElementById('mv-to'); e.value = %s; e.dispatchEvent(new Event('input', {bubbles: true}));})()" % json.dumps(text))

    def open_form(self, p):
        self.open_movement(p)
        p.js("document.querySelector('#mv-move').click()")
        p.until("!!document.querySelector('.mvm-form')", "the form opened")
        p.until("document.activeElement.id === 'mv-to'", "focus went to the first field")      # the form takes it after a frame: later, it would pull it out of an editor

    def test_hostile_words_are_sent_as_one_plain_line_and_drawn_as_text(self):
        self.hostile(1400, "light")

    def test_hostile_words_are_sent_as_one_plain_line_and_drawn_as_text_at_900_in_the_dark(self):
        self.hostile(900, "dark")

    def hostile(self, width, theme):
        long_name = ("Pat " + "Example-Longname " * 30).strip()          # too long for the server: refused, the form stays
        short_name = ("Pat " + "Example " * 15).strip()
        with chrome() as cdp:
            p = self.visit(cdp, width=width, theme=theme)
            self.open_form(p)
            self.set_date(p, "01-01-2099")
            self.fill_html(p, "who", "<p>%s</p><p>second paragraph</p>" % long_name)
            self.fill_html(p, "reason", "<p>&lt;script&gt;window.__x=1&lt;/script&gt; &amp; \U0001F680</p>")
            self.fill_html(p, "source", "<p>line one</p><p>line two</p>")
            self.assertIn("second paragraph", p.js("document.querySelector('.mvm-form').textContent"))
            self.assertEqual(p.js("!!window.__x || document.querySelectorAll('.mvm-form script').length"), 0, "no script ran or was made")
            self.assertEqual(p.js("document.documentElement.scrollWidth <= window.innerWidth"), True, "no sideways scroll at %d" % width)
            p.js("document.querySelector('#mv-go').click()")
            p.until("!!document.querySelector('.mvm-problems p')", "the server refused the long name")
            self.assertEqual(self.sent[-1][1]["rebaseline"]["agreed_with"], long_name + " second paragraph", "sent as one line")
            self.assertEqual(self.row(GO_LIVE)["baseline_date"], "2020-01-10", "nothing was written")
            self.assertEqual(p.js("!!document.querySelector('.mvm-form')"), True, "the form stays")
            self.assertEqual(p.js("document.documentElement.scrollWidth <= window.innerWidth"), True)
            self.fill_html(p, "who", "<p>%s</p><p>second paragraph</p>" % short_name)
            p.js("document.querySelector('#mv-go').click()")
            p.until("!document.querySelector('.mvm-form')", "the form closed")
            rb = self.sent[-1][1]["rebaseline"]
            self.assertEqual(rb["agreed_with"], short_name + " second paragraph")
            self.assertEqual(rb["reason"], "<script>window.__x=1</script> & \U0001F680")
            self.assertEqual(rb["source"], "line one line two")
            for v in rb.values():
                self.assertNotIn("\n", v)
            self.assertEqual(p.js("!!window.__x"), False)
            self.assertEqual(p.js("document.querySelectorAll('#movement script, .mvm-list script').length"), 0)

    def test_words_of_only_spaces_count_as_not_given(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.open_form(p)
            self.set_date(p, "01-01-2099")
            self.fill_html(p, "who", "<p> </p><p>&nbsp;</p>")
            self.fill_html(p, "reason", "<p><br></p>")
            self.fill_html(p, "source", "<p>  　</p>")
            before = len(self.sent)
            p.js("document.querySelector('#mv-go').click()")
            p.until("document.querySelectorAll('.mvm-problems p').length === 3", "all three are missing")
            self.assertEqual(len(self.sent), before, "nothing is sent")
            self.assertEqual(self.row(GO_LIVE)["baseline_date"], "2020-01-10")

    def test_a_400_and_a_401_character_reason_are_both_kept_whole_by_the_form(self):
        with chrome() as cdp:
            p = self.visit(cdp, width=900, theme="dark")
            self.open_form(p)
            for n in (400, 401):
                self.fill_html(p, "reason", "<p>" + "r" * n + "</p>")
                try:
                    p.until("(document.querySelector('.mvm-f[data-f=reason] .sec-body') || {textContent: ''}).textContent.length === %d" % n, "drawn")
                except AssertionError:
                    self.fail("%d: %s" % (n, p.js("document.querySelector('.mvm-f[data-f=reason]').outerHTML.slice(0, 400)")))


class RaidHostile(ReportBase):
    """The Own words of a card: more than the limit is not saved, and what is saved is one plain line."""
    seed = PageSide.seed
    fill = PageSide.fill
    card_ids = PageSide.card_ids
    wait_for = PageSide.wait_for
    set_select = PageSide.set_select
    arr = PageSide.arr
    TYPE, SIZE = "raid3", 3

    def stored(self, sec):
        return json.loads(next(r for r in self.store.read("report_sections", "ABC") if r["id"] == sec)["body"])["cards"]

    def own(self, p, sec, html, ctrl_enter=True, closes=False):
        box = f"[data-id={json.dumps(sec)}] .rce-f .ProseMirror"
        view = f"[data-id={json.dumps(sec)}] .rce-f .rt-view"
        p.until(f"!!document.querySelector({json.dumps(view)}) || !!document.querySelector({json.dumps(box)})", "own words field")
        if not p.js(f"!!document.querySelector({json.dumps(box)})"):
            p.js(f"document.querySelector({json.dumps(view)}).click()")
            p.until(f"!!document.querySelector({json.dumps(box)})", "the editor opened")
        p.js(f"(function(){{ const b = document.querySelector({json.dumps(box)}); b.focus(); b.cxed.editor.commands.setContent({json.dumps(html)}); }})()")
        p.key("Enter", modifiers=2, code="Enter", vk=13)
        if closes:
            # The store has the words before the editor closes (it closes when the reply arrives). The next step must open a new editor,
            # not type into this closing one, whose Ctrl+Enter is ignored: that dropped the words and failed the later wait_for.
            p.until(f"!document.querySelector({json.dumps(box)}) && !!document.querySelector({json.dumps(view)})", "the editor closed after saving")

    def test_own_words_limit_script_whitespace_and_joins(self):
        # tests/test_tpl_raid3.py drives the same page the same way
        ids = self.seed()
        sec = ids["sec"]
        self.fill(ids, {"id": ids["risk"], "source": "own", "own": "old"})
        for width, theme in ((1400, "light"), (900, "dark")):
            with chrome() as cdp:
                cdp.FOCUS_EMULATION = False
                p = self.visit(cdp)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.js(f"document.documentElement.dataset.theme = '{theme}'")
                p.edit()
                p.until(f"!!document.querySelector('[data-id={json.dumps(sec)}] .rce-f .rt-view')", "own words drawn")
                # 400 characters in two paragraphs, joined by one space: exactly the limit, saved
                self.own(p, sec, "<p>" + "a" * 199 + "</p><p>" + "b" * 200 + "</p>", closes=True)
                want = "a" * 199 + " " + "b" * 200
                self.assertTrue(self.wait_for(lambda: self.stored(sec)[0].get("own") == want), "400 characters are saved")
                n = len([s for s in self.sent if s[0] == "change"])
                # 401: not saved, no change sent, the old words stay
                self.own(p, sec, "<p>" + "c" * 401 + "</p>")
                p.js("new Promise(r => setTimeout(r, 600))")
                self.assertEqual(self.stored(sec)[0].get("own"), want, "401 characters are not saved")
                self.assertEqual(len([s for s in self.sent if s[0] == "change"]), n, "and nothing is sent")
                # a script tag typed as words is stored as text and drawn as text
                self.own(p, sec, "<p>&lt;script&gt;window.__r=1&lt;/script&gt; \U0001F680</p>", closes=True)
                self.assertTrue(self.wait_for(lambda: self.stored(sec)[0].get("own") == "<script>window.__r=1</script> \U0001F680"))
                self.assertEqual(p.js("!!window.__r || document.querySelectorAll('[data-id=%s] script').length" % json.dumps(sec)), 0)
                self.assertEqual(p.js("document.documentElement.scrollWidth <= window.innerWidth"), True)
                # only spaces: saved as empty
                self.own(p, sec, "<p> </p><p>&nbsp;</p>", closes=True)
                self.assertTrue(self.wait_for(lambda: self.stored(sec) == [{"id": ids["risk"], "source": "own"}]), "only spaces are saved as no words (the store leaves an empty one out)")
                for card in self.stored(sec):
                    self.assertNotIn("\n", card.get("own", ""))
            # the next width starts from the first words again
            self.fill(ids, {"id": ids["risk"], "source": "own", "own": "old"})

    def test_an_empty_own_words_card_takes_a_long_line_of_words_without_sideways_scroll(self):
        ids = self.seed()
        sec = ids["sec"]
        self.fill(ids, {"id": ids["risk"], "source": "own", "own": ""})
        with chrome() as cdp:
            cdp.FOCUS_EMULATION = False
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector('[data-id={json.dumps(sec)}] .rce-f .rt-view')", "own words drawn")
            self.assertEqual(self.stored(sec)[0].get("own", ""), "")
            self.own(p, sec, "<p>" + " ".join(["word"] * 80) + "</p>")
            self.assertTrue(self.wait_for(lambda: self.stored(sec)[0].get("own") == " ".join(["word"] * 80)))
            self.assertEqual(p.js("document.documentElement.scrollWidth <= window.innerWidth"), True)
