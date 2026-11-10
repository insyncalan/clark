// Settings › Published reports (#443): the latest 10 publications of the open project, newest first, with the number, when, where
// and who, and Open for each page that was kept (the prototype's card, system/prototype/views.js). Open shows the kept copy in a new
// tab, as it was published: the page the client was given, with nothing from Edit in it. Edit parts only (a published file has no
// Settings). The server decides and checks everything (past_reports.py); this draws its answers in plain words (logic/pastReports.js).
// `api`, `openTab`, `code` and `name` are seams for the tests; the page passes none of them.
import { useEffect, useState } from "preact/hooks";
import { data, project, openSettings } from "../stores/report.js";
import { openInNewTab } from "../router.js";
import { dialog } from "./publishState.js";
import { say } from "../stores/changes.js";
import { listPublications, readyPast, archivePublication, restorePublication } from "./pastReportsApi.js";
import * as L from "../logic/pastReports.js";
import { AsAtPick } from "./AsAtPick.jsx";            // item 349: the Dashboard as at a day, under the list

const REAL = { list: listPublications, ready: readyPast, archive: archivePublication, restore: restorePublication };

// The profile menu's "Published reports": Settings on its own page (item 1024), the heading focused by the page.
export function showPublished() {
  openSettings("published");
}

export function PublishedReports({ api = REAL, openTab = openInNewTab, code = project.value, name, withAsAt = true, toast = say }) {
  const [state, setState] = useState({ phase: "loading", list: null, message: "" });
  const [msg, setMsg] = useState(null);                      // {kind: "error" | "note", text}
  const [busy, setBusy] = useState(0);                       // the number being opened, or 0
  const [showArch, setShowArch] = useState(false);           // Show archived (#345): the archived ones are listed too, marked
  const [marking, setMarking] = useState(0);                 // the number being archived or restored, or 0
  const d = data.value;
  const title = name || (d && d.project && d.project.name) || code;
  const publishing = dialog.value !== null;                  // the list is read again when the Publish box closes

  async function load() {
    setState((s) => ({ ...s, phase: s.list ? "ready" : "loading" }));
    const r = await api.list(code, showArch);
    if (r.status === 200 && L.isList(r.body)) setState({ phase: "ready", list: r.body, message: "" });
    else setState({ phase: "failed", list: null, message: L.listWords(r.status, r.body) });
  }
  useEffect(() => { if (!publishing) load(); }, [code, publishing, showArch]);

  // Archive and Restore (#345): one request, the list read again, and a toast with no Undo (Restore, or Archive, is the way back).
  async function mark(number, archive) {
    if (marking) return;
    setMarking(number);
    setMsg(null);
    const r = await (archive ? api.archive : api.restore)(code, number);
    setMarking(0);
    if (r.status === 200 && r.body && r.body.ok === true) {
      toast("done", archive ? L.archivedToast(number) : L.restoredToast(number));
      load();
      return;
    }
    setMsg({ kind: "error", text: L.markWords(r.status, r.body) });
  }

  // The tab is opened first, while the click still counts (a browser blocks one opened after a wait), then pointed at the kept page.
  async function open(number) {
    if (busy) return;
    setBusy(number);
    setMsg(null);
    let r = null;
    const opened = await openTab(async () => {
      r = await api.ready(code, number);
      return r.status === 200 && r.body && r.body.ok === true && typeof r.body.url === "string" ? r.body.url : null;
    });
    setBusy(0);
    if (opened) return;
    setMsg({ kind: "error", text: r && r.status === 200 ? L.BLOCKED : L.openWords(r ? r.status : 0, r ? r.body : null) });
  }

  const list = state.list;
  const rows = list ? list.publications.map(L.rowView) : [];
  return (
    <section class="frame setting" id="pubs">
      <h2 id="pubs-h" tabIndex={-1}>{L.TITLE} · {title}</h2>
      <p class="muted">{L.INTRO}</p>
      {state.phase === "loading" ? <p class="muted" id="pubs-loading">{L.LOADING}</p> : null}
      {state.phase === "failed" ? <p class="error" role="alert">{state.message} <button type="button" class="btn sm" data-pubs-again onClick={load}>{L.LABELS.tryAgain}</button></p> : null}
      {list ? (
        <div class="pp-tools">
          <button type="button" class="btn sm arch-pill" id="pubs-archived" aria-pressed={showArch ? "true" : "false"} onClick={() => setShowArch(!showArch)}>{L.LABELS.showArchived} <em>{list.archived || 0}</em></button>
        </div>
      ) : null}
      {list && !rows.length ? <p class="muted" id="pubs-none">{!showArch && list.archived ? L.ALL_ARCHIVED : L.NONE}</p> : null}
      {rows.length ? (
        <>
          <table class="pubs" id="pubs-table">
            <thead><tr>{L.COLUMNS.map((c, i) => <th scope="col" key={i}>{c || <span class="sr">Open</span>}</th>)}</tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.number} data-pub={r.number} class={r.archived ? "arch-row" : ""}>
                  <td class="num"><b>{r.number}</b>{r.archived ? <> <span class="tag arch">{L.ARCHIVED_TAG}</span></> : null}</td>
                  <td class="num">{r.when}</td>
                  <td>{r.where}</td>
                  <td>{r.who}</td>
                  <td class="acts">{r.kept ? <button type="button" class="btn sm" data-pubopen={r.number} aria-label={`Open Publication ${r.number}`} disabled={!!busy} onClick={() => open(r.number)}>{L.LABELS.open}</button> : <span class="muted">{L.NOT_KEPT}</span>}{r.archived
                    ? <button type="button" class="btn sm quiet" data-pubrestore={r.number} aria-label={`Restore Publication ${r.number}`} disabled={!!marking} onClick={() => mark(r.number, false)}>{L.LABELS.restore}</button>
                    : <button type="button" class="btn sm quiet" data-pubarchive={r.number} aria-label={`Archive Publication ${r.number}`} disabled={!!marking} onClick={() => mark(r.number, true)}>{L.LABELS.archive}</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p class="muted small" id="pubs-note">{L.TIMES}{L.cutLine(list.total, list.shown) ? " " + L.cutLine(list.total, list.shown) : ""}</p>
        </>
      ) : null}
      <div class="pub-msg" role={msg && msg.kind === "error" ? "alert" : "status"} aria-live="polite">{msg ? <p class={msg.kind}>{msg.text}</p> : null}</div>
      {withAsAt ? <AsAtPick code={code} /> : null}
    </section>
  );
}
