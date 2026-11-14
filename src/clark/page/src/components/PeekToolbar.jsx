// Row 1180: the peek's short toolbar. Left: Close, Open full page, a thin rule, Previous item, Next item. Right: Draft email, Copy link, More.
// Self-contained: Peek.jsx hands in what each button does. A button whose handler is left out is not drawn (a read-only peek passes no
// draft, copy or more). The data-pk-prev, data-pk-next, data-pk-wide and data-pk-close hooks are the ones the old bar had.
import { Icon } from "./Icon.jsx";

// Two glyphs Icon.jsx does not have yet (mail, link), drawn here in the same 24 grid and stroke so they sit with the rest.
const OWN = { mail: ["M3 6h18v12H3z", "M3 7l9 6 9-6"], link: ["M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1", "M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"] };

export function ToolbarIcon({ name }) {
  const d = OWN[name];
  if (!d) return <Icon name={name} />;
  return (
    <svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" data-icn={name}>
      {d.map((p, i) => <path key={i} d={p} />)}
    </svg>
  );
}

/** One toolbar icon button: the words are the hover text and the screen-reader name. */
export function BarButton({ icon, words, hook, id, disabled, pressed, onClick }) {
  const hooks = hook ? { [hook]: "" } : {};
  return (
    <button type="button" class="pkp-btn" id={id} {...hooks} title={words} aria-label={words} aria-pressed={pressed} disabled={disabled} onClick={onClick}>
      <ToolbarIcon name={icon} />
    </button>
  );
}

/**
 * PeekToolbar props:
 *   near      { prev, next }  the neighbouring ids (falsy = that button is disabled)
 *   go        (id) => void    open that id
 *   wide      boolean         the panel fills the screen now
 *   onWide    () => void      toggle it
 *   onClose   () => void
 *   draft     { onClick, disabled, reason } | null   Draft email; reason is the hover text when disabled; null = not drawn
 *   onCopy    () => void | null                       Copy link; null = not drawn
 *   more      a node | null   the More menu button (PeekMore or RecordMore), drawn as it is; null = not drawn
 */
export function PeekToolbar({ near, go, wide, onWide, onClose, draft = null, onCopy = null, more = null }) {
  const wideWords = wide ? "Return the panel to its usual width" : "Open full page";
  const draftWords = draft && draft.disabled && draft.reason ? draft.reason : "Draft email";
  return (
    <div class="pk-bar pk-tb" role="toolbar" aria-label="Peek actions">
      <div class="pk-tb-grp">
        <BarButton icon="right" words="Close this panel" hook="data-pk-close" onClick={onClose} />
        <BarButton icon="arrows-out" words={wideWords} hook="data-pk-wide" pressed={!!wide} onClick={onWide} />
        <span class="pk-tb-rule" aria-hidden="true" />
        <BarButton icon="chevup" words="Previous item" hook="data-pk-prev" disabled={!near || !near.prev} onClick={() => go(near.prev)} />
        <BarButton icon="chevdown" words="Next item" hook="data-pk-next" disabled={!near || !near.next} onClick={() => go(near.next)} />
      </div>
      <span class="pk-sp" />
      <div class="pk-tb-grp">
        {draft ? <BarButton icon="mail" words={draftWords} hook="data-pk-draft" id="pk-draft" disabled={!!draft.disabled} onClick={draft.onClick} /> : null}
        {onCopy ? <BarButton icon="link" words="Copy link" hook="data-pk-copy" id="pk-copy" onClick={onCopy} /> : null}
        {more}
      </div>
    </div>
  );
}
