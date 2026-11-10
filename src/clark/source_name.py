"""The Source NAME (row 1077, the owner's ruling of 10-11-2026): a work item's or milestone's `source` words as a person may see them,
anywhere the Source line is drawn (the live peek through activity_read, a published file through publish.select).

The stored words are kept as they are in the database. Shown: hidden characters are dropped, every kind of slash (/, \\, the fullwidth,
division and lookalike slashes, %2F and %5C escapes decoded) is one separator, and a run of white space is one space.

STRICT RULE (privacy first): a value holding any separator outside a date (01/10/2026) or a closing tag (</b>) is a path, whatever its
style, spaces or commas: the file publishes ONLY the final file name (the text after the last separator, up to its extension; a URL's
?query and #fragment are cut first) and nothing else from the value, no words before it. A separator with no file name after it publishes
nothing. A value with no separator keeps its words, commas and dates: a stored YYYY-MM-DD reads DD-MM-YYYY when it is a real day. The whole
is cut at 120 characters with an ellipsis. Imports nothing from clark.
"""
import re
import unicodedata
from datetime import date

CAP = 120
_ISO_DAY = re.compile(r"(?<![\d-])(\d{4})-(\d{2})-(\d{2})(?![\d-])")
_SLASHES = str.maketrans({"\uff0f": "/", "\uff3c": "\\", "\u2215": "/", "\u29f8": "/", "\u2044": "/", "\u2216": "\\", "\ufe68": "\\", "\u2571": "/", "\u29f5": "\\"})
_PERCENT = re.compile(r"%25(?=2[Ff]|5[Cc]|3[Aa])")
_ESCAPED = re.compile(r"%(2[Ff]|5[Cc]|3[Aa])")                                                           # %2F, %5C, %3A: a separator or a colon, escaped
_SPLIT_ESCAPE = re.compile(r"%(?:\s*2\s*5)*\s*(?:2\s*[Ff]|5\s*[Cc]|3\s*[Aa])")                                   # an escape with white space inside it ("%\n5C")
_SEP = re.compile(r"[\\/]")
_DATE = re.compile(r"\d{1,4}[/\\]\d{1,2}[/\\]\d{1,4}")                                                    # 01/10/2026: a date, not a path
_TAG = re.compile(r"</|/>")                                                                              # markup is data
_QUERY = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://[^?#]*")                                               # a web address: its ?query and #fragment are cut
_EXT = re.compile(r"\.[A-Za-z0-9]{1,8}(?=[\s,?#]|$)")                                                  # a file name's extension


def _day_as_shown(m):
    try:
        date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return m.group(0)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"


def _plain(text):
    """Hidden characters out, the other slashes plain ones, separator escapes decoded, white space runs one space."""
    text = "".join(" " if ch.isspace() else ch for ch in text if unicodedata.category(ch) not in ("Cc", "Cf") or ch.isspace()).translate(_SLASHES)
    text = _SPLIT_ESCAPE.sub(lambda m: re.sub(r"\s+", "", m.group(0)), text)
    for _ in range(3):                                   # an escape of an escape (%252F) too
        text = _ESCAPED.sub(lambda m: chr(int(m.group(1), 16)), _PERCENT.sub("%", text))
    return re.sub(r" {2,}", " ", text).strip()


def _is_path(text):
    return bool(_SEP.search(_DATE.sub("", _TAG.sub("", text))))


def _file_name(text):
    """The final file name of a path, or "" (a folder, a bare host, nothing after the last separator, no extension)."""
    web = _QUERY.match(text)
    if web:
        text = web.group(0)
        if not _SEP.search(text[text.index("://") + 3:]):
            return ""                                    # a bare host
    name = _SEP.split(text)[-1].strip()
    last = None
    for last in _EXT.finditer(name):
        pass
    return name[:last.end()].strip() if last and last.start() > 0 or (last and name[:last.start()].strip()) else ""


def source_name(words):
    """The words to show for a stored `source`, or "" when there is nothing to show."""
    if not isinstance(words, str):
        return ""
    text = _plain(words)
    out = _file_name(text) if _is_path(text) else text
    out = _ISO_DAY.sub(_day_as_shown, out).strip()
    return out if len(out) <= CAP else out[:CAP - 1].rstrip() + "\u2026"
