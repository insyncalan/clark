// Row 1223, Edit only: a JPEG or WebP original made a PNG, because clark cuts and shapes only a PNG (it makes the framed copy itself, from
// the original and the framing numbers). The page draws the original at its own size on a canvas; no framing is applied here. Resolves to
// { ok: true, data, width, height } or { ok: false, message }; never throws. clark checks it like every image when it is sent.
import { dataBytes } from "./shrink.js";
import { WORDS, MOST_BYTES } from "../../logic/fullImageWords.js";

function load(url) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = url;
  });
}

export async function pngOf(url, most = MOST_BYTES) {
  const img = await load(url);
  if (!img || !img.naturalWidth) return { ok: false, message: WORDS.unreadable };
  let scale = 1;
  for (let round = 0; round < 6; round++) {
    const width = Math.max(1, Math.round(img.naturalWidth * scale)), height = Math.max(1, Math.round(img.naturalHeight * scale));
    const canvas = document.createElement("canvas");
    canvas.width = width; canvas.height = height;
    canvas.getContext("2d").drawImage(img, 0, 0, width, height);
    const png = canvas.toDataURL("image/png");
    if (png.startsWith("data:image/png;base64,") && dataBytes(png) <= most) return { ok: true, data: png, width, height };
    scale *= 0.75;
  }
  return { ok: false, message: WORDS.tooBig };
}
