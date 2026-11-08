// Risks and issues, Open actions and Decisions in Edit (prototype parity A-D5, views.js itemTableHtml): the same rows View draws,
// with every part changed in place, an eye on each row that takes it off the page, a line to add a new one ("Owner: what it is",
// then Enter), "Showing N of M" and "Add from your project record (N)". Each is ONE change with one Undo, sent through clark's one
// change route; the page keeps no copy of its own and draws what clark saved (stores/changes.js reads the project again).
// What is edited in place is what View shows: the status (Cell, edit/cells/), the owner, the date, and the client's own wording
// (client_message), and a risk's or issue's priority through its impact and likelihood (the Cell's rating picker, item 210).
import { useLayoutEffect, useRef, useState } from "preact/hooks";
import { data, openPeek } from "../stores/report.js";
import { change, changeCell, refresh, say } from "../stores/changes.js";
import { dueCell, ownerOf, showDate, dueField } from "../workItems.js";
import { dateWord, clientPill, hiddenIds } from "../logic/sectionRows.js";
import { rulesFor, publishable } from "../logic/publishable.js";
import { pickable, idsOf } from "../logic/picker.js";
import { rowsFor, candidates, wordings, todayOf } from "../components/ItemRows.jsx";
import { Picker } from "../components/Picker.jsx";
import { Icon } from "../components/Icon.jsx";
import { Cell } from "./cells/Cell.jsx";
import { plainBox, read, show } from "./Title.jsx";
import { tableOf } from "./itemEdit.js";

export const WORDS_MAX = __CLARK_ITEM_TITLE_MAX__;      // clark/limits.py ITEM_TITLE_MAX, written in by the build: a work item's text is that many characters at most
const A = { raid: "a risk", actions: "an action", decisions: "a decision" };
const PLACEHOLDER = (type) => `+ Add ${A[type]}: type “Owner: what it is”, then Enter`;

// What the add line's text says: "Owner: what it is" gives the owner and the words; with no colon the owner is not known yet.
export function parseAdd(text) {
  const t = String(text == null ? "" : text).replace(/\s+/g, " ").trim();
  const at = t.indexOf(":");
  if (at < 0) return { owner: "", what: t };
  return { owner: t.slice(0, at).trim(), what: t.slice(at + 1).trim() };
}

// The request that adds one row: the words are the row's text and its client wording, because a row with no client wording is
// not drawn. A new risk starts at Medium impact and likelihood (its priority is worked out from them).
export function addRequest(type, text) {
  const { owner, what } = parseAdd(text);
  if (!what) return { problem: "Type what it is after the owner, like Mia: Check the supplier dates." };
  if (Array.from(what).length > WORDS_MAX) return { problem: `Use ${WORDS_MAX} characters at most. Shorten it and try again.` };
  const who = owner && Array.from(owner).length <= WORDS_MAX ? owner : "";
  const values = type === "decisions" ? { decision: what, client_message: what, ...(who ? { made_by: who } : {}) }
    : { ...(type === "raid" ? { type: "Risk", impact: "Medium", likelihood: "Medium" } : {}), description: what, client_message: what, ...(who ? { owner: who } : {}) };
  return { request: { kind: type, op: "new", values, place: "report" } };
}

// The ids the section could show but does not: taken off with the eye, or shown to no client, and never a row that publish would keep out.
function canShow(type, d, items) {
  const rules = rulesFor({ code: d && d.project && d.project.code, hidden: [], labelRules: d && d.label_rules, labels: d && d.labels, sections: [] });
  return new Set(items.filter((r) => publishable({ ...((d[type] || []).find((x) => x.id === r.id) || {}), client_visible: 1 }, type, rules)).map((r) => r.id));
}

// A row's client wording, edited in place as plain text: saved when the field is left or on Enter, Esc puts the old words back.
export function Words({ row, text, cls = "cell-ce" }) {
  const ref = useRef(null), now = useRef(text), cancelled = useRef(false);
  now.current = text;
  useLayoutEffect(() => { const el = ref.current; if (el && read(el) !== text && document.activeElement !== el) show(el, text); }, [text]);       // what clark saved, drawn unless it is being typed in
  const commit = () => {
    const el = ref.current;
    if (cancelled.current) { cancelled.current = false; return; }
    const t = read(el).replace(/\s+/g, " ").trim();
    if (t === now.current) { show(el, now.current); return; }
    if (Array.from(t).length > WORDS_MAX) { show(el, now.current); say("problem", `The wording can be ${WORDS_MAX} characters at most. Shorten it and try again.`); return; }
    changeCell(tableOf(row), row.id, { client_message: t }, { text: `Wording of ${row.id} changed.`, back: `Wording of ${row.id} is back as it was.` })
      .then((reply) => (reply ? refresh() : show(el, now.current)));       // the reply never carries the words (as a title is not said back): read them again
  };
  const onKeyDown = (e) => {
    if (e.isComposing) return;
    if (e.key === "Enter") { e.preventDefault(); ref.current.blur(); }
    else if (e.key === "Escape") { e.preventDefault(); cancelled.current = true; show(ref.current, now.current); ref.current.blur(); }
  };
  return plainBox({ ref, class: cls, "data-edit-only": "", "data-ce": row.id, "data-f": "title", "aria-label": `Wording of ${row.id}`, onBlur: commit, onKeyDown, spellcheck: true });
}

function EditRow({ row, today, words }) {
  const pill = clientPill(row, today), due = dueCell(row, today), who = ownerOf(row.owner), date = dueField(row);
  const risk = row.kind === "risk" || row.kind === "issue";
  const eye = () => change({ kind: "report_hidden", op: "new", id: row.id, place: "eye" }, `${row.id} is off the page.`);
  return (
    <li class="wl-row" data-id={row.id} data-kind={row.kind}>
      <span class="wl-state"><Cell row={row} field="status" said={pill.text} keep><span class={`pill ${pill.class}`}>{pill.text}</span></Cell></span>
      <span class="wl-main">
        <span class="wl-title">{risk ? <span class="tag">{row.kind === "issue" ? "Issue" : "Risk"}</span> : null}{risk ? " " : ""}<Words row={row} text={words[row.id]} /></span>
        <span class="wl-meta">
          <Cell row={row} field="owner" said={who.initials ? who.text : "none"}>
            {who.initials ? <span class="av" aria-hidden="true">{who.initials}</span> : null}<span class={who.initials ? "" : "muted"}>{who.initials ? who.text : "No owner"}</span>
          </Cell>
          <span class="dot" aria-hidden="true">{"·"}</span>
          <Cell row={row} field="due" said={date ? showDate(date) : "none"}>
            <span class="num">{date ? `${dateWord(row)} ${showDate(date)}` : "No date"}</span>{row.kind === "action" && due.words ? <span class={due.tone ? "late" : ""}>{due.words}</span> : null}
          </Cell>
          {risk && row.priority ? <><span class="dot" aria-hidden="true">{"·"}</span><Cell row={row} field="priority" said={row.priority}><span class="prio">{row.priority}</span></Cell></> : null}
        </span>
      </span>
      <span class="wl-id num">
        <button type="button" class="idl" data-open aria-label={`Open ${row.id}`} onClick={() => openPeek(row.id, "item")}>{row.id}</button>
        <button type="button" class="ib" data-eye aria-label={`Take ${row.id} off the page`} title="Take off the page" onClick={eye}><Icon name="eye" /></button>
      </span>
    </li>
  );
}

function AddLine({ type }) {
  const input = useRef(null), [busy, setBusy] = useState(false);
  const add = async () => {
    const el = input.current;
    if (!el.value.trim() || busy) return;
    const made = addRequest(type, el.value);
    if (made.problem) { say("problem", made.problem); return; }
    setBusy(true);
    const reply = await change(made.request, `Added ${A[type].replace(/^an? /, "")}.`);
    setBusy(false);
    if (reply) el.value = "";
    el.focus();
  };
  return (
    <li class="wl-add">
      <input ref={input} class="add-in" type="text" data-add-line={type} autocomplete="off" maxLength={WORDS_MAX * 2} placeholder={PLACEHOLDER(type)} aria-label={`Add ${A[type]}`}
        onKeyDown={(e) => { if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); add(); } }} />
    </li>
  );
}

export function ItemRowsEdit({ type }) {
  const d = data.value;
  const [pick, setPick] = useState(false), button = useRef(null);
  if (!d) return null;
  const today = todayOf(), words = wordings(d), shown = rowsFor(type);
  const all = candidates(type), canPick = canShow(type, d, all);
  const hidden = hiddenIds(d), shownIds = new Set(shown.map((r) => r.id));
  const left = all.filter((r) => !shownIds.has(r.id) && canPick.has(r.id));                  // the rows a person can put back
  const text = type === "decisions" ? "decision" : "description";                            // the picker reads the client's wording, never the team's own text
  const here = { [type]: (d[type] || []).filter((r) => left.some((x) => x.id === r.id)).map((r) => ({ ...r, [text]: words[r.id] })) };   // and offers this section's kind only
  const n = idsOf(pickable(here, hidden, "", [])).length;
  const back = () => { setPick(false); setTimeout(() => { if (button.current && button.current.isConnected) button.current.focus(); }, 0); };   // the picker's search box leaves with it; focus goes to the button if it is still there
  const add = (ids) => change({ kind: "report_hidden", op: "pick", ids, place: "report" }, ids.length === 1 ? `${ids[0]} is on the page.` : `${ids.length} items are on the page.`).then((r) => { if (r) back(); });
  return (
    <div class="item-rows-edit" data-edit-only data-item-rows={type}>
      <ul class="wl">
        {shown.map((r) => <EditRow key={r.id} row={r} today={today} words={words} />)}
        <AddLine type={type} />
      </ul>
      <p class="note" data-showing>{`Showing ${shown.length} of ${all.length}. Select any part to change it; the ID opens the full item; the eye takes it off the page.`}</p>
      {n > 0 && !pick ? <button type="button" class="link add-from" data-addfrom={type} ref={button} onClick={() => setPick(true)}>{`+ Add from your project record (${n})`}</button> : null}
      {pick ? <Picker data={here} hiddenIds={hidden} onPage={[]} onAdd={add} onClose={back} /> : null}
    </div>
  );
}
