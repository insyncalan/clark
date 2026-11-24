"""ask: the logic of POST /api/ask, GET /api/ask/status, POST /api/ask/stop and POST /api/ask/change/dry and /apply (#47c, #47d,
#47e). Unguarded; server.py only routes to it. It never opens the database for writing: a change the answer suggests comes back as
data, and is saved only by the person's Apply, through ask_apply.AskApply and changes.make_ask_change (the one save path).

A SUGGESTED CHANGE IS HELD HERE, NOT TAKEN FROM THE PAGE (#47e). When an answer suggests changes, the server keeps them in memory
under a random `reply` ID for REPLY_MINUTES, with the project and whether passages from the project's saved folders were sent with
the question (`from_source`). The dry run takes only {project, reply}: the page can't send a change of its own, and has no field
that could clear the mark. A change from an answer that read the person's files always needs the separate Confirm, whether the
answer cited the file or not (a file it was given can steer it without being cited). Each reply's dry run is made once; Apply
takes the offer the dry run gave, used once (ask_apply.py). Neither route ever asks the provider.

THE SWITCH IS HONOURED HERE, ON THE SERVER (review note). Before anything is read for a question, and again just
before the request goes to the provider, the store's switch is read (`store.ask_enabled()`, which reads as off when it cannot
say). While it is off the provider is never asked, so "nothing is sent while asking is off" holds for any caller: the page, a
stale tab or anything else that can reach the route.

WHAT IS SENT. The question, the chat's earlier turns as the page holds them (they are kept nowhere else), and passages built only
from what the published file would carry (ask_data.py, through publish.select), and passages from the project's own saved
folders (ask_passages.py, every file opened again through reach.read_bytes; a PDF that cannot be read is counted with its reason). The
folders are read for the open project only. The reply carries how many files were left out for safety.

READ ONLY. The database is only ever opened read-only here (`connect(path, readonly=True)`), so nothing in this module can write
it, even by mistake: a source test in tests/test_ask_route.py fails if an ask module opens it any other way.

Every answer is (status, {ok, ...}) with plain words; a refusal also has a stable `code`. No question, passage, reply or path is
logged or kept.
"""
import re
import secrets
import sqlite3
import threading
import datetime
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

from clark import ask, ask_apply, ask_data, ask_words, ask_files, ask_folders, ask_index, ask_passages, ask_usage, pdf_link, pdf_reader, platform, publish, reach, secret_screen, settings
from clark.store import CONNECTORS, Store, connect

PROJECT_CODE = re.compile(r"[A-Z][A-Z0-9]{2,6}")
MESSAGES = {
    "bad_request": "That question could not be read. Nothing was sent. Reload the page and ask again.",
    "bad_project_code": "That isn't a project here. Nothing was sent.",
    "project_not_found": "That project isn't here. Nothing was sent.",
    "project_archived": "That project is archived. Restore it before asking about it. Nothing was sent.",
    "asking_off": "Asking is off, so nothing was sent. Turn it on in Settings to ask questions.",
    "busy": "The saved data could not be opened just now. Wait a moment and try again. Nothing was sent.",
    "not_running": "No question is being answered just now.",
    "stopping": "Stopping.",
    "change_bad_request": "That change could not be read. Nothing was changed. Reload the page and ask again.",
    "no_reply": "That answer's changes are no longer waiting. Nothing was changed. Ask again.",
    "shown_already": "Those changes were shown already. Nothing was changed. Ask again to see them afresh.",
    "open_asking_off": "Asking is off, so this file can't be opened from here. Turn it on in Settings.",   # #943: the open-file click's own sentence
    "file_unavailable": "That file can't be opened from here.",
    "folders_unreadable": "Your folders couldn't be read just now, so nothing was sent. Try again, or remove a folder in Settings.",
}
FIELDS = {"project", "question", "earlier", "files"}
DRY_FIELDS = {"project", "reply"}
UNREADY = ("busy", "no_data")      # row 1293 line 10: a dry run refused for these saved nothing and read nothing, so the reply may be tried again
PDF_START = b"%PDF-"      # #943: what a PDF file begins with
OPEN_FIELDS = {"project", "file", "page"}
APPLY_FIELDS = {"project", "offer", "confirm"}
REPLY_MINUTES = ask_apply.OFFER_MINUTES
MAX_REPLIES = 20
PASSAGE_SHOWN = 600        # characters of a source passage shown beside a change that came from it
PROJECT_SHARE = ask.BUDGET // 2      # characters of the budget the project's own data may take (row 1508: half of it, 600,000 on main); the folders get the rest


class Started(threading.Event):
    """The `cancel` event of one question. A provider reads it once, the moment it has taken its place and the run really starts (a
    question that finds the provider busy never reads it), so reading it is what marks the run as started."""

    def __init__(self):
        super().__init__()
        self.started = False

    def is_set(self):
        self.started = True
        return super().is_set()


class Run:
    """Row 1306 test 7: one question's own record: its project, the connectors it was given, and its own cancel event."""

    def __init__(self, project, connectors):
        self.project, self.connectors, self.cancel = project, tuple(connectors), Started()

    @property
    def started(self):
        return self.cancel.started


class AskService:
    """`db_path` is the database; `provider` an ask.Provider (the one provider module's in clark; a stub in tests); `onedrive_roots` as
    the launcher's."""

    def __init__(self, db_path, provider, onedrive_roots=None, *, data_dir=None, home=None, applier=None, clock=time.monotonic, open_pdf=None, indexer=None, used_hook=None):
        self.db_path = Path(db_path)
        self.data_dir = Path(data_dir) if data_dir else self.db_path.parent
        self.home = home
        self.provider = provider
        self.owner = object()                        # #284: this service's token; its Stop ends only a run it asked for
        self.onedrive_roots = list(platform.onedrive_roots() if onedrive_roots is None else onedrive_roots)
        self.lock = threading.Lock()                 # the store is opened by one question at a time
        self.applier = applier or ask_apply.AskApply(self.db_path, self.onedrive_roots)
        self.clock = clock
        self.indexer = indexer                       # ask_index.Indexer or None (Row 1366): a finished index answers a question without opening a file
        self.used_hook = used_hook                   # Row 1306: called with each connector name read in an answer (the launcher writes the log line; an ask module never logs)
        self.open_pdf = open_pdf or platform.open_pdf_at      # #943: the one thing that starts a viewer (a stub in tests)
        self.usage = ask_usage.AskUsage(self.data_dir)      # row 1294: questions and tokens this month, per project, kept on this computer
        self.today = datetime.date.today                    # a seam for tests
        self.replies = {}                            # reply ID -> Held: the changes an answer suggested, kept on the server
        self.replies_lock = threading.Lock()
        self.runs = []                               # row 1306 test 7: the questions on their way to or at the provider, each a Run (its own, never shared)
        self.using_lock = threading.Lock()
        self.cancels = set()                         # one threading.Event per question being prepared or asked; Stop sets them all
        self.cancels_lock = threading.Lock()

    def fail(self, code, message=None):
        return {"ok": False, "code": code, "message": message or MESSAGES[code]}

    def folders_for(self, store, code):
        """The folders a question in project `code` may read (row 1294): those for all projects first, then the project's own, at most ask_folders.MAX_FOLDERS."""
        own = [r["path"] for r in store.read("source_folders", code) if r.get("project", code) == code]
        out = []
        for p in [*ask_folders.shared_folders(self.data_dir), *own]:
            if p not in out:
                out.append(p)
        return out[:ask_folders.MAX_FOLDERS]

    def reader(self):
        """The store, opened read-only (a write through it fails in SQLite itself)."""
        return Store(connect(self.db_path, readonly=True), self.db_path, self.onedrive_roots)

    def enabled(self):
        """The switch, read now from the store; off when the store can't be opened or can't say (never fails open)."""
        try:
            store = self.reader()
        except (sqlite3.Error, OSError, TypeError):
            return False
        try:
            return store.ask_enabled() is True
        except Exception:  # noqa: BLE001  a switch that can't be read is off
            return False
        finally:
            store.close()

    def project_off(self, code):
        """Row 1294: True when project `code` has asking turned off for itself, or the store can't be opened or can't say (never fails open). A project
        that does not exist is not "off" here: the routes answer it as not found, and nothing is sent for it. The computer-wide switch is enabled()."""
        try:
            store = self.reader()
        except (sqlite3.Error, OSError, TypeError):
            return True
        try:
            return store.read("projects", ref=code) is not None and store.ask_off_here(code)
        except Exception:  # noqa: BLE001  a value that can't be read is off
            return True
        finally:
            store.close()

    def files_allowed(self, code):
        """Row 1294: whether files may be added to a question in project `code` (the computer's Files switch on and the project not off); False when the
        store can't be opened or can't say (never fails open)."""
        try:
            store = self.reader()
        except (sqlite3.Error, OSError, TypeError):
            return False
        try:
            return store.ask_files_allowed(code) is True
        except Exception:  # noqa: BLE001  a switch that can't be read is off
            return False
        finally:
            store.close()

    def connectors_now(self, code, chosen):
        """The connectors of `chosen` that are still On for project `code`, read now; none when the store can't say (never fails open)."""
        try:
            store = self.reader()
        except (sqlite3.Error, OSError, TypeError):
            return ()
        try:
            return tuple(c for c in chosen if store.connector_allowed(c, code))
        except Exception:  # noqa: BLE001  a switch that can't be read is off
            return ()
        finally:
            store.close()

    def stop_off(self):
        """Row 1306 test 7: after a connector change was saved (an Off, or an Undo that went back to Off), stop every question that was given a
        connector which is no longer On for its project. One that has not reached the provider yet is cancelled so it never starts; one at the
        provider is stopped. A question the change does not touch is left alone. True when a running one was stopped. Nothing is changed."""
        with self.using_lock:
            runs = list(self.runs)
        stopped = False
        for run in runs:
            if self.connectors_now(run.project, run.connectors) == run.connectors:
                continue
            run.cancel.set()                         # a question still before the provider's start never starts (it reads this when it starts)
            if run.started:
                stop = getattr(self.provider, "stop", None)
                stopped = (bool(stop(owner=self.owner)) if callable(stop) else False) or stopped
        return stopped

    # ----- GET /api/ask/status -----
    def status(self, *_ignored):
        on = self.enabled()
        if platform.container_mode():             # Row 1293: in Docker nothing can be asked; the panel and Settings say so in these words
            return 200, {"ok": True, "ask_enabled": on, "connected": False, "why": ask_words.DOCKER, "docker": True}
        st = ask.answer_status(self.provider) if on else {"connected": False, "why": MESSAGES["asking_off"]}
        label = getattr(self.provider, "label", "")      # #54: who a question goes to, so the page can say so truly
        return 200, {"ok": True, "ask_enabled": on, "connected": st["connected"], "why": st["why"], **({"provider": label} if label else {})}

    # ----- GET /api/ask-usage -----
    def usage_read(self, *_ignored):
        """Usage in tokens (row 1294): this month so far, per project and in all, read only. {ok, title, asking, projects: [{code, name, questions,
        tokens, unreported}], all: {questions, tokens, unreported}, note}; a project with no question shows 0. Archived projects with no question are left out."""
        day = self.today()
        kept = self.usage.month(day)
        try:
            store = self.reader()
        except (sqlite3.Error, OSError, TypeError):
            return 409, self.fail("busy")
        try:
            rows = [r for r in store.read("projects") if isinstance(r.get("code"), str)]
        finally:
            store.close()
        out = []
        for r in sorted(rows, key=lambda r: r["code"]):
            got = kept.get(r["code"], {"questions": 0, "tokens": 0, "unreported": 0})
            if r.get("archived") and not got["questions"]:
                continue
            out.append({"code": r["code"], "name": r.get("name") or "", **got})
        total = {"questions": sum(p["questions"] for p in out), "tokens": sum(p["tokens"] for p in out),
                 "unreported": sum(p["unreported"] for p in out)}
        return 200, {"ok": True, "title": ask_usage.group_title(day), "asking": self.enabled(), "projects": out, "all": total, "note": ask_usage.READ_ONLY}

    # ----- POST /api/ask/stop -----
    def stop(self, body=None):
        if body not in (None, {}):
            return 400, self.fail("bad_request")
        stop = getattr(self.provider, "stop", None)
        with self.cancels_lock:
            pending = list(self.cancels)
            for event in pending:
                event.set()                          # a question still reading its data is told too: its request goes out cancelled, so the provider never starts
        with self.using_lock:
            for run in self.runs:
                run.cancel.set()                     # one on its way to the provider (its record is in): its request carries this event, so the provider never starts it
        running = (bool(stop(owner=self.owner)) if callable(stop) else False) or bool(pending)
        return 200, {"ok": True, "stopped": running, "message": MESSAGES["stopping" if running else "not_running"]}

    # ----- POST /api/ask -----
    def read_body(self, body):
        """(project, question, earlier) or None for a body of the wrong shape."""
        if not isinstance(body, dict) or not set(body) <= FIELDS or not {"project", "question"} <= set(body):
            return None
        code, question, earlier = body["project"], body["question"], body.get("earlier", [])
        if not isinstance(question, str) or not isinstance(earlier, list):
            return None
        turns = []
        for t in earlier:
            if not (isinstance(t, dict) and set(t) == {"role", "text"} and t["role"] in ask.ROLES and isinstance(t["text"], str)):
                return None
            turns.append((t["role"], t["text"]))
        return code, question, turns

    def ask(self, body):
        cancel = threading.Event()
        with self.cancels_lock:
            self.cancels.add(cancel)
        try:
            return self.ask_one(body, cancel)
        finally:
            with self.cancels_lock:
                self.cancels.discard(cancel)

    def ask_one(self, body, cancel):
        got = self.read_body(body)
        if got is None:
            return 400, self.fail("bad_request")
        code, question, earlier = got
        if not isinstance(code, str) or not PROJECT_CODE.fullmatch(code):
            return 400, self.fail("bad_project_code")
        if platform.container_mode():                # Row 1293: refused before anything is read or sent
            return 409, self.fail("docker", ask_words.DOCKER)
        if not self.enabled() or self.project_off(code):                       # the gate: nothing is read for the question, nothing is sent
            return 409, self.fail("asking_off")
        try:
            ask.check_question(question, earlier)    # the screen comes first: no data is ranked or read for a question that holds a secret
        except ask.AskRefused as e:
            return 400, self.fail("refused", str(e))
        try:
            # item 1292 S14: the files of this question only, screened like any passage; nothing is kept. Row 1294: the Files switch is read now, only for a question that carries files
            added = ask_files.passages(body.get("files"), self.files_allowed(code) if body.get("files") else True)
        except ask.AskRefused as e:
            return 400, self.fail("refused", str(e))
        window = getattr(self.provider, "most_chars", lambda: None)()      # Row 1293: what the chosen model takes; a full question is cut to it, not refused
        budget = ask.budget_for(window)
        budget_left = max(0, budget - sum(len(p.text) for p in added))      # Row 1367 (#2045 CHANGES): a file added to the question keeps its room, in characters and in passages, before the project and the folders take theirs
        with self.lock:
            try:
                store = self.reader()
            except (sqlite3.Error, OSError, TypeError):
                return 409, self.fail("busy")
            try:
                row = store.read("projects", ref=code)
                if row is None:
                    return 404, self.fail("project_not_found")
                if row.get("archived"):
                    return 409, self.fail("project_archived")
                try:
                    data = ask_data.project_data(store, code, " ".join([question, *ask_data.ids_in_turns(earlier)]), min(PROJECT_SHARE, budget_left),
                                                  limit=max(0, ask.MAX_PASSAGES - len(added)))
                except publish.PublishError:
                    return 404, self.fail("project_not_found")
                folders = self.folders_for(store, code)
                on_connectors = tuple(c for c in CONNECTORS if store.connector_allowed(c, code))      # row 1306: switch On and the project has not turned it Off
                standing = {"all": store.ask_instructions(), "project": store.ask_instructions(code)}      # row 1294: sent with the question, the one for all projects first
            finally:
                store.close()
        used = sum(len(p.text) for p in data.passages)         # the folders get what the project's own data left of the budget
        try:
            room = max(0, ask.MAX_PASSAGES - len(added) - len(data.passages))
            if folders and self.indexer is not None and self.indexer.current(code, folders):
                found = ask_index.folder_data(self.data_dir, code, " ".join([question, *ask_data.ids_in_turns(earlier)]), budget_left - used, room)      # a follow-up ("and who owns it?") also looks for the item IDs the chat named
            else:
                found = ask_passages.folder_data(folders, self.data_dir, question, budget_left - used, self.home, room)
        except Exception:                            # noqa: BLE001 a folder that fails in a way not foreseen sends nothing
            return 200, self.fail("folders_unreadable")
        try:
            request = ask.build_request(question, tuple(data.passages) + tuple(found.passages) + tuple(added), earlier,
                                        today=data.today, partial=ask_data.partial_lines(data.counts), instructions=standing,
                                        max_request=ask.request_cap(window), files=len(added))
        except ask.AskRefused as e:
            return 400, self.fail("refused", str(e))
        facts = data.facts
        if cancel.is_set():                          # a Stop that came while the data was read: nothing is sent
            return 200, {"ok": False, "code": "no_answer", "message": ask.STOPPED}
        if not self.enabled() or self.project_off(code):                       # the gate again, just before anything leaves: a switch turned off meanwhile wins
            return 409, self.fail("asking_off")
        run = Run(code, on_connectors)               # row 1306 test 7: the record goes in first, holding what the store said earlier ...
        with self.using_lock:
            self.runs.append(run)
        on_connectors = self.connectors_now(code, on_connectors)      # ... so an Off saved from here on finds it (stop_off) and one saved before is read here
        run.connectors = on_connectors               # (an Off between the read and this line still differs from the wider list and cancels the run)
        if cancel.is_set():                          # a Stop that came before the record went in: the request goes out cancelled, so the provider never starts it
            run.cancel.set()
        try:
            reply = ask.ask_provider(self.provider, replace(request, owner=self.owner, connectors=on_connectors, person=settings.profile(self.data_dir)["name"], cancel=run.cancel), codes=(code,), exists=lambda ref: ref in facts,
                                     facts=lambda ref: facts.get(ref))
        finally:
            with self.using_lock:
                self.runs.remove(run)                # only this question's own entry: another's is never touched
        if isinstance(reply, ask.Failure):
            return 200, {"ok": False, "code": "no_answer", "message": reply.message, **({"held": True} if reply.message == ask.HELD_BACK else {})}
        self.usage.record(code, getattr(self.provider, "last_tokens", None), self.today())      # row 1294: one answered question, with the tokens the command reported
        if cancel.is_set():                          # row 1293 line 7: a Stop that came while the provider was finishing: the answer is not given and nothing is held (the tokens were spent, so they stay counted)
            return 200, {"ok": False, "code": "no_answer", "message": ask.STOPPED}
        index_note = {}
        notes = [n for n in (ask.dropped_note(request.dropped_turns), ask.secret_note(request.left_out_secret + data.secret),
                             left_out_note(found.left_out), ask.left_out_text(request.left_out), *ask_data.left_out_lines(data.counts), *folder_notes(found),
                             *hidden_notes(request.hidden, request.passages)) if n]
        notes += [n for n in (ask_words.LONG_ROWS if data.cut else "", ask_words.REPLY_CUT if reply.reply_cut else "",
                              ask_words.sent_about(len(request.text))) if n]      # Row 1293: said only when it happened
        if folders and self.indexer is not None:        # row 7 of Row 1366: only while the index is still being read, never once it is complete
            n = self.indexer.not_yet(code)
            note = ask_index.answer_note({"not_yet": n}) if isinstance(n, int) else ""
            if note:
                index_note = {"index_note": note, "index_note_at": len(notes)}      # its own field, so a page that draws only some notes (Cards) never gets it
        conn = connector_used(getattr(self.provider, "last_line", None))      # row 1306: what the real run did (None: no connector in the run)
        if conn and conn["line"]:
            notes.append(conn["line"])
        for part in (conn or {}).get("used", ()):
            if self.used_hook:
                try:
                    self.used_hook(part)
                except Exception:                    # a log that cannot be written never stops an answer
                    pass
        sent = tuple(data.passages) + tuple(found.passages) + tuple(added)      # (a file added to the question counts as one the answer read, so a change from it needs the separate Confirm)  # request.kept maps each passage sent to its place here (some may be left out)
        folder_ids = {pid for (pid, _label), i in zip(request.passages, request.kept) if i >= len(data.passages)}
        texts = {pid: sent[i].text for (pid, _label), i in zip(request.passages, request.kept)}
        held = self.hold(code, reply, request, folder_ids, texts, bool(conn) or bool(on_connectors)) if reply.changes else None      # fail closed: a connector On and no Used line read (a second run reset it) still needs the Confirm
        return 200, {**({"used": conn} if conn else {}), "ok": True, "answer": reply.answer, "parsed": reply.parsed, "cites": list(reply.cites),
                     "sources": [{"id": pid, "label": label, "page": page_of(sent[i]), "file": file_of(sent[i])}
                                 for (pid, label), i in zip(request.passages, request.kept) if pid in reply.cites],
                     "flags": [{"kind": f.kind, "ref": f.ref, "message": f.message} for f in reply.flags],
                     "items": [{"id": i["id"], "state": list(i["state"])} for i in reply.items],
                     "read": ask_data.read_counts(data),
                     "changes": [dict(c) for c in reply.changes], "notes": notes, **index_note, "reply": held, "draft": draft_via(reply.draft, conn),
                     "left_out_for_safety": found.safety}

    # ----- POST /api/ask/open-source (#943) -----
    def open_source(self, body):
        """{project, file, page} -> the PDF `file` (a source's `file`: a name inside one of the project's saved folders) opened at
        `page` (a whole number, or null for the file alone) in the system's PDF viewer. The name is mapped back to the saved folder
        here, judged again by reach and pdf_link (a .pdf, no links, inside the folder, and starting %PDF-), and opened only by platform.open_pdf_at.
        Nothing is read, sent or changed.
        Known LOW (#943, note only): if the viewer's start times out here but Chrome launches late, the PDF can open twice."""
        if not isinstance(body, dict) or set(body) != OPEN_FIELDS or not isinstance(body["project"], str) or not isinstance(body["file"], str):
            return 400, self.fail("bad_request")
        code, name, page = body["project"], body["file"], body["page"]
        if not PROJECT_CODE.fullmatch(code):
            return 400, self.fail("bad_project_code")
        if not self.enabled() or self.project_off(code):                       # fails closed, like the other ask routes: asking off, nothing is looked at
            return 409, self.fail("asking_off", MESSAGES["open_asking_off"])   # same code, its own sentence (MESSAGES["asking_off"] is for the other routes)
        if page is not None and (isinstance(page, bool) or not isinstance(page, int)):
            return 400, self.fail("bad_request")
        parts = name.split("/")
        if len(parts) < 2 or any(p in ("", ".", "..") for p in parts) or "\x00" in name or "\\" in name:
            return 400, self.fail("file_unavailable")
        with self.lock:
            try:
                store = self.reader()
            except (sqlite3.Error, OSError, TypeError):
                return 409, self.fail("busy")
            try:
                if store.read("projects", ref=code) is None:
                    return 404, self.fail("project_not_found")
                folders = self.folders_for(store, code)
            finally:
                store.close()
        for folder in folders:
            if Path(str(folder)).name != parts[0]:
                continue
            path = Path(str(folder)).joinpath(*parts[1:])
            try:
                kind, _why = reach.classify(path, "read", folders, self.data_dir, self.home)
                url = pdf_link.pdf_url(path, page, folders)
            except (pdf_link.PdfLinkRefused, OSError, ValueError, RuntimeError):
                continue
            if kind != "ordinary":
                continue
            try:
                start, _more = reach.read_bytes(path, folders, self.data_dir, len(PDF_START), self.home)    # the same reach check as a read
            except (reach.Never, OSError, ValueError):
                continue
            if start != PDF_START:                   # a name ending .pdf is not enough: the file must start like a PDF
                continue
            try:
                self.open_pdf(path, url)
            except (platform.PlatformError, OSError):      # the system's own text is never shown: the route's plain sentence
                return 409, self.fail("file_unavailable")
            return 200, {"ok": True}
        return 409, self.fail("file_unavailable")

    # ----- the changes an answer suggested, held on the server (#47e) -----
    def hold(self, code, reply, request, folder_ids, texts, from_connector=False):
        """Keep a reply's changes under a new reply ID, marked from_source when any folder passage was sent or a connector was in the run (row 1306:
        what a connector returns is text anyone can write, so a change after it needs the same separate Confirm). The passages shown
        beside a change are the folder passages it names or the answer cites (their labels and the start of their text)."""
        labels = dict(request.passages)
        shown = [pid for pid in dict.fromkeys([c.get("source") for c in reply.changes] + list(reply.cites))
                 if isinstance(pid, str) and pid in folder_ids]
        passages = tuple({"id": pid, "label": labels[pid], "text": texts.get(pid, "")[:PASSAGE_SHOWN]} for pid in shown)
        entry = Held(code, tuple(dict(c) for c in reply.changes), bool(folder_ids) or bool(from_connector), passages, self.clock())
        with self.replies_lock:
            now = self.clock()
            for k in [k for k, h in self.replies.items() if now - h.at > REPLY_MINUTES * 60]:
                del self.replies[k]
            while len(self.replies) >= MAX_REPLIES:
                del self.replies[next(iter(self.replies))]
            key = secrets.token_urlsafe(16)
            self.replies[key] = entry
            return key

    # ----- POST /api/ask/change/dry -----
    def change_dry(self, body):
        """{project, reply} -> the dry run of each change that answer suggested: {ok, plans: [...], from_source, passages}. Each
        plan is an offer (before and after from the data) or a plain refusal. Made once per reply; the provider is never asked."""
        if not isinstance(body, dict) or set(body) != DRY_FIELDS or not all(isinstance(body[k], str) for k in DRY_FIELDS):
            return 400, self.fail("change_bad_request")
        code = body["project"]
        if not PROJECT_CODE.fullmatch(code):
            return 400, self.fail("bad_project_code", ask_apply.NO_PROJECT)
        if not self.enabled() or self.project_off(code):                       # fails closed: nothing is read for a change while asking is off
            return 409, self.fail("asking_off", ask_apply.ASKING_OFF)
        with self.replies_lock:
            held = self.replies.get(body["reply"])
            if held is None or held.project != code or self.clock() - held.at > REPLY_MINUTES * 60:
                return 409, self.fail("no_reply")
            if held.shown:
                return 409, self.fail("shown_already")
            held.shown = True
        status, out = self.applier.plan_all(code, list(held.changes), held.from_source)
        if status != 200 or any(p.get("code") in UNREADY for p in out["plans"]):
            held.shown = False                       # row 1293 line 10: a dry run that could not be made does not use the reply up
        if status != 200:
            return status, out
        return 200, {"ok": True, "plans": out["plans"], "from_source": held.from_source, "passages": list(held.passages)}

    # ----- POST /api/ask/change/apply -----
    def change_apply(self, body):
        """{project, offer, confirm?} -> the change saved as one undoable step: {ok, kind, ref, apply_id, undoable, before, after}.
        `confirm` must be exactly true for a change the server marked from_source; the provider is never asked."""
        if not isinstance(body, dict) or not {"project", "offer"} <= set(body) or not set(body) <= APPLY_FIELDS:
            return 400, self.fail("change_bad_request")
        code, offer, confirm = body["project"], body["offer"], body.get("confirm", False)
        if not isinstance(code, str) or not isinstance(offer, str) or not isinstance(confirm, bool):
            return 400, self.fail("change_bad_request")
        if not PROJECT_CODE.fullmatch(code):
            return 400, self.fail("bad_project_code", ask_apply.NO_PROJECT)
        if not self.enabled() or self.project_off(code):                       # and the save path reads the switch again inside its step
            return 409, self.fail("asking_off", ask_apply.ASKING_OFF)
        return self.applier.apply(offer, code, confirm=confirm)


@dataclass
class Held:
    """One answer's suggested changes, on the server: the project, the changes as the model wrote them, whether the answer was
    given passages from the person's files (the page can't clear this), those passages to show, when, and whether shown."""
    project: str
    changes: tuple
    from_source: bool
    passages: tuple
    at: float
    shown: bool = field(default=False)


def page_of(passage):
    """#943: the page a passage starts on, as a whole number, or None (page numbers come with #891)."""
    page = getattr(passage, "page", None)
    return page if isinstance(page, int) and not isinstance(page, bool) else None


def file_of(passage):
    """#943: the name inside its saved folder of the file a passage came from, or None (project data has no file)."""
    file = getattr(passage, "file", None)
    return file if isinstance(file, str) else None


def left_out_note(count):
    """The plain line for passages of the project's data that did not fit what can be sent."""
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        return ""
    return ("Some of the report was too long to send in full, so only the parts closest to your question were used.")


def draft_via(draft, conn):
    """Row 1306 F6: a draft written in a run that read a connector carries the names of the parts read (`via`), so the page can say so above it.
    Nothing the connector returned is kept. The draft is otherwise unchanged and is still only a card the person adds."""
    if not isinstance(draft, dict) or not conn or not conn.get("used"):
        return draft
    return {**draft, "via": [str(p) for p in conn["used"]]}


def hidden_notes(hidden, passages):
    """Row 1293: one plain line for each passage sent that holds hidden characters (the counts of Request.hidden, which the passage
    keeps: it is sent unchanged). The question's own count is not a passage and gets none."""
    out = []
    for pid, label in passages:
        n = hidden.get(pid) if isinstance(hidden, dict) else None
        if isinstance(n, int) and not isinstance(n, bool) and n >= 1:
            out.append(f"{label}: this passage has {n} hidden {'character' if n == 1 else 'characters'}.")
    return out


def connector_used(line):
    """Row 1306: the answer's `used` data from the UsedLine of a run that had a connector in it: the line, what was used and not used,
    and the parts read with the provenance flag. No connector content. None when no connector was in the run."""
    if line is None:
        return None
    return {"line": line.text, "used": list(line.used), "not_used": list(line.not_used),
            "sources": [{"part": part, "from_connector": True} for part in line.used]}


def folder_notes(found):
    """Plain lines about the saved folders: what was left out for safety, and the types not read."""
    out = []
    if found.safety:
        out.append(f"{found.safety} {'file was' if found.safety == 1 else 'files were'} left out for safety.")
    for label in getattr(found, "secret_labels", ()):         # #215: the file's label only, never what matched
        out.append(f"{label} {secret_screen.REASON}, so it was left out and the answer may be missing something. {secret_screen.NEXT_STEP}")
    if found.pdf:
        reasons = {}
        for _label, code in found.pdf_reasons:                 # one line for each reason, in the order first met
            reasons.setdefault(pdf_reader.why(code), []).append(code)
        out += [pdf_reader.count_note(len(codes), codes[0]) for codes in reasons.values()]
        if found.pdf > len(found.pdf_reasons):                 # a count with no reason recorded: still said
            out.append(pdf_reader.count_note(found.pdf - len(found.pdf_reasons), "crash"))
    if found.other:
        out.append(f"{found.other} {'file was' if found.other == 1 else 'files were'} not read because of its type.")
    if getattr(found, "limit", 0):
        out.append(f"{found.limit} {'file was' if found.limit == 1 else 'files were'} not opened because the limit for one question was reached.")
    if found.stopped:
        out.append("Not every file in your folders was looked at.")
    return out
