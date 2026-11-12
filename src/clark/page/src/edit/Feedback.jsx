// Settings › Feedback (#1069): a form (what is wrong or suggested; an optional contact line), the exact lines of app context the email
// adds, an Open in your mail app link (a plain mailto: link) and Copy as text for a message too long for a link. Nothing is sent by
// clark. `getVersion`, `platform` and `clip` are seams for the tests; the page passes none of them.
import { useEffect, useRef, useState } from "preact/hooks";
import * as L from "../logic/feedback.js";

async function healthVersion() {
  try {
    const r = await fetch("/health", { cache: "no-store" });
    const b = await r.json();
    return b && typeof b.version === "string" ? b.version : "";
  } catch (e) {
    return "";
  }
}
const realClip = (t) => navigator.clipboard.writeText(t);

Feedback.chip = L.LABELS.title;
export function Feedback({ getVersion = healthVersion, platform, clip = realClip }) {
  const [message, setMessage] = useState("");
  const [contact, setContact] = useState("");
  const [version, setVersion] = useState("");
  const [note, setNote] = useState("");
  const [refused, setRefused] = useState(false);
  const shown = useRef(null);
  const system = platform != null ? platform : L.platformWords();
  useEffect(() => { let live = true; getVersion().then((v) => { if (live) setVersion(v || ""); }); return () => { live = false; }; }, []);

  const ctx = { version, platform: system };
  const form = { message, contact };
  const link = L.mail(form, ctx);
  const has = !!message.trim();
  const words = note || (has ? link.message : "");
  const body = L.copyText(form, ctx);

  function edit(set) { return (e) => { set(e.currentTarget.value); setNote(""); setRefused(false); }; }
  async function copy() {
    try { await clip(body); setNote(L.COPIED); setRefused(false); } catch (e) { setNote(L.COPY_REFUSED); setRefused(true); }
  }
  useEffect(() => { if (refused && shown.current) shown.current.select(); }, [refused]);

  return (
    <section class="frame setting" id="feedback">
      <h2 id="feedback-h" tabIndex={-1}>{L.LABELS.title}</h2>
      <p class="muted">{L.LABELS.intro}</p>
      <label for="feedback-message">{L.LABELS.message}</label>
      <textarea id="feedback-message" class="grow" rows={5} value={message} onInput={edit(setMessage)} />
      <label for="feedback-contact">{L.LABELS.contact}</label>
      <input id="feedback-contact" class="grow" type="text" value={contact} onInput={edit(setContact)} />
      <h3>{L.LABELS.contextHead}</h3>
      <ul class="plain" id="feedback-context">{L.contextLines(ctx).map((l) => <li key={l}>{l}</li>)}</ul>
      <p class="muted small">{L.LABELS.contextNote}</p>
      <div class="row">
        {link.href ? <a class="btn pri" data-feedback-mail href={link.href}>{L.LABELS.mail}</a> : null}
        <button type="button" class="btn" data-feedback-copy disabled={!has} onClick={copy}>{L.LABELS.copy}</button>
      </div>
      <div class="pub-msg" id="feedback-note" role="status" aria-live="polite">{words}</div>
      {refused ? <textarea id="feedback-shown" class="grow" rows={6} readOnly ref={shown} value={body} aria-label={L.LABELS.copy} /> : null}
    </section>
  );
}
