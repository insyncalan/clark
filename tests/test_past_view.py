"""#343: a past publication opens read only (guarded: server.py /past, past_reports.py, past_banner.py). Fictional data only; no browser.

The page that opens is the published file as it was, with one block added after <body> for that visit: the banner 'Publication N ·
DD-MM-YYYY · read only', a tinted frame, 'Back to now'. Nothing in it can be changed. The file's SHA-256 is checked on open and a
file that no longer matches is refused in plain words with what to do. The browser check at 1400 and 900 px is reported on the PR.

Run: python3 dev/run_tests.py test_past_view
"""
import base64
import hashlib
import http.client
import json
import re
import threading
import unittest
from html.parser import HTMLParser

import _paths  # noqa: F401
from clark import past_banner, past_reports
from clark import server as sv
from test_past_reports import Base


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)


def opened(test, number):
    """The page a person gets for Publication `number`, through the seam."""
    status, got = test.past.visit("PUB", number)
    test.assertEqual(status, 200, got)
    return test.past.take(got["url"].split("=")[1])


class TheBanner(Base):
    def setUp(self):
        super().setUp()
        self.past = past_reports.PastReports(self.db)

    def test_the_words_the_date_the_tint_and_back_to_now(self):
        done, body = self.publish(now="2026-10-23")
        shown = opened(self, done["number"]).decode("utf-8")
        found = re.search(r"Publication (\d+) · (\d\d-\d\d-\d{4}) · read only", shown)
        self.assertIsNotNone(found, "the banner words")
        self.assertEqual(int(found.group(1)), done["number"])
        row = self.store.con.execute("SELECT at FROM publications WHERE number = ?", (done["number"],)).fetchone()[0]
        y, m, d = row[:10].split("-")
        self.assertEqual(found.group(2), f"{d}-{m}-{y}", "the day is the publication's own, as DD-MM-YYYY")
        self.assertIn('id="clark-past-frame"', shown)
        self.assertIn("pointer-events:none", shown, "the tinted frame takes no clicks")
        self.assertRegex(shown, r'<a href="/" id="clark-past-back">Back to now</a>')
        self.assertIn("The report as it was published · corrections go into the next report", shown)

    def test_the_banner_is_the_first_thing_in_the_body_and_nothing_else_is_added(self):
        done, body = self.publish()
        shown = opened(self, done["number"])
        self.assertEqual(past_banner.unframe(shown), body, "taking the block out gives the published bytes, byte for byte")
        self.assertEqual(shown.count(past_banner.MARK_START), 1)
        tags = Tags()
        tags.feed(shown.decode("utf-8"))
        at = tags.tags.index("body")
        self.assertEqual(tags.tags[at + 1:at + 4], ["style", "div", "b"], "right after <body>")
        self.assertLess(len(shown) - len(body), 3000, "a small block, nothing more")

    def test_the_block_has_nothing_to_edit_and_no_way_to_write(self):
        done, body = self.publish()
        shown = opened(self, done["number"])
        block = shown[shown.index(past_banner.MARK_START):shown.index(past_banner.MARK_END)].decode("utf-8")
        for editable in ("<input", "<textarea", "<select", "<form", "<button", "contenteditable", "fetch(", "XMLHttpRequest", "/api/"):
            self.assertNotIn(editable, block)

    def test_the_pages_own_policy_lets_only_the_blocks_style_and_script_run(self):
        done, body = self.publish()
        shown = opened(self, done["number"])
        meta = past_banner.META.search(shown).group(2).decode()
        style, script = past_banner.hashes()
        self.assertIn(f"script-src {meta.split('script-src ')[1].split(';')[0]}", meta)
        self.assertEqual(meta.count(script), 1)
        self.assertEqual(meta.count(style), 1)
        self.assertIn(script, re.search(r"script-src ([^;]*)", meta).group(1))
        self.assertIn(style, re.search(r"style-src-elem ([^;]*)", meta).group(1))
        for kept in ("default-src 'none'", "connect-src 'none'", "form-action 'none'", "object-src 'none'", "base-uri 'none'"):
            self.assertIn(kept, meta, "the rest of the policy is as it was published")
        self.assertNotIn("unsafe", meta)
        self.assertEqual(meta.replace(" " + script, "").replace(" " + style, ""), past_banner.META.search(body).group(2).decode())

    def test_a_policy_with_none_for_a_list_takes_the_hash_and_gives_it_back(self):
        page = (b'<html><head><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'none\'; '
                b'style-src-elem \'none\'"></head><body>x</body></html>')
        shown = past_banner.frame(page, 1, "01-01-2026")
        self.assertIn(past_banner.hashes()[1].encode(), shown)
        self.assertNotIn(b"script-src 'none'", shown)
        self.assertEqual(past_banner.unframe(shown), page)
        self.assertIsNone(past_banner.frame(page.replace(b"script-src 'none'; ", b""), 1, "01-01-2026"), "no list to add to: not shown")

    def test_the_number_and_the_day_are_only_what_the_row_gives(self):
        for number, day in ((0, "01-01-2026"), (-1, "01-01-2026"), (True, "01-01-2026"), ("1", "01-01-2026"), (1, "2026-01-01"),
                            (1, "<b>x</b>"), (1, None), (1, "01-01-2026\n")):
            with self.subTest(number=number, day=day):
                with self.assertRaises(ValueError):
                    past_banner.block(number, day)

    def test_a_file_with_no_body_tag_gets_no_block(self):
        self.assertIsNone(past_banner.frame(b"<html><title>x</title></html>", 1, "01-01-2026"))
        self.assertEqual(past_banner.unframe(b"<body>x</body>"), b"<body>x</body>")

    def test_each_one_opens_with_its_own_number_and_day(self):
        first, _ = self.publish()
        second, _ = self.publish()
        for done in (first, second):
            self.assertIn(f"Publication {done['number']} · ", opened(self, done["number"]).decode())
        self.assertNotIn(f"Publication {first['number']} · ", opened(self, second["number"]).decode())

    def test_an_archived_publication_still_opens_read_only(self):
        done, body = self.publish()
        self.store.archive_publication("PUB", done["number"])
        self.assertIn("read only", opened(self, done["number"]).decode())


class TheChecksum(Base):
    def setUp(self):
        super().setUp()
        self.past = past_reports.PastReports(self.db)

    def test_a_file_that_no_longer_matches_is_refused_in_plain_words_with_what_to_do(self):
        done, body = self.publish()
        kept = self.copies / f"PUB-{done['number']}.html"
        kept.chmod(0o644)
        kept.write_bytes(body.replace(b"<body", b"<body data-x=1", 1))
        status, got = self.past.visit("PUB", done["number"])
        self.assertEqual((status, got["ok"], got["code"]), (409, False, "copy_changed"))
        self.assertIn("no longer matches what was published", got["message"])
        self.assertIn("Restore your data from a backup", got["message"], "what to do")
        self.assertNotIn("url", got)
        self.assertEqual(len(self.past.visits), 0, "no address is made for it, so nothing is shown")

    def test_one_changed_byte_is_enough_and_putting_it_back_opens_it_again(self):
        done, body = self.publish()
        kept = self.copies / f"PUB-{done['number']}.html"
        kept.chmod(0o644)
        kept.write_bytes(body[:-1] + (b"X" if body[-1:] != b"X" else b"Y"))
        self.assertEqual(self.past.visit("PUB", done["number"])[1]["code"], "copy_changed")
        kept.write_bytes(body)
        self.assertEqual(self.past.visit("PUB", done["number"])[0], 200)

    def test_a_matching_file_without_a_body_tag_is_refused_not_shown_bare(self):
        data = b"<!doctype html><title>x</title>"
        source = self.root / "bare.html"
        source.write_bytes(data)
        seq = self.store.log_publication("PUB", source, "2026-10-23", hashlib.sha256(data).hexdigest(), "x")
        number = self.store.number_of(seq)
        self.assertEqual(self.past.visit("PUB", number)[1]["code"], "copy_changed")


class OverHttp(Base):
    def setUp(self):
        super().setUp()
        self.past = past_reports.PastReports(self.db)
        self.httpd = sv.LocalServer((sv.HOST, 0), data_for=self.store.data_for, projects=lambda: [], past=self.past)
        self.httpd.handle_error = lambda *a: None
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def call(self, method, path, token=True, body=None):
        conn = http.client.HTTPConnection(sv.HOST, self.httpd.server_port, timeout=20)
        try:
            h = {"Host": f"127.0.0.1:{self.httpd.server_port}"}
            if token:
                h[sv.TOKEN_HEADER] = sv.TOKEN
            data = None
            if body is not None:
                data = body.encode()
                h.update({"Content-Length": str(len(data)), "Content-Type": "application/json"})
            conn.request(method, path, data, h)
            r = conn.getresponse()
            return r.status, r, r.read()
        finally:
            conn.close()

    def address(self, number):
        status, _, raw = self.call("GET", f"/api/past-report?project=PUB&number={number}")
        self.assertEqual(status, 200, raw)
        return json.loads(raw)["url"]

    def test_the_route_serves_the_banner_under_the_same_sandbox_and_a_policy_that_lets_it_run(self):
        done, body = self.publish()
        status, resp, shown = self.call("GET", self.address(done["number"]), token=False)
        self.assertEqual(status, 200)
        self.assertEqual(past_banner.unframe(shown), body)
        self.assertIn(b"read only", shown)
        csp = "; ".join(resp.msg.get_all("Content-Security-Policy"))
        self.assertIn("sandbox allow-scripts", csp)
        for flag in ("allow-same-origin", "allow-forms", "allow-top-navigation", "allow-popups"):
            self.assertNotIn(flag, csp)
        script = re.search(rb"<script>(document\.getElementById\('clark-past-back'\).*?)</script>", shown, re.S).group(1)
        digest = base64.b64encode(hashlib.sha256(script).digest()).decode()
        self.assertIn(f"'sha256-{digest}'", csp, "the banner's own script is allowed by hash, nothing is opened up")
        self.assertNotIn("'unsafe-inline'", re.search(r"script-src ([^;]*)", csp).group(1))

    def test_nothing_on_the_view_can_change_anything(self):
        done, body = self.publish()
        url = self.address(done["number"])
        before = (self.copies / f"PUB-{done['number']}.html").read_bytes()
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            self.assertGreaterEqual(self.call(method, "/past?id=x", body="{}")[0], 400, method)
        self.assertEqual((self.copies / f"PUB-{done['number']}.html").read_bytes(), before, "the kept file is as it was")
        self.assertEqual(self.call("GET", url, token=False)[0], 200, "and the address was not used up by any of that")
        self.assertEqual([r for r in sv.POST_ROUTES if "past" in r], [], "no route that writes names a past publication")

    def test_a_changed_file_is_a_409_with_the_words_over_http(self):
        done, body = self.publish()
        kept = self.copies / f"PUB-{done['number']}.html"
        kept.chmod(0o644)
        kept.write_bytes(body + b"\n")
        status, _, raw = self.call("GET", f"/api/past-report?project=PUB&number={done['number']}")
        got = json.loads(raw)
        self.assertEqual((status, got["code"]), (409, "copy_changed"))
        self.assertIn("Restore your data from a backup", got["message"])


if __name__ == "__main__":
    unittest.main()
