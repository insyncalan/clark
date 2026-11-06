// The Help peek (#645 steps 3 to 5): a right-hand panel over the page with the context text for the screen you are on (text only) and a
// foot link to the full Help. The frame, the slide in and the slide out are the item peek's (.peek, peek/exit.js). Edit parts only:
// App.jsx mounts it from `tools`, so a published file has none. Focus goes in on open and back on close (helpStore.js gives it back).
import { useLayoutEffect, useEffect, useRef } from "preact/hooks";
import { contextOpen, contextScreen, contextOf, closeContext, openFull } from "./helpStore.js";
import { peek } from "../stores/report.js";
import { Icon } from "../components/Icon.jsx";
import { slideOut } from "../peek/exit.js";

export function HelpPeek() {
  const open = contextOpen.value, c = open ? contextOf(contextScreen.value) : null, on = !!c;
  const box = useRef(null);
  useLayoutEffect(() => {
    if (!on) return;
    const x = box.current && box.current.querySelector("[data-hpk-close]");
    if (x) x.focus();
  }, [on]);
  // An item peek that is closing as this opens gives its row the focus a moment later: the peek takes it back.
  const itemOpen = !!peek.value;
  useEffect(() => {
    if (!on || !box.current || box.current.contains(document.activeElement)) return;
    const x = box.current.querySelector("[data-hpk-close]");
    if (x) x.focus();
  }, [itemOpen]);                                         // eslint-disable-line react-hooks/exhaustive-deps
  if (!on) slideOut(box.current);                         // closed: a copy of the panel slides out
  if (!on) return null;
  return (
    <aside class="peek hpk" id="help-peek" ref={box} aria-label={`Help for ${c.title}`}>
      <div class="hpk-head">
        <h2 class="hpk-title">{c.title}</h2>
        <button type="button" class="pkp-btn" data-hpk-close title="Close" aria-label="Close" onClick={() => closeContext()}><Icon name="x" /></button>
      </div>
      {c.lines.map((l, i) => <p class="hpk-line" key={i}>{l}</p>)}
      {c.cards.length ? <ul class="hpk-cards">{c.cards.map((k, i) => <li key={i}>{k.name ? <b>{k.name}</b> : null}{k.name && k.line ? " " : ""}{k.line}</li>)}</ul> : null}
      {c.articles.length ? <><h3 class="hpk-sub">{c.articlesTitle}</h3><ul class="hpk-arts">{c.articles.map((a) => <li key={a.place}><button type="button" class="hpk-link" data-hpk-art={a.place} onClick={() => openFull(a.place)}>{a.title}</button></li>)}</ul></> : null}
      <div class="hpk-foot"><button type="button" class="hpk-link" data-hpk-full onClick={() => openFull()}>Open full Help</button></div>
    </aside>
  );
}
