import type { GroupId, ViewId } from "./nav";

/** One claim, the evidence behind it, and the view that shows it in full. */
export interface Finding {
  text: string;
  n: number | null;
  source: string;
  view: ViewId;
}

export type Insights = Record<
  GroupId,
  { question: string; findings: Finding[] }
>;
