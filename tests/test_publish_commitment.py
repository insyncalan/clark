"""#709: the commitment flag in what a client is given: the published rows (publish.select), the Dashboard strip, the Word copy, an
older publication's rows (no flag: none), and the as-at view (the flag as it stood on a day).

Run: python3 dev/run_tests.py test_publish_commitment
No browser: the rows are the #39 plant (project PUB, made up) passed through publish.select, and the Word copy is read back with docx_read.
"""
import copy
import io
import json
import shutil
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
import _publish_fixture as fx
from _demo import USER
from clark import as_at, docx_build, docx_read, glance, publish, store as clark_store
from clark.store import COMMITMENTS, open_store


def plant_with(**flags):
    """The plant with a flag on some use cases ({id: word}); the plant's own rows carry no `commitment` key at all (an old row)."""
    p = fx.load()
    for u in p["data"]["use_cases"]:
        if u["id"] in flags:
            u["commitment"] = flags[u["id"]]
    return p


def kept(p):
    return {u["id"]: u for u in publish.select(fx.inputs(p))["data"]["use_cases"]}


class Published(unittest.TestCase):
    def test_the_flag_is_in_the_whitelist_and_goes_with_the_use_case(self):
        self.assertIn("commitment", publish.PUBLISH_FIELDS["use_cases"])
        got = kept(plant_with(**{"PUB-U-001": "Committed"}))
        self.assertEqual(got["PUB-U-001"]["commitment"], "Committed")

    def test_a_use_case_with_no_flag_or_an_old_row_with_no_key_carries_none(self):
        got = kept(plant_with())
        self.assertIsNone(got["PUB-U-001"]["commitment"])
        self.assertIn("commitment", got["PUB-U-001"], "the key is always there, so the page need not guess")

    def test_each_of_the_three_words_is_carried_as_written(self):
        for word in COMMITMENTS:
            with self.subTest(word=word):
                self.assertEqual(kept(plant_with(**{"PUB-U-001": word}))["PUB-U-001"]["commitment"], word)

    def test_a_use_case_the_eye_hides_carries_nothing_of_its_flag(self):
        p = plant_with(**{"PUB-U-001": "Committed", "PUB-U-002": "Planned 2027", "PUB-U-003": "Candidate"})
        out = publish.select(fx.inputs(p))
        got = {u["id"] for u in out["data"]["use_cases"]}
        self.assertNotIn("PUB-U-002", got)                     # the eye is off
        self.assertNotIn("PUB-U-003", got)                     # Sensitive
        text = json.dumps(out)
        self.assertNotIn("Planned 2027", text)
        self.assertNotIn("Candidate", text)

    def test_an_archived_or_report_hidden_use_case_carries_nothing(self):
        p = plant_with(**{"PUB-U-001": "Planned 2027"})
        p["data"]["use_cases"][0]["archived"] = 1
        self.assertNotIn("Planned 2027", json.dumps(publish.select(fx.inputs(p))))
        p = plant_with(**{"PUB-U-001": "Planned 2027"})
        p["hidden"].append("PUB-U-001")
        self.assertNotIn("Planned 2027", json.dumps(publish.select(fx.inputs(p))))

    def test_a_stray_word_in_the_database_is_not_published(self):
        got = kept(plant_with(**{"PUB-U-001": "Planned 2028"}))
        self.assertIsNone(got["PUB-U-001"]["commitment"])

    def test_the_use_cases_section_hidden_publishes_none(self):
        p = plant_with(**{"PUB-U-001": "Committed"})
        for s in p["sections"]:
            if s["type"] == "usecases":
                s["hidden"] = 1
        self.assertNotIn("Committed", json.dumps(publish.select(fx.inputs(p))))

    def test_the_client_rule_still_gives_ids_only(self):
        p = plant_with(**{"PUB-U-001": "Committed"})
        pages = publish.client_use_cases(p["data"], "PUB", p["hidden"], p["label_rules"])
        for page in pages:
            self.assertEqual(set(page), {"id", "next_steps", "milestones"})


class Strip(unittest.TestCase):
    def strip(self, p):
        k = glance.kept_from(publish.select(fx.inputs(p)), p["sections"])
        return {r["id"]: r for r in glance.use_case_strip(None, None, p["as_at"], for_client=True, kept=k)["rows"]}

    def test_a_strip_row_carries_the_flag_or_none(self):
        rows = self.strip(plant_with(**{"PUB-U-001": "Candidate"}))
        self.assertEqual(rows["PUB-U-001"]["commitment"], "Candidate")
        rows = self.strip(plant_with())
        self.assertIsNone(rows["PUB-U-001"]["commitment"])

    def test_the_editors_strip_carries_it_too(self):
        p = plant_with(**{"PUB-U-002": "Committed"})
        rows = glance.use_case_strip(p["data"]["use_cases"], [], p["as_at"])["rows"]
        self.assertEqual({r["id"]: r["commitment"] for r in rows}["PUB-U-002"], "Committed")


class WordCopy(unittest.TestCase):
    def build(self, p):
        return docx_build.build(publish.select(fx.inputs(p)))

    def table(self, data):
        for b in docx_read.read(data, "report.docx").blocks:
            if b.get("kind") == "table" and "Commitment" in (b.get("rows") or [[]])[0]:
                return b["rows"]
        return None

    def test_the_use_case_table_has_a_commitment_column_after_status(self):
        rows = self.table(self.build(plant_with(**{"PUB-U-001": "Planned 2027"})))
        self.assertIsNotNone(rows)
        head = rows[0]
        self.assertEqual(head[head.index("Status") + 1], "Commitment")
        self.assertEqual([r[head.index("Commitment")] for r in rows[1:]], ["Planned 2027"])

    def test_a_use_case_with_no_flag_has_a_blank_cell_and_a_hidden_one_is_not_there(self):
        data = self.build(plant_with(**{"PUB-U-002": "Candidate"}))
        rows = self.table(data)
        self.assertEqual([r[rows[0].index("Commitment")] for r in rows[1:]], [""])
        zf = zipfile.ZipFile(io.BytesIO(data))
        text = "\n".join(zf.read(n).decode("utf-8") for n in zf.namelist() if n.endswith((".xml", ".rels")))
        self.assertNotIn("Candidate", text)


class OlderPublication(unittest.TestCase):
    def test_rows_from_a_publication_made_before_the_flag_show_none(self):
        """A past publication's rows have no commitment key at all: the strip and the Word copy read them as none."""
        p = fx.load()
        for u in p["data"]["use_cases"]:
            self.assertNotIn("commitment", u)
        out = publish.select(fx.inputs(p))
        old = copy.deepcopy(out)
        for u in old["data"]["use_cases"]:
            del u["commitment"]                                  # a file made by 1.0.0
        k = glance.kept_from(old, p["sections"])
        rows = glance.use_case_strip(None, None, p["as_at"], for_client=True, kept=k)["rows"]
        self.assertTrue(rows)
        self.assertEqual({r["commitment"] for r in rows}, {None})
        docx_build.build(old)                                    # builds, with a blank cell


def at(text):
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)


class AsAt(unittest.TestCase):
    """A flag set on 12-10-2026 and cleared on 20-10-2026 is rebuilt as it stood on each day."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.now = at("2026-10-05 09:00")
        patch = mock.patch.object(clark_store, "clock", lambda: self.now)
        patch.start()
        self.addCleanup(patch.stop)
        self.store = open_store(self.dir / "clark.db", onedrive_roots=[])
        self.addCleanup(self.store.close)
        s = self.store
        with s.step("dashboard", USER) as st:
            st.create("projects", {"code": "ABC", "name": "Example Programme", "health": "On track", "week_ending": "2026-10-09"})
            self.uc = st.create("use_cases", {"project": "ABC", "title": "Matching", "status": "On track", "source": "demo"})
        self.now = at("2026-10-12 10:00")
        with s.step("dashboard", USER) as st:
            st.update("use_cases", self.uc, {"commitment": "Committed"})
        self.now = at("2026-10-20 11:00")
        with s.step("dashboard", USER) as st:
            st.update("use_cases", self.uc, {"commitment": None})
        self.now = at("2026-11-03 08:00")
        self.seam = as_at.AsAt(s.path, today=lambda: "2026-11-03", tz=timezone.utc)

    def flag(self, day):
        status, body = self.seam.read("ABC", day)
        self.assertEqual(status, 200, body)
        (row,) = body["data"]["use_cases"]
        return row["commitment"]

    def test_the_flag_is_as_it_stood_on_each_day(self):
        self.assertIsNone(self.flag("2026-10-06"))
        self.assertEqual(self.flag("2026-10-12"), "Committed")
        self.assertEqual(self.flag("2026-10-19"), "Committed")
        self.assertIsNone(self.flag("2026-10-20"))
        self.assertIsNone(self.flag("2026-11-03"))

    def test_the_feed_carries_the_words_so_the_page_never_writes_them(self):
        status, body = self.seam.read("ABC", "2026-11-03")
        self.assertEqual(body["data"]["commitments"], list(COMMITMENTS))
        self.assertEqual(self.store.data_for("ABC")["commitments"], list(COMMITMENTS))


if __name__ == "__main__":
    unittest.main()
