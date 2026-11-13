// One use case's own page in a published file (row 1111): the same layout and classes as the page the editor has (UseCaseDetail), read only.
// It reads what the file holds (data.use_case_pages names, for each use case the client may see, the next steps and milestones to show),
// draws no control and no History, and its Details card shows only the fields the file holds (status, commitment), and asks for nothing. A work item opens the file's read only peek; "Open all" opens the file's Work items.
import { useEffect, useRef } from "preact/hooks";
import { data, rows, project, openWork, openPeek } from "../stores/report.js";
import { isOpen, pillOf, dueCell, ownerOf, todayIso, plural, showDate } from "../workItems.js";
import { initial, setFilter } from "../filters.js";
import { refOf } from "../logic/useCasesList.js";
import { milestoneRows } from "../logic/milestones.js";
import { MsMark } from "./MsMark.jsx";
import { toneOf } from "./ItemRows.jsx";
import { commitWord } from "../logic/commitment.js";
import { CommitChip } from "./CommitChip.jsx";

const rag = (status) => ({ "On track": "g", Flag: "a", "High risk": "r", Done: "n" })[status] || "n";

export function UseCaseFilePage({ id }) {
  const d = data.value, head = useRef(null);
  const u = d ? (d.use_cases || []).find((x) => x.id === id) || null : null;
  // The heading takes the focus when the page is drawn (and again when another use case is opened), never on a later redraw of the same one.
  useEffect(() => { if (head.current) head.current.focus({ preventScroll: true }); }, [id, !!d]);
  if (!d) return null;
  const listAt = `#usecases&p=${project.value}`;
  const crumb = (label) => <nav class="ucf-crumb" aria-label="You are here"><a href={listAt} data-uc-back>Use cases</a><span aria-hidden="true"> › </span><span>{label}</span></nav>;
  if (!u) return <div class="ucf" data-ucf data-missing>{crumb("Use case")}<h1 ref={head} tabIndex={-1} class="ucf-h">That use case isn't in this report</h1><p><a href={listAt}>Go back to the use cases</a>.</p></div>;
  const page = (d.use_case_pages || []).find((x) => x.id === u.id) || { next_steps: [], milestones: [] };
  const work = page.next_steps.map((n) => rows.value.find((r) => r.id === n)).filter(Boolean);
  const ms = page.milestones.map((n) => (d.milestones || []).find((m) => m.id === n)).filter(Boolean);
  const open = work.filter(isOpen), label = u.ref ? `Use case ${u.ref}` : "";
  const name = refOf(u) || "Use case";
  const sub = work.length ? `${open.length} of ${plural(work.length, "work item")} open` : "No work items";
  const std = u.standing || "";                    // cleaned at publish (publish.select), as the Use cases tab draws it
  return (
    <div class="ucf" data-ucf data-uc-id={u.id}>
      {crumb(name)}
      <div class="ucf-head">
        <div class="ucf-titles">
          <h1 ref={head} tabIndex={-1} class="ucf-h"><span class="ucf-ref">{name} ·</span><span class="ucf-name ucf-ro" data-ucf-field="title">{u.title}</span></h1>
          <p class="ucf-sub">
            <span class={`ucf-word rag-${rag(u.status)}`} data-word><i class="ragdot" aria-hidden="true"></i>{u.status}</span>
            <CommitChip u={u} />
            <span>{sub} · {plural(ms.length, "milestone")}</span>
          </p>
          <p class="ucf-line"><span class="ucf-headline ucf-ro" data-ucf-field="headline">{u.headline || <span class="muted">No headline yet</span>}</span></p>
        </div>
      </div>
      <div class="ucf-grid">
        <div class="ucf-main">
          <section class="ucf-card" aria-labelledby="ucf-h-std">
            <h2 id="ucf-h-std" class="ucf-ch"><span>Where it stands</span></h2>
            {std ? <div class="prose ucf-std" dangerouslySetInnerHTML={{ __html: std }} /> : <p class="muted">Not written yet.</p>}
          </section>
          <section class="ucf-card" aria-labelledby="ucf-h-work">
            <h2 id="ucf-h-work" class="ucf-ch"><span>Work items</span>
              {open.length && label ? <button type="button" class="link" data-open-all onClick={() => openWork(setFilter(initial(), "use_case", [label], false))}>{`Open all ${open.length} in Work items`}</button> : null}
            </h2>
            {work.length ? (
              <ul class="ucf-items plain">
                {work.map((r) => {
                  const due = r.kind === "decision" || r.kind === "action" ? dueCell(r, todayIso()).date : "", who = ownerOf(r.owner).text, pill = pillOf(r, todayIso());
                  const extra = [who !== "—" ? who : "", due && due !== "—" ? `Due ${due}` : r.kind === "action" ? "No due date" : ""].filter(Boolean).join(" · ") || "No owner";
                  return (
                    <li key={r.id}>
                      <button type="button" class="ucf-item" data-item={r.id} onClick={() => openPeek(r.id, "item")}>
                        <span class="ucf-id num">{r.id}</span><span class="ucf-t" title={r.client_message || r.title}>{r.client_message || r.title}</span>
                        <span class={`pill ${toneOf(r, pill)}`}>{pill.text}</span><span class="ucf-x">{extra}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            ) : <p class="muted" data-no-work>No work items are shared for this use case.</p>}
          </section>
        </div>
        <div class="ucf-side">
          <section class="ucf-card" aria-labelledby="ucf-h-det" data-ucf-details>
            <h2 id="ucf-h-det" class="ucf-ch">Details</h2>
            <dl class="ucf-kv">
              <dt>Status</dt><dd data-det-status>{u.status}</dd>
              {commitWord(u) ? <><dt>Commitment</dt><dd data-det-commit>{commitWord(u)}</dd></> : null}
            </dl>
          </section>
          <section class="ucf-card" aria-labelledby="ucf-h-ms">
            <h2 id="ucf-h-ms" class="ucf-ch">Milestones</h2>
            {ms.length ? <ul class="ucf-ms plain">{ms.map((m) => {
                const st = milestoneRows([m], todayIso(), false)[0];
                return <li key={m.id} data-ms={m.id}><button type="button" class="link ucf-msname" data-ms-open={m.id} onClick={() => openPeek(m.id, "milestone")}>{m.name}</button>
                  <span class="ucf-msx">{st ? <span class={`mst c-${st.colour}`} data-ms-state><MsMark name={st.mark} />{st.word}</span> : null}<span class="muted num">{showDate(m.status === "Done" && m.actual_date ? m.actual_date : m.baseline_date || m.forecast_date)}</span></span></li>;
              })}</ul>
              : <p class="muted">No milestones are shared for this use case.</p>}
          </section>
        </div>
      </div>
    </div>
  );
}
