// One rich field in Edit (#66): drawn as the cleaned text, and a click (or Enter on it) opens the editor in its place. The drawn
// text is always cleanHtml of what is stored, never the stored text itself, so a row written past the store can't reach the page
// as markup. Saving goes through saveRich (the seam in richSave.js), or through `save(html)` when a field brings its own write
// (a use case's standing text, which has a write kind of its own).
import { useEffect, useRef, useState } from "preact/hooks";
import { cleanHtml } from "../logic/cleanHtml.js";
import { RichText } from "./RichText.jsx";
import { saveRich } from "./richSave.js";

const shown = (html) => { try { return cleanHtml(html || ""); } catch (e) { return ""; } };

// A field may bring a look and a few controls of its own (the At a glance Reason): `cls` and `attrs` go on the view and on the open box, `aria` is the
// view's name instead of "Edit <label>", `forceOpen` opens it from outside (a health picked with no reason yet), `onClose(refocus)` is told when it closes.
export function RichField({ field, id, value, label, empty = "Click to write.", save, viewId, labelledBy, cls = "", attrs = null, aria = "", forceOpen = false, onClose = null, oneLine = false }) {
  const [open, setOpen] = useState(false);
  const view = useRef(null), back = useRef(false);
  // Esc or Cmd/Ctrl+Enter closed the editor: the focus goes to the field's view, not to the page body (#188). A close because the
  // focus went elsewhere leaves it where the person put it.
  useEffect(() => { if (!open && back.current) { back.current = false; if (view.current) view.current.focus(); } }, [open]);
  useEffect(() => { if (forceOpen) setOpen(true); }, [forceOpen]);
  if (open) {
    const editor = <RichText oneLine={oneLine} value={value || ""} label={label} onSave={(html) => (save ? save(html) : saveRich(field, id, html))} onClose={(refocus) => { back.current = refocus === true; if (onClose) onClose(refocus); setOpen(false); }} />;
    return cls ? <div class={`${cls} rich`} {...(attrs || {})}>{editor}</div> : editor;
  }
  const html = shown(value);
  return (
    <div class={cls ? `rt-view ${cls}` : "rt-view"} ref={view} data-edit-only data-rich={field} role="button" tabindex="0" id={viewId} aria-label={labelledBy ? undefined : (aria || `Edit ${label || "text"}`)} aria-labelledby={labelledBy} {...(attrs || {})}
      onClick={(e) => { if (!e.target.closest("a")) setOpen(true); }}
      onKeyDown={(e) => { if ((e.key === "Enter" || e.key === " ") && e.target === e.currentTarget) { e.preventDefault(); setOpen(true); } }}>
      {html ? <div class="sec-body prose" dangerouslySetInnerHTML={{ __html: html }} /> : <p class="quiet">{empty}</p>}
    </div>
  );
}
