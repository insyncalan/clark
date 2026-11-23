// Documents and links (#96), store type "doclinks": its view part. The papers that go with this week's report, as one list: each
// file is a link to its copy in the client folder's "Report files" folder (relative to the report, so it opens from the client's
// copy, which sits beside that folder), each link opens its page. Text nodes only; every address through ./safe.js (files.js).
// The page clark serves names a file without linking it: the file is beside the client's copy, not beside this page.
// isEmpty: nothing that can be drawn, so the section is left out of the served View and the published file alike (FR-11).
import { fromFile } from "../stores/report.js";
import { docItems, kindWords, sizeWords, badgeWords, factsWords } from "./files.js";
import { PageIcon, ActIcon } from "./docIcons.jsx";
import * as W from "../logic/docLinksWords.js";
import { classicTheme } from "../components/Contents.jsx";

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

// Row 1221: the editor's way to read a file row's file (edit/templates/fileRoute.js sets it). The editor's View has no address for a file
// (a file's own address resolves only beside the client's copy of the report), so its Open and Download read the file through clark.
export const fileReader = { read: null };

// Cards (no Theme layered) keeps its file row as it was: Open and Download as words, in the editor's View only.
function FileActions({ file }) {
  const read = fileReader.read;
  if (!read) return null;
  return (
    <span class="tpl-acts">
      <button type="button" class="tpl-act" aria-label={`${W.UNRULED_OPEN} ${file.name}`} onClick={() => read(file.name, false)}>{W.UNRULED_OPEN}</button>
      <button type="button" class="tpl-act" aria-label={`${W.UNRULED_DOWNLOAD} ${file.name}`} onClick={() => read(file.name, true)}>{W.UNRULED_DOWNLOAD}</button>
    </span>
  );
}

// The Open and Download of a row (Classic): 44px icon buttons named for a screen reader. A link has Open on every row (in a new tab). A file has
// Open and Download as links in a published file, and as buttons that read through clark in the editor's View (when the editor set fileReader).
function Actions({ item }) {
  const name = item.label || (item.kind === "file" ? item.name : item.shown);
  if (item.kind === "link" || fromFile.value) {
    const open = <a class="tpl-act" href={item.href} target="_blank" rel="noopener noreferrer" title={W.OPEN} aria-label={`${W.OPEN} ${name}`}><ActIcon which="open" /></a>;
    if (item.kind === "link") return open;
    return (
      <>
        {open}
        <a class="tpl-act" href={item.href} download={item.name} title={W.DOWNLOAD} aria-label={`${W.DOWNLOAD} ${name}`}><ActIcon which="download" /></a>
      </>
    );
  }
  const read = fileReader.read;
  if (!read) return null;
  return (
    <>
      <button type="button" class="tpl-act" title={W.OPEN} aria-label={`${W.OPEN} ${name}`} onClick={() => read(item.name, false)}><ActIcon which="open" /></button>
      <button type="button" class="tpl-act" title={W.DOWNLOAD} aria-label={`${W.DOWNLOAD} ${name}`} onClick={() => read(item.name, true)}><ActIcon which="download" /></button>
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

function CardsView({ section }) {
  return (
    <ul class="tpl-dl">
      {docItems(section).map((i, n) => (
        <li key={n} class={`tpl-dl-i tpl-dl-${i.kind}`}>
          {i.kind === "file" ? <><FileRow file={i} label={i.label} />{fromFile.value ? null : <FileActions file={i} />}</> : (
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

function ClassicView({ section }) {
  return (
    <ul class="tpl-dl tpl-dl-links">
      {docItems(section).map((i, n) => (
        <li key={n} class={`tpl-dl-i tpl-dl-${i.kind}`}>
          <EntryRow item={i} />
          <span class="tpl-acts"><Actions item={i} /></span>
        </li>
      ))}
    </ul>
  );
}

// The look of item 1194 is Classic's; with no Theme (Cards) the list is drawn as it always was.
export function View({ section }) {
  return classicTheme() ? <ClassicView section={section} /> : <CardsView section={section} />;
}

export const isEmpty = (section) => docItems(section).length === 0;
