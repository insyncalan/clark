"""Row 1264 slice 2: killer tests for mutants the slice's own tests let survive (mutation review). Fictional data only."""
import types
import unittest

from clark.section_kinds import base, glancetemplate as gt
from test_tpl_glance_counts_1264 import AS_AT, counts, pub, rows


class Killers(unittest.TestCase):
    def test_k01_a_row_that_is_not_a_row_is_not_counted_and_does_not_fail(self):
        # base.Context copies every row with dict(), so this is the template's own guard (a stand-in context, not the real one)
        def stub(given):
            return types.SimpleNamespace(rows=given, as_at=AS_AT)
        noisy = {k: [None, "x", 3, ["y"]] + v for k, v in rows().items()}
        self.assertEqual(counts(gt.published({"v": 1}, stub(noisy))), counts(pub()))
        off = {"v": 1, "health": {"shown": False}}
        self.assertIsNone(gt.published(off, stub({"actions": [None, "x"], "raid": [3], "decisions": [["y"]]})))      # nothing countable and no health eye: no section
        self.assertNotIn("counts", gt.published({"v": 1}, stub({"actions": [None, "x"], "raid": [3], "decisions": [["y"]]}))["content"])

    def test_k02_a_bespoke_tone_is_published_as_stored(self):
        for tone in ("green", "amber", "red", "blue"):
            out = pub({"v": 1, "bespoke": [{"id": "t1", "label": "Own", "tone": tone}]})
            self.assertEqual(out["content"]["bespoke"][0]["tone"], tone)
        out = pub({"v": 1, "bespoke": [{"id": "t1", "label": "Own", "tone": "nonsense"}]})
        self.assertEqual(out["content"]["bespoke"][0]["tone"], "neutral")


if __name__ == "__main__":
    unittest.main()
