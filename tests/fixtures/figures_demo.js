// Test-only (tests/_tpl_figures.py): the Key figures templates' page side on a bare page, never part of clark's bundle.
import * as figures from "@src/templates/figures.js";
import * as safe from "@src/templates/safe.js";
import { TEMPLATE_PARTS } from "@src/templates/index.js";

window.F = { figures, safe, parts: Object.fromEntries(["figures4", "figures3"].map((t) => [t, { ready: TEMPLATE_PARTS[t].ready }])),
  empty: (type, section, data) => TEMPLATE_PARTS[type].isEmpty(section, data) };
