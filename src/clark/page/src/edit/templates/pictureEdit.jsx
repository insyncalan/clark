// The Pictures group's shared Edit parts (#96: Text and image, Image with caption, Image gallery, Headline band). Edit only: this
// folder is never in a published file.
// - Words are saved with one change() each (one step, one Undo, place "report"), the body sent WITHOUT its pictures: the server keeps
//   the stored ones (changes.py _keep_pictures). A field is saved when it is left or on Enter; Esc puts the saved words back.
// - A picture is made smaller on a canvas (shrink.js) and sent on its own to POST /api/section-image: one slot, one step, one Undo.
// - Under each picture template, the running total of the pictures in the report against the 5 MB a published page can hold.
import { useLayoutEffect, useRef, useState } from "preact/hooks";
import { data, project, reread, token, plainChange } from "../../stores/report.js";
import { change, say } from "../../stores/changes.js";
import { stored, PICTURE_TYPES } from "../../templates/pictures.jsx";
import { safeImage } from "../../templates/safe.js";
import { shrink, dataBytes, TYPES } from "./shrink.js";

export const PAGE_LIMIT = 5 * 1024 * 1024;         // publish.MAX_BYTES: a published page over this is refused
export const NEAR = 4 * 1024 * 1024;              // pictures past this are close to it (the rest of the page needs room too)
const PLACE = "report";

// The section's words as the page last saved them, without its pictures. A later field saved before the page has read the earlier
// one back starts from the earlier one's words, so two quick saves never lose one another's words.
const pending = new Map();
export function wordsOf(section) {
  if (pending.has(section.id)) return pending.get(section.id);
  const v = { ...(stored(section) || {}) };
  delete v.pictures;
  v.v = 1;
  return v;
}

// Save some fields (an empty value takes the field out). Resolves to the reply, or null when nothing was saved.
export function saveWords(section, fields, words) {
  const next = { ...wordsOf(section) };
  for (const [k, v] of Object.entries(fields)) {
    if (v === "" || v === null || v === undefined || (Array.isArray(v) && !v.length) || (v && typeof v === "object" && !Array.isArray(v) && !Object.keys(v).length)) delete next[k];
    else next[k] = v;
  }
  pending.set(section.id, next);
  return change({ op: "update", id: section.id, changes: { body: JSON.stringify(next) }, place: PLACE }, words).then((reply) => {
    if (pending.get(section.id) === next) pending.delete(section.id);
    return reply;
  });
}

// The server's own words for a refused picture are short fixed sentences (section_kinds/textimage.py); anything else gets the
// page's words for its status.
function refusal(status, reply) {
  const said = reply && typeof reply.message === "string" ? reply.message : "";
  return status === 400 && said && said.length <= 200 && !/[\u0000-\u001f]/.test(said) ? said : plainChange(status, reply);
}

// Set (or, with image null, take out) the picture in one slot. Resolves to the reply, or null (the toast says why).
export async function sendPicture(section, slot, image, words) {
  const code = project.value;
  try {
    const r = await fetch("/api/section-image", {
      method: "POST",
      headers: { "X-Clark-Token": token(), "Content-Type": "application/json" },
      body: JSON.stringify({ project: code, section: section.id, slot, image, place: PLACE }),
      cache: "no-store",
    });
    const reply = await r.json().catch(() => null);
    if (!r.ok || !reply || reply.ok !== true) { say("problem", refusal(r.status, reply)); return null; }
    if (!(await reread(code)) && project.value === code) say("problem", "The picture was saved, but the page could not be refreshed. Reload the page to see it.");
    else if (reply.apply_id) say("done", words, reply.apply_id, code);
    return reply;
  } catch (e) {
    say("problem", plainChange(0));
    return null;
  }
}

// One line of words. `max` characters at most (the server's own limit). `check(text)` may give a problem in plain words, said instead
// of saving; `save(text)` saves it another way than as the field `field` (the gallery's captions).
export function LineField({ section, field, label, value, max, hint, words, check, save }) {
  const ref = useRef(null), esc = useRef(false);
  useLayoutEffect(() => { if (ref.current && document.activeElement !== ref.current) ref.current.value = value || ""; }, [value]);
  const commit = () => {
    if (esc.current) { esc.current = false; return; }
    const v = ref.current.value.replace(/\s+/g, " ").trim();
    if (v === (value || "")) { ref.current.value = value || ""; return; }
    const problem = check ? check(v) : "";
    if (problem) { say("problem", problem); ref.current.value = value || ""; return; }
    (save ? save(v) : saveWords(section, { [field]: v }, words)).then((r) => { if (!r && ref.current) ref.current.value = value || ""; });
  };
  const onKeyDown = (e) => {
    if (e.isComposing) return;
    if (e.key === "Enter") { e.preventDefault(); ref.current.blur(); }
    else if (e.key === "Escape") { e.preventDefault(); esc.current = true; ref.current.value = value || ""; ref.current.blur(); }
  };
  const id = `tpl-${section.id}-${field}`;
  return (
    <div class="tpl-pic-field">
      <label for={id}>{label}</label>
      <input id={id} ref={ref} type="text" maxLength={max} placeholder={hint || ""} defaultValue={value || ""} onBlur={commit} onKeyDown={onKeyDown} spellcheck={true} />
    </div>
  );
}

// Paragraphs: each line typed is a paragraph. Saved when the box is left; Esc puts the saved words back.
export function WordsField({ section, field, label, value, max, hint, words }) {
  const ref = useRef(null), esc = useRef(false);
  const joined = (value || []).join("\n");
  useLayoutEffect(() => { if (ref.current && document.activeElement !== ref.current) ref.current.value = joined; }, [joined]);
  const commit = () => {
    if (esc.current) { esc.current = false; return; }
    const list = ref.current.value.split(/\r?\n/).map((p) => p.replace(/\s+/g, " ").trim()).filter(Boolean);
    if (list.join("\n") === joined) return;
    saveWords(section, { [field]: list }, words).then((r) => { if (!r && ref.current) ref.current.value = joined; });
  };
  const onKeyDown = (e) => {
    if (e.key === "Escape") { e.preventDefault(); esc.current = true; ref.current.value = joined; ref.current.blur(); }
  };
  const id = `tpl-${section.id}-${field}`;
  return (
    <div class="tpl-pic-field">
      <label for={id}>{label}</label>
      <textarea id={id} ref={ref} rows={4} maxLength={max} placeholder={hint || ""} defaultValue={joined} onBlur={commit} onKeyDown={onKeyDown} />
    </div>
  );
}

// One picture's place: the picture, or an empty frame; Add a picture (or drop one here), Change picture, Take the picture out.
export function PictureSlot({ section, slot, image, label, longest = 1600, most = 1024 * 1024, words }) {
  const input = useRef(null);
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const pic = safeImage(image || "");
  const take = async (file) => {
    if (!file || busy) return;
    setBusy(true);
    const made = await shrink(file, { longest, most });
    if (!made.ok) { say("problem", made.message); setBusy(false); return; }
    await sendPicture(section, slot, made.data, words.added);
    setBusy(false);
  };
  const onDrop = (e) => {
    e.preventDefault(); setOver(false);
    const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) take(f);
  };
  return (
    <div class={`tpl-pic-slot${pic ? " has-pic" : ""}${over ? " over" : ""}`} data-slot={slot}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={onDrop}>
      {pic ? <img src={pic} alt="" class="tpl-pic-slot-img" /> : <p class="tpl-pic-slot-empty">{busy ? "Making the picture smaller…" : `${label}: choose a picture, or drop one here.`}</p>}
      <div class="tpl-pic-slot-acts">
        <button type="button" class="btn sm" data-act="pick" disabled={busy} onClick={() => input.current && input.current.click()}>
          {pic ? "Change picture" : "Add a picture"}
        </button>
        {pic ? <button type="button" class="btn sm quiet" data-act="out" disabled={busy}
          onClick={() => sendPicture(section, slot, null, words.removed)}>Take the picture out</button> : null}
      </div>
      <input ref={input} type="file" accept={TYPES.join(",")} class="tpl-file" tabIndex={-1} aria-hidden="true"
        onChange={(e) => { const f = e.target.files && e.target.files[0]; e.target.value = ""; take(f); }} />
    </div>
  );
}

// The pictures of every section that would publish (not left out), in bytes as the file carries them.
export function picturesTotal(sections) {
  let n = 0;
  for (const s of sections || []) {
    if (!s || s.hidden || !PICTURE_TYPES.includes(s.type)) continue;
    const v = stored(s);
    const pics = v && v.pictures && typeof v.pictures === "object" ? v.pictures : {};
    for (const p of Object.values(pics)) if (typeof p === "string") n += p.length;
  }
  return n;
}

const mb = (n) => `${(n / (1024 * 1024)).toFixed(1)} MB`;

// The running total (#96: decision 2). Publish refuses a page over 5 MB, so the warning comes before that, not past it.
export function PicturesTotal() {
  const n = picturesTotal(data.value && data.value.report_sections);
  if (!n) return null;
  const near = n >= NEAR;
  return (
    <p class={`quiet tpl-total${near ? " near" : ""}`} role="status">
      {`Pictures in this report: ${mb(n)} of the 5 MB a published page can hold, with everything else on it.`}
      {near ? " That is close to the most. Take a picture out or add smaller ones, or Publish will refuse the page." : ""}
    </p>
  );
}

export { dataBytes };
