// Test-only (tests/test_picker_minimap.py): the pure logic and the two components on a bare page, never part of clark's
// bundle. window.T gives the tests the logic; mountMinimap and mountPicker draw the components with fictional data and
// record what their callbacks were given in T.jumped, T.added and T.closed.
import { render } from "preact";
import * as picker from "@src/logic/picker.js";
import * as minimap from "@src/logic/minimap.js";
import { showDate } from "@src/workItems.js";
import { Picker } from "@src/components/Picker.jsx";
import { Minimap } from "@src/components/Minimap.jsx";

const T = { picker, minimap, showDate, jumped: [], added: [], closed: 0 };
window.T = T;

const BAR = 48;

// A page of tall sections under a sticky bar, with the minimap beside it. `sections` as in report_sections.
T.mountMinimap = (sections, hiddenSections, noOnJump, counts) => {
  const root = document.getElementById("root");
  root.innerHTML = '<div id="bar" style="position:sticky;top:0;height:48px;background:var(--brand-navy);color:var(--white);z-index:30">bar</div><div id="page" style="padding-bottom:100vh"></div><div id="mm"></div><button id="after">after</button>';
  const page = document.getElementById("page");
  const shut = new Set(hiddenSections);
  for (const s of sections.filter((x) => !x.hidden && !shut.has(x.id))) {     // a hidden section is not on the page
    const sec = document.createElement("section");
    sec.id = minimap.anchorId(s.id);
    sec.style.cssText = "height:700px;padding:16px";
    const h = document.createElement("h2");
    h.textContent = s.title;                    // text, never markup
    sec.appendChild(h);
    page.appendChild(sec);
  }
  const onJump = (id) => {
    T.jumped.push(id);
    const e = minimap.entries(sections, hiddenSections).find((x) => x.id === id);
    const top = minimap.scrollTargets([{ id, top: document.getElementById(e.anchor).getBoundingClientRect().top + window.scrollY }], BAR)[id];
    window.scrollTo(0, top);
  };
  render(<Minimap sections={sections} hiddenSections={hiddenSections} stickyHeight={BAR} onJump={noOnJump ? undefined : onJump} counts={counts} />, document.getElementById("mm"));
};

T.mountPicker = (data, hiddenIds, onPage) => {
  const root = document.getElementById("root");
  root.innerHTML = '<div id="pk" style="padding:16px"></div>';
  render(<Picker data={data} hiddenIds={hiddenIds} onPage={onPage} onAdd={(ids) => T.added.push(ids)} onClose={() => { T.closed += 1; }} />, document.getElementById("pk"));
};
