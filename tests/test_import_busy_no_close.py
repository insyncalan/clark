"""Hunt 14: while the import is applying, Cancel, Esc and the backdrop do nothing (ImportWorkbook.jsx), so the result and Undo are not lost.

Run: python3 dev/run_tests.py test_import_busy_no_close
Quick tier: no browser; reads the source.
"""
import unittest

from _paths import SRC

EDIT = SRC / "clark" / "page" / "src" / "edit" / "ImportWorkbook.jsx"


class ImportBusyNoClose(unittest.TestCase):
    def test_applying_ignores_close(self):
        s = EDIT.read_text(encoding="utf-8")
        self.assertIn('const applying = step.at === "applying"', s)
        self.assertIn("const close = () => { if (!applying) onClose(); }", s)
        self.assertIn('onClick={close}>{T.cancel}', s)
        plan = s[s.index('key="plan"'):]
        self.assertIn("onClose={close}", plan.split("\n")[0])
        self.assertIn('aria-disabled={applying ? "true" : undefined} onClick={close}', plan)
        self.assertNotIn("onClick={onClose}", plan)


if __name__ == "__main__":
    unittest.main()
