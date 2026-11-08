"""One document (H7, #96): the content of a section of type 'onedoc', one file to read with a few lines about it. The file and
text rules are Documents and links' (doclinks.py), so the Files and links templates never drift apart. See base.py.

The stored content (canonical JSON, checked field by field; anything else is refused):

    {"v": 1, "file": {"name": NAME, "rel": "Report files/" + NAME, "bytes": N}, "label": TEXT, "text": [LINE, ...], "html": HTML}

`file` is the one the server copied into the client folder's "Report files" folder (POST /api/section-file; choosing another
replaces it on the section, never in the folder); `label` the words shown for it ('' shows the file's name); `text` at most
TEXT_LINES lines of at most LINE_MAX characters (what older clarks wrote: still read, and shown when there is
no `html`); `html` the words as the one editor writes them, kept through sanitise.clean_html (at most HTML_MAX characters once
cleaned; '' for none). The editor saves `html` and empties `text`. Published: those fields, picked by name; nothing until there is a file (the
file is the point of the section, so words alone stay out of the file).
"""
from clark.section_kinds import doclinks as files

READY = True
LIMIT = 32768
EMPTY = ""
TEXT_LINES = 6
LINE_MAX = 600
HTML_MAX = TEXT_LINES * LINE_MAX
BAD_TEXT = f"The words under the file can be {TEXT_LINES} paragraphs of {LINE_MAX} characters at most. Shorten them and try again."


def check(value, rules):
    value = files.fields(value, ("v", "file", "label", "text", "html"), ("v",))
    files.version(value)
    out = {"v": 1, "label": files.words(value.get("label", ""), rules),
           "text": files.paragraphs(value.get("text", []), rules, TEXT_LINES, LINE_MAX, BAD_TEXT)}
    html = files.rich(value.get("html"), rules, HTML_MAX, BAD_TEXT)
    if html:
        out["html"] = html
    if value.get("file") is not None:
        out["file"] = files.file_entry(value["file"])
    return out


def published(value, ctx):
    """The file, its words and the lines under it. None until there is a file."""
    f = value.get("file") if isinstance(value, dict) else None
    if not f:
        return None
    return {"content": {"file": {"name": f["name"], "rel": f["rel"], "bytes": f["bytes"]}, "label": value.get("label", ""),
                        "text": list(value.get("text") or []), **({"html": value["html"]} if value.get("html") else {})}}


def add_file(value, entry):
    """The content with `entry` ({name, rel, bytes}, made by the server) as its file, in place of any earlier one (that file stays
    in the folder). `value` is the checked content, or None for a section with none yet."""
    out = {"v": 1, "label": (value or {}).get("label", ""), "text": list((value or {}).get("text") or [])}
    if (value or {}).get("html"):
        out["html"] = value["html"]
    out["file"] = files.file_entry(entry)
    return out

