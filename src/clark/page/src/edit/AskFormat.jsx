// Row 1217: draws an answer's blocks (askFormat.js) with elements of clark's own. Every word is a text node; nothing is read as markup.
// Row 1292: with `sources` (askCite.js), a numbered chip follows each mention of a named item's ID; it opens that item beside the panel.
import { parseAnswer } from "./askFormat.js";
import { pieces } from "./askCite.js";
import { CITE_LABEL, CITE_TITLE } from "./askWords.js";

function Nodes({ list, src, open }) {
  return list.map((n, i) => n.t === "strong" ? <strong key={i}><Nodes list={n.c} src={src} open={open} /></strong>
    : n.t === "em" ? <em key={i}><Nodes list={n.c} src={src} open={open} /></em>
    : n.t === "code" ? <code key={i}>{n.v}</code>
    : src && src.length ? pieces(n.v, src).map((p, k) => p.t === "cite"
      ? <button type="button" key={k} class="ask-cite" data-cite={p.id} aria-label={CITE_LABEL(p.n, p.id)} title={CITE_TITLE(p.id)} onClick={() => open && open(p.id)}>{p.n}</button>
      : p.v)
    : n.v);
}

function Lines({ lines, src, open }) {
  return lines.map((l, i) => <>{i ? <br /> : null}<Nodes list={l} src={src} open={open} /></>);
}

export function FormattedAnswer({ text, sources, open }) {
  return (
    <div class="ask-text ask-md">
      {parseAnswer(text).map((b, i) => {
        if (b.t === "h") { const H = "h" + (b.level + 2); return <H key={i} class="ask-h"><Nodes list={b.c} src={sources} open={open} /></H>; }
        if (b.t === "p") return <p key={i}><Lines lines={b.lines} src={sources} open={open} /></p>;
        if (b.t === "pre") return <pre key={i}><code>{b.v}</code></pre>;
        const L = b.t;
        return <L key={i} start={b.t === "ol" && b.start !== 1 ? b.start : undefined}>{b.items.map((it, k) => <li key={k}><Lines lines={it} src={sources} open={open} /></li>)}</L>;
      })}
    </div>
  );
}
