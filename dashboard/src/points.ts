import type { RetrievalTicket, ScoredSet } from "./api";

export interface Point {
  ticket: RetrievalTicket;
  covered: boolean;
  wrong: boolean;
  x: number;
  y: number;
}

/** Each ticket as a point: the score that should match against the best other one.
 * A family with no playbook plots its best score against the next. */
export function points(
  dev: ScoredSet | null,
  unseen: ScoredSet | null,
): Point[] {
  const covered = (dev?.tickets ?? []).flatMap((ticket) =>
    ticket.right_score === null || ticket.best_wrong_score === null
      ? []
      : [
          {
            ticket,
            covered: true,
            wrong: !ticket.hit,
            x: ticket.right_score,
            y: ticket.best_wrong_score,
          },
        ],
  );
  const uncovered = (unseen?.tickets ?? []).flatMap((ticket) => {
    const best = ticket.ranked.at(0);
    const next = ticket.ranked.at(1);
    return best && next
      ? [
          {
            ticket,
            covered: false,
            wrong: ticket.false_match,
            x: best.score,
            y: next.score,
          },
        ]
      : [];
  });
  return [...covered, ...uncovered];
}
