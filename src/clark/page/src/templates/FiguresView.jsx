// The Key figures templates' shared view (#96): the figures in a row, drawn as the At a glance figures are. Text nodes only. The
// colour is never the only signal: the figure's words say it (aria-label), and the dot is decoration.
import { data } from "../stores/report.js";
import { todayIso } from "../workItems.js";
import { figuresOf, PLACES } from "./figures.js";

const WORDS = { g: "green", a: "amber", r: "red" };

export function FigureRow({ list, type }) {
  return (
    <div class={`tpl-figs n${PLACES[type]}`} data-figures={type}>
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

// The view part and isEmpty for one of the two templates.
export function figuresParts(type) {
  const list = (section, d) => figuresOf(section, d || data.value, todayIso(), PLACES[type]);
  return {
    View: ({ section, data: d }) => <FigureRow list={list(section, d)} type={type} />,
    isEmpty: (section, d) => list(section, d).length === 0,
  };
}
