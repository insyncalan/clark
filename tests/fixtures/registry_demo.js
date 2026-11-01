// Test-only (tests/test_section_registry.py): the section template registry's page side on a bare page, never part of clark's bundle.
import * as templates from "@src/logic/templates.js";
import * as publishable from "@src/logic/publishable.js";
import * as safe from "@src/templates/safe.js";
import { TEMPLATE_TYPES } from "@src/templates/types.js";
import { TEMPLATE_PARTS, templateFor, templateEmpty } from "@src/templates/index.js";
import { TEMPLATE_EDITS } from "@src/edit/templates/index.js";

window.T = {
  templates, publishable, safe, TEMPLATE_TYPES,
  parts: Object.fromEntries(Object.entries(TEMPLATE_PARTS).map(([t, p]) => [t, { ready: p.ready, view: typeof p.view, isEmpty: typeof p.isEmpty }])),
  edits: Object.fromEntries(Object.entries(TEMPLATE_EDITS).map(([t, e]) => [t, typeof e])),
  templateFor, templateEmpty,
};
