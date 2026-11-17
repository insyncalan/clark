// Test-only (tests/test_tpl_gallery_view.py): the Image gallery's view part drawn into a bare page, never part of clark's bundle.
import { render } from "preact";
import * as gallery from "@src/templates/Gallery.jsx";

window.G = {
  shown: (v) => gallery.shown(v),
  isEmpty: (section) => gallery.isEmpty(section),
  ready: gallery.READY === true,
  mount: (section, cls) => {
    const root = document.getElementById("root");
    root.className = cls || "";
    render(null, root);
    render(<gallery.View section={section} />, root);
  },
};
