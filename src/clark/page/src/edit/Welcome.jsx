// #174: the first-run welcome. The first time clark is opened with no name in Settings › Profile › About you, a small card asks for
// it. It saves through the same route as About you (stores/profile.js), so the name is kept by clark in the data folder, not here.
// It never blocks the page. Row 857: when it opens it puts the focus in the Name box (unless the person is already in something
// else), Tab stays inside it and Esc is Not now, like every dialog. It is asked once: it is never shown again once a name is saved (here or in
// Settings) or once Not now is chosen; that answer is remembered in this browser (clark.welcome). Skipping changes nothing else: a
// change made with no name in Settings carries this computer's login name, as before.
import { useEffect, useRef, useState } from "preact/hooks";
import { profile, profileRead, setProfile, welcomeHeld } from "../stores/profile.js";

const KEY = "clark.welcome";
const answered = () => { try { return localStorage.getItem(KEY) === "done"; } catch (e) { return false; } };
const remember = () => { try { localStorage.setItem(KEY, "done"); } catch (e) { /* a private window: closed for this visit only */ } };

export const WELCOME_WORDS = {
  head: "Welcome to clark",
  ask: "What is your name? It goes on each change you make, at the top of your menu, and on what you publish.",
  label: "Your name",
  line: "Not now leaves it empty: your changes show this computer's login name. You can add it later in Settings › Profile.",
  save: "Save",
  skip: "Not now",
  empty: "Type your name, or choose Not now.",
};

export function Welcome() {
  const [gone, setGone] = useState(answered);
  const [said, setSaid] = useState("");
  const [busy, setBusy] = useState(false);
  const box = useRef(null);
  const card = useRef(null);
  const shown = !(gone || welcomeHeld.value || !profileRead.value || profile.value.name);
  useEffect(() => {
    const a = document.activeElement;
    if (shown && box.current && (!a || a === document.body || a === document.documentElement)) box.current.focus();
  }, [shown]);
  if (gone || welcomeHeld.value || !profileRead.value || profile.value.name) return null;
  const close = () => { remember(); setGone(true); };
  const save = async () => {
    const name = box.current ? box.current.value.trim() : "";
    if (!name) { setSaid(WELCOME_WORDS.empty); return; }
    setBusy(true);
    const r = await setProfile(name, profile.value.email);
    setBusy(false);
    if (r.ok) { close(); return; }
    setSaid(r.message || "");
  };
  return (
    <section class="welcome" role="dialog" aria-modal="false" aria-labelledby="welcome-h" aria-describedby="welcome-ask" data-welcome ref={card}
      onKeyDown={(e) => {
        if (e.key === "Escape") { e.stopPropagation(); close(); return; }
        if (e.key !== "Tab") return;
        const tabs = [...card.current.querySelectorAll("input, button:not([disabled])")];
        const end = tabs[e.shiftKey ? 0 : tabs.length - 1];
        if (document.activeElement === end) { e.preventDefault(); tabs[e.shiftKey ? tabs.length - 1 : 0].focus(); }
      }}>
      <h2 id="welcome-h">{WELCOME_WORDS.head}</h2>
      <p id="welcome-ask">{WELCOME_WORDS.ask}</p>
      <form class="fld" onSubmit={(e) => { e.preventDefault(); save(); }}>
        <label for="welcome-name">{WELCOME_WORDS.label}</label>
        <input id="welcome-name" ref={box} type="text" autocomplete="name" aria-describedby="welcome-line"
          aria-invalid={said ? "true" : undefined} onInput={() => said && setSaid("")} />
        <p class="fld-bad" role="alert">{said}</p>
        <small id="welcome-line">{WELCOME_WORDS.line}</small>
        <div class="welcome-acts">
          <button type="submit" class="btn primary sm" data-welcome-save disabled={busy}>{WELCOME_WORDS.save}</button>
          <button type="button" class="btn quiet sm" data-welcome-skip onClick={close}>{WELCOME_WORDS.skip}</button>
        </div>
      </form>
    </section>
  );
}
