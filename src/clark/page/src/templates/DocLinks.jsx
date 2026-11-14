// Documents and links (#96), store type "doclinks": its view part. The papers that go with this week's report, as one list: each
// file is a link to its copy in the client folder's "Report files" folder (relative to the report, so it opens from the client's
// copy, which sits beside that folder), each link opens its page. Text nodes only; every address through ./safe.js (files.js).
// The page clark serves names a file without linking it: the file is beside the client's copy, not beside this page.
// isEmpty: nothing that can be drawn, so the section is left out of the served View and the published file alike (FR-11).
import { fromFile } from "../stores/report.js";
import { docItems, kindWords, sizeWords, badgeWords, factsWords } from "./files.js";
import { PageIcon, ActIcon } from "./docIcons.jsx";
import * as W from "../logic/docLinksWords.js";

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

// The Open and Download of a row: 44px icon buttons named for a screen reader, Open on every row (in a new tab), Download on a file only.
// A file's own address resolves only beside the client's copy of the report, so a file's actions are drawn in a published file.
function Actions({ item }) {
  const name = item.label || (item.kind === "file" ? item.name : item.shown);
  const open = <a class="tpl-act" href={item.href} target="_blank" rel="noopener noreferrer" title={W.UNRULED_OPEN} aria-label={`${W.UNRULED_OPEN} ${name}`}><ActIcon which="open" /></a>;
  if (item.kind === "link") return open;
  if (!fromFile.value) return null;
  return (
    <>
      {open}
      <a class="tpl-act" href={item.href} download={item.name} title={W.UNRULED_DOWNLOAD} aria-label={`${W.UNRULED_DOWNLOAD} ${name}`}><ActIcon which="download" /></a>
    </>
  );
}

// The name of an entry: a link in a published file, plain words in the editor's View (a link's Open is its own button).
export function EntryName({ item }) {
  const words = item.label || (item.kind === "file" ? item.name : item.shown);
  return fromFile.value
    ? <a class="tpl-name" href={item.href} target="_blank" rel="noopener noreferrer">{words}</a>
    : <span class="tpl-name">{words}</span>;
}

// One entry: the page-style icon, the name, and under it "<Type> · <size or site>".
export function EntryRow({ item, nameNode }) {
  return (
    <>
      <PageIcon label={badgeWords(item)} />
      <span class="tpl-main">
        {nameNode || <EntryName item={item} />}
        <span class="tpl-facts">{factsWords(item)}</span>
      </span>
    </>
  );
}

export function View({ section }) {
  return (
    <ul class="tpl-dl">
      {docItems(section).map((i, n) => (
        <li key={n} class={`tpl-dl-i tpl-dl-${i.kind}`}>
          <EntryRow item={i} />
          <span class="tpl-acts"><Actions item={i} /></span>
        </li>
      ))}
    </ul>
  );
}

export const isEmpty = (section) => docItems(section).length === 0;
