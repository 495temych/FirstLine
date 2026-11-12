/** The dashboard's three groups, their views, and each view's link. */

export const groups = [
  {
    id: "try",
    label: "Try it",
    views: [
      {
        id: "queue",
        label: "Queue",
        question:
          "How would the agent work a morning's tickets, with a technician checking it?",
      },
      {
        id: "assistant",
        label: "Assistant",
        question: "What would FirstLine do with your ticket, and why?",
      },
    ],
  },
  {
    id: "worth",
    label: "Is it worth it?",
    views: [
      {
        id: "money",
        label: "Money",
        question:
          "Does it save more than it costs, and what would change that?",
      },
      {
        id: "models",
        label: "Models",
        question: "Which model should it run on, for the money?",
      },
    ],
  },
  {
    id: "how",
    label: "How it works",
    views: [
      {
        id: "workflow",
        label: "Workflow",
        question: "What happens to a ticket, from arrival to the last gate?",
      },
      {
        id: "harness",
        label: "Harness",
        question: "What does the model see, and what does code check after it?",
      },
      {
        id: "retrieval",
        label: "Retrieval",
        question: "Does search find the right playbook for a ticket?",
      },
      {
        id: "tickets",
        label: "Tickets",
        question:
          "Which tickets do we test on, and what is the right answer for each?",
      },
      {
        id: "evaluations",
        label: "Evaluations",
        question: "How well does it do on tickets with known answers?",
      },
    ],
  },
] as const;

export type Group = (typeof groups)[number];
export type GroupId = Group["id"];
export type ViewId = Group["views"][number]["id"];

const VIEW_PARAM = "view";
const views: { id: ViewId; label: string; question: string }[] = [];
for (const g of groups) views.push(...g.views);

export const isView = (value: string | null): value is ViewId =>
  views.some((v) => v.id === value);

export const labelOf = (view: ViewId): string =>
  views.find((v) => v.id === view)?.label ?? view;

/** The question a view answers, under its title. */
export const questionOf = (view: ViewId): string =>
  views.find((v) => v.id === view)?.question ?? "";

export function groupOf(view: ViewId): Group {
  return groups.find((g) => g.views.some((v) => v.id === view)) ?? groups[0];
}

/** The view a link opens: its `view`, or the Assistant for a paused run, or the
 * Queue, the core of the product. */
export function viewFrom(search: string): ViewId {
  const params = new URLSearchParams(search);
  const named = params.get(VIEW_PARAM);
  if (isView(named)) return named;
  return params.has("run") ? "assistant" : "queue";
}

/** The link to a view, keeping the rest of the address, such as a paused run. */
export function linkTo(view: ViewId, search: string): string {
  const params = new URLSearchParams(search);
  params.set(VIEW_PARAM, view);
  return `?${params.toString()}`;
}
