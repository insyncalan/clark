// Test-only (tests/test_tpl_textimage_side_view.py): the Text and image view part (its version 2 body is Text and Image Side by Side) drawn into a bare page, never part of clark's bundle.
import { render } from "preact";
import * as textimage from "@src/templates/TextImage.jsx";

const root = () => document.getElementById("root");

window.F = {
  shown: (v) => textimage.shown(v, (h) => h),
  isEmpty: (section) => textimage.isEmpty(section),
  ready: textimage.READY === true,
  // slot "full" draws the section alone, "left" or "right" inside a half width cell as the page's grid makes it (class slot-left or slot-right).
  mount: (section, slot) => {
    const view = <textimage.View section={section} clean={(h) => h} />;
    render(slot === "left" || slot === "right" ? <div class={`slot-${slot}`} style="width:calc(50% - 12px)">{view}</div> : view, root());
  },
};
