// An archived work item in the side peek (B-5, #126; Edit parts only): read only, with one Restore, as the prototype's peek does
// (system/prototype/peek.js archHtml and wireArch). The note says why it cannot be changed; Restore puts the item back in one step
// with one Undo (stores/changes.js restoreItem) and the peek then shows it as any live item. Restore is offered in Edit only: View
// changes nothing, so there the note says to switch to Edit. The history (Activity tab) is read as for any item.
import { mode } from "../stores/report.js";
import { restoreItem } from "../stores/changes.js";
import { KIND_WORDS, dueCell, ownerOf, todayIso } from "../workItems.js";
import { Icon } from "../components/Icon.jsx";

const NOTE = "Archived, so it is read-only. It is out of the lists, the counts and the published page; nothing in it was deleted.";

// The note above the title: the Archived tag, why it is read only, and the one Restore.
export function ArchivedNote({ row }) {
  const editing = mode.value === "edit";
  const restore = () => restoreItem(row.table, row.id).then((reply) => {
    if (reply) setTimeout(() => { const b = document.querySelector("[data-pk-close]"); if (b) b.focus({ preventScroll: true }); }, 0);
    return reply;
  });
  return (
    <div class="pk-archnote" data-archived-note>
      <span class="tag arch"><Icon name="archive" />Archived</span>
      <p>{NOTE}</p>
      {editing ? <button type="button" class="btn pri" id="pkRestore" onClick={restore}>Restore</button> : null}
    </div>
  );
}

const Fact = ({ name, children }) => <div class="pk-row"><dt>{name}</dt><dd>{children}</dd></div>;

// The fields as they were, as words; nothing to type into. Then the latest update, when it has one, and the foot line.
export function ArchivedFields({ row }) {
  const editing = mode.value === "edit", decision = row.kind === "decision", due = dueCell(row, todayIso());
  return (
    <>
      <dl class="pk-fields pk-rofacts">
        <Fact name="Type">{KIND_WORDS[row.kind] || row.kind}</Fact>
        <Fact name="Status">{row.status || "—"}</Fact>
        {decision ? null : <Fact name="Priority">{row.priority || "—"}</Fact>}
        <Fact name={decision ? "Decision by" : "Owner"}>{ownerOf(row.owner).text === "—" ? "No owner" : ownerOf(row.owner).text}</Fact>
        <Fact name={decision ? "Date" : "Due"}>{due.date === "—" ? "No date" : due.date}</Fact>
        {decision ? null : <Fact name="Workstream">{row.workstream || "—"}</Fact>}
        {decision ? null : <Fact name="Milestone">{row.milestone || "None"}</Fact>}
      </dl>
      {row.latest_update ? <><div class="pk-lab">Latest update</div><div class="pk-text pk-update">{row.latest_update}</div></> : null}
      <p class="pk-saved muted">{editing ? "Restore it to make a change" : "Switch to Edit to restore it"}</p>
    </>
  );
}
