// The Dashboard's use case summary in Edit (#455, prototype parity: system/prototype/views.js ucTableHtml and ucForm). The Edit parts
// that Section.jsx and UseCases.jsx take from `tools.ucEdit`, so a published file and View have none of them:
//   Add      the growing "+" in the section's header ("Add use case"); it opens the box "Add a use case" (ID, Use case, Status, Headline)
//   Status   the status word on each row, a button in Edit; it opens a menu of the three words
//   Commit   (issue 709) the commitment chip under the status: a menu of the three words and "No flag" (edit/CommitMenu.jsx)
//   Headline the headline on each row, changed in place
//   Name     the name in the opened row, changed in place
//   FromRecord  "+ Add a use case from your project record (N)": the picker of the use cases that are not on the dashboard
//   Eye      (#485) the eye on each row: take the use case off the page (Undo puts it back)
//   Standing (#485) "Where it stands" in the opened row, changed in place with the same editor as the use case's own page
//   NextStep (#485) "+ Add a next step: “Owner: what it is”, then Enter" in the opened row: a new action that names the use case
//   LinkButton (#485) "+ Link an existing work item": the box that links open work items to the use case
// The three boxes (Add a use case, the picker, the link box) are NOT drawn where their buttons are: those sit inside <main>, and a box makes <main> inert,
// so a box drawn there could not take focus, typing or a click. The buttons only set the signal `box`; `Boxes` draws them, and App.jsx
// mounts `Boxes` beside <main> the way it mounts AddDialog.
// Each is ONE change through stores/changes.js (kind use_cases: update, new; or report_hidden: pick). A new use case has no Undo
// (a use case is archived, never deleted: its toast says so), the rest keep theirs. A new use case starts hidden from the client (eye off,
// the owner, 03-11-2026): it is counted in "from your project record (N)" and on the Use cases page until its eye is turned on.
import { signal } from "@preact/signals";
import { getArchived } from "../api.js";
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { data, mode, project, rows } from "../stores/report.js";
import { inertBehind } from "./modalLayers.js";
import { change, say } from "../stores/changes.js";
import { NewTile } from "../components/NewTile.jsx";
import { Menu } from "../components/Menu.jsx";
import { Picker } from "../components/Picker.jsx";
import { Icon } from "../components/Icon.jsx";
import { actionIcon } from "../menuIcons.js";
import { Line, NAME_MAX, HEAD_MAX, HEADLINE_PROMPT, STANDING_PROMPT } from "../components/UseCaseDetail.jsx";
import { RichField } from "./RichField.jsx";
import { KIND_WORDS, todayIso } from "../workItems.js";
import { splitStep, knownNames, stepValues, linkable, openCount, narrow, KINDS, linkedWords, linkableMilestones } from "../logic/ucRow.js";
import { peopleList } from "../stores/handover.js";
import { CommitMenu } from "./CommitMenu.jsx";

export const STATUSES = [["On track", "g"], ["Flag", "a"], ["High risk", "r"]];
const rag = (status) => (STATUSES.find((s) => s[0] === status) || [0, "n"])[1];
const REF_MAX = 20;                                           // changes.py UC_REF_LIMIT
const name = (u) => u.ref || u.id;                            // "Use case 1.1" as the prototype's toasts say it

/** Which box is open: null, or { kind: "add" | "pick" | "link", opener, uc } (opener is the element that had focus, so Esc gives it back;
 * uc is the use case the link box is for). */
const box = signal(null);
const openBox = (kind, uc = "", live = false) => { box.value = { kind, uc, live, opener: document.activeElement && document.activeElement !== document.body ? document.activeElement : null }; };
const closeBox = () => { box.value = null; };
/** Row 830: the Add box from the Use cases page, which has no View|Edit switch (the Dashboard's button only draws it in Edit). */
export const openAdd = () => openBox("add", "", true);

/** The id of the use case just added: the summary opens its row (UseCases.jsx reads it once and clears it). */
export const added = signal("");

const send = (u, changes, done) => change({ kind: "use_cases", op: "update", id: u.id, changes, place: "cell" }, done);

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

// A modal box: the page behind is inert, Esc and a click on the backdrop close it, Tab stays inside, focus goes back to what opened it.
function Modal({ onClose, opener, children }) {
  const root = useRef(null);
  // A layout effect, not useEffect: the page goes inert, and the opener is held for the way back, in the step that draws the box (where the
  // box also takes its focus). useEffect runs a paint later, or up to a tenth of a second on a slow runner: a box shut by Esc before then
  // never ran its clean-up, so the focus did not go back, and until then the box showed with the page behind it still live.
  useLayoutEffect(() => {
    const release = inertBehind(root.current);                // everything outside the box, a toast that arrives later too (modalLayers.js, #425)
    return () => {
      release();
      if (opener && opener.isConnected && opener.focus) opener.focus();
    };
  }, []);
  // Esc also on the document: while a save is out the Add button is disabled, the focus drops to the page, and a key there never reaches the box's own handler.
  useEffect(() => {
    const esc = (e) => { if (e.key === "Escape" && !e.defaultPrevented) { e.preventDefault(); onClose(); } };
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, []);
  const keys = (e) => {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onClose(); return; }
    if (e.key !== "Tab" || !root.current) return;
    const all = Array.from(root.current.querySelectorAll(FOCUSABLE));
    if (!all.length) return;
    const first = all[0], last = all[all.length - 1];
    if (!root.current.contains(document.activeElement)) { e.preventDefault(); (e.shiftKey ? last : first).focus(); }
    else if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  };
  return <div class="ad-scrim" data-edit-only ref={root} onKeyDown={keys} onPointerDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>{children}</div>;
}

// "Add a use case": the prototype's box and words. The ID is the reference the project writes ("3.1"); clark gives the id itself.
function AddBox({ onClose, opener }) {
  const first = useRef(null), [busy, setBusy] = useState(false);
  // Focus goes to the ID field in the same step that draws the box. useEffect runs after the paint, so a person (or a test) who had
  // already clicked into Use case could have the late focus pull them back to ID mid-typing: the name then landed in ID, Use case
  // stayed empty, and Add was refused without a word.
  useLayoutEffect(() => { if (first.current) first.current.focus(); }, []);
  const submit = async (e) => {
    e.preventDefault();
    const f = e.currentTarget, ref = f.ucI.value.trim(), title = f.ucT.value.trim();
    const taken = (list) => list.some((u) => String(u.ref || "").trim().toLowerCase() === ref.toLowerCase());
    const refuse = () => { f.ucI.setCustomValidity("That ID is already used"); f.ucI.reportValidity(); f.ucI.setCustomValidity(""); };
    if (!ref) { f.ucI.value = ""; f.ucI.reportValidity(); return; }   // a blank ID: the field's own "fill in" bubble
    if (taken(data.value.use_cases || [])) { refuse(); return; }
    // The page's own data leaves the archived use cases out, but their ID is still taken: read them with the archived rows.
    const arch = await getArchived(project.value);
    if (arch.ok && taken((arch.data.use_cases || []).filter((u) => u.archived))) { refuse(); return; }
    setBusy(true);
    const reply = await change({ kind: "use_cases", op: "new", values: { ref, title, status: f.ucS.value, headline: f.ucH.value.trim() }, place: "report" }, "");
    setBusy(false);
    if (!reply) return;                                             // the toast says why; the box stays, nothing was added
    added.value = reply.ref;
    onClose(true);
    say("done", `Use case ${ref} added, hidden from the client until its eye is turned on. Archive it from the Use cases page if it is not wanted.`);   // #455: a new use case starts with its eye off
  };
  return (
    <Modal onClose={() => onClose(false)} opener={opener}>
      <form class="ad ucm" id="ucF" role="dialog" aria-modal="true" aria-labelledby="ucm-title" onSubmit={submit}>
        <div class="ad-head"><h2 id="ucm-title">Add a use case</h2></div>
        <div class="ucm-form">
          <label for="ucI">ID</label><input class="field" id="ucI" name="ucI" ref={first} required maxLength={REF_MAX} placeholder="For example: 3.1" autocomplete="off" />
          <label for="ucT">Use case</label><input class="field" id="ucT" name="ucT" required maxLength={NAME_MAX} placeholder="What it does" autocomplete="off" />
          <label for="ucS">Status</label><select class="field" id="ucS" name="ucS">{[...STATUSES, ["Done"]].map(([s]) => <option key={s}>{s}</option>)}</select>
          <label for="ucH">Headline</label><input class="field" id="ucH" name="ucH" maxLength={HEAD_MAX} placeholder={HEADLINE_PROMPT} autocomplete="off" />
        </div>
        <div class="ad-foot">
          <button type="button" class="pk-btn" data-cancel onClick={() => onClose(false)}>Cancel</button>
          <button type="submit" class="pk-btn pri" data-place disabled={busy}>Add</button>
        </div>
      </form>
    </Modal>
  );
}

/** The growing Add button in the section's header: a "+" that grows to "Add use case" on the pointer or the keyboard. */
export function Add() {
  return (
    <span class="uc-add" data-edit-only>
      <NewTile word="Add use case" kind="use_case" id="ucAdd" onAdd={() => openBox("add")} />
    </span>
  );
}

/** The status word of a row: a button in Edit that opens the three words. */
export function Status({ u }) {
  const r = rag(u.status);
  return (
    <span class="ucst" data-uc-status={u.id} data-edit-only>
      <Menu label={u.status} labelCls={`ucword rag-${r}`} btnCls="ucw-btn" ariaLabel={`Status: ${u.status}. Change`} menuLabel="Status" id={`ucst-${u.id}`} chevron={false}
        items={STATUSES.map(([n, c]) => ({ id: n, name: n, word: c, icon: actionIcon("status"), checked: u.status === n }))}
        onPick={(n) => { if (n !== u.status) send(u, { status: n }, `Use case ${name(u)} set to ${n}.`); }} />
    </span>
  );
}

/** The headline of a row, changed in place (Enter or leaving it saves, Esc puts the old words back). */
export function Headline({ u }) {
  return (
    <span class="uchead uchead-ed" data-edit-only>
      <Line value={u.headline} label={`Headline for ${name(u)}`} cls="uchead-in" field="headline" max={HEAD_MAX} empty={HEADLINE_PROMPT} ro={false}
        problem={(t) => (Array.from(t).length > HEAD_MAX ? `A headline can be ${HEAD_MAX} characters at most. The old headline was kept.` : "")}
        onSave={(t) => send(u, { headline: t }, `Use case ${name(u)} saved.`)} />
    </span>
  );
}

/** "Use case 1.1: Name" at the top of an opened row, the name changed in place. */
export function Name({ u }) {
  return (
    <div class="ucx-name" data-edit-only>
      <span class="ucx-ref">Use case {name(u)}:</span>
      <Line value={u.title} label={`Use case name for ${name(u)}`} cls="ucx-in" field="title" max={NAME_MAX} empty="Name this use case" ro={false}
        problem={(t) => (!t ? "A use case needs a name. The old name was kept." : Array.from(t).length > NAME_MAX ? `A name can be ${NAME_MAX} characters at most. The old name was kept.` : "")}
        onSave={(t) => send(u, { title: t }, `Use case ${name(u)} saved.`)} />
    </div>
  );
}

// The picker of the use cases that are not on the dashboard, in the prototype's words.
function Pick({ onClose, opener }) {
  const only = { use_cases: (data.value.use_cases || []).filter((u) => !u.archived) };
  const add = async (ids) => {
    onClose(true);
    const n = ids.length;
    const reply = await change({ kind: "report_hidden", op: "pick", ids, place: "report" }, `${n} use case${n > 1 ? "s" : ""} added to the page`);
    if (reply && !reply.apply_id) say("done", `${n} use case${n > 1 ? "s" : ""} added to the page`);
  };
  return (
    <Modal onClose={() => onClose(false)} opener={opener}>
      <Picker data={only} hiddenIds={[]} title="Add a use case from your project record" placeholder="Search by name, ID, owner or use case"
        onAdd={add} onClose={() => onClose(false)} />
    </Modal>
  );
}

/** "+ Add a use case from your project record (N)": N is the use cases that are not on the dashboard. */
export function FromRecord({ n }) {
  if (!n) return null;
  return <button type="button" class="link add-from" data-uc-back data-edit-only onClick={() => openBox("pick")}>{`+ Add a use case from your project record (${n})`}</button>;
}

/** The eye on a row: takes the use case off the page. It is the use case's own switch (the same change as the eye on the Use cases page);
 * one step, one Undo, and the row leaves the dashboard (it stays on the Use cases page, and "Add a use case from your project record" brings it back). */
export function Eye({ u }) {
  const take = async (e) => {
    e.stopPropagation();
    const btn = e.currentTarget, eyes = Array.from(document.querySelectorAll(".uc .ucrow [data-uc-eye]")), at = eyes.indexOf(btn);
    const reply = await change({ kind: "use_cases", op: "update", id: u.id, changes: { client_visible: 0 }, place: "eye" }, `Use case ${name(u)} taken off the page.`, { focus: `[data-uc-eye="${u.id}"]` });
    if (!reply) return;
    setTimeout(() => {          // the row has left: the focus goes to the next row's eye, else the one before, else the way back to the record
      const now = Array.from(document.querySelectorAll(".uc .ucrow [data-uc-eye]"));
      const to = now[at] || now[at - 1] || document.querySelector("[data-uc-back], #ucAdd");
      if (to && to.focus) to.focus({ preventScroll: true });
    }, 60);
  };
  return <button type="button" class="uceye" data-uc-eye={u.id} data-edit-only aria-label={`Take use case ${name(u)} off the page`} title="Take it off the page" onClick={take}><Icon name="eye" /></button>;
}

/** "Where it stands" in an opened row: the text is changed in place, as on the use case's own page (the same editor, one change with one Undo). */
export function Standing({ u }) {
  return <RichField field="standing" id={u.id} value={u.standing} label={`where ${name(u)} stands`} empty={STANDING_PROMPT}
    save={(html) => send(u, { standing: html }, `Use case ${name(u)} saved.`)} />;
}

/** "+ Add a next step: “Owner: what it is”, then Enter": a new action that names the use case, in one step with one Undo. The words before
 * the first colon are the owner when they are a person ("Fix: the loader" has none); the step is due a week from today, as in the prototype. A step that is refused stays in the box. */
export function NextStep({ u }) {
  const busy = useRef(false);
  const keys = async (e) => {
    if (e.key !== "Enter" || e.isComposing) return;
    e.preventDefault();
    const input = e.currentTarget, parts = splitStep(input.value, knownNames(data.value, peopleList.value));
    if (!parts || busy.current) return;
    busy.current = true;
    const reply = await change({ kind: "actions", op: "new", values: stepValues(parts, u.id, todayIso()), place: "report" }, `Next step added to use case ${name(u)}.`);
    busy.current = false;
    if (reply) { input.value = ""; input.focus(); }
  };
  return (
    <div class="ucx-step" data-edit-only>
      <input class="field" data-uc-step={u.id} placeholder="+ Add a next step: “Owner: what it is”, then Enter" aria-label="Add a next step" autocomplete="off" onKeyDown={keys} />
    </div>
  );
}

/** Row 1141: "Add a milestone" (the link of row 1107): a menu of the project's milestones this use case has no direct link to. A pick is ONE change (msadd) that links the
 * use case itself to the milestone, with one Undo. */
export function MilestoneLink({ u }) {
  const items = linkableMilestones(data.value, u.id);
  const pick = (id) => {
    const m = items.find((x) => x.id === id);
    if (m) change({ kind: "use_cases", op: "msadd", id: u.id, ids: [m.id], place: "report" }, `${m.name} linked to use case ${name(u)}.`);
  };
  return (
    <span class="ucx-mslink" data-ms-link={u.id} data-edit-only>
      <Menu label="Add a milestone" ariaLabel={`Add a milestone to use case ${name(u)}`} menuLabel="Milestones to link" id={`ucd-mslink-${u.id}`} btnCls="btn sm" left
        items={items.map((m) => ({ ...m, icon: actionIcon("milestone") }))} onPick={pick} />
    </span>
  );
}

/** Row 1107: "Unlink" on a milestone the use case is linked to directly: ends that one link (msremove), one Undo; its work items are not touched. */
export function MilestoneUnlink({ u, m }) {
  const go = () => change({ kind: "use_cases", op: "msremove", id: u.id, ids: [m.id], place: "report" }, `${m.name} unlinked from use case ${name(u)}.`,
    { focus: "[data-ms-link] button" });
  return <button type="button" class="link ucx-msrm" data-ms-unlink={m.id} data-edit-only aria-label={`Unlink ${m.name} from use case ${name(u)}`} onClick={go}>Unlink</button>;
}

/** "+ Link an existing work item": opens the box of the open work items that are not yet linked to this use case. */
export function LinkButton({ u }) {
  return <button type="button" class="link add-from" data-uc-link={u.id} data-edit-only onClick={() => openBox("link", u.id, true)}>+ Link an existing work item</button>;
}

// The box that links work items to a use case, in the prototype's words: the open ones not yet linked, searched by name, ID, owner or use
// case, narrowed to a kind, several chosen at once. The link is ONE change for all of them, with one Undo.
function LinkBox({ uc, onClose, opener }) {
  const d = data.value, u = (d && d.use_cases || []).find((x) => x.id === uc);
  const [query, setQuery] = useState(""), [kind, setKind] = useState(""), [chosen, setChosen] = useState([]);
  const search = useRef(null), list = useRef(null);
  useLayoutEffect(() => { if (search.current) search.current.focus(); }, []);    // as the Add box: focus is in the search field before the box is drawn
  if (!u) return null;
  const items = linkable(d, rows.value, uc, todayIso()), shown = narrow(items, kind, query);
  const picked = chosen.filter((id) => items.some((i) => i.id === id)), n = picked.length;
  const toggle = (id) => setChosen(chosen.includes(id) ? chosen.filter((x) => x !== id) : [...chosen, id]);
  const submit = async (e) => {
    e.preventDefault();
    if (!n) return;
    onClose(true);
    await change({ kind: "use_cases", op: "link", id: uc, ids: picked, place: "report" }, linkedWords(n, name(u)));
  };
  const typed = (e) => {
    if (e.isComposing || e.keyCode === 229) return;      // an input method is composing (keyCode 229 is Safari's word for it): Enter picks a candidate, not a row
    if (e.key === "Enter") { e.preventDefault(); if (shown.length === 1 && !chosen.includes(shown[0].id)) setChosen([...chosen, shown[0].id]); }
    else if (e.key === "ArrowDown") { e.preventDefault(); const first = list.current && list.current.querySelector("input"); if (first) first.focus(); }
  };
  const title = `Link work items to use case ${name(u)}`;
  return (
    <Modal onClose={() => onClose(false)} opener={opener}>
      <form class="picker uclink" role="dialog" aria-modal="true" aria-label={title} onSubmit={submit}>
        <div class="pk-head"><h2>{title}</h2><p class="muted">Open work items not linked to this use case yet</p></div>
        <div class="pk-search">
          <label class="pk-q"><span class="sr">Search</span>
            <input ref={search} type="search" placeholder="Search by name, ID, owner or use case" autocomplete="off" value={query} onInput={(e) => setQuery(e.currentTarget.value)} onKeyDown={typed} />
          </label>
          <div class="seg" role="group" aria-label="Kind">
            <button type="button" data-t="" aria-pressed={kind === "" ? "true" : "false"} onClick={() => setKind("")}>All</button>
            {KINDS.map(([k, words]) => <button type="button" key={k} data-t={k} aria-pressed={kind === k ? "true" : "false"} onClick={() => setKind(k)}>{words}</button>)}
          </div>
          <button type="button" class="pk-btn" data-all disabled={!shown.length} onClick={() => setChosen([...chosen, ...shown.map((i) => i.id).filter((id) => !chosen.includes(id))])}>Select all shown</button>
        </div>
        <div class="pk-body">
          <ul class="pick" ref={list}>
            {shown.map((i) => (
              <li key={i.id}>
                <label>
                  <input type="checkbox" value={i.id} checked={chosen.includes(i.id)} onChange={() => toggle(i.id)} />
                  <span class="pk-text"><span class={`type k-${i.kind}`}>{KIND_WORDS[i.kind] || i.kind}</span> {i.title}<br /><span class="muted">{i.meta}</span> <span class={`pill ${i.pill.class}`}>{i.pill.text}</span></span>
                </label>
              </li>
            ))}
          </ul>
          {!shown.length ? <p class="muted pk-none" data-none>{items.length ? "Nothing matches." : openCount(rows.value) ? "Every open work item is linked to this use case already." : "There are no open work items to link."}</p> : null}
        </div>
        <div class="pk-foot">
          <span class="muted pk-count" aria-live="polite">{n ? `${n} selected` : "None selected"}</span>
          <button type="button" class="pk-btn" data-cancel onClick={() => onClose(false)}>Cancel</button>
          <button type="submit" class="pk-btn pri" disabled={!n}>{n ? `Add ${n}` : "Add selected"}</button>
        </div>
      </form>
    </Modal>
  );
}

/** The open box, drawn beside <main> (App.jsx), so the page it makes inert does not hold it. */
export function Boxes() {
  const b = box.value;
  if (!b || (mode.value !== "edit" && !b.live)) return null;       // row 830: a box opened from the Use cases page needs no Edit mode
  if (b.kind === "link") return <LinkBox key={`link-${b.uc}`} uc={b.uc} opener={b.opener} onClose={closeBox} />;
  return b.kind === "add" ? <AddBox key="add" opener={b.opener} onClose={closeBox} /> : <Pick key="pick" opener={b.opener} onClose={closeBox} />;
}

/** The Edit parts as one object, `tools.ucEdit`. */
export const UCEDIT = { Add, Status, Commit: CommitMenu, Headline, Name, FromRecord, Eye, Standing, NextStep, LinkButton, MilestoneLink, MilestoneUnlink, Boxes, added };
