// One section of the report (#65). In Edit, `tools` (edit/) adds the handle, the editable title, the options menu and Add; View
// never renders any of them, so they are not in the page at all.
// A text section's body (Summary, This week, Next week; #74) is drawn only in a published file, view-only: the publish build
// cleaned it (publish.clean_html) before it wrote the file, and the file holds nothing else. A published file draws no other type
// (Dashboard leaves those sections out of it, so a client never reads that something is missing). The page clark serves never
// draws a saved body as markup until the one editor and the page's cleanHtml arrive (#66); there, every section shows one quiet
// line, the same for every type.
import { dropAt, fromFile } from "../stores/report.js";

export function Section({ section, index, count, slot, tools }) {
  const editing = !!tools;
  const hidden = section.hidden ? 1 : 0;
  const drop = editing && dropAt.value ? dropAt.value : null;      // what a drag would draw (#95)
  const mark = !drop ? "" : drop.line === "before" && drop.ids.includes(section.id) ? " drop-before"
    : drop.outline === section.id ? ` drop-${drop.side}` : "";
  return (
    <article class={`sec slot-${slot}${hidden ? " is-hidden" : ""}${mark}`}
      id={`sec-${section.id}`} data-id={section.id} data-type={section.type}>
      <header class="sec-head">
        {editing ? <tools.Handle section={section} count={count} /> : null}
        <h2 class="sec-h">{editing ? <tools.Title section={section} /> : section.title}</h2>
        {editing && hidden ? <span class="tag hid">Hidden from the published report</span> : null}
        {editing ? <tools.Options section={section} index={index} count={count} /> : null}
      </header>
      {fromFile.value && section.type === "text"
        ? (typeof section.body === "string" && section.body ? <div class="sec-body prose" dangerouslySetInnerHTML={{ __html: section.body }} /> : null)
        : <p class="quiet">Not shown on this page yet.</p>}
      {editing ? <tools.Add after={section.id} /> : null}
    </article>
  );
}
