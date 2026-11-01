// The use case summary's Edit parts (A-D12), handed to UseCases through `tools`: the name and the headline edited in place, a
// status button on each row, and the opened row's "Where it stands" text. A published file never has this file (edit/index.js).
import { useLayoutEffect, useRef, useState } from "preact/hooks";
import { MenuPick } from "./cells/MenuPick.jsx";
import { RichField } from "./RichField.jsx";
import { Icon } from "../components/Icon.jsx";
import { refText } from "../components/UseCases.jsx";
import { saveLine, saveStatus, saveStanding, called } from "./useCaseEdit.js";

const read = (el) => el.value;
const show = (el, text) => { el.value = text; };

// The name or the headline, edited in place as plain text, in an ordinary one-line text field: saved when the field is left or on Enter, Esc puts the old text back.
export function UcText({ u, field, label }) {
  const ref = useRef(null), now = useRef(u[field] || ""), cancelled = useRef(false);
  now.current = u[field] || "";
  useLayoutEffect(() => { if (ref.current && read(ref.current) !== now.current && document.activeElement !== ref.current) show(ref.current, now.current); }, [u[field]]);
  useLayoutEffect(() => { show(ref.current, now.current); }, []);
  const commit = () => {
    const el = ref.current;
    if (cancelled.current) { cancelled.current = false; return; }
    saveLine(u, field, read(el)).then((reply) => { if (!reply && el.isConnected) show(el, now.current); });
  };
  const keys = (e) => {
    if (e.isComposing) return;
    if (e.key === "Enter") { e.preventDefault(); ref.current.blur(); }
    else if (e.key === "Escape") { e.preventDefault(); cancelled.current = true; show(ref.current, now.current); ref.current.blur(); }
  };
  const name = `${label} of ${called(u)}`;
  const common = { ref, class: `ucedit-text uc${field === "title" ? "title" : "head"}`, "data-uc-field": field, "data-edit-only": "", "aria-label": name, onBlur: commit, onKeyDown: keys, spellcheck: false };
  return <input {...common} type="text" placeholder={field === "headline" ? "Add a headline" : undefined} title={u[field] || undefined} />;
}

const STATUSES = [["On track", "g"], ["Flag", "a"], ["High risk", "r"]];

// The status word as a button that opens the three statuses.
export function UcStatus({ u }) {
  const [open, setOpen] = useState(false), btn = useRef(null);
  const rag = (STATUSES.find((s) => s[0] === u.status) || [0, "n"])[1];
  const close = (back) => { setOpen(false); if (back && btn.current) btn.current.focus(); };
  return (
    <span class="ucstatus-wrap">
      <button type="button" ref={btn} class={`ucword ucstatus rag-${rag}`} data-uc-status data-edit-only aria-haspopup="menu" aria-expanded={open ? "true" : "false"}
        aria-label={`Status: ${u.status}. Change`} onClick={() => setOpen(!open)}>
        <i class="ragdot" aria-hidden="true"></i>{u.status}<Icon name="chevdown" />
      </button>
      {open ? <MenuPick anchor={btn} label={`Status of ${called(u)}`} current={u.status} choices={STATUSES.map(([k]) => ({ value: k, text: k }))}
        onPick={(v) => { close(true); saveStatus(u, v); }} onClose={close} /> : null}
    </span>
  );
}

// The opened row's "Where it stands", written in the one rich editor.
export function UcStanding({ u }) {
  return <RichField field="standing" id={u.id} value={u.standing} label={`Where it stands for ${called(u)}`} empty="Click to say where it stands." save={(html) => saveStanding(u, html)} />;
}

// In Edit the bar is not one button: the name, headline and status are controls of their own, so the reference box opens the row.
export function UcBar({ u, shown, id, label, toggle, steps }) {
  const name = u.title || label || "this use case";
  return (
    <div class="ucbar ucbar-edit">
      <button type="button" class="ucref ucopen num" data-ref data-uc-open aria-expanded={shown ? "true" : "false"} aria-controls={id} aria-label={`${shown ? "Close" : "Open"} ${name}`} onClick={toggle}>{refText(u.ref) || (shown ? "Close" : "Open")}</button>
      <UcText u={u} field="title" label="Name" />
      <UcText u={u} field="headline" label="Headline" />
      <UcStatus u={u} />
      <span class="ucsteps num">{steps}</span>
    </div>
  );
}

export const USE_CASE_EDIT = { Bar: UcBar, Text: UcText, Status: UcStatus, Standing: UcStanding };
