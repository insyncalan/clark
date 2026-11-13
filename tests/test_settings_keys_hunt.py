"""Hunt: keyboard-only on Settings > Backups (real keys, real routes). Run: python3 dev/run_tests.py test_settings_keys_hunt"""
import json
import unittest

import test_settings_data_page as D
from test_filter_line_keys import Keys
from test_server import chrome

from clark import backup, safety


class Hunt(D.Base):
    settle = D.Card.settle
    open_settings = D.Card.open_settings

    press = Keys.press

    def setUp(self):
        super().setUp()
        self.rig.httpd.excel_import = D.excel_route.make_excel_import(self.rig.db, [], D.USER)
        for tag in list(backup.TAGS)[:2]:
            backup.make(self.rig.db, self.rig.data_dir / "backups", [], tag=tag)
        self.rig.httpd.safety = safety.Safety(self.rig.db, onedrive_roots=[])

    def test_backups_panel_keeps_the_focus_and_esc_closes_it(self):
        with chrome() as cdp:
            p = self.page(cdp)
            for width in D.WIDTHS:
                with self.subTest(width=width):
                    p.width(width)
                    self.open_settings(p)
                    p.until("!!document.querySelector('[data-preview]')", "backups drew")
                    for kind, closer in (("[data-preview]", "Escape"), ("[data-restore]", "Escape"), ("[data-restore]", "Enter")):
                        p.js(f"document.querySelector('{kind}').focus()")
                        self.press(cdp, p.sid, "Enter")
                        p.until("!!document.querySelector('#backup-panel')", "the panel opened")
                        p.until("document.activeElement && document.activeElement.id === 'backup-panel'", "the focus went into the panel")
                        if closer == "Enter":
                            p.js("document.querySelector('#backup-panel [data-cancel]').focus()")
                        self.press(cdp, p.sid, closer)
                        p.until("!document.querySelector('#backup-panel')", closer + " closed the panel")
                        p.until("document.activeElement && document.activeElement.matches(%s)" % json.dumps("[data-backup] " + kind), "focus back on the opener " + kind)
