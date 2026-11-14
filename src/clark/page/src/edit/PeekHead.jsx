// Row 1180: the peek's head under the toolbar. The item's ID in a small outlined tag with the project's name beside it (said once), and the
// title edited in place in a textarea (all four kinds). Click, or Tab to it: Enter saves, Esc puts the old title back, leaving the box saves;
// a blank or unchanged title changes nothing. One change, one Undo in the toast ("Title changed"), one line in Activity (the server's).
import { useLayoutEffect, useRef } from "preact/hooks";
import { project, reread } from "../stores/report.js";
import { changeCell, changeMilestone, say, refresh } from "../stores/changes.js";
import { titleProblem } from "./actions.js";
import { tableOf } from "./itemEdit.js";
import { TITLE_ITEM_MAX } from "./PeekTitle.jsx";
import { textChange } from "./msPeek.js";

// The shared box. `save(text)` resolves to true when the title was saved (or stays false when refused, and the box keeps what was typed).
function TitleArea({ value, label, attrs, check, save }) {
  const ref = useRef(null), now = useRef(value), cancelled = useRef(false), refused = useRef(false);
  now.current = value;
  const grow = () => { const el = ref.current; if (!el) return; el.style.height = "auto"; el.style.height = `${el.scrollHeight}px`; };
  useLayoutEffect(() => { const el = ref.current; if (el && document.activeElement !== el) { el.value = value; } grow(); }, [value]);
  useLayoutEffect(() => { ref.current.value = value; grow(); }, []);
  const settle = () => { if (refused.current) return; const b = ref.current && ref.current.closest("#peek")?.querySelector("[data-pk-close]"); if (b && document.activeElement !== b) b.focus(); };
  const commit = async () => {
    const el = ref.current;
    if (cancelled.current) { cancelled.current = false; return; }
    const t = el.value.replace(/\s+/g, " ").trim();
    if (!t || t === now.current) { el.value = now.current; grow(); return; }
    const problem = check ? check(t) : "";
    if (problem) { refused.current = true; say("problem", problem); setTimeout(() => { refused.current = false; el.focus(); }, 0); return; }
    const ok = await save(t);
    if (!ok) { el.value = now.current; grow(); }
  };
  const onKeyDown = (e) => {
    if (e.isComposing) return;
    if (e.key === "Enter") { e.preventDefault(); ref.current.blur(); settle(); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); cancelled.current = true; ref.current.value = now.current; grow(); ref.current.blur(); settle(); }
  };
  return <textarea class="pkh-title-in pk-title-in" ref={ref} rows={1} spellcheck={true} aria-label={label} title="Click to edit the title"
    {...attrs} onInput={grow} onBlur={commit} onKeyDown={onKeyDown} />;
}

// A work item's title (an action's or a RAID item's `description`, a decision's `decision`): <PeekItemTitle row={row} />
export function PeekItemTitle({ row }) {
  const field = row.kind === "decision" ? "decision" : "description";
  const save = (t) => changeCell(tableOf(row), row.id, { [field]: t }, { text: "Title changed", back: "Title is back as it was.", place: "peek" })
    .then((reply) => { if (reply) refresh(); return !!reply; });
  return <TitleArea value={row.title} label={`Title of ${row.id}`} attrs={{ "data-pk-title-in": row.id }} check={(t) => titleProblem(t, TITLE_ITEM_MAX)} save={save} />;
}

// A milestone's name: <PeekMilestoneTitle m={m} />
export function PeekMilestoneTitle({ m }) {
  const save = async (t) => {
    const c = textChange("name", m.name, t, { required: true });
    if (!c) return true;
    const res = await changeMilestone({ id: m.id, changes: c, place: "peek" }, "Title changed");
    if (!res.ok) { say("problem", res.message); return false; }
    await reread(project.value);
    return true;
  };
  return <TitleArea value={m.name} label={`Name of ${m.id}`} attrs={{ "data-ms-field": "name" }} check={(t) => (t.length > 200 ? "The name can be at most 200 characters." : "")} save={save} />;
}
