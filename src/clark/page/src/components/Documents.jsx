// The Supporting documents section (#74), as a reader sees it: in the page clark serves (View) and in a published file. Each
// document is a link with its title, "Kind · date" under it and an "Open {title}" icon link, as in the prototype. Text
// nodes only: a title is never read as markup. The section is left out (Dashboard) while it has no document to show.
import { data, fromFile } from "../stores/report.js";
import { visibleDocs, docHref, isMail, kindDateOf } from "../logic/documents.js";
import { Icon } from "./Icon.jsx";

export function Documents() {
  const docs = visibleDocs(data.value, fromFile.value);
  if (!docs.length) return <p class="quiet">No documents yet.</p>;
  return (
    <ul class="tpl-dl docs-list">
      {docs.map((doc, n) => (
        <li key={n} class="tpl-dl-i docs-view-row">
          <span class="docs-ic"><Icon name="doc" /></span>
          <span class="tpl-main">
            <a class="tpl-name" href={docHref(doc.url)} rel="noopener noreferrer" target={isMail(doc.url) ? undefined : "_blank"}>{doc.title}</a>
            <span class="tpl-facts">{kindDateOf(doc)}</span>
          </span>
          <a class="ib docs-open" href={docHref(doc.url)} rel="noopener noreferrer" target={isMail(doc.url) ? undefined : "_blank"} aria-label={`Open ${doc.title}`}><Icon name="ext" /></a>
        </li>
      ))}
    </ul>
  );
}
