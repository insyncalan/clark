"""Row 654 part C: dev/tools/perf_baseline.py reads a page's parts and the -X importtime lines correctly.

Run: python3 dev/run_tests.py test_tools_perf_baseline
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dev" / "tools"))
import perf_baseline as pb  # noqa: E402


class PartsTests(unittest.TestCase):
    def test_parts_count_style_script_data_and_rest(self):
        html = '<html><style>a{b:url(data:image/png;base64,AAAA)}</style><script>x=1</script><p>é</p></html>'
        p = pb.parts(html)
        self.assertEqual(p["total"], len(html.encode("utf-8")))
        self.assertEqual(p["style"], len('<style>a{b:url(data:image/png;base64,AAAA)}</style>'))
        self.assertEqual(p["script"], len("<script>x=1</script>"))
        self.assertEqual(p["data_uris"], len("data:image/png;base64,AAAA"))
        self.assertEqual(p["rest"], p["total"] - p["style"] - p["script"])

    def test_slowest_imports_sorted_by_self_time(self):
        rows = pb.slowest_imports("json", 3)
        self.assertEqual(len(rows), 3)
        self.assertEqual([r["self_ms"] for r in rows], sorted((r["self_ms"] for r in rows), reverse=True))

    def test_render_names_every_measure(self):
        m = {"page_served": {"total": 1}, "page_published": {"total": 2}, "import_server_ms": 3.0, "page_html_ms": 4.0,
             "slowest_imports": [{"module": "m", "self_ms": 1.0, "cumulative_ms": 2.0}]}
        text = pb.render(m)
        for word in ("page_served", "page_published", "import clark.server", "page_html()", "  m"):
            self.assertIn(word, text)


if __name__ == "__main__":
    unittest.main()
