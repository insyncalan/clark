// The Use Cases tab of a published file: view only. It reads what the published file holds (data.use_case_pages names,
// for each use case the client may see, the next steps and milestones to show) and draws it. It changes nothing and asks for nothing.
// Row 1114: the list as the full app's Use cases page draws it, read only: the tabs with their counts (no "On the dashboard" tab, every
// published row is on it), Sort by and Group by menus (item 1149: the rows are the dashboard summary's) with groups that shut, the count line and the filtered-empty state.
// A published row carries no work item count, so there is no Work items heading to sort by. The choice lives for the visit only.
import { signal } from "@preact/signals";
import { data, uc, project } from "../stores/report.js";
import { ucFor, ucKey, refBox, stepsWord, listOf, pickRows, groupsOf, groupLabel, TABS, GROUPS, SORTS, FIRST } from "../logic/useCasesList.js";
import { commitWords } from "../logic/commitment.js";
import { plural } from "../workItems.js";
import { UseCaseFilePage } from "./UseCaseFilePage.jsx";
import { printing } from "../stores/print.js";
import { CommitChip } from "./CommitChip.jsx";
import { Menu } from "./Menu.jsx";
import { Icon } from "./Icon.jsx";
import { groupIcon, sortIcon } from "../menuIcons.js";

const RAGS = { "On track": "g", Flag: "a", "High risk": "r", Done: "n" };
const view = signal({ ...FIRST });
const shut = signal(new Set());
const TABS_HERE = TABS.filter(([id]) => id !== "on");
const GROUPS_HERE = GROUPS.filter(([id]) => id !== "on");
const SORTS_HERE = SORTS.filter(([id]) => id !== "open");
const set = (patch) => { view.value = { ...view.value, ...patch }; };

function Item({ p, u, steps, marks }) {
  const d = data.value;
  const mine = p.next_steps.map((id) => steps[id]).filter(Boolean);
  const ms = p.milestones.map((id) => marks[id]).filter(Boolean);
  return (
    <details class="ucp" open={printing.value}>
      <summary class="ucp-bar">{/* item 1149: the dashboard summary's row: reference box, title, where it stands, status word with the commitment, the shared next steps */}
        {u.ref ? <span class="ucref num" data-ref>{refBox(u.ref)}</span> : <span></span>}
        <span class="uctitle ucp-title">{u.title}</span>
        <span class="uchead ucp-headline">{u.headline}</span>
        <span class="ucstc"><span class={`ucword rag-${(RAGS[u.status] || "n")}`} data-word><i class="ragdot" aria-hidden="true"></i>{u.status}</span><CommitChip u={u} /></span>
        <span class="ucsteps num">{stepsWord(mine.length)}</span>
      </summary>
      <div class="ucp-body">
        <p><a class="link" data-uc-page href={`#usecases&p=${project.value}&uc=${encodeURIComponent(ucKey(d, u))}`}>Open the page</a></p>
        {u.standing ? <div class="prose" dangerouslySetInnerHTML={{ __html: u.standing }} /> : null}
        <h2>Next steps</h2>
        {mine.length ? <ul class="plain">{mine.map((a) => <li key={a.id}>{a.client_message || a.description}</li>)}</ul> : <p class="muted ucp-none">No next steps are shared for this use case.</p>}
        <h2>Milestones</h2>
        {ms.length ? <ul class="plain">{ms.map((m) => <li key={m.id}>{m.name} <span class="muted">{m.state_word}</span></li>)}</ul> : <p class="muted ucp-none">No milestones are shared for this use case.</p>}
      </div>
    </details>
  );
}

function UseCasesList({ d, pages, cases, steps, marks }) {
  const paper = printing.value;                                          // a print shows every use case: no tab chosen, no group shut, no tools
  const f = paper ? { ...view.value, tab: "all" } : view.value, ids = new Set(pages.map((p) => p.id));
  const rows = listOf(d, []).filter((r) => ids.has(r.id));
  const pageOf = Object.fromEntries(pages.map((p) => [p.id, p]));
  const kept = pickRows(rows, f);
  const groups = groupsOf(kept, f.group, commitWords(d)).map((g) => ({ ...g, shut: !paper && shut.value.has(`${f.group}|${g.key}`) }));
  const toggle = (g) => { const next = new Set(shut.value), k = `${f.group}|${g.key}`; if (next.has(k)) next.delete(k); else next.add(k); shut.value = next; };
  const items = (rs) => rs.map((r) => <Item key={r.id} p={pageOf[r.id]} u={cases[r.id] || r.u} steps={steps} marks={marks} />);
  return (
    <>
      {paper ? null : <div class="fviews ucp-views">
        <div class="fvrow">
          <div class="vtabs" role="group" aria-label="Use case views">
            {TABS_HERE.map(([id, name]) => (
              <button type="button" key={id} class="vtab" data-tab={id} aria-pressed={f.tab === id ? "true" : "false"} onClick={() => set({ tab: id })}><span>{name}</span><em class="num">{pickRows(rows, { ...f, tab: id }).length}</em></button>
            ))}
          </div>
          <span class="ucp-tools">
            <Menu label="Sort by" ariaLabel={`Sort by: ${(SORTS_HERE.find(([k]) => k === f.sort) || SORTS_HERE[0])[1]}`} id="ucp-sort" btnCls="btn sm" menuLabel="Sort by" items={SORTS_HERE.map(([k, w]) => ({ id: k, name: w, icon: sortIcon(k), checked: f.sort === k }))} onPick={(k) => set({ sort: k })} />
            <Menu label="Group by" ariaLabel={`Group by: ${groupLabel(f.group)}`} id="ucp-group" btnCls="btn sm" menuLabel="Group by" items={GROUPS_HERE.map(([k, w]) => ({ id: k, name: w, icon: groupIcon(k), checked: f.group === k }))} onPick={(k) => set({ group: k })} />
          </span>
        </div>
      </div>}
      {!kept.length ? (
        <div class="ucp-empty" data-empty>
          <p class="muted">No use cases match these filters.</p>
          <button type="button" class="btn" data-clear-all onClick={() => set({ tab: "all" })}>Clear the filters</button>
        </div>
      ) : f.group === "nothing" ? items(kept) : groups.map((g) => (
        <div class="wgroup ucp-group" key={g.key} data-group={g.key}>
          <div class="ucp-grp">
            <button type="button" class="grp-b" aria-expanded={g.shut ? "false" : "true"} onClick={() => toggle(g)}>
              <Icon name="chevdown" cls={g.shut ? "turn" : ""} /><span class="gl">{g.label}</span><span class="gc num">{plural(g.rows.length, "use case")}</span>
            </button>
          </div>
          {g.shut ? null : items(g.rows)}
        </div>
      ))}
      {paper ? null : <p class="ucp-count num" id="ucp-count" role="status">{plural(kept.length, "use case")}</p>}
    </>
  );
}

export function UseCasesTab() {
  const d = data.value;
  const pages = d.use_case_pages || [];
  const by = (rows) => Object.fromEntries((rows || []).map((r) => [r.id, r]));
  const cases = by(d.use_cases), steps = by(d.actions), marks = by(d.milestones);
  const open = uc.value && !printing.value ? ucFor(d, uc.value) : null;     // paper lists every use case; // row 1111: one use case page, read only
  if (open && pages.some((p) => p.id === open.id)) return <UseCaseFilePage id={open.id} />;
  return (
    <section class="frame ucpage" id="usecases-file">
      <p class="crumbs">{d.project.name}</p>
      <h1>Use cases</h1>
      {pages.length ? <UseCasesList d={d} pages={pages.filter((p) => cases[p.id])} cases={cases} steps={steps} marks={marks} /> : <p class="muted">No use cases are shared in this report.</p>}
    </section>
  );
}
