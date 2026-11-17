// Work items list (row 1268, saved-view tabs): the tabs row above the filter in Edit, drawn as the approved mock-up draws it: one tab per
// saved view with its count, the dot and "Save view" / "Discard changes" when the list has moved off the on tab, a fold-out of options on the
// on tab (plain buttons in a details, not a menu box: a menu needs the icon drive of test_menu_icons_every_1138, left for a later part), and "+ New view" with a name box (an empty name is refused). The views are the Work items page's kind (logic/filterLine.js, page
// "workitemslist"), kept in this browser per project. View mode never draws this row; the filter itself is saved by the Edit part.
import { useRef, useState } from "preact/hooks";
import { project } from "../../stores/report.js";
import { local } from "../../stores/line.js";
import { say } from "../../stores/changes.js";
import { viewsGet, viewsPut, visibleViews, addView, renameView, duplicateView, deleteView, saveView, MAX_NAME } from "../../logic/filterLine.js";
import { editListOf, bodyOf, idsToShow } from "../../templates/workItemsList.js";
import { PAGE, NEEDS_NAME, applyView, tabState, lineKey } from "../../templates/workItemsViews.js";
import { lineOf } from "../../templates/workItemsLine.js";

const ITEMS = [{ id: "save", name: "Save changes" }, { id: "saveas", name: "Save as a new view…" }, { id: "rename", name: "Rename view" },
  { id: "dup", name: "Duplicate view" }, { id: "del", name: "Delete view", danger: true }];

export function Tabs({ add, section, filter, d, now, known, nameOf, apply }) {
  const code = project.value;
  const [rev, setRev] = useState(0);                       // drawn again after the views were saved
  const [picked, setPicked] = useState("");              // the tab the person picked
  const [form, setForm] = useState(null);                // { mode: "new" | "rename", name, error }
  const box = useRef(null);
  void rev;
  const views = visibleViews(viewsGet(local(), code, PAGE));
  const { active, dot } = tabState(views, filter, picked, nameOf);
  const save = (next) => { viewsPut(local(), code, next, PAGE); setRev((n) => n + 1); };
  const count = (v) => {
    const r = applyView(v, filter, known);
    if (!r.filter) return 0;
    return idsToShow(editListOf({ ...section, body: bodyOf(r.filter) }, d, now), true).length;
  };
  const pick = (v) => {
    const r = applyView(v, filter, known);
    if (r.problem) { say("problem", r.problem); return; }
    setPicked(v.id); setForm(null); apply(r.filter);
  };
  const line = () => lineOf(filter, nameOf);
  const act = (id) => {
    if (id === "save" && active) { const r = saveView(views, active.id, line()); if (r.ok) { save(r.views); say("done", "View saved."); } else say("problem", r.message); }
    else if (id === "saveas") setForm({ mode: "new", name: "", error: "" });
    else if (id === "rename" && active) setForm({ mode: "rename", name: active.name, error: "" });
    else if (id === "dup" && active) { const r = duplicateView(views, active.id); if (r.ok) { save(r.views); setPicked(r.id); say("done", "View copied."); } else say("problem", r.message); }
    else if (id === "del" && active) {
      const at = views.indexOf(active), r = deleteView(views, active.id);
      if (r.ok) { save(r.views); const next = r.views[Math.max(0, at - 1)]; setPicked(next ? next.id : ""); say("done", "View deleted."); } else say("problem", r.message);
    }
  };
  const submit = (e) => {
    e.preventDefault();
    const name = form.name.split(/\s+/).filter(Boolean).join(" ");
    if (!name) { setForm({ ...form, error: NEEDS_NAME }); return; }
    const r = form.mode === "rename" ? renameView(views, active.id, name) : addView(views, name, line());
    if (!r.ok) { setForm({ ...form, error: r.message }); return; }
    save(r.views); if (form.mode === "new") setPicked(r.id);
    setForm(null);
  };
  return (
    <div class="fviews wil-views" data-wil-views="" ref={box}>
      <div class="fvrow">
        <div class="vtabs" role="group" aria-label="Saved views">
          {views.map((v) => {
            const on = !!active && active.id === v.id, n = count(on ? { ...v, line: line() } : v);
            return (
              <span class="vt" key={v.id}>
                <button type="button" class="vtab" data-view-id={v.id} aria-pressed={on ? "true" : "false"}
                  aria-label={`${v.name}, ${n} ${n === 1 ? "item" : "items"}${on && dot ? ", the filter has changes you have not saved" : ""}`} onClick={() => pick(v)}>
                  <span>{v.name}</span><em class="num">{n}</em>{on && dot ? <i class="fdot" data-dot aria-hidden="true"></i> : null}
                </button>
                {on ? <details class="wil-vopts" data-wil-opts=""><summary class="vtabmenu" aria-label={`Options for ${v.name}`}>{"▾"}</summary>
                  <div class="wil-vopts-in">{(dot ? ITEMS : ITEMS.slice(1)).map((it) => (
                    <button type="button" key={it.id} class={it.danger ? "link danger" : "link"} data-wil-act={it.id}
                      onClick={(e) => { const dt = e.currentTarget.closest("details"); if (dt) dt.open = false; act(it.id); }}>{it.name}</button>))}</div></details> : null}
              </span>
            );
          })}
        </div>
        <button type="button" class="vnew" data-wil-new="" onClick={() => act("saveas")}>{"+ New view"}</button>
        {dot ? <span class="fvacts"><button type="button" class="btn sm" data-wil-save="" onClick={() => act("save")}>Save view</button>
          <button type="button" class="link" data-wil-discard="" onClick={() => pick(active)}>Discard changes</button></span> : null}
        {add}
      </div>
      {form ? (
        <form class="vform" onSubmit={submit} onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); setForm(null); } }}>
          <label for="wil-vname">{form.mode === "rename" ? "New name for this view" : "Name for the new view"}</label>
          <input id="wil-vname" type="text" maxLength={MAX_NAME} value={form.name} autofocus onInput={(e) => setForm({ ...form, name: e.currentTarget.value, error: "" })} />
          <button type="submit" class="btn sm">Save</button>
          <button type="button" class="btn sm" onClick={() => setForm(null)}>Cancel</button>
          <span class="vmsg" role="status">{form.error}</span>
        </form>
      ) : null}
    </div>
  );
}
