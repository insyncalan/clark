// A section template's settings (#930, Edit only): a small popover titled with the template's name, the line "Template settings. These
// apply to this tracker only." and a group of radio options, one choice saved as one change at once. It opens from a cog on the section
// (SettingsCog) and from the item "Template settings" in the section's grip menu (edit/Gutter.jsx, which also hosts the popover).
// Escape or a click away closes it, with focus back on what opened it. A template with settings has an entry in SETTINGS, keyed by its
// type; a template with none has no cog and no menu item. Nothing here is in View or a published file.
import { signal } from "@preact/signals";
import { useEffect, useLayoutEffect, useRef } from "preact/hooks";
import { Fade } from "../components/Menu.jsx";
import { trackerSettings } from "./trackerSettings.js";
import { WORDS } from "../logic/trackerEdit.js";

export const SETTINGS = { tracker: trackerSettings };
export const hasSettings = (section) => !!SETTINGS[section.type];
export const MENU_WORD = WORDS.templateSettings;

// Which section's settings are open, and the element that opened them (focus goes back there).
export const openFor = signal(null);
export const openSettings = (section, anchor) => { openFor.value = { id: section.id, anchor }; };
export const closeSettings = (back = true) => {
  const o = openFor.value;
  openFor.value = null;
  if (back && o && o.anchor && o.anchor.isConnected) o.anchor.focus();
};

const COG = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
  </svg>
);

// The cog on the section.
export function SettingsCog({ section }) {
  const def = SETTINGS[section.type];
  if (!def) return null;
  const label = `${WORDS.templateSettings}: ${def.title}`;
  return (
    <button type="button" class="ib t-cog" data-edit-only data-template-settings aria-haspopup="dialog" aria-label={label} title={WORDS.templateSettings}
      onClick={(e) => (openFor.value && openFor.value.id === section.id ? closeSettings(false) : openSettings(section, e.currentTarget))}>{COG}</button>
  );
}

// The popover, drawn by the section's gutter while this section's settings are open.
export function SettingsPopover({ section }) {
  const o = openFor.value;
  const def = SETTINGS[section.type];
  const box = useRef(null);
  const open = !!(o && def && o.id === section.id);
  useLayoutEffect(() => {
    if (!open || !box.current) return;
    const el = box.current, a = o.anchor && o.anchor.getBoundingClientRect ? o.anchor.getBoundingClientRect() : { right: 320, bottom: 40 };
    el.style.left = `${Math.round(Math.max(8, Math.min(a.right - el.offsetWidth, window.innerWidth - el.offsetWidth - 8)))}px`;
    el.style.top = `${Math.round(a.bottom + 6)}px`;
    const on = box.current.querySelector("input:checked") || box.current.querySelector("input");
    if (on) on.focus({ preventScroll: true });
  }, [open]);
  useEffect(() => {
    if (!open) return undefined;
    const away = (e) => { if (box.current && !box.current.contains(e.target) && !(o.anchor && o.anchor.contains && o.anchor.contains(e.target))) closeSettings(false); };
    const shut = () => closeSettings(false);
    document.addEventListener("pointerdown", away, true);
    window.addEventListener("resize", shut);
    return () => { document.removeEventListener("pointerdown", away, true); window.removeEventListener("resize", shut); };
  }, [open]);
  if (!open) return null;
  const now = def.current(section);
  return (
    <Fade class="tset" boxRef={box} role="dialog" aria-label={`${WORDS.templateSettings}: ${def.title}`} data-template-settings-box data-edit-only
      onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closeSettings(true); } }}>
      <h4 class="tset-h">{def.title}</h4>
      <p class="quiet tset-line">{def.line}</p>
      <div class="tset-opts" role="radiogroup" aria-label={def.label}>
        {def.options.map(([value, name, what]) => (
          <label key={value} class={`tset-opt${value === now ? " on" : ""}`}>
            <input type="radio" name={`tset-${section.id}`} value={value} checked={value === now} onChange={() => { if (value !== now) def.save(section, value); }} />
            <span><b>{name}</b><small>{what}</small></span>
          </label>
        ))}
      </div>
    </Fade>
  );
}
