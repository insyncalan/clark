// Test-only (tests/test_tpl_imagecap_full_view.py): the Image with caption's view part (its version 2 body is the Full width image) drawn into a bare page, never part of clark's bundle.
import { render } from "preact";
import * as imagecap from "@src/templates/ImageCap.jsx";

window.F = {
  shown: (v) => imagecap.shown(v),
  isEmpty: (section) => imagecap.isEmpty(section),
  ready: imagecap.READY === true,
  mount: (section) => { render(<imagecap.View section={section} />, document.getElementById("root")); },
};
