// The use case summary (#45): a strip (the total, a count for each status, a small meter) and one slim row for each use case:
// reference, title, headline, the status word and the open next steps. The status words sit in one column. A row opens in place
// (an accordion): where it stands, the open next steps as "Owner: what it is", and "See all N work items". Read-only here: changing a
// status, linking a work item and editing the text are other items'. In a published file every use case and linked item on the page
// is one the file kept (publish.select), so the page counts what it holds and a Sensitive or client-off item is never drawn.
import { useEffect, useState } from "preact/hooks";
import { data, rows, openWork, fromFile, show, project, mode } from "../stores/report.js";
import { format } from "../router.js";
import { isOn, liveOf } from "../logic/useCasesList.js";
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

/** The use cases on the dashboard (the eye is on; a published file only holds those) with what is linked to them: [{u, linked, open, steps}] (steps are the open actions). The ones not on it are on the Use cases page. */
export function summary(d, all) {
  const link = {};
  for (const r of [...(d.actions || []), ...(d.raid || []), ...(d.decisions || [])]) if (r.use_case) link[r.id] = r.use_case;
  return liveOf(d).filter(isOn).map((u) => {
    const linked = all.filter((r) => link[r.id] === u.id), open = linked.filter(isOpen);
    return { u, linked, open, steps: open.filter((r) => r.kind === "action") };
  });
}

/** The reference as it is read in the small box: references that were merged ("1.3, 1.4" or "1.3 and 1.4") read "1.3 + 1.4". */
export function refText(ref) {
  return String(ref || "").split(/\s*(?:,|;|\+|\band\b)\s*/i).map((x) => x.trim()).filter(Boolean).join(" + ");
}

// A row and "See all" are buttons by role, not <button> elements: a published file has no button but its tabs (and nothing in it edits).
// In Edit a row holds its own controls (the status button, the headline's box): a press on one of them is theirs, not the row's.
const mine = (e) => e.target !== e.currentTarget && !!e.target.closest("textarea, button, [role=menu], .dd");
const press = (e, run) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); run(); } };

function Row({ s, shown, toggle, ed }) {
  const { u } = s, id = `uc-${u.id}`, label = u.ref ? `Use case ${u.ref}` : "";
  // "See all N" counts the open items and the link opens the open ones: one list, `s.open`, for both.
  const n = s.open.length, go = () => openWork(setFilter(initial(), "use_case", [label], false));
  return (
    <li class={`ucrow${shown ? " open" : ""}${ed ? " ucrow-ed" : ""}`} data-uc={u.id}>
      <div class="ucbar" role="button" tabIndex={0} aria-expanded={shown ? "true" : "false"} aria-controls={id}
        onClick={(e) => { if (ed && mine(e)) return; toggle(); }} onKeyDown={(e) => { if (ed && e.target !== e.currentTarget) return; press(e, toggle); }}>
        {ed ? <ed.Eye u={u} /> : null}
        {u.ref ? <span class="ucref num" data-ref>{refText(u.ref)}</span> : <span></span>}
        <span class="uctitle">{u.title}</span>
        {ed ? <ed.Headline u={u} /> : <span class="uchead">{u.headline}</span>}
        {ed ? <ed.Status u={u} /> : <span class={`ucword rag-${rag(u.status)}`} data-word><i class="ragdot" aria-hidden="true"></i>{u.status}</span>}
        <span class="ucsteps num">{s.steps.length === 1 ? "1 next step" : s.steps.length ? `${s.steps.length} next steps` : "No open steps"}</span>
      </div>
      {shown ? (
        <div class="ucdetail" id={id}>
          {ed ? <ed.Name u={u} /> : null}
          <h3>Where it stands</h3>
          {ed ? <ed.Standing u={u} /> : fromFile.value && u.standing ? <div class="prose" dangerouslySetInnerHTML={{ __html: u.standing }} /> : <p>{plain(u.standing) || "Nothing written yet."}</p>}
          <h3>Next steps</h3>
          {s.steps.length ? <ul class="plain">{s.steps.map((r) => <li key={r.id}><b>{(r.owner || "No owner").trim() || "No owner"}:</b> {r.title}</li>)}</ul> : <p class="muted">No open next steps.</p>}
          {ed ? <><ed.NextStep u={u} /><ed.LinkButton u={u} /></> : null}
          {n && label ? <span class="link" role="button" tabIndex={0} data-seeall onClick={go} onKeyDown={(e) => press(e, go)}>{`See all ${n} open work ${n === 1 ? "item" : "items"}`}</span> : n ? <p class="muted">{`${n} open work ${n === 1 ? "item" : "items"}.`}</p> : <p class="muted">No open work items.</p>}
        </div>
      ) : null}
    </li>
  );
}

// "N more on the Use cases page": the editor's line under the summary when some use cases are not on the dashboard. A published file holds only
// the ones that were, so it has none.
function More({ n }) {
  if (!n || fromFile.value) return null;
  const go = (e) => { e.preventDefault(); show("usecases"); };
  return <p class="ucmore"><a href={format({ view: "usecases", project: project.value })} data-uc-more onClick={go}>{n === 1 ? "1 more on the Use cases page" : `${n} more on the Use cases page`}</a></p>;
}

export function UseCases({ onExport, tools }) {
  const d = data.value, [open, setOpen] = useState(() => new Set());
  const ed = tools && tools.ucEdit && !fromFile.value && mode.value === "edit" ? tools.ucEdit : null;       // Edit's parts (#455, #485): only in Edit; View and a published file have none
  const list = summary(d, rows.value), off = fromFile.value ? 0 : liveOf(d).filter((u) => !isOn(u)).length;
  const fresh = ed ? ed.added.value : "";                                           // a use case just added opens its row
  useEffect(() => {
    if (ed && fresh && list.some((s) => s.u.id === fresh)) { setOpen(new Set([...open, fresh])); ed.added.value = ""; }
  }, [fresh, list.length]);   // eslint-disable-line react-hooks/exhaustive-deps
  const strip = fromFile.value && d.glance && d.glance.strip;
  const counts = strip ? strip.words : Object.fromEntries(STATUSES.map(([k]) => [k, list.filter((s) => s.u.status === k).length]));
  const total = strip ? strip.total : list.length;
  if (!list.length) return <><p class="muted" data-nouc>{off ? "No use cases are on the dashboard." : "No use cases yet."}</p>{ed ? <ed.FromRecord n={off} /> : null}<More n={off} /></>;
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
      <ul class="ucrows plain">{list.map((s) => <Row key={s.u.id} s={s} shown={open.has(s.u.id)} toggle={() => flip(s.u.id)} ed={ed} />)}</ul>
      {ed ? <ed.FromRecord n={off} /> : null}
      <More n={off} />
    </div>
  );
}
