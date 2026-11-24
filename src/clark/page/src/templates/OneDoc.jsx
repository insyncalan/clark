// One document (#96), store type "onedoc": its view part. A single file to read, with a few lines about it: the file is a link to
// its copy in the client folder's "Report files" folder (relative to the report; the page clark serves names it without linking,
// as Documents and links does). Text nodes only; addresses through ./safe.js (files.js).
// isEmpty: no file to draw (the file is the point of the section), so it is left out of the served View and the file alike.
import { oneDoc } from "./files.js";
import { FileRow } from "./DocLinks.jsx";

export const READY = true;

export function View({ section }) {
  const d = oneDoc(section);
  if (!d) return null;
  return (
    <div class="tpl-od">
      <p class="tpl-od-file"><FileRow file={d.file} label={d.label} /></p>
      {d.text.map((t, n) => <p key={n} class="tpl-od-text">{t}</p>)}
    </div>
  );
}

export const isEmpty = (section) => oneDoc(section) === null;
