"""The Source NAME (row 1077, the owner's ruling of 10-11-2026): a work item's or milestone's `source` words as a person may see them,
anywhere the Source line is drawn (the live peek through activity_read, a published file through publish.select).

The stored words are kept as they are in the database. Shown, by a CHARACTER ALLOW-LIST (a list of what is allowed, never a list of the
slashes that are not; fourth pass, privacy first):
  A. Normalise: NFKC; decode %XX, %uXXXX and HTML entities (numeric and named) until nothing changes (decode and clean together, to a fixed point; an escape split by a control or
     zero-width character is joined first); any white space is one space; control, format and zero-width characters go.
  B. PLAIN WORDS: every character is a letter or digit (str.isalnum) or one of PLAIN_EXTRA = space , . - _ ( ) : ' & + #  , and the value does
     not start with a drive letter ("C:"), and holds no "&#" or "&name;" (a left-over entity; "R&D" and "C#" stay). Plain words keep today's behaviour: their words, commas, and a stored YYYY-MM-DD read DD-MM-YYYY.
  C. Any other character (a slash of any kind, < > @ % ~ and so on) makes the value NOT plain. It then publishes ONLY a final file name: the
     text after the last character that is not a letter, digit or one of NAME_EXTRA = space . - _ ( ) ' & + # , and only when it ends in an
     extension (a dot and 1 to 8 letters or digits) after a non-empty stem; otherwise NOTHING. A bare web address publishes nothing.
  D. PUBLISHED FILES (published=True): the owner's ruling A of row 1077, the Source line in a client file is the file name only, free text dropped.
     Plain words are not published as they stand: only the last comma part that is wholly a file name (a stem, then an extension holding a letter)
     goes out, so "Added by hand in clark" publishes nothing and "Word import, 2026-11-11, plan.docx, under a person's name" publishes "plan.docx".
     The live peek (published=False) still shows the plain words to the people who work in clark.
  E. At most 120 characters, cut with an ellipsis. Text longer than MAX_IN characters is cut before step A (the end for a published value, where the
     name is, the start otherwise), so a huge value costs a bounded amount of work.
Imports nothing from clark.
"""
import html
import re
import unicodedata
from datetime import date

CAP = 120
MAX_IN = 2000
PLAIN_EXTRA = " ,.-_():'&+#"
NAME_EXTRA = " .-_()'&+#"
_ISO_DAY = re.compile(r"(?<![\d-])(\d{4})-(\d{2})-(\d{2})(?![\d-])")
_HIDDEN = lambda ch: unicodedata.category(ch) in ("Cc", "Cf", "Cs", "Co", "Cn") and not ch.isspace()          # control, format, zero-width, unassigned
_ESCAPE = re.compile(r"%(?:u[0-9A-Fa-f]{4}|[0-9A-Fa-f]{2})")
_ENTITY = re.compile(r"&#|&[A-Za-z0-9]+;")
_DRIVE = re.compile(r"[A-Za-z]:")
_EXT = re.compile(r"\.[A-Za-z0-9]{1,8}$")
_BARE = re.compile(r"(?:[A-Za-z][A-Za-z0-9+.-]*:)?//[^/\\]*$")                                              # a web address with a host and no path after it (a "?query" or "#fragment" is not a path)
_COLON_PATH = re.compile(r":(?![\s\d]|$)")                                                                   # "Macintosh HD:Users:name:Folder:file": a colon with words right after it, not "Plan: v2" or "12:30"


def _day_as_shown(m):
    try:
        date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return m.group(0)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"


def _join_escapes(text):
    """"%\\n5C" or "%5\\u200bC": control and zero-width characters inside an escape are taken out, so the escape is still read."""
    out, i = [], 0
    while i < len(text):
        if text[i] != "%":
            out.append(text[i])
            i += 1
            continue
        j, got = i + 1, []
        while j < len(text) and len(got) < 5 and (_HIDDEN(text[j]) or text[j] in "\t\n\r" or text[j] in "uU0123456789abcdefABCDEF"):
            if not (_HIDDEN(text[j]) or text[j] in "\t\n\r"):
                got.append(text[j])
            j += 1
        out.append("%" + "".join(got) if _ESCAPE.match("%" + "".join(got)) else text[i:j])
        i = j
    return "".join(out)


def _decode(text):
    text = _join_escapes(text)
    text = re.sub(r"%u([0-9A-Fa-f]{4})", lambda m: chr(int(m.group(1), 16)), text)
    text = re.sub(r"%([0-9A-Fa-f]{2})", lambda m: chr(int(m.group(1), 16)), text)
    return unicodedata.normalize("NFKC", html.unescape(text))


def _clean(text):
    text = "".join(" " if ch.isspace() else ch for ch in text if ch.isspace() or not _HIDDEN(ch))
    return re.sub(r" {2,}", " ", text).strip()


def _normal(words):
    """The whole of A, decode and clean together, again and again until the text stops changing (a clean can make a new escape)."""
    text = unicodedata.normalize("NFKC", words)
    for _ in range(60):
        again = _clean(_decode(text))
        if again == text:
            break
        text = again
    return text


def _is_plain(text):
    return (all(ch.isalnum() or ch in PLAIN_EXTRA for ch in text) and not _DRIVE.match(text)
            and not _ENTITY.search(text) and not _COLON_PATH.search(text))                                  # "&#47" or "&amp;" left over is an entity, never words ("R&D", "C#" stay)


def _file_name(text):
    """The final file name, or "": after the last character outside letters, digits and NAME_EXTRA, with an extension after a stem."""
    if _BARE.match(text):
        return ""
    cut = max((i for i, ch in enumerate(text) if not (ch.isalnum() or ch in NAME_EXTRA)), default=-1)
    if cut >= 0 and text[cut] == "@":                        # "name@host.example": a host name is no file name
        return ""
    name = text[cut + 1:].strip()
    ext = _EXT.search(name)
    return name if ext and name[:ext.start()].strip() else ""


def _listed_name(text):
    """Plain words in a file (D): the last comma part that is wholly a file name (a stem and an extension holding a letter), or ""."""
    for part in reversed(text.split(",")):
        part = part.strip()
        ext = _EXT.search(part)
        if ext and part[:ext.start()].strip() and re.search(r"[A-Za-z]", ext.group(0)) and not _ISO_DAY.fullmatch(part):
            return part
    return ""


def source_name(words, published=False):
    """The words to show for a stored `source`, or "" when there is nothing to show. published=True: the file name only (D)."""
    if not isinstance(words, str):
        return ""
    if len(words) > MAX_IN:
        words = words[-MAX_IN:] if published else words[:MAX_IN]
    text = _normal(words)
    if not _is_plain(text):
        out = _file_name(text)
    else:
        out = _listed_name(text) if published else text
    out = _ISO_DAY.sub(_day_as_shown, out).strip()
    return out if len(out) <= CAP else out[:CAP - 1].rstrip() + "\u2026"
