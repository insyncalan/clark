// Settings › Projects: Name, Code, Client, Workstreams and Items for each project, with Open, Archive and Restore, and Show archived.
// Edit's page only: a published file has no Settings. Archive and Restore are one step each with Undo, through the routes that
// exist (projectsApi.js); a project's data is never deleted. Adding and editing a project are not here: the server has no route for
// them yet. `api` is a seam for the tests; the page passes none.
import { useEffect, useState } from "preact/hooks";
import { project as openCode, openProjectAt } from "../stores/report.js";
import { say, undone, enqueue } from "../stores/changes.js";
import { listProjects, readProject, sendProjectArchive } from "./projectsApi.js";
import * as L from "../logic/projectsTable.js";

const REAL = { list: listProjects, read: readProject, archive: sendProjectArchive };

export function Projects({ api = REAL }) {
  const [state, setState] = useState({ phase: "loading", live: [], gone: [] });
  const [showGone, setShowGone] = useState(false);
  const [busy, setBusy] = useState("");

  async function load() {
    const [live, gone] = await Promise.all([api.list(false), api.list(true)]);
    if (!live || !gone) { setState({ phase: "failed", live: [], gone: [] }); return; }
    const rowsOf = (list, archived) => Promise.all(list.map(async (p) => L.rowOf(p, await api.read(p.code), archived)));
    setState({ phase: "ready", live: await rowsOf(live, false), gone: await rowsOf(gone, true) });
  }
  useEffect(() => { load(); }, [undone.value]);          // read again after an Undo (the toast's), which puts a project back

  async function change(row, op) {
    if (op === "archive" && row.code === openCode.value) return;     // the open project stays: the table offers no Archive for it
    setBusy(row.code);
    await enqueue(async () => {                                      // in order with every other change and Undo
      const r = await api.archive(row.code, op);
      if (!r.ok) { say("problem", r.message); return; }
      await load();
      say("done", op === "archive" ? L.archivedWords(row.name) : L.restoredWords(row.name), r.applyId, row.code);
    });
    setBusy("");
  }

  const rows = showGone ? [...state.live, ...state.gone] : state.live;
  return (
    <section class="frame setting projects" id="projects">
      <div class="proj-head">
        <h2 id="projects-h" tabIndex={-1}>{L.TITLE}</h2>
        <button type="button" class="btn sm" id="show-archived" aria-pressed={showGone ? "true" : "false"} onClick={() => setShowGone(!showGone)}>
          {showGone ? L.LABELS.hide : L.countLabel(state.gone.length)}
        </button>
      </div>
      <p class="muted">{L.INTRO}</p>
      {state.phase === "loading" ? <p class="muted">{L.LOADING}</p> : null}
      {state.phase === "failed" ? <p class="error" role="alert">{L.FAILED} <button type="button" class="btn sm" onClick={load}>{L.LABELS.tryAgain}</button></p> : null}
      {state.phase === "ready" && !rows.length ? <p class="muted" id="projects-none">{state.gone.length ? L.ALL_ARCHIVED : L.NONE}</p> : null}
      {rows.length ? (
        <table class="items proj-table" id="projects-table" aria-label={L.TITLE}>
          <thead><tr>{L.COLUMNS.map((c) => <th key={c} scope="col">{c}</th>)}<th scope="col" aria-label="Actions"></th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.code} data-project={r.code} class={r.archived ? "arch" : ""}>
                <td><b>{r.name}</b>{r.archived ? <> <span class="tag">{L.ARCHIVED}</span></> : r.code === openCode.value ? <> <span class="tag">{L.OPEN_NOW}</span></> : null}</td>
                <td class="num">{r.code}</td>
                <td>{r.client}</td>
                <td>{r.workstreams}</td>
                <td class="num">{r.items}</td>
                <td class="acts">
                  {r.archived ? (
                    <button type="button" class="btn sm" data-restore disabled={!!busy} onClick={() => change(r, "restore")}>{L.LABELS.restore}</button>
                  ) : (
                    <>
                      {r.code !== openCode.value ? <button type="button" class="btn sm" data-open onClick={() => openProjectAt(r.code, "dashboard")}>{L.LABELS.open}</button> : null}
                      {r.code === openCode.value
                        ? <span class="muted" data-open-note>{L.OPEN_NOTE}</span>
                        : <button type="button" class="btn sm" data-archive disabled={!!busy} onClick={() => change(r, "archive")}>{L.LABELS.archive}</button>}
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
