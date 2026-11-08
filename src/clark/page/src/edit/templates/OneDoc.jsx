// One document (#96), store type "onedoc": its Edit part. The file (Choose the file…: clark's file window, then the copy into the
// client folder's "Report files" folder, fileRoute.js; choosing another replaces it on the section, never in the folder), the words
// shown for it and the lines under it, saved together with Save. Each is one change: one step, one Undo, place "report".
import { useState, useEffect, useRef } from "preact/hooks";
import { oneDoc, fileOf } from "../../templates/files.js";
import { FileRow } from "../../templates/DocLinks.jsx";
import { chooseFile } from "./fileRoute.js";
import { stored, oneLine, labelProblem, saveContent, wordsAsHtml, noBreaks } from "./filesEdit.js";
import { RichField } from "../RichField.jsx";

export function Edit({ section }) {
  const content = stored(section);
  const savedLabel = typeof content.label === "string" ? content.label : "";
  const [label, setLabel] = useState(savedLabel);
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);
  const seen = useRef(section.body);
  useEffect(() => {                       // a save or an Undo brought another body: show it (never on the first draw, which would undo typing)
    if (seen.current === section.body) return;
    seen.current = section.body;
    setLabel(savedLabel);
  }, [section.body]);
  const file = fileOf(content.file);
  const d = oneDoc(section);

  const pick = async () => {
    setProblem("");
    setBusy(true);
    try { await chooseFile(section.id); } finally { setBusy(false); }
  };
  const save = (e) => {
    e.preventDefault();
    const words = oneLine(label);
    const why = labelProblem(words);
    setProblem(why);
    if (why) return;
    saveContent(section, { ...content, label: words }, "Saved.");
  };
  const fid = `tpl-${section.id}`;
  const changed = oneLine(label) !== savedLabel;
  return (
    <div class="tpl-edit tpl-files-edit">
      {file ? <p class="tpl-od-file"><FileRow file={file} label={d ? d.label : ""} /></p>
        : <p class="quiet tpl-empty">No file yet. Choose the file: until then this section stays out of the published page.</p>}
      <div class="tpl-actions">
        <button type="button" class="btn" data-add-file disabled={busy} onClick={pick}>
          {busy ? "Choosing a file…" : file ? "Choose another file…" : "Choose the file…"}</button>
      </div>
      <form class="tpl-form" onSubmit={save} data-save>
        <label for={`${fid}-label`}>Words to show for the file (optional)</label>
        <input id={`${fid}-label`} type="text" autocomplete="off" value={label} onInput={(e) => setLabel(e.currentTarget.value)} />
        <button type="submit" class="btn" disabled={!changed}>Save</button>
      </form>
      <div class="tpl-form tpl-rich-words">
        <span class="tpl-lbl">Words under the file (optional)</span>
        <RichField field="onedoc" empty="Click to write." id={section.id} value={wordsAsHtml(content.html, content.text)} label="Words under the file"
          save={(html) => saveContent(section, { ...content, html: noBreaks(html), text: [] }, "Saved.")} />
      </div>
      {problem ? <p class="tpl-problem" role="alert">{problem}</p> : null}
      <p class="quiet tpl-hint">The file is copied into the client folder's “Report files” folder and opens from the client's copy of the report.</p>
    </div>
  );
}
