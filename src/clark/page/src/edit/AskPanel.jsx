// The ask panel (#47a): a full-height panel on the right, over the open page. Edit pages only (a published file has none). The look
// is #102's light panel with a soft wash (#214), built from the page's own tokens (edit.css). The reply is drawn as text only: it is
// never read as markup (row 1217: a listed set of marks becomes elements clark makes itself, see askFormat.js). Nothing is sent while asking is off.
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { project, showSettings, token, view, rows, filterCtx, openPeek } from "../stores/report.js";
import { zoneFetch } from "../api.js";
import { words, askFilesRead } from "./publishApi.js";
import { stopRestore } from "../router.js";
import { askProvider } from "./askState.js";
import { draft, panelOpen, panelState, panelDocker, panelDisconnected, panelModel, panelStanding, panelWidth, panelFocus, turns, pending, chatEpoch, handed, answersReady, queue, queueHeld, queueDrop, QUEUE_MAX, subject, setQueue, closePanel, newChat, setWidth, resetWidth, clampWidth, widthRange, drawQuip, quipDelay } from "./askPanelState.js";
import * as W from "./askWords.js";
import { classicTheme } from "../components/Contents.jsx";
import { pills, asking } from "./askPills.js";
import { stateOf } from "./askPillState.js";
import { helpOpen } from "../help/helpStore.js";
import { slashMatches, stepSlash } from "./askSlash.js";
import { ownCommands, loadOwnCommands } from "./askOwn.js";
import { Icon } from "../components/Icon.jsx";
import { holdScroll } from "../core/holdScroll.js";
import { chatId, histOpen, histTick, chats, keepChat, deleteChat, when } from "./askHistory.js";
import { ChangeCards, fixedLine } from "./AskChange.jsx";
import { FormattedAnswer } from "./AskFormat.jsx";
import { sourcesOf, kindOf } from "./askCite.js";
import { AskDraft } from "./AskDraft.jsx";
import { readDraft } from "./askDraft.js";
import * as F from "./askFiles.js";
import { nowMs } from "../workItems.js";

// Row 890: the files an answer used, as the server sends them ({id, label}). A long file is cut into parts labelled "name (part N)":
// the suffix is dropped and each file is listed once, in the order first seen.
function sourceLabels(list) {
  if (!Array.isArray(list)) return [];
  const out = [];
  for (const s of list) {
    if (!s || typeof s.label !== "string" || !s.label) continue;
    const name = s.label.replace(/ \(part \d+\)$/, "");
    const file = typeof s.file === "string" && s.file ? s.file : "";
    const page = Number.isInteger(s.page) && s.page >= 1 ? s.page : null;
    const seen = out.find((o) => o.name === name);
    if (!seen) out.push({ name, file, page });
    else if (!seen.file && file) { seen.file = file; seen.page = page; }
  }
  return out;
}

// Row 1292: what an answer read, as the server says it (counts and a day): only whole counts and a text day are kept.
function readOf(r) {
  if (!r || typeof r !== "object") return null;
  const n = (v) => (Number.isInteger(v) && v >= 0 ? v : 0);
  return { work_items: n(r.work_items), milestones: n(r.milestones), use_cases: n(r.use_cases), as_at: typeof r.as_at === "string" ? r.as_at.slice(0, 10) : "", items: n(r.items), left_out: n(r.left_out) };      // row 1294: items read and items left out, for "N items read, M left out."
}

// Row 1292: a citation or a Used chip opens that item or milestone in its peek, which sits left of the panel (the panel stays open).
const cited = (t) => (classicTheme() ? sourcesOf(t.items) : []);       // row 1292: sources are Classic only; their CSS is the Classic theme's, so Cards draws none
const openCite = (id) => openPeek(id, kindOf(id) === "milestone" ? "milestone" : "item");

async function post(path, body) {
  try {
    const r = await zoneFetch(path, { method: "POST", headers: { "X-Clark-Token": token(), "Content-Type": "application/json" }, body: JSON.stringify(body), cache: "no-store" });
    return { status: r.status, body: await r.json().catch(() => null) };
  } catch (e) {
    return { status: 0, body: null };
  }
}

const stillMotion = () => document.documentElement.dataset.motion === "reduce" || (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

let nextId = 1;

/** Row 1218: the notes about what was left out (kind "note") follow the answer as one small block, not a paragraph each. */
function shownTurns(list) {
  const out = [];
  for (const t of list) {
    const last = out[out.length - 1];
    if (t.kind === "note" && typeof t.text === "string") {
      if (last && last.kind === "notes") last.lines.push(t.text); else out.push({ kind: "notes", role: "assistant", lines: [t.text] });
    } else out.push(t);
  }
  return out;
}

export function AskPanel() {
  const open = panelOpen.value, state = panelState.value, model = panelModel.value, width = panelWidth.value;
  const list = turns.value, busy = pending.value;
  const classic = classicTheme();
  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  const [pick, setPick] = useState(0), [shut, setShut] = useState(false);   // #1292 S10: the slash menu's chosen row, and whether Esc has closed it
  const hold = classicTheme() ? W.PLACEHOLDER_CLASSIC : W.PLACEHOLDER;          // row 1350: the new placeholder is Classic only
  const usable = state === "ready" || state === "checking";      // the box takes text only then: with asking off no slash command is offered or run
  const menu = shut || !usable ? null : slashMatches(text, classicTheme(), classicTheme() ? ownCommands.value : []);
  useEffect(() => { if (open && state === "ready" && classicTheme()) loadOwnCommands(project.value); }, [open, state, project.value]);      // row 1295: Classic only, and only while asking is on; the person's own commands join the / menu
  const [secs, setSecs] = useState(0);
  const [quip, setQuip] = useState("");
  const [said, setSaid] = useState("");            // row 1220: what a screen reader is told when a message is queued or removed
  const waiting = queue.value, held = queueHeld.value, dropping = queueDrop.value;
  const showHist = histOpen.value && !busy;
  const saved = showHist ? (histTick.value, chats()) : [];
  const [files, setFiles] = useState([]);       // #1292 S14: the files and pictures waiting for the next question (used for that question only)
  const [dropOver, setDropOver] = useState(false);
  const [filesOk, setFilesOk] = useState(true);     // row 1294: the Files switch (all projects) and this project's own turn-off, read each time the panel opens; until the server says "not allowed" the paperclip stays, as it does on main (the server checks again for every question)
  const box = useRef(null), log = useRef(null), stopped = useRef(false), picker = useRef(null);
  // Row 1215: the box is one line high when empty and grows with its text; the cap and the line height are in edit.css, past the cap it scrolls inside.
  useLayoutEffect(() => { const b = box.current; if (!b) return; b.style.height = "auto"; b.style.height = text ? b.scrollHeight + 2 + "px" : ""; });   // empty: the placeholder never makes it taller
  // Row 885: closing sinks the panel first, and it stays drawn until the animation ends (a 400 ms timer guards it, so no dead overlay is left).
  // Where motion is off it leaves at once, as before.
  const phase = useRef(open ? "open" : "closed"), [, redraw] = useState(0);
  if (open) phase.current = "open"; else if (phase.current === "open") phase.current = stillMotion() ? "closed" : "leaving";
  const leaving = phase.current === "leaving";
  const finish = () => { if (phase.current === "leaving") { phase.current = "closed"; redraw((n) => n + 1); } };
  useEffect(() => { if (!leaving) return undefined; const t = setTimeout(finish, 400); return () => clearTimeout(t); }, [leaving]);
  useEffect(() => {
    if (!open) return undefined;
    let live = true;
    askFilesRead(project.value).then((r) => {
      if (!live) return;
      const b = r.body, off = r.status === 200 && !!b && b.ok === true && b.allowed === false;
      setFilesOk(!off);
      if (off) setFiles([]);
    });
    return () => { live = false; };
  }, [open, project.value]);

  // Row 858: the box is usable while the check is out (what is typed stays, and so does focus); only Send waits for the answer.
  // The answer arriving (a state change alone) moves focus only while it is still in the panel or nowhere: a person who has moved on keeps their place.
  const seen = useRef({ open: false, bump: 0, busy: false, state });
  useEffect(() => {
    const was = seen.current;
    const fresh = was.open !== open || was.bump !== panelFocus.value;
    seen.current = { open, bump: panelFocus.value, busy, state };
    const at = document.activeElement, c = document.getElementById("ask-panel");
    // A change of busy alone (a send starting, an answer landing) moves focus only after Stop: the Stop icon leaves with the check, so focus is on the body.
    // A control the person tabbed to meanwhile (Copy, a source link) keeps it.
    if (!fresh && was.state === state && was.busy !== busy && !(was.busy && !busy && (!at || at === document.body))) return;
    if (!fresh && at && at !== document.body && !(c && c.contains(at))) return;
    if (open && (state === "ready" || state === "checking") && box.current) box.current.focus(); else if (open && c) c.focus();
  }, [open, state, panelFocus.value, busy]);
  // A reply taller than the log opens at its top (the reader starts at the first line); a short one, or the person's own question, sits at the end.
  useEffect(() => {
    const el = log.current;
    if (!el) return;
    const last = el.lastElementChild;
    if (last && last.getAttribute("data-role") === "assistant" && last.offsetHeight > el.clientHeight) el.scrollTop = last.offsetTop - el.offsetTop;
    else el.scrollTop = el.scrollHeight;
  }, [list.length, busy]);
  useEffect(() => {
    if (!busy) { setSecs(0); setQuip(""); return undefined; }
    if (classicTheme()) {      // row 1292, Classic only: the working line counts seconds from the send
      const from = nowMs();
      setSecs(0);
      const c = setInterval(() => setSecs((nowMs() - from) / 1000), 1000);
      return () => clearInterval(c);
    }
    let t = null;      // Cards keeps its quips, as before
    setQuip(drawQuip());
    const tick = () => { t = setTimeout(() => { setQuip(drawQuip()); tick(); }, quipDelay()); };
    tick();
    return () => clearTimeout(t);
  }, [busy]);

  if (!open && !leaving) return null;

  // #1292 S14: files come from the paperclip, a drop on the panel or a paste; what cannot be taken says why in plain words.
  function addFiles(list) {
    if (!list.length || state !== "ready" || !filesOk) return;
    const r = F.addFiles(files, list);
    setFiles(r.files); setNote(r.notes.join(" "));
    if (box.current) box.current.focus();
  }
  function removeFile(f) {
    setFiles(F.removeFile(files, f.id)); setNote("");
    setTimeout(() => { const left = document.querySelectorAll("#ask-files .ask-file-del"); const to = left[Math.min(files.findIndex((x) => x.id === f.id), left.length - 1)] || box.current; if (to) to.focus(); }, 0);
  }
  const dragHasFiles = (e) => !!e.dataTransfer && Array.from(e.dataTransfer.types || []).includes("Files");
  const hasFiles = (e) => filesOk && dragHasFiles(e);

  // Item 943: a source that is a saved PDF opens in the system's viewer at its page; the server judges the file again.
  async function openSource(n) {
    const r = await post("/api/ask/open-source", { project: project.value, file: n.file, page: n.page });
    if (r.status === 200) return;
    const m = r.status === 0 ? W.NOT_REACHED_LINE : words(r, "answer");
    turns.value = [...turns.value, { role: "assistant", text: m, kind: "problem" }];
  }

  // `preset` is a suggestion's words: it is asked as it stands and leaves what is typed in the box alone. While an answer is made, what is
  // typed is queued instead (row 1220); a suggestion is not (they are not drawn then).
  function send(e, preset) {
    if (e) e.preventDefault();
    if (state !== "ready") return;
    const q = (preset || text).trim();
    if (busy) {
      if (preset || !q) return;
      if (queue.value.length >= QUEUE_MAX) { setNote(W.QUEUE_FULL); return; }
      setQueue([...queue.value, { id: nextId++, text: q }]);
      setText(""); setNote((n) => (n === W.QUEUE_FULL ? "" : n)); setSaid(W.QUEUE_SAY_ADDED(queue.value.length));
      return;
    }
    if (!q) { setNote(W.EMPTY_LINE); return; }
    run(q, preset, null, files);
  }

  // #1292 S10: a chosen slash command. A question command sends its question as a suggestion does; /new and /history send nothing.
  function runSlash(c) {
    if (!c || !usable) return;
    setText(""); setPick(0); setShut(false);
    if (c.act === "new") { newChat(); setNote(""); return; }
    if (c.act === "history") { if (!busy) histOpen.value = true; return; }
    send(null, c.ask);
  }

  // Asks one question and, when it is answered, sends the next queued one. `from` is the queued message this question came from. It reads the
  // signals, never this render's values, because a queued question is sent from the end of the one before.
  async function run(q, preset, from, att) {
    setNote(""); stopped.current = false;
    if (att && att.length) setFiles([]);          // the chips go with the send; they come back if nothing was answered
    histOpen.value = false;                       // a question asked over Earlier chats: the answer must come back to the chat, not under the list
    const earlier = turns.value.filter((t) => !t.kind).map((t) => ({ role: t.role, text: t.text }));
    const mine = { role: "user", text: q, ...(subject.value ? { about: subject.value.name } : {}) };
    turns.value = [...turns.value, mine];
    if (!preset && !from) setText("");
    if (box.current) box.current.focus();         // the suggestion that was pressed is about to be replaced: keep the keyboard's place
    pending.value = true;
    const epoch = chatEpoch.value;
    const about = subject.value;                     // row 1292: the chip's subject goes ahead of the question; the chat shows only the person's words
    const body = { project: project.value, question: about ? W.ABOUT_LEAD(about.kind, about.id, about.name) + q : q, earlier };
    if (att && att.length) body.files = await F.encodeFiles(att);
    const r = await post("/api/ask", body);
    pending.value = false;
    setNote("");                                     // the Stopping line is over once the turn (answer or stopped line) is here
    if (epoch !== chatEpoch.value) return;           // row 1119: the page was left meanwhile; the answer belongs to a chat that is gone
    const b = r.body;
    const came = r.status === 200 && b && b.ok === true && typeof b.answer === "string";
    const late = came && stopped.current;      // row 1293 line 7: Stop was pressed and an answer still came back: it is not shown, the stopped line is
    const answered = came && !late;
    if (!answered && !preset && !from) {      // nothing was answered: the question goes back in the box unless something new was typed meanwhile, and its turn leaves the transcript so it is not shown twice
      setText((t) => t || q);
      if (att && att.length) setFiles((now) => (now.length ? now : att));
      if (!stopped.current) turns.value = turns.value.filter((t) => t !== mine);      // a Stop keeps the question: the stopped line follows it
    }
    if (!answered && from && !stopped.current) {     // a queued question that was not answered goes back to the front of the queue, so nothing typed is lost
      turns.value = turns.value.filter((t) => t !== mine);
      setQueue([from, ...queue.value]);
    }
    if (answered) {
      // #1293 A: what the claims check found follows the answer in the same small block, in the server's own words ([D] a quiet line, not a badge per source).
      // An answer that did not follow the form is shown whole, and its flag (unreadable or disguised) says so: that line is the banner.
      const found = Array.isArray(b.flags) ? b.flags.filter((f) => f && typeof f.message === "string" && f.message).map((f) => f.message) : [];
      const shared = Array.isArray(b.notes) ? b.notes.filter((n) => typeof n === "string") : [];
      if (classicTheme() && typeof b.index_note === "string" && b.index_note) shared.splice(Math.min(Number.isInteger(b.index_note_at) ? b.index_note_at : shared.length, shared.length), 0, b.index_note);      // row 7 of 1366: the "still reading" note is the Classic theme's, in the place the server gave it
      const extra = [...shared, ...found];
      const made = readDraft(b.draft);      // row 1292: a draft the answer carries opens beside the panel; nothing is in the report until it is added
      turns.value = [...turns.value, { role: "assistant", text: b.answer, sources: sourceLabels(b.sources), items: Array.isArray(b.items) ? b.items : [], ...(readOf(b.read) ? { read: readOf(b.read) } : {}), ...(made ? { draft: made } : {}) }, ...extra.map((n) => ({ role: "assistant", text: n, kind: "note" }))];
      keepChat(turns.value);
      if (made) draft.value = made;
      if (!panelOpen.value) answersReady.value++;       // row 1292: the button says an answer is waiting
      if (typeof b.reply === "string" && b.reply && Array.isArray(b.changes) && b.changes.length) await showChanges(b.reply);
    } else if (r.status === 409 && b && b.code === "asking_off") {
      panelState.value = "off";
    } else if (r.status === 0) {
      turns.value = [...turns.value, { role: "assistant", text: W.NOT_REACHED_LINE, kind: "problem" }];
    } else {
      const m = late ? W.STOPPED_LINE : r.status === 200 && !(b && typeof b.message === "string" && b.message) ? W.NO_ANSWER_LINE : words(r, "answer");
      turns.value = [...turns.value, { role: "assistant", text: m, kind: "problem" }];
    }
    if (epoch !== chatEpoch.value || !queue.value.length) return;
    // Row 1220: an answered question sends the next queued one; a stopped or failed one leaves the queue waiting, so a stop never spends another run.
    if (!answered || stopped.current) { queueHeld.value = stopped.current ? "stopped" : "failed"; return; }
    if (queueHeld.value || !panelOpen.value || panelState.value !== "ready" || pending.value) return;
    const [next, ...rest] = queue.value;
    setQueue(rest);
    run(next.text, undefined, next);
  }

  // S11: a question the quick bar handed over is taken once the check has answered. Sent at once when it was handed over with Ctrl or Cmd + Enter and
  // the panel is ready (queued while an answer is made); otherwise, or when asking cannot answer now, its words go in the box so they are not lost.
  useEffect(() => {
    const h = handed.value;
    if (!h || !open || state === "checking") return;
    handed.value = null;
    if (h.send && state === "ready") { if (!busy) run(h.text, h.text, null); else if (queue.value.length < QUEUE_MAX) setQueue([...queue.value, { id: nextId++, text: h.text }]); else setText(h.text); }
    else setText(h.text);
  }, [handed.value, open, state]);

  // Send them: the first waiting message is sent, and the rest follow as each is answered.
  function sendWaiting() {
    if (state !== "ready" || busy || !queue.value.length) return;
    const [next, ...rest] = queue.value;
    queueHeld.value = ""; setQueue(rest);
    run(next.text, undefined, next);
  }

  // The bin that was pressed leaves with its line: focus goes to the next line's bin, else the one before, else the question box.
  function removeQueued(m, e) {
    const rows = Array.from(e.currentTarget.closest("ul").querySelectorAll("li[data-queued]")), at = rows.indexOf(e.currentTarget.closest("li"));
    setQueue(queue.value.filter((x) => x.id !== m.id));
    setSaid(W.QUEUE_SAY_REMOVED(queue.value.length));
    setTimeout(() => {
      const left = Array.from(document.querySelectorAll("#ask-queue .ask-queue-del"));
      const to = left[Math.min(at, left.length - 1)] || document.getElementById("ask-queue-send") || box.current;
      if (to) to.focus();
    }, 0);
  }

  // #47e: the dry run of the changes the answer suggested; the server holds them, so only the reply's ID is sent.
  async function showChanges(reply) {
    pending.value = true;
    const epoch = chatEpoch.value;
    const r = await post("/api/ask/change/dry", { project: project.value, reply });
    pending.value = false;
    if (epoch !== chatEpoch.value) return;
    const b = r.body;
    if (r.status === 200 && b && b.ok === true && Array.isArray(b.plans)) {
      turns.value = [...turns.value, { role: "assistant", kind: "changes", text: "", plans: b.plans, fromSource: b.from_source === true, passages: b.passages }];
    } else if (r.status === 409 && b && b.code === "asking_off") {
      panelState.value = "off";
    } else {
      const m = r.status === 400 || r.status === 409 ? fixedLine(b && b.message, W.CHANGES_GONE_LINE) : W.CHANGES_GONE_LINE;
      turns.value = [...turns.value, { role: "assistant", text: m, kind: "problem" }];
    }
  }

  function openChat(c) {
    if (busy) return;
    turns.value = c.turns.map((t) => ({ ...t }));
    chatId.value = c.id; histOpen.value = false; setNote("");
    setTimeout(() => { if (box.current) box.current.focus(); }, 0);   // the button that was pressed is gone: the focus goes to the question box
  }

  // The delete button that was pressed is removed with its row: the focus goes to the same place in the list (the next row's delete
  // button, else the one before), and to the list's heading when no chat is left, never to the page body.
  function removeChat(c, e) {
    const rows = Array.from(e.currentTarget.closest("ul").querySelectorAll("li")), at = rows.indexOf(e.currentTarget.closest("li"));
    deleteChat(c.id);
    setTimeout(() => {
      const left = Array.from(document.querySelectorAll("#ask-hist .ask-hist-del"));
      const to = left[Math.min(at, left.length - 1)] || document.querySelector("#ask-hist h3");
      if (to) to.focus();
    }, 0);
  }

  async function stop() {
    stopped.current = true;
    setNote(W.STOPPING_LINE);
    await post("/api/ask/stop", {});
  }

  function grip(e) {
    e.preventDefault();
    const el = e.currentTarget;
    el.setPointerCapture(e.pointerId);
    const move = (ev) => setWidth(document.documentElement.clientWidth - ev.clientX, false);
    const up = () => { el.removeEventListener("pointermove", move); el.removeEventListener("pointerup", up); el.removeEventListener("pointercancel", up); setWidth(panelWidth.value, true); };
    el.addEventListener("pointermove", move); el.addEventListener("pointerup", up); el.addEventListener("pointercancel", up);
  }
  function gripKey(e) {
    const d = e.key === "ArrowLeft" ? 24 : e.key === "ArrowRight" ? -24 : 0;
    if (d) { e.preventDefault(); setWidth(panelWidth.value + d, true); }
  }
  // To Settings and the Asking card there: scrolled into view and focused, so the link lands on the switch, not at the top.
  function toSettings(e) {
    e.preventDefault(); closePanel(true); showSettings("claude");
    const focusCard = (tries) => {                       // wait for the Settings card to be drawn, then scroll to it and focus its heading
      const c = document.getElementById("ask-settings");
      if (c) {                                           // the page's own place-restore would set the scroll back to the top: stop it, then scroll while the cards above settle
        stopRestore();
        for (let i = 0; i < 12; i++) setTimeout(() => c.scrollIntoView({ block: "start" }), i * 50);
        const h = c.querySelector("h2"); if (h) { h.setAttribute("tabindex", "-1"); h.focus({ preventScroll: true }); }
      }
      else if (tries < 40) setTimeout(() => focusCard(tries + 1), 50);
    };
    focusCard(0);
  }

  return (
    <>
    <aside id="ask-panel" ref={(n) => { if (n) holdScroll(n); }} class={leaving ? "ask-panel leaving" : "ask-panel"} onAnimationEnd={(e) => { if (e.target === e.currentTarget && e.animationName === "ask-down") finish(); }} role="complementary" aria-label={W.PANEL_TITLE} tabindex="-1" style={{ width: clampWidth(width) + "px" }}
      data-drop={dropOver ? "true" : undefined}
      onDragOver={(e) => { if (dragHasFiles(e)) { e.preventDefault(); if (hasFiles(e)) setDropOver(true); } }}      /* item 1506: with Files off the drag is still taken (so the browser does not open the file) but nothing lights up */
      onDragLeave={(e) => { if (e.target === e.currentTarget || !e.currentTarget.contains(e.relatedTarget)) setDropOver(false); }}
      onDrop={(e) => { if (!e.dataTransfer || !e.dataTransfer.files.length) return; e.preventDefault(); setDropOver(false); addFiles(Array.from(e.dataTransfer.files)); }}>
      <div class="ask-grip" id="ask-grip" role="separator" aria-orientation="vertical" aria-label={W.GRIP} aria-valuenow={clampWidth(width)} aria-valuemin={widthRange().min} aria-valuemax={widthRange().max} tabindex="0" onPointerDown={grip} onKeyDown={gripKey} onDblClick={classicTheme() ? resetWidth : undefined} />
      <header class="ask-head">
        <h2>{W.PANEL_TITLE}</h2>
        <div class="ask-head-btns">
          <button type="button" class="pkp-btn" id="ask-new" disabled={busy} title={W.NEW_CHAT} aria-label={W.NEW_CHAT} onClick={() => { setNote(""); newChat(); }}><Icon name="plus" /></button>
          <button type="button" class="pkp-btn" id="ask-history" disabled={busy} title={W.HISTORY} aria-label={W.HISTORY} aria-pressed={showHist ? "true" : "false"} onClick={() => { histOpen.value = !histOpen.value; }}><Icon name="clock" /></button>
          <button type="button" class="pkp-btn" id="ask-close" title={W.CLOSE} aria-label={W.CLOSE} onClick={closePanel}><Icon name="x" /></button>
        </div>
      </header>
      <p class="ask-status" id="ask-status" role="status" aria-live="polite">
        {busy ? W.WORKING : state === "checking" ? W.CHECKING_LINE : state === "unknown" ? null : state === "off" ? (classic ? W.CLASSIC_STATUS_READY : W.READY_LINE) : state === "signed-out" ? null : classic ? W.CLASSIC_STATUS_READY : model ? W.MODEL_LINE(model) : W.READY_LINE}
        {panelStanding.value && !busy && (state === "ready" || state === "signed-out") ? <> <a href="#settings&s=claude" id="ask-instr" data-ask-settings onClick={toSettings}>{classic ? W.CLASSIC_STANDING : W.STANDING_LINE}</a></> : null}
      </p>
      {state === "off" ? (
        <p class="ask-off" id="ask-off">{W.OFF_LINE} <a href="#settings&s=claude" data-ask-settings onClick={toSettings}>{W.OFF_LINK}</a></p>
      ) : null}
      {classic && panelDocker.value && state !== "off" ? (
        <p class="ask-off" id="ask-docker" data-ask-docker>{panelDocker.value}</p>
      ) : state === "signed-out" ? (
        <p class="ask-off" id="ask-signed-out">{panelDisconnected.value ? W.DISCONNECTED_LINE : W.named(W.SIGNED_OUT_LINE, askProvider.value)} <a href="#settings&s=claude" data-ask-settings onClick={toSettings}>{W.SETTINGS_LINK}</a></p>
      ) : null}
      {showHist ? (
        <div class="ask-hist" id="ask-hist" role="region" aria-label={W.HISTORY_TITLE}>
          <h3 tabindex="-1">{W.HISTORY_TITLE}</h3>
          <p class="ask-hist-note">{W.HISTORY_NOTE}</p>
          {saved.length ? (
            <ul>{saved.map((c) => (
              <li key={c.id} data-chat={c.id}>
                <button type="button" class="ask-hist-open" title={W.HISTORY_OPEN(c.title)} aria-label={W.HISTORY_OPEN(c.title)} onClick={() => openChat(c)}><span class="ask-hist-title">{c.title}</span><span class="ask-hist-when">{when(c.at)}</span></button>
                <button type="button" class="pkp-btn ask-hist-del" title={W.DELETE} aria-label={W.HISTORY_DELETE(c.title)} onClick={(e) => removeChat(c, e)}><Icon name="trash" /></button>
              </li>
            ))}</ul>
          ) : <p class="ask-hist-empty" id="ask-hist-empty">{W.HISTORY_EMPTY}</p>}
        </div>
      ) : null}
      {!showHist && !list.length && (state === "ready" || state === "off") ? (
        <section class="ask-first-run" id="ask-first-run" aria-label={W.FIRST_RUN_LABEL}>
          {classic ? (<>
            <h3>{W.CARD_HEAD}</h3>
            <ul>
              <li>{W.CARD_READS}</li>
              <li>{W.CARD_CHANGES.split(W.CARD_CHANGES_BOLD)[0]}<b>{W.CARD_CHANGES_BOLD}</b>{W.CARD_CHANGES.split(W.CARD_CHANGES_BOLD)[1]}</li>
              <li>{W.named(W.CARD_SENT, askProvider.value)} <a href="#settings&s=claude" data-ask-first-settings onClick={toSettings}>{W.CARD_LINK}</a></li>
            </ul>
            <p class="ask-first-tip">{W.CARD_TIP_BEFORE}<kbd>{W.CARD_TIP_KEY}</kbd>{W.CARD_TIP_AFTER}</p>
          </>) : (<>
            <p>{W.FIRST_RUN_READS}</p>
            <p>{W.FIRST_RUN_CHANGES}</p>
            <p>{W.named(W.FIRST_RUN_SENT, askProvider.value)}</p>
            <div class="ask-first-link"><a href="#settings&s=claude" data-ask-first-settings onClick={toSettings}>{W.FIRST_RUN_LINK}</a></div>
          </>)}
        </section>
      ) : null}
      <div class="ask-log" id="ask-log" hidden={showHist} role="log" aria-live="polite" aria-label={W.LOG_LABEL} ref={log}>
        {shownTurns(list).map((t, i) => t.kind === "notes" ? (
          <ul key={i} class="ask-turn assistant ask-notes" data-role="assistant" data-ask-notes>{t.lines.map((n, k) => <li key={k}>{n}</li>)}</ul>
        ) : (
          <div key={i} class={`ask-turn ${t.role}${t.kind ? " " + t.kind : ""}`} data-role={t.role}>
            <div class="ask-who">{t.role === "user" ? W.YOU : W.REPLY}</div>
            {t.kind === "changes" ? <ChangeCards turn={t} /> : t.role === "assistant" && !t.kind && typeof t.text === "string" ? <FormattedAnswer text={t.text} sources={cited(t)} open={openCite} /> : <div class="ask-text">{t.text}</div>}
            {t.role === "user" && t.about ? <div class="ask-about-line">{W.ABOUT_LINE(t.about)}</div> : null}
            {t.role === "assistant" && !t.kind && cited(t).length ? (
              <p class="ask-used" data-ask-used><span class="ask-used-h">{W.USED}</span> {cited(t).map((x) => <button type="button" key={x.id} class="ask-used-chip" data-cite={x.id} aria-label={W.CITE_LABEL(x.n, x.id)} title={W.CITE_TITLE(x.id)} onClick={() => openCite(x.id)}><b>{x.n}</b> {x.id}</button>)}</p>
            ) : null}
            {t.role === "assistant" && !t.kind && classicTheme() && W.READ_LINE(t.read) ? <p class="ask-read" data-ask-read>{W.READ_LINE(t.read)}</p> : null}
            {t.draft ? (
              <div class="ask-draftcard" data-ask-draftcard>
                <Icon name="doc" />
                <span><span class="ask-draftcard-title">{W.DRAFT_READY}</span><br /><span class="ask-draftcard-note">{t.draft.title ? t.draft.title + ". " : ""}{W.DRAFT_READY_LINE}{t.draft.via && t.draft.via.length ? <span data-ask-draft-via>{" " + W.DRAFT_VIA(t.draft.via.join(" and "))}</span> : null}</span></span>
                <button type="button" class={classicTheme() ? "btn sm pri ask-draftcard-open" : "btn primary"} onClick={() => { draft.value = t.draft; }}>{W.DRAFT_OPEN}</button>
              </div>
            ) : null}
            {t.sources && t.sources.length ? (
              <details class="ask-sources">
                <summary>{W.SOURCES}</summary>
                <ul>{t.sources.map((n, k) => <li key={k}>{n.file ? <button type="button" class="ask-source-open" data-file={n.file} onClick={() => openSource(n)}>{n.name}</button> : n.name}</li>)}</ul>
              </details>
            ) : null}
          </div>
        ))}
      </div>
      {busy ? (
        <p class="ask-work" id="ask-work">
          <span class="ask-dots" aria-hidden="true"><i /><i /><i /></span>
          {classic ? <span class="ask-quip ask-step" id="ask-step" aria-hidden="true">{W.workingLine(askProvider.value, secs)}</span> : <span class="ask-quip" id="ask-quip" aria-hidden="true">{quip}</span>}
        </p>
      ) : (state === "ready" || state === "off") && !text.trim() ? (
        <div class="ask-pills" id="ask-pills" role="group" aria-label={W.PILLS_LABEL}>
          {(subject.value && !helpOpen.value ? (W.PILLS_ABOUT[subject.value.kind] || []) : pills(view.value, list, helpOpen.value, stateOf(rows.value, filterCtx().today))).map((q) => <button type="button" key={q} disabled={state === "off"} aria-disabled={state === "off" ? "true" : undefined} onClick={() => send(null, asking(q, list))}>{q}</button>)}
        </div>
      ) : null}
      <p class="ask-note" id="ask-note" role="status" aria-live="polite">{note}</p>
      {waiting.length ? (
        <div class="ask-queue" id="ask-queue-box">
          <ul id="ask-queue" aria-label={W.QUEUE_LABEL}>
            {waiting.map((m) => (
              <li key={m.id} data-queued={m.id}>
                <span class="ask-queue-text" title={m.text}>{m.text}</span>
                <button type="button" class="pkp-btn ask-queue-del" title={W.QUEUE_REMOVE} aria-label={W.QUEUE_REMOVE} onClick={(e) => removeQueued(m, e)}><Icon name="trash" /></button>
              </li>
            ))}
            {waiting.length > 2 ? <li class="ask-queue-more" id="ask-queue-more">{W.QUEUE_MORE(waiting.length - 2)}</li> : null}
          </ul>
          {held && !busy ? (
            <p class="ask-queue-held" id="ask-queue-held">
              <span>{held === "stopped" ? W.QUEUE_STOPPED(waiting.length) : W.QUEUE_FAILED(waiting.length)}</span>
              <button type="button" class="ask-queue-act" id="ask-queue-send" disabled={state !== "ready"} onClick={sendWaiting}>{W.QUEUE_SEND}</button>
              <button type="button" class="ask-queue-act" id="ask-queue-clear" onClick={() => { setQueue([]); if (box.current) box.current.focus(); }}>{W.QUEUE_CLEAR}</button>
            </p>
          ) : null}
        </div>
      ) : null}
      {dropping ? <p class="ask-queue-drop" id="ask-queue-drop" role="status" aria-live="polite">{W.QUEUE_DROP(dropping)}</p> : null}
      <p class="sr-only" id="ask-queue-say" role="status" aria-live="polite">{said}</p>
      {dropOver ? <p class="ask-drop-line" id="ask-drop-line" aria-hidden="true">{F.DROP_LINE}</p> : null}
      {files.length ? (
        <div class="ask-files" id="ask-files">
          <ul aria-label={F.FILES_LABEL}>
            {files.map((f) => (
              <li key={f.id} data-file={f.id}>
                <span class="ask-file-name" title={f.name}>{f.name}</span><span class="ask-file-size">{F.sizeText(f.size)}</span>
                <button type="button" class="pkp-btn ask-file-del" title={W.DELETE} aria-label={F.REMOVE_FILE(f.name)} onClick={() => removeFile(f)}><Icon name="trash" /></button>
              </li>
            ))}
          </ul>
          <p class="ask-files-note">{F.SCREEN_LINE} {F.THIS_QUESTION_LINE}</p>
        </div>
      ) : null}
      {classic && panelDocker.value && state !== "off" ? null : <form class="ask-form" onSubmit={send}>
        {subject.value ? (
          <p class="ask-chip" id="ask-chip" data-ask-chip={subject.value.id}>
            <Icon name="sparkle" />
            <span class="ask-chip-t">{W.ABOUT_CHIP(subject.value.name)}</span>
            <button type="button" class="ask-chip-x" id="ask-chip-x" aria-label={W.ABOUT_REMOVE(subject.value.name)} title={W.ABOUT_REMOVE_TITLE} onClick={() => { subject.value = null; if (box.current) box.current.focus(); }}><Icon name="x" /></button>
          </p>
        ) : null}
        {menu ? (
          <ul class="ask-slash" id="ask-slash" role="listbox" aria-label={W.SLASH_LABEL}>
            {menu.length ? menu.map((c, i) => (
              <li key={c.name} role="option" id={"ask-slash-" + c.name} data-name={c.name} aria-selected={i === pick ? "true" : "false"} onMouseDown={(e) => { e.preventDefault(); runSlash(c); }}>
                <b>{"/" + c.name}</b> <span>{c.hint}</span>{c.own ? <em class="ask-slash-own">{W.SLASH_YOURS}</em> : null}
              </li>
            )) : <li class="ask-slash-none">{W.SLASH_NONE}</li>}
          </ul>
        ) : null}
        <textarea ref={box} id="ask-box" rows="1" value={text} placeholder={hold} aria-label={hold} disabled={state !== "ready" && state !== "checking"}
          role={menu ? "combobox" : undefined} aria-expanded={menu ? "true" : undefined} aria-controls={menu ? "ask-slash" : undefined} aria-autocomplete={menu ? "list" : undefined}
          aria-activedescendant={menu && menu.length ? "ask-slash-" + menu[pick].name : undefined}
          onInput={(e) => { setText(e.currentTarget.value); setPick(0); setShut(false); }}
          onPaste={(e) => { const got = Array.from((e.clipboardData && e.clipboardData.files) || []); if (got.length) { e.preventDefault(); addFiles(got); } }}
          onKeyDown={(e) => {
            if (menu && !e.isComposing) {
              if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); setShut(true); return; }       // the menu closes first; the panel stays
              if (["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key) && menu.length) { e.preventDefault(); setPick(stepSlash(pick, e.key, menu.length)); return; }
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (menu.length) runSlash(menu[pick]); return; }
            }
            if (e.key === "Enter" && !e.shiftKey && !e.isComposing) send(e);
          }} />
        <div class="ask-actions">
          {filesOk ? <input ref={picker} type="file" id="ask-file-input" multiple hidden accept=".txt,.md,.csv" tabindex="-1" onChange={(e) => { addFiles(Array.from(e.currentTarget.files)); e.currentTarget.value = ""; }} /> : null}
          {filesOk ?
          <button type="button" class="pkp-btn" id="ask-attach" title={F.ATTACH_LABEL} aria-label={F.ATTACH_LABEL} disabled={state !== "ready"} onClick={() => picker.current && picker.current.click()}><Icon name="paperclip" /></button> : null}
          {busy ? (
            <button type="button" key="stop" class="btn primary ask-stop-icon" id="ask-stop" title={W.STOP} aria-label={W.STOP} onClick={stop}>
              <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false"><rect x="3.5" y="3.5" width="9" height="9" rx="1.5" fill="currentColor" /></svg>
            </button>
          ) : (
            <button type="submit" key="send" class="btn primary" id="ask-send" title={W.SEND} aria-label={W.SEND} disabled={state !== "ready"} data-empty={text.trim() ? undefined : "true"} aria-disabled={text.trim() ? undefined : "true"}>
              <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false"><path d="M8 13V3M3.5 7.5 8 3l4.5 4.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" /></svg>
            </button>
          )}
        </div>
      </form>}
    </aside>
    <AskDraft />
    </>
  );
}
