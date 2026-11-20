// Callout (item 96, item 1272), store type "callout": its Edit part, in place. A toolbar above the box (category, colour, icon, and whether the tile and the
// heading show), then the box as the reader sees it, with its title and words typed inside it (the one editor, with its / menu). Each save is one change()
// (noteEdit.jsx saveContent): one step, one Undo. The view part is templates/Callout.jsx.
import { useEffect, useRef, useState } from "preact/hooks";
import { source, tidyCallout, calloutLook, PROMPTS, TONE_WORDS, COLOURS, ICONS, LIMITS } from "../../templates/notes.js";
import { mark, boxClass } from "../../templates/Callout.jsx";
import { Field, useSaver } from "./noteEdit.jsx";
import { RichField } from "../RichField.jsx";
import { Icon } from "../../components/Icon.jsx";
import { wordsAsHtml, noBreaks } from "./filesEdit.js";
import { startOr } from "../startingText.js";

// The three words a category can be picked from: each sets the colour and the icon the old tone drew.
const SUGGESTED = { info: ["violet", "info"], decision: ["amber", "fork"], warning: ["red", "warning"] };
const SWATCH = { violet: "shViolet", amber: "shAmber", red: "shRed", green: "shGreen", grey: "shGrey" };

function IconPicker({ value, onPick }) {
  const [open, setOpen] = useState(false);
  const box = useRef(null);
  useEffect(() => {
    if (!open) return;
    const first = box.current && box.current.querySelector("[aria-selected=true]");
    if (first) first.focus();
  }, [open]);
  const close = () => { setOpen(false); const b = box.current && box.current.querySelector(".cb-icon-btn"); if (b) b.focus(); };
  const keys = (e) => {
    if (e.key === "Escape") { e.preventDefault(); close(); return; }
    const opts = [...box.current.querySelectorAll("[role=option]")], at = opts.indexOf(document.activeElement);
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (step && at >= 0) { e.preventDefault(); opts[(at + step + opts.length) % opts.length].focus(); }
  };
  return (
    <div class="cb-icon" ref={box} onKeyDown={keys}>
      <button type="button" class="cb-btn cb-icon-btn" aria-haspopup="listbox" aria-expanded={open ? "true" : "false"} aria-label="Choose an icon" onClick={() => setOpen(!open)}>
        {value !== "none" ? <Icon name={value} /> : null}<span>{ICONS[value]}</span>
      </button>
      {open ? (
        <div class="cb-icons" role="listbox" aria-label="Icon">
          {Object.keys(ICONS).map((k) => (
            <button type="button" role="option" key={k} class="cb-opt" aria-selected={k === value ? "true" : "false"} tabIndex={k === value ? 0 : -1}
              onClick={() => { onPick(k); close(); }}>
              {k !== "none" ? <Icon name={k} /> : null}<span>{ICONS[k]}</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function Edit({ section }) {
  const [typed, setTyped] = useState(null);
  const saved = tidyCallout(source(section));
  const k = calloutLook(saved);
  const write = useSaver(section, saved, "Callout saved.");
  // A change of the look also stores what an older callout was drawing, so it does not change by itself.
  const look = (patch) => write({ category: saved.category === undefined ? k.word : saved.category, colour: k.colour, icon: k.icon, ...patch });
  const suggest = (tone) => look({ tone, category: TONE_WORDS[tone], colour: SUGGESTED[tone][0], icon: SUGGESTED[tone][1] });
  return (
    <div class="tpl-edit tpl-edit-callout cb" data-tpl="callout">
      <div class="cb-bar" role="toolbar" aria-label="Callout tools">
        <div class="cb-set"><span class="cb-lbl">Category</span>
          <Field value={k.word} label="Category" max={LIMITS.category} placeholder="Type a category" cls="cb-in" onCommit={(category) => look({ category })} />
          {Object.keys(SUGGESTED).map((t) => (
            <button type="button" class="cb-btn" key={t} aria-pressed={k.word === TONE_WORDS[t] ? "true" : "false"} aria-label={`Use ${TONE_WORDS[t]}`} onClick={() => suggest(t)}>{TONE_WORDS[t]}</button>
          ))}
          <button type="button" class="cb-btn" aria-label="No category" onClick={() => look({ category: "" })}>No category</button>
        </div>
        <div class="cb-set"><span class="cb-lbl">Colour</span>
          <div class="cb-grp" role="radiogroup" aria-label="Colour">
            {Object.keys(COLOURS).map((c) => (
              <button type="button" role="radio" class={`cb-btn cb-col k-${c}`} key={c} aria-checked={k.colour === c ? "true" : "false"} aria-label={COLOURS[c]} onClick={() => look({ colour: c })}>
                <span class="cb-sw" aria-hidden="true">{SWATCH[c] ? <Icon name={SWATCH[c]} /> : null}</span><span>{COLOURS[c]}</span>
              </button>
            ))}
          </div>
        </div>
        <div class="cb-set"><span class="cb-lbl">Icon</span><IconPicker value={k.icon} onPick={(icon) => look({ icon })} /></div>
        <div class="cb-set"><span class="cb-lbl">Show</span>
          <button type="button" role="switch" class="cb-btn" aria-checked={k.tile ? "true" : "false"} aria-label="Show the tile (the card around the callout)" onClick={() => look({ tile: !k.tile })}><Icon name={k.tile ? "eye" : "eyeoff"} />Tile</button>
          <button type="button" role="switch" class="cb-btn" aria-checked={k.heading ? "true" : "false"} aria-label="Show the heading" onClick={() => look({ heading: !k.heading })}><Icon name={k.heading ? "eye" : "eyeoff"} />Heading</button>
          <span class="cb-sep" aria-hidden="true"></span>
          <span class="cb-count" data-cb-count>{`Title ${typed === null ? (saved.title || "").length : typed} of ${LIMITS.title}`}</span>
        </div>
      </div>
      <div class={boxClass(k)} data-colour={k.colour} data-icon={k.icon}>
        {mark(k)}
        <div class="tpl-callout-main">
          {k.word ? <p class="tpl-callout-tone">{k.word}</p> : null}
          <Field value={saved.title} label="Callout title" max={LIMITS.title} placeholder={PROMPTS.title} cls="cb-title" onDraft={setTyped} onCommit={(title) => write({ title })} />
          <RichField field="callout" empty={startOr(PROMPTS.words, "callout", "empty")} id={section.id} value={wordsAsHtml(saved.html, saved.paras)} label="Callout words" save={(html) => write({ html: noBreaks(html), paras: [] })} />
        </div>
      </div>
      {!saved.title && saved.paras.length === 0 && !saved.html ? <p class="quiet">Empty for now: add a title or some words. It stays out of the published page until then.</p> : null}
    </div>
  );
}
