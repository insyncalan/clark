"""Row 853: the Word report on the brand's own Word template (a letterhead): its page, header, footer, styles, theme and logo.

A brand's folder may hold word/template.docx. `wrap(template, built)` takes that file's bytes and the report docx_build made, and
gives the template's file with the report's body in it: the template's page set-up, headers, footers, theme, fonts and pictures
stay as they are; the template's own styles win by name and the report's styles are added only where the template has none of
that name; the report's lists, links and pictures come across under names that cannot clash with the template's. The template is
opened with the same safety rules as any Word file (word_template._load). Nothing in the template is read as text, and no
placeholder is filled: the body is the report's. `find(branding)` is the template file of a brand folder or None.
Standard library only, Python 3.9.
"""
import io
import os
import re
import zipfile
from pathlib import Path

from clark import docx_build as _b
from clark import docx_read as _r
from clark import word_template
from clark.docx_read import WordRefused

REL_PATH = ("word", "template.docx")
NAME = "The Word template in the branding folder"
PREFIX = "rIdBrand"
STYLE = re.compile(r'<w:style\s[^>]*?w:styleId="([A-Za-z0-9_-]+)"[^>]*>.*?</w:style>', re.S)
SECT = re.compile(r"<w:sectPr(?:\s[^>]*)?>.*?</w:sectPr>\s*(?=</w:body>)", re.S)
RELS = "word/_rels/document.xml.rels"


def find(branding):
    """The path of the brand folder's Word template, or None: a regular file, inside the folder after links are followed, no
    bigger than the reader's limit. A folder with none (or the Generic one) gives None and the report keeps its own layout."""
    try:
        base = Path(branding).resolve()
        found = base.joinpath(*REL_PATH)
        if found.is_symlink() or not found.is_file() or not found.resolve().is_relative_to(base):
            return None
        return found if found.stat().st_size <= _r.MAX_FILE_BYTES else None
    except (OSError, RuntimeError, ValueError):
        return None


def on_template(built, branding):
    """The report `built` on the brand folder's Word template if it has one; else `built` as it is. Raises WordRefused."""
    found = find(branding)
    if found is None:
        return built
    with open(found, "rb") as f:
        return wrap(f.read(), built)


def _text(data, name):
    try:
        return data[name].decode("utf-8")
    except (KeyError, UnicodeDecodeError):
        raise WordRefused(f"{NAME} is not a Word document clark can use: part {name} can't be read.") from None


def wrap(template, built):
    infos, parts = word_template._load(template, NAME)
    with zipfile.ZipFile(io.BytesIO(built)) as z:
        mine = {i.filename: z.read(i.filename) for i in z.infolist()}
    doc = _text(parts, "word/document.xml")
    sect = SECT.findall(doc)
    mine_doc = mine["word/document.xml"].decode("utf-8")
    body = mine_doc[mine_doc.index("<w:body>") + 8:mine_doc.rindex("<w:sectPr")]
    if sect:
        tail = sect[-1].rstrip()
    else:                                                  # no page set-up in the template: the report's, with no footer of its own
        tail = re.sub(r"<w:footerReference[^>]*/>", "", mine_doc[mine_doc.rindex("<w:sectPr"):mine_doc.rindex("</w:body>")])
    m = re.search(r"<w:body(?:\s[^>]*)?>", doc)
    if m is None or "</w:body>" not in doc:
        raise WordRefused(f"{NAME} is not a Word document clark can use: it has no body.")
    root = re.search(r"<w:document(?:\s[^>]*)?>", doc).group(0)
    head = root
    for prefix, uri in (("w", _b.NS_W), ("r", _b.NS_R)):
        if f"xmlns:{prefix}=" not in head:
            head = head[:-1] + f' xmlns:{prefix}="{uri}">'
    # the report's relationship ids (links and pictures) get a prefix no template uses
    rid = {}
    for m2 in re.finditer(r'<Relationship Id="(rId\d+)" Type="[^"]*/(hyperlink|image)" Target="([^"]*)"(?: TargetMode="External")?/>',
                          mine["word/_rels/document.xml.rels"].decode("utf-8")):
        rid[m2.group(1)] = (PREFIX + m2.group(1)[3:], m2.group(0))
    body = re.sub(r'(r:(?:id|embed)=")(rId\d+)"', lambda m3: m3.group(1) + rid.get(m3.group(2), (m3.group(2),))[0] + '"', body)
    new_rels = ""
    media = {}
    for old, (new, xml) in rid.items():
        xml = xml.replace(f'Id="{old}"', f'Id="{new}"')
        mt = re.search(r'Target="media/([^"]+)"', xml)
        if mt:
            media[f"word/media/{mt.group(1)}"] = f"word/media/clark-{mt.group(1)}"
            xml = xml.replace(f"media/{mt.group(1)}", f"media/clark-{mt.group(1)}")
        new_rels += xml
    out = dict(parts)
    out["word/document.xml"] = (_b.HEAD + head + "<w:body>" + body + tail + "</w:body></w:document>").encode("utf-8")
    # styles: the template's win; ours are added where the template has none of that id
    ours = mine["word/styles.xml"].decode("utf-8")
    if "word/styles.xml" in parts:
        theirs = _text(parts, "word/styles.xml")
        have = set(STYLE.findall(theirs))
        extra = "".join(m4.group(0) for m4 in STYLE.finditer(ours) if m4.group(1) not in have)
        i = theirs.rindex("</w:styles>")
        out["word/styles.xml"] = (theirs[:i] + extra + theirs[i:]).encode("utf-8")
    else:
        out["word/styles.xml"] = mine["word/styles.xml"]
    num = re.search(r'Type="[^"]*/numbering"[^>]*?Target="([^"/][^"]*)"|Target="([^"/][^"]*)"[^>]*?Type="[^"]*/numbering"',
                    _text(parts, RELS) if RELS in parts else "")
    target = next((g for g in num.groups() if g), "numbering.xml") if num else "numbering.xml"
    out["word/" + target] = mine["word/numbering.xml"]           # the report's lists are numbered by the report's own definitions
    for old, new in media.items():
        out[new] = mine[old]
    # relationships and content types
    rels = _text(parts, RELS) if RELS in parts else f'{_b.HEAD}<Relationships xmlns="{_b.NS_REL}"></Relationships>'
    add = new_rels
    for typ in ("styles", "numbering"):
        if not re.search(rf'Type="[^"]*/{typ}"', rels):
            add += f'<Relationship Id="{PREFIX}{typ.capitalize()}" Type="{_b.NS_R}/{typ}" Target="{typ}.xml"/>'
    i = rels.rindex("</Relationships>")
    out[RELS] = (rels[:i] + add + rels[i:]).encode("utf-8")
    ct = _text(parts, "[Content_Types].xml")
    add = ""
    if not re.search(r'Extension="png"', ct) and media:
        add += '<Default Extension="png" ContentType="image/png"/>'
    for part, kind in ((f"/word/{target}", "numbering"), ("/word/styles.xml", "styles")):
        if f'PartName="{part}"' not in ct:
            add += f'<Override PartName="{part}" ContentType="{_b.DOC_TYPE}.{kind}+xml"/>'
    i = ct.rindex("</Types>")
    out["[Content_Types].xml"] = (ct[:i] + add + ct[i:]).encode("utf-8")
    for n in ("docProps/core.xml", "docProps/app.xml"):         # the file's author and company are clark's, never the template's
        if n in parts and n in mine:
            out[n] = mine[n]
    order = [i.filename for i in infos]
    order += [n for n in out if n not in parts]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as w:
        for n in order:
            zi = zipfile.ZipInfo(n, _b.ZIP_TIME)
            zi.compress_type, zi.create_system, zi.external_attr = zipfile.ZIP_DEFLATED, 3, 0o644 << 16
            w.writestr(zi, out[n], compresslevel=6)
    data = buf.getvalue()
    if len(data) > _b.MAX_BYTES:
        raise _b.WordError(f"The report is {len(data) / 1048576:.1f} MB, which is over the {_b.MAX_BYTES // 1048576} MB limit. "
                           "Leave out some sections or pictures and try again.")
    return data
