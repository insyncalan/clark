// Item 1182 (was item 210's two lists): the rating picker of a risk or an issue in the table is the peek's 3 x 3 matrix (components/PeekRiskBody.jsx),
// the one matrix. A pick is sent as "High/Medium" (impact first); itemEdit.js changeFor turns it into the one change of both fields.
import { RatingMatrix } from "../../components/PeekRiskBody.jsx";

export function RatingPick({ row, anchor, onPick, onClose }) {
  return <RatingMatrix row={row} anchor={anchor} onPick={(impact, likelihood) => onPick(`${impact}/${likelihood}`)} onClose={onClose} />;
}
