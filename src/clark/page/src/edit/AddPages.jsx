// Settings, Reports: the Pages card (row 1252, Classic only). The Add page row with its cap line and meter, the list of the project's pages (the prebuilt Gantt
// page first, then each added page in menu order) and, under a page's Configure button, the Configure group: Name, Menu position, Shown to the client, Sections,
// Hide from the menu, Remove page. The prebuilt Gantt page counts as one of the five ALWAYS, hidden or shown. Every change is one step with Undo (added_pages).
// The Add page button asks for the Add page box (AddPageBox.jsx) with the document event below; this card opens it.
import { useEffect, useRef, useState } from "preact/hooks";
import { signal } from "@preact/signals";
import { data, project, shownTabs, titleOf, show } from "../stores/report.js";
import { change, undo } from "../stores/changes.js";
import { classicTheme } from "../components/Contents.jsx";
import { editorOn, clientOn, requestFor } from "../gantt/ganttTab.js";
import { MAX_ADDED_PAGES } from "../logic/templates.js";
import { AddPageBox } from "./AddPageBox.jsx";

export const ADD_PAGE_EVENT = "clark:add-page";
const WORDS = {
  add: "A custom page for %, built from a template, then named, placed and marked client or internal",
  cap: `Up to ${MAX_ADDED_PAGES} added pages per project`,
  full: `You have ${MAX_ADDED_PAGES} added pages. Remove one to add another.`,
  gantt: "Hidden from you and from the client. Counts as one of the 5. Sections built in: Header and Text, Gantt, Work items.",
  name: "Shown in the menu and at the top of the page.",
  position: "After Gantt, before Settings. Move one step at a time, with Undo.",
  client: "Off: the page is in the editor only, not in the published report.",
  sections: "Built from the starter's templates. Open the page to change them with Add a template below. Sections you add by hand cannot be Gantt or Work items; only the Gantt template contains them.",
  hide: "The page and its sections are kept; it stays here to switch back on.",
  remove: "Deletes the page and its sections. Undo stays for this session.",
};
const lastMove = signal(null);      // { code, steps }: the steps of the last Menu position move, which the strip's Undo takes back
const sorted = (pages) => [...pages].sort((a, b) => (a.sort_order - b.sort_order) || (a.id < b.id ? -1 : 1));
const slug = (t) => "ap-" + t.toLowerCase().replace(/[^a-z]+/g, "-") + "-n";
const upd = (id, changes) => ({ kind: "added_pages", op: "update", id, changes });

// A Configure row: name and help line at the left, the control at the right (the Settings row's own look). `id` names a control the label can point at.
function Row({ id, name, help, children }) {
  return (
    <div class="set-row">
      <div class="set-row-text">
        <div class="set-row-name">{id ? <label for={id}>{name}</label> : <span id={slug(name)}>{name}</span>}</div>
        <small>{help}</small>
      </div>
      <div class="set-row-ctl" role={id ? undefined : "group"} aria-labelledby={id ? undefined : slug(name)}>{children}</div>
    </div>
  );
}

function Configure({ page, pages }) {
  const [typed, setTyped] = useState(null);
  const busy = useRef(false);
  const shown = typed === null ? page.name : typed;
  const visible = pages.filter((p) => p.hidden !== 1), at = visible.findIndex((p) => p.id === page.id);
  const save = async () => {
    if (typed === null || busy.current) return;
    busy.current = true;
    const r = typed.trim() === page.name ? true : await change(upd(page.id, { name: typed }), "", { silent: true });
    busy.current = false;
    setTyped(null);       // a refused name shows the server's words (the toast) and the old name comes back
    return r;
  };
  const move = async (by) => {
    const other = visible[at + by];
    if (!other) return;
    const order = pages.map((p) => p.id);
    const i = order.indexOf(page.id), j = order.indexOf(other.id);
    [order[i], order[j]] = [order[j], order[i]];
    const steps = [];
    for (let k = 0; k < order.length; k++) {
      const p = pages.find((x) => x.id === order[k]);
      if (p.sort_order === k) continue;
      const r = await change(upd(p.id, { sort_order: k }), "", { silent: true });
      if (!r) break;
      steps.push(r.apply_id);
    }
    lastMove.value = steps.length ? { code: project.value, steps } : null;
  };
  const back = async () => { const steps = [...lastMove.value.steps].reverse(); lastMove.value = null; for (const s of steps) await undo(s); };
  const flag = (field) => (e) => change(upd(page.id, { [field]: e.currentTarget.checked ? 1 : 0 }), "", { silent: true });
  const remove = () => change({ kind: "added_pages", op: "delete", id: page.id }, `Removed “${page.name}”.`);
  const tabs = shownTabs.value.filter((v) => v !== "published");
  return (
    <div id="ap-configure" class="ap-configure">
      <h3>Configure: {page.name}</h3>
      <Row id="ap-name" name="Name" help={WORDS.name}>
        <input id="ap-name" type="text" value={shown} maxLength={60} onInput={(e) => setTyped(e.currentTarget.value)} onBlur={save}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); save(); } else if (e.key === "Escape") setTyped(null); }} />
      </Row>
      <Row name="Menu position" help={WORDS.position}>
        <div class="ap-pos">
          <ol class="ap-strip">{tabs.map((v) => <li key={v} aria-current={v === "page:" + page.id ? "true" : undefined}>{titleOf(v)}</li>)}</ol>
          <div class="ap-acts">
            <button type="button" id="ap-left" class="btn" disabled={at <= 0} onClick={() => move(-1)}>Move left</button>
            <button type="button" id="ap-right" class="btn" disabled={at < 0 || at >= visible.length - 1} onClick={() => move(1)}>Move right</button>
            <button type="button" id="ap-undo" class="btn" disabled={!(lastMove.value && lastMove.value.code === project.value)} onClick={back}>Undo</button>
          </div>
        </div>
      </Row>
      <Row id="ap-client" name="Shown to the client" help={WORDS.client}>
        <input type="checkbox" id="ap-client" checked={page.client === 1} onChange={flag("client")} />
      </Row>
      <Row name="Sections" help={WORDS.sections}>
        <button type="button" id="ap-open" class="btn" onClick={() => show("page:" + page.id)}>Open the page</button>
      </Row>
      <Row id="ap-hide" name="Hide from the menu" help={WORDS.hide}>
        <input type="checkbox" id="ap-hide" checked={page.hidden === 1} onChange={flag("hidden")} />
      </Row>
      <Row name="Remove page" help={WORDS.remove}>
        <button type="button" id="ap-remove" class="btn" onClick={remove}>Remove page</button>
      </Row>
    </div>
  );
}

export function AddPages() {
  const [open, setOpen] = useState("");
  const [box, setBox] = useState(null);       // the Add page box: { opener } while it is open
  useEffect(() => {
    const ask = (e) => setBox({ opener: (e.detail && e.detail.opener) || null });
    document.addEventListener(ADD_PAGE_EVENT, ask);
    return () => document.removeEventListener(ADD_PAGE_EVENT, ask);
  }, []);
  if (!classicTheme() || !data.value) return null;
  const p = data.value.project || {}, pages = sorted(data.value.added_pages || []);
  const used = pages.length + 1, full = used >= MAX_ADDED_PAGES;       // the prebuilt Gantt page is one of the five, hidden or shown
  const current = pages.find((x) => x.id === open) || null;
  const off = () => change(requestFor("editor", false), "The Gantt tab is off for you.");
  return (
    <section class="frame setting ap" id="add-pages" aria-labelledby="add-pages-h">
      <h2 id="add-pages-h" tabIndex={-1}>Pages</h2>
      <div class="set-row">
        <div class="set-row-text"><div class="set-row-name"><span>Add page</span></div><small>{WORDS.add.replace("%", p.name || project.value)}</small></div>
        <div class="set-row-ctl">
          <button type="button" id="add-page" class="btn pri" disabled={full}
            onClick={(e) => document.dispatchEvent(new CustomEvent(ADD_PAGE_EVENT, { detail: { opener: e.currentTarget } }))}>Add page</button>
        </div>
      </div>
      {full ? <p class="ap-limit" role="status">{WORDS.full}</p> : null}
      <ul class="ap-list plain">
        <li class="ap-page ap-gantt">
          <div class="ap-text"><b class="ap-name">Gantt</b><small>{WORDS.gantt}</small></div>
          <span class="st">{`You: ${editorOn(p) ? "on" : "off"}`}</span><span class="st">{`Client: ${clientOn(p) ? "on" : "off"}`}</span>
          {editorOn(p) ? <button type="button" id="ap-gantt-remove" class="btn" onClick={off}>Remove page</button> : null}
        </li>
        {pages.map((x) => (
          <li key={x.id} class="ap-page">
            <div class="ap-text"><b class="ap-name">{x.name}</b></div>
            <button type="button" class="btn ap-cfg" aria-expanded={open === x.id ? "true" : "false"} onClick={() => setOpen(open === x.id ? "" : x.id)}>Configure</button>
          </li>
        ))}
      </ul>
      <div class="ap-foot"><div class="ap-bar" aria-hidden="true"><i style={{ width: `${Math.min(100, used * 20)}%` }} /></div>
        <p class="ap-meter">{`${used} of ${MAX_ADDED_PAGES} added pages`}</p><p class="ap-cap muted">{WORDS.cap}</p></div>
      {current ? <Configure key={current.id} page={current} pages={pages} /> : null}
      {box && !full ? <AddPageBox project={p} opener={box.opener} onClose={() => setBox(null)} /> : null}
    </section>
  );
}
