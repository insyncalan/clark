// The Draft email editor (FR-44, FR-45; #50): the kind, the ticks, the preview you can edit, Copy for Outlook, Copy as text,
// Open in mail app and I sent it. It builds nothing and saves nothing: `draft` is what the builder returned for `state`, the
// caller asks for a new one in onChange(state) and saves the history entry that onSent(entry) is given (it answers {ok, message}). clark never sends mail.
// Every word from the data is a text node; the email's own HTML is cleaned (safeHtml) before it is drawn.
import { useState, useRef, useEffect } from "preact/hooks";
import { MODES, LABELS, NO_BUILDER, safeHtml, blocked, copyNow, browserClip, mailLink, internalNote, pickWords, togglePick, sentEntry, sentWords, NO_OPEN_ITEMS, NO_ADDRESS } from "../logic/draftEmail.js";

export function DraftEmail({ items, state, draft, today, onChange, onSent, sentOff, onClose, clip, none: noneWords }) {
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);          // I sent it is in flight: the button is off and a second press does nothing (one press, one record)
  const saveLock = useRef(false);
  const sentBtn = useRef(null), wasSaving = useRef(false);
  const preview = useRef(null);
  const edited = useRef(false);
  const shown = useRef("");
  const html = draft ? safeHtml(draft.html) : "";
  // The preview is drawn again only when the builder gives a different email, so a change typed in it is not lost on a re-draw.
  useEffect(() => {
    if (preview.current && shown.current !== html) { preview.current.innerHTML = html; shown.current = html; edited.current = false; }
  }, [html]);
  // A saved (or failed) press turned the button off, which drops focus to the page: put it back on the button, so Esc still reaches the dialog.
  useEffect(() => {
    if (saving) wasSaving.current = true;
    else if (wasSaving.current) { wasSaving.current = false; if (sentBtn.current) sentBtn.current.focus({ preventScroll: true }); }
  }, [saving]);
  const change = (patch) => { setNote(""); if (onChange) onChange({ ...state, ...patch }); };
  const body = () => {
    const el = preview.current;
    return edited.current && el ? { html: el.innerHTML, text: el.innerText } : null;
  };
  const selectPreview = () => {
    const el = preview.current;
    if (!el || !window.getSelection) return;
    const r = document.createRange();
    r.selectNodeContents(el);
    const s = window.getSelection();
    s.removeAllRanges();
    s.addRange(r);
  };
  const copy = async (which) => {
    const got = await copyNow(which, draft, body(), clip || browserClip);
    setNote(got.message);
    if (!got.ok && !got.blocked) selectPreview();
  };
  // onSent(entry) may answer {ok: true} (saved in the history), {ok: false, message} (not saved: the note says why and nothing is
  // marked) or nothing (a caller that does not save yet: the note says so).
  const sent = async () => {
    if (sentOff || saveLock.current) return;
    saveLock.current = true;
    setSaving(true);
    try {
      const entry = sentEntry(draft ? draft.ids : [], state.mode, today);
      const r = onSent ? await onSent(entry) : null;
      if (r && typeof r === "object" && r.ok === false) setNote(typeof r.message === "string" && r.message ? r.message : sentWords(entry, false, true));
      else setNote(sentWords(entry, !!(r && typeof r === "object" && r.ok === true)));
    } catch (e) { setNote(e.message); }
    finally { saveLock.current = false; setSaving(false); }          // a failure leaves it ready to press again
  };
  const keys = (e) => { if (e.key === "Escape") { e.stopPropagation(); if (onClose) onClose(); } };
  if (!draft) {
    return (
      <div class="de" role="dialog" aria-label={LABELS.title}><p class="muted">{NO_BUILDER}</p>
        <button type="button" class="pk-btn" onClick={() => onClose && onClose()}>{LABELS.close}</button></div>
    );
  }
  const none = items.length === 0;                       // nothing is offered: one clear message (a caller may say why in its own words), nothing to tick
  const problem = none ? noneWords || NO_OPEN_ITEMS : blocked(draft);
  const link = mailLink(draft);
  const internal = internalNote(draft.internal_ids);
  const picked = state.picked || [];
  return (
    <div class="de" role="dialog" aria-label={LABELS.title} onKeyDown={keys}>
      <div class="de-head"><h2>{LABELS.title}</h2></div>
      <div class="de-body">
        <fieldset class="de-kinds"><legend class="sr">{LABELS.kind}</legend>
          {MODES.map((m) => (
            <label key={m.mode}><input type="radio" name="de-kind" value={m.mode} checked={state.mode === m.mode} onChange={() => change({ mode: m.mode })} /> {m.label}</label>
          ))}
        </fieldset>
        <dl class="de-meta">
          <dt>{LABELS.to}</dt><dd>{draft.to || NO_ADDRESS}</dd>
          <dt>{LABELS.subject}</dt><dd>{draft.subject}</dd>
        </dl>
        {none ? null : <section aria-label={LABELS.items}>
          <h3>{LABELS.items}</h3>
          <ul class="pick">
            {items.map((i) => (
              <li key={i.id}><label>
                <input type="checkbox" value={i.id} checked={picked.includes(i.id)} onChange={() => change({ picked: togglePick(items, picked, i.id) })} />
                <span class="pk-text"><b>{i.id}</b> {i.text}</span>
              </label></li>
            ))}
          </ul>
          <p class="muted de-count" aria-live="polite">{pickWords(picked.length, items.length)}</p>
        </section>}
        <div class="de-opts">
          <label>{LABELS.replyBy} <input type="date" value={state.replyBy || ""} onInput={(e) => change({ replyBy: e.currentTarget.value })} /></label>
          {state.mode === "decision" || state.mode === "chase" ? <label>{LABELS.unblocks} <input type="text" value={state.unblocks || ""} onInput={(e) => change({ unblocks: e.currentTarget.value })} /></label> : null}
          <label><input type="checkbox" checked={!!state.includeUpdate} onChange={(e) => change({ includeUpdate: e.currentTarget.checked })} /> {LABELS.includeUpdate}</label>
        </div>
        {problem ? <p class="de-problem" role="alert">{problem}</p> : null}
        <p class="muted">{LABELS.edit}</p>
        <div class="de-preview" ref={preview} contentEditable={true} role="textbox" aria-multiline="true" aria-label="Email" tabIndex={0}
          onInput={() => { edited.current = true; }} />
        {internal ? <p class="de-internal">{internal}</p> : null}
        <p class="muted de-note" role="status" aria-live="polite">{note}</p>
        {link.message && !problem ? <p class="muted de-mail">{link.message}</p> : null}
      </div>
      {sentOff ? <p class="muted de-note" id="de-sent-off">{sentOff}</p> : null}
      <div class="pk-foot">
        <button type="button" class="pk-btn pri" disabled={!!problem} onClick={() => copy("outlook")}>{LABELS.copyOutlook}</button>
        <button type="button" class="pk-btn" disabled={!!problem} onClick={() => copy("text")}>{LABELS.copyText}</button>
        {link.href ? <a class="pk-btn" href={link.href}>{LABELS.mail}</a> : null}
        <button type="button" class="pk-btn" ref={sentBtn} disabled={!!problem || saving || !!sentOff} aria-describedby={sentOff ? "de-sent-off" : undefined} onClick={sent}>{LABELS.sent}</button>
        <button type="button" class="pk-btn" onClick={() => onClose && onClose()}>{LABELS.close}</button>
      </div>
    </div>
  );
}
