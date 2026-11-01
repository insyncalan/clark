// Settings › Published reports (#443): the latest 10 publications of the open project, newest first, with the number, when, where
// and who, and Open for each page that was kept (the prototype's card, system/prototype/views.js). Open shows the kept copy in a new
// tab, as it was published: the page the client was given, with nothing from Edit in it. Edit parts only (a published file has no
// Settings). The server decides and checks everything (past_reports.py); this draws its answers in plain words (logic/pastReports.js).
// `api`, `openTab`, `code` and `name` are seams for the tests; the page passes none of them.
import { useEffect, useState } from "preact/hooks";
import { data, project, show } from "../stores/report.js";
import { openInNewTab } from "../router.js";
import { dialog } from "./publishState.js";
import { listPublications, readyPast } from "./pastReportsApi.js";
import * as L from "../logic/pastReports.js";

const REAL = { list: listPublications, ready: readyPast };

// The profile menu's "Published reports": Settings, with the card brought to the top (smoothly unless the person asked for less motion).
export function showPublished() {
  show("settings");
  setTimeout(() => {
    const el = document.getElementById("pubs");
    if (!el) return;
    let calm = false;
    try { calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) { calm = false; }
    el.scrollIntoView({ block: "start", behavior: calm ? "auto" : "smooth" });
  }, 60);
}

export function PublishedReports({ api = REAL, openTab = openInNewTab, code = project.value, name }) {
  const [state, setState] = useState({ phase: "loading", list: null, message: "" });
  const [msg, setMsg] = useState(null);                      // {kind: "error" | "note", text}
  const [busy, setBusy] = useState(0);                       // the number being opened, or 0
  const d = data.value;
  const title = name || (d && d.project && d.project.name) || code;
  const publishing = dialog.value !== null;                  // the list is read again when the Publish box closes

  async function load() {
    setState((s) => ({ ...s, phase: s.list ? "ready" : "loading" }));
    const r = await api.list(code);
    if (r.status === 200 && L.isList(r.body)) setState({ phase: "ready", list: r.body, message: "" });
    else setState({ phase: "failed", list: null, message: L.listWords(r.status, r.body) });
  }
  useEffect(() => { if (!publishing) load(); }, [code, publishing]);

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
      <h2>{L.TITLE} · {title}</h2>
      <p class="muted">{L.INTRO}</p>
      {state.phase === "loading" ? <p class="muted" id="pubs-loading">{L.LOADING}</p> : null}
      {state.phase === "failed" ? <p class="error" role="alert">{state.message} <button type="button" class="btn sm" data-pubs-again onClick={load}>{L.LABELS.tryAgain}</button></p> : null}
      {list && !rows.length ? <p class="muted" id="pubs-none">{L.NONE}</p> : null}
      {rows.length ? (
        <>
          <table class="pubs" id="pubs-table">
            <thead><tr>{L.COLUMNS.map((c, i) => <th scope="col" key={i}>{c || <span class="sr">Open</span>}</th>)}</tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.number} data-pub={r.number}>
                  <td class="num"><b>{r.number}</b></td>
                  <td class="num">{r.when}</td>
                  <td>{r.where}</td>
                  <td>{r.who}</td>
                  <td class="acts">{r.kept ? <button type="button" class="btn sm" data-pubopen={r.number} aria-label={`Open Publication ${r.number}`} disabled={!!busy} onClick={() => open(r.number)}>{L.LABELS.open}</button> : <span class="muted">{L.NOT_KEPT}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p class="muted small" id="pubs-note">{L.TIMES}{L.cutLine(list.total, list.shown) ? " " + L.cutLine(list.total, list.shown) : ""}</p>
        </>
      ) : null}
      <div class="pub-msg" role={msg && msg.kind === "error" ? "alert" : "status"} aria-live="polite">{msg ? <p class={msg.kind}>{msg.text}</p> : null}</div>
    </section>
  );
}
