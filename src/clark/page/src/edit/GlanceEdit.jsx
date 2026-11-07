// The At a glance controls (Edit only, #45), handed to the page as `tools.glance`: a tile's grip (drag, or Alt with the arrows), its
// eye (hide it from the published report), a right-click menu for its outline colour, and Project health's pill menu and reason box.
// Nothing here is in a published file.
import { useEffect, useRef, useState } from "preact/hooks";
import { RichText } from "./RichText.jsx";
import { richOrPlain } from "../logic/richOrPlain.js";
import { richWords } from "../logic/richWords.js";
import { Menu, MenuPanel } from "../components/Menu.jsx";
import { Icon } from "../components/Icon.jsx";
import { OUTLINE_CHOICES, TILE_TITLES } from "../glanceTiles.js";
import { data } from "../stores/report.js";
import { note } from "./notes.js";
import { hideTile, outlineTile, moveTile, stepOne, dropTile, pendingHealth, pickHealth, sendHealth, sendReason } from "./glanceActions.js";

const THRESHOLD = 4;

// The tile `key` dragged to (x, y): { before: key | null, mark: { key, side } } from where the pointer is among the tiles.
function target(order, key, x, y) {
  let best = null;
  for (const el of document.querySelectorAll(`.glance > .tcell`)) {
    const r = el.getBoundingClientRect(), cx = (r.left + r.right) / 2, cy = (r.top + r.bottom) / 2, dist = Math.hypot(x - cx, (y - cy) * 2);
    if (!best || dist < best.dist) best = { dist, key: el.dataset.tile, left: x < cx };
  }
  if (!best) return null;
  const i = order.indexOf(best.key);
  return { before: best.left ? best.key : order[i + 1] || null, mark: { key: best.key, side: best.left ? "left" : "right" } };
}

function startDrag(e, grip, key, order) {
  if (e.button !== 0 || order.length < 2) return;
  e.preventDefault();
  const sx = e.clientX, sy = e.clientY;
  let dragging = false, cancelled = false, aim = null;
  try { grip.setPointerCapture(e.pointerId); } catch (x) { /* a pointer that cannot be captured still drags */ }
  grip.focus();
  const move = (m) => {
    if (cancelled) return;
    if (!dragging && Math.hypot(m.clientX - sx, m.clientY - sy) < THRESHOLD) return;
    dragging = true;
    aim = target(order, key, m.clientX, m.clientY);
    dropTile.value = aim ? aim.mark : null;
  };
  const esc = (k) => { if (k.key === "Escape") { cancelled = true; aim = null; dropTile.value = null; } };
  const end = (u) => {
    document.removeEventListener("keydown", esc);
    grip.removeEventListener("pointermove", move);
    grip.removeEventListener("pointerup", end);
    grip.removeEventListener("pointercancel", end);
    dropTile.value = null;
    if (dragging && !cancelled && u.type === "pointerup" && aim) moveTile(key, aim.before, order, "report");
  };
  document.addEventListener("keydown", esc);
  grip.addEventListener("pointermove", move);
  grip.addEventListener("pointerup", end);
  grip.addEventListener("pointercancel", end);
}

function Cell({ tile, order, children }) {
  const [menu, setMenu] = useState(false);
  const grip = useRef(null), box = useRef(null);
  const title = TILE_TITLES[tile.key], drop = dropTile.value && dropTile.value.key === tile.key ? ` drop-${dropTile.value.side}` : "";
  const onKey = (e) => {
    if (!e.altKey || e.ctrlKey || e.metaKey) return;
    const dir = e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : 0;
    if (!dir) return;
    e.preventDefault();
    stepOne(tile.key, dir, order);
  };
  return (
    <div class={`tcell${tile.key === "health" ? " health" : ""}${tile.hidden ? " is-hidden" : ""}${drop}`} data-tile={tile.key} ref={box}
      onContextMenu={(e) => { e.preventDefault(); setMenu(true); }}>
      <button type="button" class="tgrip" ref={grip} data-edit-only data-tile-grip aria-keyshortcuts="Alt+ArrowLeft Alt+ArrowRight"
        aria-label={`Move ${title}. Press Alt with the left or right arrow, or drag. Right-click for its outline colour.`}
        onKeyDown={onKey} onPointerDown={(e) => startDrag(e, grip.current, tile.key, order)}>
        <svg viewBox="0 0 12 18" width="10" height="14" aria-hidden="true" focusable="false"><g fill="currentColor"><circle cx="3" cy="3" r="1.5" /><circle cx="9" cy="3" r="1.5" /><circle cx="3" cy="9" r="1.5" /><circle cx="9" cy="9" r="1.5" /><circle cx="3" cy="15" r="1.5" /><circle cx="9" cy="15" r="1.5" /></g></svg>
      </button>
      {tile.key === "health" ? null : (
        <button type="button" class="teye" data-edit-only data-tile-eye aria-pressed={tile.hidden ? "true" : "false"}
          aria-label={tile.hidden ? `Show ${title} in the published report` : `Hide ${title} from the published report`}
          title={tile.hidden ? "Hidden from the published report. Show it." : "Hide from the published report"} onClick={() => hideTile(tile.key, !tile.hidden)}>
          <Icon name={tile.hidden ? "eyeoff" : "eye"} />
        </button>
      )}
      {children}
      {tile.hidden ? <span class="tag hid thid">Hidden from the published report</span> : null}
      {menu ? (
        <MenuPanel label={`Outline colour for ${title}`} cls="left tilemenu" fade anchor={grip.current} onClose={() => setMenu(false)}>
          <div class="lab" role="presentation">Outline colour</div>
          {OUTLINE_CHOICES.map(([value, name]) => (
            <button key={value || "auto"} type="button" role="menuitemradio" aria-checked={tile.outline === value ? "true" : "false"} tabIndex={-1} data-outline={value || "auto"}
              onClick={() => { setMenu(false); outlineTile(tile.key, value); }}>{(tile.outline === value ? "✓ " : "") + name}</button>
          ))}
        </MenuPanel>
      ) : null}
    </div>
  );
}

const ITEMS = [["On track", "g"], ["At risk", "a"], ["Off track", "r"]];

function HealthPill({ health, reason }) {
  const rag = (ITEMS.find((i) => i[0] === health) || [0, "n"])[1];
  return (
    <Menu label={health || "Not set"} btnCls={`pill hpill ${rag} pillbtn`} ariaLabel={`Project health: ${health || "not set"}. Change it`} id="health-pill" menuId="health-menu" menuLabel="Project health"
      items={ITEMS.map(([name, r]) => ({ id: name, name, pill: r, checked: name === health }))} onPick={(h) => pickHealth(h, health, reason)} chevron={false} left />
  );
}

// The reason, in place (item 1005: the one rich editor, with the / menu). A click opens it; it is saved when the field is left, and Esc
// puts the old words back. It is drawn as richOrPlain of what is stored (an old reason is plain text), never the stored text itself.
// A health picked while it was empty opens it, and is saved with it.
function Reason({ health, reason }) {
  const [open, setOpen] = useState(false);
  const view = useRef(null), back = useRef(false);
  const pending = pendingHealth.value;                 // for the box's look; the save reads the signal itself, as it is when the box is left
  useEffect(() => { if (pending) setOpen(true); }, [pending]);
  useEffect(() => { if (!open && back.current) { back.current = false; if (view.current) view.current.focus(); } }, [open]);
  let shown = "";
  try { shown = richOrPlain(reason); } catch (e) { shown = ""; }
  const save = async (html) => {
    const words = richWords(html).trim(), pend = pendingHealth.value;
    if (pend) {
      pendingHealth.value = "";
      if (!words) { note("Nothing was changed. A health change needs a reason."); return true; }
      const done = await sendHealth(pend, html);
      if (!done) pendingHealth.value = pend;            // it failed (the toast says why): the health still waits for its reason
      return done || null;
    }
    if (!words && health && health !== "On track") { note("Say why in a line or two. The reason stays as it was."); return true; }
    return (await sendReason(words ? html : "")) || null;
  };
  const close = (refocus) => {
    back.current = refocus === true;
    if (pendingHealth.value && refocus !== true) { pendingHealth.value = ""; note("Nothing was changed. A health change needs a reason."); }
    else if (pendingHealth.value) pendingHealth.value = "";
    setOpen(false);
  };
  if (open) {
    return <div class={`hreason edit rich${pending ? " needs" : ""}`} data-reason><RichText value={shown} label="Why the project has this health" onSave={save} onClose={close} /></div>;
  }
  return (
    <div class="hreason edit rt-view" ref={view} data-reason role="button" tabindex="0" aria-label="Why the project has this health. Edit it"
      onClick={(e) => { if (!e.target.closest("a")) setOpen(true); }}
      onKeyDown={(e) => { if ((e.key === "Enter" || e.key === " ") && e.target === e.currentTarget) { e.preventDefault(); setOpen(true); } }}>
      {shown ? <div class="prose" dangerouslySetInnerHTML={{ __html: shown }} /> : <p class="quiet">{pending ? `Why is it ${pending}?` : "Say why"}</p>}
    </div>
  );
}

// The line under the tiles in Edit: what a tile can do. Edit only; the published page never carries it.
function Hint() {
  return <p class="glance-hint" data-glance-hint>Drag a tile to move it, or hold Alt and press an arrow key. Use the eye to hide or show a tile. Right-click a tile to change its colour. Hidden tiles are left out of the published page.</p>;
}

export const GLANCE = { Cell, HealthPill, Reason, Hint };
