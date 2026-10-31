// The state marks on the milestone line, as the prototype draws them (creaite's marks), as elements: no raw HTML. `name` is a
// shape name from logic/milestones.js LOOK. Colours are tokens; the white inside is the surface so a mark reads in the dark theme.
export function MsMark({ name, cls }) {
  const c = `ms-i${cls ? " " + cls : ""}`;
  switch (name) {
    case "tick-circle":
      return <svg class={c} viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="8" fill="var(--surface)" stroke="var(--status-green)" stroke-width="2" /><path d="M6 10.3l2.7 2.6L14 7.6" fill="none" stroke="var(--status-green)" stroke-width="2" /></svg>;
    case "dot":
      return <svg class={c} viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="7" fill="var(--status-green)" /></svg>;
    case "triangle":
      return <svg class={c} viewBox="0 0 20 20" aria-hidden="true"><path d="M10 3l8 14H2z" fill="var(--surface)" stroke="var(--status-amber)" stroke-width="2" stroke-linejoin="round" /><path d="M10 8v4.2M10 14.4v.3" stroke="var(--status-amber)" stroke-width="2" /></svg>;
    case "diamond":
      return <svg class={c} viewBox="0 0 20 20" aria-hidden="true"><path d="M10 2.5l7.5 7.5-7.5 7.5L2.5 10z" fill="var(--surface)" stroke="var(--status-red)" stroke-width="2" /></svg>;
    case "cross-circle":
      return <svg class={c} viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="8" fill="var(--status-red)" /><path d="M7 7l6 6M13 7l-6 6" stroke="var(--surface)" stroke-width="2" /></svg>;
    case "dashed-circle":
      return <svg class={c} viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="7" fill="var(--surface)" stroke="var(--status-blue)" stroke-width="2" stroke-dasharray="3 2.4" /></svg>;
    case "dash":
      return <svg class={c} viewBox="0 0 20 20" aria-hidden="true"><path d="M5 10h10" stroke="var(--status-grey)" stroke-width="2" /></svg>;
    default:
      return null;
  }
}
