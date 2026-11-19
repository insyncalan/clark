// Documents and links (item 1194), store type "doclinks": its Edit part. Two icon buttons (add a file: clark's file window, then the copy
// into the client folder's "Report files" folder, fileRoute.js; add a link: a small box with the address and its description, which is
// required), then the list with rename in place, move up and down, and Remove. Each is one change: one step, one Undo, place "report".
import { useState, useRef } from "preact/hooks";
import { docItems, linkProblem } from "../../templates/files.js";
import { EntryRow } from "../../templates/DocLinks.jsx";
import { ActIcon } from "../../templates/docIcons.jsx";
import { chooseFile } from "./fileRoute.js";
import { stored, oneLine, labelProblem, saveContent } from "./filesEdit.js";
import * as W from "../../logic/docLinksWords.js";

export const MAX_ITEMS = 20;
export const FULL = `A Documents and links section can hold ${MAX_ITEMS} files and links at most. Remove one, then add the new one.`;

const Icon = ({ d }) => <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d={d} /></svg>;
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
  const [boxProblem, setBoxProblem] = useState("");
  const linkIcon = useRef(null);
  const root = useRef(null);
  const content = stored(section);
  const raw = Array.isArray(content.items) ? content.items : [];
  const full = raw.length >= MAX_ITEMS;

  const save = (items, words) => saveContent(section, { ...content, items }, words);
  const remove = (n) => {
    const item = raw[n];
    save(raw.filter((_, i) => i !== n), item && item.kind === "file" ? W.REMOVED_FILE(item.label || item.name || item.href) : W.REMOVED(item ? item.label || item.name || item.href : ""));
  };
  const move = async (n, by) => {
    const to = n + by;
    if (to < 0 || to >= raw.length) return;
    const items = raw.slice();
    [items[n], items[to]] = [items[to], items[n]];
    const reply = await save(items, W.MOVED);
    if (reply && root.current) {
      const button = root.current.querySelector(`[data-row="${to}"] [${by < 0 ? "data-up" : "data-down"}]:not([disabled])`) || root.current.querySelector(`[data-row="${to}"] [data-up]:not([disabled]), [data-row="${to}"] [data-down]:not([disabled])`);
      if (button) button.focus();
    }
  };
  // The name is a box in place: Enter or leaving it saves, Esc puts the old name back, an empty or unchanged name is as it was.
  const rename = (n, typed, box) => {
    const words = oneLine(typed), item = raw[n];
    const was = item ? item.label || (item.kind === "file" ? item.name : "") : "";
    if (!words || !item || words === was) { if (box) box.value = was || (item && item.href) || ""; return; }
    if (labelProblem(words)) { setProblem(labelProblem(words)); if (box) box.value = was; return; }
    save(raw.map((x, i) => (i === n ? { ...x, label: words } : x)), W.RENAMED);
  };
  const addFile = async () => {
    if (full) { setProblem(FULL); return; }
    setProblem("");
    setBusy(true);
    try { await chooseFile(section.id); } finally { setBusy(false); }
  };
  const closeBox = () => { setBoxOpen(false); setHref(""); setLabel(""); setProblem(""); setBoxProblem(""); if (linkIcon.current) linkIcon.current.focus(); };
  const addLink = async (e) => {
    e.preventDefault();
    const link = href.trim(), words = oneLine(label);
    const why = full ? FULL : (linkProblem(link) ? `Link ${raw.length + 1}: ${linkProblem(link)}` : "") || (words ? labelProblem(words) : W.NO_DESCRIPTION(raw.length + 1));
    setBoxProblem(why);
    if (why) return;
    const reply = await save([...raw, { kind: "link", href: link, label: words }], W.LINK_ADDED);
    if (reply) closeBox();
  };
  const fid = `tpl-${section.id}`;
  return (
    <div class="tpl-edit tpl-files-edit" ref={root}>
      <div class="tpl-icons">
        <button type="button" class="btn quiet tpl-icon" data-add-file disabled={busy} onClick={addFile} title={W.ADD_FILE} aria-label={W.ADD_FILE}><Icon d={FILE_ICON} /></button>
        <button type="button" class="btn quiet tpl-icon" data-open-link ref={linkIcon} aria-expanded={boxOpen} onClick={() => setBoxOpen(!boxOpen)} title={W.ADD_LINK} aria-label={W.ADD_LINK}><Icon d={LINK_ICON} /></button>
            {boxOpen ? (
        <form class="tpl-form" onSubmit={addLink} data-add-link onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); closeBox(); } }}>
          <label for={`${fid}-href`}>{W.LINK_ADDRESS_LABEL}</label>
          <input id={`${fid}-href`} type="text" inputMode="url" autocomplete="off" spellcheck={false} placeholder="https://" autofocus
            value={href} onInput={(e) => setHref(e.currentTarget.value)} />
          <label for={`${fid}-label`}>{W.DESCRIPTION_LABEL}</label>
          <input id={`${fid}-label`} type="text" autocomplete="off" aria-required="true" value={label} onInput={(e) => setLabel(e.currentTarget.value)} />
          {boxProblem ? <p class="tpl-problem" role="alert">{boxProblem}</p> : null}
          <div class="tpl-actions">
            <button type="button" class="btn quiet" onClick={closeBox}>{W.CANCEL}</button>
            <button type="submit" class="btn">{W.ADD_LINK_SUBMIT}</button>
          </div>
        </form>
      ) : null}
      </div>
      {problem ? <p class="tpl-problem" role="alert">{problem}</p> : null}
      {docItems(section).length ? (
        <ul class="tpl-dl tpl-dl-links">
          {raw.map((item, n) => {
            const i = docItems({ content: { items: [item] } })[0];
            if (!i) return null;
            const name = i.label || i.name || i.shown;
            return (
              <li key={n} data-row={n} class={`tpl-dl-i tpl-dl-${i.kind}`}>
                <EntryRow item={i} nameNode={
                  <input key={`${n}:${name}`} class="tpl-rename" data-rename-input type="text" autocomplete="off" defaultValue={name} aria-label={W.RENAME(name)}
                    onKeyDown={(e) => {
                      const box = e.currentTarget;
                      if (e.key === "Enter") { e.preventDefault(); box.dataset.done = "1"; rename(n, box.value, box); }
                      else if (e.key === "Escape") { e.preventDefault(); box.dataset.done = "1"; box.value = name; box.blur(); }
                    }}
                    onBlur={(e) => { const box = e.currentTarget; if (box.dataset.done) { delete box.dataset.done; return; } rename(n, box.value, box); }} />
                } />
                <button type="button" class="btn sm quiet tpl-icon" data-up disabled={n === 0} onClick={() => move(n, -1)} title={W.MOVE_UP(name)} aria-label={W.MOVE_UP(name)}><Icon d={UP_ICON} /></button>
                <button type="button" class="btn sm quiet tpl-icon" data-down disabled={n === raw.length - 1} onClick={() => move(n, 1)} title={W.MOVE_DOWN(name)} aria-label={W.MOVE_DOWN(name)}><Icon d={DOWN_ICON} /></button>
                <button type="button" class="btn sm quiet tpl-icon tpl-remove" onClick={() => remove(n)} title={W.REMOVE(name)} aria-label={W.REMOVE(name)}><ActIcon which="trash" /></button>
              </li>
            );
          })}
        </ul>
      ) : <p class="quiet tpl-empty">{W.EMPTY}</p>}
      <p class="tpl-allowed"><strong>{W.ALLOWED_HEAD}</strong>{" "}{W.ALLOWED_TYPES}{" "}<strong>{W.NOT_HEAD}</strong>{" "}{W.NOT_TYPES}</p>
      <p class="quiet tpl-hint">{W.RENAME_HINT} {W.NOTE}</p>
    </div>
  );
}
