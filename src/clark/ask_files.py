"""#1292 S14: the files a person adds to one question ("files" in POST /api/ask). Unguarded; ask_service.py calls it. Nothing is written
anywhere: the bytes are read from the request, turned into passages named by the file name, and gone when the question is answered.

Each file is {"name", "data"} (the bytes in base64). At most FILE_MAX files of FILE_BYTES each. A name is a plain file name (the same
rule as a passage label, and no slash at all). A text, Markdown or CSV file is read as text; its text goes through the same key and
password screen as every other passage, and one file that looks like it holds a key or a password refuses the whole question (nothing is
sent), naming the file but never what matched. PDF, Word, Excel and picture files are not read yet (NEEDS RULING: a reader for them, and
whether the command takes pictures); they are refused in plain words so nothing is sent without being screened.
"""
import base64
import binascii
import re

from clark import ask

FILE_MAX = 5
FILE_BYTES = 10 * 1024 * 1024
TEXT_KINDS = re.compile(r"\.(txt|md|csv)$", re.IGNORECASE)
NOT_YET = re.compile(r"\.(pdf|docx|xlsx|png|jpe?g)$", re.IGNORECASE)


def _refuse(message):
    raise ask.AskRefused(message)


# Row 1294: the words when the Files switch is off (ruled by the design lead 20-11 10:30, NEW-WORDS.md): the file refusal is true here, the question is not sent either
OFF_WORDS = "Files are turned off for asking, so none were sent. Turn them on in Settings, or ask again without them."


def passages(files, allowed=True):
    """The passages for the files named in a request, in order. `files` is the request's value (None or [] means none). Raises
    `ask.AskRefused` (plain words) for a wrong shape, too many or too large files, a bad name, bytes that are not base64, a kind
    that is not read yet, or a file that looks like it holds a password or a key. Row 1294: with `allowed` False (the Files switch is off for
    the computer or the project) any file at all is refused, in the words of OFF_WORDS."""
    if files is None or files == []:
        return []
    if not allowed:
        _refuse(OFF_WORDS)
    if not isinstance(files, list):
        _refuse("The files could not be read. Nothing was sent. Reload the page and ask again.")
    if len(files) > FILE_MAX:
        _refuse(f"{FILE_MAX} files at most for one question. Nothing was sent. Remove one and ask again.")
    out = []
    for item in files:
        if not (isinstance(item, dict) and set(item) == {"name", "data"} and isinstance(item["name"], str) and isinstance(item["data"], str)):
            _refuse("The files could not be read. Nothing was sent. Reload the page and ask again.")
        name = item["name"]
        if not ask._label_ok(name) or "/" in name or "\x00" in name:
            _refuse("A file has a name that cannot be used. Nothing was sent.")
        if len(item["data"]) > FILE_BYTES * 4 // 3 + 8:                 # base64 is a third longer: refuse before decoding
            _refuse(f"{name} is over 10 MB. Nothing was sent. Add a smaller one.")
        try:
            raw = base64.b64decode(item["data"], validate=True)
        except (binascii.Error, ValueError):
            _refuse(f"{name} could not be read. Nothing was sent.")
        if len(raw) > FILE_BYTES:
            _refuse(f"{name} is over 10 MB. Nothing was sent. Add a smaller one.")
        if NOT_YET.search(name) or not TEXT_KINDS.search(name):
            _refuse(f"{name} cannot be read yet. Nothing was sent. Add a text, Markdown or CSV file.")
        text = raw.decode("utf-8", errors="replace")
        if ask._secret(text) or ask._secret(name):
            _refuse(f"{name} looks like it holds a password or a key. Nothing was sent. Take it out and ask again.")
        out.append(ask.Passage(label=name, text=text))
    return out
