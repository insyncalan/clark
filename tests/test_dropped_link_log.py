"""Tech Debt 610: a stored link in a documentation range is left out of the published file as before, and the drop is logged by
document id and reason code only (src/clark/publish.py; guarded). The link's text and address are never in the log line.

Run: python3 dev/run_tests.py test_dropped_link_log
"""
import logging
import re
import sqlite3
import unittest

from _demo import DemoStore
from clark import publish

DOC_LINKS = ("https://192.0.2.7/ZQ-ONE-secret", "http://198.51.100.9/ZQ-TWO", "https://203.0.113.5/ZQ-THREE", "mailto:a@192.88.99.1")
FINE = "https://example.com/ZQ-FINE"


class DroppedLinkLog(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.n = 0

    def plant(self, title, url):
        self.n += 1
        ref = f"ABC-L-{self.n:03d}"
        con = sqlite3.connect(str(self.s.path))
        con.execute("INSERT INTO documents (project, id, title, kind, url, date, sort_order, archived) VALUES (?,?,?,?,?,?,?,?)",
                    ("ABC", ref, title, "Report", url, "2030-01-02", self.n * 1024, 0))
        con.commit()
        con.close()
        return ref

    def built(self):
        return publish.build(self.s, "ABC", now="2030-01-15")

    def test_a_documentation_range_link_is_dropped_as_before_and_logged_by_id_and_reason(self):
        kept = self.plant("Kept paper", FINE)
        dropped = self.plant("Range paper", DOC_LINKS[0])
        with self.assertLogs("clark.publish", level="INFO") as cm:
            built = self.built()
        self.assertIn(b"ZQ-FINE", built["body"])
        self.assertNotIn(b"ZQ-ONE", built["body"])
        self.assertNotIn(b"192.0.2.7", built["body"])
        lines = [r.getMessage() for r in cm.records]
        self.assertEqual(lines, [f"document link left out of the published file id={dropped} reason=documentation range"])
        for text in ("192.0.2.7", "ZQ-ONE", "Range paper", kept):
            self.assertNotIn(text, lines[0])

    def test_a_link_outside_the_ranges_logs_nothing(self):
        self.plant("Fine paper", FINE)
        self.plant("Local paper", "http://10.0.0.1/x")             # refused too, but not a documentation range
        with self.assertLogs("clark.publish", level="DEBUG") as cm:
            logging.getLogger("clark.publish").debug("probe")
            built = self.built()
        self.assertEqual([r.getMessage() for r in cm.records], ["probe"])
        self.assertIn(b"ZQ-FINE", built["body"])
        self.assertNotIn(b"10.0.0.1", built["body"])

    def test_two_dropped_links_log_two_lines(self):
        ids = [self.plant(f"Paper {i}", url) for i, url in enumerate(DOC_LINKS[:2])]
        with self.assertLogs("clark.publish", level="INFO") as cm:
            self.built()
        lines = [r.getMessage() for r in cm.records]
        self.assertEqual(len(lines), 2)
        for ref, line in zip(ids, lines):
            self.assertRegex(line, re.escape(f"id={ref} reason=documentation range"))


if __name__ == "__main__":
    unittest.main()
