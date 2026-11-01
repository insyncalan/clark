// One section of the report (#65). In Edit, `tools` (edit/) adds the gutter control (grip, + and menu) and the editable title; View
// never renders any of them, so they are not in the page at all.
// A 'Needs from you' section (#121) is a table of rows: view only here and in a published file, edited in place in Edit (edit/NeedsEdit.jsx).
// A text section's body (Summary, This week, Next week; #74) is drawn only in a published file, view-only: the publish build
// cleaned it (publish.clean_html) before it wrote the file, and the file holds nothing else. A published file draws no other type
// (Dashboard leaves those sections out of it, so a client never reads that something is missing). The page clark serves never
// draws a saved body as markup until the one editor and the page's cleanHtml arrive (#66); there, every section shows one quiet
// line, the same for every type.
import { dropAt, fromFile } from "../stores/report.js";
import { isChanged, WORD } from "../stores/changed.js";
import { anchorId } from "../logic/minimap.js";
import { Glance } from "./Glance.jsx";
import { UseCases } from "./UseCases.jsx";
import { MsBlock } from "./MsBlock.jsx";
import { Needs } from "./Needs.jsx";

export function Section({ section, index, count, slot, anchor, tools, onExport }) {
  const editing = !!tools;
  const hidden = section.hidden ? 1 : 0;
  const drop = editing && dropAt.value ? dropAt.value : null;      // what a drag would draw (#95)
  const mark = !drop ? "" : drop.line === "before" && drop.ids.includes(section.id) ? " drop-before"
    : drop.outline === section.id ? ` drop-${drop.side}` : "";
  const changed = isChanged(section.id);
  return (
    <article class={`sec slot-${slot}${hidden ? " is-hidden" : ""}${changed ? " is-changed" : ""}${mark}`}
      id={anchor || anchorId(section.id)} tabIndex={-1} data-id={section.id} data-type={section.type} data-changed={changed ? "1" : undefined}>
      {editing ? <tools.Gutter section={section} count={count} /> : null}
      <header class="sec-head">
        <h2 class="sec-h">{editing ? <tools.Title section={section} /> : section.title}</h2>
        {changed ? <span class="tag chg">{WORD}</span> : null}
        {editing && hidden ? <span class="tag hid">Left out of the published page</span> : null}
      </header>
      {section.type === "glance" ? <Glance tools={tools} /> : section.type === "usecases" ? <UseCases onExport={onExport} /> : section.type === "milestones" ? <MsBlock place={`sec-${section.id}`} />
        : section.type === "needs" ? (editing ? <tools.NeedsEdit section={section} /> : <Needs section={section} />)
        : editing && section.type === "text" && tools.richOn("body")
        ? <tools.RichField field="body" id={section.id} value={section.body} label={`${section.title} text`} />
        : fromFile.value && section.type === "text"
        ? (typeof section.body === "string" && section.body ? <div class="sec-body prose" dangerouslySetInnerHTML={{ __html: section.body }} /> : null)
        : <p class="quiet">Not shown on this page yet.</p>}
    </article>
  );
}
