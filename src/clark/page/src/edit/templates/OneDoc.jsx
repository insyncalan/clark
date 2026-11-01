// One document (#96), store type "onedoc": its Edit part. The file (Choose the file…: clark's file window, then the copy into the
// client folder's "Report files" folder, fileRoute.js; choosing another replaces it on the section, never in the folder), the words
// shown for it and the lines under it, saved together with Save. Each is one change: one step, one Undo, place "report".
import { useState, useEffect, useRef } from "preact/hooks";
import { oneDoc, fileOf } from "../../templates/files.js";
import { FileRow } from "../../templates/DocLinks.jsx";
import { chooseFile } from "./fileRoute.js";
import { stored, oneLine, paragraphsOf, linesProblem, labelProblem, saveContent } from "./filesEdit.js";

export const TEXT_LINES = 6, LINE_MAX = 600;
export const BAD_TEXT = `The words under the file can be ${TEXT_LINES} paragraphs of ${LINE_MAX} characters at most. Shorten them and try again.`;

export function Edit({ section }) {
  const content = stored(section);
  const savedLabel = typeof content.label === "string" ? content.label : "";
  const savedText = (Array.isArray(content.text) ? content.text : []).filter((t) => typeof t === "string").join("\n");
  const [label, setLabel] = useState(savedLabel);
  const [text, setText] = useState(savedText);
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);
  const seen = useRef(section.body);
  useEffect(() => {                       // a save or an Undo brought another body: show it (never on the first draw, which would undo typing)
    if (seen.current === section.body) return;
    seen.current = section.body;
    setLabel(savedLabel); setText(savedText);
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
    const words = oneLine(label), lines = paragraphsOf(text);
    const why = labelProblem(words) || linesProblem(lines, TEXT_LINES, LINE_MAX, BAD_TEXT);
    setProblem(why);
    if (why) return;
    saveContent(section, { ...content, label: words, text: lines }, "Saved.");
  };
  const fid = `tpl-${section.id}`;
  const changed = oneLine(label) !== savedLabel || paragraphsOf(text).join("\n") !== savedText;
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
        <label for={`${fid}-text`}>Words under the file (optional, one paragraph a line)</label>
        <textarea id={`${fid}-text`} rows={3} value={text} onInput={(e) => setText(e.currentTarget.value)} />
        <button type="submit" class="btn" disabled={!changed}>Save</button>
      </form>
      {problem ? <p class="tpl-problem" role="alert">{problem}</p> : null}
      <p class="quiet tpl-hint">The file is copied into the client folder's “Report files” folder and opens from the client's copy of the report.</p>
    </div>
  );
}
