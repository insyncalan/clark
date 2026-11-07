// The peek's title, edited in place as plain text (a work item's, not a milestone's): a click puts the caret in it, Enter or a click away
// saves, Esc puts the old title back, and an empty title is put back with the section title's own sentence. One change, one Undo in the toast.
// The title is the column the page lists as the item's title (an action's or a RAID item's `description`, a decision's `decision`);
// clark never says it back in a reply, so the data is read again after a save.
import { useLayoutEffect, useRef } from "preact/hooks";
import { changeCell, say, refresh } from "../stores/changes.js";
import { titleProblem } from "./actions.js";
import { tableOf } from "./itemEdit.js";
import { plainBox, read, show } from "./Title.jsx";

export const TITLE_ITEM_MAX = __CLARK_ITEM_TITLE_MAX__;      // #942: clark/changes.py ITEM_TITLE_MAX, written in by the build (dev/tools/build_page.py page_limits); the one source

export function PeekTitle({ row }) {
  const ref = useRef(null), now = useRef(row.title), cancelled = useRef(false);
  now.current = row.title;
  useLayoutEffect(() => { const el = ref.current; if (el && read(el) !== row.title && document.activeElement !== el) show(el, row.title); }, [row.title]);
  useLayoutEffect(() => { show(ref.current, row.title); }, []);
  const commit = () => {
    const el = ref.current;
    if (cancelled.current) { cancelled.current = false; return; }
    const t = read(el).replace(/\s+/g, " ").trim();
    if (t === now.current) { show(el, now.current); return; }
    const problem = titleProblem(t, TITLE_ITEM_MAX);
    if (problem) { show(el, now.current); say("problem", problem); return; }
    const field = row.kind === "decision" ? "decision" : "description";
    changeCell(tableOf(row), row.id, { [field]: t }, { text: `Title of ${row.id} changed.`, back: `Title of ${row.id} is back as it was.`, place: "peek" })
      .then((reply) => (reply ? refresh() : show(el, now.current)));
  };
  const onKeyDown = (e) => {
    if (e.isComposing) return;
    if (e.key === "Enter") { e.preventDefault(); ref.current.blur(); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); cancelled.current = true; show(ref.current, now.current); ref.current.blur(); }
  };
  return plainBox({ ref, class: "pk-title-in", "data-pk-title-in": row.id, "aria-label": `Title of ${row.id}`, onBlur: commit, onKeyDown, spellcheck: true });
}
