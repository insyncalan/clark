// One use case's own page in a published file (row 1111): the same layout and classes as the page the editor has (UseCaseDetail), read only.
// It reads what the file holds (data.use_case_pages names, for each use case the client may see, the next steps and milestones to show),
// draws no control, no History and no Last change (the 20-11 decision, row 1479), and its Details card shows Owner, status and commitment, and asks for nothing. A work item opens the file's read only peek; "Open all" opens the file's Work items.
import { useEffect, useRef } from "preact/hooks";
import { data, rows, project } from "../stores/report.js";
import { refOf } from "../logic/useCasesList.js";
import { UseCaseLayout, Crumb } from "./UseCaseLayout.jsx";
import { commitWord } from "../logic/commitment.js";
import { CommitChip } from "./CommitChip.jsx";

const OWN = "[role=textbox],[role=combobox],[role=listbox],[role=menu],[role=dialog],[role=alertdialog],dialog";
const busy = (e) => !!e && e.nodeType === 1 && (e.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(e.tagName) || !!e.closest(OWN));

export function UseCaseFilePage({ id }) {
  const d = data.value, head = useRef(null);
  const u = d ? (d.use_cases || []).find((x) => x.id === id) || null : null;
  // The heading takes the focus when the page is drawn (and again when another use case is opened), never on a later redraw of the same one.
  useEffect(() => { if (head.current) head.current.focus({ preventScroll: true }); }, [id, !!d]);
  // Esc leaves for the list, as the editor's page does, unless focus is in a field or a menu, or a peek is open (the peek takes the first Esc).
  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== "Escape" || e.defaultPrevented || e.isComposing || e.metaKey || e.ctrlKey || e.altKey) return;
      if (busy(document.activeElement) || busy(e.target) || document.querySelector("dialog[open],[role=dialog],[role=alertdialog],[role=menu],[data-peek]")) return;
      const back = document.querySelector("[data-ucf] .ucf-crumb a");
      if (back) back.click();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);
  if (!d) return null;
  const listAt = `#usecases&p=${project.value}`;
  const crumb = (label) => <Crumb p="ucf" href={listAt} label={label} />;
  if (!u) return <div class="ucf" data-ucf data-missing>{crumb("Use case")}<h1 ref={head} tabIndex={-1} class="ucf-h">That use case isn't in this report</h1><p><a href={listAt}>Go back to the use cases</a>.</p></div>;
  const page = (d.use_case_pages || []).find((x) => x.id === u.id) || { next_steps: [], milestones: [] };
  const work = page.next_steps.map((n) => rows.value.find((r) => r.id === n)).filter(Boolean);
  const ms = page.milestones.map((n) => (d.milestones || []).find((m) => m.id === n)).filter(Boolean);
  const std = u.standing || "";                    // cleaned at publish (publish.select), as the Use cases tab draws it
  // The layout is the editor's (UseCaseLayout, row 1479), given no control: no menu, no hint, no add row, no History, no Last change.
  return (
    <UseCaseLayout p="ucf" u={u} name={refOf(u) || "Use case"} work={work} headRef={head} ro
      ms={ms.map((m) => ({ m, how: "Through work items" }))}
      crumb={crumb(refOf(u) || "Use case")}
      title={<span class="ucf-name ucf-ro" data-ucf-field="title">{u.title}</span>}
      sub={{ chip: <CommitChip u={u} /> }}
      headline={<span class="ucf-headline ucf-ro" data-ucf-field="headline">{u.headline || <span class="muted">No headline yet</span>}</span>}
      titleOfRow={(r) => r.client_message || r.title}
      std={std ? <div class="prose ucf-std" dangerouslySetInnerHTML={{ __html: std }} /> : <p class="muted">Not written yet.</p>}
      noWork="No work items are shared for this use case."
      owner={u.owner ? <span class="ucf-owner ucf-ro" data-ucf-field="owner">{u.owner}</span> : null}
      rows={<>
        <dt>Status</dt><dd data-det-status>{u.status}</dd>
        {commitWord(u) ? <><dt>Commitment</dt><dd data-det-commit>{commitWord(u)}</dd></> : null}
      </>}
      noMs="No milestones are shared for this use case." />
  );
}
