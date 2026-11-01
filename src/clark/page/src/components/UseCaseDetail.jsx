// One use case on its own page (#157, Edit only: a published file never has this component). The crumb leads back to the list, the
// title and status word come first, then two columns: where it stands, the linked work items and Archive on the left; the details,
// the linked milestones and the history on the right. In Edit the title, headline and standing text are changed in place, the status
// from a menu, the eye with a button; each is ONE change with one Undo (stores/changes.js, kind use_cases, op update), and Archive
// and Restore are the existing archive ops. In View, and for an archived use case, nothing here changes anything. The history is
// read from the use cases route (api.js); an archived use case is read with the archived rows (the page's usual read leaves them
// out). Work items open filtered to the use case: there is no peek on the page yet.
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { data, rows, mode, fromFile, project, openWork } from "../stores/report.js";
import { change, say } from "../stores/changes.js";
import { cameBackFrom } from "../stores/useCaseFocus.js";
import { readUseCaseHistory, readArchivedUseCase } from "../api.js";
import { Menu } from "./Menu.jsx";
import { Icon } from "./Icon.jsx";
import { RichField } from "../edit/RichField.jsx";
import { cleanHtml } from "../logic/cleanHtml.js";
import { isOpen, pillOf, dueCell, ownerOf, sortRows, showDate, todayIso, plural } from "../workItems.js";
import { initial, setFilter } from "../filters.js";
import { refOf } from "../logic/useCasesList.js";

const STATUSES = [["On track", "g"], ["Flag", "a"], ["High risk", "r"]];
const rag = (status) => (STATUSES.find((s) => s[0] === status) || [0, "n"])[1];
export const NAME_MAX = 120, HEAD_MAX = 300;
const SHOW = 8;
const EYE = { on: "On the dashboard", off: "Not on the dashboard" };

const refWords = (u) => refOf(u) || "Use case";
const safe = (html) => { try { return cleanHtml(html || ""); } catch (e) { return ""; } };

// The work items linked to a use case, as the list rows (rowsOf): every action, risk, issue and decision that names it.
function linkedTo(d, id, all) {
  const link = {};
  for (const r of [...(d.actions || []), ...(d.raid || []), ...(d.decisions || [])]) if (r.use_case) link[r.id] = r.use_case;
  return sortRows(all.filter((r) => link[r.id] === id), todayIso());
}

// The milestones its linked work items point at, in the order the project keeps them.
function milestonesOf(d, id) {
  const named = new Set([...(d.actions || []), ...(d.raid || [])].filter((r) => r.use_case === id && r.milestone).map((r) => r.milestone));
  return (d.milestones || []).filter((m) => named.has(m.id));
}

// A stored UTC time (YYYY-MM-DD HH:MM:SS.sss) as the person's own time: DD-MM-YYYY and HH:MM.
function when(stamp) {
  const m = /^(\d{4})-(\d\d)-(\d\d)[T ](\d\d):(\d\d)(?::(\d\d))?/.exec(String(stamp || ""));
  if (!m) return { day: "", time: "" };
  const t = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] || 0)));
  if (Number.isNaN(t.getTime())) return { day: "", time: "" };
  const two = (n) => String(n).padStart(2, "0");
  return { day: `${two(t.getDate())}-${two(t.getMonth() + 1)}-${t.getFullYear()}`, time: `${two(t.getHours())}:${two(t.getMinutes())}` };
}

const FIELD_WORDS = { title: "name", headline: "headline", status: "status", standing: "text of where it stands", client_visible: "dashboard choice", archived: "archive state" };
const HOW = { assistant: "with the assistant", excel: "from Excel", client: "from the client", team: "by the team", migrate: "when the data was moved" };
const said = (v) => (v === null || v === undefined || v === "" ? "nothing" : String(v).split("\n")[0]);

// What one history line says, in plain words (the doer is drawn in bold before it).
function whatWas(h) {
  const nm = FIELD_WORDS[h.field] || "use case";
  if (h.made) return "added the use case";
  if (h.undo) return `undid a change to the ${nm}`;
  if (h.field === "standing") return "edited where it stands";
  if (h.field === "client_visible") return h.after === "1" ? "put it on the dashboard" : "took it off the dashboard";
  if (h.field === "archived") return h.after === "1" ? "archived it" : "restored it";
  return `changed the ${nm} from ${said(h.before)} to ${said(h.after)}`;
}

// A one-line or short text field changed in place: a text box that looks like the text it holds. Enter saves it, so does leaving
// it; Esc puts the old text back. It grows with what is typed and never scrolls sideways. `ro` draws the text as text.
export function Line({ value, label, cls, field, max, empty, ro, onSave, problem }) {
  const el = useRef(null), cancelled = useRef(false), now = useRef(value);
  now.current = value;
  const fit = () => { const t = el.current; if (t) { t.style.height = "auto"; t.style.height = `${t.scrollHeight}px`; } };
  useLayoutEffect(() => {
    const t = el.current;
    if (t && t.value !== value && document.activeElement !== t) t.value = value;
    fit();
  }, [value, ro]);
  useEffect(() => { addEventListener("resize", fit); return () => removeEventListener("resize", fit); }, []);
  if (ro) return <span class={`${cls} ucd-ro`} data-ucd-field={field}>{value || <span class="muted">{empty}</span>}</span>;
  const commit = () => {
    const t = el.current;
    if (cancelled.current) { cancelled.current = false; return; }
    const text = t.value.replace(/\s+/g, " ").trim();
    if (text === now.current) { t.value = now.current; fit(); return; }
    const why = problem(text);
    if (why) { t.value = now.current; fit(); say("problem", why); return; }
    onSave(text).then((reply) => { if (!reply) { t.value = now.current; fit(); } });
  };
  const keys = (e) => {
    if (e.isComposing) return;
    if (e.key === "Enter") { e.preventDefault(); el.current.blur(); }
    else if (e.key === "Escape") { e.preventDefault(); cancelled.current = true; el.current.value = now.current; el.current.blur(); }
  };
  return <textarea ref={el} class={`${cls} ucd-in`} data-ucd-field={field} rows={1} defaultValue={value} placeholder={empty} aria-label={label} maxLength={max * 2} spellcheck onInput={fit} onBlur={commit} onKeyDown={keys}></textarea>;
}

const OWN = '[role=textbox],[role=combobox],[role=listbox],[role=menu],[role=dialog],[role=alertdialog],dialog';
const busy = (e) => !!e && e.nodeType === 1 && (e.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(e.tagName) || !!e.closest(OWN));

export function UseCaseDetail({ id }) {
  const d = data.value, code = project.value;
  const editing = mode.value === "edit" && !fromFile.value;
  const live = d && (d.use_cases || []).find((u) => u.id === id) || null;
  const [gone, setGone] = useState({ row: null, done: false });            // the archived row, once read
  const [hist, setHist] = useState({ state: "loading", lines: [] });
  const [all, setAll] = useState(false);
  const [mine, setMine] = useState(false);                                 // archived here, a moment ago: draw the row as it was while it is read again
  const snap = useRef(null), head = useRef(null), back = useRef(null);
  if (live) snap.current = live;

  // An archived use case is not in the page's data: read it (and read it again after Archive, Restore and their Undo).
  useEffect(() => {
    if (live) { setGone({ row: null, done: false }); setMine(false); return undefined; }
    let stale = false;
    readArchivedUseCase(code, id).then((r) => { if (!stale) setGone({ row: r.ok ? r.row : null, done: true }); });
    return () => { stale = true; };
  }, [id, code, !!live, d]);

  // The history is read again after every change and every Undo (each redraws the data).
  useEffect(() => {
    if (!live) return undefined;
    let stale = false;
    readUseCaseHistory(code, id).then((r) => { if (!stale) setHist(r.ok ? { state: "ready", lines: r.lines } : { state: "failed", lines: [] }); });
    return () => { stale = true; };
  }, [id, code, d]);

  // The heading takes the focus when a use case is drawn (and again when another is opened), so the page is announced and the
  // keys carry on from the top.
  const shown = !!(live || gone.row || (mine && snap.current));
  useEffect(() => { if (head.current) head.current.focus({ preventScroll: true }); }, [id, shown || gone.done]);

  // Esc leaves for the list, unless focus is in a field, the editor or a menu (they take Esc themselves).
  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== "Escape" || e.defaultPrevented || e.isComposing || e.metaKey || e.ctrlKey || e.altKey) return;
      if (busy(document.activeElement) || busy(e.target) || document.querySelector("dialog[open],[role=dialog],[role=alertdialog],[role=menu]")) return;
      if (back.current) back.current.click();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const u = live || gone.row || (mine ? snap.current : null);
  const listAt = `#usecases&p=${code}`;
  const crumb = (label) => (
    <nav class="ucd-crumb" aria-label="You are here">
      <a href={listAt} ref={back} data-uc-back onClick={() => { cameBackFrom.value = id; }}>Use cases</a><span aria-hidden="true"> › </span><span>{label}</span>
    </nav>
  );
  if (!d) return null;
  if (!u) {
    if (!live && !gone.done) return <div class="ucd" data-ucd>{crumb("Use case")}<p class="muted">Loading the use case.</p></div>;
    return <div class="ucd" data-ucd data-missing>{crumb("Use case")}<h1 ref={head} tabIndex={-1} class="ucd-h">That use case isn't in this project</h1><p>It may have been removed, or the address is for another project. <a href={listAt}>Go back to the use cases.</a></p></div>;
  }

  const archived = !live;
  const ro = !editing || archived;
  const work = linkedTo(d, u.id, rows.value), ms = milestonesOf(d, u.id), open = work.filter(isOpen);
  const label = u.ref ? `Use case ${u.ref}` : "";
  const on = !!u.client_visible;
  const send = (changes, done) => change({ kind: "use_cases", op: "update", id: u.id, changes, place: "cell" }, done);
  const archive = (op) => change({ kind: "use_cases", op, id: u.id, place: "cell" }, op === "archive" ? "Use case archived. It can be restored." : "Use case restored.")
    .then((reply) => { if (reply && op === "archive") setMine(true); return reply; });
  const lines = all ? hist.lines : hist.lines.slice(0, SHOW);
  const last = (hist.lines.length ? when(hist.lines[0].at).day : "") || when(u.updated_at).day;
  const sub = work.length ? `${open.length} of ${plural(work.length, "work item")} open` : "No work items";

  return (
    <div class="ucd" data-ucd data-uc-id={u.id} data-archived={archived ? "1" : undefined}>
      {crumb(refWords(u))}
      <div class="ucd-head">
        <div class="ucd-titles">
          <h1 class="ucd-h" ref={head} tabIndex={-1}>
            <span class="ucd-ref">{refWords(u)} ·</span>
            <Line value={u.title} label={`Name of ${refWords(u)}`} cls="ucd-name" field="title" max={NAME_MAX} empty="Name this use case" ro={ro}
              problem={(t) => (!t ? "A use case needs a name. The old name was kept." : Array.from(t).length > NAME_MAX ? `A name can be ${NAME_MAX} characters at most. The old name was kept.` : "")}
              onSave={(t) => send({ title: t }, "Name changed.")} />
          </h1>
          <p class="ucd-sub">
            {archived ? <span class="tag ucd-arch">Archived</span> : null}
            <span class={`ucd-word rag-${rag(u.status)}`} data-word><i class="ragdot" aria-hidden="true"></i>{u.status}</span>
            <span>{sub} · {plural(ms.length, "milestone")}</span>
          </p>
          <p class="ucd-line">
            <Line value={u.headline} label={`One line on where ${refWords(u)} stands`} cls="ucd-headline" field="headline" max={HEAD_MAX} empty="One line on where it stands" ro={ro}
              problem={(t) => (Array.from(t).length > HEAD_MAX ? `A headline can be ${HEAD_MAX} characters at most. The old headline was kept.` : "")}
              onSave={(t) => send({ headline: t }, "Headline changed.")} />
          </p>
        </div>
        {!ro ? (
          <div class="ucd-acts">
            <Menu label="Change status" ariaLabel="Change status" menuLabel="Status" id="ucd-status" btnCls="btn" left
              items={STATUSES.map(([name]) => ({ id: name, name, checked: u.status === name }))}
              onPick={(name) => { if (name !== u.status) send({ status: name }, `Status changed to ${name}.`); }} />
            <span class={`ucd-eye${on ? " on" : ""}`} data-eye><Icon name={on ? "eye" : "eyeoff"} /><span>{on ? EYE.on : EYE.off}</span></span>
            <button type="button" class="btn" data-eye-toggle onClick={() => send({ client_visible: on ? 0 : 1 }, on ? "Taken off the dashboard." : "Put on the dashboard.")}>{on ? "Take off the dashboard" : "Put on the dashboard"}</button>
          </div>
        ) : null}
      </div>
      {archived ? (
        <div class="ucd-note" data-archived-note>
          <p>This use case is archived, so it is read-only. It is out of the lists, the counts and the dashboard. Nothing in it was deleted.</p>
          {editing ? <button type="button" class="btn pri" data-restore onClick={() => archive("restore")}>Restore</button> : <span class="muted">Switch to Edit to restore it.</span>}
        </div>
      ) : null}
      <div class="ucd-grid">
        <div class="ucd-main">
          <section class="ucd-card" aria-labelledby="ucd-h-std">
            <h2 id="ucd-h-std" class="ucd-ch"><span>Where it stands</span>{!ro ? <span class="ucd-hint">Click the text to change it</span> : null}</h2>
            {!ro ? <RichField field="standing" id={u.id} value={u.standing} label={`where ${refWords(u)} stands`} empty="Nothing written yet. Click to write."
              save={(html) => send({ standing: html }, "Text saved.")} />
              : safe(u.standing) ? <div class="prose ucd-std" dangerouslySetInnerHTML={{ __html: safe(u.standing) }} /> : <p class="muted">Nothing written yet.</p>}
          </section>
          <section class="ucd-card" aria-labelledby="ucd-h-work">
            <h2 id="ucd-h-work" class="ucd-ch"><span>Work items</span>
              {open.length && label ? <button type="button" class="link" data-open-all onClick={() => openWork(setFilter(initial(), "use_case", [label], false))}>{`Open all ${open.length} in Work items`}</button> : null}
            </h2>
            {work.length ? (
              <ul class="ucd-items plain">
                {work.map((r) => {
                  const due = r.kind === "decision" || r.kind === "action" ? dueCell(r, todayIso()).date : "", who = ownerOf(r.owner).text, pill = pillOf(r, todayIso());
                  const extra = [who !== "—" ? who : "", due && due !== "—" ? `Due ${due}` : r.kind === "action" ? "No due date" : ""].filter(Boolean).join(" · ") || "No owner";
                  const mode_ = isOpen(r) ? "open" : "all";
                  return (
                    <li key={r.id}>
                      <button type="button" class="ucd-item" data-item={r.id} title={`Show ${r.id} in Work items`}
                        onClick={() => openWork({ ...setFilter(initial(), "use_case", [label], false), mode: mode_ })}>
                        <span class="ucd-id num">{r.id}</span><span class="ucd-t">{r.title}</span>
                        <span class={`pill ${pill.class}`}>{pill.text}</span><span class="ucd-x">{extra}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            ) : <p class="muted" data-no-work>No work items are linked to this use case yet.</p>}
          </section>
          {!ro ? (
            <p class="ucd-foot"><button type="button" class="link" data-archive onClick={() => archive("archive")}>Archive this use case (it can be restored; nothing is deleted)</button></p>
          ) : null}
        </div>
        <div class="ucd-side">
          <section class="ucd-card" aria-labelledby="ucd-h-det">
            <h2 id="ucd-h-det" class="ucd-ch">Details</h2>
            <dl class="ucd-kv">
              {u.owner ? <><dt>Owner</dt><dd>{u.owner}</dd></> : null}
              <dt>Dashboard</dt><dd data-dash>{archived ? "Archived" : on ? EYE.on : EYE.off}</dd>
              <dt>Last change</dt><dd>{last || "No changes recorded"}</dd>
            </dl>
          </section>
          <section class="ucd-card" aria-labelledby="ucd-h-ms">
            <h2 id="ucd-h-ms" class="ucd-ch">Milestones</h2>
            {ms.length ? <ul class="ucd-ms plain">{ms.map((m) => <li key={m.id} data-ms={m.id}><span>{m.name}</span><span class="muted num">{showDate(m.status === "Done" && m.actual_date ? m.actual_date : m.baseline_date || m.forecast_date)}{m.status === "Done" ? " · Done" : ""}</span></li>)}</ul>
              : <p class="muted">No milestones: none of its work items is linked to one.</p>}
          </section>
          <section class="ucd-card" aria-labelledby="ucd-h-hist">
            <h2 id="ucd-h-hist" class="ucd-ch">History</h2>
            {archived ? <p class="muted" data-hist-note>Its history comes back when it is restored.</p>
              : hist.state === "failed" ? <p class="muted" data-hist-note>The history could not be read just now. Reload the page to try again.</p>
              : hist.state === "loading" ? <p class="muted" data-hist-note>Reading the history.</p>
              : !hist.lines.length ? <p class="muted" data-hist-note>No changes recorded yet.</p>
              : (
                <>
                  <ul class="ucd-hist plain" data-history>
                    {lines.map((h, i) => {
                      const t = when(h.at), how = HOW[h.how] || "";
                      return <li key={`${h.at}-${h.field}-${i}`}><span class="ucd-hw">{h.who ? <><b>{h.who}</b>{" "}</> : null}{whatWas(h)}</span><time class="ucd-hm">{[t.day && t.time ? `${t.day} at ${t.time}` : t.day, how].filter(Boolean).join(" · ")}</time></li>;
                    })}
                  </ul>
                  {hist.lines.length > SHOW ? <button type="button" class="link" data-hist-all onClick={() => setAll(!all)}>{all ? "Show the latest only" : `Show all ${hist.lines.length} changes`}</button> : null}
                </>
              )}
          </section>
        </div>
      </div>
    </div>
  );
}
