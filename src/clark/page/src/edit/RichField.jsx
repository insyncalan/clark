// One rich field in Edit (#66): drawn as the cleaned text, and a click (or Enter on it) opens the editor in its place. The drawn
// text is always cleanHtml of what is stored, never the stored text itself, so a row written past the store can't reach the page
// as markup. Saving goes through saveRich (the seam in richSave.js).
import { useEffect, useRef, useState } from "preact/hooks";
import { cleanHtml } from "../logic/cleanHtml.js";
import { RichText } from "./RichText.jsx";
import { saveRich } from "./richSave.js";
import { makeInto } from "./makeInto.js";

const shown = (html) => { try { return cleanHtml(html || ""); } catch (e) { return ""; } };

export function RichField({ field, id, value, label, empty = "Click to write." }) {
  const [open, setOpen] = useState(false);
  const view = useRef(null), back = useRef(false);
  // Esc or Cmd/Ctrl+Enter closed the editor: the focus goes to the field's view, not to the page body (#188). A close because the
  // focus went elsewhere leaves it where the person put it.
  useEffect(() => { if (!open && back.current) { back.current = false; if (view.current) view.current.focus(); } }, [open]);
  if (open) {
    return <RichText value={value || ""} label={label} onMakeInto={makeInto} onSave={(html) => saveRich(field, id, html)} onClose={(refocus) => { back.current = refocus === true; setOpen(false); }} />;
  }
  const html = shown(value);
  return (
    <div class="rt-view" ref={view} data-edit-only data-rich={field} role="button" tabindex="0" aria-label={`Edit ${label || "text"}`}
      onClick={(e) => { if (!e.target.closest("a")) setOpen(true); }}
      onKeyDown={(e) => { if ((e.key === "Enter" || e.key === " ") && e.target === e.currentTarget) { e.preventDefault(); setOpen(true); } }}>
      {html ? <div class="sec-body prose" dangerouslySetInnerHTML={{ __html: html }} /> : <p class="quiet">{empty}</p>}
    </div>
  );
}
