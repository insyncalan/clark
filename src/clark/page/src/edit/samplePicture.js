// Row 1251: the sample pictures of an empty picture template (Classic only, Edit only). The six files are made by clark
// (src/clark/sample_images.py) and inlined here at build time (dev/tools/build_page.py, sample_pictures_path); the published page's
// build maps "clark-sample-pictures" to an empty list, so a published file holds none. A sample is drawn by the page and never saved.
import PICTURES from "clark-sample-pictures";

/** The data: URI of sample picture n (0 to 5, wrapping), or "" when there is none (the published page). */
export const samplePicture = (n = 0) => (PICTURES.length ? PICTURES[((n % PICTURES.length) + PICTURES.length) % PICTURES.length] : "");
