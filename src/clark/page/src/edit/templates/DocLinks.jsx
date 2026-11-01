// Documents and links (#96), store type "doclinks": its Edit part. The list as the reader will see it, each entry with Remove; Add a
// file (clark's file window, then the copy into the client folder's "Report files" folder: fileRoute.js) and Add link (a typed
// https:// or mailto: link, with optional words to show). Each is one change: one step, one Undo, place "report".
import { useState } from "preact/hooks";
import { docItems, linkProblem } from "../../templates/files.js";
import { FileRow } from "../../templates/DocLinks.jsx";
import { chooseFile } from "./fileRoute.js";
import { stored, oneLine, labelProblem, saveContent } from "./filesEdit.js";

export const MAX_ITEMS = 20;
export const FULL = `A Documents and links section can hold ${MAX_ITEMS} files and links at most. Remove one, then add the new one.`;

export function Edit({ section }) {
  const [href, setHref] = useState("");
  const [label, setLabel] = useState("");
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);
  const content = stored(section);
  const raw = Array.isArray(content.items) ? content.items : [];
  const shown = docItems(section);
  const full = raw.length >= MAX_ITEMS;

  const remove = (n) => {
    const item = raw[n];
    const words = item && item.kind === "file" ? "File taken off the section. It stays in the client folder." : "Link removed.";
    saveContent(section, { ...content, items: raw.filter((_, i) => i !== n) }, words);
  };
  const addFile = async () => {
    if (full) { setProblem(FULL); return; }
    setProblem("");
    setBusy(true);
    try { await chooseFile(section.id); } finally { setBusy(false); }
  };
  const addLink = async (e) => {
    e.preventDefault();
    const link = href.trim(), words = oneLine(label);
    const why = full ? FULL : linkProblem(link) || labelProblem(words);
    setProblem(why);
    if (why) return;
    const reply = await saveContent(section, { ...content, items: [...raw, { kind: "link", href: link, label: words }] }, "Link added.");
    if (reply) { setHref(""); setLabel(""); }
  };
  const fid = `tpl-${section.id}`;
  return (
    <div class="tpl-edit">
      {shown.length ? (
        <ul class="tpl-dl">
          {raw.map((item, n) => {
            const i = docItems({ content: { items: [item] } })[0];
            if (!i) return null;
            return (
              <li key={n} class={`tpl-dl-i tpl-dl-${i.kind}`}>
                {i.kind === "file" ? <FileRow file={i} label={i.label} /> : (
                  <>
                    <span class="tpl-badge">Link</span>
                    <span class="tpl-main"><span class="tpl-name">{i.label || i.shown}</span>{i.label ? <span class="tpl-facts">{i.shown}</span> : null}</span>
                  </>
                )}
                <button type="button" class="btn sm quiet tpl-remove" onClick={() => remove(n)}
                  aria-label={`Remove ${i.label || i.name || i.shown}`}>Remove</button>
              </li>
            );
          })}
        </ul>
      ) : <p class="quiet tpl-empty">No files or links yet. Add one below: until then this section stays out of the published page.</p>}
      <div class="tpl-actions">
        <button type="button" class="btn" data-add-file disabled={busy} onClick={addFile}>{busy ? "Choosing a file…" : "Add a file…"}</button>
      </div>
      <form class="tpl-form" onSubmit={addLink} data-add-link>
        <label for={`${fid}-href`}>Link</label>
        <input id={`${fid}-href`} type="text" inputMode="url" autocomplete="off" spellcheck={false} placeholder="https://"
          value={href} onInput={(e) => setHref(e.currentTarget.value)} />
        <label for={`${fid}-label`}>Words to show (optional)</label>
        <input id={`${fid}-label`} type="text" autocomplete="off" value={label} onInput={(e) => setLabel(e.currentTarget.value)} />
        <button type="submit" class="btn">Add link</button>
      </form>
      {problem ? <p class="tpl-problem" role="alert">{problem}</p> : null}
      <p class="quiet tpl-hint">A file is copied into the client folder's “Report files” folder and opens from the client's copy of the report.</p>
    </div>
  );
}
