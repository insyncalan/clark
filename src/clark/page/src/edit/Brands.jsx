// Settings › Brands: the brands added to this computer (name, version, Remove), Review the newest brand file in Downloads or Choose
// one, the review panel (Install for a new brand, Replace for one already added: a second click), Remove (arm, then confirm) and
// Undo (one click). Edit parts only. The server decides and checks everything; its sentence is drawn as text (logic/brand.js).
// `api` is a seam for the tests; the page passes none.
import { useEffect, useRef, useState } from "preact/hooks";
import * as A from "./brandApi.js";
import * as L from "../logic/brand.js";

const REAL = { list: A.listBrands, review: A.reviewBrand, install: A.installBrand, remove: A.removeBrand, undo: A.undoBrand };
const ok = (r) => r.status === 200 && r.body && r.body.ok === true;

Brands.chip = L.TITLE;
export function Brands({ api = REAL }) {
  const [state, setState] = useState({ phase: "loading", view: null, message: "" });
  const [panel, setPanel] = useState(null);           // null, or {id, view}
  const [armed, setArmed] = useState(null);           // null, or the brand id Remove asked about
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const heading = useRef(null);
  const opener = useRef("[data-review]");      // the button that opened the panel: the focus goes back to it when the panel closes
  const back = (...sels) => requestAnimationFrame(() => { for (const sel of sels) { const b = document.querySelector(`#brands ${sel}`); if (b) { b.focus(); return; } } });      // the first of these that is on the page
  const closeAsk = () => { const id = armed; setArmed(null); back(`li[data-brand="${id}"] [data-remove]`, "[data-review]"); };      // Cancel or Esc on Remove's question
  const closePanel = () => { setPanel(null); back(opener.current); };
  const escape = (close) => (e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); } };

  async function load() {
    const r = await api.list();
    if (ok(r)) setState({ phase: "ready", view: L.listView(r.body), message: "" });
    else setState({ phase: "failed", view: null, message: L.answerWords(r.status, r.body) });
  }
  useEffect(() => { load(); }, []);
  useEffect(() => { if (armed) back("[data-remove-confirm]"); }, [armed]);      // Remove's question is drawn after the list: the focus goes to it
  useEffect(() => { if (panel && heading.current) heading.current.focus(); }, [panel]);

  async function review(from) {
    if (busy) return;      // aria-disabled keeps the focus on the button while the server answers; a click then does nothing
    opener.current = from === "file" ? "[data-choose]" : "[data-review]";
    setBusy(true);
    setMsg(null);
    setPanel(null);
    setArmed(null);
    const r = await api.review(from);
    setBusy(false);
    // The server answers {ok: true, review: null} when no file was chosen (Cancel in the dialog, or nothing in Downloads).
    if (ok(r) && (r.body.cancelled || r.body.review === null)) { setMsg({ kind: "info", text: from === "downloads" && !r.body.cancelled ? L.NO_BRAND : L.CANCELLED }); back(opener.current); return; }
    if (ok(r) && r.body.review) {
      setPanel({ id: text(r.body.review.review_id), view: L.reviewView(r.body.review, state.view ? state.view.brands : []) });
      return;
    }
    setMsg({ kind: "error", text: L.answerWords(r.status, r.body) });
    back(opener.current);                                        // refused: the button that was pressed took the focus away while it worked
  }

  // Install, Remove and Undo: ask, then read the list again whatever the answer was.
  async function act(ask, ...after) {
    if (busy) return;
    setBusy(true);
    setMsg(null);
    const r = await ask();
    if (!ok(r)) setMsg({ kind: "error", text: L.answerWords(r.status, r.body) });
    await load();
    setBusy(false);
    if (after.length) back(...after);      // the button that was clicked has gone: the focus goes to the next one that is there
  }
  const install = () => { const id = panel.id; setPanel(null); return act(() => api.install(id), opener.current, "[data-review]"); };
  const remove = () => { const id = armed; setArmed(null); return act(() => api.remove(id), `li[data-brand="${id}"] [data-remove]`, "[data-review]"); };

  const v = state.view;
  return (
    <section class="frame setting" id="brands">
      <h2 id="brands-h" tabIndex={-1}>{L.TITLE}</h2>
      <p class="muted">{L.INTRO}</p>
      {state.phase === "loading" ? <p class="muted">{L.LOADING}</p> : null}
      {state.phase === "failed" ? <p class="error" role="alert">{state.message} <button type="button" class="btn sm" onClick={load}>{L.LABELS.tryAgain}</button></p> : null}
      {v ? (
        <>
          {v.brands.length ? (
            <ul class="plain" id="brands-list">
              {v.brands.map((b) => (
                <li key={b.id} data-brand={b.id}>
                  <b>{b.name}</b> {b.version}{" "}
                  {b.own ? <button type="button" class="btn sm" data-remove disabled={busy} onClick={() => setArmed(b.id)}>{L.LABELS.remove}</button> : null}
                </li>
              ))}
            </ul>
          ) : <p class="muted" id="brands-list">{L.EMPTY}</p>}
          {armed ? (
            <div class="row" onKeyDown={escape(closeAsk)}>
              <button type="button" class="btn pri" data-remove-confirm disabled={busy} onClick={remove}>{L.CONFIRM_REMOVE}</button>
              <button type="button" class="btn quiet" disabled={busy} onClick={closeAsk}>{L.LABELS.cancel}</button>
            </div>
          ) : null}
          <div class="row">
            <button type="button" class={v.ready ? "btn pri" : "btn"} data-review aria-describedby="brands-hint" aria-disabled={busy ? "true" : undefined} onClick={() => review("downloads")}>{L.LABELS.review}</button>
            <button type="button" class="btn" data-choose aria-disabled={busy ? "true" : undefined} onClick={() => review("file")}>{L.LABELS.choose}</button>
            {v.undo ? <button type="button" class="btn" data-undo aria-disabled={busy ? "true" : undefined} onClick={() => act(() => api.undo(), "[data-undo]", "[data-review]")}>{L.LABELS.undo}</button> : null}
          </div>
          <p class="muted" id="brands-hint">{L.REVIEW_HINT}</p>
        </>
      ) : null}
      {panel ? (
        <div class="backup-panel" id="brands-panel" role="region" aria-labelledby="brands-panel-h" onKeyDown={escape(closePanel)}>
          <p id="brands-panel-h" tabIndex={-1} ref={heading}><b>{panel.view.name}</b> {panel.view.version}</p>
          {panel.view.lists.map(([label, names]) => names.length ? (
            <div key={label}>
              <p><b>{label}</b></p>
              <ul class="plain">{names.map((n) => { const w = L.fileWords(n); return <li key={n}>{w.label}{w.file ? <> <small class="brand-file">{w.file}</small></> : null}</li>; })}</ul>
            </div>
          ) : null)}
          <div class="row">
            <button type="button" class="btn pri" data-install disabled={busy} onClick={install}>{panel.view.replace ? L.LABELS.replace : L.LABELS.install}</button>
            <button type="button" class="btn quiet" data-cancel disabled={busy} onClick={closePanel}>{L.LABELS.cancel}</button>
          </div>
        </div>
      ) : null}
      <div class="pub-msg" role="status" aria-live="polite">{msg ? <p class={msg.kind}>{msg.text}{msg.kind === "error" ? <> <button type="button" class="btn sm" data-dismiss onClick={() => setMsg(null)}>{L.LABELS.dismiss}</button></> : null}</p> : null}</div>
    </section>
  );
}
const text = (s) => (typeof s === "string" ? s : "");
