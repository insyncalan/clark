// Documents and links (#96), store type "doclinks": its view part. The papers that go with this week's report, as one list: each
// file is a link to its copy in the client folder's "Report files" folder (relative to the report, so it opens from the client's
// copy, which sits beside that folder), each link opens its page. Text nodes only; every address through ./safe.js (files.js).
// The page clark serves names a file without linking it: the file is beside the client's copy, not beside this page.
// isEmpty: nothing that can be drawn, so the section is left out of the served View and the published file alike (FR-11).
import { fromFile } from "../stores/report.js";
import { docItems, kindWords, sizeWords } from "./files.js";

export const READY = true;

// A file's name (or the words given for it): a link in a published file, plain words in the page clark serves.
export function FileName({ file, label }) {
  const words = label || file.name;
  return fromFile.value
    ? <a class="tpl-name" href={file.href} target="_blank" rel="noopener noreferrer">{words}</a>
    : <span class="tpl-name">{words}</span>;
}

// One file as a row: its kind, its name, and under it the file's own name (when words were given) and its size.
export function FileRow({ file, label }) {
  const facts = [label ? file.name : "", sizeWords(file.bytes)].filter(Boolean).join(" · ");
  return (
    <>
      <span class="tpl-badge">{kindWords(file.name)}</span>
      <span class="tpl-main">
        <FileName file={file} label={label} />
        {facts ? <span class="tpl-facts">{facts}</span> : null}
      </span>
    </>
  );
}

export function View({ section }) {
  return (
    <ul class="tpl-dl">
      {docItems(section).map((i, n) => (
        <li key={n} class={`tpl-dl-i tpl-dl-${i.kind}`}>
          {i.kind === "file" ? <FileRow file={i} label={i.label} /> : (
            <>
              <span class="tpl-badge">Link</span>
              <span class="tpl-main">
                <a class="tpl-name" href={i.href} target="_blank" rel="noopener noreferrer">{i.label || i.shown}</a>
                {i.label ? <span class="tpl-facts">{i.shown}</span> : null}
              </span>
            </>
          )}
        </li>
      ))}
    </ul>
  );
}

export const isEmpty = (section) => docItems(section).length === 0;
