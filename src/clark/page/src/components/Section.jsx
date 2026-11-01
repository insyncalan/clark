// One section of the report (#65). In Edit, `tools` (edit/) adds the gutter control (grip, + and menu) and the editable title; View
// never renders any of them, so they are not in the page at all.
// A 'Needs from you' section (#121) is a table of rows: view only here and in a published file, edited in place in Edit (edit/NeedsEdit.jsx).
// A text section's body (Summary, This week, Next week; #74) is drawn only in a published file, view-only: the publish build
// cleaned it (publish.clean_html) before it wrote the file, and the file holds nothing else. A published file draws no other type
// (Dashboard leaves those sections out of it, so a client never reads that something is missing). The page clark serves never
// draws a saved body as markup in Edit until the one editor arrives (#66); there, every type but the ones below shows one quiet
// line. In View (A-D4) the page clark serves draws a text section's body, and the Current state section's text (the project's
// current_state), as the cleaned text: `clean` is the page's own cleaner (cleanHtml, from edit/index.js; the published page has none
// and has no use for one, its text is already cleaned). A published file does not draw Current state: that is a product decision.
// A section template (#96) is drawn by its own parts, looked up by type (Edit: its Edit part from tools.templateEdit, given the
// section and the tools; View and the file: its view part from templates/index.js, given the section and the report's data). Dashboard leaves a template
// with nothing to show out of View and the file, so its view part is only ever asked to draw something. No branch per template
// is ever added here. The Supporting documents section (#74) is its links: Documents.jsx in View and a file, tools.DocumentsEdit in Edit.
import { dropAt, fromFile, data } from "../stores/report.js";
import { templateFor } from "../templates/index.js";
import { anchorId } from "../logic/minimap.js";
import { Glance } from "./Glance.jsx";
import { UseCases } from "./UseCases.jsx";
import { MsBlock } from "./MsBlock.jsx";
import { emptyBody } from "../logic/emptyBody.js";
import { Needs } from "./Needs.jsx";
import { Documents } from "./Documents.jsx";

// View's text for a text or current section: cleaned HTML in the prose style, or one plain line when there is nothing to read.
function ViewText({ html }) {
  return emptyBody(html) ? <p class="quiet">Nothing recorded.</p> : <div class="sec-body prose" data-view-text dangerouslySetInnerHTML={{ __html: html }} />;
}

// A template's Edit part, from the tools (edit/templates/); the quiet line if the tools have none for it.
function TemplateEdit({ section, tools }) {
  const Edit = tools.templateEdit ? tools.templateEdit(section.type) : null;
  return Edit ? <Edit section={section} tools={tools} /> : <p class="quiet">Not shown on this page yet.</p>;
}

export function Section({ section, index, count, slot, anchor, tools, clean, onExport }) {
  const editing = !!tools;
  const hidden = section.hidden ? 1 : 0;
  const drop = editing && dropAt.value ? dropAt.value : null;      // what a drag would draw (#95)
  const mark = !drop ? "" : drop.line === "before" && drop.ids.includes(section.id) ? " drop-before"
    : drop.outline === section.id ? ` drop-${drop.side}` : "";
  const tpl = templateFor(section.type);
  return (
    <article class={`sec slot-${slot}${hidden ? " is-hidden" : ""}${mark}`}
      id={anchor || anchorId(section.id)} tabIndex={-1} data-id={section.id} data-type={section.type}>
      {editing ? <tools.Gutter section={section} count={count} /> : null}
      <header class="sec-head">
        <h2 class="sec-h">{editing ? <tools.Title section={section} /> : section.title}</h2>
        {editing && hidden ? <span class="tag hid">Left out of the published page</span> : null}
      </header>
      {section.type === "glance" ? <Glance tools={tools} /> : section.type === "usecases" ? <UseCases onExport={onExport} /> : section.type === "milestones" ? <MsBlock place={`sec-${section.id}`} />
        : tpl ? (editing ? <TemplateEdit section={section} tools={tools} /> : <tpl.view section={section} data={data.value} />)
        : section.type === "needs" ? (editing ? <tools.NeedsEdit section={section} /> : <Needs section={section} />)
        : section.type === "docs" ? (editing ? <tools.DocumentsEdit section={section} /> : <Documents />)
        : editing && section.type === "text" && tools.richOn("body")
        ? <tools.RichField field="body" id={section.id} value={section.body} label={`${section.title} text`} />
        : fromFile.value && section.type === "text"
        ? (typeof section.body === "string" && section.body ? <div class="sec-body prose" dangerouslySetInnerHTML={{ __html: section.body }} /> : null)
        : !editing && clean && (section.type === "text" || section.type === "current")
        ? <ViewText html={clean(section.type === "current" ? ((data.value && data.value.project) || {}).current_state : section.body)} />
        : <p class="quiet">Not shown on this page yet.</p>}
    </article>
  );
}
