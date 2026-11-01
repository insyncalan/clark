// The other pages as a shell: Work items and the Dashboard (Dashboard.jsx) sit in one frame of the same width (
// "Make Dashboard same width as work items"). The Work items list is WorkItems.jsx (#36).
import { useEffect, useState } from "preact/hooks";
import { skeleton, reduced } from "../stores/motion.js";
import { status, message, project, projects, projectsState, openProject, tryAgain, view, isFile } from "../stores/report.js";

import { MsBlock } from "./MsBlock.jsx";

// The placeholder shown while a project's data is on its way: grey blocks in the shape of the screen, drawn still (no
// shimmer), and only if the wait is longer than SKELETON_AFTER_MS, so data that arrives at once never flashes one. A published
// file has its data inside it and no wait, so it never draws one. The words are for a screen reader; the blocks are hidden from it.
export const SKELETON_AFTER_MS = 150;

const BLOCKS = {
  work: () => (
    <>
      <span class="skel skel-line wide" />
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <div class="skel-row" key={i}><span class="skel skel-line" /><span class="skel skel-line wide" /><span class="skel skel-line" /><span class="skel skel-line" /></div>
      ))}
    </>
  ),
  milestones: () => [0, 1, 2, 3, 4].map((i) => <div class="skel-row one" key={i}><span class="skel skel-line wide" /></div>),
  dashboard: () => (
    <>
      <div class="skel-tiles">{[0, 1, 2].map((i) => <span class="skel skel-tile" key={i} />)}</div>
      {[0, 1, 2].map((i) => <div class="skel-sec" key={i}><span class="skel skel-line half" /><span class="skel skel-line wide" /><span class="skel skel-line wide" /></div>)}
    </>
  ),
};

function Loading() {
  const [late, setLate] = useState(false);
  useEffect(() => {
    if (isFile()) return undefined;
    skeleton.value = null;
    const t = setTimeout(() => { setLate(true); skeleton.value = view.value; }, SKELETON_AFTER_MS);
    return () => clearTimeout(t);
  }, []);
  if (!late) return null;
  const Shape = BLOCKS[view.value] || BLOCKS.work;
  return (
    <section class="frame skel-frame">
      <h1 class="sr">Loading</h1>
      <p class="sr">Opening {project.value}.</p>
      <div class="skel-body" aria-hidden="true"><span class="skel skel-title" /><Shape /></div>
    </section>
  );
}

// When the data arrives after a placeholder was drawn, the placeholder fades out over --dur-instant on top of the screen. It
// never takes a click, and it is not drawn at all when the page may not move, where the screen replaces it at once.
export function Leaving() {
  const shape = skeleton.value, still = reduced();
  useEffect(() => {
    if (!shape) return undefined;
    if (still) { skeleton.value = null; return undefined; }
    const t = setTimeout(() => { skeleton.value = null; }, 600);      // if the animation event never comes
    return () => clearTimeout(t);
  }, [shape, still]);
  if (!shape || still) return null;
  const Shape = BLOCKS[shape] || BLOCKS.work;
  return (
    <div class="frame skel-frame skel-leave" aria-hidden="true" onAnimationEnd={() => { skeleton.value = null; }}>
      <div class="skel-body"><span class="skel skel-title" /><Shape /></div>
    </div>
  );
}

function Empty({ title, children, action }) {
  return <section class="frame empty"><h1>{title}</h1><p class="muted">{children}</p>{action}</section>;
}

export function Milestones({ tools }) {
  const More = tools && tools.MilestoneMore;      // the owner's extra block under the Plan view (#136): Edit only, so a published page has none
  return (
    <section class="frame milestones" id="milestones">
      <h1>Milestones</h1>
      <MsBlock place="page" />
      {More ? <More /> : null}
    </section>
  );
}

export function Settings({ tools }) {
  const ClientFolder = tools && tools.ClientFolder;      // the client folder (#43); the rest of Settings is FR-1
  const Personal = tools && tools.Personal;            // Settings › Personal (#45): Edit's page only; a published file has no Settings
  const Diagnostics = tools && tools.Diagnostics;        // logs and diagnostics (#110)
  const Safety = tools && tools.Safety;                  // the backups (#111); a published file has none
  const AskSettings = tools && tools.AskSettings;        // asking: the switch and its folders (#47)
  return (
    <>
      <Empty title="Settings">Settings are not ready yet.</Empty>
      {ClientFolder ? <ClientFolder /> : null}
      {Personal ? <Personal /> : null}
      {Diagnostics ? <Diagnostics /> : null}
      {Safety ? <Safety /> : null}
      {AskSettings ? <AskSettings /> : null}
    </>
  );
}

// The "No project open" screen: the projects to choose from or, when there are none (or the list could not be read), what to do.
function NoProject() {
  const list = projects.value, state = projectsState.value;
  if (state === "loading") return <Empty title="No project open">Looking for projects.</Empty>;
  if (state === "failed") return <Empty title="No project open" action={<button type="button" class="again" onClick={tryAgain}>Try again</button>}>{message.value}</Empty>;
  if (!list.length) {
    return (
      <section class="frame empty">
        <h1>No project open</h1>
        <p class="muted">There are no projects yet.</p>
        <p class="muted">To look around with made-up projects, close clark and start it again with <code>python3 -m clark --demo</code>.</p>
      </section>
    );
  }
  return (
    <section class="frame empty">
      <h1>No project open</h1>
      <p class="muted">Choose a project.</p>
      <ul class="plain choose">{list.map((p) => <li key={p.code}><button type="button" class="link" onClick={() => openProject(p.code)}>{p.name}</button> <span class="muted num">{p.code}</span></li>)}</ul>
    </section>
  );
}

export function Gate() {
  const s = status.value;
  if (s === "none") return <NoProject />;
  if (s === "loading") return isFile() ? <Empty title="Loading">Opening {project.value}.</Empty> : <Loading key={project.value} />;
  if (s === "missing") return <Empty title="That project isn't here">{message.value || "Check the project's code."}</Empty>;
  if (s === "failed") return <Empty title="Something went wrong" action={<button type="button" class="again" onClick={tryAgain}>Try again</button>}>{message.value}</Empty>;
  return null;
}
