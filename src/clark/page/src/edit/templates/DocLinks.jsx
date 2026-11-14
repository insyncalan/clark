// Documents and links (item 1194), store type "doclinks": its Edit part. Two icon buttons (add a file: clark's file window, then the copy
// into the client folder's "Report files" folder, fileRoute.js; add a link: a small box with the address and its description, which is
// required), then the list with rename in place, move up and down, and Remove. Each is one change: one step, one Undo, place "report".
import { useState, useRef } from "preact/hooks";
import { docItems, linkProblem } from "../../templates/files.js";
import { EntryRow } from "../../templates/DocLinks.jsx";
import { chooseFile } from "./fileRoute.js";
import { stored, oneLine, labelProblem, saveContent } from "./filesEdit.js";
import * as W from "../../logic/docLinksWords.js";

export const MAX_ITEMS = 20;
export const FULL = `A Documents and links section can hold ${MAX_ITEMS} files and links at most. Remove one, then add the new one.`;

const Icon = ({ d }) => <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d={d} /></svg>;
const FILE_ICON = "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z M14 3v5h5 M12 12v5 M9.5 14.5h5";
const LINK_ICON = "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1 M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1";
const UP_ICON = "M6 15l6-6 6 6";
const DOWN_ICON = "M6 9l6 6 6-6";

export function Edit({ section }) {
  const [href, setHref] = useState("");
  const [label, setLabel] = useState("");
  const [boxOpen, setBoxOpen] = useState(false);
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);
  const [renaming, setRenaming] = useState(-1);
  const linkIcon = useRef(null);
  const root = useRef(null);
  const content = stored(section);
  const raw = Array.isArray(content.items) ? content.items : [];
  const full = raw.length >= MAX_ITEMS;

  const save = (items, words) => saveContent(section, { ...content, items }, words);
  const remove = (n) => {
    const item = raw[n];
    save(raw.filter((_, i) => i !== n), item && item.kind === "file" ? "File taken off the section. It stays in the client folder." : "Link removed.");
  };
  const move = async (n, by) => {
    const to = n + by;
    if (to < 0 || to >= raw.length) return;
    const items = raw.slice();
    [items[n], items[to]] = [items[to], items[n]];
    const reply = await save(items, W.UNRULED_MOVED);
    if (reply && root.current) {
      const button = root.current.querySelector(`[data-row="${to}"] [${by < 0 ? "data-up" : "data-down"}]:not([disabled])`) || root.current.querySelector(`[data-row="${to}"] [data-up]:not([disabled]), [data-row="${to}"] [data-down]:not([disabled])`);
      if (button) button.focus();
    }
  };
  const rename = (n, typed) => {
    setRenaming(-1);
    const words = oneLine(typed), item = raw[n];
    if (!words || !item || words === item.label || (item.kind === "file" && !item.label && words === item.name)) return;   // empty or unchanged: as it was
    if (labelProblem(words)) { setProblem(labelProblem(words)); return; }
    save(raw.map((x, i) => (i === n ? { ...x, label: words } : x)), W.UNRULED_RENAMED);
  };
  const addFile = async () => {
    if (full) { setProblem(FULL); return; }
    setProblem("");
    setBusy(true);
    try { await chooseFile(section.id); } finally { setBusy(false); }
  };
  const closeBox = () => { setBoxOpen(false); setHref(""); setLabel(""); setProblem(""); if (linkIcon.current) linkIcon.current.focus(); };
  const addLink = async (e) => {
    e.preventDefault();
    const link = href.trim(), words = oneLine(label);
    const why = full ? FULL : linkProblem(link) || (words ? labelProblem(words) : W.UNRULED_NO_DESCRIPTION);
    setProblem(why);
    if (why) return;
    const reply = await save([...raw, { kind: "link", href: link, label: words }], W.UNRULED_LINK_ADDED);
    if (reply) closeBox();
  };
  const fid = `tpl-${section.id}`;
  return (
    <div class="tpl-edit tpl-files-edit" ref={root}>
      <div class="tpl-icons">
        <button type="button" class="btn quiet tpl-icon" data-add-file disabled={busy} onClick={addFile} title={W.UNRULED_ADD_FILE} aria-label={W.UNRULED_ADD_FILE}><Icon d={FILE_ICON} /></button>
        <button type="button" class="btn quiet tpl-icon" data-open-link ref={linkIcon} aria-expanded={boxOpen} onClick={() => setBoxOpen(!boxOpen)} title={W.UNRULED_ADD_LINK} aria-label={W.UNRULED_ADD_LINK}><Icon d={LINK_ICON} /></button>
      </div>
      {boxOpen ? (
        <form class="tpl-form" onSubmit={addLink} data-add-link onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); closeBox(); } }}>
          <label for={`${fid}-href`}>{W.UNRULED_LINK_ADDRESS_LABEL}</label>
          <input id={`${fid}-href`} type="text" inputMode="url" autocomplete="off" spellcheck={false} placeholder="https://" autofocus
            value={href} onInput={(e) => setHref(e.currentTarget.value)} />
          <label for={`${fid}-label`}>{W.UNRULED_DESCRIPTION_LABEL}</label>
          <input id={`${fid}-label`} type="text" autocomplete="off" aria-required="true" value={label} onInput={(e) => setLabel(e.currentTarget.value)} />
          <div class="tpl-actions">
            <button type="button" class="btn quiet" onClick={closeBox}>{W.UNRULED_CANCEL}</button>
            <button type="submit" class="btn">{W.UNRULED_ADD_LINK_SUBMIT}</button>
          </div>
        </form>
      ) : null}
      {problem ? <p class="tpl-problem" role="alert">{problem}</p> : null}
      {docItems(section).length ? (
        <ul class="tpl-dl">
          {raw.map((item, n) => {
            const i = docItems({ content: { items: [item] } })[0];
            if (!i) return null;
            const name = i.label || i.name || i.shown;
            return (
              <li key={n} data-row={n} class={`tpl-dl-i tpl-dl-${i.kind}`}>
                {renaming === n ? (
                  <>
                    <span class={`tpl-badge tpl-badge-${i.kind}`}>{i.kind === "link" ? (/^mailto:/i.test(i.href) ? "MAIL" : "URL") : "FILE"}</span>
                    <input class="tpl-rename" data-rename-input type="text" autocomplete="off" autofocus defaultValue={name} aria-label={W.UNRULED_RENAME(name)}
                      onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); rename(n, e.currentTarget.value); } else if (e.key === "Escape") { e.preventDefault(); setRenaming(-1); } }} />
                  </>
                ) : (
                  <>
                    <EntryRow item={i} />
                    <button type="button" class="btn sm quiet" data-rename onClick={() => setRenaming(n)} aria-label={W.UNRULED_RENAME(name)}>{W.UNRULED_RENAME("")}</button>
                  </>
                )}
                <button type="button" class="btn sm quiet tpl-icon" data-up disabled={n === 0} onClick={() => move(n, -1)} title={W.UNRULED_MOVE_UP(name)} aria-label={W.UNRULED_MOVE_UP(name)}><Icon d={UP_ICON} /></button>
                <button type="button" class="btn sm quiet tpl-icon" data-down disabled={n === raw.length - 1} onClick={() => move(n, 1)} title={W.UNRULED_MOVE_DOWN(name)} aria-label={W.UNRULED_MOVE_DOWN(name)}><Icon d={DOWN_ICON} /></button>
                <button type="button" class="btn sm quiet tpl-remove" onClick={() => remove(n)} aria-label={W.UNRULED_REMOVE(name)}>Remove</button>
              </li>
            );
          })}
        </ul>
      ) : <p class="quiet tpl-empty">{W.UNRULED_EMPTY}</p>}
      <p class="quiet tpl-hint">{W.UNRULED_NOTE}</p>
    </div>
  );
}
