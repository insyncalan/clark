// One document (#96), store type "onedoc": its Edit part. The file (Choose the file…: clark's file window, then the copy into the
// client folder's "Report files" folder, fileRoute.js; choosing another replaces it on the section, never in the folder), the words
// shown for it and the lines under it, saved together with Save. Each is one change: one step, one Undo, place "report".
import { useState, useEffect, useRef } from "preact/hooks";
import { oneDoc, fileOf } from "../../templates/files.js";
import { FileRow } from "../../templates/DocLinks.jsx";
import { chooseFile } from "./fileRoute.js";
import { StartPrompt } from "../StartPrompt.jsx";
import { stored, oneLine, labelProblem, saveContent, plainWords, withPlainWords, paragraphsOf, linesProblem } from "./filesEdit.js";

// The words under the file are Not rich (row 1288): plain lines in a box, saved with Save; the store allows TEXT_LINES paragraphs of LINE_MAX characters (onedoc.py).
const LINES = 6, EACH = 600, BAD_WORDS = `The words under the file can be ${LINES} paragraphs of ${EACH} characters at most. Shorten them and try again.`;

export function Edit({ section }) {
  const content = stored(section);
  const savedLabel = typeof content.label === "string" ? content.label : "";
  const savedWords = plainWords(content.html, content.text);
  const [label, setLabel] = useState(savedLabel);
  const [words, setWords] = useState(savedWords);
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);
  const seen = useRef(section.body);
  useEffect(() => {                       // a save or an Undo brought another body: show it (never on the first draw, which would undo typing)
    if (seen.current === section.body) return;
    seen.current = section.body;
    setLabel(savedLabel);
    setWords(savedWords);
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
    const shown = oneLine(label);
    const wordsChanged = words !== savedWords;         // words left alone keep what is stored (an old file's formatting stays until they are typed over)
    const why = labelProblem(shown) || (wordsChanged ? linesProblem(paragraphsOf(words), LINES, EACH, BAD_WORDS) : "");
    setProblem(why);
    if (why) return;
    saveContent(section, { ...(wordsChanged ? withPlainWords(content, words) : content), label: shown }, "Saved.");
  };
  const fid = `tpl-${section.id}`;
  const changed = oneLine(label) !== savedLabel || words !== savedWords;
  return (
    <div class="tpl-edit tpl-files-edit">
      {file ? <p class="tpl-od-file"><FileRow file={file} label={d ? d.label : ""} /></p>
        : <><StartPrompt id="one-doc" /><p class="quiet tpl-empty">No file yet. Choose the file: until then this section stays out of the published page.</p></>}
      <div class="tpl-actions">
        <button type="button" class="btn" data-add-file disabled={busy} onClick={pick}>
          {busy ? "Choosing a file…" : file ? "Choose another file…" : "Choose the file…"}</button>
      </div>
      <form class="tpl-form" onSubmit={save} data-save>
        <label for={`${fid}-label`}>Words to show for the file (optional)</label>
        <input id={`${fid}-label`} type="text" autocomplete="off" value={label} onInput={(e) => setLabel(e.currentTarget.value)} />
        <label for={`${fid}-words`}>Words under the file (optional)</label>
        <textarea id={`${fid}-words`} rows={3} autocomplete="off" value={words} onInput={(e) => setWords(e.currentTarget.value)} />
        <button type="submit" class="btn" disabled={!changed}>Save</button>
      </form>
      {problem ? <p class="tpl-problem" role="alert">{problem}</p> : null}
      <p class="quiet tpl-hint">The file is copied into the client folder's “Report files” folder and opens from the client's copy of the report.</p>
    </div>
  );
}
