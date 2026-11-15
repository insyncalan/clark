// Row 1217: draws an answer's blocks (askFormat.js) with elements of clark's own. Every word is a text node; nothing is read as markup.
import { parseAnswer } from "./askFormat.js";

function Nodes({ list }) {
  return list.map((n, i) => n.t === "strong" ? <strong key={i}><Nodes list={n.c} /></strong>
    : n.t === "em" ? <em key={i}><Nodes list={n.c} /></em>
    : n.t === "code" ? <code key={i}>{n.v}</code>
    : n.v);
}

function Lines({ lines }) {
  return lines.map((l, i) => <>{i ? <br /> : null}<Nodes list={l} /></>);
}

export function FormattedAnswer({ text }) {
  return (
    <div class="ask-text ask-md">
      {parseAnswer(text).map((b, i) => {
        if (b.t === "h") { const H = "h" + (b.level + 2); return <H key={i} class="ask-h"><Nodes list={b.c} /></H>; }
        if (b.t === "p") return <p key={i}><Lines lines={b.lines} /></p>;
        if (b.t === "pre") return <pre key={i}><code>{b.v}</code></pre>;
        const L = b.t;
        return <L key={i} start={b.t === "ol" && b.start !== 1 ? b.start : undefined}>{b.items.map((it, k) => <li key={k}><Lines lines={it} /></li>)}</L>;
      })}
    </div>
  );
}
