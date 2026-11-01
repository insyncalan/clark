// Key figures, four (#96), store type "figures4": its view part. Typed figures and live ones (the At a glance figures), drawn by FiguresView.jsx
// from section.body (the served page) or section.figures (the published file, already worked out). Text nodes only. Its Edit part
// is edit/templates/Figures4.jsx; the rules are section_kinds/figures4.py; tests/test_tpl_figures4.py.
import { figuresParts } from "./FiguresView.jsx";

export const READY = true;
export const { View, isEmpty } = figuresParts("figures4");
