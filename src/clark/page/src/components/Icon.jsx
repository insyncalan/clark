// One of the page's icons as elements, never raw HTML (creaite v2.6.9 `system/templates/dashboard/src/components/Icon.jsx`,
// with only the icons clark's Work items needs; the shapes are creaite's `core/dom.js` ICONS). Hidden from screen readers:
// the words beside an icon carry the meaning.
const ICONS = {
  plus: '<path d="M12 5v14M5 12h14"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  chevdown: '<path d="m6 9 6 6 6-6"/>',
};
const SHAPES = new Set(["path", "circle", "rect", "line", "polyline", "polygon", "ellipse"]);
const PARSED = {};

// An icon's shapes as element data: [["path", {d: "..."}]]. Only plain SVG shapes and their attributes are kept.
export function iconShapes(name) {
  if (PARSED[name]) return PARSED[name];
  const src = String(ICONS[name] || ""), out = [];
  for (const m of src.matchAll(/<([a-z]+)((?:\s+[a-z-]+="[^"]*")*)\s*\/?>/g)) {
    if (!SHAPES.has(m[1])) continue;
    const attrs = {};
    for (const a of m[2].matchAll(/([a-z-]+)="([^"]*)"/g)) if (!/^on/i.test(a[1])) attrs[a[1]] = a[2];
    out.push([m[1], attrs]);
  }
  PARSED[name] = out;
  return out;
}

export function Icon({ name, cls }) {
  return (
    <svg class={`i${cls ? " " + cls : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
      stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" data-icn={name}>
      {iconShapes(name).map(([tag, attrs], i) => { const T = tag; return <T key={i} {...attrs} />; })}
    </svg>
  );
}
