// The Published reports page (#443, row 1087): a page of its own, reached only from the profile circle (no tab, no Settings card). Under the
// project's brand band it shows the latest publication, the earlier ones (number, week ending, date, where it went, files, who) with Open,
// Archive, Show archived and Restore, and where the report is saved (the Local and Client folders). The list is clark's own record of what it
// published (past_reports.py), never the folder. Open shows the kept copy in a new tab, as it was published: the page the client was given,
// with nothing from Edit in it. Times are shown in the person's own zone. Edit parts only (a published file has no such page). The server
// decides and checks everything; this draws its answers in plain words (logic/pastReports.js).
// `api`, `openTab`, `code`, `name`, `zone`, `folders` and `toSettings` are seams for the tests; the page passes none of them.
import { useEffect, useState } from "preact/hooks";
import { data, project, show } from "../stores/report.js";
import { Cover } from "../components/Cover.jsx";
import { openInNewTab } from "../router.js";
import { dialog, savedFolder, savedLocal, toPublishingCard } from "./publishState.js";
import { say } from "../stores/changes.js";
import { listPublications, readyPast, archivePublication, restorePublication } from "./pastReportsApi.js";
import * as L from "../logic/pastReports.js";
import { AsAtPick } from "./AsAtPick.jsx";            // item 349: the Dashboard as at a day, under the list

const REAL = { list: listPublications, ready: readyPast, archive: archivePublication, restore: restorePublication };

// The profile menu's "Published reports": the page of its own.
export function showPublished() {
  show("published");
}

export function PublishedReports({ api = REAL, openTab = openInNewTab, code = project.value, name, withAsAt = true, toast = say, zone, folders, toSettings = toPublishingCard }) {
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
  const all = list ? L.groups(list.publications, zone) : [];
  const latest = all.find((g) => !g.archived) || null;
  const rows = all.filter((g) => g !== latest);
  const where = folders || { local: savedLocal(), client: savedFolder() };
  const client = d && d.project && typeof d.project.client_name === "string" ? d.project.client_name.trim() : "";
  const openButton = (g, quiet) => (g.kept
    ? <button type="button" class="btn sm" data-pubopen={g.number} aria-label={`Open Publication ${g.number}`} disabled={!!busy} onClick={() => open(g.number)}>{L.LABELS.open}</button>
    : <span class="muted">{L.NOT_KEPT}</span>);
  const markButton = (g) => (g.archived
    ? <button type="button" class="btn sm quiet" data-pubrestore={g.number} aria-label={`Restore Publication ${g.number}`} disabled={!!marking} onClick={() => mark(g.number, false)}>{L.LABELS.restore}</button>
    : <button type="button" class="btn sm quiet" data-pubarchive={g.number} aria-label={`Archive Publication ${g.number}`} disabled={!!marking} onClick={() => mark(g.number, true)}>{L.LABELS.archive}</button>);
  return (
    <div class="pub-page" id="pubs">
      <Cover title={L.TITLE} kind={title} lines={client ? ["for " + client] : []}><p class="cover-intro">{L.INTRO}</p></Cover>
      {state.phase === "loading" ? <p class="muted" id="pubs-loading">{L.LOADING}</p> : null}
      {state.phase === "failed" ? <p class="error" role="alert">{state.message} <button type="button" class="btn sm" data-pubs-again onClick={load}>{L.LABELS.tryAgain}</button></p> : null}
      <div class="pub-cols">
        <div class="pub-main">
          {latest ? (
            <section class="frame setting pub-latest" id="pubs-latest" aria-labelledby="pubs-latest-h">
              <p class="pub-label"><span id="pubs-latest-h">{L.LATEST}</span> <span class="tag pub-when">{L.publishedBadge(latest)}</span></p>
              <h2 class="pub-head">{L.latestHead(latest)}</h2>
              <p class="muted">{L.wentLatest(latest)} · by {latest.who}</p>
              <p class="muted small">Files: <span data-files>{latest.files}</span></p>
              <p class="pub-acts">{openButton(latest)}{markButton(latest)}</p>
            </section>
          ) : null}
          <section class="frame setting" id="pubs-earlier" aria-labelledby="pubs-earlier-h">
            <h2 class="pub-label" id="pubs-earlier-h">{L.EARLIER}</h2>
            {list ? (
              <div class="pp-tools">
                <button type="button" class="btn sm arch-pill" id="pubs-archived" aria-pressed={showArch ? "true" : "false"} onClick={() => setShowArch(!showArch)}>{L.LABELS.showArchived} <em>{list.archived || 0}</em></button>
              </div>
            ) : null}
            {list && !all.length ? <p class="muted" id="pubs-none">{!showArch && list.archived ? L.ALL_ARCHIVED : L.NONE}</p> : null}
            {list && all.length && !rows.length ? <p class="muted" id="pubs-earlier-none">{L.EARLIER_NONE}</p> : null}
            {rows.length ? (
              <table class="pubs" id="pubs-table">
                <thead><tr>{L.COLUMNS.map((c, i) => <th scope="col" key={i}>{c || <span class="sr">Open</span>}</th>)}</tr></thead>
                <tbody>
                  {rows.map((g) => (
                    <tr key={g.number} data-pub={g.number} class={g.archived ? "arch-row" : ""}>
                      <td class="num"><b>{g.number}</b>{g.archived ? <> <span class="tag arch">{L.ARCHIVED_TAG}</span></> : null}</td>
                      <td class="num">{g.week || L.NOT_RECORDED}</td>
                      <td class="num">{g.when}</td>
                      <td>{L.wentRow(g)}</td>
                      <td>{g.files}</td>
                      <td>{g.who}</td>
                      <td class="acts">{openButton(g)}{markButton(g)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : null}
            {list ? <p class="muted small" id="pubs-note">{L.timesLine(L.zoneName(zone))}{L.cutLine(list.total, list.shown) ? " " + L.cutLine(list.total, list.shown) : ""}</p> : null}
          </section>
        </div>
        <div class="pub-side">
          <section class="frame setting" id="pubs-folders" aria-labelledby="pubs-folders-h">
            <h2 class="pub-label" id="pubs-folders-h">{L.SAVED}</h2>
            <p class="muted small">{L.LOCAL_FOLDER}</p>
            <p class="pub-folder" id="pubs-local">{where.local || <span class="muted">{L.NO_LOCAL}</span>}</p>
            <p class="muted small">{L.CLIENT_FOLDER}</p>
            <p class="pub-folder" id="pubs-client">{where.client || <span class="muted">{L.NO_CLIENT}</span>}</p>
            <p><button type="button" class="btn sm" data-pubs-settings onClick={toSettings}>{L.CHANGE_IN_SETTINGS}</button></p>
            <p class="muted small">{L.SAVED_NOTE}</p>
          </section>
        </div>
      </div>
      <div class="pub-msg" role={msg && msg.kind === "error" ? "alert" : "status"} aria-live="polite">{msg ? <p class={msg.kind}>{msg.text}</p> : null}</div>
      {withAsAt ? <section class="frame setting" id="pubs-asat"><AsAtPick code={code} /></section> : null}
    </div>
  );
}
