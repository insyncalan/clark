// The Key figures templates' shared view (#96): the figures in a row, drawn as the At a glance figures are. Text nodes only. The
// colour is never the only signal: the figure's words say it (aria-label), and the dot is decoration.
import { data } from "../stores/report.js";
import { todayIso } from "../workItems.js";
import { figuresOf, countOf } from "./figures.js";

const WORDS = { g: "green", a: "amber", r: "red" };

export function FigureRow({ list, type, count }) {
  return (
    <div class={`tpl-figs n${count}`} data-figures={type}>
      {list.map((f, i) => (
        <div class={`fig rag-${f.rag}`} role="group" data-fig="figure" key={i}
          aria-label={`${f.label}: ${f.value}${f.detail ? ", " + f.detail : ""}${f.asof ? ", as of " + f.asof : ""}${WORDS[f.rag] ? ", " + WORDS[f.rag] : ""}`}>
          <span class="k"><i class="ragdot" aria-hidden="true"></i>{f.label}</span>
          <span class="v num">{f.value}</span>
          {f.detail ? <span class="dd">{f.detail}</span> : null}
          {f.asof ? <span class="dd">As of {f.asof}</span> : null}
        </div>
      ))}
    </div>
  );
}

// The view part and isEmpty for one of the two stored types (row 1263: the one Numbers card reads both; the count is the body's or the type's).
export function figuresParts(type) {
  const list = (section, d) => figuresOf(section, d || data.value, todayIso(), countOf(section, type));
  return {
    View: ({ section, data: d }) => <FigureRow list={list(section, d)} type={type} count={countOf(section, type)} />,
    isEmpty: (section, d) => list(section, d).length === 0,
  };
}
