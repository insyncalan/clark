// Test-only (tests/test_plan_summary_view_1251.py): a text Section drawn in View into a bare page, never part of clark's bundle.
import { render } from "preact";
import { Section } from "@src/components/Section.jsx";
import { emptyBody } from "@src/logic/emptyBody.js";

window.P = {
  emptyBody: (html) => emptyBody(html),
  mount: (body) => {
    const root = document.getElementById("root");
    render(null, root);
    render(<Section section={{ id: "ABC-S-091", type: "text", title: "ZQ plan summary", body }} index={0} count={1} clean={(h) => h} />, root);
  },
};
