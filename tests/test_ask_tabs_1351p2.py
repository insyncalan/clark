"""Row 1351 part 2 (mock-up A8): the ask clark page tab pills and the Model line, measured in Chrome in Classic at 1400, and the page padding at 900.

Run: python3 dev/run_tests.py test_ask_tabs_1351p2
Pins: pill padding 5px 14px, radius 999, 13.5px type, 29 px high, 6 px between pills; the chosen pill is the brand-blue token with the on-brand
token text at weight 600; "Settings for" is 12.5px, muted, 6 px margin to its right; the Model line is the model name, the existing production
note and a Change link with a dashed underline; at 900 the page padding is 6px 16px 30px. Cards is unmaintained and is not pinned here. Chrome is required."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from _editor_checks import for_project
from test_ai_connect import FakeChatGPT, FakeClaude
from test_ask_settings import make_db, service
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import ai_connect, page

NOTE = "Connections and the model are yours, not this project's. They are the same in every project."
TOKEN = "(v => { const e = document.createElement('i'); e.style.color = 'var(' + v + ')'; document.body.appendChild(e); const c = getComputedStyle(e).color; e.remove(); return c; })"
READ = """(() => {
  const css = (e, ...ps) => { const s = getComputedStyle(e); return ps.map(p => s[p]); };
  const tabs = [...document.querySelectorAll('[data-ask-tab]')], lab = document.querySelector('#ask-tabs .ask-tabs-lab');
  const pill = t => css(t, 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'borderTopLeftRadius', 'fontSize').concat([t.getBoundingClientRect().height]);
  return {pill: tabs.map(pill), idle: css(tabs[0], 'fontWeight'), on: css(tabs[1], 'backgroundColor', 'color', 'fontWeight'),
          gap: Math.round(tabs[1].getBoundingClientRect().left - tabs[0].getBoundingClientRect().right), rowgap: getComputedStyle(document.querySelector('#ask-tabs')).columnGap,
          lab: css(lab, 'fontSize', 'color', 'marginRight'), main: getComputedStyle(document.querySelector('#main')).padding};
})()"""


class Tabs(unittest.TestCase):
    def setUp(self):
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.page_html(tempfile.mkdtemp(), theme="prototype-2.0"))
        self.addCleanup(self.s.close)
        d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, d, True)
        self.s.httpd.app_settings = service(make_db(d))
        self.s.httpd.ai_connect = ai_connect.AiConnect(d, FakeClaude(), FakeChatGPT())

    def show(self, cdp, width):
        sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
        js = lambda e: cdp.js(e, sid)          # noqa: E731
        self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-model]')"), 30), "the tabs and the Model line are on the page")
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        js("document.querySelectorAll('[data-ask-tab]').forEach(b => { b.style.transition = 'none'; })")
        return js

    def test_the_pills_and_the_label_at_1400(self):
        with chrome() as cdp:
            js = self.show(cdp, 1400)
            got = js(READ)
            for p in got["pill"]:
                self.assertEqual(p, ["5px", "14px", "5px", "14px", "999px", "13.5px", 29], "pill padding, radius, font size, height")
            self.assertEqual(got["gap"], 6, "6 px between the pills")
            self.assertEqual(got["rowgap"], "6px")
            self.assertEqual(got["idle"], ["400"])
            self.assertEqual(got["on"], [js(TOKEN + "('--brand-blue')"), js(TOKEN + "('--text-on-brand')"), "600"], "chosen pill: --brand-blue fill, --text-on-brand text, weight 600")
            self.assertEqual(got["lab"], ["12.5px", js(TOKEN + "('--text-muted')"), "6px"], "Settings for: 12.5px, muted, margin-right 6")

    def test_the_model_line_keeps_the_production_words_and_the_change_link_is_dashed(self):
        with chrome() as cdp:
            js = self.show(cdp, 1400)
            self.assertEqual(js("document.querySelector('[data-ask-model]').innerText"), "Claude Sonnet", "the model name")
            self.assertEqual(js("document.querySelector('#ask-used-all .ask-model-note').innerText"), NOTE, "the existing production note, unchanged")
            self.assertEqual(js("document.querySelector('#ask-used-all .ask-model-label').innerText"), "Model", "row label")
            self.assertEqual(js("document.querySelector('#ask-used-all .ask-model-same').innerText"), "Same for every project.", "approved words, logged in NEW-WORDS")
            self.assertTrue(js("(() => { const r = document.querySelector('#ask-used-all .ask-model').getBoundingClientRect(), n = document.querySelector('#ask-used-all .ask-model-note').getBoundingClientRect(); return n.top >= r.bottom; })()"), "the production note sits under the row")
            self.assertEqual(js("(() => { const s = getComputedStyle(document.querySelector('[data-ask-goall]')); return [s.borderBottomStyle, s.borderBottomWidth, s.backgroundColor, s.paddingLeft]; })()"),
                             ["dashed", "1px", "rgba(0, 0, 0, 0)", "0px"], "Change is a link with a dashed underline, not a button")
            self.assertEqual(js("document.querySelector('[data-ask-goall]').innerText"), "Change")
            self.assertEqual(js("[...document.querySelectorAll('#ask-used-all .ask-model > *')].map(e => e.className.split(' ').pop())"), ["ask-model-text", "ask-model-name", "ask-model-change"], "label block, name, link in that order")
            self.assertEqual(js("[...document.querySelectorAll('#ask-used-all .ask-model-text > *')].map(e => e.className.split(' ').pop())"), ["ask-model-label", "ask-model-same"], "label then the same-line")
            self.assertEqual(js("(() => { const q = x => getComputedStyle(document.querySelector(x)); const l = q('.ask-model-label'), m = q('.ask-model-same'), n = q('.ask-model-name'), t = q('#ask-used-all .ask-model-note'); const lb = document.querySelector('.ask-model-label').getBoundingClientRect(), sb = document.querySelector('.ask-model-same').getBoundingClientRect(); return [l.fontWeight, m.fontSize, m.color === n.color, n.fontWeight, t.marginTop, t.marginRight, t.marginLeft, t.marginBottom, sb.top >= lb.bottom - 1]; })()"),
                             ["400", "13px", True, "400", "6px", "6px", "6px", "0px", True], "A8: label normal, same-line 13px muted under it, name muted normal, note margin 6px 6px 0")
            self.assertEqual(js("(() => { const q = x => getComputedStyle(document.querySelector(x)); const tx = document.querySelector('.ask-model-text').getBoundingClientRect(), nm = document.querySelector('.ask-model-name').getBoundingClientRect(), lab = document.querySelector('.ask-model-label').getBoundingClientRect(); return [q('#ask-used-all .ask-model-note').fontSize, q('.ask-model-label').color !== q('.ask-model-name').color, q('.ask-model-same').color !== q('.ask-model-label').color, tx.width > document.querySelector('#ask-used-all .ask-model').getBoundingClientRect().width / 2, tx.right <= nm.left + 1]; })()"),
                             ["13px", True, True, True, True], "A8: note 13px; label text-coloured, same-line and name muted; the text block takes the free width and the name sits after it")

    def test_cards_keeps_the_card_as_it_was(self):
        self.s.close()
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=None))
        self.addCleanup(self.s.close)
        d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, d, True)
        self.s.httpd.app_settings = service(make_db(d))
        self.s.httpd.ai_connect = ai_connect.AiConnect(d, FakeClaude(), FakeChatGPT())
        with chrome() as cdp:
            sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
            js = lambda e: cdp.js(e, sid)          # noqa: E731
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-used-all')"), 30), "the card is on the page")
            self.assertEqual(js("document.querySelector('#ask-used-all .ask-model') === null && document.querySelector('[data-ask-model]') === null"), True, "Cards: no model line")
            self.assertEqual(js("document.querySelector('#ask-used-all > p.muted').innerText"), NOTE, "Cards: the note is its own paragraph, as on main")
            self.assertEqual(js("document.querySelector('#ask-used-all .row > button.btn[data-ask-goall]').innerText"), "Change", "Cards: Change is the button, as on main")

    def test_the_page_padding_at_900(self):
        with chrome() as cdp:
            js = self.show(cdp, 900)
            self.assertTrue(wait(lambda: js(READ)["main"] == "6px 16px 30px", 10), f"page padding at 900: {js(READ)['main']}")
            js2 = self.show(cdp, 1400)
            self.assertTrue(wait(lambda: js2(READ)["main"] != "6px 16px 30px", 10), "the 900 padding does not apply at 1400")


if __name__ == "__main__":
    unittest.main()
