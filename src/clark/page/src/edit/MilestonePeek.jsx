// Item 1184: the milestone editor's body moved to components/PeekMilestoneBody.jsx (the shared peek frame; the header line, state buttons and
// progress control are now the chip row drawn by Peek.jsx). MilestoneEdit is the same name the editor's tools offer.
export { MilestoneBody as MilestoneEdit, saveMilestone, said, DateField } from "../components/PeekMilestoneBody.jsx";
