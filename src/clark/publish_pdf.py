"""The PDF option of Publish, as publish_flow.Publisher runs it. The routes' logic that is only about the PDF
is here, so that publish_flow.py has a few calls and nothing more.

A PDF is made by printing the finished report file with Chrome (pdf.py), once, before anything is written. What it holds is
checked from its own text (pdf_text.py): no text that was meant to be left out (the same markers as To client), no outside address,
and not the client folder's place. Then the PDF is saved beside the Local file (same name, .pdf) and, with To client ticked, in the client
folder under the report's name there with .pdf. A taken name is asked about first: the client folder's through the dialog (pdf_on_clash,
pdf_new_name, pdf_confirmed), the Local one through the system's own Save window, as the Local report is.

Request keys (all optional): pdf (true or false), pdf_on_clash ("number", "rename", "overwrite", "cancel"), pdf_new_name, pdf_confirmed.
Standard library only, Python 3.9.
"""
import hashlib
import logging
import re
import tempfile
from pathlib import Path

from clark import pdf, pdf_text, platform, publish, to_client

LOG = logging.getLogger("clark.publish_pdf")
KEYS = ("pdf", "pdf_on_clash", "pdf_new_name", "pdf_confirmed")
EXT = ".pdf"
UNREADABLE = "a PDF clark could not read back"
TOO_BIG = "a PDF too big to check"
SAVE_PROMPT = "Save the PDF"
NO_CHROME_LINE = "A PDF needs Google Chrome, and clark could not find it on this computer."
MESSAGES = {
    "bad_pdf_request": "The PDF box can only be ticked or unticked.",
    "no_chrome": pdf.NO_CHROME + " Nothing was published.",
    "pdf_failed": "{reason} Nothing was published.",
    "pdf_held_back": "The PDF was held back, because it would hold {what}. Nothing was published.",
    "pdf_unreadable": "The PDF could not be read back to check it, so it was held back. Nothing was published.",
    "pdf_too_big": "The PDF is too big to check, so it was held back. Nothing was published.",
    "pdf_clash_title": "A PDF with that name is already in the client folder.",
    "pdf_overwrite_note": "The PDF in the client folder will be replaced. The client's folder keeps no copy of the old one.",
    "pdf_local_not_pdf": "The PDF's name must end in .pdf. Nothing was published.",
    "pdf_local_place": "That is not a place the PDF can be saved. Choose another folder. Nothing was published.",
    "pdf_saved_local": "PDF saved as “{name}”.",
    "pdf_saved_client": "PDF copied to the client folder as “{name}”.",
    "pdf_not_saved": "The PDF was not saved: {why} The report itself is published.",
    "pdf_not_made_here": "No PDF was saved, because the publish did not finish.",
    "why_failed": "the client folder could not be written to.",
    "why_restored": "the copy in the client folder did not match, so the earlier PDF was put back.",
    "why_left": "the copy in the client folder did not match and could not be removed. Delete “{name}” from there.",
    "why_changed": "the client folder changed while it was being written to, so nothing was copied.",
}


def available(environ=None):
    """{"ok", "note"} for the dialog: whether Chrome can be found, and the one plain line saying why not when it cannot."""
    found = pdf.find_chrome(environ) if environ is not None else pdf.find_chrome()
    return {"ok": bool(found), "note": "" if found else NO_CHROME_LINE}


def split(body):
    """(request, rest): the PDF keys of a publish request, checked, and the request without them (which the rest of the route
    reads as it always has). `request` is {"on", "choice", "new_name", "confirmed", "error"}; error is a MESSAGES key or None."""
    body = body if isinstance(body, dict) else {}
    rest = {k: v for k, v in body.items() if k not in KEYS}
    req = {"on": body.get("pdf") is True, "choice": body.get("pdf_on_clash"), "new_name": body.get("pdf_new_name"),
           "confirmed": body.get("pdf_confirmed") is True, "error": None}
    if "pdf" in body and not isinstance(body["pdf"], bool):
        req["error"] = "bad_pdf_request"
    if req["choice"] not in (None,) + to_client.CHOICES or (req["new_name"] is not None and not isinstance(req["new_name"], str)):
        req["error"] = "bad_pdf_request"
    if req["choice"] == "overwrite" and not req["confirmed"]:
        req["error"] = "bad_pdf_request"
    return req, rest


def pdf_name(html_name):
    """The PDF's name for a report's name: the same, ending .pdf."""
    stem, _dot, ext = str(html_name).rpartition(".")
    return (stem if stem and ext.lower() == "html" else str(html_name)) + EXT


def rename_target(new_name, folder=None):
    """The name a typed Rename means for a PDF: trimmed, .pdf added if missing, made safe; None if nothing was typed."""
    typed = (new_name or "").strip()
    stem = typed[:-len(EXT)] if typed.lower().endswith(EXT) else typed
    if not stem.strip(". ") or typed.endswith(".") or to_client._has_hidden_character(typed):
        return None
    return platform.safe_name(typed if typed.lower().endswith(EXT) else typed + EXT, folder)


def client_name(fs, folder, html_name, html_replaced, req):
    """What to do about the PDF's name in the client folder, with nothing written. Returns one of
    ("write", name, replaces), ("ask", reply_fields) or ("stop", message). `html_replaced` is True when the report itself is
    being replaced (the person already confirmed that): the PDF of that name is replaced with it."""
    name = pdf_name(html_name)
    try:
        entries = [dict(e) for e in fs.listdir(folder)]
    except OSError:
        return "stop", to_client.MESSAGES["refused_nothing_published"].format(reason="The client folder could not be opened.")
    if req["choice"] == "cancel":
        return "stop", to_client.MESSAGES["cancelled"]
    if req["choice"] == "rename":
        name = rename_target(req["new_name"], folder)
        if name is None:
            return "stop", to_client.MESSAGES["empty_name"]
    hit = to_client._find(entries, name)
    if hit is None:
        return "write", name, False
    if hit["kind"] != "file":
        return "stop", to_client.MESSAGES["not_plain_file"].format(name=hit["name"])
    taken = [e["name"] for e in entries]
    if req["choice"] == "number":
        return "write", to_client.numbered_name(name, taken, folder), False
    if (req["choice"] == "overwrite" and req["confirmed"]) or html_replaced:
        return "write", name, True
    return "ask", {"name": name, "numbered": to_client.numbered_name(name, taken, folder), "can_overwrite": True}


def ask_reply(fields):
    """The question about a taken PDF name, in the shape the dialog already reads for the report's own (plus pdf: true)."""
    return {"ok": False, "code": "ask", "action": "ask", "message": MESSAGES["pdf_clash_title"], "name": fields["name"], "clash": True,
            "numbered": fields["numbered"], "can_overwrite": fields["can_overwrite"], "note": MESSAGES["pdf_overwrite_note"], "pdf": True}


def footer_text(as_at, number=None):
    """The footer's left side: "Publication N · DD-MM-YYYY", as the published page's own footer reads. With no number
    (a caller that has none) it is "Published DD-MM-YYYY"."""
    m = re.fullmatch(r"(\d{4})-(\d\d)-(\d\d)", str(as_at or ""))
    date = f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else str(as_at or "")
    if isinstance(number, int) and not isinstance(number, bool) and number > 0:
        return f"Publication {number}" + (f" · {date}" if date else "")
    return "Published " + date


def make(body_bytes, as_at, orientation="portrait", make_pdf=None, number=None):
    """The PDF's bytes for the finished report `body_bytes`. Raises pdf.PdfError in plain words."""
    make_pdf = make_pdf or pdf.make_pdf
    with tempfile.TemporaryDirectory(prefix="clark-pub-") as tmp:
        page = Path(tmp) / "report.html"
        page.write_bytes(body_bytes)
        return make_pdf(page, Path(tmp) / "report.pdf", orientation, footer_left=footer_text(as_at, number)).read_bytes()


INFO_STRING = re.compile(rb"/(?:Title|Author|Subject|Keywords|Creator|Producer)\s*(\((?:\\.|[^\\)])*\)|<[0-9a-fA-F\s]*>)", re.S)


def details_of(data):
    """The PDF's own details (title, author and so on) as text. They are not on any page, so they are read apart."""
    found = []
    for m in INFO_STRING.finditer(data):
        raw = m.group(1)
        if raw[:1] == b"<":
            try:
                value = bytes.fromhex(re.sub(rb"\s", b"", raw[1:-1]).decode("ascii") + ("0" if len(re.sub(rb"\s", b"", raw[1:-1])) % 2 else ""))
            except ValueError:
                value = b""
        else:
            value = re.sub(rb"\\(.)", rb"\1", raw[1:-1], flags=re.S)
        found.append(value.decode("utf-16-be", "replace") if value[:2] == b"\xfe\xff" else value.decode("latin-1"))
    return "\n".join(found)


def problems(data, markers, folder=None):
    """What is wrong with the PDF `data` as a file to send, as short phrases (to_client.held_words reads them), from its own
    text: the planted or dropped text, an address that goes outside, and the place of the client folder. Spaces are ignored on both
    sides (a line break can fall inside a word). A PDF whose text cannot be read is a problem, never taken as clean. The PDF's
    details (title, author) are checked in the same way, and a PDF over the size limit is held back."""
    if len(data) > publish.MAX_BYTES:
        return ["a file over the size limit"]
    try:
        text = pdf_text.text_of(data)
    except pdf_text.TooBig:
        return [TOO_BIG]
    except pdf_text.Undecodable:               # text that cannot be turned back into words cannot be checked
        return [UNREADABLE]
    if not text.strip():
        return [UNREADABLE]
    text = text + "\n" + details_of(data)
    found = list(publish.outside_addresses(text))
    squashed = to_client._key(re.sub(r"\s+", "", text))
    if folder and to_client._key(re.sub(r"\s+", "", str(folder))) in squashed:
        found.append("the location of the client folder")
    for m in markers or ():
        for spelling in (m, m.lower()):
            if spelling and to_client._key(re.sub(r"\s+", "", spelling)) in squashed:
                found.append("text that was meant to be left out")
                return found
    return found


class Step:
    """One publish's PDF: asked for, made, checked, then written once the report is. Held on the publisher for the call."""

    def __init__(self, req, pub):
        self.req, self.pub, self.data = req, pub, None
        self.local = None            # where the Local PDF goes (a Path), set by prepare
        self.client = None           # (folder, name, replaces), set by plan_client
        self.identity = None         # which folder the client folder was when it was checked, set by plan_client
        self.markers = None          # what must be absent from the PDF, set by prepare
        self.saved = None            # the client folder as saved in Settings, set by prepare
        self.note = None

    @property
    def on(self):
        return bool(self.req["on"])

    def plan_client(self, pub, plan, html_confirmed):
        """With To client ticked: the PDF's name in the client folder, before the Save window. None, or an (status, body) to send."""
        kind, *got = client_name(pub.fs, plan["folder"], plan["name"], bool(plan["replaces"] and html_confirmed), self.req)
        if kind == "ask":
            return 200, ask_reply(got[0])
        if kind == "stop":
            return 409, pub.fail("pdf_failed", MESSAGES["pdf_failed"].format(reason=got[0].replace(" Nothing was published.", "").rstrip()))
        self.client = (Path(plan["folder"]), got[0], got[1])
        self.identity = plan.get("identity")
        return None

    def prepare(self, pub, dest, built, as_at, store, code, markers, saved):
        """Make the PDF and check it, and choose where the Local one goes, with nothing written. None, or (status, body).
        `markers` is what To client already worked out, or None (then it is worked out here from the store)."""
        body_bytes = built["body"]
        if markers is None:
            from clark import page, publish_flow            # publish_flow imports this module, so it is imported here
            markers = publish_flow.markers_for(store, code, built["published"], page.page_html(pub.branding, view=True))
        if not pdf.find_chrome():
            return 409, pub.fail("no_chrome", MESSAGES["no_chrome"])
        local = Path(dest).with_suffix(EXT)
        if local.exists() or local.is_symlink():            # the system's Save window asks whether to replace it
            try:
                chosen = pub.choose_save_file(SAVE_PROMPT, local.name, start=local.parent)
            except platform.PlatformError as e:
                return 409, pub.fail("pdf_failed", MESSAGES["pdf_failed"].format(reason=str(e).rstrip()))
            if chosen is None:
                return 200, pub.fail("cancelled")
            local = Path(chosen)
            if local.suffix.lower() != EXT:
                return 409, pub.fail("pdf_failed", MESSAGES["pdf_local_not_pdf"])
            if (saved and pub.inside_folder(local.parent, saved)) or any(
                    pub.inside_folder(local, own) for own in (pub.data_dir, pub.backups_dir) if own):
                return 409, pub.fail("pdf_failed", MESSAGES["pdf_local_place"])
        try:
            data = make(body_bytes, as_at, number=built.get("number"))
        except pdf.PdfError as e:
            return 409, pub.fail("pdf_failed", MESSAGES["pdf_failed"].format(reason=str(e).rstrip()))
        bad = problems(data, markers, saved if self.client is not None else None)
        if bad:
            if bad == [UNREADABLE]:
                return 409, pub.fail("pdf_failed", MESSAGES["pdf_unreadable"])
            if bad == [TOO_BIG]:
                return 409, pub.fail("pdf_failed", MESSAGES["pdf_too_big"])
            return 409, pub.fail("pdf_failed", MESSAGES["pdf_held_back"].format(what=to_client.held_words(bad)))
        self.data, self.local, self.markers, self.saved = data, local, markers, saved
        return None

    def write(self, pub):
        """Save the PDF (Local, then the client folder) and read each back. Returns the sentences to add to the reply."""
        digest = hashlib.sha256(self.data).hexdigest()
        said, kept = [], 0
        try:
            platform.write_file(self.local, self.data)
            if hashlib.sha256(self.local.read_bytes()).hexdigest() != digest:
                raise OSError("differs")
            said.append(MESSAGES["pdf_saved_local"].format(name=self.local.name))
            kept += 1
        except (OSError, platform.PlatformError):
            said.append(MESSAGES["pdf_not_saved"].format(why="the folder could not be written to."))
        if self.client is not None:
            folder, name, replaces = self.client
            try:             # the one writer into a client folder: the folder is checked again, the copy read back and checked, a bad one taken back
                res = to_client.copy_to_client(
                    pub.fs, folder, name, self.data, project=None, at=None, markers=self.markers or [], replaces=replaces,
                    confirmed=replaces, local_sha256=digest, extra_problems=lambda d: problems(d, self.markers, self.saved),
                    guard={"data_dir": pub.data_dir, "backups_dir": pub.backups_dir, "identity": self.identity})
            except Exception:
                res = to_client.ClientResult(False, "failed", "")
            if res.ok:
                said.append(MESSAGES["pdf_saved_client"].format(name=name))
                kept += 1
            else:
                if res.restored:
                    why = MESSAGES["why_restored"]
                elif res.path and not res.nothing_written:
                    why = MESSAGES["why_left"].format(name=name)
                elif res.action == "refused":
                    why = MESSAGES["why_changed"]
                else:
                    why = MESSAGES["why_failed"]
                said.append(MESSAGES["pdf_not_saved"].format(why=why))
        LOG.info("pdf saved: %d of %d copies, %d bytes", kept, 2 if self.client is not None else 1, len(self.data))
        return said


def finish(step, out, status):
    """Add the PDF's part to a finished publish reply `out` (a dict): its sentences, and its names. Writes the PDF only when the
    report itself was published. Nothing is added for a publish with no PDF."""
    if step is None or not step.on or step.data is None or not isinstance(out, dict):
        return
    if not (status == 200 and out.get("ok") is True):
        if out.get("local_saved") is True:
            out["message"] = (out.get("message") or "") + " " + MESSAGES["pdf_not_made_here"]
        return
    said = step.write(step.pub)
    out["message"] = (out.get("message") or "") + " " + " ".join(said)
    out["pdf_name"] = step.local.name
