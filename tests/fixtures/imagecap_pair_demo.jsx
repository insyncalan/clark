// Test-only (tests/test_tpl_imagecap_pair_1223.py): two Images (the Image with caption's view part, body version 2) drawn as a pair of sections in
// the page's own grid (the real shell.css), with the slot classes the page's placement logic gives. Never part of clark's bundle.
import { render } from "preact";
import * as imagecap from "@src/templates/ImageCap.jsx";
import * as placement from "@src/logic/placement.js";

window.F = {
  mount: (list) => {
    const slot = placement.slots(list);
    render(
      <div class="secs">
        {list.map((s) => (
          <section class={`sec slot-${slot[s.id]}`} data-id={s.id} data-type="imagecap">
            <imagecap.View section={s} />
          </section>
        ))}
      </div>,
      document.getElementById("root"),
    );
  },
};
