// The one layout of a use case's own page (row 1479, the 20-11 decision: the published page is the editor's page with the controls off, so the two cannot drift).
// UseCaseDetail (the editor's page) and UseCaseFilePage (a published file's) both draw it: the crumb, the heading and its status line, the cards and their
// order, the work item rows and the milestone rows are written HERE, once. A page gives it the facts and, where a person can change something, the controls
// as slots; a page with no slot draws none. `p` is the class prefix each page keeps ("ucd" in the editor, "ucf" in a file), so the two themes' rules still apply.
import { openWork, openPeek } from "../stores/report.js";
import { isOpen, dueCell, ownerOf, todayIso, plural, showDate } from "../workItems.js";
import { initial, setFilter } from "../filters.js";
import { milestoneRows } from "../logic/milestones.js";
import { MsMark } from "./MsMark.jsx";
import { ItemIcon, iconWords, TipParts } from "./ItemRows.jsx";      // row 1145: the coloured pill with words is the tinted letter icon alone (row 1021's)
import { clientPill } from "../logic/sectionRows.js";

export const rag = (status) => ({ "On track": "g", Flag: "a", "High risk": "r", Done: "n" })[status] || "n";

export function Crumb({ p, href, label, backRef, onBack }) {
  return (
    <nav class={`${p}-crumb`} aria-label="You are here">
      <a href={href} ref={backRef} data-uc-back onClick={onBack}>Use cases</a><span aria-hidden="true"> › </span><span>{label}</span>
    </nav>
  );
}

// props: p, u (the use case), name (its reference words), work (its work item rows), ms ([{m, how, attr?, side?}]), headRef, root (extra attributes of the page's div),
// crumb (the Crumb element), ro (read only: no hint), title and headline (the nodes the page draws for them), sub (the status line's nodes before the counts),
// acts (the controls beside the title), top (a note between the head and the cards), std (the Where it stands body) and stdHint, titleOfRow, noWork, noMs,
// owner (the Owner value node, none when there is no Owner row), rows (further Details rows), addWork and addMs (the add controls), msNote, after (the cards after Milestones).
export function UseCaseLayout({ p, u, name, work, ms, headRef, root, crumb, ro, title, headline, sub, acts, top, std, stdHint, titleOfRow, noWork, noMs, owner, rows, addWork, addMs, msNote, after }) {
  const open = work.filter(isOpen), label = u.ref ? `Use case ${u.ref}` : "";
  const counts = work.length ? `${open.length} of ${plural(work.length, "work item")} open` : "No work items";
  return (
    <div class={p} {...{ [`data-${p}`]: true }} data-uc-id={u.id} {...root}>
      {crumb}
      <div class={`${p}-head`}>
        <div class={`${p}-titles`}>
          <h1 class={`${p}-h`} ref={headRef} tabIndex={-1}><span class={`${p}-ref`}>{name} ·</span>{title}</h1>
          <p class={`${p}-sub`}>
            {sub && sub.before}
            <span class={`${p}-word rag-${rag(u.status)}`} data-word><i class="ragdot" aria-hidden="true"></i>{u.status}</span>
            {sub && sub.chip}
            <span>{counts} · {plural(ms.length, "milestone")}</span>
          </p>
          <p class={`${p}-line`}>{headline}</p>
        </div>
        {acts || null}
      </div>
      {top || null}
      <div class={`${p}-grid`}>
        <div class={`${p}-main`}>
          <section class={`${p}-card`} aria-labelledby={`${p}-h-std`}>
            <h2 id={`${p}-h-std`} class={`${p}-ch`}><span>Where it stands</span>{stdHint || null}</h2>
            {std}
          </section>
          <section class={`${p}-card`} aria-labelledby={`${p}-h-work`}>
            <h2 id={`${p}-h-work`} class={`${p}-ch`}><span>Work items</span>
              {open.length && label ? <button type="button" class="link" data-open-all onClick={() => openWork(setFilter(initial(), "use_case", [label], false))}>{`Open all ${open.length} in Work items`}</button> : null}
            </h2>
            {work.length ? (
              <ul class={`${p}-items plain`}>
                {work.map((r) => {
                  const due = r.kind === "decision" || r.kind === "action" ? dueCell(r, todayIso()).date : "", who = ownerOf(r.owner).text, pill = clientPill(r, todayIso()), say = iconWords(r, pill, todayIso());
                  const extra = [who !== "—" ? who : "", due && due !== "—" ? `Due ${due}` : r.kind === "action" ? "No due date" : ""].filter(Boolean).join(" · ") || "No owner";
                  const text = titleOfRow ? titleOfRow(r) : r.title;
                  return (
                    <li key={r.id}>
                      <button type="button" class={`${p}-item`} data-item={r.id} data-tip={say.tip} onClick={() => openPeek(r.id, "item")}>
                        <ItemIcon row={r} pill={pill} today={todayIso()} plain /><TipParts say={say} /><span class="sr">{say.name}</span>
                        <span class={`${p}-id num`}>{r.id}</span><span class={`${p}-t`} title={titleOfRow ? text : undefined}>{text}</span><span class={`${p}-x`}>{extra}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            ) : <p class="muted" data-no-work>{noWork}</p>}
            {addWork || null}
          </section>
        </div>
        <div class={`${p}-side`}>
          <section class={`${p}-card`} aria-labelledby={`${p}-h-det`} {...{ [`data-${p}-details`]: true }}>
            <h2 id={`${p}-h-det`} class={`${p}-ch`}>Details</h2>
            <dl class={`${p}-kv`}>
              {owner ? <><dt>Owner</dt><dd data-uc-owner>{owner}</dd></> : null}
              {rows}
            </dl>
          </section>
          <section class={`${p}-card`} aria-labelledby={`${p}-h-ms`}>
            <h2 id={`${p}-h-ms`} class={`${p}-ch`}>Milestones</h2>
            {ms.length ? <ul class={`${p}-ms plain`}>{ms.map((k) => {
                const m = k.m, st = milestoneRows([m], todayIso(), false)[0];                 // the same state word and mark as the Milestones page (row 860)
                return <li key={m.id} data-ms={m.id} data-how={k.attr}><button type="button" class={`link ${p}-msname`} data-ms-open={m.id} onClick={() => openPeek(m.id, "milestone")}>{m.name}</button>
                  <span class={`${p}-msx`}>{st ? <span class={`mst c-${st.colour}`} data-ms-state><MsMark name={st.mark} />{st.word}</span> : null}<span class="muted num">{showDate(m.status === "Done" && m.actual_date ? m.actual_date : m.baseline_date || m.forecast_date)}</span>{k.side || null}</span>
                  <span class={`muted ${p}-mshow`} data-ms-how>{k.how}</span></li>;
              })}</ul>
              : <p class="muted">{noMs}</p>}
            {ms.length ? msNote || null : null}
            {addMs || null}
          </section>
          {after || null}
        </div>
      </div>
    </div>
  );
}
