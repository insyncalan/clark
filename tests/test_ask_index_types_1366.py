"""Row 1366 slice (c): the index reads PDF and Excel (vendored pypdf through pdf_reader, vendored openpyxl). Made-up files only.
Pictures, PowerPoint, HTML and OCR are not in this slice."""
import io
import unittest
import zipfile
from unittest import mock

from _paths import SRC  # noqa: F401

from test_ask_index_1366 import Base, ix
from test_ask_pdf_passages import FAKE_PYPDF, pdf
from clark import ask_extract, pdf_reader


def xlsx(sheets):
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append(r)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


NS = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'


def sxml(*paras):
    body = "".join(f"<a:p><a:r><a:t>{p}</a:t></a:r></a:p>" for p in paras)
    return f'<?xml version="1.0"?><p:sld {NS} xmlns:p="p"><p:txBody>{body}</p:txBody></p:sld>'.encode()


def pptx(slides, notes=None, extra=None, compression=zipfile.ZIP_DEFLATED):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression) as z:
        for n, paras in slides.items():
            z.writestr(f"ppt/slides/slide{n}.xml", sxml(*paras))
        for n, paras in (notes or {}).items():
            z.writestr(f"ppt/notesSlides/notesSlide{n}.xml", sxml(*paras))
        for name, data in (extra or {}).items():
            z.writestr(name, data)
    return out.getvalue()


class Types(Base):
    def setUp(self):
        super().setUp()
        v = self.d / "vendor"
        (v / "pypdf").mkdir(parents=True)
        (v / "pypdf" / "__init__.py").write_text(FAKE_PYPDF, encoding="utf-8")
        p = mock.patch.object(pdf_reader, "VENDOR", v)
        p.start()
        self.addCleanup(p.stop)

    def test_pdf_pages_are_found_with_their_page_number(self):
        self.put("plan.pdf", pdf(["zqpdfone first", "zqpdftwo second"]), binary=True)
        self.build()
        got = self.found("zqpdftwo")
        self.assertEqual(len(got), 1)
        self.assertIn("plan.pdf, page 2", got[0][0])
        self.assertEqual(ix.status(self.data, "P1", [self.box])["indexed"], 1)

    def test_a_scanned_pdf_is_left_out_with_a_plain_reason(self):
        self.put("scan.pdf", pdf([None, None]), binary=True)
        self.build()
        s = ix.status(self.data, "P1", [self.box])
        self.assertEqual((s["indexed"], s["type"]), (0, 1))
        out = ix.mod().files_left_out(self.data, "P1", 200)
        self.assertEqual([n for n, _ in out["files"]], ["saved/scan.pdf"])

    def test_excel_cells_are_found_with_sheet_name(self):
        self.put("budget.xlsx", xlsx({"Plan": [["item", "owner"], ["zqxlone", "Ana"]], "Late": [["zqxltwo", 42]]}), binary=True)
        self.build()
        a, b = self.found("zqxlone"), self.found("zqxltwo")
        self.assertEqual((len(a), len(b)), (1, 1))
        self.assertIn("Plan", a[0][0])
        self.assertIn("Late", b[0][0])
        self.assertIn("zqxlone", a[0][1])

    def test_excel_hidden_sheet_is_not_read(self):
        import io
        import openpyxl
        wb = openpyxl.Workbook()
        wb.active.title = "Shown"
        wb.active.append(["zqxlshown"])
        h = wb.create_sheet("Secret")
        h.append(["zqxlhidden"])
        h.sheet_state = "hidden"
        vh = wb.create_sheet("Deep")
        vh.append(["zqxlverydeep"])
        vh.sheet_state = "veryHidden"
        buf = io.BytesIO()
        wb.save(buf)
        self.put("h.xlsx", buf.getvalue(), binary=True)
        self.build()
        self.assertTrue(self.found("zqxlshown"))
        self.assertFalse(self.found("zqxlhidden"))
        self.assertFalse(self.found("zqxlverydeep"))

    def test_excel_every_row_carries_the_header_row_into_its_passage(self):
        rows = [["item", "owner", "due"]] + [[f"task{i}", f"zqxlowner{i}", f"day{i}"] for i in range(400)]
        self.put("tasks.xlsx", xlsx({"Plan": rows}), binary=True)
        self.build()
        got = self.found("zqxlowner399")
        self.assertEqual(len(got), 1)
        self.assertIn("owner: zqxlowner399", got[0][1])
        self.assertIn("due: day399", got[0][1])

    def test_excel_formulas_give_their_stored_values_not_the_formula(self):
        self.put("f.xlsx", xlsx({"S": [[1, 2, "=A1+B1"], ["zqxlname"]]}), binary=True)
        self.build()
        self.assertTrue(self.found("zqxlname"))
        self.assertFalse(self.found("A1"))

    def test_a_damaged_excel_file_is_left_out_not_an_error(self):
        self.put("bad.xlsx", b"PK\x03\x04 not really", binary=True)
        self.build()
        s = ix.status(self.data, "P1", [self.box])
        self.assertEqual(s["indexed"], 0)
        self.assertEqual(sum(s[k] for k in ("type", "safety")), 1)

    def test_a_secret_in_a_cell_keeps_the_whole_file_out(self):
        self.put("k.xlsx", xlsx({"S": [["zqxlkey"], ["password = " + "hunter2" * 3]]}), binary=True)
        self.build()
        self.assertFalse(self.found("zqxlkey"))
        self.assertEqual(ix.status(self.data, "P1", [self.box])["safety"], 1)

    def test_pdf_and_excel_follow_a_refresh(self):
        p = self.put("a.xlsx", xlsx({"S": [["zqxlold"]]}), binary=True)
        self.build()
        self.put("a.xlsx", xlsx({"S": [["zqxlnew word"]]}), binary=True)
        import os
        os.utime(p, (1, 1))
        ix.refresh(self.data, "P1", [self.box])
        self.assertFalse(self.found("zqxlold"))
        self.assertTrue(self.found("zqxlnew"))

    def test_pptx_slides_and_notes_are_found_with_slide_number(self):
        self.put("deck.pptx", pptx({1: ["zqppone title"], 2: ["zqpptwo body", "second para"]}, {2: ["zqppnote spoken"]}), binary=True)
        self.build()
        a, b, c = self.found("zqppone"), self.found("zqpptwo"), self.found("zqppnote")
        self.assertEqual((len(a), len(b), len(c)), (1, 1, 1))
        self.assertIn("deck.pptx, slide 1", a[0][0])
        self.assertIn("deck.pptx, slide 2", b[0][0])
        self.assertIn("deck.pptx, slide 2", c[0][0])
        self.assertEqual(ix.status(self.data, "P1", [self.box])["indexed"], 1)

    def test_pptx_with_no_text_counts_as_type(self):
        self.put("empty.pptx", pptx({1: []}), binary=True)
        self.build()
        s = ix.status(self.data, "P1", [self.box])
        self.assertEqual((s["indexed"], s["type"], s["safety"]), (0, 1, 0))

    def test_a_truncated_pptx_is_type_not_an_error(self):
        self.put("cut.pptx", pptx({1: ["zqpptcut"]})[:-30], binary=True)
        self.build()
        s = ix.status(self.data, "P1", [self.box])
        self.assertEqual((s["indexed"], s["type"], s["safety"]), (0, 1, 0))

    def test_a_pptx_with_broken_xml_is_type(self):
        self.put("x.pptx", pptx({}, extra={"ppt/slides/slide1.xml": b"<a:p><a:t>zqpptbad</a:p>"}), binary=True)
        self.build()
        self.assertFalse(self.found("zqpptbad"))
        self.assertEqual(ix.status(self.data, "P1", [self.box])["type"], 1)

    def test_a_pptx_with_an_entity_declaration_is_type_and_nothing_is_expanded(self):
        evil = b'<?xml version="1.0"?><!DOCTYPE s [<!ENTITY e "zqpptlol">]><a:p %s><a:r><a:t>&e;</a:t></a:r></a:p>' % NS.encode()
        self.put("e.pptx", pptx({}, extra={"ppt/slides/slide1.xml": evil}), binary=True)
        self.build()
        self.assertFalse(self.found("zqpptlol"))
        self.assertEqual(ix.status(self.data, "P1", [self.box])["type"], 1)

    def test_a_real_secret_inside_a_pptx_is_still_safety(self):
        self.put("k.pptx", pptx({1: ["zqpptkey", "password = " + "hunter2" * 3]}), binary=True)
        self.build()
        self.assertFalse(self.found("zqpptkey"))
        s = ix.status(self.data, "P1", [self.box])
        self.assertEqual((s["safety"], s["type"]), (1, 0))

    def test_a_zip_bomb_pptx_is_type(self):
        big = b"<a:p %s><a:r><a:t>zqpptbomb</a:t></a:r></a:p>" % NS.encode() + b" " * (ask_extract.MAX_XML + 10)
        self.put("bomb.pptx", pptx({}, extra={"ppt/slides/slide1.xml": big}), binary=True)
        self.build()
        self.assertFalse(self.found("zqpptbomb"))
        self.assertEqual(ix.status(self.data, "P1", [self.box])["type"], 1)

    def test_a_pptx_with_a_forged_small_header_is_still_limited(self):
        big = b"<a:p %s><a:r><a:t>zqpptforge</a:t></a:r></a:p>" % NS.encode() + b" " * 4000
        raw = pptx({}, extra={"ppt/slides/slide1.xml": big})
        with mock.patch.object(ask_extract, "MAX_XML", 1000):
            with self.assertRaises(ValueError):
                ask_extract.pptx_groups(raw)

    def test_a_pptx_with_too_many_members_or_slides_or_bytes_is_refused(self):
        raw = pptx({1: ["zqpptmany"], 2: ["b"]}, extra={"junk1": b"x", "junk2": b"y"})
        for name, small in (("MAX_MEMBERS", 3), ("MAX_SLIDES", 1), ("MAX_UNCOMPRESSED", 100)):
            with mock.patch.object(ask_extract, name, small):
                with self.assertRaises(ValueError, msg=name):
                    ask_extract.pptx_groups(raw)
        self.assertTrue(ask_extract.pptx_groups(raw))

    def test_pptx_limits_allow_exactly_the_limit(self):
        raw = pptx({1: ["a"], 2: ["b"]})
        n = len(zipfile.ZipFile(io.BytesIO(raw)).infolist())
        size = sum(i.file_size for i in zipfile.ZipFile(io.BytesIO(raw)).infolist())
        with mock.patch.object(ask_extract, "MAX_MEMBERS", n), mock.patch.object(ask_extract, "MAX_SLIDES", 2), mock.patch.object(ask_extract, "MAX_UNCOMPRESSED", size):
            self.assertEqual(len(ask_extract.pptx_groups(raw)), 2)

    def test_pptx_truncated_read_and_slide_order(self):
        with self.assertRaises(ValueError):
            ask_extract.pptx_groups(pptx({1: ["a"]}), truncated=True)
        got = ask_extract.pptx_groups(pptx({10: ["ten"], 2: ["two"], 1: ["one"]}, {3: ["note three"]}))
        self.assertEqual(got, [("slide 1", ["one"]), ("slide 2", ["two"]), ("slide 3", ["note three"]), ("slide 10", ["ten"])])
        self.assertEqual(ask_extract.pptx_groups(pptx({1: ["a"]}, {1: ["n"]})), [("slide 1", ["a", "n"])])

    def test_pptx_ignores_other_members_and_text_outside_a_t(self):
        x = b'<a:p %s><a:pPr>zzhid</a:pPr><a:r><a:t>shown</a:t></a:r></a:p>' % NS.encode()
        raw = pptx({}, extra={"ppt/slides/slide1.xml": x, "ppt/slides/slide1.xml.rels": b"zzrels", "docProps/slide9.xml": sxml("zzother")})
        self.assertEqual(ask_extract.pptx_groups(raw), [("slide 1", ["shown"])])

    def test_html_visible_text_only(self):
        page = (b"<html><head><title>zzhead</title><style>.a{}zzstyle</style></head><body><h1>zqhtone Title</h1>"
                b"<script>var zzscript=1;</script><p>zqhttwo <b>bold</b> &amp; more</p><noscript>zznos</noscript>"
                b"<!-- zzcomment --><ul><li>one</li><li>two</li></ul></body></html>")
        self.put("p.html", page, binary=True)
        self.put("q.htm", b"<p>zqhtthree</p>", binary=True)
        self.build()
        self.assertEqual(len(self.found("zqhtone")), 1)
        self.assertIn("p.html", self.found("zqhtone")[0][0])
        self.assertTrue(self.found("zqhtthree"))
        self.assertIn("zqhttwo bold & more", self.found("zqhttwo")[0][1])
        for w in ("zzhead", "zzstyle", "zzscript", "zznos", "zzcomment"):
            self.assertFalse(self.found(w), w)
        self.assertEqual(ix.status(self.data, "P1", [self.box])["indexed"], 2)

    def test_html_lines_follow_blocks_and_ignore_nesting_of_skip(self):
        got = ask_extract.html_groups(b"<div>a<p>b</p>c<br>d<script><script>x</script>e</div>f<style>y</style>g")
        self.assertEqual(got, [(None, ["a", "b", "c", "de", "fg"])])
        self.assertEqual(ask_extract.html_groups(b"<p>x</p><hr/><p>y</p>"), [(None, ["x", "y"])])
        self.assertEqual(ask_extract.html_groups(b"<p>a  \n b</p>"), [(None, ["a b"])])
        self.assertEqual(ask_extract.html_groups(b"<img><p>a</p>"), [(None, ["a"])])

    def test_html_with_no_text_counts_as_type_and_bad_bytes_are_replaced(self):
        self.put("e.html", b"<html><script>x</script></html>", binary=True)
        self.put("b.html", b"<p>zqhtbad \xff\xfe ok</p>", binary=True)
        self.build()
        s = ix.status(self.data, "P1", [self.box])
        self.assertEqual((s["indexed"], s["type"]), (1, 1))
        self.assertTrue(self.found("zqhtbad"))

    def test_a_huge_html_file_is_type_and_unclosed_tags_are_fine(self):
        with self.assertRaises(ValueError):
            ask_extract.html_groups(b"<p>a</p>", truncated=True)
        with mock.patch.object(ask_extract, "MAX_HTML_BYTES", 10):
            with self.assertRaises(ValueError):
                ask_extract.html_groups(b"x" * 11)
            self.assertEqual(ask_extract.html_groups(b"x" * 10), [(None, ["x" * 10])])
        self.put("big.html", b"<p>zqhtbig</p>" + b" " * (ask_extract.MAX_HTML_BYTES + 5), binary=True)
        self.put("deep.html", b"<div>" * 20000 + b"zqhtdeep" + b"<script>", binary=True)
        self.build()
        s = ix.status(self.data, "P1", [self.box])
        self.assertEqual((s["type"], s["indexed"], s["safety"]), (1, 1, 0))
        self.assertFalse(self.found("zqhtbig"))
        self.assertTrue(self.found("zqhtdeep"))

    def test_html_line_count_is_capped(self):
        with mock.patch.object(ask_extract, "MAX_HTML_LINES", 3):
            got = ask_extract.html_groups(b"".join(b"<p>l%d</p>" % i for i in range(10)))
        self.assertEqual(got, [(None, ["l0", "l1", "l2"])])

    def test_pptx_paragraphs_runs_and_names(self):
        two_runs = b'<a:p %s><a:r><a:t>he</a:t></a:r>junk<a:r><a:t>llo</a:t></a:r>tail</a:p><a:p %s><a:r><a:t>next</a:t></a:r></a:p>' % (NS.encode(), NS.encode())
        raw = pptx({}, extra={"ppt/slides/slide1.xml": b"<r>" + two_runs + b"</r>"})
        self.assertEqual(ask_extract.pptx_groups(raw), [("slide 1", ["hello", "next"])])
        plain = b'<s><p><r><t>unprefixed</t></r>zzjunk</p><p><r><t>two</t></r></p></s>'
        raw = pptx({}, extra={"ppt/slides/slide1.xml": plain})
        self.assertEqual(ask_extract.pptx_groups(raw), [("slide 1", ["unprefixed", "two"])])
        tab = b'<s %s><a:p><a:tab>zztab</a:tab><a:pt>zzpt</a:pt><a:r><a:t>ok</a:t></a:r></a:p></s>' % NS.encode()
        self.assertEqual(ask_extract.pptx_groups(pptx({}, extra={"ppt/slides/slide1.xml": tab})), [("slide 1", ["ok"])])

    def test_a_hidden_slide_and_its_notes_are_not_read(self):
        hide = lambda n, v: b'<p:sld %s xmlns:p="p" show="%s"><a:p><a:r><a:t>' % (NS.encode(), v) + n + b'</a:t></a:r></a:p></p:sld>'     # noqa: E731
        for v in (b"0", b"false"):
            raw = pptx({2: ["zqshown"]}, notes={1: ["zqhiddennote"], 2: ["zqshownnote"]}, extra={"ppt/slides/slide1.xml": hide(b"zqhidden", v)})
            self.assertEqual(ask_extract.pptx_groups(raw), [("slide 2", ["zqshown", "zqshownnote"])], v)
        shown = pptx({}, extra={"ppt/slides/slide1.xml": hide(b"zqkept", b"1")})
        self.assertEqual(ask_extract.pptx_groups(shown), [("slide 1", ["zqkept"])], "show=1 is an ordinary slide")
        self.assertEqual(ask_extract.pptx_groups(pptx({}, extra={"ppt/slides/slide1.xml": hide(b"zqonly", b"0")})), [], "a deck of hidden slides has no text")

    def test_only_the_slide_element_itself_says_hidden(self):
        child = b'<p:sld %s xmlns:p="p"><p:x show="0"/><a:p><a:r><a:t>zqchild</a:t></a:r></a:p></p:sld>' % NS.encode()
        self.assertEqual(ask_extract.pptx_groups(pptx({}, extra={"ppt/slides/slide1.xml": child})), [("slide 1", ["zqchild"])], "a child with show=0 hides nothing")
        note = b'<p:notes %s xmlns:p="p" show="0"><a:p><a:r><a:t>zqnote</a:t></a:r></a:p></p:notes>' % NS.encode()
        raw = pptx({1: ["zqslide"]}, extra={"ppt/notesSlides/notesSlide1.xml": note})
        self.assertEqual(ask_extract.pptx_groups(raw), [("slide 1", ["zqslide", "zqnote"])], "only the slide's own show counts")

    def test_a_hidden_slide_is_not_found_in_the_index(self):
        raw = pptx({2: ["zqvisible"]}, notes={1: ["zqsecretnote"]}, extra={"ppt/slides/slide1.xml": b'<p:sld %s xmlns:p="p" show="0"><a:p><a:r><a:t>zqhiddentext</a:t></a:r></a:p></p:sld>' % NS.encode()})
        self.put("deck.pptx", raw, binary=True)
        self.build()
        self.assertTrue(self.found("zqvisible"))
        self.assertFalse(self.found("zqhiddentext"))
        self.assertFalse(self.found("zqsecretnote"))

    def test_the_module_notes_do_not_call_a_hostile_or_damaged_file_a_safety_one(self):
        for doc in (ask_extract.__doc__, __import__("clark.ask_index", fromlist=["x"]).__doc__):
            self.assertNotIn("as `safety`", doc.replace("password-like", ""), "such a file counts as `type`")

    def test_pptx_cut_off_xml_is_refused_and_a_part_of_exactly_the_limit_is_read(self):
        cut = b'<a:p %s><a:r><a:t>zzcut' % NS.encode()
        with self.assertRaises(ValueError):
            ask_extract.pptx_groups(pptx({}, extra={"ppt/slides/slide1.xml": cut}))
        ok = sxml("exact")
        with mock.patch.object(ask_extract, "MAX_XML", len(ok)):
            self.assertEqual(ask_extract.pptx_groups(pptx({1: ["exact"]})), [("slide 1", ["exact"])])
        with mock.patch.object(ask_extract, "MAX_XML", len(ok) - 1):
            with self.assertRaises(ValueError):
                ask_extract.pptx_groups(pptx({1: ["exact"]}))

    def test_the_limits_are_the_documented_ones(self):
        mb = 1024 * 1024
        self.assertEqual((ask_extract.MAX_MEMBERS, ask_extract.MAX_SLIDES, ask_extract.MAX_UNCOMPRESSED, ask_extract.MAX_XML),
                         (5000, 2000, 100 * mb, 8 * mb))
        self.assertEqual((ask_extract.MAX_HTML_BYTES, ask_extract.MAX_HTML_LINES), (5 * mb, 200000))

    def test_every_html_block_tag_breaks_a_line_and_every_skipped_tag_hides_its_text(self):
        blocks = ("p div br li ul ol tr table h1 h2 h3 h4 h5 h6 section article header footer blockquote pre hr td th title main nav aside "
                  "form dd dt dl").split()
        for tag in blocks:
            self.assertEqual(ask_extract.html_groups(f"x<{tag}>y".encode()), [(None, ["x", "y"])], tag)
        for tag in ("br", "hr"):
            self.assertEqual(ask_extract.html_groups(f"x<{tag}/>y".encode()), [(None, ["x", "y"])], tag)
        self.assertEqual(ask_extract.html_groups(b"x<span>y</span><b>z</b>"), [(None, ["xyz"])])
        for tag in ("script", "style", "noscript", "template", "head"):
            self.assertEqual(ask_extract.html_groups(f"x<{tag}>hidden</{tag}>y".encode()), [(None, ["xy"])], tag)

    def test_html_unclosed_skip_tag_hides_the_rest(self):
        self.assertEqual(ask_extract.html_groups(b"<p>shown</p><style>hidden"), [(None, ["shown"])])
        self.assertEqual(ask_extract.html_groups(b"<head><p>no</p></head><p>yes</p>"), [(None, ["yes"])])

    def test_a_pptx_or_html_file_over_one_megabyte_is_still_read_and_old_ppt_is_a_type(self):
        import os
        self.put("big.pptx", pptx({1: ["zqppbig"]}, extra={"ppt/media/image1.bin": os.urandom(1300000)}), binary=True)
        self.put("big.html", b"<p>zqhtmeg</p>" + b"<!-- " + b"x" * 1300000 + b" -->", binary=True)
        self.put("old.ppt", b"\xd0\xcf\x11\xe0 zqpptold", binary=True)
        self.build()
        s = ix.status(self.data, "P1", [self.box])
        self.assertEqual((s["indexed"], s["type"], s["safety"]), (2, 1, 0))
        self.assertTrue(self.found("zqppbig"))
        self.assertTrue(self.found("zqhtmeg"))


if __name__ == "__main__":
    unittest.main()
