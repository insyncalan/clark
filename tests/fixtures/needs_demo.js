// Test-only (tests/test_needs_page.py): the 'Needs from you' logic and the template list on a bare page, never part of clark's bundle.
import * as needs from "@src/logic/needs.js";
import * as templates from "@src/logic/templates.js";

window.N = { needs, templates };
