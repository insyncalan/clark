// One section of the report (#65). In Edit, `tools` (edit/) adds the gutter control (grip, + and menu) and the editable title; View
// never renders any of them, so they are not in the page at all.
// A text section's body (Summary, This week, Next week; #74) is drawn only in a published file, view-only: the publish build
// cleaned it (publish.clean_html) before it wrote the file, and the file holds nothing else. A published file draws no other type
// (Dashboard leaves those sections out of it, so a client never reads that something is missing). The page clark serves never
// draws a saved body as markup until the one editor and the page's cleanHtml arrive (#66); there, every section shows one quiet
// line, the same for every type.
import { dropAt, fromFile } from "../stores/report.js";
import { anchorId } from "../logic/minimap.js";
import { Glance } from "./Glance.jsx";
import { UseCases } from "./UseCases.jsx";
import { MsBlock } from "./MsBlock.jsx";

export function Section({ section, index, count, slot, anchor, tools }) {
  const editing = !!tools;
  const hidden = section.hidden ? 1 : 0;
  const drop = editing && dropAt.value ? dropAt.value : null;      // what a drag would draw (#95)
  const mark = !drop ? "" : drop.line === "before" && drop.ids.includes(section.id) ? " drop-before"
    : drop.outline === section.id ? ` drop-${drop.side}` : "";
  return (
    <article class={`sec slot-${slot}${hidden ? " is-hidden" : ""}${mark}`}
      id={anchor || anchorId(section.id)} tabIndex={-1} data-id={section.id} data-type={section.type}>
      {editing ? <tools.Gutter section={section} count={count} /> : null}
      <header class="sec-head">
        <h2 class="sec-h">{editing ? <tools.Title section={section} /> : section.title}</h2>
        {editing && hidden ? <span class="tag hid">Left out of the published page</span> : null}
      </header>
      {section.type === "glance" ? <Glance tools={tools} /> : section.type === "usecases" ? <UseCases /> : section.type === "milestones" ? <MsBlock place={`sec-${section.id}`} />
        : editing && section.type === "text" && tools.richOn("body")
        ? <tools.RichField field="body" id={section.id} value={section.body} label={`${section.title} text`} />
        : fromFile.value && section.type === "text"
        ? (typeof section.body === "string" && section.body ? <div class="sec-body prose" dangerouslySetInnerHTML={{ __html: section.body }} /> : null)
        : <p class="quiet">Not shown on this page yet.</p>}
    </article>
  );
}
