// The Feedback tag (#1298): a button on the right edge, a little below the middle, in Help and in Settings only (logic/feedbackTag.js says
// where). It opens a small dialog that slides in from the right edge: the Feedback card's question, Problem / Idea / Question, the three
// lines added automatically, Copy as text and Open in your mail app (the server hands the mailto: link to the mail app, row 1297; nothing is sent by clark). Edit parts only.
// `getVersion`, `getDiagnostics`, `nav` and `clip` are seams for the tests; the page passes none of them.
import { useEffect, useRef, useState } from "preact/hooks";
import * as L from "../logic/feedbackTag.js";
import { mailClick, MAIL_NOTE } from "./mailApi.js";   // Open in your mail app goes through the server route (row 1297), as in Settings, Feedback
import { readDiagnostics } from "./diagnosticsApi.js";   // GET /api/diagnostics: its System line gives the macOS version for the mail
import { healthVersion } from "./Feedback.jsx";   // the same health check; it asks for no zone, so it is not a zoneFetch
import { view, settingsPage, settingsFeedbackShown, peek, fromFile } from "../stores/report.js";
import { helpOpen, contextOpen } from "../help/helpStore.js";
import { width as peekWidth, wide as peekWide } from "../stores/peekState.js";

const realClip = (t) => navigator.clipboard.writeText(t);

function Dialog({ ctx, onClose, clip }) {
  const [kind, setKind] = useState(L.DEFAULT_KIND);
  const [message, setMessage] = useState("");
  const [note, setNote] = useState("");
  const [refused, setRefused] = useState(false);
  const [mailFailed, setMailFailed] = useState(false);
  const box = useRef(null), area = useRef(null), shown = useRef(null);
  const form = { kind, message };
  const link = L.mail(form, ctx);
  const has = !!message.trim();
  const body = L.copyText(form, ctx);
  useEffect(() => { if (area.current) area.current.focus(); }, []);
  useEffect(() => { if (refused && shown.current) shown.current.select(); }, [refused]);
  function key(e) {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onClose(); }
  }
  async function copy() {
    if (tryEmpty()) return;
    try { await clip(body); setNote(L.COPIED); setRefused(false); } catch (e) { setNote(L.COPY_REFUSED); setRefused(true); }
  }
  const words = note || (has ? link.message : "");
  const [empty, setEmpty] = useState(false);     // Copy or Open pressed with nothing written: the red line under the box
  const tryEmpty = () => { if (L.emptySend(form)) { setEmpty(true); return true; } return false; };
  return (
    <div class="fbt-dlg" id="feedback-tag-dialog" role="dialog" aria-labelledby="fbt-h" ref={box} onKeyDown={key}>
      <div class="fbt-head"><h2 id="fbt-h">{L.TAG_LABELS.title}</h2><button type="button" class="fbt-x" data-fbt-close aria-label={L.TAG_LABELS.close} onClick={onClose}>&times;</button></div>
      <p class="muted small">{L.TAG_LABELS.intro}</p>
      <div role="radiogroup" aria-label={L.TAG_LABELS.kind} class="fbt-kinds">
        {L.KINDS.map((k) => <button type="button" key={k} role="radio" aria-checked={k === kind} class={`fbt-kind${k === kind ? " on" : ""}`} data-fbt-kind={k} onClick={() => { setKind(k); setNote(""); setMailFailed(false); }}>{k}</button>)}
      </div>
      <label for="fbt-message">{L.TAG_LABELS.message}</label>
      <textarea id="fbt-message" class="grow" rows={4} ref={area} aria-describedby={empty ? "fbt-error" : undefined} value={message} onInput={(e) => { setMessage(e.currentTarget.value); setNote(""); setEmpty(false); setRefused(false); setMailFailed(false); }} />
      {empty ? <div class="fbt-error" id="fbt-error" role="alert">{L.EMPTY_SEND}</div> : null}
      <div class="fbt-added" id="fbt-added">
        <b>{L.TAG_LABELS.addedHead}</b>
        <ul class="plain">{L.contextLines(ctx).map((l) => <li key={l}>{l}</li>)}</ul>
        <span>{L.TAG_LABELS.addedNote}</span>
      </div>
      <p class="muted small">{L.TAG_LABELS.mailNote}</p>
      <div class="row">
        <button type="button" class="btn" data-fbt-copy onClick={copy}>{L.TAG_LABELS.copy}</button>
        {link.href ? <a class="btn pri" data-fbt-mail href={link.href} onClick={(e) => mailClick(e, link.href, setMailFailed)}>{L.TAG_LABELS.mail}</a>
          : <a class="btn pri" data-fbt-mail role="button" tabindex="0" onClick={tryEmpty} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); tryEmpty(); } }}>{L.TAG_LABELS.mail}</a>}
      </div>
      {mailFailed ? <p class="muted" data-mail-note>{MAIL_NOTE}</p> : null}
      <div class="pub-msg" id="fbt-note" role="status" aria-live="polite">{words}</div>
      {refused ? <textarea id="fbt-shown" class="grow" rows={5} readOnly ref={shown} value={body} aria-label={L.TAG_LABELS.copy} /> : null}
    </div>
  );
}

export function FeedbackTag({ getVersion = healthVersion, getDiagnostics = readDiagnostics, nav, clip = realClip }) {
  const where = { view: view.value, page: settingsPage.value, helpOpen: helpOpen.value, fromFile: fromFile.value, feedbackCard: settingsFeedbackShown.value };
  const on = L.tagShown(where);
  const [open, setOpen] = useState(false);
  const [version, setVersion] = useState("");
  const [report, setReport] = useState("");
  const tag = useRef(null);
  useEffect(() => { let live = true; if (on && open) getVersion().then((v) => { if (live) setVersion(v || ""); }); return () => { live = false; }; }, [on, open]);   // eslint-disable-line react-hooks/exhaustive-deps
  // The System line comes from the same report Copy diagnostics copies; a failed call leaves it empty and the mail says just "macOS".
  useEffect(() => {
    let live = true;
    if (on && open) Promise.resolve().then(getDiagnostics).then((r) => { if (live) setReport(r && r.status === 200 && r.body && typeof r.body.report === "string" ? r.body.report : ""); }, () => { if (live) setReport(""); });
    return () => { live = false; };
  }, [on, open]);   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (!on) setOpen(false); }, [on]);
  // Esc closes the dialog from anywhere on the page (focus may still be on the tag), and Help (whose own Esc stands aside while the dialog is open) stays.
  useEffect(() => {
    if (!open) return undefined;
    const esc = (e) => { if (e.key === "Escape" && !e.defaultPrevented) { e.preventDefault(); setOpen(false); if (tag.current) tag.current.focus(); } };
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [open]);
  // The item peek is a card 16 px in from the edge, as wide as it was dragged, or the window less 32 px (wide, or under 1000 px): the tag reads where its left edge really is.
  const [gap, setGap] = useState(null);
  const dragged = peekWidth.value, spans = peekWide.value, shownPeek = !!peek.value;
  useEffect(() => {
    const el = shownPeek && on ? document.getElementById("peek") : null;
    if (!el) { setGap(null); return undefined; }
    const read = () => setGap(Math.max(0, Math.round(document.documentElement.clientWidth - el.getBoundingClientRect().left)));
    read();
    const ro = typeof ResizeObserver === "function" ? new ResizeObserver(read) : null;
    if (ro) ro.observe(el);
    window.addEventListener("resize", read);
    return () => { if (ro) ro.disconnect(); window.removeEventListener("resize", read); };
  }, [shownPeek, on, dragged, spans]);
  if (!on) return null;
  const close = () => { setOpen(false); if (tag.current) tag.current.focus(); };
  const ctx = { version, platform: L.systemWords(nav, report), page: L.pageWords(where) };
  const beside = !!peek.value, besideHelp = contextOpen.value;      // the item peek is as wide as it was dragged (or the window less 32 px), the Help peek 380 (--hpk-w); with both up the inline right below wins
  const edge = beside && !open && gap != null ? `${gap}px` : "";
  return (
    <>
      <button type="button" class={`fbt-tag${beside ? " beside" : ""}${besideHelp ? " beside-help" : ""}${open ? " open" : ""}`} id="feedback-tag" style={edge ? `right:${edge}` : undefined} ref={tag} aria-label={L.TAG_LABELS.tagAria} aria-expanded={open ? "true" : "false"} aria-controls="feedback-tag-dialog" onClick={() => (open ? close() : setOpen(true))}>{L.TAG_LABELS.tag}</button>
      {open ? <Dialog ctx={ctx} onClose={close} clip={clip} /> : null}
    </>
  );
}
