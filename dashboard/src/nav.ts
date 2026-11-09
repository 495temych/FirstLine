/** The dashboard's three groups, their views, and each view's link. */

export const groups = [
  {
    id: "try",
    label: "Try it",
    views: [
      { id: "queue", label: "Queue" },
      { id: "assistant", label: "Assistant" },
    ],
  },
  {
    id: "worth",
    label: "Is it worth it?",
    views: [
      { id: "money", label: "Money" },
      { id: "models", label: "Models" },
    ],
  },
  {
    id: "how",
    label: "How it works",
    views: [
      { id: "workflow", label: "Workflow" },
      { id: "harness", label: "Harness" },
      { id: "retrieval", label: "Retrieval" },
      { id: "tickets", label: "Tickets" },
      { id: "evaluations", label: "Evaluations" },
    ],
  },
] as const;

export type Group = (typeof groups)[number];
export type GroupId = Group["id"];
export type ViewId = Group["views"][number]["id"];

const VIEW_PARAM = "view";
const views: { id: ViewId; label: string }[] = [];
for (const g of groups) views.push(...g.views);

export const isView = (value: string | null): value is ViewId =>
  views.some((v) => v.id === value);

export const labelOf = (view: ViewId): string =>
  views.find((v) => v.id === view)?.label ?? view;

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
