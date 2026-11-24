// Risks and issues, Open actions and Decisions in Edit (prototype parity A-D5, views.js itemTableHtml): the same rows View draws,
// with every part changed in place, an eye on each row that takes it off the page, a line to add a new one ("Owner: what it is",
// then Enter), "Showing N of M" and "Add from your project record (N)". Each is ONE change with one Undo, sent through clark's one
// change route; the page keeps no copy of its own and draws what clark saved (stores/changes.js reads the project again).
// What is edited in place is what View shows: the status (Cell, edit/cells/), the owner, the date, and the client's own wording
// (client_message), and a risk's or issue's priority through its impact and likelihood (the Cell's rating picker, item 210).
import { useRef, useState } from "preact/hooks";
import { data, openPeek } from "../stores/report.js";
import { change, changeCell, refresh, say } from "../stores/changes.js";
import { ownerOf, showDate, dueField } from "../workItems.js";
import { dateWord, clientPill, lateWord, hiddenIds } from "../logic/sectionRows.js";
import { rulesFor, publishable } from "../logic/publishable.js";
import { pickable, idsOf } from "../logic/picker.js";
import { rowsFor, candidates, wordings, todayOf, ItemIcon, Head, iconWords, listClass, columnsFor, place } from "../components/ItemRows.jsx";
import { Picker } from "../components/Picker.jsx";
import { Icon } from "../components/Icon.jsx";
import { Cell } from "./cells/Cell.jsx";
import { RichField } from "./RichField.jsx";
import { richOrPlain } from "../logic/richOrPlain.js";
import { richWords } from "../logic/richWords.js";
import { tableOf } from "./itemEdit.js";
import { eyeWords } from "../logic/eyeWords.js";
import { AskAbout } from "./AskAbout.jsx";

export const WORDS_MAX = __CLARK_ITEM_TITLE_MAX__;      // clark/limits.py ITEM_TITLE_MAX, written in by the build: a work item's text is that many characters at most
const A = { raid: "a risk", actions: "an action", decisions: "a decision" };
const PLACEHOLDER = (type) => `+ Add ${A[type]}: type “Owner: what it is”, then Enter`;

const NOT_NAMES = new Set(["note", "notes", "todo", "fyi", "update", "re", "http", "https", "action", "risk", "issue", "decision"]);

// What the add line's text says: "Owner: what it is" gives the owner and the words; with no colon the owner is not known yet.
export function parseAdd(text) {
  const t = String(text == null ? "" : text).replace(/\s+/g, " ").trim();
  const at = t.indexOf(":");
  if (at < 0) return { owner: "", what: t };
  const who = t.slice(0, at).trim();
  // Only a name before a colon and a space (or the end) is an owner: a time like 10:30, a link or "Note: x" is part of the words.
  const looksLikeName = who && who.split(" ").length <= 3 && !/\d/.test(who) && !/[/\\@]/.test(who)
    && (at === t.length - 1 || t[at + 1] === " ") && !NOT_NAMES.has(who.toLowerCase());
  if (!looksLikeName) return { owner: "", what: t };
  return { owner: who, what: t.slice(at + 1).trim() };
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

// A row's client wording (row 1288): the Full editor (RichField), saved as its HTML (the server cleans it, as a milestone's Client wording): the page,
// the file and the Word and Excel copies carry its words, and an older plain value loads as the same words and is left as it is until changed. A click
// away saves, Esc puts the old words back; one change, one Undo. A text too long is said in the field, which stays open.
export function Words({ row, text, cls = "wl-words" }) {
  const was = text || "";
  const html = (() => { try { return richOrPlain(was); } catch (e) { return ""; } })();
  const put = async (value) => {
    const t = richWords(value).trim() ? value : "";
    if (t === was || t === html) return true;
    if (Array.from(richWords(value).trim()).length > WORDS_MAX) return `The wording can be ${WORDS_MAX} characters at most. Shorten it and try again.`;
    const reply = await changeCell(tableOf(row), row.id, { client_message: t }, { text: `Client Message of ${row.id} changed.`, back: `Client Message of ${row.id} is back as it was.` });
    if (!reply) return false;
    await refresh();                                  // the reply never carries the words (as a title is not said back): read them again
    return true;
  };
  return <RichField field="client_message" id={row.id} value={html} label={`Client Message of ${row.id}`} empty="" cls={cls} attrs={{ "data-ce": row.id }} save={put} />;
}

function EditRow({ row, today, words, type, cols }) {
  const pill = clientPill(row, today), who = ownerOf(row.owner), date = dueField(row), late = lateWord(row, today);
  const risk = row.kind === "risk" || row.kind === "issue";
  const w = eyeWords(true, row), eye = () => change({ kind: "report_hidden", op: "new", id: row.id, place: "eye" }, w.said);
  const st = (c) => place(cols.ord, c);      // row 1534: the cells are drawn in the order saved for this type on the Work items page
  const cell = {
    ico: <span class="c-ico" style={st("ico")}><Cell row={row} field="status" said={pill.text} keep tipSay={iconWords(row, pill, todayOf())}><ItemIcon row={row} pill={pill} plain /></Cell></span>,
    title: <span class="wl-title c-title" style={st("title")} title={words[row.id]}><Words row={row} text={row.client_message || words[row.id]} /></span>,
    owner: <span class="c-owner" style={st("owner")} title={who.initials ? who.text : undefined}>
      <Cell row={row} field="owner" said={who.initials ? who.text : "none"}>
        {who.initials ? <><span class="av" aria-hidden="true">{who.initials}</span><span class="nm">{who.text}</span></> : <span class="nm muted">No owner</span>}
      </Cell>
    </span>,
    date: <span class="c-date num" style={st("date")}>
      <Cell row={row} field="due" said={date ? showDate(date) : "none"}>
        <span class="num">{date ? `${type === "decisions" ? dateWord(row) + " " : ""}${showDate(date)}` : "No date"}</span>
      </Cell>
    </span>,
    prio: <span class="c-prio" style={st("prio")}>{risk && row.priority ? <Cell row={row} field="priority" said={row.priority}><span class="prio">{row.priority}</span></Cell> : late ? <span class="late">{late}</span> : null}</span>,
    id: <span class="c-id wl-id num" style={st("id")}>
      <button type="button" class="idl" data-open aria-label={`Open ${row.id}`} onClick={() => openPeek(row.id, "item")}>{row.id}</button>
      <button type="button" class="ib" data-eye aria-label={w.label} title={w.title} onClick={eye}><Icon name="eye" /></button>
      <AskAbout kind="item" id={row.id} name={`${row.id} ${words[row.id] || ""}`.trim()} />
    </span>,
  };
  return (
    <li class="wl-row" data-id={row.id} data-kind={row.kind}>
      {cols.list.map((c) => cell[c])}
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
  const today = todayOf(), words = wordings(d), shown = rowsFor(type), cols = columnsFor(type, true);
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
      <ul class={listClass(type, "edit")} {...cols.attrs}>
        <Head type={type} id cols={cols} />
        {shown.map((r) => <EditRow key={r.id} row={r} today={today} words={words} type={type} cols={cols} />)}
        <AddLine type={type} />
      </ul>
      <p class="note" data-showing>{`Showing ${shown.length} of ${all.length}. Select any part to change it; the ID opens the full item; the eye takes it off the page.`}</p>
      {n > 0 && !pick ? <button type="button" class="link add-from" data-addfrom={type} ref={button} onClick={() => setPick(true)}>{`+ Add from your project record (${n})`}</button> : null}
      {pick ? <Picker data={here} hiddenIds={hidden} onPage={[]} onAdd={add} onClose={back} /> : null}
    </div>
  );
}
