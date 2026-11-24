// Callout (#96), store type "callout": its view part. Draws one boxed note: a tone word (so the tone is never colour alone), an
// optional title and paragraphs, all as text nodes. isEmpty: no title and no paragraph (the section is then left out of the served
// View and the published file alike). The Edit part is edit/templates/Callout.jsx; the content rules are section_kinds/callout.py.
import { source, tidyCallout, calloutEmpty, TONE_WORDS } from "./notes.js";

export const READY = true;
export const isEmpty = (section) => calloutEmpty(tidyCallout(source(section)));

export function View({ section }) {
  const c = tidyCallout(source(section));
  return (
    <div class={`tpl-callout tone-${c.tone}`} role="note">
      <p class="tpl-callout-tone">{TONE_WORDS[c.tone]}</p>
      {c.title ? <p class="tpl-callout-h">{c.title}</p> : null}
      {c.paras.map((p, i) => <p class="tpl-callout-p" key={i}>{p}</p>)}
    </div>
  );
}
