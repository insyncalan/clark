// The Dashboard's use case summary in Edit (#455, prototype parity: system/prototype/views.js ucTableHtml and ucForm). The Edit parts
// that Section.jsx and UseCases.jsx take from `tools.ucEdit`, so a published file and View have none of them:
//   Add      the growing "+" in the section's header ("Add use case"); it opens the box "Add a use case" (ID, Use case, Status, Headline)
//   Status   the status word on each row, a button in Edit; it opens a menu of the three words
//   Headline the headline on each row, changed in place
//   Name     the name in the opened row, changed in place
//   FromRecord  "+ Add a use case from your project record (N)": the picker of the use cases that are not on the dashboard
// Each is ONE change through stores/changes.js (kind use_cases: update, new; or report_hidden: pick). A new use case has no Undo
// (a use case is archived, never deleted: its toast says so), the rest keep theirs.
import { signal } from "@preact/signals";
import { useEffect, useRef, useState } from "preact/hooks";
import { data } from "../stores/report.js";
import { change, say } from "../stores/changes.js";
import { NewTile } from "../components/NewTile.jsx";
import { Menu } from "../components/Menu.jsx";
import { Picker } from "../components/Picker.jsx";
import { Line, NAME_MAX, HEAD_MAX } from "../components/UseCaseDetail.jsx";
import { liveOf } from "../logic/useCasesList.js";

export const STATUSES = [["On track", "g"], ["Flag", "a"], ["High risk", "r"]];
const rag = (status) => (STATUSES.find((s) => s[0] === status) || [0, "n"])[1];
const REF_MAX = 20;                                           // changes.py UC_REF_LIMIT
const name = (u) => u.ref || u.id;                            // "Use case 1.1" as the prototype's toasts say it

/** The id of the use case just added: the summary opens its row (UseCases.jsx reads it once and clears it). */
export const added = signal("");

const send = (u, changes, done) => change({ kind: "use_cases", op: "update", id: u.id, changes, place: "cell" }, done);

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
const BEHIND = ["#main", ".top"];                             // made inert while a box is open (the same as the Add a section box)

// A modal box: the page behind is inert, Esc and a click on the backdrop close it, Tab stays inside, focus goes back to what opened it.
function Modal({ onClose, opener, children }) {
  const root = useRef(null);
  useEffect(() => {
    const held = BEHIND.map((q) => document.querySelector(q)).filter(Boolean);
    held.forEach((el) => el.setAttribute("inert", ""));
    return () => {
      held.forEach((el) => el.removeAttribute("inert"));
      if (opener && opener.isConnected && opener.focus) opener.focus();
    };
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
  useEffect(() => { if (first.current) first.current.focus(); }, []);
  const submit = async (e) => {
    e.preventDefault();
    const f = e.currentTarget, ref = f.ucI.value.trim(), title = f.ucT.value.trim();
    if (liveOf(data.value).some((u) => String(u.ref || "").trim().toLowerCase() === ref.toLowerCase())) {
      f.ucI.setCustomValidity("That ID is already used"); f.ucI.reportValidity(); f.ucI.setCustomValidity(""); return;
    }
    setBusy(true);
    const reply = await change({ kind: "use_cases", op: "new", values: { ref, title, status: f.ucS.value, headline: f.ucH.value.trim() }, place: "report" }, "");
    setBusy(false);
    if (!reply) return;                                             // the toast says why; the box stays, nothing was added
    added.value = reply.ref;
    onClose(true);
    say("done", `Use case ${ref} added. Archive it from the Use cases page if it is not wanted.`);
  };
  return (
    <Modal onClose={() => onClose(false)} opener={opener}>
      <form class="ad ucm" id="ucF" role="dialog" aria-modal="true" aria-labelledby="ucm-title" onSubmit={submit}>
        <div class="ad-head"><h2 id="ucm-title">Add a use case</h2></div>
        <div class="ucm-form">
          <label for="ucI">ID</label><input class="field" id="ucI" name="ucI" ref={first} required maxLength={REF_MAX} placeholder="For example: 3.1" autocomplete="off" />
          <label for="ucT">Use case</label><input class="field" id="ucT" name="ucT" required maxLength={NAME_MAX} placeholder="What it does" autocomplete="off" />
          <label for="ucS">Status</label><select class="field" id="ucS" name="ucS">{STATUSES.map(([s]) => <option key={s}>{s}</option>)}</select>
          <label for="ucH">Headline</label><input class="field" id="ucH" name="ucH" maxLength={HEAD_MAX} placeholder="One line on where it stands" autocomplete="off" />
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
  const [open, setOpen] = useState(null);                           // null, or the element that had focus
  return (
    <span class="uc-add" data-edit-only>
      <NewTile word="Add use case" kind="use_case" id="ucAdd" onAdd={() => setOpen(document.activeElement || true)} />
      {open ? <AddBox opener={open === true ? null : open} onClose={() => setOpen(null)} /> : null}
    </span>
  );
}

/** The status word of a row: a button in Edit that opens the three words. */
export function Status({ u }) {
  const r = rag(u.status);
  return (
    <span class="ucst" data-uc-status={u.id} data-edit-only>
      <Menu label={u.status} labelCls={`ucword rag-${r}`} btnCls="ucw-btn" ariaLabel={`Status: ${u.status}. Change`} menuLabel="Status" id={`ucst-${u.id}`} chevron={false}
        items={STATUSES.map(([n, c]) => ({ id: n, name: n, word: c, checked: u.status === n }))}
        onPick={(n) => { if (n !== u.status) send(u, { status: n }, `Use case ${name(u)} set to ${n}.`); }} />
    </span>
  );
}

/** The headline of a row, changed in place (Enter or leaving it saves, Esc puts the old words back). */
export function Headline({ u }) {
  return (
    <span class="uchead uchead-ed" data-edit-only>
      <Line value={u.headline} label={`Headline for ${name(u)}`} cls="uchead-in" field="headline" max={HEAD_MAX} empty="One line on where it stands" ro={false}
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
  const [open, setOpen] = useState(null);
  if (!n) return null;
  return (
    <>
      <button type="button" class="link add-from" data-uc-back data-edit-only onClick={() => setOpen(document.activeElement || true)}>{`+ Add a use case from your project record (${n})`}</button>
      {open ? <Pick opener={open === true ? null : open} onClose={() => setOpen(null)} /> : null}
    </>
  );
}

/** The Edit parts as one object, `tools.ucEdit`. */
export const UCEDIT = { Add, Status, Headline, Name, FromRecord, added };
