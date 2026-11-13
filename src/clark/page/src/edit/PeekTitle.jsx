// The peek's title, edited in place as plain text (a work item's, not a milestone's): a click puts the caret in it, Enter or a click away
// saves, Esc puts the old title back, and a blank or too long title stays as typed, with the section title's own sentence and the caret back in the box. One change, one Undo in the toast.
// The title is the column the page lists as the item's title (an action's or a RAID item's `description`, a decision's `decision`);
// clark never says it back in a reply, so the data is read again after a save.
import { useLayoutEffect, useRef } from "preact/hooks";
import { changeCell, say, refresh } from "../stores/changes.js";
import { titleProblem } from "./actions.js";
import { tableOf } from "./itemEdit.js";
import { plainBox, read, show } from "./Title.jsx";

export const TITLE_ITEM_MAX = __CLARK_ITEM_TITLE_MAX__;      // #942: clark/changes.py ITEM_TITLE_MAX, written in by the build (dev/tools/build_page.py page_limits); the one source

export function PeekTitle({ row }) {
  const ref = useRef(null), now = useRef(row.title), cancelled = useRef(false), refused = useRef(false);
  now.current = row.title;
  useLayoutEffect(() => { const el = ref.current; if (el && read(el) !== row.title && document.activeElement !== el) show(el, row.title); }, [row.title]);
  useLayoutEffect(() => { show(ref.current, row.title); }, []);
  const commit = () => {
    const el = ref.current;
    if (cancelled.current) { cancelled.current = false; return; }
    const t = read(el).replace(/\s+/g, " ").trim();
    if (t === now.current) { show(el, now.current); return; }
    const problem = titleProblem(t, TITLE_ITEM_MAX);
    if (problem) { refused.current = true; say("problem", problem); setTimeout(() => { refused.current = false; el.focus(); }, 0); return; }
    const field = row.kind === "decision" ? "decision" : "description";
    changeCell(tableOf(row), row.id, { [field]: t }, { text: `Title of ${row.id} changed.`, back: `Title of ${row.id} is back as it was.`, place: "peek" })
      .then((reply) => (reply ? refresh() : show(el, now.current)));
  };
  // Focus goes to the peek's close button when the box lets go of it (not back into the box: the title shown is then not refreshed after an Undo), as the milestone peek refocuses its button.
  const settle = () => { if (refused.current) return; const b = ref.current.closest("#peek")?.querySelector("[data-pk-close]"); if (b && document.activeElement !== b) b.focus(); };
  const onKeyDown = (e) => {
    if (e.isComposing) return;
    if (e.key === "Enter") { e.preventDefault(); ref.current.blur(); settle(); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); cancelled.current = true; show(ref.current, now.current); ref.current.blur(); settle(); }
  };
  return plainBox({ ref, class: "pk-title-in", "data-pk-title-in": row.id, "aria-label": `Title of ${row.id}`, onBlur: commit, onKeyDown, spellcheck: true });
}
