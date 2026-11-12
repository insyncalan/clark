// The peek's Workstream, Milestone and Use case, each a button that opens a short list to choose from (the same menu the Status and
// Priority pickers use): Up and Down move, Enter picks, Esc leaves it as it was. A pick is one change through clark with one Undo in
// the toast, and the words of the toast follow the owner and due-date ones. clark takes a workstream by its name, a milestone and a
// use case by their ids, and a decision has no workstream and no milestone (it is shown, not changed). The list offers the project's
// open workstreams, the milestones and the use cases that are not archived, and the one the item has now even if it is archived.
import { useRef, useState } from "preact/hooks";
import { data } from "../stores/report.js";
import { changeCell, refresh } from "../stores/changes.js";
import { tableOf } from "./itemEdit.js";
import { MenuPick } from "./cells/MenuPick.jsx";
import { fieldIcon } from "../menuIcons.js";

const NAMES = { workstream: "Workstream", milestone: "Milestone", use_case: "Use case" };
const NONE = { workstream: "No workstream", milestone: "No milestone", use_case: "No use case" };

const withIcon = (field, list) => list.map((c) => ({ ...c, ...fieldIcon(field, c.value === "") }));
const raw = (row) => ((data.value && data.value[tableOf(row)]) || []).find((r) => r.id === row.id) || {};

/** The choices of a field: [{value, text}], the current one first kept even when archived, and a last one that clears it. */
export function choicesOf(field, now) {
  const d = data.value || {};
  if (field === "workstream") {
    const open = (d.workstreams || []).filter((w) => w.name && ((w.status !== "Closed" && !w.archived) || w.name === now)).map((w) => w.name);
    return [...(now && !open.includes(now) ? [now] : []), ...open].map((w) => ({ value: w, text: w })).concat([{ value: "", text: NONE.workstream }]);
  }
  if (field === "milestone") {
    return (d.milestones || []).filter((m) => !m.archived || m.id === now).map((m) => ({ value: m.id, text: m.name })).concat([{ value: "", text: NONE.milestone }]);
  }
  return (d.use_cases || []).filter((u) => !u.archived || u.id === now).map((u) => ({ value: u.id, text: `Use case ${u.ref}` })).concat([{ value: "", text: NONE.use_case }]);
}

export function PeekPick({ row, field }) {
  const [open, setOpen] = useState(false);
  const button = useRef(null);
  const name = NAMES[field], rec = raw(row);
  const now = rec[field] || "";                                        // the stored value: a name, or an id
  const list = withIcon(field, choicesOf(field, now));
  const text = (v) => (list.find((c) => c.value === v) || { text: "" }).text;
  const said = (v) => text(v);
  const shown = row[field === "use_case" ? "uc" : field] || NONE[field];
  const close = (back) => { setOpen(false); if (back && button.current) button.current.focus(); };
  const pick = (value) => {
    close(true);
    if (value === now) return;
    const was = said(now), to = said(value);
    changeCell(tableOf(row), row.id, { [field]: value || null },
      { text: value ? (field === "use_case" ? `${row.id}: use case changed to ${text(value).replace(/^Use case /, "")}.` : `${name} of ${row.id} changed to ${to}.`) : `${name} of ${row.id} cleared.`,
        back: was ? `${name} of ${row.id} is back to ${was}.` : `${name} of ${row.id} is blank again.`, place: "peek" }).then((reply) => (reply ? refresh() : null));
  };
  return (
    <>
      <button type="button" class="pk-pick" ref={button} data-pk-pick={field} aria-haspopup="menu" aria-expanded={open ? "true" : "false"}
        aria-label={`${name} of ${row.id}: ${shown}. Change`} onClick={() => setOpen(!open)}>{shown}</button>
      {open ? <MenuPick anchor={button} label={`${name} of ${row.id}`} current={now} choices={list} onPick={pick} onClose={close} /> : null}
    </>
  );
}
