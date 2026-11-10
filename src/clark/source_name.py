"""The Source NAME (row 1077, the owner's ruling of 10-11-2026): a work item's or milestone's `source` words as a person may see them,
anywhere the Source line is drawn (the live peek through activity_read, a published file through publish.select).

The stored words are kept as they are in the database. Shown, by a CHARACTER ALLOW-LIST (a list of what is allowed, never a list of the
slashes that are not; fourth pass, privacy first):
  A. Normalise: NFKC; decode %XX, %uXXXX and HTML entities (numeric and named) until nothing changes (5 rounds; an escape split by a control or
     zero-width character is joined first); any white space is one space; control, format and zero-width characters go.
  B. PLAIN WORDS: every character is a letter or digit (str.isalnum) or one of PLAIN_EXTRA = space , . - _ ( ) : ' & + #  , and the value does
     not start with a drive letter ("C:"). Plain words keep today's behaviour: their words, commas, and a stored YYYY-MM-DD read DD-MM-YYYY.
  C. Any other character (a slash of any kind, < > @ % ~ and so on) makes the value NOT plain. It then publishes ONLY a final file name: the
     text after the last character that is not a letter, digit or one of NAME_EXTRA = space . - _ ( ) ' & + # , and only when it ends in an
     extension (a dot and 1 to 8 letters or digits) after a non-empty stem; otherwise NOTHING. A bare web address publishes nothing.
  E. At most 120 characters, cut with an ellipsis.
Imports nothing from clark.
"""
import html
import re
import unicodedata
from datetime import date

CAP = 120
PLAIN_EXTRA = " ,.-_():'&+#"
NAME_EXTRA = " .-_()'&+#"
_ISO_DAY = re.compile(r"(?<![\d-])(\d{4})-(\d{2})-(\d{2})(?![\d-])")
_HIDDEN = lambda ch: unicodedata.category(ch) in ("Cc", "Cf", "Cs", "Co", "Cn") and not ch.isspace()          # control, format, zero-width, unassigned
_ESCAPE = re.compile(r"%(?:u[0-9A-Fa-f]{4}|[0-9A-Fa-f]{2})")
_DRIVE = re.compile(r"[A-Za-z]:")
_EXT = re.compile(r"\.[A-Za-z0-9]{1,8}$")
_BARE = re.compile(r"(?:[A-Za-z][A-Za-z0-9+.-]*:)?//[^/\\?#]*[/\\]?$")                                       # a web address with a host and nothing after it


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


def _normal(words):
    text = unicodedata.normalize("NFKC", words)
    for _ in range(5):
        again = _decode(text)
        if again == text:
            break
        text = again
    text = "".join(" " if ch.isspace() else ch for ch in text if ch.isspace() or not _HIDDEN(ch))
    return re.sub(r" {2,}", " ", text).strip()


def _is_plain(text):
    return all(ch.isalnum() or ch in PLAIN_EXTRA for ch in text) and not _DRIVE.match(text)


def _file_name(text):
    """The final file name, or "": after the last character outside letters, digits and NAME_EXTRA, with an extension after a stem."""
    if _BARE.match(text):
        return ""
    cut = max((i for i, ch in enumerate(text) if not (ch.isalnum() or ch in NAME_EXTRA)), default=-1)
    name = text[cut + 1:].strip()
    ext = _EXT.search(name)
    return name if ext and name[:ext.start()].strip() else ""


def source_name(words):
    """The words to show for a stored `source`, or "" when there is nothing to show."""
    if not isinstance(words, str):
        return ""
    text = _normal(words)
    out = text if _is_plain(text) else _file_name(text)
    out = _ISO_DAY.sub(_day_as_shown, out).strip()
    return out if len(out) <= CAP else out[:CAP - 1].rstrip() + "\u2026"
