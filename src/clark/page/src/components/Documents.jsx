// The Supporting documents section (#74), as a reader sees it: in the page clark serves (View) and in a published file. Each
// document is a link with its title, its kind, its date and the site it goes to, so a title can never hide where it goes. Text
// nodes only: a title is never read as markup. The section is left out (Dashboard) while it has no document to show.
import { data, fromFile } from "../stores/report.js";
import { visibleDocs, docHref, isMail, factsOf } from "../logic/documents.js";

export function Documents() {
  const docs = visibleDocs(data.value, fromFile.value);
  if (!docs.length) return <p class="quiet">No documents yet.</p>;
  return (
    <ul class="tpl-dl docs-list">
      {docs.map((doc, n) => (
        <li key={n} class="tpl-dl-i">
          <span class="tpl-badge">{doc.kind || "Link"}</span>
          <span class="tpl-main">
            <a class="tpl-name" href={docHref(doc.url)} rel="noopener noreferrer" target={isMail(doc.url) ? undefined : "_blank"}>{doc.title}</a>
            <span class="tpl-facts">{factsOf(doc)}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}
