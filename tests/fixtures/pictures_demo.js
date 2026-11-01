// Test-only (tests/test_tpl_textimage.py and the other Pictures group tests): the four picture templates' view parts and the shrink
// step on a bare page, never part of clark's bundle.
import * as textimage from "@src/templates/TextImage.jsx";
import * as imagecap from "@src/templates/ImageCap.jsx";
import * as gallery from "@src/templates/Gallery.jsx";
import * as headline from "@src/templates/Headline.jsx";
import { shrink, dataBytes } from "@src/edit/templates/shrink.js";
import { picturesTotal } from "@src/edit/templates/pictureEdit.jsx";

const parts = { textimage, imagecap, gallery, headline };
window.P = {
  shown: (type, value) => parts[type].shown(value),
  isEmpty: (type, section) => parts[type].isEmpty(section),
  ready: Object.fromEntries(Object.entries(parts).map(([t, m]) => [t, m.READY === true])),
  shrink, dataBytes, picturesTotal,
};
