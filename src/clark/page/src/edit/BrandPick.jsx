// Settings › Brands › "Brand for this project" (item 944): Generic or one of the added brands, the open project's own (projects.brand).
// A choice is one change with Undo and a line in the history (field "brand"). When the saved brand is no longer added, the select shows
// Generic and the note says why; the server already keeps that project's output on Generic. Edit parts only.
import { useState } from "preact/hooks";
import { data } from "../stores/report.js";
import { change } from "../stores/changes.js";

export const GONE = "The brand chosen for this project is no longer available, so this project uses Generic.";

/** The select's value and whether the saved brand has gone: [value, gone]. */
export function pickState(saved, brands) {
  if (typeof saved !== "string" || saved === "" || saved === "generic") return ["generic", false];
  return brands.some((b) => b.id === saved) ? [saved, false] : ["generic", true];
}

const saveReal = (id, name) => change({ kind: "projects", op: "update", changes: { brand: id }, place: "menu" }, `Brand: ${name}.`);

export function BrandPick({ brands, project = undefined, save = saveReal }) {
  const [draft, setDraft] = useState(null);      // what the arrows are on; nothing is saved until Enter or Save
  const p = project !== undefined ? project : data.value && data.value.project;
  if (!p) return null;          // no project open: nothing to choose for
  const [value, gone] = pickState(p.brand, brands);
  const shown = draft === null ? value : draft;
  const commit = async () => {
    const id = shown;
    if (id === value) return;
    const b = brands.find((x) => x.id === id);
    await save(id, id === "generic" ? "Generic" : (b ? b.name : id));
    setDraft(null);      // the select shows what clark kept (a refused change leaves the old brand)
  };
  const key = (e) => {
    if (e.key === "Escape" && draft !== null) { e.preventDefault(); setDraft(null); }
    else if (e.key === "Enter") { e.preventDefault(); commit(); }
  };
  return (
    <div class="fld" data-brand-pick>
      <label for="brand-pick">Brand for this project</label>
      <select id="brand-pick" value={shown} aria-describedby="brand-pick-line" onChange={(e) => setDraft(e.currentTarget.value)} onKeyDown={key}>
        <option value="generic">Generic</option>
        {brands.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
      </select>
      <button type="button" class="btn" data-brand-save disabled={shown === value} onClick={commit}>Save</button>
      <small id="brand-pick-line">Enter or Save keeps the choice, Esc puts the saved brand back. The published page, Excel, Word and PDF of this project use it.</small>
      <p class="muted" role="status" data-brand-gone>{gone ? GONE : ""}</p>
    </div>
  );
}
