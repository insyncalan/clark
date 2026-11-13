"""Row 1115, S3: the Essentials card, first in the Settings long scroll with its chip first, in a real browser at 1400 and 900 px, light and dark.
Run: python3 dev/run_tests.py test_settings_essentials_1115

Essentials holds eight settings on the shared setting row: Your name, Appearance, Spacing, Motion, Single-key shortcuts, Backups, Publishing folder,
Asking on or off. The originals stay in their cards; each control here changes the same state. Chrome is required: these tests fail, never skip, without it."""
import unittest

from test_settings_head import Head
from test_server import chrome

WIDTHS = (1400, 900)
MODES = ("light", "dark")
NAMES = ["Your name", "Appearance", "Spacing", "Motion", "Single-key shortcuts", "Backups", "Publishing folder", "Asking on or off"]
ROWS = """[...document.querySelectorAll('#essentials .set-row')].map(r => r.querySelector('.set-row-text label').textContent)"""


# The test server has no backups to list and no asking switch, so the page's own fetch answers those routes, as test_backup_copy_focus and test_ask_settings do.
STUB = r"""(() => {
  const real = window.fetch.bind(window);
  const reply = (b) => new Response(JSON.stringify(b), { status: 200, headers: { "Content-Type": "application/json" } });
  let asking = true;
  window.fetch = (url, opts) => {
    if (String(url).startsWith("/api/ask-enabled")) {
      if (opts && opts.method === "POST") asking = JSON.parse(opts.body).enabled;
      return Promise.resolve(reply({ ok: true, ask_enabled: asking, saved: true }));
    }
    if (String(url).startsWith("/api/backups/copy-folder")) return Promise.resolve(reply({ ok: true, folder: "/tmp/essentials-copy", message: "Saved." }));
    if (String(url).startsWith("/api/backups")) return Promise.resolve(reply({ ok: true, backups: [{ name: "b1", when: "today", kind_label: "Daily", size_text: "1 KB" }], status: "Fine.", newest_ok: true, keep: 5, keep_label: "Kept", keep_help: "h",
      copy_folder: "", copy_label: "Copy my backups to", copy_help: "Help.", copy_suggestions: [] }));
    return real(url, opts);
  };
})()"""


class Essentials(Head):
    # Head's own tests belong to test_settings_head; this file borrows only its helpers
    test_C_the_title_the_help_line_and_a_chip_for_each_card_that_exists = test_C_a_click_scrolls_to_the_card_and_focuses_its_heading = None
    test_C_keyboard_tab_to_a_chip_and_enter = test_C_the_list_is_at_the_left_at_900_and_wider_and_a_row_of_chips_below_900 = test_C_text_size_and_contrast_in_light_and_dark = None

    def settings(self, cdp, w, mode):
        p = self.page(cdp)
        p.js(STUB)      # the page is on the Dashboard: Settings draws afresh, and its cards read the stand-in
        self.open_settings(p, w, mode)
        self.drawn(p)
        return p

    def drawn(self, p):
        p.until("!!document.querySelector('#essentials') && document.querySelectorAll('#essentials .set-row').length === 8 && !!document.querySelector('#ess-safety-copy-box')",
                "Essentials drew its eight rows")

    def test_S3_essentials_is_the_first_card_and_the_first_chip(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.settings(cdp, w, mode)
                    self.assertEqual(self.chips(p)[0], "Essentials")
                    self.assertEqual(p.js("document.querySelector('.set-cards > section').id"), "essentials", "the first card")
                    self.assertEqual(p.js("document.querySelector('.set-cards > section h2').textContent"), "Essentials")
                    self.assertEqual(p.js("document.querySelector('.set-nav .set-chip').getAttribute('aria-current')"), "location")
                    self.assertFalse(p.js("document.documentElement.scrollWidth > document.documentElement.clientWidth"), "no sideways scroll")

    def test_S3_the_eight_rows_are_there_on_the_shared_row_with_working_controls(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.settings(cdp, w, mode)
                    self.assertEqual(p.js(ROWS), NAMES)
                    got = p.js("""[...document.querySelectorAll('#essentials .set-row')].map(r => { const c = r.querySelector('.set-row-ctl'), b = r.getBoundingClientRect(), k = c.getBoundingClientRect();
                        return [c.querySelector('input, button') !== null, k.right <= b.right + 1 && k.left >= b.left - 1]; })""")
                    self.assertTrue(all(g[0] and g[1] for g in got), f"each row has a control inside it: {got}")
                    # Appearance: Dark here is Dark in Personal too
                    p.js("document.querySelector('[data-ess-theme-pick=dark]').click()")
                    p.until("document.documentElement.dataset.theme === 'dark' && document.querySelector('[data-theme-pick=dark]').getAttribute('aria-checked') === 'true'", "Dark chosen from Essentials shows in Personal")
                    p.js("document.querySelector('[data-ess-theme-pick=light]').click()")
                    p.until("!document.documentElement.dataset.theme && document.querySelector('[data-theme-pick=light]').getAttribute('aria-checked') === 'true'", "Light")
                    p.js("document.querySelector('[data-ess-theme-pick=system]').click()")
                    # Spacing
                    p.js("document.querySelector('[data-ess-density-pick=comfortable]').click()")
                    p.until("document.documentElement.dataset.density === 'comfortable' && document.querySelector('input[name=density][value=comfortable]').checked", "Spacing set from Essentials shows in Personal")
                    p.js("document.querySelector('[data-ess-density-pick=compact]').click()")
                    p.until("document.documentElement.dataset.density === 'compact'", "Compact again")
                    # Motion
                    p.js("document.querySelector('[data-ess-motion]').click()")
                    p.until("document.documentElement.dataset.motion === 'reduce' && document.querySelector('[data-ess-motion]').getAttribute('aria-checked') === 'false'", "Motion off reduces motion")
                    p.js("document.querySelector('[data-ess-motion]').click()")
                    p.until("!document.documentElement.dataset.motion", "Motion on again")
                    # Single-key shortcuts: the same switch as in Personal
                    p.js("document.querySelector('[data-ess-keys]').click()")
                    p.until("document.querySelector('[data-ess-keys]').getAttribute('aria-checked') === 'false' && document.querySelector('#personal .switch').getAttribute('aria-checked') === 'false'", "the keys switch is one state")
                    p.js("document.querySelector('[data-ess-keys]').click()")
                    p.until("document.querySelector('#personal .switch').getAttribute('aria-checked') === 'true'", "keys on again")
                    # Your name: saved, and About you shows it
                    p.js("""(() => { const b = document.getElementById('ess-name'); b.focus(); b.value = 'Sam Essential'; b.dispatchEvent(new Event('input', {bubbles: true})); b.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true, cancelable: true})); })()""")
                    p.until("document.getElementById('about-name').value === 'Sam Essential'", "the name saved from Essentials shows in About you")
                    # Backups: the copy-folder box and its Save are there
                    self.assertTrue(p.js("!!document.querySelector('#essentials [data-ess-copy-save]') && !!document.querySelector('#essentials #ess-safety-copy-box')"))
                    p.js("""(() => { const b = document.getElementById('ess-safety-copy-box'); b.focus(); b.value = '/tmp/essentials-copy'; b.dispatchEvent(new Event('input', {bubbles: true})); document.querySelector('[data-ess-copy-save]').click(); })()""")
                    p.until("!!document.querySelector('#ess-safety-copy-said p.success')", "the copy folder saved from Essentials")
                    # Publishing folder: Choose folder is there (the project is open)
                    self.assertTrue(p.js("!!document.querySelector('#essentials [data-ess-choose-local]')"))
                    # Asking: the switch is the same one as in Asking
                    p.until("!document.querySelector('[data-ess-ask]').disabled", "the asking switch is ready")
                    was = p.js("document.querySelector('[data-ask-switch]').getAttribute('aria-pressed')")
                    self.assertEqual(p.js("document.querySelector('[data-ess-ask]').getAttribute('aria-pressed')"), was)
                    p.js("document.querySelector('[data-ess-ask]').click()")
                    p.until(f"document.querySelector('[data-ask-switch]').getAttribute('aria-pressed') !== '{was}'", "Asking flipped from Essentials shows in Asking")
                    self.assertFalse(p.js("document.documentElement.scrollWidth > document.documentElement.clientWidth"), "no sideways scroll")
                    self.assertEqual(p.js("[...document.querySelectorAll('[id]')].map(e => e.id).filter((id, i, a) => a.indexOf(id) !== i)"), [], "no id is on the page twice")

    def test_S3_the_originals_stay_in_their_cards_and_the_rows_are_searchable(self):
        with chrome() as cdp:
            p = self.settings(cdp, 1400, "light")
            for sel in ("#about-name", "[data-theme-pick=dark]", "input[name=density]", "#personal .switch", "#safety-copy-box", "#local-folder [data-choose-local]", "[data-ask-switch]"):
                self.assertTrue(p.js(f"!!document.querySelector({sel!r})"), sel + " stays in its own card")
            p.js("""(() => { const b = document.getElementById('set-search-box'); b.focus(); b.value = 'motion'; b.dispatchEvent(new Event('input', {bubbles: true})); })()""")
            p.until("[...document.querySelectorAll('#essentials .set-row')].filter(r => !r.hidden).length === 1", "the Motion row is the one row left in Essentials")
            self.assertEqual(p.js("[...document.querySelectorAll('#essentials .set-row:not([hidden]) label')].map(l => l.textContent)"), ["Motion"])


if __name__ == "__main__":
    unittest.main()
