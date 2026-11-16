// Callout (#96), store type "callout": its view part. Draws one boxed note: a tone word (so the tone is never colour alone), an
// optional title and paragraphs, all as text nodes. isEmpty: no title and no paragraph (the section is then left out of the served
// View and the published file alike). The Edit part is edit/templates/Callout.jsx; the content rules are section_kinds/callout.py.
import { source, tidyCallout, calloutEmpty, calloutLook, COLOURS, ICONS } from "./notes.js";

import { CleanProse } from "../components/CleanProse.jsx";
import { Icon } from "../components/Icon.jsx";

export const READY = true;
export const isEmpty = (section) => calloutEmpty(tidyCallout(source(section)));

// The box as it is drawn in View and, with its fields typed in place, in Edit (edit/templates/Callout.jsx): colour, icon, category word. `look` is calloutLook.
export function mark(k) {
  const name = k.icon !== "none" ? k.icon : k.shape;
  return name ? <Icon name={name} cls="tpl-callout-ic" /> : null;
}
// #1272: the colour and the icon in words (for a reader who cannot tell colours apart, and a screen reader): "Colour: Violet. Icon: Light bulb." Plain has a colour name too; No icon says nothing.
export const lookWords = (k) => `Colour: ${COLOURS[k.colour]}.${k.icon !== "none" ? ` Icon: ${ICONS[k.icon]}.` : ""}`;
export const boxClass = (k) => `tpl-callout k-${k.colour}${k.icon === "none" && !k.shape ? " noic" : ""}`;

export function View({ section, clean }) {
  const c = tidyCallout(source(section), clean), k = calloutLook(c);
  return (
    <div class={boxClass(k)} role="note" data-colour={k.colour} data-icon={k.icon}>
      {mark(k)}
      <div class="tpl-callout-main">
        <span class="sr-only">{lookWords(k)}</span>
        {k.word ? <p class="tpl-callout-tone">{k.word}</p> : null}
        {c.title ? <p class="tpl-callout-h">{c.title}</p> : null}
        {c.html ? <CleanProse cls="tpl-callout-p tpl-rich prose" html={c.html} />
          : c.paras.map((p, i) => <p class="tpl-callout-p" key={i}>{p}</p>)}
      </div>
    </div>
  );
}
