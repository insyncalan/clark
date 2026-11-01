// The Use Cases tab of a published file: view only. It reads what the published file holds (data.use_case_pages names,
// for each use case the client may see, the next steps and milestones to show) and draws it. It changes nothing and asks for nothing.
import { data } from "../stores/report.js";
import { showDate } from "../workItems.js";
import { avatarOf, wordingOf } from "../logic/useCaseSteps.js";

export function UseCasesTab() {
  const d = data.value;
  const pages = d.use_case_pages || [];
  const by = (rows) => Object.fromEntries((rows || []).map((r) => [r.id, r]));
  const cases = by(d.use_cases), steps = by(d.actions), marks = by(d.milestones);
  return (
    <section class="frame ucpage" id="usecases-file">
      <h1>Use Cases</h1>
      {pages.length ? pages.map((p) => {
        const u = cases[p.id];
        if (!u) return null;
        // the client wording, in the order of the date it is due; a step with no client wording is left out, never drawn with the action's own text (the prototype's usecases.js)
        const mine = p.next_steps.map((id) => steps[id]).filter((a) => a && wordingOf(a)).sort((a, b) => (a.due_date || "9").localeCompare(b.due_date || "9"));
        const ms = p.milestones.map((id) => marks[id]).filter(Boolean);
        return (
          <details class="ucp" key={u.id}>
            <summary><span class="num">{u.ref}</span> <span class="ucp-title">{u.title}</span> <span class="muted">{u.status}</span></summary>
            <div class="ucp-body">
              {u.headline ? <p class="ucp-headline">{u.headline}</p> : null}
              {u.standing ? <div class="prose" dangerouslySetInnerHTML={{ __html: u.standing }} /> : null}
              <h2>{`Next steps \u00b7 ${mine.length}`}</h2>
              {mine.length ? (
                <ul class="plain ucp-steps">{mine.map((a) => (
                  <li key={a.id} data-step={a.id}>
                    <span class="av" aria-hidden="true">{avatarOf(a.owner)}</span>
                    <span class="ucp-sm"><b>{(a.owner || "").trim() || "No owner"}:</b> {wordingOf(a)} <span class="ucp-sx"><span class="num">{a.id}</span>{a.due_date ? ` \u00b7 due ${showDate(a.due_date)}` : ""}</span></span>
                  </li>
                ))}</ul>
              ) : <p class="muted">No next steps to show.</p>}
              <h2>Milestones</h2>
              {ms.length ? <ul class="plain">{ms.map((m) => <li key={m.id}>{m.name} <span class="muted">{m.state_word}</span></li>)}</ul> : <p class="muted">No milestones are shared for this use case.</p>}
            </div>
          </details>
        );
      }) : <p class="muted">No use cases are shared in this report.</p>}
    </section>
  );
}
