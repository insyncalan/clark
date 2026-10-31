"""#136: hostile probes of GET /api/movement and the milestone change kinds (POST /api/change, /api/undo). PROPOSAL, plain unittest.

Uses the publish Rig (server + change + undo + publisher over the PUB plant) with the Movement read wired in. Every probe takes a
read-only snapshot of milestones, change_log, item_events, applies and decisions before and after: a refusal must change nothing.
Set HOSTILE_REPORT=1 to print one line per probe (class, status, body, rows changed)."""
import hashlib
import json
import os
import re
import socket
import sqlite3
import threading
import unittest

import _publish_fixture as fx
from clark import movement_read
from clark import server as sv
from clark import store as clark_store
from test_publish_route import DAY, USER, Rig

M, M2, DONE_M = "PUB-M-001", "PUB-M-002", "PUB-M-003"
TABLES = ("milestones", "change_log", "item_events", "applies", "decisions", "projects")
REPORT = bool(os.environ.get("HOSTILE_REPORT"))
INTERNAL = "ZQ-HOSTILE-INTERNAL-8841"
WHO, REASON, SOURCE = "ZQ-WHO-5512 Pat Placeholder", "ZQ-REASON-6623 build ran long", "ZQ-SRC-7734 steering minutes"
GOOD = {"agreed_with": WHO, "reason": REASON, "source": SOURCE}
HOLD_WORD = "ZQ-HOLDWORD-9945"


class Hostile(unittest.TestCase):
    def setUp(self):
        self.rig = Rig(self)
        store = self.rig.store
        read = movement_read.make_read(store.milestone_moves, store.data_for, today=lambda: DAY)
        self.rig.httpd.movement = read
        with store.step("dashboard", USER) as st:               # a second project with a milestone, for the foreign-id probes
            st.create("projects", {"code": "OTH", "name": "Other Programme", "health": "On track"})
            self.other = st.create("milestones", {"project": "OTH", "name": "Other milestone", "baseline_date": "2030-03-01", "source": "demo"})
            st.update("milestones", M, {"internal_note": INTERNAL})
        self.port = self.rig.httpd.server_port

    # ---- helpers
    def snap(self):
        con = sqlite3.connect("file:%s?mode=ro" % self.rig.db, uri=True)
        try:
            out = {}
            for t in TABLES:
                rows = con.execute("SELECT * FROM %s ORDER BY 1, 2" % t).fetchall()
                out[t] = (len(rows), hashlib.sha256(repr(rows).encode()).hexdigest())
            return out
        finally:
            con.close()

    def milestone(self, ref):
        con = sqlite3.connect("file:%s?mode=ro" % self.rig.db, uri=True)
        con.row_factory = sqlite3.Row
        try:
            return dict(con.execute("SELECT * FROM milestones WHERE id=?", (ref,)).fetchone())
        finally:
            con.close()

    def raw(self, data, timeout=10):
        s = socket.create_connection(("127.0.0.1", self.port), timeout=timeout)
        try:
            try:
                s.sendall(data)
            except OSError:                                  # the server refused before reading it all: read its answer
                pass
            buf = b""
            try:
                while True:
                    c = s.recv(65536)
                    if not c:
                        break
                    buf += c
                    if b"\r\n\r\n" in buf:
                        head, _, body = buf.partition(b"\r\n\r\n")
                        m = re.search(rb"(?i)content-length: *(\d+)", head)
                        if m and len(body) >= int(m.group(1)):
                            break
            except (socket.timeout, ConnectionResetError):
                pass
            status = int(buf.split(b" ", 2)[1]) if buf.startswith(b"HTTP/") else 0
            return status, buf
        finally:
            s.close()

    def req(self, method, path, body=None, headers=None, token=True):
        h = {"Host": "127.0.0.1:%d" % self.port}
        if token:
            h[sv.TOKEN_HEADER] = sv.TOKEN
        data = b""
        if body is not None:
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            h.update({"Content-Type": "application/json", "Content-Length": str(len(data))})
        h.update(headers or {})
        head = "%s %s HTTP/1.1\r\n" % (method, path) + "".join("%s: %s\r\n" % kv for kv in h.items()) + "\r\n"
        return self.raw(head.encode("utf-8", "surrogateescape") + data)

    def post(self, path, body, **kw):
        status, buf = self.req("POST", path, body, **kw)
        try:
            return status, json.loads(buf.partition(b"\r\n\r\n")[2] or b"null")
        except ValueError:
            return status, None

    def change(self, fields, ref=M, rebaseline=None, **more):
        req = {"project": "PUB", "kind": "milestones", "op": "update", "id": ref, "changes": fields, "place": "movement", **more}
        if rebaseline is not None:
            req["rebaseline"] = rebaseline
        return self.post("/api/change", req)

    def refused_and_unchanged(self, label, call, statuses=(400, 403, 404, 409, 411, 413, 415, 422)):
        before = self.snap()
        status, body = call()
        after = self.snap()
        if REPORT:
            print("PROBE|%s|%s|%s|%s" % (label, status, json.dumps(body, ensure_ascii=True)[:110], "NONE" if before == after else "CHANGED"))
        self.assertIn(status, statuses, label)
        self.assertEqual(before, after, label + ": a refusal wrote something")

    # ---- the read
    def test_read_door_checks(self):
        p = "/api/movement?project=PUB"
        for label, kw in (("no token", {"token": False}), ("wrong token", {"headers": {sv.TOKEN_HEADER: "nope"}}),
                          ("empty token", {"headers": {sv.TOKEN_HEADER: ""}}), ("foreign host", {"headers": {"Host": "evil.example"}}),
                          ("foreign origin", {"headers": {"Origin": "https://evil.example"}}),
                          ("null origin", {"headers": {"Origin": "null"}}),
                          ("cross-site fetch", {"headers": {"Sec-Fetch-Site": "cross-site", "Origin": "https://evil.example"}}),
                          ("rebinding host", {"headers": {"Host": "127.0.0.1.evil.example"}}),
                          ("dup Host", {"headers": {}})):
            status, buf = self.req("GET", p, **kw) if label != "dup Host" else self.raw(
                ("GET %s HTTP/1.1\r\nHost: 127.0.0.1:%d\r\nHost: evil.example\r\n%s: %s\r\n\r\n" % (p, self.port, sv.TOKEN_HEADER, sv.TOKEN)).encode())
            if REPORT:
                print("PROBE|read %s|%s|%s|NONE" % (label, status, buf.partition(b"\r\n\r\n")[2][:80]))
            self.assertEqual(status, 403 if label != "dup Host" else 400, label)
            self.assertNotIn(b"movement", buf.partition(b"\r\n\r\n")[2].lower().replace(b"movement_", b""), label)

    def test_read_methods_and_bodies(self):
        before = self.snap()
        for method in ("HEAD", "PUT", "DELETE", "OPTIONS", "PATCH", "TRACE"):
            status, buf = self.req(method, "/api/movement?project=PUB")
            if REPORT:
                print("PROBE|read method %s|%s|%s|NONE" % (method, status, buf.partition(b"\r\n\r\n")[2][:60]))
            self.assertIn(status, (400, 403, 404, 405, 501), method)
            if method == "HEAD":
                self.assertEqual(buf.partition(b"\r\n\r\n")[2], b"")
        for label, extra in (("body", b'{"project":"PUB"}'),):
            h = "GET /api/movement?project=PUB HTTP/1.1\r\nHost: 127.0.0.1:%d\r\n%s: %s\r\nContent-Length: %d\r\n\r\n" % (
                self.port, sv.TOKEN_HEADER, sv.TOKEN, len(extra))
            status, _ = self.raw(h.encode() + extra)
            self.assertEqual(status, 400, label)
        for label, cl in (("CL 00", "00"), ("CL +1", "+1"), ("CL -1", "-1"), ("CL huge", "99999999999999999999"), ("CL junk", "x")):
            h = "GET /api/movement?project=PUB HTTP/1.1\r\nHost: 127.0.0.1:%d\r\n%s: %s\r\nContent-Length: %s\r\n\r\n" % (
                self.port, sv.TOKEN_HEADER, sv.TOKEN, cl)
            status, buf = self.raw(h.encode())
            if REPORT:
                print("PROBE|read %s|%s|%s|NONE" % (label, status, buf.partition(b"\r\n\r\n")[2][:60]))
            self.assertIn(status, (200, 400, 411), label)       # "00" is a number; nothing may crash or hang
        h = "GET /api/movement?project=PUB HTTP/1.1\r\nHost: 127.0.0.1:%d\r\n%s: %s\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n" % (
            self.port, sv.TOKEN_HEADER, sv.TOKEN)
        self.assertEqual(self.raw(h.encode())[0], 400)
        self.assertEqual(before, self.snap())

    def test_read_project_codes(self):
        for label, q in (("lower", "pub"), ("space", "PUB%20"), ("lead space", "%20PUB"), ("NUL", "PUB%00"), ("newline", "PUB%0A"),
                         ("CRLF", "PUB%0D%0AX-A:1"), ("unicode", "P%C3%9CB"), ("fullwidth", "%EF%BC%B0%EF%BC%B5%EF%BC%A2"),
                         ("long", "A" * 5000), ("sql", "PUB%27%20OR%20%271%27%3D%271"), ("sql2", "PUB%3B%20DROP%20TABLE%20milestones"),
                         ("percent twice", "%2550UB"), ("plus", "PUB+"), ("empty", ""), ("dup", "PUB&project=OTH"), ("extra", "PUB&x=1"),
                         ("dup other order", "OTH&project=PUB"), ("semicolon", "PUB;project=OTH")):
            status, buf = self.req("GET", "/api/movement?project=" + q)
            body = buf.partition(b"\r\n\r\n")[2]
            if REPORT:
                print("PROBE|read code %s|%s|%s|NONE" % (label, status, body[:70]))
            self.assertIn(status, (400, 404, 414), label)
            self.assertNotIn(b"Traceback", body)
            self.assertNotIn(INTERNAL.encode(), body)
        self.assertEqual(self.req("GET", "/api/movement?project=PUB")[0], 200)

    def test_read_never_returns_internal_text_or_step_notes(self):
        self.assertEqual(self.change({"movement": "hold"})[0], 200)
        self.assertEqual(self.change({"baseline_date": "2035-01-31"}, rebaseline=GOOD)[0], 200)
        self.assertEqual(self.milestone(M)["internal_note"] is not None and INTERNAL in self.milestone(M)["internal_note"], True)
        status, buf = self.req("GET", "/api/movement?project=PUB")
        text = buf.partition(b"\r\n\r\n")[2].decode()
        self.assertEqual(status, 200)
        for marker in (INTERNAL, "internal_note"):
            self.assertNotIn(marker, text)

    # ---- hold: where its words go
    def test_a_hold_writes_only_its_dated_line_and_never_the_internal_note(self):
        before = self.milestone(M)
        status, got = self.change({"movement": "hold", "state_reason": "x"})
        self.assertEqual(status, 200, got)
        after = self.milestone(M)
        self.assertEqual(after["internal_note"], before["internal_note"], "a Hold must not touch internal_note")
        for field in ("owner", "name", "workstream", "archived", "client_visible"):
            self.assertEqual(after[field], before[field], field)
        con = sqlite3.connect("file:%s?mode=ro" % self.rig.db, uri=True)
        try:
            fields = {r[0] for r in con.execute("SELECT field FROM change_log WHERE apply_id=?", (got["apply_id"],))}
        finally:
            con.close()
        self.assertNotIn("internal_note", fields)

    # ---- the change door
    def test_change_door_checks(self):
        body = {"project": "PUB", "kind": "milestones", "op": "update", "id": M, "changes": {"movement": "hold"}, "place": "movement"}
        for label, kw in (("no token", {"token": False}), ("wrong token", {"headers": {sv.TOKEN_HEADER: "nope"}}),
                          ("foreign host", {"headers": {"Host": "evil.example"}}), ("foreign origin", {"headers": {"Origin": "https://evil.example"}}),
                          ("text/plain", {"headers": {"Content-Type": "text/plain"}})):
            self.refused_and_unchanged("change " + label, lambda kw=kw: self.post("/api/change", body, **kw))
        for method in ("PUT", "DELETE", "OPTIONS", "HEAD"):
            self.refused_and_unchanged("change method " + method, lambda m=method: (self.req(m, "/api/change", body)[0], None), (403, 404, 405, 501))
        self.refused_and_unchanged("change no length", lambda: (self.raw(("POST /api/change HTTP/1.1\r\nHost: 127.0.0.1:%d\r\n%s: %s\r\nContent-Type: application/json\r\n\r\n" % (
            self.port, sv.TOKEN_HEADER, sv.TOKEN)).encode())[0], None))
        for label, cl in (("CL -1", "-1"), ("CL huge", "99999999999")):
            self.refused_and_unchanged("change " + label, lambda cl=cl: (self.raw(("POST /api/change HTTP/1.1\r\nHost: 127.0.0.1:%d\r\n%s: %s\r\nContent-Type: application/json\r\nContent-Length: %s\r\n\r\n{}" % (
                self.port, sv.TOKEN_HEADER, sv.TOKEN, cl)).encode(), 3)[0], None))
        self.refused_and_unchanged("change 2MB body", lambda: self.post("/api/change", {**body, "pad": "x" * 2_000_000}))
        self.refused_and_unchanged("change not json", lambda: self.post("/api/change", b"{nope"))
        self.refused_and_unchanged("change json list", lambda: self.post("/api/change", b"[]"))
        self.refused_and_unchanged("change dup keys", lambda: self.post("/api/change", b'{"project":"OTH","project":"PUB","kind":"milestones","op":"update","id":"%s","changes":{"state":"Bogus"}}' % M.encode()))

    # ---- what may be written
    def test_fields_not_allowed(self):
        for f, v in (("internal_note", INTERNAL + "2"), ("owner", "Mallory"), ("archived", 1), ("status", "Cancelled"), ("name", "Hijack"),
                     ("workstream", "X"), ("client_visible", 0), ("percent_complete", 5), ("description", "x"), ("sort_order", 9),
                     ("source", "x"), ("project", "OTH"), ("id", "PUB-M-009"), ("updated_at", "2020-01-01 00:00:00"), ("status", "Planned "),
                     ("status", ["Done"]), ("status", None)):
            self.refused_and_unchanged("field %s=%r" % (f, v), lambda f=f, v=v: self.change({f: v}))

    def test_many_fields_one_invalid_writes_nothing(self):
        for bad in ({"state": "Bogus"}, {"status": "Cancelled"}, {"movement": "escalate"}, {"forecast_date": "2026-02-30"}, {"internal_note": "x"},
                    {"client_message": "a" * 501}, {"state_reason": "a\x00b"}):
            fields = {"forecast_date": "2031-01-01", "client_message": "ZQ-PARTIAL-1", "movement": "hold", **bad}
            self.refused_and_unchanged("mixed with %r" % list(bad), lambda fields=fields: self.change(fields))

    def test_movement_choice_and_status_and_state_words(self):
        for v in ("HOLD", "Hold", " hold", "hold\n", "recover", "escalate", "rebaseline ", "drop table", 1, True, [], {}, "⁠hold"):
            self.refused_and_unchanged("movement %r" % (v,), lambda v=v: self.change({"movement": v}))
        for v in ("Cancelled", "done", "Open", "", 1, "Planned​"):
            self.refused_and_unchanged("status %r" % (v,), lambda v=v: self.change({"status": v}))

    def test_date_forms(self):
        for v in ("2026-W44-3", "2026-02-30", "0000-01-01", "2026-10-30T10:00", "2026-10-30 10:00", "２０２６-１０-３０",
                  "30-10-2026x", "2026/10/30", "20261030", "2026-1-3", "-2026-10-3", "1e3", "2026-10-30\n", "٢٠٢٦-١٠-٣٠", "nan", 20261030, True, {}):
            self.refused_and_unchanged("forecast %r" % (v,), lambda v=v: self.change({"forecast_date": v}))
            self.refused_and_unchanged("actual %r" % (v,), lambda v=v: self.change({"actual_date": v}))
            if isinstance(v, str) and any(c.isdigit() and not c.isascii() for c in v):
                continue                                       # non-ASCII digits: see the next test
            self.refused_and_unchanged("agreed %r" % (v,), lambda v=v: self.change({"baseline_date": v}, rebaseline=GOOD))

    def test_fullwidth_digits_are_stored_as_plain_digits_or_refused(self):
        status, got = self.change({"baseline_date": "\uff12\uff10\uff13\uff15-\uff10\uff11-\uff13\uff11"}, rebaseline=GOOD)
        self.assertIn(status, (200, 400))
        if status == 200:
            self.assertEqual(self.milestone(M)["baseline_date"], "2035-01-31")

    def test_text_fields(self):
        for label, v in (("control", "a\x01b"), ("NUL", "a\x00b"), ("newline", "a\nb"), ("RTL", "a‮b"), ("zero width", "a​b"),
                         ("BOM", "﻿a"), ("lone surrogate", "a\ud800b"), ("100KB", "a" * 100_000), ("501", "a" * 501), ("tag chars", "a\U000e0041"),
                         ("number", 5), ("list", ["a"])):
            self.refused_and_unchanged("client_message " + label, lambda v=v: self.change({"client_message": v}))
            self.refused_and_unchanged("state_reason " + label, lambda v=v: self.change({"state_reason": v}))
            for k in ("agreed_with", "reason", "source"):
                self.refused_and_unchanged("rebaseline %s %s" % (k, label), lambda v=v, k=k: self.change({"baseline_date": "2035-01-31"}, rebaseline={**GOOD, k: v}))

    # ---- rebaseline rules
    def test_rebaseline_rules(self):
        cases = (("no rebaseline", {"baseline_date": "2035-01-31"}, None), ("empty rebaseline", {"baseline_date": "2035-01-31"}, {}),
                 ("no who", {"baseline_date": "2035-01-31"}, {"reason": "r", "source": "s"}),
                 ("no reason", {"baseline_date": "2035-01-31"}, {"agreed_with": "w", "source": "s"}),
                 ("no source", {"baseline_date": "2035-01-31"}, {"agreed_with": "w", "reason": "r"}),
                 ("blank strings", {"baseline_date": "2035-01-31"}, {"agreed_with": " ", "reason": " ", "source": " "}),
                 ("to the past", {"baseline_date": "2026-01-01"}, GOOD), ("earlier than agreed", {"baseline_date": "2026-10-14"}, GOOD),
                 ("same date", {"baseline_date": "2026-10-15"}, GOOD), ("cleared", {"baseline_date": None}, GOOD),
                 ("extra rebaseline key", {"baseline_date": "2035-01-31"}, {**GOOD, "x": "y"}),
                 ("rebaseline not a dict", {"baseline_date": "2035-01-31"}, "who"), ("rebaseline a list", {"baseline_date": "2035-01-31"}, [GOOD]),
                 ("rebaseline w/o date", {"movement": "hold"}, GOOD), ("bad decision date", {"baseline_date": "2035-01-31"}, {**GOOD, "date": "31-02-2026"}),
                 ("future decision date", {"baseline_date": "2035-01-31"}, {**GOOD, "date": "2099-01-01"}))
        for label, fields, rb in cases:
            self.refused_and_unchanged("rebaseline " + label, lambda f=fields, rb=rb: self.change(f, rebaseline=rb))

    def test_a_far_future_forecast_is_harmless_to_the_read_and_the_publish(self):
        self.assertEqual(self.change({"forecast_date": "9999-12-31"})[0], 200)
        status, buf = self.req("GET", "/api/movement?project=PUB")
        self.assertEqual(status, 200, buf[-200:])
        self.assertEqual(self.rig.publish(to_client=True)[0], 200)

    def test_undoing_a_rebaseline_puts_the_date_back_and_leaves_no_client_decision(self):
        moved = self.change({"baseline_date": "2035-01-31"}, rebaseline=GOOD)[1]
        status, got = self.post("/api/undo", {"project": "PUB", "apply_id": moved["apply_id"]})
        if REPORT:
            print("PROBE|undo of a rebaseline|%s|%s|n/a" % (status, json.dumps(got)[:200]))
        self.assertIn(status, (200, 409))
        self.assertEqual(self.milestone(M)["baseline_date"], "2026-10-15")
        con = sqlite3.connect("file:%s?mode=ro" % self.rig.db, uri=True)
        try:
            shown = con.execute("SELECT count(*) FROM decisions WHERE id=? AND client_visible=1", (moved["decision"],)).fetchone()[0]
        finally:
            con.close()
        self.assertEqual(shown, 0, "the decision that names who agreed the date must never be client-visible")

    def test_ids(self):
        for label, ref in (("other project", self.other), ("non-milestone action", "PUB-A-001"), ("decision", "PUB-D-001"), ("missing", "PUB-M-999"),
                           ("lower", "pub-m-001"), ("trailing space", M + " "), ("NUL", M + "\x00"), ("sql", M + "' OR '1'='1"), ("none", None), ("int", 1),
                           ("list", [M]), ("project code only", "PUB"), ("long", "PUB-M-" + "1" * 5000), ("glob", "PUB-M-00?"), ("like", "PUB-M-%")):
            self.refused_and_unchanged("id " + label, lambda ref=ref: self.change({"movement": "hold"}, ref=ref))
        self.refused_and_unchanged("project OTH, id PUB-M-001", lambda: self.post("/api/change", {
            "project": "OTH", "kind": "milestones", "op": "update", "id": M, "changes": {"movement": "hold"}, "place": "movement"}))
        for place in ("Movement", "movement ", "boards", "", 5):
            self.refused_and_unchanged("place %r" % (place,), lambda place=place: self.change({"movement": "hold"}, place=place))

    def test_archived_and_done(self):
        with self.rig.store.step("dashboard", USER) as st:
            st.archive("milestones", M2)
            st.update("milestones", DONE_M, {"status": "Done", "actual_date": "2026-10-01", "state": "Achieved", "state_set": 1})
        self.refused_and_unchanged("hold on archived", lambda: self.change({"movement": "hold"}, ref=M2))
        self.refused_and_unchanged("rebaseline archived", lambda: self.change({"baseline_date": "2035-01-31"}, ref=M2, rebaseline=GOOD))
        self.refused_and_unchanged("hold on Done", lambda: self.change({"movement": "hold"}, ref=DONE_M), (400, 409, 422))      # FINDING: today 200
        self.refused_and_unchanged("rebaseline Done", lambda: self.change({"baseline_date": "2035-01-31"}, ref=DONE_M, rebaseline=GOOD))
        reopened = self.change({"status": "Planned"}, ref=DONE_M)          # reopening is allowed (the store says so); it may not stay Achieved
        self.assertEqual(reopened[0], 200, reopened)
        self.assertEqual(self.milestone(DONE_M)["status"], "Planned")
        self.assertNotEqual(self.milestone(DONE_M)["state"], "Achieved")
        self.refused_and_unchanged("state Achieved on Planned", lambda: self.change({"state": "Achieved", "state_set": 1}, ref=M))
        self.refused_and_unchanged("state_set 2", lambda: self.change({"state_set": 2}))
        self.refused_and_unchanged("state_set string", lambda: self.change({"state_set": "1; DROP"}))

    # ---- order, replay, undo
    def test_replay_does_not_move_twice(self):
        first = self.change({"baseline_date": "2035-01-31"}, rebaseline=GOOD)
        self.assertEqual(first[0], 200, first)
        before = self.snap()
        again = self.change({"baseline_date": "2035-01-31"}, rebaseline=GOOD)
        if REPORT:
            print("PROBE|replay rebaseline|%s|%s|%s" % (again[0], json.dumps(again[1])[:100], "NONE" if before == self.snap() else "CHANGED"))
        self.assertIn(again[0], (400, 409, 422))
        self.assertEqual(before, self.snap())

    def test_undo_order_and_foreign_steps(self):
        a = self.change({"forecast_date": "2031-01-01"})[1]["apply_id"]
        b = self.change({"forecast_date": "2032-01-01"})[1]["apply_id"]
        status, got = self.post("/api/undo", {"project": "PUB", "apply_id": a})          # a later step overwrote it
        if REPORT:
            print("PROBE|undo of a step a later one overwrote|%s|%s|n/a" % (status, json.dumps(got)[:140]))
        self.assertEqual(status, 200)
        self.assertEqual(self.milestone(M)["forecast_date"], "2032-01-01", "the later step's value must not be clobbered")
        self.assertTrue(got["skipped"])
        status, got = self.post("/api/undo", {"project": "PUB", "apply_id": b})
        self.assertEqual(status, 200)
        undo_id = got["apply_id"]
        self.refused_and_unchanged("undo twice", lambda: self.post("/api/undo", {"project": "PUB", "apply_id": b}))
        self.refused_and_unchanged("undo of an undo", lambda: self.post("/api/undo", {"project": "PUB", "apply_id": undo_id}))
        self.refused_and_unchanged("undo with OTH", lambda: self.post("/api/undo", {"project": "OTH", "apply_id": a}))
        for v in (0, -1, 2 ** 63, 1.5, "1", True, None, [1]):
            self.refused_and_unchanged("undo id %r" % (v,), lambda v=v: self.post("/api/undo", {"project": "PUB", "apply_id": v}))

    def test_undo_of_steps_this_route_did_not_make(self):
        with self.rig.store.step("assistant", USER) as st:               # a step by ask clark: another route's
            st.update("milestones", M, {"forecast_date": "2040-01-01"})
        foreign = self.rig.store.con.execute("SELECT max(apply_id) FROM applies").fetchone()[0]
        with self.rig.store.step("dashboard", USER) as st:               # a raw step touching a milestone AND an action
            st.update("milestones", M, {"forecast_date": "2041-01-01"})
            st.update("actions", "PUB-A-001", {"priority": "High"}) if self.rig.store.read("actions", ref="PUB-A-001") else None
        mixed = self.rig.store.con.execute("SELECT max(apply_id) FROM applies").fetchone()[0]
        for label, step in (("assistant step", foreign), ("mixed raw step", mixed), ("project creation", 1)):
            self.refused_and_unchanged("undo " + label, lambda step=step: self.post("/api/undo", {"project": "PUB", "apply_id": step}))

    def test_two_threads_on_one_milestone(self):
        results, before = [], self.snap()

        def go(d):
            results.append(self.change({"forecast_date": d}))
        ts = [threading.Thread(target=go, args=("20%d-01-01" % (30 + i),)) for i in range(6)]
        [t.start() for t in ts]
        [t.join(30) for t in ts]
        if REPORT:
            print("PROBE|6 concurrent changes|%s|n/a|%s" % (sorted(r[0] for r in results), "applies +%d" % (self.snap()["applies"][0] - before["applies"][0])))
        self.assertTrue(all(r[0] in (200, 503) for r in results), results)
        ok = [r for r in results if r[0] == 200]
        self.assertEqual(self.snap()["applies"][0] - before["applies"][0], len(ok))
        self.assertIn(self.milestone(M)["forecast_date"], ["20%d-01-01" % (30 + i) for i in range(6)])

    # ---- leaks
    def test_nothing_planted_reaches_the_published_file_or_the_client_copy(self):
        self.change({"forecast_date": "2034-12-01"})
        self.change({"baseline_date": "2035-01-31"}, rebaseline={**GOOD, "date": DAY})
        self.change({"movement": "hold", "state_reason": "Waiting on the vendor"})
        self.change({"client_message": "Hello client"})
        status, got = self.rig.publish(to_client=True)
        self.assertEqual((status, got["ok"]), (200, True), got)
        files = [(self.rig.local / "chosen.html").read_bytes().decode("utf-8")] + [p.read_bytes().decode("utf-8", "replace") for p in self.rig.client.iterdir()]
        for marker in (INTERNAL, WHO, REASON, SOURCE, "Pat Placeholder"):
            for spelling in fx.spellings(marker):
                for text in files:
                    self.assertNotIn(spelling, text, spelling)
        for text in files:                                       # the decision the rebaseline made, and who made the change
            self.assertNotRegex(text, r"holding; agreed date unchanged")
            self.assertNotIn(USER, text)


if __name__ == "__main__":
    unittest.main()
