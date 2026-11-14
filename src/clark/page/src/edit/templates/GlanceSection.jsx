// The Edit part of the At a glance section (row 1190), store type "glance": the same Glance with the page's edit tools (grip, eye,
// outline, health pill, Reason), as the built-in drew it.
import { Glance } from "../../components/Glance.jsx";

export function Edit({ tools }) { return <Glance tools={tools} clean={tools.clean} />; }
