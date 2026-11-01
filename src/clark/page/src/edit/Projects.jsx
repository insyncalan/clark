// Settings › Projects (prototype parity A-S6, #444): Name, Code, Client, Workstreams and Items for each project, with Open, Edit,
// Archive and Restore, Show archived and Add project, as the prototype's table has them. Edit's page only: a published file has no
// Settings. Archive and Restore are one step each with Undo (projectsApi.js); a project's data is never deleted. Archive is on every
// project, the open one too: archiving the open one opens the first other live project, and when there is none the page says so and
// does nothing. Add project and Edit open the project form (ProjectForm.jsx, drawn by Boxes.jsx; POST /api/project). `api` is a seam for the tests.
import { useEffect, useState } from "preact/hooks";
import { project as openCode, openProjectAt, loadProjects, reread } from "../stores/report.js";
import { say, undone, enqueue } from "../stores/changes.js";
import { NewTile } from "../components/NewTile.jsx";
import { listProjects, readProject, sendProjectArchive } from "./projectsApi.js";
import { openBox, closeBox } from "./boxes.js";
import * as L from "../logic/projectsTable.js";
import * as D from "../logic/dataCard.js";

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

  function focusHeading() { const h = document.getElementById("projects-h"); if (h) h.focus(); }

  async function change(row, op) {
    let next = null;                                                 // archiving the open project opens the first other live one
    if (op === "archive" && row.code === openCode.value) {
      next = D.nextAfterArchive(state.live, row.code);
      if (!next) { say("problem", D.ONLY_ONE); return; }              // the only live project: nothing is archived
    }
    setBusy(row.code);
    try {
      await enqueue(async () => {                                    // in order with every other change and Undo
        const r = await api.archive(row.code, op);
        if (!r.ok) { say("problem", r.message); return; }
        if (next) openProjectAt(next, "settings");
        await load();
        loadProjects();                                              // the top bar's list follows
        if (op === "archive") focusHeading();                        // the clicked button is gone: keep the place
        const nextName = next ? (state.live.find((x) => x.code === next) || {}).name || next : "";
        say("done", op === "archive" ? (next ? D.archivedOpenWords(row.name, nextName) : L.archivedWords(row.name)) : L.restoredWords(row.name), r.applyId, row.code);
      });
    } finally {
      setBusy("");                                                   // the buttons never stay switched off
    }
  }

  async function saved(body, edit) {
    closeBox();
    await load();
    loadProjects();
    if (edit) {
      if (body.code === openCode.value) await reread(body.code);     // the top bar and the page show the new name
      say("done", D.PROJECT.saved);
      focusHeading();
    } else {
      openProjectAt(body.code, "work");                              // a new project opens on Work items, ready for an import
      say("done", D.PROJECT.created(body.name));
    }
  }
  const openForm = (row, from) => openBox("project", { row, opener: from, onSaved: saved });

  const rows = showGone ? [...state.live, ...state.gone] : state.live;
  return (
    <section class="frame setting projects" id="projects">
      <div class="proj-head">
        <h2 id="projects-h" tabIndex={-1}>{L.TITLE}</h2>
        <span class="sp"></span>
        <button type="button" class="btn sm" id="show-archived" aria-pressed={showGone ? "true" : "false"} onClick={() => setShowGone(!showGone)}>
          {showGone ? L.LABELS.hide : L.countLabel(state.gone.length)}
        </button>
        <NewTile word={L.LABELS.add} kind="project" id="npBtn" onAdd={() => openForm(null, document.getElementById("npBtn"))} />
      </div>
      <p class="muted">{L.INTRO}</p>
      {state.phase === "loading" ? <p class="muted">{L.LOADING}</p> : null}
      {state.phase === "failed" ? <p class="error" role="alert">{L.FAILED} <button type="button" class="btn sm" onClick={load}>{L.LABELS.tryAgain}</button></p> : null}
      {state.phase === "ready" && !rows.length ? <p class="muted" id="projects-none">{state.gone.length ? L.ALL_ARCHIVED : L.NONE}</p> : null}
      {rows.length ? (
        <table class="items proj-table" id="projects-table" aria-label={L.TITLE}>
          <thead><tr>{L.COLUMNS.map((c) => <th key={c} scope="col">{c}</th>)}<th scope="col" aria-label="What you can do"></th></tr></thead>
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
                    <button type="button" class="btn sm" data-restore aria-label={`Restore ${r.name}`} disabled={!!busy} onClick={() => change(r, "restore")}>{L.LABELS.restore}</button>
                  ) : (
                    <>
                      {r.code !== openCode.value ? <button type="button" class="btn sm" data-open aria-label={`Open ${r.name}`} onClick={() => openProjectAt(r.code, "dashboard")}>{L.LABELS.open}</button> : null}
                      <button type="button" class="btn sm" data-edit aria-label={`Edit ${r.name}`} disabled={!!busy} onClick={(e) => openForm(r, e.currentTarget)}>{L.LABELS.edit}</button>
                      <button type="button" class="btn sm" data-archive aria-label={`Archive ${r.name}`} disabled={!!busy} onClick={() => change(r, "archive")}>{L.LABELS.archive}</button>
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
