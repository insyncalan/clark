// The use case summary (#45): a strip (the total, a count for each status, a small meter) and one slim row for each use case:
// reference, title, headline, the status word and the open next steps. The status words sit in one column. A row opens in place
// (an accordion): where it stands, the open next steps as "Owner: what it is", and "See all N work items". Read-only here, and in
// Edit (A-D12, `edit` from edit/UseCaseEdit.jsx) the name, the headline and the status are changed in place and the opened row's
// "Where it stands" is written; linking a work item is another item's. In a published file every use case and linked item on the page
// is one the file kept (publish.select), so the page counts what it holds and a Sensitive or client-off item is never drawn.
import { useState } from "preact/hooks";
import { data, rows, openWork, fromFile } from "../stores/report.js";
import { isOpen } from "../workItems.js";
import { initial, setFilter } from "../filters.js";
import { Icon } from "./Icon.jsx";

export const STATUSES = [["On track", "g"], ["Flag", "a"], ["High risk", "r"]];
const rag = (status) => (STATUSES.find((s) => s[0] === status) || [0, "n"])[1];

// A saved standing as plain text: the page clark serves never draws a saved body as markup (#66 brings the editor).
function plain(html) {
  const doc = new DOMParser().parseFromString(String(html || ""), "text/html");
  return doc.body.textContent.trim();
}

/** The use cases with what is linked to them: [{u, linked, open, steps}] (steps are the open actions). */
export function summary(d, all) {
  const link = {};
  for (const r of [...(d.actions || []), ...(d.raid || []), ...(d.decisions || [])]) if (r.use_case) link[r.id] = r.use_case;
  return (d.use_cases || []).filter((u) => !u.archived).map((u) => {
    const linked = all.filter((r) => link[r.id] === u.id), open = linked.filter(isOpen);
    return { u, linked, open, steps: open.filter((r) => r.kind === "action") };
  });
}

/** The reference as it is read in the small box: references that were merged ("1.3, 1.4" or "1.3 and 1.4") read "1.3 + 1.4". */
export function refText(ref) {
  return String(ref || "").split(/\s*(?:,|;|\+|\band\b)\s*/i).map((x) => x.trim()).filter(Boolean).join(" + ");
}

// A row and "See all" are buttons by role, not <button> elements: a published file has no button but its tabs (and nothing in it edits).
const press = (e, run) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); run(); } };

function Row({ s, shown, toggle, edit }) {
  const { u } = s, id = `uc-${u.id}`, label = u.ref ? `Use case ${u.ref}` : "";
  // "See all N" counts the open items and the link opens the open ones: one list, `s.open`, for both.
  const n = s.open.length, go = () => openWork(setFilter(initial(), "use_case", [label], false));
  const stepsText = s.steps.length === 1 ? "1 next step" : s.steps.length ? `${s.steps.length} next steps` : "No open steps";
  const more = shown ? (
    <div class="ucdetail" id={id}>
      <h3>Where it stands</h3>
      {edit ? <edit.Standing u={u} /> : fromFile.value && u.standing ? <div class="prose" dangerouslySetInnerHTML={{ __html: u.standing }} /> : <p>{plain(u.standing) || "Nothing written yet."}</p>}
      <h3>Next steps</h3>
      {s.steps.length ? <ul class="plain">{s.steps.map((r) => <li key={r.id}><b>{(r.owner || "No owner").trim() || "No owner"}:</b> {r.title}</li>)}</ul> : <p class="muted">No open next steps.</p>}
      {n && label ? <span class="link" role="button" tabIndex={0} data-seeall onClick={go} onKeyDown={(e) => press(e, go)}>{`See all ${n} open work ${n === 1 ? "item" : "items"}`}</span> : n ? <p class="muted">{`${n} open work ${n === 1 ? "item" : "items"}.`}</p> : <p class="muted">No open work items.</p>}
    </div>
  ) : null;
  if (edit) {
    return (
      <li class={`ucrow${shown ? " open" : ""}`} data-uc={u.id}>
        <edit.Bar u={u} shown={shown} id={id} label={label} toggle={toggle} steps={stepsText} />
        {more}
      </li>
    );
  }
  return (
    <li class={`ucrow${shown ? " open" : ""}`} data-uc={u.id}>
      <div class="ucbar" role="button" tabIndex={0} aria-expanded={shown ? "true" : "false"} aria-controls={id} onClick={toggle} onKeyDown={(e) => press(e, toggle)}>
        {u.ref ? <span class="ucref num" data-ref>{refText(u.ref)}</span> : <span></span>}
        <span class="uctitle">{u.title}</span>
        <span class="uchead">{u.headline}</span>
        <span class={`ucword rag-${rag(u.status)}`} data-word><i class="ragdot" aria-hidden="true"></i>{u.status}</span>
        <span class="ucsteps num">{stepsText}</span>
      </div>
      {more}
    </li>
  );
}

export function UseCases({ onExport, edit }) {
  const d = data.value, [open, setOpen] = useState(() => new Set());
  const list = summary(d, rows.value);
  const strip = fromFile.value && d.glance && d.glance.strip;
  const counts = strip ? strip.words : Object.fromEntries(STATUSES.map(([k]) => [k, list.filter((s) => s.u.status === k).length]));
  const total = strip ? strip.total : list.length;
  if (!list.length) return <p class="muted" data-nouc>No use cases yet.</p>;
  const flip = (id) => { const n = new Set(open); if (n.has(id)) n.delete(id); else n.add(id); setOpen(n); };
  return (
    <div class="uc" data-uc-section>
      <div class="ucstrip">
        <b class="uctotal">{total === 1 ? "1 use case" : `${total} use cases`}</b>
        {STATUSES.filter(([k]) => counts[k]).map(([k, c]) => <span key={k} class={`ucn rag-${c}`} data-count={k}><i class="ragdot" aria-hidden="true"></i>{counts[k]} {k}</span>)}
        <span class="meter" role="img" aria-label={STATUSES.filter(([k]) => counts[k]).map(([k]) => `${counts[k]} ${k}`).join(", ")}>
          {STATUSES.flatMap(([k, c]) => Array.from({ length: counts[k] || 0 }, (_, n) => <i key={k + n} class={`m-${c}`}></i>))}
        </span>
        {onExport ? <button type="button" class="bib ucexport" data-uc-export data-tip="Export to Excel (the use cases are one sheet of it)" aria-label="Export to Excel. The use cases are one sheet of the workbook." onClick={onExport}><Icon name="dl" /></button> : null}
      </div>
      <ul class="ucrows plain">{list.map((s) => <Row key={s.u.id} s={s} shown={open.has(s.u.id)} toggle={() => flip(s.u.id)} edit={edit} />)}</ul>
    </div>
  );
}
