"""Row 1269, slice B, the published file: it inlines the Theme chosen at the moment of the publish; a file already published is unchanged
byte for byte; in Classic the Gantt tab's cover band is dropped and the sections carry the gutter rule; in Cards the file is as it was;
publish.check_brand still refuses an unembedded font and an @import under both Themes. Chrome checks at 1400 and 900, light.
Fictional data only.

Run: python3 -m unittest test_theme_published      (from tests/, with PYTHONPATH=../src:../vendor:.; needs Chrome)
"""
import hashlib
import unittest

from _demo import USER
from _publish import PublishedFile
from test_glance_page import Setup
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

from clark import page, publish

PROBE = """(() => {
  const all = document.querySelectorAll('.secs > .sec'), s = all[1] || document.querySelector('.sec'), b = all[0], c = document.createElement('header');
  c.className = 'cover'; document.body.appendChild(c);      // no published tab draws the band today: a probe band shows what the rules do to one
  const cs = s && getComputedStyle(s);
  return {sec: !!s, band_rule: b && getComputedStyle(b).borderLeftWidth, rule: cs && cs.borderLeftWidth, pad: cs && cs.paddingLeft, cover: getComputedStyle(c).display,
          theme: !!document.getElementById('theme')};
})()"""


class Base(PublishedFile, Setup):
    theme = None      # these tests set the Theme themselves (set_theme)
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            st.create("gantt_lines", {"project": "ABC", "type": "task", "name": "x", "start": "2026-11-02", "end": "2026-11-13", "health": "Green", "show": 1, "sort_order": 1})
        self.store.con.execute("UPDATE projects SET show_gantt_client = 1, show_gantt_editor = 1 WHERE code = 'ABC'")
        self.store.con.commit()

    def set_theme(self, value):
        with self.store.con:
            self.store.con.execute("UPDATE app_settings SET theme = ? WHERE id = 1", (value,))

    def file(self):
        return publish.build(self.store, "ABC", now="2026-10-28", number=1)["body"]

    def look(self, path, width, view):
        with chrome() as cdp:
            p = self.draw(cdp, path, width)
            p.until("!!document.querySelector('.top-file .tab')", "the bar drew")
            if view != "dashboard":
                p.js(f"document.querySelector('.top-file .tab[data-view=\"{view}\"]').click()")
                p.until(f"document.querySelector('.top-file .tab[aria-selected=true]').dataset.view === '{view}'", f"{view} opened")
            else:
                p.until("!!document.querySelector('.sec')", "the sections drew")
            return p.js(PROBE)


class Inlined(Base):
    def test_the_file_inlines_the_classic_theme_whatever_is_stored_and_an_old_file_is_unchanged_byte_for_byte(self):      # row 1363
        self.set_theme("classic")
        old = self.file()
        old_hash = hashlib.sha256(old).hexdigest()
        self.assertEqual(old.count(b'id="theme"'), 1)
        self.set_theme("cards")
        self.assertEqual(hashlib.sha256(self.file()).hexdigest(), old_hash, "a stored Cards value publishes the same Classic file")

    def test_nothing_in_a_written_file_reads_the_setting_when_it_is_opened(self):
        self.set_theme("classic")
        text = self.file().decode("utf-8")
        self.assertNotIn("/api/theme", text)


class Look(Base):
    def test_classic_drops_the_cover_band_and_draws_the_gutter_rule(self):
        self.set_theme("classic")
        path = self.publish()
        for width in (1400, 900):
            with self.subTest(width=width):
                dash = self.look(path, width, "dashboard")
                self.assertTrue(dash["theme"])
                self.assertEqual((dash["rule"], dash["pad"]), ("2px", "20px"), dash)      # the 2nd section keeps the gutter rule
                self.assertEqual(dash["band_rule"], "0px", dash)      # row 1311: the 1st is a band, with none
                gantt = self.look(path, width, "gantt")
                self.assertEqual(gantt["cover"], "none", gantt)


class Check(unittest.TestCase):
    """The check on a brand's tokens still refuses an unembedded font and any @import in the finished page, under either Theme."""
    def test_both_themes_refuse_a_font_by_address_and_an_import(self):
        for name in (None, "prototype-2.0"):
            base = page.page_html(view=True, theme=name)
            publish.check_brand(base)
            for bad in ("@import url(data:text/css,a);", "@font-face { font-family: X; src: url(https://example.com/x.woff2); }"):
                with self.subTest(theme=name, bad=bad[:12]), self.assertRaises(publish.PublishError):
                    publish.check_brand(base.replace("</head>", f"<style>{bad}</style></head>", 1))


if __name__ == "__main__":
    unittest.main()
