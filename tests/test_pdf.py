"""PDF export. Pure parts need no Chrome; one test prints a page with the real Chrome. Run: python3 dev/run_tests.py test_pdf"""
import os
import re
import subprocess
import tempfile
import zlib
import unittest
from unittest import mock
from pathlib import Path

from _paths import ROOT  # noqa: F401  (puts src/ and dev/tools on sys.path)

from clark import pdf, platform
from run_support import chrome_path

PAGE = "<!doctype html><html><head><meta charset=utf-8><title>Demo</title></head><body style='background:#eef'><h1>Harbour Road survey</h1><p>All fine.</p></body></html>"


def pdf_text(data):
    """Rough text of a PDF. Chrome writes glyph ids as hex strings, with one ToUnicode map per font; so every map is tried
    on every text string, and the readings are joined (the wrong ones are only noise)."""
    streams = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", data, re.S):
        try:
            streams.append(zlib.decompress(m.group(1)).decode("latin-1"))
        except zlib.error:
            pass
    maps = []
    for st in streams:
        if "beginbfchar" not in st and "beginbfrange" not in st:
            continue
        one = {}
        for a, b in re.findall(r"<([0-9a-fA-F]{4})>\s*<([0-9a-fA-F]{4})>\s*(?=<|endbfchar|\n)", st.split("beginbfrange")[0]):
            one[int(a, 16)] = chr(int(b, 16))
        for lo, hi, to in re.findall(r"<([0-9a-fA-F]{4})>\s*<([0-9a-fA-F]{4})>\s*<([0-9a-fA-F]{4})>",
                                      st.split("beginbfrange", 1)[1] if "beginbfrange" in st else ""):
            for i in range(int(lo, 16), int(hi, 16) + 1):
                one[i] = chr(int(to, 16) + i - int(lo, 16))
        maps.append(one)
    shown = []
    for st in streams:
        if "beginbf" in st:
            continue
        for m in re.finditer(r"\[([^\]]*)\]\s*TJ|<([0-9a-fA-F]+)>\s*Tj", st):
            shown.append(re.sub(r"[^0-9a-fA-F]", "", re.sub(r"\)?-?\d+(\.\d+)?(?=<)", "", m.group(1) or m.group(2))))
    out = []
    for one in maps:
        for hexs in shown:
            out.append("".join(one.get(int(hexs[i:i + 4], 16), "") for i in range(0, len(hexs) - 3, 4)))
            out.append(" ")
    return "".join(out)


class Pure(unittest.TestCase):
    def test_print_css(self):
        self.assertIn("size:A4 portrait", pdf.print_css())
        self.assertIn("size:A4 landscape", pdf.print_css("landscape"))
        self.assertIn("print-color-adjust:exact", pdf.print_css())
        with self.assertRaises(ValueError):
            pdf.print_css("sideways")

    def test_css_goes_in_head(self):
        out = pdf.with_print_css(PAGE)
        self.assertLess(out.index("@page"), out.index("</head>"))
        self.assertEqual(pdf.with_print_css("<p>x</p>").count("@page"), 1)

    def test_args(self):
        a = pdf.chrome_args("/c/chrome", "/p", "/x/page.html", "/x/o.pdf")
        for flag in ("--use-mock-keychain", "--password-store=basic", "--no-pdf-header-footer",
                     "--host-resolver-rules=MAP * ~NOTFOUND", "--proxy-server=http://127.0.0.1:1", "--user-data-dir=/p",
                     "--print-to-pdf=/x/o.pdf"):
            self.assertIn(flag, a)
        self.assertIn("--proxy-server=http://127.0.0.1:1", pdf._devtools_args("/c", "/p", True), "the pipe start has the dead proxy too")
        self.assertIn("--proxy-server=http://127.0.0.1:1", pdf._devtools_args("/c", "/p", False), "and so has the port start")
        self.assertTrue(a[-1].startswith("file:///"))

    def test_a_child_that_was_already_gone_has_no_group_signalled(self):
        signals = []

        class Gone:
            pid = 2 ** 22 + 7

            def poll(self):
                return 0

            def wait(self, t=None):
                return 0
        with mock.patch.object(pdf.os, "killpg", lambda *a: signals.append(a)):
            pdf.stop_child(Gone())
        self.assertEqual(signals, [], "a group number that may belong to someone else now is never signalled")

    def test_find_chrome(self):
        self.assertEqual(pdf.find_chrome({"CLARK_CHROME": "/a"}, which=lambda n: None, exists=lambda p: p == "/a"), "/a")
        self.assertEqual(pdf.find_chrome({}, which=lambda n: "/usr/bin/chromium" if n == "chromium" else None, exists=lambda p: False), "/usr/bin/chromium")
        self.assertIsNone(pdf.find_chrome({}, which=lambda n: None, exists=lambda p: False))

    def test_missing_chrome_plain_words(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(pdf, "find_chrome", return_value=None), \
                self.assertRaises(pdf.PdfError) as cm:
            page = Path(d) / "p.html"
            page.write_text(PAGE, encoding="utf-8")
            pdf.make_pdf(page, Path(d) / "o.pdf")
        self.assertEqual(str(cm.exception), pdf.NO_CHROME)

    def test_cannot_start(self):
        def boom(*a, **k):
            raise FileNotFoundError("x")
        with tempfile.TemporaryDirectory() as d:
            page = Path(d) / "p.html"
            page.write_text(PAGE, encoding="utf-8")
            with self.assertRaises(pdf.PdfError) as cm:
                pdf.make_pdf(page, Path(d) / "o.pdf", chrome="/nope", popen=boom)
            self.assertEqual(str(cm.exception), pdf.NO_CHROME)

    def test_timeout_stops_child(self):
        procs = []

        def sleeper(args, **k):          # holds the pipe's ends, as Chrome does, so the print waits for it
            procs.append(subprocess.Popen(["sleep", "30"], start_new_session=True, pass_fds=k.get("pipe", ()),
                                          ))
            return procs[0]
        with tempfile.TemporaryDirectory() as d:
            page = Path(d) / "p.html"
            page.write_text(PAGE, encoding="utf-8")
            with self.assertRaises(pdf.PdfError) as cm:
                pdf.make_pdf(page, Path(d) / "o.pdf", chrome="/x", timeout=0.2, popen=sleeper)
            self.assertEqual(str(cm.exception), pdf.TOO_SLOW)
        self.assertIsNotNone(procs[0].poll())

    def test_footer_is_escaped(self):
        f = pdf.footer_template("Publication 3 <script>alert(1)</script> & co")
        self.assertNotIn("<script>", f)
        self.assertIn("&lt;script&gt;", f)
        self.assertIn('class="pageNumber"', f)
        self.assertIn('class="totalPages"', f)
        self.assertIn("Arial", f)

    def test_footer_left_is_optional(self):
        self.assertIn("Page ", pdf.footer_template())
        self.assertNotIn("None", pdf.footer_template(None))

    def test_print_params(self):
        p = pdf.print_params("landscape", "Publication 4 \u00b7 28-10-2026")
        self.assertTrue(p["landscape"])
        self.assertFalse(pdf.print_params()["landscape"])
        self.assertEqual((p["paperWidth"], p["paperHeight"]), (8.27, 11.69))
        self.assertTrue(p["printBackground"] and p["displayHeaderFooter"])
        self.assertIn("Publication 4 \u00b7 28-10-2026", p["footerTemplate"])
        with self.assertRaises(ValueError):
            pdf.print_params("sideways")

    def test_falls_back_to_the_flag_when_devtools_cannot_start(self):
        calls = []

        class Gone:
            returncode = 1

            pid = 2 ** 22 + 5

            def poll(self):
                return 1

            def wait(self, t=None):
                return 1

        def fake(args, **k):
            calls.append(args)
            return Gone()
        with tempfile.TemporaryDirectory() as d:
            page = Path(d) / "p.html"
            page.write_text(PAGE, encoding="utf-8")
            with self.assertRaises(pdf.PdfError) as cm:
                pdf.make_pdf(page, Path(d) / "o.pdf", chrome="/x", timeout=5, popen=fake)
            self.assertEqual(str(cm.exception), pdf.FAILED)
        self.assertTrue(any(a.endswith("debugging-pipe") for a in calls[0]), "a pipe, so no port is opened")
        self.assertFalse(any("debugging-port" in a for a in calls[0]))
        self.assertTrue(any(a.startswith("--print-to-pdf=") for a in calls[1]))

    def test_print_rules(self):
        css = pdf.print_css()
        for need in ("print-stacked #app{display:none", "break-before:page", "break-inside:avoid", "color-scheme:light",
                     ".top,", ".toc", "button", "thead{display:table-header-group}", "@media print"):
            self.assertIn(need, css)
        self.assertEqual(css, pdf.print_css("portrait"))
        self.assertNotIn("dark", css)

    def test_page_is_light_in_the_copy(self):
        for page in (PAGE, PAGE.replace("<html>", '<html lang="en" data-theme="dark">'), PAGE.replace("<html>", "<html data-theme=auto>")):
            out = pdf.with_print_css(page)
            self.assertEqual(out.count("data-theme"), 1)
            self.assertIn('data-theme="light"', out)
        self.assertEqual(pdf.with_print_css("<p>x</p>").count("data-theme"), 0)

    def test_stack_script_uses_the_pages_own_navigation(self):
        js = pdf.stack_script()
        self.assertNotIn("clarkPage", js)
        self.assertIn(".click()", js)
        self.assertIn("print-stacked", js)
        self.assertNotIn("location", js)
        self.assertNotIn("href", js)

    def test_no_port_is_opened_on_posix(self):
        piped, ported = pdf._devtools_args("/c", "/p", True), pdf._devtools_args("/c", "/p", False)
        self.assertTrue(any(a.endswith("debugging-pipe") for a in piped))
        self.assertFalse(any("debugging-port" in a for a in piped))
        self.assertTrue(any("debugging-port" in a for a in ported))

    def test_chrome_is_spawned_without_preexec_fn_and_with_fds_3_and_4(self):
        import ast
        for module in (pdf, platform):
            tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
            self.assertNotIn("preexec_fn", {n.arg for n in ast.walk(tree) if isinstance(n, ast.keyword)},
                             "threads: no code runs in the child between fork and exec")
        seen = {}

        def fake_spawn(path, args, env, **k):
            seen.update(k)
            return 1
        with mock.patch.object(os, "posix_spawn", fake_spawn):
            pdf._start_piped("/c", "/p", None)
        moves = [a[2] for a in seen["file_actions"] if a[0] == os.POSIX_SPAWN_DUP2]
        self.assertEqual(moves, [3, 4])
        self.assertEqual(seen["setpgroup"], 0)

    def test_pipe_messages_are_nul_ended(self):
        import os
        import time
        a_r, a_w = os.pipe()
        b_r, b_w = os.pipe()
        pipe = pdf._Pipe(a_w, b_r, time.monotonic() + 5)
        pipe.send_json({"id": 1})
        self.assertEqual(os.read(a_r, 100), b'{"id": 1}\0')
        os.write(b_w, b'{"id": 2}\0{"id"')
        self.assertEqual(pipe.recv_json(), {"id": 2})
        os.write(b_w, b': 3}\0')
        self.assertEqual(pipe.recv_json(), {"id": 3})
        for fd in (a_r, b_w):
            os.close(fd)
        with self.assertRaises(ConnectionError):
            pipe.recv_json()
        pipe.close()

    def test_remove_folder_retries(self):
        with tempfile.TemporaryDirectory() as d:
            sub = Path(d) / "a"
            (sub / "b").mkdir(parents=True)
            self.assertTrue(pdf.remove_folder(sub))
            self.assertTrue(pdf.remove_folder(sub))


class RealChrome(unittest.TestCase):
    def test_prints_a_pdf(self):
        chrome = chrome_path()
        self.assertTrue(chrome, "Chrome is needed: set CLARK_CHROME or put google-chrome on the PATH")
        with tempfile.TemporaryDirectory() as d:
            page = Path(d) / "p.html"
            page.write_text(PAGE, encoding="utf-8")
            before = page.read_text(encoding="utf-8")
            for o in ("portrait", "landscape"):
                out = pdf.make_pdf(page, Path(d) / f"{o}.pdf", o, chrome=chrome)
                data = out.read_bytes()
                self.assertTrue(data.startswith(b"%PDF"))
                box = data.split(b"/MediaBox")[1][:60] if b"/MediaBox" in data else b""
                self.assertTrue(box, "no page size found")
                nums = [float(x) for x in box.split(b"[")[1].split(b"]")[0].split()]
                w, h = nums[2] - nums[0], nums[3] - nums[1]
                self.assertAlmostEqual(min(w, h), 595, delta=3)
                self.assertAlmostEqual(max(w, h), 842, delta=3)
                self.assertEqual(w > h, o == "landscape")
            self.assertEqual(page.read_text(encoding="utf-8"), before)

    def test_footer_and_page_numbers(self):
        chrome = chrome_path()
        self.assertTrue(chrome, "Chrome is needed: set CLARK_CHROME or put google-chrome on the PATH")
        long = PAGE.replace("<p>All fine.</p>", "<p>All fine.</p>" + "<p style='break-after:page'>More.</p>" * 2)
        with tempfile.TemporaryDirectory() as d:
            page = Path(d) / "p.html"
            page.write_text(long, encoding="utf-8")
            out = pdf.make_pdf(page, Path(d) / "o.pdf", chrome=chrome,
                               footer_left="Publication 7 \u00b7 28-10-2026 <script>")
            text = re.sub(r"\s+", " ", pdf_text(out.read_bytes()))
            for word in ("Publication", "28-10-2026", "<script>", "Page 1 of 2", "Page 2 of 2"):
                self.assertIn(word, text)
            self.assertIn("Harbour", text)
            self.assertEqual(len(re.findall(rb"/Type\s*/Page[^s]", out.read_bytes())), 2)




# ===== The Publish option (publish_pdf.py) =====
import _publish_fixture as fx                                     # noqa: E402
from test_publish_route import Rig, WANTED, DAY                   # noqa: E402
from clark import pdf_text as pdftext, publish_pdf, to_client                # noqa: E402
from clark.store import Store                                       # noqa: E402

PDF_WANTED = WANTED[:-5] + ".pdf"


def squash(text):
    return re.sub(r"\s+", "", text).casefold()


class PublishPure(unittest.TestCase):
    def test_request_keys_are_split_off_and_checked(self):
        req, rest = publish_pdf.split({"project": "PUB", "to_client": True, "pdf": True, "pdf_on_clash": "number"})
        self.assertEqual(rest, {"project": "PUB", "to_client": True})
        self.assertTrue(req["on"])
        self.assertIsNone(req["error"])
        self.assertFalse(publish_pdf.split({"project": "PUB"})[0]["on"])
        for bad in ({"pdf": "yes"}, {"pdf": 1}, {"pdf_on_clash": "sideways"}, {"pdf_new_name": 5},
                    {"pdf_on_clash": "overwrite"}, {"pdf_on_clash": "overwrite", "pdf_confirmed": "true"}):
            self.assertEqual(publish_pdf.split(bad)[0]["error"], "bad_pdf_request", bad)
        self.assertIsNone(publish_pdf.split({"pdf_on_clash": "overwrite", "pdf_confirmed": True})[0]["error"])

    def test_names(self):
        self.assertEqual(publish_pdf.pdf_name("PUB-report-2026-10-23.html"), "PUB-report-2026-10-23.pdf")
        self.assertEqual(publish_pdf.pdf_name("a (2).html"), "a (2).pdf")
        self.assertEqual(publish_pdf.rename_target(" Weekly "), "Weekly.pdf")
        self.assertEqual(publish_pdf.rename_target("Weekly.PDF"), "Weekly.PDF")
        for bad in ("", "  ", ".pdf", "x.", "a‮b"):
            self.assertIsNone(publish_pdf.rename_target(bad), bad)

    def test_a_taken_name_is_asked_about(self):
        class Fs:
            def __init__(self, entries):
                self.entries = entries

            def listdir(self, folder):
                return self.entries
        req = publish_pdf.split({})[0]
        free = Fs([{"name": "x.html", "kind": "file"}])
        self.assertEqual(publish_pdf.client_name(free, "/c", "x.html", False, req), ("write", "x.pdf", False))
        taken = Fs([{"name": "X.PDF", "kind": "file"}])
        kind, fields = publish_pdf.client_name(taken, "/c", "x.html", False, req)
        self.assertEqual((kind, fields["numbered"], fields["can_overwrite"]), ("ask", "x (2).pdf", True))
        self.assertEqual(publish_pdf.ask_reply(fields)["pdf"], True)
        number = publish_pdf.split({"pdf_on_clash": "number"})[0]
        self.assertEqual(publish_pdf.client_name(taken, "/c", "x.html", False, number), ("write", "x (2).pdf", False))
        over = publish_pdf.split({"pdf_on_clash": "overwrite", "pdf_confirmed": True})[0]
        self.assertEqual(publish_pdf.client_name(taken, "/c", "x.html", False, over), ("write", "X.PDF"[:0] + "x.pdf", True))
        self.assertEqual(publish_pdf.client_name(taken, "/c", "x.html", True, req), ("write", "x.pdf", True), "replaced with the report")
        folder = Fs([{"name": "x.pdf", "kind": "folder"}])
        self.assertEqual(publish_pdf.client_name(folder, "/c", "x.html", False, req)[0], "stop")

    def test_the_footer_has_the_publication_number_and_the_date(self):
        self.assertEqual(publish_pdf.footer_text("2026-10-28", 7), "Publication 7 \u00b7 28-10-2026")
        self.assertEqual(publish_pdf.footer_text("2026-10-28"), "Published 28-10-2026", "no number: the date alone")
        self.assertEqual(publish_pdf.footer_text("2026-10-28", True), "Published 28-10-2026", "a flag is not a number")
        self.assertNotIn("TODO", Path(publish_pdf.__file__).read_text(encoding="utf-8"))

    def test_the_pdfs_text_is_checked_for_dropped_markers_addresses_and_the_folder(self):
        def check(text, markers=(), folder=None):
            with mock.patch.object(pdftext, "text_of", return_value=text):
                return publish_pdf.problems(b"%PDF", list(markers), folder)
        self.assertEqual(check("All fine. ZQ-KEEP-1"), [])
        self.assertEqual(check("seen ZQ-HIDDEN-\nACTION here", ["ZQ-HIDDEN-ACTION"]), ["text that was meant to be left out"])
        self.assertEqual(check("zq-hidden-action", ["ZQ-HIDDEN-ACTION"]), ["text that was meant to be left out"])
        self.assertEqual(check('<a href="https://example.com/x">'), publish.outside_addresses('<a href="https://example.com/x">'))
        self.assertTrue(check('<a href="https://example.com/x">'), "the scan of the finished file runs on the PDF's text")
        self.assertEqual(check("in /Users/x/Client Folder/a", folder="/Users/x/Client Folder"), ["the location of the client folder"])
        self.assertEqual(check("  "), ["a PDF clark could not read back"], "an unreadable PDF is never clean")

    def test_available_says_why_not(self):
        with mock.patch.object(pdf, "find_chrome", return_value=None):
            got = publish_pdf.available()
        self.assertEqual(got, {"ok": False, "note": publish_pdf.NO_CHROME_LINE})
        with mock.patch.object(pdf, "find_chrome", return_value="/c"):
            self.assertEqual(publish_pdf.available(), {"ok": True, "note": ""})


from clark import publish                                          # noqa: E402


class PublishWithoutChrome(unittest.TestCase):
    def test_no_chrome_stops_before_anything_is_written(self):
        rig = Rig(self)
        with mock.patch.object(pdf, "find_chrome", return_value=None):
            status, got = rig.publish(to_client=True, pdf=True)
        self.assertEqual((status, got["ok"], got["code"]), (409, False, "no_chrome"))
        self.assertIn("Google Chrome", got["message"])
        self.assertEqual(rig.everything_written(), [])
        self.assertEqual(rig.rows(), [])

    def test_a_pdf_that_cannot_be_read_back_or_leaks_is_held_back_with_nothing_written(self):
        rig = Rig(self)
        with mock.patch.object(publish_pdf, "make", return_value=b"%PDF-1.4"), \
                mock.patch.object(pdftext, "text_of", return_value="seen ZQ-HIDDEN-ACTION here"):
            status, got = rig.publish(to_client=True, pdf=True)
        self.assertEqual((status, got["ok"]), (409, False))
        self.assertIn("The PDF was not made, because it would contain", got["message"])
        self.assertEqual(rig.everything_written(), [])
        self.assertEqual(rig.rows(), [])

    def test_without_the_tick_nothing_about_a_pdf_happens(self):
        rig = Rig(self)
        with mock.patch.object(publish_pdf, "make", side_effect=AssertionError("no PDF was asked for")):
            status, got = rig.publish(to_client=True)
        self.assertEqual((status, got["ok"]), (200, True))
        self.assertNotIn("pdf_name", got)
        self.assertEqual(rig.listing(rig.client), [WANTED])


class PublishRealChrome(unittest.TestCase):
    def test_the_pdf_holds_only_what_is_published(self):
        chrome = chrome_path()
        self.assertTrue(chrome, "Chrome is needed: set CLARK_CHROME or put google-chrome on the PATH")
        rig = Rig(self)
        status, got = rig.publish(to_client=True, pdf=True)
        self.assertEqual((status, got["ok"]), (200, True), got)
        local, client = rig.local / "chosen.pdf", rig.client / PDF_WANTED
        self.assertEqual(rig.listing(rig.client), sorted([WANTED, PDF_WANTED]))
        self.assertEqual(local.read_bytes(), client.read_bytes(), "the same bytes in both places")
        self.assertEqual((got["pdf_name"], got["message"].count("PDF ")), ("chosen.pdf", 2))
        self.assertEqual(len(rig.rows()), 1, "one publication, not one for the PDF")
        data = local.read_bytes()
        self.assertTrue(data.startswith(b"%PDF"))
        text = pdftext.text_of(data)
        squashed = squash(text)
        for key, marker in rig.plant["markers"].items():
            self.assertNotIn(squash(marker), squashed, f"{key} is in the PDF")
        for key in ("PUB-A-001", "PUB-A-002", "PUB-001", "PUB-M-001", "PUB-M-002", "text_section"):      # what the three tabs draw
            marker = rig.plant["kept_markers"][key]
            self.assertIn(squash(marker), squashed, f"{key} is missing from the PDF")
        self.assertEqual(publish.outside_addresses(text), [])
        self.assertNotIn(squash(str(rig.client)), squashed)
        for word in ("Dashboard", "Work items", "Milestones", "28-10-2026", "Page 1 of"):
            self.assertIn(word, text)
        self.assertIn("Published 28-10-2026", text, "the footer carries the date")
        self.assertNotIn("Filter by", text, "no controls")
        self.assertEqual(text.count("Programme notes"), 1, "the live page is not printed as well as the stack")
        # a taken name in the client folder is asked about first, and nothing is written for the question
        (rig.client / WANTED).unlink()            # the report's name is free, the PDF's is taken
        before = rig.everything_written()
        rig.save_to = rig.local / "second.html"
        status, ask = rig.publish(to_client=True, pdf=True)
        self.assertEqual((status, ask["ok"], ask.get("clash"), ask.get("pdf")), (200, False, True, True), ask)
        self.assertEqual(ask["numbered"], PDF_WANTED[:-4] + " (2).pdf")
        self.assertEqual(rig.everything_written(), before)
        status, again = rig.publish(to_client=True, pdf=True, pdf_on_clash="number")
        self.assertEqual((status, again["ok"]), (200, True), again)
        self.assertEqual((rig.client / (PDF_WANTED[:-4] + " (2).pdf")).read_bytes()[:4], b"%PDF")


class PublishedFileAndPdfCarryTheSame(unittest.TestCase):
    """Client safety: the PDF is printed from the published file, so every word it holds is a word the published file holds."""

    # What the print itself adds: the tab headings, the footer and the page counter.
    ADDED = {"dashboard", "items", "milestones", "published", "page", "work"}

    def test_every_word_in_the_pdf_is_in_the_published_file(self):
        chrome = chrome_path()
        self.assertTrue(chrome, "Chrome is needed: set CLARK_CHROME or put google-chrome on the PATH")
        rig = Rig(self)
        status, got = rig.publish(to_client=True, pdf=True)
        self.assertEqual((status, got["ok"]), (200, True), got)
        published = (rig.client / WANTED).read_bytes().decode("utf-8").casefold()
        text = pdftext.text_of((rig.client / PDF_WANTED).read_bytes())
        words = {w.casefold() for w in re.findall(r"[^\W\d_]{4,}", text)}
        self.assertTrue(words, "the PDF has words")
        extra = sorted(w for w in words - self.ADDED if w not in published)
        self.assertEqual(extra, [], "words in the PDF that the published file does not hold")
        # and the other way for what was planted: dropped text is in neither
        for key, marker in rig.plant["markers"].items():
            self.assertNotIn(marker.casefold(), published, f"{key} is in the published file")
            self.assertNotIn(squash(marker), squash(text), f"{key} is in the PDF")

    def test_the_pdf_is_made_from_exactly_the_bytes_that_are_published(self):
        rig = Rig(self)
        seen = []

        def make(body_bytes, as_at, orientation="portrait", make_pdf=None, number=None):
            seen.append(body_bytes)
            return b"%PDF-1.4\n"
        with mock.patch.object(publish_pdf, "make", make), mock.patch.object(pdftext, "text_of", return_value="All fine."):
            status, got = rig.publish(to_client=True, pdf=True)
        self.assertEqual((status, got["ok"]), (200, True), got)
        self.assertEqual(seen, [(rig.client / WANTED).read_bytes()])
        self.assertEqual(seen, [(rig.local / "chosen.html").read_bytes()])


class PdfClientCopyIsChecked(unittest.TestCase):
    """The PDF reaches the client folder only through to_client.copy_to_client, with the report's own checks."""

    GOOD = b"%PDF-1.4\n1 0 obj<</Title (Weekly report)>>endobj\n"

    def run_it(self, rig, data, text="Programme"):
        with mock.patch.object(publish_pdf, "make", return_value=data), mock.patch.object(pdftext, "text_of", return_value=text):
            return rig.publish(to_client=True, pdf=True)

    def test_a_forbidden_word_in_the_pdfs_details_stops_it_being_written(self):
        for label, info in (("plain", b"(seen ZQ-HIDDEN-ACTION here)"),
                            ("utf16", "﻿seen ZQ-HIDDEN-ACTION".encode("utf-16-be").hex().join((b"<".decode(), ">")).encode()),
                            ("address", b'(<a href="https://example.com/x">)')):
            rig = Rig(self)
            data = b"%PDF-1.4\n1 0 obj<</Title " + info + b">>endobj\n"
            status, got = self.run_it(rig, data)
            self.assertEqual((status, got["ok"]), (409, False), label)
            self.assertIn("The PDF was not made, because it would contain", got["message"], label)
            self.assertEqual(rig.everything_written(), [], label)

    def test_a_pdf_over_the_size_limit_is_held_back(self):
        rig = Rig(self)
        status, got = self.run_it(rig, self.GOOD + b"0" * (publish.MAX_BYTES + 1))
        self.assertEqual((status, got["ok"]), (409, False))
        self.assertEqual(rig.everything_written(), [])

    def test_a_pdf_copy_that_does_not_read_back_is_taken_back(self):
        rig = Rig(self)
        real = to_client.RealFs.read_bytes

        seen = []

        def odd(fs, path, limit=None):             # only the read-back is wrong; the proof the file is ours is not
            data = real(fs, path, limit)
            if Path(path).suffix == ".pdf" and Path(path).parent.name == rig.client.name and not seen:
                seen.append(1)
                return data + b"x"
            return data
        with mock.patch.object(to_client.RealFs, "read_bytes", odd):
            status, got = self.run_it(rig, self.GOOD)
        self.assertEqual(rig.listing(rig.client), [WANTED], "the PDF is not left in the client folder")
        self.assertIn("not saved", got["message"])

    def test_the_folder_being_swapped_stops_the_pdf(self):
        rig = Rig(self)
        calls = []

        def swapped(fs, folder, guard):
            calls.append(1)
            return "changed" if len(calls) > 1 else None          # the report's copy passes; the PDF's check sees a swap
        with mock.patch.object(to_client, "folder_unchanged", swapped):
            status, got = self.run_it(rig, self.GOOD)
        self.assertEqual(len(calls), 2, "the folder is looked at again before the PDF is written")
        self.assertEqual(rig.listing(rig.client), [WANTED])

    def test_the_plain_words_are_pinned(self):
        M = publish_pdf.MESSAGES
        self.assertEqual(publish_pdf.NO_CHROME_LINE, "A PDF needs Google Chrome, and clark could not find it on this computer. Install Chrome to use this.")
        self.assertEqual(M["bad_pdf_request"], "Something is wrong inside clark. Nothing was published. Reload the page and try again; if it keeps happening, tell the clark team.")
        self.assertEqual(M["pdf_held_back"], "The PDF was not made, because it would contain {what}. Nothing was published. Leave the PDF box unticked, or tell the clark team.")
        self.assertEqual(M["pdf_not_checked"], "The PDF could not be checked, so it was not made. Nothing was published. Try once more; if it fails again, leave the PDF box unticked.")
        self.assertEqual(M["pdf_too_big"], "The PDF is too big to check, so it was not made. Nothing was published. Leave the PDF box unticked.")
        self.assertEqual(M["pdf_local_not_pdf"], "Choose a name that ends in .pdf. Nothing was published.")
        self.assertEqual(M["pdf_overwrite_note"], "The PDF in the client folder will be replaced. The old PDF will be gone.")
        self.assertEqual(M["why_held"], "the PDF was held back, so nothing was copied.")
        self.assertEqual(M["why_changed"], "the client folder changed while it was being written to, so nothing was copied.")
        self.assertEqual(M["pdf_not_saved"].format(why=M["why_local_failed"]),
                         "The PDF was not saved: the folder you chose could not be written to. Choose a folder you can save in and publish again. The report itself is published.")
        self.assertEqual(M["pdf_not_saved"].format(why=M["why_failed"]),
                         "The PDF was not saved: the client folder could not be written to. Check you can edit it. The report itself is published.")
        self.assertEqual(publish_pdf.SAME_BYTES, "The PDF could not be made from the report as it is. Try again; if it keeps happening, leave the PDF box unticked.")
        self.assertEqual(pdf.CANNOT_CLEAN, "The PDF could not be made safe to share, so it was not made. Leave the PDF box unticked and publish again.")

    def test_a_refused_copy_is_told_by_its_own_cause(self):
        TC = publish_pdf.to_client.MESSAGES
        for key, fill, want in (("held_back", {"what": "x"}, "why_held"), ("name_appeared", {"name": "a.pdf"}, "why_taken"),
                                ("not_plain_file", {"name": "a.pdf"}, "why_not_plain"), ("not_same_file", {}, "why_not_same"),
                                ("folder_changed", {}, "why_changed")):
            self.assertEqual(publish_pdf.refused_why(TC[key].format(**fill)), publish_pdf.MESSAGES[want], key)
        self.assertEqual(publish_pdf.refused_why("something else"), publish_pdf.MESSAGES["why_refused"])

    def test_the_wording_never_starts_with_the_product_name(self):
        for text in list(publish_pdf.MESSAGES.values()) + [publish_pdf.NO_CHROME_LINE]:
            self.assertFalse(text.lower().startswith("clark"), text)

    def test_the_pdf_module_never_writes_into_the_client_folder_itself(self):
        import ast
        tree = ast.parse(Path(publish_pdf.__file__).read_text(encoding="utf-8"))
        writers = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr in ("write_file", "write_file_unless_exists")
                   and not (isinstance(n.value, ast.Name) and n.value.id == "platform")]
        self.assertEqual(writers, [], "the client folder is written only by to_client.copy_to_client")


# ===== The review of the PDF checks: the second check, the size and speed of the reader, fonts, order, the fallback =====
import subprocess as _subprocess                                    # noqa: E402
import sys as _sys                                                  # noqa: E402


def tiny_pdf(content, font_map=True, extra=b""):
    """A small PDF by hand: font F1 with a map (code 0x0101 is A, 0x0102 is B), font F2 with no map, and one content stream."""
    cmap = b"1 beginbfchar\n<0101> <0041>\n<0102> <0042>\nendbfchar\n"
    parts = [b"1 0 obj\n<< /Font << /F1 2 0 R /F2 4 0 R >> >>\nendobj\n",
             b"2 0 obj\n<< /Type /Font /ToUnicode 3 0 R >>\nendobj\n" if font_map else b"2 0 obj\n<< /Type /Font >>\nendobj\n",
             b"3 0 obj\n<< /Length %d >>\nstream\n%s\nendstream\nendobj\n" % (len(cmap), cmap),
             b"4 0 obj\n<< /Type /Font >>\nendobj\n",
             b"5 0 obj\n<< /Length %d >>\nstream\n%s\nendstream\nendobj\n" % (len(content), content), extra]
    return b"%PDF-1.4\n" + b"".join(parts)


class TheReviewOfThePdfChecks(unittest.TestCase):
    def test_a_pdf_with_text_in_a_font_that_has_a_map_is_read_and_clean(self):
        data = tiny_pdf(b"BT /F1 12 Tf <01010102> Tj ET")
        self.assertEqual(pdftext.text_of(data), "AB")
        self.assertEqual(publish_pdf.problems(data, ["ZQ-HIDDEN"]), [])

    def test_text_in_a_font_with_no_map_is_never_taken_as_clean(self):
        hidden = tiny_pdf(b"BT /F1 12 Tf <01010102> Tj ET BT /F2 12 Tf <5a512d48> Tj ET")      # visible text beside text that cannot be read
        self.assertEqual(publish_pdf.problems(hidden, []), ["a PDF clark could not read back"])
        nomap = tiny_pdf(b"BT /F1 12 Tf <01010102> Tj ET", font_map=False)
        self.assertEqual(publish_pdf.problems(nomap, []), ["a PDF clark could not read back"])

    def test_a_glyph_the_map_does_not_cover_is_never_taken_as_clean(self):
        data = tiny_pdf(b"BT /F1 12 Tf <010101030102> Tj ET")
        self.assertEqual(publish_pdf.problems(data, []), ["a PDF clark could not read back"])

    def test_a_stream_that_inflates_past_the_limit_is_refused_plainly(self):
        bomb = zlib.compress(b"\0" * (80 * 1024 * 1024))
        extra = b"6 0 obj\n<< /Filter /FlateDecode /Length %d >>\nstream\n%s\nendstream\nendobj\n" % (len(bomb), bomb)
        data = tiny_pdf(b"BT /F1 12 Tf <0101> Tj ET", extra=extra)
        self.assertLess(len(data), publish.MAX_BYTES, "it is small on disk: only the inflating is the danger")
        self.assertEqual(publish_pdf.problems(data, []), ["a PDF too big to check"])
        self.assertEqual(publish_pdf.MESSAGES["pdf_too_big"],
                         "The PDF is too big to check, so it was not made. Nothing was published. Leave the PDF box unticked.")

    def test_hostile_text_cannot_make_the_reader_hang(self):
        script = ("import sys\nfrom clark import pdf_text\ndata = open(sys.argv[1], 'rb').read()\n"
                  "try:\n    pdf_text.text_of(data)\nexcept Exception:\n    pass\n")
        for label, content in (("brackets and line breaks", b"BT /F1 12 Tf [" + b"\n" * 80 + b" ET"),
                               ("a great many open brackets", b"BT /F1 12 Tf " + b"[" * 400000 + b" ET"),
                               ("a long run of hex with no end", b"BT /F1 12 Tf <" + b"0a" * 400000 + b" ET")):
            with tempfile.TemporaryDirectory() as d:
                f = Path(d) / "h.pdf"
                f.write_bytes(tiny_pdf(content))
                try:
                    done = _subprocess.run([_sys.executable, "-c", script, str(f)], timeout=60, capture_output=True,
                                           env=dict(os.environ, PYTHONPATH=str(ROOT / "src")))
                except _subprocess.TimeoutExpired:
                    self.fail("the reader hung on " + label)
                self.assertEqual(done.returncode, 0, label + ": " + done.stderr.decode()[-300:])

    def test_the_second_check_runs_after_the_first_and_never_instead_of_it(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            leak = tiny_pdf(b"BT ET") + b"ZQ-INTERNAL"
            got = to_client.copy_to_client(to_client.RealFs(), folder, "a.pdf", leak, project="PUB", at="2026-10-28",
                                           markers=["zq-internal"], extra_problems=lambda data: [])
            self.assertEqual((got.ok, got.action), (False, "refused"), "an empty second check turns nothing off")
            got = to_client.copy_to_client(to_client.RealFs(), folder, "b.pdf", tiny_pdf(b"BT ET"), project="PUB", at="2026-10-28",
                                           markers=["zq-internal"], extra_problems=lambda data: ["a second reason"])
            self.assertEqual((got.ok, got.action), (False, "refused"))
            self.assertEqual(list(folder.iterdir()), [])
            got = to_client.copy_to_client(to_client.RealFs(), folder, "c.pdf", tiny_pdf(b"BT ET"), project="PUB", at="2026-10-28",
                                           markers=["zq-internal"], extra_problems=lambda data: [])
            self.assertTrue(got.ok)

    def test_the_pdf_is_not_made_when_the_report_will_be_refused(self):
        for label, name_for in (("not .html", lambda rig: rig.local / "chosen.txt"),
                                ("clark's own folder", lambda rig: rig.data_dir / "x.html"),
                                ("the client folder", lambda rig: rig.client / "x.html")):
            rig = Rig(self)
            rig.save_to = name_for(rig)
            (rig.save_to.with_suffix(".pdf")).parent.mkdir(parents=True, exist_ok=True)
            if rig.save_to.parent == rig.local:
                rig.save_to.with_suffix(".pdf").write_bytes(b"%PDF-old")           # a second Save window would open for this
            with mock.patch.object(pdf, "find_chrome", return_value="/c"), \
                    mock.patch.object(publish_pdf, "make", side_effect=AssertionError("made before the refusals")):
                status, got = rig.publish(to_client=False, pdf=True)
            self.assertEqual((status, got["ok"]), (409, False), label)
            self.assertIn(got["code"], ("local_not_html", "local_clark_files", "same_folder"), label)
            self.assertEqual(len(rig.saves), 1, label + ": no second Save window")

    def test_the_fallback_prints_the_same_footer(self):
        seen = []

        class Gone:
            returncode = 1
            pid = 2 ** 22 + 5

            def poll(self):
                return 1

            def wait(self, t=None):
                return 1

        class Done(Gone):
            returncode = 0

        def fake(args, **k):
            flag = [a for a in args if a.startswith("--print-to-pdf=")]
            if not flag:
                return Gone()
            Path(flag[0].split("=", 1)[1]).write_bytes(build_pdf({1: b"<</Type /Catalog /Pages 2 0 R>>", 2: b"<</Type /Pages /Kids [] /Count 0>>"}))          # a small, whole PDF
            seen.append(Path(args[-1][len("file://"):].replace("%20", " ")).read_text(encoding="utf-8"))
            return Done()
        with tempfile.TemporaryDirectory() as d:
            page = Path(d) / "p.html"
            page.write_text(PAGE, encoding="utf-8")
            pdf.make_pdf(page, Path(d) / "o.pdf", chrome="/x", timeout=5, popen=fake, footer_left="Publication 4 · 28-10-2026 <b>")
            pdf.make_pdf(page, Path(d) / "o2.pdf", chrome="/x", timeout=5, popen=fake)
        self.assertIn("Publication 4 · 28-10-2026 &lt;b&gt;", seen[0])
        self.assertNotIn("<b>", seen[0], "the footer text is escaped")
        self.assertTrue(seen[0].index("Publication 4") < seen[0].rindex("</body>"))
        self.assertNotIn("Publication", seen[1], "no footer asked for, none added")



# ===== The second review of the PDF option: same bytes, an allow-list of words, streams that will not inflate, the raw check =====
class TheSecondReview(unittest.TestCase):
    def test_the_page_printed_must_be_the_bytes_published(self):
        body = b"<html><body>the report</body></html>"
        called = []
        real = Path.write_bytes

        def drifting(self, data):
            return real(self, data + b" ")          # the copy on disk is not what was handed over
        with mock.patch.object(Path, "write_bytes", drifting):
            with self.assertRaises(pdf.PdfError) as caught:
                publish_pdf.make(body, "2026-10-28", make_pdf=lambda *a, **k: called.append(1))
        self.assertEqual(called, [], "nothing is printed from a copy that differs")
        self.assertEqual(str(caught.exception), publish_pdf.SAME_BYTES)
        seen = []
        publish_pdf.make(body, "2026-10-28", make_pdf=lambda page, out, *a, **k: (seen.append(Path(page).read_bytes()), Path(out).write_bytes(b"%PDF"))[1] and Path(out))
        self.assertEqual(seen, [body])

    def test_extra_words_are_found_and_the_footer_and_headings_are_allowed(self):
        body = "<p>Harbour crossing plan</p> caf\\u00e9 &amp; bar".encode()
        self.assertEqual(publish_pdf.extra_words("Harbour crossing PLAN Published Page Dashboard Work items Milestones", body), [])
        self.assertEqual(publish_pdf.extra_words("Harbour zzextra crossing", body), ["zzextra"])
        self.assertEqual(publish_pdf.extra_words("caf\u00e9", body), [], "an escaped letter in the file is the same letter")
        for text, extra in (("Harbour crossing", False), ("Harbour crossing zzextra", True)):
            with mock.patch.object(pdftext, "text_of", return_value=text):
                got = publish_pdf.problems(b"%PDF-1.4", [], None, body)
            self.assertEqual(got, [publish_pdf.EXTRA_WORDS] if extra else [], text)
        with mock.patch.object(pdftext, "text_of", return_value="Harbour zzextra"):
            self.assertEqual(publish_pdf.problems(b"%PDF-1.4", []), [], "no file to compare with: only the other checks")

    def test_a_pdf_with_a_word_the_report_does_not_hold_is_refused_with_nothing_written(self):
        rig = Rig(self)
        with mock.patch.object(publish_pdf, "make", return_value=b"%PDF-1.4"), \
                mock.patch.object(pdftext, "text_of", return_value="Programme zzstrangeword"):
            status, got = rig.publish(to_client=True, pdf=True)
        self.assertEqual((status, got["ok"]), (409, False))
        self.assertIn("words that are not in the published report", got["message"])
        self.assertEqual(rig.everything_written(), [])

    def test_real_chrome_a_page_with_an_added_word_is_refused(self):
        chrome = chrome_path()
        self.assertTrue(chrome, "Chrome is needed: set CLARK_CHROME or put google-chrome on the PATH")
        rig = Rig(self)
        real = publish_pdf.make

        def other(body, *a, **k):          # prints a page that is not the published one
            self.assertIn(b"</body>", body)
            return real(body.replace(b"</body>", b"<p>Zzsneakedin wording</p></body>", 1), *a, **k)
        with mock.patch.object(publish_pdf, "make", other):
            status, got = rig.publish(to_client=True, pdf=True)
        self.assertEqual((status, got["ok"]), (409, False), got)
        self.assertIn("words that are not in the published report", got["message"])
        self.assertEqual(rig.everything_written(), [])

    def test_a_stream_that_will_not_inflate_is_never_skipped(self):
        for label, stream in (("broken", b"xxxxxxxxxxxx"), ("cut short", zlib.compress(b"BT /F1 12 Tf <0101> Tj ET" * 50)[:-6])):
            extra = b"6 0 obj\n<< /Filter /FlateDecode /Length %d >>\nstream\n%s\nendstream\nendobj\n" % (len(stream), stream)
            data = tiny_pdf(b"BT /F1 12 Tf <0101> Tj ET", extra=extra)
            with self.assertRaises(pdftext.Undecodable, msg=label):
                pdftext.text_of(data)
            self.assertEqual(publish_pdf.problems(data, []), [publish_pdf.UNREADABLE], label)

    def test_the_local_pdf_gets_the_raw_byte_check_too(self):
        rig = Rig(self)          # no To client: only the Local copy is made
        raw = b"%PDF-1.4\n1 0 obj<</Note (<a href=\"https://example.com/x\">)>>endobj\n"
        with mock.patch.object(publish_pdf, "make", return_value=raw), \
                mock.patch.object(pdftext, "text_of", return_value="Programme"):
            status, got = rig.publish(pdf=True)
        self.assertEqual((status, got["ok"]), (409, False), got)
        self.assertIn("The PDF was not made, because it would contain", got["message"])
        self.assertEqual(rig.everything_written(), [])

    def test_a_fault_while_making_or_checking_is_a_plain_refusal(self):
        for error in (OSError("disk"), ValueError("odd")):
            for where in ("make", "text_of"):
                rig = Rig(self)
                if where == "make":
                    first = mock.patch.object(publish_pdf, "make", side_effect=error)
                    second = mock.patch.object(pdftext, "text_of", return_value="Programme")
                else:
                    first = mock.patch.object(publish_pdf, "make", return_value=b"%PDF-1.4")
                    second = mock.patch.object(pdftext, "text_of", side_effect=error)
                with first, second:
                    status, got = rig.publish(to_client=True, pdf=True)
                self.assertEqual((status, got["ok"], got["code"]), (409, False, "pdf_failed"), (where, error))
                self.assertIn("Nothing was published.", got["message"])
                self.assertNotIn("Traceback", got["message"])
                self.assertEqual(rig.everything_written(), [])



# ===== The PDF carries nothing about this computer or its browser =====
LEAKS = ("Mozilla", "AppleWebKit", "Chrome", "Macintosh", "Intel", "HeadlessChrome", "Skia", "Gecko", "KHTML", "Safari")
ALLOWED_INFO = {"Title", "Creator", "Producer"}


def streams_of(data):
    """The raw PDF and every stream of it, inflated where it is Flate, as text to search."""
    found = [data.decode("latin-1")]
    for _num, (head, raw) in pdftext.objects(data).items():
        found.append(head.decode("latin-1"))
        if raw is not None:
            found.append(raw.decode("latin-1"))
    return found


def info_of(data):
    """{key: value text} of the Info dictionary the trailer points at, read the plain way."""
    trailer = data[data.rfind(b"trailer"):]
    num = int(re.search(rb"/Info\s+(\d+)\s+0\s+R", trailer).group(1))
    body = re.search(rb"(?<![0-9])%d\s+0\s+obj(.*?)endobj" % num, data, re.S).group(1)
    return {m.group(1).decode(): m.group(2) for m in re.finditer(rb"/([A-Za-z]+)\s*(\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f]*>|[^/>\s]+)", body)}


def build_pdf(objects, root=1, info=None, extra_trailer=b""):
    """A PDF by hand from {number: object body}, with a true cross-reference table."""
    out, at, offsets = b"%PDF-1.4\n%\xd3\xeb\xe9\xe1\n", None, {}
    for num in sorted(objects):
        offsets[num] = len(out)
        out += b"%d 0 obj\n%s\nendobj\n" % (num, objects[num])
    size = max(objects) + 1
    start = len(out)
    table = b"0000000000 65535 f \n" + b"".join(b"%010d 00000 n \n" % offsets[n] if n in offsets else b"0000000000 00000 f \n" for n in range(1, size))
    trailer = b"<</Size %d\n/Root %d 0 R\n%s%s>>" % (size, root, b"/Info %d 0 R\n" % info if info else b"", extra_trailer)
    return out + b"xref\n0 %d\n" % size + table + b"trailer\n" + trailer + b"\nstartxref\n%d\n%%%%EOF\n" % start


class PdfDetailsAreNeutral(unittest.TestCase):
    PAGE = "<html><head><title>Weekly &amp; report</title></head><body><h1>Harbour plan</h1><p>Some text.</p></body></html>"

    def printed(self, d):
        chrome = chrome_path()
        self.assertTrue(chrome, "Chrome is needed: set CLARK_CHROME or put google-chrome on the PATH")
        page = Path(d) / "page.html"
        page.write_text(self.PAGE, encoding="utf-8")
        return pdf.make_pdf(page, Path(d) / "out.pdf", chrome=chrome, footer_left="Published 01-01-2026").read_bytes()

    def check_clean(self, data):
        for where in streams_of(data):
            for leak in LEAKS:
                self.assertNotIn(leak.casefold(), where.casefold(), f"{leak} is in the PDF")
        self.assertNotIn(b"/Metadata", data)
        self.assertNotIn(b"/ID", data[data.rfind(b"trailer"):])
        got = info_of(data)
        self.assertEqual(set(got), ALLOWED_INFO, "the Info dictionary holds only what is allowed")
        self.assertEqual((got["Creator"], got["Producer"]), (b"(clark)", b"(clark)"))
        self.assertEqual(got["Title"], b"(Weekly & report)")
        text = pdftext.text_of(data)                  # and it still reads, so the table and the objects are in order
        self.assertIn("Harbour plan", text)
        starts = [int(m.group(1)) for m in re.finditer(rb"(\d{10}) 00000 n", data)]
        self.assertTrue(starts)
        for off in starts:
            self.assertRegex(data[off:off + 12], rb"^\d+ 0 obj")
        self.assertTrue(data[int(re.findall(rb"startxref\s+(\d+)", data)[-1]):].startswith(b"xref"))

    def test_real_chrome_pdf_has_no_details_about_this_computer(self):
        with tempfile.TemporaryDirectory() as d:
            self.check_clean(self.printed(d))

    def test_real_chrome_unscrubbed_pdf_does_have_them(self):
        """The reason for the step: without it Chrome's own PDF carries the browser's name and the computer's kind."""
        with tempfile.TemporaryDirectory() as d, mock.patch.object(pdf, "scrub", lambda data, title="": data):
            raw = self.printed(d)
        self.assertTrue(any(leak in "".join(streams_of(raw)) for leak in LEAKS))

    def test_the_published_pdf_in_both_places_is_clean(self):
        chrome = chrome_path()
        self.assertTrue(chrome)
        rig = Rig(self)
        status, got = rig.publish(to_client=True, pdf=True)
        self.assertEqual((status, got["ok"]), (200, True), got)
        for path in (rig.local / "chosen.pdf", rig.client / PDF_WANTED):
            data = path.read_bytes()
            for where in streams_of(data):
                for leak in LEAKS:
                    self.assertNotIn(leak.casefold(), where.casefold(), f"{leak} is in {path.name}")
            self.assertEqual(set(info_of(data)), ALLOWED_INFO)
            self.assertNotIn(b"/Metadata", data)

    def test_xmp_metadata_is_emptied_and_unpointed(self):
        xmp = b"<</Type /Metadata /Subtype /XML /Length 40>>\nstream\n<x:xmpmeta>Mozilla/5.0 HeadlessChrome</x:xmpmeta>\nendstream"
        data = build_pdf({1: b"<</Type /Catalog /Pages 2 0 R /Metadata 4 0 R>>",
                          2: b"<</Type /Pages /Kids [] /Count 0>>",
                          3: b"<</Creator (Mozilla/5.0 Macintosh) /Producer (Skia/PDF) /Author (Someone) /CreationDate (D:20261101)>>",
                          4: xmp}, root=1, info=3, extra_trailer=b"/ID [<00><00>]\n")
        out = pdf.scrub(data, "A title")
        for leak in ("Mozilla", "HeadlessChrome", "Macintosh", "Skia", "Someone", "xmpmeta", "CreationDate", "/ID"):
            self.assertNotIn(leak.encode(), out, leak)
        self.assertNotIn(b"/Metadata", out)
        self.assertEqual(set(info_of(out)), ALLOWED_INFO)
        self.assertEqual(info_of(out)["Title"], b"(A title)")
        offsets = [int(m.group(1)) for m in re.finditer(rb"(\d{10}) 00000 n", out)]
        self.assertEqual(len(offsets), 4)
        for num, off in zip((1, 2, 3, 4), offsets):
            self.assertTrue(out[off:].startswith(b"%d 0 obj" % num), num)

    def test_a_title_is_written_safely_and_a_missing_one_is_neutral(self):
        base = build_pdf({1: b"<</Type /Catalog /Pages 2 0 R>>", 2: b"<</Type /Pages /Kids [] /Count 0>>", 3: b"<</Creator (x)>>"}, info=3)
        self.assertEqual(info_of(pdf.scrub(base, "a (b) \\ c"))["Title"], b"(a \\(b\\) \\\\ c)")
        self.assertTrue(info_of(pdf.scrub(base, "Caf\u00e9"))["Title"].startswith(b"<FEFF"))
        self.assertEqual(pdf.title_of("<p>no title</p>"), pdf.CLEAN_TITLE)
        self.assertEqual(pdf.title_of("<title> A &amp;\n B </title>"), "A & B")
        no_info = build_pdf({1: b"<</Type /Catalog /Pages 2 0 R>>", 2: b"<</Type /Pages /Kids [] /Count 0>>"})
        self.assertEqual(set(info_of(pdf.scrub(no_info, "T"))), ALLOWED_INFO, "an Info dictionary is added when there was none")

    def test_a_file_of_an_unusual_shape_is_refused_in_plain_words(self):
        for bad in (b"%PDF-1.4\nnothing here", b"%PDF-1.7\nstartxref\n5\n%%EOF", b""):
            with self.assertRaises(pdf.PdfError) as caught:
                pdf.scrub(bad)
            self.assertEqual(str(caught.exception), pdf.CANNOT_CLEAN)



# ===== The third review: files that cannot be rewritten whole, plain words, the temporary copy, memory faults =====
class TheThirdReview(unittest.TestCase):
    CATALOG = {1: b"<</Type /Catalog /Pages 2 0 R>>", 2: b"<</Type /Pages /Kids [] /Count 0>>", 3: b"<</Creator (x)>>"}

    def test_a_trailer_that_cannot_be_rewritten_is_refused_whole(self):
        for key in (b"/Encrypt 9 0 R\n", b"/Prev 120\n", b"/XRefStm 77\n"):
            data = build_pdf(self.CATALOG, info=3, extra_trailer=key)
            with self.assertRaises(pdf.PdfError, msg=key) as caught:
                pdf.scrub(data)
            self.assertEqual(str(caught.exception), pdf.CANNOT_CLEAN)
        pdf.scrub(build_pdf(self.CATALOG, info=3))          # the same file without them is fine

    def test_a_file_with_a_cross_reference_stream_is_refused(self):
        body = b"%PDF-1.5\n1 0 obj\n<</Type /Catalog>>\nendobj\n5 0 obj\n<</Type /XRef /Size 6 /W [1 2 1] /Root 1 0 R /Length 0>>\nstream\n\nendstream\nendobj\n"
        data = body + b"startxref\n%d\n%%%%EOF\n" % body.index(b"5 0 obj")
        with self.assertRaises(pdf.PdfError) as caught:
            pdf.scrub(data)
        self.assertEqual(str(caught.exception), pdf.CANNOT_CLEAN)

    def test_only_the_transient_refusal_says_try_again(self):
        self.assertNotIn("Try again", pdf.CANNOT_CLEAN)
        self.assertIn("Try again", publish_pdf.SAME_BYTES)
        self.assertTrue(pdf.CANNOT_CLEAN.endswith("unticked and publish again."))

    def test_memory_and_recursion_faults_are_plain_refusals(self):
        data = build_pdf(self.CATALOG, info=3)
        for error in (MemoryError(), RecursionError()):
            with mock.patch.object(pdf.re, "findall", side_effect=error):
                with self.assertRaises(pdf.PdfError, msg=repr(error)) as caught:
                    pdf.scrub(data)
            self.assertEqual(str(caught.exception), pdf.CANNOT_CLEAN)
            with mock.patch.object(pdftext, "text_of", side_effect=error):
                self.assertEqual(publish_pdf.problems(b"%PDF-1.4", []), [publish_pdf.UNREADABLE], repr(error))
            rig = Rig(self)
            with mock.patch.object(publish_pdf, "make", side_effect=error):
                status, got = rig.publish(pdf=True)
            self.assertEqual((status, got["ok"], got["code"]), (409, False, "pdf_failed"), repr(error))
            self.assertIn("Nothing was published.", got["message"])
            self.assertEqual(rig.everything_written(), [])

    def test_the_local_pdf_is_read_back_from_the_temporary_copy_before_it_replaces_anything(self):
        with tempfile.TemporaryDirectory() as d:
            local = Path(d) / "kept.pdf"
            local.write_bytes(b"%PDF-earlier")
            step = publish_pdf.Step(publish_pdf.split({"pdf": True})[0], None)
            step.data, step.local, step.local_replaces = b"%PDF-1.4 new", local, True          # the Save window asked, and was answered yes
            real = platform._write_temp

            def wrong(dest, data):                  # the temporary copy comes out different from what was handed over
                return real(dest, data + b"!")
            with mock.patch.object(platform, "_write_temp", wrong):
                said = step.write(None)
            self.assertEqual(local.read_bytes(), b"%PDF-earlier", "a copy that does not match never replaces the earlier file")
            self.assertIn("was not saved", " ".join(said))
            self.assertEqual(sorted(p.name for p in Path(d).iterdir()), ["kept.pdf"], "no temporary file is left")
            said = step.write(None)
            self.assertEqual(local.read_bytes(), b"%PDF-1.4 new")
            self.assertEqual(sorted(p.name for p in Path(d).iterdir()), ["kept.pdf"])


class TheReviewFindings(unittest.TestCase):
    """The PDF at the route: a same-name PDF, a failed save, the same report already there, a name that appears, Local only."""
    GOOD = b"%PDF-1.4\n1 0 obj<</Title (Weekly report)>>endobj\n"
    OLDER = b"<!doctype html>a different earlier file"

    def setUp(self):
        self.rig = Rig(self)
        self.rig.publish(to_client=True)          # Local "chosen.html" and the client's copy of the report
        self.rig.saves.clear()
        self.report = self.rig.client / WANTED
        self.client_pdf = self.rig.client / PDF_WANTED
        self.rig.save_to = self.rig.local / "second.html"
        self.before = self.rig.everything_written()

    def go(self, text="Programme", before=None, **body):
        """Publish with Chrome faked: `before` runs as the PDF is made (after every check of the names)."""
        def make_it(*a, **k):
            if before is not None:
                before()
            return self.GOOD
        with mock.patch.object(pdf, "find_chrome", return_value="/c"), mock.patch.object(publish_pdf, "make", make_it), \
                mock.patch.object(pdftext, "text_of", return_value=text):
            return self.rig.publish(**body)

    def test_replacing_the_report_says_a_pdf_of_that_name_goes_too_and_it_does(self):
        self.report.write_bytes(self.OLDER)
        self.client_pdf.write_bytes(b"%PDF-earlier")
        before = self.rig.everything_written()
        status, got = self.go(to_client=True, pdf=True)
        self.assertEqual((status, got["ok"], got["code"], got["can_overwrite"]), (200, False, "ask", True))
        self.assertIn(publish_pdf.MESSAGES["pdf_overwrite_note"], got["note"])
        self.assertIn("The PDF in the client folder will be replaced. The old PDF will be gone.", got["note"])
        self.assertEqual((self.client_pdf.read_bytes(), self.rig.everything_written()), (b"%PDF-earlier", before), "the question writes nothing")
        status, got = self.go(to_client=True, pdf=True, on_clash="overwrite", confirmed=True)
        self.assertEqual((status, got["ok"], got["pdf_saved"]), (200, True, True), got)
        self.assertEqual(self.client_pdf.read_bytes(), self.GOOD)

    def test_the_pdf_warning_is_only_shown_when_there_is_a_pdf_to_replace(self):
        self.report.write_bytes(self.OLDER)
        for label, ticked, there in (("no tick", False, True), ("no such PDF", True, False)):
            if there:
                self.client_pdf.write_bytes(b"%PDF-earlier")
            elif self.client_pdf.exists():
                self.client_pdf.unlink()
            status, got = self.go(to_client=True, pdf=True) if ticked else self.rig.publish(to_client=True)
            self.assertEqual(got["code"], "ask", label)
            self.assertNotIn("PDF", got["note"], label)

    def test_a_pdf_that_was_not_saved_is_said_in_the_reply_and_has_no_name(self):
        real = platform._write_temp

        def failing(dest, data):
            if str(dest).endswith(".pdf"):
                raise OSError("disk")
            return real(dest, data)
        with mock.patch.object(platform, "_write_temp", failing):
            status, got = self.go(to_client=False, pdf=True)
        self.assertEqual((status, got["ok"], got["pdf_saved"]), (200, True, False), got)
        self.assertNotIn("pdf_name", got)
        self.assertIn(publish_pdf.MESSAGES["pdf_not_saved"].format(why=publish_pdf.MESSAGES["why_local_failed"]), got["message"])
        self.assertEqual(sorted(p.name for p in self.rig.local.iterdir()), ["chosen.html", "second.html"])

    def test_a_fault_while_saving_the_pdf_never_turns_a_published_report_into_a_failure(self):
        def boom(step, pub, with_client=True):
            raise RuntimeError("secret detail /private/path")
        with mock.patch.object(publish_pdf.Step, "write", boom):
            status, got = self.go(to_client=False, pdf=True)
        self.assertEqual((status, got["ok"], got["pdf_saved"]), (200, True, False), got)
        self.assertNotIn("pdf_name", got)
        self.assertIn(publish_pdf.MESSAGES["pdf_not_saved"].format(why=publish_pdf.MESSAGES["why_fault"]), got["message"])
        self.assertNotIn("secret detail", got["message"])
        self.assertNotIn("RuntimeError", got["message"])
        self.assertEqual(len(self.rig.rows()), 2, "the report is published and recorded")
        self.assertTrue((self.rig.local / "second.html").exists())

    def test_local_saved_and_the_client_report_copy_fails_the_local_pdf_is_still_saved_and_the_reply_says_what_was_not(self):
        write = to_client.RealFs.write_file

        def failing(fs, dest, data, replaces=False):
            if str(dest).endswith(".html"):
                raise OSError("disk")
            return write(fs, dest, data, replaces=replaces)
        self.report.unlink()
        with mock.patch.object(to_client.RealFs, "write_file", failing):
            status, got = self.go(to_client=True, pdf=True)
        self.assertEqual((status, got["ok"], got["local_saved"]), (409, False, True), got)
        self.assertEqual((got["pdf_saved"], got["pdf_name"]), (False, "second.pdf"), got)
        self.assertEqual(self.rig.listing(self.rig.local), ["chosen.html", "second.html", "second.pdf"])
        self.assertEqual((self.rig.local / "second.pdf").read_bytes(), self.GOOD)
        self.assertEqual(self.rig.listing(self.rig.client), [], "nothing, not even the PDF, went to the client folder")
        self.assertIn("PDF saved as “second.pdf”.", got["message"])
        self.assertIn(publish_pdf.MESSAGES["pdf_client_report_failed"], got["message"])
        self.assertNotIn(publish_pdf.MESSAGES["pdf_not_made_here"], got["message"])
        self.assertNotIn("did not finish", got["message"].split("PDF saved as")[1])
        self.assertEqual(len(self.rig.rows()), 2, "the Local publish is recorded")

    def test_a_publish_that_was_not_recorded_saves_no_pdf(self):
        with mock.patch.object(Store, "log_publication", side_effect=OSError("db")):
            status, got = self.go(to_client=False, pdf=True)
        self.assertEqual((status, got["ok"], got["code"]), (409, False, "not_recorded"), got)
        self.assertIn(publish_pdf.MESSAGES["pdf_not_made_here"], got["message"])
        self.assertFalse((self.rig.local / "second.pdf").exists())

    def test_a_saved_pdf_says_so_and_is_named(self):
        status, got = self.go(to_client=False, pdf=True)
        self.assertEqual((status, got["ok"], got["pdf_saved"], got["pdf_name"]), (200, True, True, "second.pdf"), got)
        status, got = self.rig.publish(to_client=False)
        self.assertNotIn("pdf_saved", got, "no PDF asked for: no field")

    def test_a_pdf_that_reached_only_one_place_is_not_saved_in_full(self):
        write = to_client.RealFs.write_file

        def failing(fs, dest, data, replaces=False):
            if str(dest).endswith(".pdf"):
                raise OSError("disk")
            return write(fs, dest, data, replaces=replaces)
        self.report.unlink()
        with mock.patch.object(to_client.RealFs, "write_file", failing):
            status, got = self.go(to_client=True, pdf=True)
        self.assertEqual((status, got["ok"], got["pdf_saved"], got["pdf_name"]), (200, True, False, "second.pdf"), got)
        self.assertIn(publish_pdf.MESSAGES["pdf_not_saved"].format(why=publish_pdf.MESSAGES["why_failed"]), got["message"])

    def test_the_same_report_already_in_the_client_folder_says_no_pdf_was_copied(self):
        status, got = self.go(to_client=True, pdf=True)
        self.assertEqual((status, got["ok"], got["action"], got["pdf_saved"]), (200, True, "nothing_to_do", False), got)
        self.assertIn(publish_pdf.MESSAGES["pdf_client_same"], got["message"])
        self.assertEqual(self.rig.listing(self.rig.client), [WANTED], "nothing went to the client folder")
        self.assertEqual(got["pdf_name"], "second.pdf", "the Local PDF is saved")
        self.assertIn("PDF saved as", got["message"])

    def test_a_local_name_that_appears_after_the_check_is_never_written_over(self):
        mine = self.rig.local / "second.pdf"
        status, got = self.go(to_client=False, pdf=True, before=lambda: mine.write_bytes(b"someone else's"))
        self.assertEqual((status, got["ok"], got["pdf_saved"]), (200, True, False), got)
        self.assertEqual(mine.read_bytes(), b"someone else's")
        self.assertIn(publish_pdf.MESSAGES["why_local_taken"], got["message"])
        self.assertNotIn("pdf_name", got)
        self.assertEqual(sorted(p.name for p in self.rig.local.iterdir()), ["chosen.html", "second.html", "second.pdf"], "no temporary file is left")

    def test_a_local_name_that_was_taken_and_confirmed_in_the_save_window_is_replaced(self):
        mine = self.rig.local / "second.pdf"
        mine.write_bytes(b"%PDF-earlier")

        def dialog(prompt, default_name, start=None):           # the Save window for the PDF is answered with the PDF's own name
            self.rig.saves.append((prompt, default_name, start))
            return mine if prompt == publish_pdf.SAVE_PROMPT else self.rig.save_to
        self.rig.publisher.choose_save_file = dialog
        status, got = self.go(to_client=False, pdf=True)
        self.assertEqual((status, got["ok"], got["pdf_saved"]), (200, True, True), got)
        self.assertEqual(mine.read_bytes(), self.GOOD)
        self.assertIn(publish_pdf.SAVE_PROMPT, [p for p, *_ in self.rig.saves], "the Save window asked about the taken PDF name")

    def test_a_client_name_that_appears_after_the_check_is_never_written_over(self):
        self.report.unlink()
        status, got = self.go(to_client=True, pdf=True, before=lambda: self.client_pdf.write_bytes(b"someone else's"))
        self.assertEqual((status, got["ok"], got["pdf_saved"]), (200, True, False), got)
        self.assertEqual(self.client_pdf.read_bytes(), b"someone else's")
        self.assertIn(publish_pdf.MESSAGES["pdf_not_saved"].format(why=publish_pdf.MESSAGES["why_taken"]), got["message"])
        self.assertEqual(self.rig.listing(self.rig.client), sorted([WANTED, PDF_WANTED]))

    def test_local_only_with_the_pdf_ticked_still_checks_it_for_dropped_markers(self):
        status, got = self.go(text="seen ZQ-HIDDEN-ACTION here", to_client=False, pdf=True)
        self.assertEqual((status, got["ok"], got["code"]), (409, False, "pdf_failed"), got)
        self.assertIn("The PDF was not made, because it would contain", got["message"])
        self.assertEqual((self.rig.everything_written(), len(self.rig.rows())), (self.before, 1), "the report is not published either")

    def test_the_pdfs_name_in_the_client_folder_is_planned_once_when_nothing_changes(self):
        self.report.unlink()
        with mock.patch.object(publish_pdf, "client_name", wraps=publish_pdf.client_name) as called:
            status, got = self.go(to_client=True, pdf=True)
        self.assertEqual((status, got["ok"], got["pdf_saved"]), (200, True, True), got)
        self.assertEqual(called.call_count, 1)
        self.assertEqual(len(self.rig.saves), 1)


if __name__ == "__main__":
    unittest.main()
