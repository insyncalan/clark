// The Use Cases tab of a published file: view only. It reads what the published file holds (data.use_case_pages names,
// for each use case the client may see, the next steps and milestones to show) and draws it. It changes nothing and asks for nothing.
import { data } from "../stores/report.js";

export function UseCasesTab() {
  const d = data.value;
  const pages = d.use_case_pages || [];
  const by = (rows) => Object.fromEntries((rows || []).map((r) => [r.id, r]));
  const cases = by(d.use_cases), steps = by(d.actions), marks = by(d.milestones);
  return (
    <section class="frame ucpage" id="usecases-file">
      <h1>Use cases</h1>
      {pages.length ? pages.map((p) => {
        const u = cases[p.id];
        if (!u) return null;
        const mine = p.next_steps.map((id) => steps[id]).filter(Boolean);
        const ms = p.milestones.map((id) => marks[id]).filter(Boolean);
        return (
          <details class="ucp" key={u.id}>
            <summary><span class="num">{u.ref}</span> <span class="ucp-title">{u.title}</span> <span class="muted">{u.status}</span></summary>
            <div class="ucp-body">
              {u.headline ? <p class="ucp-headline">{u.headline}</p> : null}
              {u.standing ? <div class="prose" dangerouslySetInnerHTML={{ __html: u.standing }} /> : null}
              <h2>Next steps</h2>
              {mine.length ? <ul class="plain">{mine.map((a) => <li key={a.id}>{a.client_message || a.description}</li>)}</ul> : <p class="muted">No next steps are shared for this use case.</p>}
              <h2>Milestones</h2>
              {ms.length ? <ul class="plain">{ms.map((m) => <li key={m.id}>{m.name} <span class="muted">{m.state_word}</span></li>)}</ul> : <p class="muted">No milestones are shared for this use case.</p>}
            </div>
          </details>
        );
      }) : <p class="muted">No use cases are shared in this report.</p>}
    </section>
  );
}
